# Special Keys Guide

GDS Trainer uses four non-alphanumeric characters as control keys, the same way a real GDS terminal does — each one changes how the rest of an entry is read, rather than being part of the data itself. This guide covers exactly what each one does here, with every character's own ASCII-friendly fallback (most US keyboards don't have a dedicated key for `¥`/`‡`/`¤`, so every one of them can be typed as a plain keyboard character instead).

Works the same in both editions — type `HELP` at any time for a condensed version of this same reference.

---

## Quick reference

| Key | Name | Fallback | Does |
|---|---|---|---|
| `*` | Display key | — | Retrieves or displays PNR data |
| `¥` | Item delimiter | `/` | Separates an optional filter/qualifier from the rest of an availability entry |
| `‡` | Chain key | *(none — see below)* | Runs several commands from one typed line |
| `¤` | Change key | `~` | Edits one line of a field in place |

`¥`, `‡`, and `¤` only ever mean something at a specific position in an entry — none of them are ever valid as ordinary data (a name, a remark, a phone number), so there's no ambiguity with free text.

---

## Typing the real characters

Every one of `¥`/`‡`/`¤` has an ASCII fallback specifically so you never *have* to type the real character — but if you want to, same as a real GDS terminal's own keymap would let you, here's how.

**Browser edition — in-app shortcuts.** Press the combo with the cursor in the command line; it inserts the real character right there, same as typing any other key:

| Press | Inserts |
|---|---|
| `Ctrl` + `[` | `¥` |
| `Ctrl` + `]` | `¤` |
| `Ctrl` + `\` | `‡` |

**CLI edition and general OS-level input.** These work in *any* text field on your system, not just this app — the terminal just passes along whatever your OS sends it:

- **Windows** — hold `Alt` and type the code on the numeric keypad: `0165` for `¥`, `0164` for `¤`, `0135` for `‡`.
- **Mac** — `Option+Y` types `¥` directly; for `¤` and `‡`, press `Control+Command+Space` to open Character Viewer and search by name ("currency sign," "double dagger").
- **Any platform** — copy the character straight out of this guide, or out of `HELP`'s own output in either edition, and paste it in.

The CLI edition doesn't get the same `Ctrl+[`/`Ctrl+]`/`Ctrl+\` shortcuts as the browser — a raw terminal can't distinguish `Ctrl+[` from pressing `Escape` itself (both send the identical byte), so binding it there would be unreliable rather than just inconvenient.

---

## `*` — Display key

Retrieves or displays something — never mutates the PNR by itself.

```
*R          Redisplay the current PNR
*H          Display the PNR's chronological activity history
*ABC123     Retrieve a saved PNR by its record locator
```

Partial displays show just one category of PNR element instead of the whole thing — same absolute element numbers a full `*R` would show, so `X{N}` cancellation still works against them directly:

```
*I    Itinerary (segments) only
*N    Names only
*P    Contact fields only (phone + email)
*T    Ticketing only (arrangement + issued tickets)
*PE   Email only
*FF   Frequent flyer numbers only
*PQ   Price quote only
*B    Baggage allowance only (once the itinerary's been priced)
```

---

## `¥` — Item delimiter

Separates an optional filter/qualifier from the entry it modifies. Used in exactly two places, both on availability searches:

**Airline filter** — only show flights on one carrier, appended after any availability entry (and after an optional departure-time filter, if both are used):

```
A15AUGDFWORD¥AA       Only American Airlines flights
A15AUGDFWORD11A¥AA    Departing at/after 11AM, American Airlines only
```

**`1R` date shift sign** — `¥` can stand in for the `+` sign (never `-`) when shifting the return-availability date forward:

```
1R¥7     Same as 1R+7 - the return search, 7 days after the outbound date
```

`/` is the ASCII fallback for `¥` in both positions — `A15AUGDFWORD/AA` works exactly the same as `A15AUGDFWORD¥AA`.

**`‡` is deliberately not usable here.** Command chaining (below) splits a typed line on `‡` before anything else is parsed, so `A15AUGDFWORD‡AA` is read as two separate commands — `A15AUGDFWORD` (an unfiltered search) and `AA` (not a valid command on its own) — silently losing the filter instead of applying it. Always use `¥` or `/` for a filter, never `‡`.

---

## `‡` — Chain key

Runs several commands from one typed line, each dispatching in order exactly as if it had been typed and entered on its own — including its own signed-in check:

```
SI‡A15AUGDFWORD              Sign in, then search availability, in one line
A15AUGDFWORD‡01Y1‡-SMITH/JOHN MR   Search, sell, and add a name in one line
```

There's deliberately **no ASCII fallback character** for `‡` (unlike `¥`'s `/`) — a chaining delimiter needs to be a character that will never show up inside ordinary free text. An ASCII character like `;` risks silently mis-splitting a remark, an OSI note, or a received-from value that happens to contain it mid-sentence; `‡` avoids that because it isn't on a standard keyboard, so no one types it into a sentence by accident.

---

## `¤` — Change key

Edits one line of a field in place, instead of cancelling (`X{N}`) and re-adding it. Addressed by that field's **own prefix character** plus a line number **scoped to that specific field type** — e.g. `92¤...` means "phone line 2," the 2nd phone on file, not a PNR-wide element number (`X{N}`'s numbering is a different, global scheme that spans every kind of element on the PNR; the change key's numbering only counts within one field type).

```
-1¤SMITH/JANE MRS        Change name line 1
92¤214555-9999-A         Change phone line 2
9E1¤NEW@EXAMPLE.COM      Change email line 1
51¤UPDATED REMARK TEXT   Change general remark line 1
6¤NEW RECEIVED FROM      Change received-from (no line number - only one exists)
```

`~` is the ASCII fallback for `¤` — `92~214555-9999-A` works exactly the same as `92¤214555-9999-A`.

Limited to the five fields above — name, phone, email, general remark, received-from — since those are the only fields with no effect elsewhere in the PNR. Every other field type (a segment, a seat, an SSR, etc.) is still edited by cancelling (`X{N}`) and re-adding, since those carry effects (pricing, passenger-index attribution) an in-place text swap can't safely redo.

---

## Related

- [`HOW-TO-BOOK-A-FLIGHT.md`](HOW-TO-BOOK-A-FLIGHT.md) — the full step-by-step booking walkthrough
- Type `HELP` in either edition for the complete command reference, including a condensed version of this guide
