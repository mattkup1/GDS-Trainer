#!/usr/bin/env python3
"""Generate the browser's <script src> wrapper files from spec/*.json.

The browser app can't fetch() local JSON reliably (Chrome blocks it under
CORS when index.html is opened via file://) and this project deliberately
has no bundler/build step (see root CLAUDE.md), so each spec file gets a
plain `const NAME = {...};` wrapper the browser loads as a global. Python
just reads the JSON files directly at runtime - only the browser needs this.

Run after editing anything in spec/:

    python3 spec/build.py
"""

from __future__ import annotations

import json
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SPEC_DIR.parent
OUT_DIR = REPO_ROOT / "web" / "generated"

# (spec json filename, generated js filename, global const name, header comment)
TARGETS = [
    (
        "airports.json",
        "airports.js",
        "AIRPORTS",
        "// Auto-generated from spec/airports.json (source: OpenFlights public dataset,\n"
        "// https://github.com/jpatokal/openflights) - IATA code -> [name, city, country].\n"
        "// Edit spec/airports.json and re-run spec/build.py, don't hand-edit this file.",
    ),
    (
        "reference-data.json",
        "reference-data.js",
        "REFERENCE_DATA",
        "// Auto-generated from spec/reference-data.json - edit that file and re-run\n"
        "// spec/build.py, don't hand-edit this file.",
    ),
    (
        "command-grammar.json",
        "command-grammar.js",
        "COMMAND_GRAMMAR",
        "// Auto-generated from spec/command-grammar.json - edit that file and re-run\n"
        "// spec/build.py, don't hand-edit this file.",
    ),
    (
        "pnr-completeness.json",
        "pnr-completeness.js",
        "PNR_COMPLETENESS",
        "// Auto-generated from spec/pnr-completeness.json - edit that file and re-run\n"
        "// spec/build.py, don't hand-edit this file.",
    ),
]


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    for json_name, js_name, const_name, header in TARGETS:
        data = json.loads((SPEC_DIR / json_name).read_text(encoding="utf-8"))
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        out_path = OUT_DIR / js_name
        out_path.write_text(f"{header}\nconst {const_name} = {payload};\n", encoding="utf-8")
        print(f"wrote {out_path.relative_to(REPO_ROOT)} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
