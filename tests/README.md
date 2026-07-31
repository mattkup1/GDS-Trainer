# tests/

Cross-edition test suite for GDS Trainer — the shared scenarios both the browser
and CLI editions must honor identically. Python-only unit tests for the CLI's
own internals (`rng.py`, `dates.py`, `util.py`, a few `commands.py` helpers)
live alongside the package instead, in `../gds-trainer-cli/tests/`.

## Prerequisite

```bash
cd gds-trainer-cli
python3 -m venv .venv          # if you haven't already
source .venv/bin/activate
pip install -e ".[dev]"        # pulls in pytest
```

The web scenario tests also need Google Chrome installed at the standard macOS
location (`/Applications/Google Chrome.app/...`) — same requirement the
`docs/GDS-TRAINER-BOOKING-GUIDE.pdf` regen step already has (see `CLAUDE.md`).
No other dependency: `tests/cdp.py` is a stdlib-only Chrome DevTools Protocol
client (no `selenium`/`playwright`), since neither is installed in this
environment and the browser edition itself has no build tooling to lean on.

## Running

With the venv active, from the repo root:

```bash
pytest gds-trainer-cli/tests     # fast: unit tests only, no Chrome, run on every change
pytest tests                     # cross-edition scenarios + real-browser E2E (needs Chrome)
pytest                           # everything (testpaths configured in root pyproject.toml)
```

## What's here

- **`scenarios.py`** — the shared `Scenario`/`Step` list: sign-in gate, full
  booking flow through ticketing, party-size validation, lap-infant exemption,
  SSR accept/reject, phone format accept/reject, seat re-assignment rejection,
  cancel forms (single/range/list/whole-itinerary), `ER` vs `ET`, PNR and
  ticketing completeness gates, retrieve-by-locator, invalid-entry fallback,
  `HELP` sanity, airport encode/decode.
- **`cdp.py`** — the minimal CDP client. `ChromeSession.run_commands()` drives
  the real `#cmdline` input with real `keydown` events (exactly like a user
  typing + pressing Enter) and returns the accumulated `#output` transcript;
  `split_transcript()` slices that transcript on each `> COMMAND` echo line so
  each step's output can be checked independently. `ChromeSession.reset()`
  clicks the page's own `#btnReset` button between scenarios rather than
  re-navigating — `Page.navigate` hands back control before the new page's
  execution context is actually ready, which races the very next
  `Runtime.evaluate` call; clicking a button on the already-loaded page has no
  such race.
- **`test_cli_scenarios.py`** — runs `SCENARIOS` against
  `gds_trainer.dispatcher.process_command` directly, capturing output via a
  `printer.console` swapped to a `StringIO`-backed `rich.Console`.
- **`test_web_scenarios.py`** — runs the identical `SCENARIOS` against
  `web/index.html` via a single reused headless Chrome instance.

## Why assertions are structural, not exact-value

Fares, seat occupancy, ticket serial numbers, and record locators are
independently random per edition by design (see `CLAUDE.md`'s "Shared rules
core" section) — same seeded-RNG *algorithm* and *inputs* in both editions,
but never required to bit-match across languages. So every `Step` asserts on
**message substrings and structural outcomes** ("party size" error appears,
"SEAT ASSIGNED" does *not* appear on a repeat assignment, an element count
changes) — never on a specific fare total or seat letter.

## Adding a scenario

Add a `Scenario` to `scenarios.py`'s `SCENARIOS` list — both suites pick it up
automatically via parametrization, no other file needs touching. Reuse the
`Step` fragments already defined near the top of that file (`SIGN_IN`,
`AVAIL_DFW_ORD`, etc.) where they fit, so a change to a shared setup step
(e.g. the availability example route) only needs updating once.

## CI

`.github/workflows/tests.yml` runs `pytest` from the repo root on every push
to `main` and every pull request. GitHub-hosted runners are Linux, so
`cdp.py`'s `default_chrome_path()` doesn't find the macOS install path there —
the workflow provisions Chrome via `browser-actions/setup-chrome` and passes
its path through the `GDS_TRAINER_TEST_CHROME` env var, which
`default_chrome_path()` checks first before falling back to the macOS path or
scanning `PATH` for common Linux Chrome/Chromium binary names. Same env var
works for local Linux dev, not just CI.

## What's *not* covered here

JS-internals unit testing — `web/script.js` has no build step/exports to
unit-test against without adding tooling the project has deliberately avoided
(see `CLAUDE.md`), so the browser edition's coverage is E2E-only, via
`test_web_scenarios.py`.
