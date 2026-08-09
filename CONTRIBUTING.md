# Contributing to GDS Trainer

Thanks for taking a look. This is a small, deliberately dependency-free
project — the bar for a good contribution is that it stays that way.

## Before you start

- **Read [`spec/README.md`](spec/README.md) if you're touching command
  grammar, reference data, airport data, or PNR-completeness rules.** Both
  editions (`web/` and `gds-trainer-cli/`) read the same files in `spec/` —
  edit those, not the generated copies in `web/generated/`, and regenerate
  with `python3 spec/build.py` before committing.
- **Read [`tests/README.md`](tests/README.md)** for how the cross-edition
  test suite works. Both editions loop over the identical command grammar
  precisely so they can't drift apart — a change to one should almost always
  come with the matching change to the other.

## Setup

```bash
cd gds-trainer-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The browser edition needs no install — open `web/index.html` directly.

## Making a change

1. If it touches shared rules/data, edit `spec/*.json` first, then run
   `python3 spec/build.py` and commit the regenerated `web/generated/*.js`
   files alongside it.
2. Implement the behavior in both `web/script.js` and
   `gds-trainer-cli/gds_trainer/` if it's a command or PNR behavior — see
   `CLAUDE.md` for the dispatcher pattern each edition uses.
3. Add or update a scenario in `tests/scenarios.py` (runs against both
   editions) or a unit test in `gds-trainer-cli/tests/` if the change is
   CLI-internals-only.
4. From the repo root:
   ```bash
   pytest
   ```
   This needs Chrome/Chromium installed for the browser-edition scenario
   tests — see `tests/README.md` if that's not available locally.

## Pull requests

- Keep them focused — one behavior or fix per PR.
- CI (`.github/workflows/tests.yml`) runs the full suite on every PR; it
  needs to be green before merge.
- Match the existing code style: no comments beyond what explains a
  non-obvious *why*, no speculative abstraction for hypothetical future
  needs.

## Reporting a bug or requesting a feature

Open an issue with the command sequence that reproduces it (or the behavior
you'd like to see) — since all data is synthetic and deterministic, a
reproduction is almost always just "these commands, in this order."
