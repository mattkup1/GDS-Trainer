"""Minimal Chrome DevTools Protocol (CDP) client, stdlib only.

Drives a real headless Chrome to exercise web/index.html exactly like a user
would - setting the #cmdline input's value and dispatching a real 'keydown'
Enter event, then reading back #output's rendered text - rather than reaching
into script.js's internals (which aren't exposed; it's a single IIFE with no
exports, by design - see spec/README.md and CLAUDE.md).

No browser-automation library (selenium/playwright) is installed in this
environment, and none is added here - this is deliberately dependency-free
beyond Chrome itself, which the project already requires for the PDF-guide
regen step (see CLAUDE.md).
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

CHROME_ENV_VAR = "GDS_TRAINER_TEST_CHROME"
_MAC_CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_LINUX_CHROME_NAMES = ("google-chrome-stable", "google-chrome", "chromium-browser", "chromium")


def default_chrome_path() -> str:
    """Resolve a Chrome/Chromium binary, in priority order:
    1. $GDS_TRAINER_TEST_CHROME (CI sets this to browser-actions/setup-chrome's
       output path - see .github/workflows/tests.yml - since GitHub-hosted
       runners are Linux, not macOS, and shouldn't rely on the mac install path).
    2. The standard macOS install location (this project's primary dev
       environment).
    3. Common Linux binary names, resolved via PATH.
    Always returns a string (best guess) rather than raising - ChromeSession.start()
    is what actually surfaces a clear error if the returned path doesn't work,
    including everything that was tried.
    """
    env_override = os.environ.get(CHROME_ENV_VAR)
    if env_override:
        return env_override
    if Path(_MAC_CHROME_PATH).exists():
        return _MAC_CHROME_PATH
    for name in _LINUX_CHROME_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return _MAC_CHROME_PATH


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ChromeSession:
    """A single headless Chrome process, reused across many test scenarios."""

    def __init__(self, chrome_path: str | None = None):
        self._chrome_path = chrome_path if chrome_path is not None else default_chrome_path()
        self._proc: subprocess.Popen | None = None
        self._profile_dir: str | None = None
        self._sock: socket.socket | None = None
        self._msg_id = 0

    # ---------- lifecycle ----------

    def start(self, url: str, timeout: float = 15.0) -> None:
        resolved = self._chrome_path if Path(self._chrome_path).exists() else shutil.which(self._chrome_path)
        if not resolved:
            raise RuntimeError(
                f"Chrome not found (tried {self._chrome_path!r}) - required for the web edition's "
                f"test suite (tests/README.md). Install Chrome/Chromium, or set ${CHROME_ENV_VAR} "
                "to its executable path."
            )
        self._chrome_path = resolved
        port = _free_port()
        self._profile_dir = tempfile.mkdtemp(prefix="gds-trainer-test-chrome-")
        self._proc = subprocess.Popen(
            [
                self._chrome_path,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                f"--remote-debugging-port={port}",
                "--no-first-run",
                f"--user-data-dir={self._profile_dir}",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ws_url = self._wait_for_ws_url(port, timeout)
        self._connect(ws_url)
        self.call("Runtime.enable")
        self._wait_ready(timeout)

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None
        if self._profile_dir is not None:
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None

    def __enter__(self) -> "ChromeSession":
        return self

    def __exit__(self, *_exc_info) -> None:
        self.close()

    # ---------- connection setup ----------

    def _wait_for_ws_url(self, port: int, timeout: float) -> str:
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1) as resp:
                    targets = json.loads(resp.read())
                for t in targets:
                    if t.get("type") == "page":
                        return t["webSocketDebuggerUrl"]
            except Exception as e:  # noqa: BLE001 - Chrome may not be listening yet
                last_error = e
            time.sleep(0.2)
        raise RuntimeError(f"Chrome DevTools endpoint never became available: {last_error}")

    def _connect(self, ws_url: str) -> None:
        u = urlparse(ws_url)
        sock = socket.create_connection((u.hostname, u.port))
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {u.path} HTTP/1.1\r\n"
            f"Host: {u.hostname}:{u.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(4096)
        self._sock = sock

    def _wait_ready(self, timeout: float) -> None:
        """Wait until boot() has actually run and printed the banner - not just
        until #cmdline/#output exist in the DOM. Static markup for both elements
        is present the instant HTML parsing reaches them, which can be well
        before the <script> tags at the end of body have executed; checking only
        for element existence risks reading a page that's present but not yet
        booted."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            ready = self.evaluate("document.querySelectorAll('#output .line').length > 0")
            if ready:
                return
            time.sleep(0.2)
        raise RuntimeError("web/index.html never finished booting (#output has no .line children)")

    # ---------- raw CDP framing ----------

    def _send_frame(self, data: bytes) -> None:
        header = bytearray([0x81])  # FIN + text frame
        length = len(data)
        if length <= 125:
            header.append(0x80 | length)
        elif length <= 65535:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask_key = os.urandom(4)
        masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
        self._sock.sendall(bytes(header) + mask_key + masked)

    def _recv_frame(self) -> tuple[int, bytes]:
        def recv_exact(n: int) -> bytes:
            buf = b""
            while len(buf) < n:
                chunk = self._sock.recv(n - len(buf))
                if not chunk:
                    raise ConnectionError("CDP socket closed unexpectedly")
                buf += chunk
            return buf

        b0, b1 = recv_exact(2)
        opcode = b0 & 0x0F
        masked = b1 & 0x80
        length = b1 & 0x7F
        if length == 126:
            length = struct.unpack(">H", recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack(">Q", recv_exact(8))[0]
        mask_key = recv_exact(4) if masked else None
        payload = recv_exact(length)
        if masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def call(self, method: str, params: dict | None = None, timeout: float = 10.0) -> dict:
        self._msg_id += 1
        msg_id = self._msg_id
        self._send_frame(json.dumps({"id": msg_id, "method": method, "params": params or {}}).encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            opcode, payload = self._recv_frame()
            if opcode == 0x8:
                raise ConnectionError("CDP connection closed by Chrome")
            if opcode != 0x1:
                continue
            msg = json.loads(payload.decode())
            if msg.get("id") == msg_id:
                return msg
        raise TimeoutError(f"no CDP response to {method} within {timeout}s")

    # ---------- test-facing API ----------

    def evaluate(self, expression: str):
        result = self.call(
            "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True}
        )
        if "error" in result:
            raise RuntimeError(result["error"])
        r = result["result"]["result"]
        if r.get("subtype") == "error":
            raise RuntimeError(result["result"])
        return r.get("value")

    def reset(self, timeout: float = 15.0) -> None:
        """Reset app state between scenarios by clicking the page's own #btnReset
        button - the same "RESET SESSION" affordance a real user has - rather
        than re-navigating. CDP's Page.navigate hands back control before the
        new page's execution context is actually ready, which races with the
        very next Runtime.evaluate call and silently evaluates against a stale
        context; clicking a button on the already-loaded page has no such
        navigation/context-switch to race against.
        """
        self.evaluate("document.getElementById('btnReset').click()")
        self._wait_ready(timeout)

    def run_commands(self, commands: list[str]) -> str:
        """Drive the real #cmdline input with real keydown events, one per command
        (exactly like a user typing + pressing Enter), and return the full
        accumulated #output transcript.

        Reconstructs line-separated text from each .line div's textContent rather
        than reading #output.innerText directly - innerText depends on layout/paint
        having completed, which races with Runtime.evaluate in headless Chrome and
        can return '' even when the DOM is already fully populated.
        """
        driver_js = """
        (function(cmds) {
            const input = document.getElementById('cmdline');
            for (const cmd of cmds) {
                input.value = cmd;
                const ev = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true });
                input.dispatchEvent(ev);
            }
            return Array.from(document.querySelectorAll('#output .line'))
                .map(el => el.textContent)
                .join('\\n');
        })(%s)
        """ % json.dumps(commands)
        return self.evaluate(driver_js)


def split_transcript(full_text: str, commands: list[str]) -> list[str]:
    """Split a full #output transcript into per-command chunks, each starting
    right after that command's '> COMMAND' echo line and running up to (not
    including) the next echo line. len(result) == len(commands)."""
    chunks: list[str] = []
    lines = full_text.split("\n")
    echo_prefixes = [f"> {cmd.strip().upper()}" for cmd in commands]
    start_indices: list[int] = []
    search_from = 0
    for prefix in echo_prefixes:
        idx = None
        for i in range(search_from, len(lines)):
            if lines[i].strip() == prefix:
                idx = i
                break
        if idx is None:
            raise AssertionError(f"could not find echoed command line {prefix!r} in transcript")
        start_indices.append(idx)
        search_from = idx + 1
    for i, start in enumerate(start_indices):
        end = start_indices[i + 1] if i + 1 < len(start_indices) else len(lines)
        chunks.append("\n".join(lines[start + 1 : end]))
    return chunks
