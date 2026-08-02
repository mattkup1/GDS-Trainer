# spec/

The single source of truth for the business rules shared by both GDS Trainer
editions — the browser app (`../web/`) and the CLI (`../gds-trainer-cli/`).
Edit files here; don't hand-edit the generated `.js` copies in `../web/generated/`.

## Files

- **`reference-data.json`** — SSR codes, card types, equipment, classes,
  class-fare multipliers, tax pool, phone location codes, months/weekdays,
  and the fare-pricing formula's tunable constants (`fareFormula`). The
  pricing *algorithm* (multiply/round/accumulate against each edition's own
  seeded RNG) still lives in each codebase — only its numbers live here.
- **`airlines.json`** — IATA code → `{name, numericCode}`, one object per
  carrier this sim generates flights for. Kept separate from
  `reference-data.json` (it used to be three parallel structures in there —
  a code list plus two side maps keyed by the same codes — which only grows
  more error-prone to keep in sync as more per-airline fields get added).
- **`airline-logos/`** — optional real airline logo images, one per carrier,
  named by lowercase IATA code (`aa.svg`, `dl.png`, ...). **Gitignored except
  for its own `README.md`** — these are real trademarked/copyrighted assets,
  not something this repo distributes. `spec/build.py` inlines whatever's
  present as base64 data URIs into `web/generated/airline-logos.js` (also
  gitignored); any carrier without a file there just gets the generated
  colored-badge placeholder instead (`airlineBadgeSVG` in `web/script.js`).
  Browser-only — the CLI edition has no GUI to show a logo in.
- **`pnr-completeness.json`** — the ordered `{field, check, message}` rules
  `endTransaction`/`end_transaction` and `issueTickets`/`issue_tickets` walk
  to decide whether a PNR is complete. `check` is one of `non_empty` (array
  has at least one element), `present` (value is not null/None), `empty`
  (array has zero elements).
- **`command-grammar.json`** — the ordered list of `{name, pattern, handler}`
  entries both dispatchers loop over. `pattern` is a regex source string
  valid in both JS `RegExp` and Python `re` (checked: no named groups, no
  lookbehind, nothing engine-specific) — first match wins, same as the
  original hand-written `if/elif` chain. `handler` is an UPPER_SNAKE token;
  each edition maps tokens to its own local function via a lookup table.
  Every handler is called as `handler(rawInput, ...captureGroups)` — the
  full matched command string first, then whatever the pattern captured
  (`None`/`undefined` for unmatched optional groups).
- **`airports.json`** — IATA code → `[name, city, country]`, converted once
  from the OpenFlights public dataset.

## How each edition consumes this

- **Python** (`gds-trainer-cli/gds_trainer/`) loads these JSON files
  directly at runtime (`json.load`) via a relative path up to `spec/` —
  no build step needed, no bundling. This only works run from a repo
  checkout (editable install), which matches how the CLI is installed today.
- **Browser** (`web/script.js`) can't `fetch()` local JSON reliably — Chrome
  blocks it under CORS when `web/index.html` is opened via `file://`, and this
  project deliberately has no bundler or build step (see root `CLAUDE.md`).
  So the browser instead loads generated `.js` wrapper files
  (`const REFERENCE_DATA = {...};` etc.) from `../web/generated/` via plain
  `<script src>` tags in `web/index.html`.

## Regenerating the `.js` wrappers

After editing any file in `spec/`, regenerate the `web/generated/` copies:

```bash
python3 spec/build.py
```

This writes `web/generated/airports.js`, `web/generated/reference-data.js`,
`web/generated/airlines.js`, `web/generated/command-grammar.js`, and
`web/generated/pnr-completeness.js`. Commit the regenerated files alongside
your `spec/` edit — there's no CI step that does this for you.

It also writes `web/generated/airline-logos.js` from whatever's in
`spec/airline-logos/`, but **don't commit that one** — it's gitignored
along with its source images (see `airline-logos/README.md` above). Run
the build after adding/removing a logo file same as any other `spec/`
edit; the app just works with fewer real logos (falls back to the
placeholder badge) if you don't.
