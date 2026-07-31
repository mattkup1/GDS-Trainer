# gds-trainer-cli

Terminal (CLI) edition of **GDS Trainer**, alongside the browser edition in `../web/`. Same
industry-standard GDS entry mnemonics (sign-in, availability, sell, PNR build, pricing,
SSR/OSI, seats, ticketing, end transaction) and the same deterministic
seeded-PRNG synthetic flight data, in a Python REPL instead of a browser page.

## Install & run

```bash
cd gds-trainer-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
gds-trainer
```

Type `SI` to sign in, then `HELP` for the full command reference.
