# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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

[1.0.0]: https://github.com/mattkup1/GDS-Simulator/releases/tag/v1.0.0
