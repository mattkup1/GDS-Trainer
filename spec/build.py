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

import base64
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
        "airlines.json",
        "airlines.js",
        "AIRLINES_DATA",
        "// Auto-generated from spec/airlines.json - edit that file and re-run\n"
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

# code (lowercase filename stem) -> (extension, MIME type), preference order
LOGO_MIME_TYPES = {
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def build_targets() -> None:
    for json_name, js_name, const_name, header in TARGETS:
        data = json.loads((SPEC_DIR / json_name).read_text(encoding="utf-8"))
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        out_path = OUT_DIR / js_name
        out_path.write_text(f"{header}\nconst {const_name} = {payload};\n", encoding="utf-8")
        print(f"wrote {out_path.relative_to(REPO_ROOT)} ({len(payload)} bytes)")


def build_airline_logos() -> None:
    """Inlines spec/airline-logos/{code}.{svg,png,jpg} as base64 data URIs into
    web/generated/airline-logos.js. Unlike everything else this script writes,
    both the source images and this generated file are gitignored (see
    spec/airline-logos/README.md) - real airline logos are trademarked/
    copyrighted assets this repo doesn't want to distribute. Missing entries
    just mean the browser falls back to the generated placeholder badge for
    that carrier (see airlineBadgeSVG in web/script.js), so it's fine for
    this to produce an empty map on a fresh checkout.
    """
    codes = list(json.loads((SPEC_DIR / "airlines.json").read_text(encoding="utf-8")).keys())
    logos_dir = SPEC_DIR / "airline-logos"

    found: dict[str, str] = {}
    for code in codes:
        for ext, mime in LOGO_MIME_TYPES.items():
            path = logos_dir / f"{code.lower()}.{ext}"
            if path.is_file():
                b64 = base64.b64encode(path.read_bytes()).decode("ascii")
                found[code] = f"data:{mime};base64,{b64}"
                break

    payload = json.dumps(found, ensure_ascii=False, separators=(",", ":"))
    out_path = OUT_DIR / "airline-logos.js"
    header = (
        "// Auto-generated from spec/airline-logos/ - gitignored, not committed (see\n"
        "// spec/airline-logos/README.md). Regenerate with spec/build.py after adding\n"
        "// or removing logo files."
    )
    out_path.write_text(f"{header}\nconst AIRLINE_LOGOS = {payload};\n", encoding="utf-8")
    missing = sorted(set(codes) - found.keys())
    print(f"wrote {out_path.relative_to(REPO_ROOT)} ({len(found)}/{len(codes)} carriers have a logo file"
          f"{', missing: ' + ', '.join(missing) if missing else ''})")


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    build_targets()
    build_airline_logos()


if __name__ == "__main__":
    main()
