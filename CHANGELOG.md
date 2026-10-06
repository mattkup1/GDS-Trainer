# Changelog

All notable changes to this project are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Contact email (`9E{ADDRESS}`)** — a second PNR contact field alongside
  phone, e.g. `9EJSMITH@EXAMPLE.COM`. Optional (unlike phone, not required to
  end transact), cancellable per-entry like a phone row, and copied - not
  moved - to both sides of a PNR divide. Shown in the dock's PNR panel under
  the same Contact section as phone, with its own icon.

### Changed

- **Browser edition redesign** — the web edition's outer chrome now models a
  modern GDS agent client instead of a green-phosphor CRT terminal: a menu
  bar, work-area tabs (`A`–`F`, only `A` active — this trainer models one
  session, not real multi-work-area sign-in), a command bar with a `SEND`
  button, a collapsible programmable-function-key row (`PF KEYS`), and a new
  `HELPER APPS` sidebar alongside the existing PNR/seat-map/encode-decode/
  format-finder dock — the dock's own 2x2 tab grid was removed in favor of
  it, since the two were a straight duplicate of each other; a plain label
  (not a second set of tabs) now shows which dock panel is visible. The
  `SCANLINES`/`SCREEN GLOW`/`SCREEN CURVATURE`
  settings are gone with the CRT look they controlled; `DISPLAY MODE`,
  `TEXT SIZE`, and the color-theme swatches (now `ACCENT COLOR`, restyled to
  drive interactive highlights only, not full-screen phosphor color) remain.
  No real GDS vendor names, branding, or logos are used anywhere in it.
  The File/Edit/View/Tools/Help menu bar is now fully functional (sign
  in/out, clear/reset, jump to a dock panel, Show/Hide checkmarked items for
  the dock and function keys, and read-only reference commands) rather than
  decorative labels, and the terminal/dock/helper-rail panels can be resized
  by dragging the dividers between them (persisted like any other display
  setting, with a `View > Reset Panel Sizes` item to restore the defaults).
  Dark/light mode and text size stay in exactly one place - the settings
  panel, reachable only via `View > Display Settings...` now (the separate
  `SETTINGS` toolbar button was removed) - rather than being duplicated as a
  second set of menu items.
- **PNR dock panel redesign** — the dock's PNR tab now renders as grouped,
  iconed cards (Passengers, Itinerary, Special Services, Pricing, Contact,
  Payment & Ticketing) instead of a flat list of padded monospace lines, so
  it reads like a reservation summary instead of a second copy of the
  terminal dump. The underlying text per element is unchanged - same
  formatters, same `X{n}` numbering - just presented with a section, an
  icon, and a card instead of raw columns.
- **Seat map dock panel polish** — the grid now centers in its own framed
  card instead of hugging the left edge with a wall of empty space beside
  it. The `Seat Map` entry point (helper-rail button and `Tools` menu item)
  is hidden entirely until at least one segment is on file, instead of
  silently bouncing to the PNR tab if clicked too early; once available, it
  defaults to the first segment automatically even if `4{N}` was never
  typed. An itinerary with more than one segment gets a row of tabs above
  the grid to switch between them (each one running that segment's real
  `4{N}` command, same as clicking an open seat does).
- **`File > Generate Itinerary/Invoice/E-Ticket`** — new menu items for
  `EM`/`EMI`/`EMT`, hidden until the PNR actually satisfies the same
  completeness gate submitting one of those commands would check. Like
  every other menu item that mutates the PNR, clicking one inserts the
  command and focuses the command line rather than running it immediately -
  these save and clear the work area exactly like `ET` does, so they're
  never a one-click action.

### Fixed

- On a double-decker aircraft's seat map (747-400/-8, A380), the "UPPER
  DECK"/"MAIN DECK" labels centered on the panel as a whole instead of on
  the seat grid beneath them, since the row-number column only exists on
  actual seat rows and threw the two off from a shared center by about
  14px.
- The dock's show/hide chevron sat right next to its resize handle, close
  enough that ordinary mouse imprecision routinely grabbed the handle's drag
  behavior instead of registering a click, making the button feel like it
  "didn't always work." An interim fix nested the button inside the handle
  to force it to unambiguously win its own pixels, but that traded the
  original problem for a subtler one: a mousedown landing on the button
  still shifted focus there before any drag intent was resolved, so trying
  to drag starting from the button produced a stuck-looking, half-pressed
  state with neither a clean click nor a clean drag. The button now lives
  fully outside the handle with real breathing room between them, matching
  how VS Code's and Chrome DevTools' sidebar toggles do it - a click target
  and a drag handle never share, or even lightly overlap, the same
  hit-region at all.
- Dragging the dock/helper-rail resizer wider could, mid-drag, cross the
  same width threshold that flips the layout into its narrow-viewport
  stacked mode - even though the *window* itself hadn't changed size, only
  the panel the user was actively resizing. Once that happened, the CSS
  driving stacked mode forces the dock's width via `!important`, so the drag
  appeared to "stop working, only move a tiny bit," and its `mouseup`
  handler would then read back and save that CSS-forced full-width value as
  the persisted dock width - corrupting it so the broken, stuck-stacked
  layout survived a reload, and the show/hide chevron looked like it
  "stopped revealing the panel" afterward (it was toggling visibility fine,
  just onto a wrecked layout). A resize drag is now clamped so it can never
  itself trigger that flip; a window that's genuinely too narrow still
  stacks normally, same as before.
- The `View > Display Settings...` menu item opened the settings panel and
  then immediately closed it again on the same click (the click event kept
  bubbling to the same "close on an outside click" listener the panel
  already had).
- A dock/helper-rail width dragged (or restored from a saved) wide enough
  could squeeze the terminal down to an unreadably narrow column while
  still reporting a "wide" viewport, since the browser/dock stacked layout
  only ever kicked in below a fixed 900px window width - the command bar's
  buttons could clip and terminal text could wrap mid-word well above that.
  The stacking (and command-bar-wrapping) decision is now computed from the
  terminal's actual available width instead of a fixed breakpoint.
- A lap-infant date typed with a 4-digit year (e.g. `(INFDOE/BABY/25DEC2026)`
  instead of the expected `25DEC26`) silently fell through to the plain
  name-splitting logic and surfaced a baffling "PARTY SIZE EXCEEDS SEATS
  SOLD" error instead of a format error. Both editions now recognize a
  malformed `(INF...)` clause and report the actual problem.

## [1.1.0] — 2026-09-23

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

[1.1.0]: https://github.com/mattkup1/GDS-Trainer/releases/tag/v1.1.0
[1.0.0]: https://github.com/mattkup1/GDS-Trainer/releases/tag/v1.0.0
