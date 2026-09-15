# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Child fare (`(CHD)` name suffix)** — a `CNN`-style passenger type distinct
  from a lap infant: a fully named, seat-occupying passenger priced at a
  discount off the adult base fare (`fareFormula.childFareMultiplier`).
  Tagged per-passenger within a multi-name entry, e.g.
  `-SMITH/JOHN MR/JOHNNY MSTR(CHD)`; `WP`/`WPNCS` split each segment's fare
  between adult and child portions accordingly.
- **Light mode** — a theme toggle alongside the existing glow/scanline
  settings, persisted the same way via `localStorage`.
- **Codeshare flights** — availability/schedule display and the PNR now show
  a flight's operating carrier when it differs from the marketing carrier
  (`OPERATED BY {NAME} ({CODE}{NUM})`), matching real GDS availability.
  Deterministic per flight, derived from a seed independent of the shared
  availability RNG stream so it can't perturb any other generated value.
- **Fuller fare rules** — each booking class's fare rules gained a
  cancellation fee (distinct from the change fee), minimum stay, and maximum
  stay, shown in `FQ.../{CLASS}`, `WP`/`WPNCS`, and the itinerary document.
  `TKTR` now deducts the cancellation fee from the refund amount instead of
  always refunding the fare in full.
- **Flexible-date availability (`AF{DD}{MMM}{ORIG}{DEST}`)** — a fare-calendar
  view showing the lowest indicative fare per day across a ±3 day window
  around the given date, nonstop only, not bookable directly (search that
  date with `A` to book).

### Fixed

- SSR and `3FQTV` entries with an explicit `-{PAX#}` of `0` are now rejected
  (`INVALID PASSENGER NUMBER`) instead of silently accepted, in both editions.
- `HELP` output in both editions now lists the `DEPS`/`EXST`/`CBBG`/`STCR` SSR
  codes (previously present in `spec/reference-data.json` and usable, just
  missing from the printed reference).
- The cross-edition test suite now freezes "today" (`tests/conftest.py`'s
  `FROZEN_TODAY`) for both editions instead of letting it float with the real
  wall-clock date. `scenarios.py` hardcodes flight numbers, seat availability,
  and connection line numbers the shared seeded PRNG produces for specific
  bare `{DD}{MMM}` command dates (there's no year in that syntax — both
  editions resolve it to the next future occurrence relative to "today"), so
  once real time crossed one of those dates (e.g. `15AUG`) mid-year, the same
  command silently resolved to next year and generated different flights,
  breaking the suite. See `tests/conftest.py` and `tests/cdp.py` for the fix.

## [1.0.0] — 2026-08-09

First tagged release. GDS Trainer had already grown into a full two-edition
simulator before this point; this release is the line where the project
picked up the packaging a public repo needs — README, license, CI badge,
and a first version number — rather than a specific feature milestone.

### Highlights

- **Two editions, one shared rules core** — a browser edition (`web/`, no
  build step) and a Python CLI edition (`gds-trainer-cli/`), both driven by
  the same command grammar, reference data, and PNR-completeness rules in
  `spec/`, so behavior can't drift between them.
- **Full PNR lifecycle** — sign-in, availability (nonstop and connections),
  sell, multi-passenger name fields (incl. lap infants and group `TBA/TBA`
  placeholders), phone/received-from, SSR/OSI/frequent-flyer, seat maps
  (including multi-deck aircraft), pricing (`WP`), ticketing arrangement,
  form of payment, ticket issuance/void/refund/exchange, PNR divide, queues,
  and end transaction — all against deterministic, seeded-PRNG synthetic
  flight and fare data.
- **Realism touches** — minimum connect time enforcement, overnight (`+N`)
  arrivals, schedule changes and waitlist clearing on save, baggage
  allowance, married-segment connection tracking, and generated
  itinerary/invoice/e-ticket documents.
- **Browser GUI chrome** — a persistent dock (PNR view, seat map,
  encode/decode, format finder) alongside the terminal, plus a standalone
  command-recall quiz (`quiz/`).
- **Cross-edition test suite** — shared scenarios run against both the CLI
  directly and the browser edition over real headless Chrome (DevTools
  Protocol, stdlib-only), wired into CI on every push and PR.
- **Documentation** — a step-by-step booking walkthrough, a printable
  booking guide, and printable training scenarios in `docs/`.

[1.0.0]: https://github.com/mattkup1/GDS-Trainer/releases/tag/v1.0.0
