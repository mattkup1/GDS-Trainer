# Booking Your First Flight — Step by Step

Open `../web/index.html` in a browser to start. Everything is typed at the `>` prompt and submitted with **Enter**. Commands aren't case-sensitive, but standard GDS convention is ALL CAPS.

---

### 1. Sign in

```
SI
```
Confirms sign-in with a demo agent sine and pseudo city code (PCC). Nothing else works until you're signed in.

---

### 2. Shop fares and check the schedule (optional, before booking)

Format: `FQ` + origin + destination, for an indicative fare quote independent of any booking

```
FQDFWORD
```
Shows a per-class table of indicative base fare, taxes, and total for that city pair — no PNR involved, nothing is booked. Useful for a quick "what would this cost" before searching availability.

Add `/{CLASS}` to check a class's fare rules instead of its price:

```
FQDFWORD/Y
```
Shows that class's change fee, refundability, and advance-purchase requirement — the same rule data shown after you price an itinerary with `WP` (step 9), but queryable up front for any class on any route, no booking required.

To see what flies a route across a whole week rather than one date — times and equipment only, no booking classes or seat counts, since it's not tied to sellable inventory:

```
S15AUGDFWORD
```

---

### 3. Search flight availability

Format: `A` + day + month + origin + destination (or `1` in place of `A` — both are real GDS entries)

```
A15AUGDFWORD
```
This requests flights from **DFW** (Dallas/Ft Worth) to **ORD** (Chicago O'Hare) on **August 15**. You'll get back a numbered list of flights, each with airline, flight number, seats open per class (F/J/C/Y/B/M), departure/arrival times. Most lines share the searched city pair, but a few may show a different one — that's a connecting flight's leg (see the next step).

A long enough flight departing late in the day lands after midnight — its arrival time shows a `+1` suffix (e.g. `1206A+1`) to mark that it's the next calendar day, the same convention real Sabre uses. This shows up anywhere an arrival time is printed: availability, schedule display, the PNR, and the itinerary document.

> Any real-world IATA airport code works — the simulator ships with data for ~6,000 airports worldwide.

---

### 4. Sell a seat from the list

Format: `0` + line number + class letter + number of seats

```
04Y1
```
Sells **1 seat in Y class from line 4** of the availability display you just pulled up. The simulator confirms the segment and shows your PNR so far (currently just that flight segment). Selling reduces that class's remaining seat count for the rest of the session — sell it down to 0 and the next sell in that class waitlists (status `HL`) instead of being blocked.

You can also sell a specific flight directly, without pulling up availability first (a "long sell"). Format: `0` + airline + flight number + class + date + origin/destination + status code + party size:

```
0AA100Y15AUGDFWORDNN1
```

If two lines' cities and times line up (one line's destination matches another's origin, with a workable connection time), sell them together as a connecting itinerary in one entry: seats, then class + line number for each leg:

```
02Y1M2
```
Sells 2 seats — Y class on line 1, M class on line 2 — as two segments that are **married**: they were sold as one connection, so cancelling one later requires cancelling both together (`X1,2`), rather than silently leaving the other leg behind.

"Workable connection time" means the layover clears minimum connect time (MCT) at the connecting airport: **45 minutes** if both legs stay within the same country, **90 minutes** if either leg crosses a border (extra time for immigration, security, or re-check-in). A layover that's too short is rejected with the required and actual minutes shown.

---

### 5. Add the passenger's name

Format: `-` + SURNAME + `/` + GIVEN NAME + TITLE

```
-SMITH/JOHN MR
```

To add **more than one passenger with the same surname** in a single entry, prefix the surname with a count and chain additional given-name/title pairs with `/`:

```
-2SMITH/JOHN MR/JANE MRS
```

For passengers with different surnames, add a separate `-` entry for each.

To add a **lap infant** traveling with a passenger, append `(INF{SURNAME}/{GIVEN}/{DOB})` to that passenger's name entry (`DOB` is `DDMONYY`):

```
-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)
```

**Booking a group (10 or more passengers):** if the names aren't finalized yet, add placeholder passengers in one entry instead of spelling out each one:

```
-12TBA/TBA
```
Adds 12 identical `TBA/TBA` placeholders — real groups are held this way, with names filled in closer to departure. A group needs a deposit on file before it can be saved:

```
3DEPS
```
To finalize a placeholder later, cancel it and add the real name — the same two entries you'd use to fix any other passenger's name:

```
X5
-SMITH/JOHN MR
```

---

### 6. Add passenger travel documents (APIS) (optional)

Format: `3DOCS` + document type + `/` + issuing country + `/` + number + `/` + nationality + `/` + date of birth + `/` + sex + `/` + expiry date + `-` + passenger number

```
3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1
```
This is Advance Passenger Information (APIS) / Secure Flight-style data, tied to a specific passenger by number (`-1` above means passenger 1 in the name field). `TYPE` is `P` for passport. Dates are `DDMONYY`, sex is `M` or `F`.

**For a lap infant**, append `.{INFANT#}` after the passenger number — real GDSs don't give infants their own top-level name-field entry, so they're addressed as a decimal off the adult they travel with (`1.1` = the 1st infant travelling with passenger 1):

```
3DOCSP/US/123456789/US/12JAN26/M/25DEC30-1.1
```

---

### 7. Add special service requests / other service info (optional)

Format: `3{SSRCODE}` for a service request (meals, wheelchair, etc.), optionally with a passenger number and free text: `3{SSRCODE}-{PAX#}/{TEXT}`. Format: `3OSI{AIRLINE}{TEXT}` for other-service-info free text to a carrier.

```
3VGML
3WCHR-1/AISLE SEAT PREFERRED
3OSIAA VIP PASSENGER
```

Common SSR codes: `WCHR`/`WCHS`/`WCHC` (wheelchair), `VGML`/`BBML`/`CHML`/`KSML`/`MOML`/`DBML`/`SPML` (meals), `BLND`/`DEAF` (accessibility), `UMNR` (unaccompanied minor), `PETC` (pet in cabin), `BSCT` (bassinet), `XBAG` (extra baggage), `EXST` (extra seat purchased), `CBBG` (extra seat for cabin baggage/instrument), `STCR` (stretcher case), `DEPS` (group deposit received — see step 5).

To book an extra seat (a comfort/oversized-passenger purchase, or one held for an instrument), sell one more seat than passengers and tag it with the SSR:

```
04Y2
-SMITH/JOHN MR
3EXST-1
```
Sells 2 seats but names only 1 passenger — the fare quote (`WP`) automatically prices for both seats, since it charges per seat sold on the segment, not per name.

A frequent flyer number can optionally be tied to a specific passenger and/or carry a loyalty tier:

```
3FQTVAA1234567-1/GLD
```
Tiers: `SLV` (Silver), `GLD` (Gold), `PLT` (Platinum), `DIA` (Diamond). Both the passenger number and the tier are optional and independent — `3FQTVAA1234567-1` (no tier) and `3FQTVAA1234567/GLD` (no passenger, applies to the PNR generally) both work too.

To add an agency-internal note that isn't sent to the airline (distinct from OSI, which is carrier-facing):

```
5VIP CLIENT - HANDLE WITH CARE
```

---

### 8. Assign a seat (optional)

Format: `4{N}` to display the seat map for itinerary segment N, then `4{N}-{SEAT}` to assign one, optionally tied to a specific passenger with `/{PAX#}`.

```
41
41-14A
```

With a solo passenger on file, the passenger number can be omitted — it's assigned to them automatically. With more than one name on the PNR, it's required (there's no way to guess whose seat it is):

```
41-14A/1
41-14B/2
```

---

### 9. Price the itinerary

Format: `WP` (once segments and at least one name are on the PNR)

```
WP
```
Prices the itinerary and shows a base fare, itemized taxes, a total, the trip type (one way/round trip/circle trip/open jaw — worked out from how your segments' origins and destinations connect), and fare rules (change fee, refundability, advance-purchase requirement) — this is stored on the PNR as a fare quote and is **required before ticketing**. `WPNCS` prices the lowest fare regardless of seat availability (informational only).

To apply a negotiated/corporate fare code, append it after a slash:

```
WP/ACME01
```
An unrecognized code is rejected with the list of valid codes; a valid one applies its discount to the base fare and is noted on the quote.

---

### 10. Add a contact phone number

Format: `9` + phone number + `-` + location code (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)

```
9214555-1234-A
```

---

### 11. Add "received from" (who the booking request came from)

Format: `6` + text

```
6JSMITH
```

---

### 12. Add a ticketing arrangement

```
7TAW/
```
This means "ticket at will" (no ticketing deadline). There's also `7TAX16AUG/1800` to set a ticketing time limit of Aug 16 at 6:00 PM.

---

### 13. Add a form of payment

Format: `FPCASH`, `FPCHECK`, or `FPCC{TYPE}{CARDNUMBER}/{MMYY}` for a credit card (`TYPE` is `VI`=Visa, `CA`=MasterCard, `AX`=Amex, `DC`=Diners Club, `DS`=Discover, `JC`=JCB).

```
FPCASH
```
or
```
FPCCVI4111111111111111/1225
```
Just like a real GDS, the PNR can't be saved without a form of payment on file. Card numbers are masked to the last 4 digits once stored.

---

### 14. End the transaction (save the booking)

```
ER
```
This saves the PNR and gives you a **6-character record locator** — your confirmation code. `ER` redisplays the saved PNR; `ET` saves it and clears the screen for a new booking. (A group PNR — 10 or more names — additionally needs a deposit on file; see step 5.)

---

### 15. Issue the ticket (optional)

```
TKTT
```
This is the step people often assume `ER` already did — it doesn't. Saving a PNR (`ER`/`ET`) and **ticketing** it are two different things: the "ticketing arrangement" you added in step 12 just sets a deadline (or "ticket at will"), it doesn't issue anything. `TKTT` is the actual ticketing entry — it requires the PNR to already be saved (has a record locator) and to have a fare quote, ticketing arrangement, and form of payment on file, and it generates a real-format ticket number (airline numeric code + serial) per passenger, including infants.

If you change the itinerary after ticketing (sell or cancel a segment), the ticket(s) are automatically voided along with the fare quote — you'll need to `WP` and `TKTT` again before saving. Three more entries handle a ticketed PNR from there: `TKTV` voids the ticket(s) same-day, no penalty, leaving the fare quote in place so `TKTT` can reissue right away; `TKTR` refunds them (blocked if the fare basis isn't refundable); `WFR{TICKET#}` exchanges an already-issued ticket after a later fare/itinerary change — applies its value toward the newly-priced total, shows an additional collection or a residual, and reissues.

---

### 16. Print or save the customer a copy of the itinerary/invoice (optional)

```
EMI
```
`EMI` ends the transaction (same requirements as `ER`/`ET`) and generates a formatted itinerary/invoice document — passenger names, flights, seats, the fare breakdown, form of payment, and ticket numbers if `TKTT` has already run. In the browser edition this opens in a new tab you can print or "Save as PDF" from your browser's print dialog; the CLI edition prints the same content directly in the terminal. Two related entries generate narrower documents the same way: `EM` (itinerary only, no fare/payment) and `EMT` (ticket-focused, notes "NOT YET TICKETED" if you haven't run `TKTT` yet). All three clear the work area on success, like `ET`.

---

### 17. Look up the booking again later

```
*ABC123
```
(using the actual locator you were given)

To see the full chronological history of everything that's been added, changed, or cancelled on the PNR:

```
*H
```

---

### 18. Divide the PNR into two bookings (optional)

Format: `SP` + passenger number(s)

```
SP2
```
Splits passenger 2 out of the current PNR into a brand-new, separately-locatored PNR — the itinerary and contact/ticketing info are copied to both. Needs a saved PNR (`ER`/`ET` already run) to work from; both resulting PNRs need a fresh `WP` (and `TKTT` if already ticketed) before they can be saved again, since the party size changed on each side — each side's `WP` prices for its own headcount, not the original combined party. Any seat assignment tied to the divided passenger (see step 8) follows them into the new PNR; seats tied to passengers who stay behind stay with the original.

---

### 19. Queue the PNR for follow-up (optional)

Format: `QE` + queue number (once the PNR has been saved with `ER`/`ET`)

```
QE25
```
Places the saved PNR on queue **25** for later work — real agencies route PNRs to numbered queues for things like ticketing follow-up or schedule changes, rather than an agent handling everything in one sitting. Queuing clears the work area, the same as `ET`.

To see how many PNRs are waiting on each queue:

```
QC
```
Or check one specific queue:
```
QC25
```

To pull the next PNR off a queue and load it into the work area:

```
QN25
```
This works one PNR at a time, first-in-first-out — exactly how an agent works a real queue. An empty or unused queue number just reports there's nothing there.

Three queues populate themselves automatically as you work a PNR, no entry required: queue **1** picks up a PNR whose flight time changed after booking (a schedule change), queue **2** picks up one whose flight was cancelled outright by the carrier, and queue **18** picks up one whose waitlisted segment cleared to confirmed. All three are discovered the same way — checking `QC`/`QN{N}`, or noticing the on-screen note the next time the PNR is redisplayed. A cancelled segment (queue 2) is the strictest of the three: the itinerary can't be re-priced with `WP` until you cancel that segment (`X{n}`) and sell a replacement — unlike a schedule change, which just needs a fresh `WP`.

---

## Quick reference

| Step | Command | Example |
|---|---|---|
| Sign in | `SI` | `SI` |
| Shop fares by city pair (no PNR needed) | `FQ{ORIG}{DEST}` | `FQDFWORD` |
| Check a class's fare rules by city pair (no PNR needed) | `FQ{ORIG}{DEST}/{CLASS}` | `FQDFWORD/Y` |
| Flight schedule, 7-day window (no booking classes/seats) | `S{DD}{MON}{ORIG}{DEST}` | `S15AUGDFWORD` |
| Search flights | `A{DD}{MON}{ORIG}{DEST}` | `A15AUGDFWORD` |
| Sell from list | `0{LINE}{CLASS}{SEATS}` | `04Y1` |
| Sell a connection (two avail lines) | `0{SEATS}{CLASS}{LINE}{CLASS}{LINE}` | `02Y1M2` |
| Long/direct sell | `0{AL}{FLT}{CLASS}{DD}{MON}{ORIG}{DEST}{STATUS}{SEATS}` | `0AA100Y15AUGDFWORDNN1` |
| Add name | `-{SURNAME}/{GIVEN} {TITLE}` | `-SMITH/JOHN MR` |
| Add multiple passengers | `-{N}{SURNAME}/{G1} {T1}/{G2} {T2}` | `-2SMITH/JOHN MR/JANE MRS` |
| Add lap infant | `-...(INF{SURNAME}/{GIVEN}/{DOB})` | `-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)` |
| Add a group of placeholder names (10+ = a group) | `-{N}TBA/TBA` | `-12TBA/TBA` |
| Record a group deposit (required to save a 10+ name PNR) | `3DEPS` | `3DEPS` |
| Add travel document (APIS) | `3DOCS{TYPE}/{CTY}/{NUM}/{NATL}/{DOB}/{SEX}/{EXP}-{PAX#}[.{INFANT#}]` | `3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1` or `...-1.1` for an infant |
| Add SSR | `3{SSRCODE}[-{PAX#}][/{TEXT}]` | `3VGML` |
| Add OSI | `3OSI{AL}{TEXT}` | `3OSIAA VIP PASSENGER` |
| Add frequent flyer number (+ pax, tier) | `3FQTV{AL}{NUMBER}[-{PAX#}][/{TIER}]` | `3FQTVAA1234567-1/GLD` |
| Add general remark | `5{TEXT}` | `5VIP CLIENT` |
| Seat map / assign seat (+ pax) | `4{N}` / `4{N}-{SEAT}[/{PAX#}]` | `41` / `41-14A` or `41-14A/1` |
| Decode airport code | `DC{CODE}` | `DCORD` |
| Search airports by name | `DAN{TEXT}` | `DANCHICAGO` |
| Price itinerary (+ corporate code) | `WP[/{CORPCODE}]` | `WP` or `WP/ACME01` |
| Add phone | `9{NUMBER}-{LOC}` | `9214555-1234-A` |
| Add received-from | `6{TEXT}` | `6JSMITH` |
| Add ticketing | `7TAW/` | `7TAW/` |
| Add form of payment | `FPCASH`, `FPCHECK`, `FPCC{TYPE}{NUM}/{MMYY}` | `FPCASH` |
| Save booking | `ER` or `ET` | `ER` |
| Issue ticket | `TKTT` | `TKTT` |
| Void ticket (same-day, no penalty) | `TKTV` | `TKTV` |
| Refund ticket (blocked for nonrefundable fares) | `TKTR` | `TKTR` |
| Exchange ticket after a fare/itinerary change | `WFR{TICKET#}` | `WFR045-1234567890` |
| Print/save itinerary, invoice, or e-ticket document | `EM`, `EMI`, `EMT` | `EMI` |
| Redisplay PNR | `*R` or `*` | `*R` |
| Show PNR activity history | `*H` | `*H` |
| Retrieve saved PNR | `*{LOCATOR}` | `*ABC123` |
| Divide passenger(s) into a new PNR | `SP{N}` or `SP{N},{M}` | `SP2` |
| Place PNR on a queue | `QE{N}` | `QE25` |
| Show queue counts | `QC` or `QC{N}` | `QC` or `QC25` |
| Retrieve next PNR from a queue | `QN{N}` | `QN25` (queue `1` auto-populates on a schedule change, `2` on a flight cancellation, `18` on a waitlist clearing) |
| Cancel an item | `X{N}`, `X{N}-{M}`, `X{N},{M}` | `X2` |
| Cancel entire itinerary | `XI` | `XI` |
| Discard unsaved work | `IG` | `IG` |
| Full command list | `HELP` | `HELP` |

**Full walkthrough, start to finish:**
```
SI
A15AUGDFWORD
04Y1
-SMITH/JOHN MR
3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1
3VGML
41-14A
WP
9214555-1234-A
6JSMITH
7TAW/
FPCASH
ER
TKTT
```

---

## Command &amp; terminology keymap, by PNR stage

Every command and every piece of jargon from this guide, grouped by where it fits in building a PNR from scratch.

### 1. Sign on

| Command | Does |
|---|---|
| `SI` | Sign in |
| `SI{sine}/{pcc}` | Sign in with a specific agent sine and pseudo city code |
| `SO` | Sign out |
| `HELP` | Full in-app command reference |

**Terminology**
- **Sine** — the agent's identifying code, shown on every sign-in and stamped on the PNR's activity log
- **PCC** (Pseudo City Code) — the agency/office identifier an agent is signed in under
- **GDS** (Global Distribution System) — the reservation platform itself; PNRs, fares, and inventory all live in it

### 2. Shop for fares &amp; schedules

| Command | Does |
|---|---|
| `FQ{ORG}{DST}` | Fare quote shop by city pair — indicative only, no PNR involved |
| `FQ{ORG}{DST}/{CLASS}` | Fare rules for that class on that route (change fee, refundable, advance purchase) — no PNR involved |
| `S{DD}{MON}{ORG}{DST}` | Flight schedule across a 7-day window — no booking classes or seats |

**Terminology**
- **Fare shop** — an indicative, per-class fare check by city pair, independent of any itinerary; distinct from `WP`, which prices an already-sold itinerary
- **Fare rules** — the change fee, refundability, and advance-purchase requirement tied to a booking class; viewable stand-alone via `FQ.../{CLASS}` or automatically shown after pricing with `WP`
- **Schedule display** — a several-day view of what flies a route, independent of sellable inventory; distinct from availability, which shows one date's bookable classes/seats

### 3. Shop for availability

| Command | Does |
|---|---|
| `A{DD}{MON}{ORG}{DST}` | Air availability |
| `1{DD}{MON}{ORG}{DST}` | Air availability (alternate entry, same result) |
| `DC{CODE}` | Decode a 3-letter airport/city code |
| `DAN{TEXT}` | Search airports/cities by name |

**Terminology**
- **Availability display** — the numbered list of flights returned by an `A`/`1` entry
- **Line number** — the number to the left of each flight on the availability display, used to sell it
- **Class of service** — the single-letter fare class (`F` First, `J`/`C` Business, `Y`/`B`/`M` Economy) shown with a seat count per flight
- **EQP** — the aircraft equipment code (e.g. `738`, `320`) shown on each flight line

### 4. Sell the itinerary

| Command | Does |
|---|---|
| `0{LINE}{CLASS}{SEATS}` | Sell from an availability line |
| `0{SEATS}{CLASS}{LINE}{CLASS}{LINE}` | Sell a connection — both legs in one entry |
| `0{AL}{FLT}{CLASS}{DD}{MON}{ORG}{DST}{STATUS}{SEATS}` | Long/direct sell (no availability display needed) |
| `X{N}` | Cancel element `N` |
| `X{N}-{M}`, `X{N},{M}` | Cancel a range or list of elements |
| `XI` | Cancel the entire itinerary (all segments) |

**Terminology**
- **Segment** — one sold flight on the PNR
- **Long sell** — selling a specific flight directly by airline/flight number, bypassing the availability display
- **Status code** — the two-letter segment status: `HK` = holds confirmed; `HL` = waitlisted (a class sold down to 0 remaining sells as a waitlist request instead of being blocked); `NN` = need/request, used when typing a long-sell entry by hand
- **Party size** — the number of seats requested in a sell entry; caps how many passenger names the PNR can carry
- **PNR element** — any single numbered line on the PNR display (a name, a segment, a phone, etc.) — what `X{N}` cancels
- **Married segments** — two segments sold together as one connection; the PNR display notes each one's pairing, and cancelling either alone is blocked — both must be cancelled in the same `X` entry
- **Minimum connect time (MCT)** — the shortest layover a connection sell will accept at the connecting airport: 45 minutes if both legs stay within the same country, 90 minutes if either leg crosses a border. A shorter layover is rejected with the required and actual minutes shown

### 5. Add passenger data (name field &amp; documents)

| Command | Does |
|---|---|
| `-{SURNAME}/{GIVEN} {TITLE}` | Add a name |
| `-{N}{SURNAME}/{G1} {T1}/{G2} {T2}` | Add multiple passengers sharing a surname in one entry |
| `-...(INF{SURNAME}/{GIVEN}/{DOB})` | Attach a lap infant to the name just added |
| `-{N}TBA/TBA` | Add `N` identical group-placeholder passengers in one entry (`N` &gt; 1) |
| `3DEPS` | Record a group deposit received (required to save a 10+ name PNR) |
| `3DOCS{TYPE}/{CTY}/{NUM}/{NATL}/{DOB}/{SEX}/{EXP}-{PAX#}[.{INFANT#}]` | Add a travel document (APIS) for a passenger, or for their infant |

**Terminology**
- **Name field** — the passenger name(s) on the PNR; required before pricing
- **Lap infant** — an infant traveling on an adult's lap rather than in their own seat; doesn't count against the party size/seats-sold limit
- **DOB format** — `DDMONYY`, e.g. `12JAN26`
- **Group** — a PNR with 10 or more passengers; typically built with `TBA/TBA` placeholder names finalized closer to departure, and requires a deposit (`3DEPS`) on file before it can be saved
- **APIS** (Advance Passenger Information) — passport/nationality/date-of-birth data governments require for international travel, tied to a specific passenger by number — or, for an infant, by `{PAX#}.{INFANT#}` (Sabre-style decimal notation, since an infant has no name-field entry of its own)

### 6. Special service requests / other service info

| Command | Does |
|---|---|
| `3{SSRCODE}[-{PAX#}][/{TEXT}]` | Add a special service request |
| `3OSI{AL}{TEXT}` | Add other-service-info free text to a carrier |
| `3FQTV{AL}{NUMBER}[-{PAX#}][/{TIER}]` | Add a frequent flyer number, optionally tied to a passenger, optionally with a loyalty tier |
| `5{TEXT}` | Add a general remark (agency-internal, not sent to the carrier) |

**Terminology**
- **SSR** (Special Service Request) — a coded request to the airline: meals, wheelchair assistance, unaccompanied minor, extra baggage, a group deposit (`DEPS`), etc.
- **OSI** (Other Service Info) — free-text information sent to a carrier that isn't a coded SSR
- **FQTV** — frequent flyer number, stored as a special kind of SSR; can be tied to a specific passenger by number (like a regular SSR), and can carry a loyalty tier (`SLV`/`GLD`/`PLT`/`DIA`)
- **General remark** — an agency-internal note on the PNR, distinct from OSI (which the carrier sees)

### 7. Seat selection

| Command | Does |
|---|---|
| `4{N}` | Display the seat map for segment `N` |
| `4{N}-{SEAT}[/{PAX#}]` | Assign a seat on segment `N`, optionally tied to a passenger |

**Terminology**
- **Seat map** — the row/column grid of open (`.`) and occupied (`X`) seats for a segment
- **Seat/passenger attribution** — which specific passenger a seat assignment belongs to; optional and auto-assumed for a solo passenger, required once there's more than one name on the PNR. Matters for `SP` (divide): only an attributed seat can follow its passenger into a new PNR

### 8. Price the itinerary

| Command | Does |
|---|---|
| `WP` | Price the itinerary |
| `WPNCS` | Price at the lowest fare, regardless of seat availability (informational only) |
| `WP/{CORPCODE}`, `WPNCS/{CORPCODE}` | Price using a negotiated/corporate fare code |

**Terminology**
- **Fare quote** — the stored pricing result on the PNR; required before ticketing, and cleared automatically if the itinerary changes afterward
- **Fare basis** — the short code summarizing the fare's class and trip type (e.g. `YOW` = Y class, one-way)
- **Trip type** — the itinerary's shape, printed alongside the fare basis and on every PNR display once a segment is sold: **one way** (a single segment), **round trip** (out and back on the same city pair), **circle trip** (multiple stops that return to the origin), or **open jaw** (the return leg starts or ends at a different city than the outbound)
- **Base fare** — the pre-tax fare amount
- **Taxes/fees** — the itemized government and carrier charges added on top of the base fare
- **Fare rules** — the change fee, refundability, and advance-purchase requirement shown with every fare quote, keyed off the itinerary's class
- **Corporate/negotiated fare code** — an account code that unlocks a discounted fare tier

### 9. Add contact &amp; booking info

| Command | Does |
|---|---|
| `9{NUMBER}-{LOC}` | Add a phone number |
| `9/{CTY}{NUMBER}-{LOC}` | Add a phone number, out-of-area (with city code) |
| `6{TEXT}` | Add "received from" |

**Terminology**
- **Phone field** — the contact number(s) on the PNR; required before end transaction
- **Location code** — the phone type suffix (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)
- **Received From (RF)** — who requested the booking; required before end transaction, same as a phone field

### 10. Ticketing arrangement &amp; form of payment

| Command | Does |
|---|---|
| `7TAW/` | Ticketing at will (no deadline) |
| `7TAW{DD}{MON}/{HHMM}` | Ticketing at will, queued to a date/time |
| `7TAX{DD}{MON}/{HHMM}` | Ticketing time limit |
| `FPCASH` | Form of payment: cash |
| `FPCHECK` | Form of payment: check |
| `FPCC{TYPE}{CARDNUM}/{MMYY}` | Form of payment: credit card |

**Terminology**
- **Ticketing arrangement** — the deadline (or lack of one) by which the PNR must be ticketed; not the same as ticketing itself. In this trainer it also stands in for a group's names-finalization deadline.
- **Ticket at will** — no fixed ticketing deadline
- **Time limit** — a fixed date/time by which the PNR must be ticketed or it's expected to cancel
- **Form of payment (FOP)** — how the ticket will be paid for; required before end transaction. Card numbers are masked to the last 4 digits once stored

### 11. End transaction

| Command | Does |
|---|---|
| `ER` | End transaction, redisplay the saved PNR |
| `ET` | End transaction, clear the work area for a new booking |
| `IG` | Ignore the PNR (discard unsaved work) |

**Terminology**
- **RLOC** (Record Locator) — the 6-character confirmation code assigned the first time a PNR is end-transacted
- **End transaction** — saving the PNR; requires a segment, a name, a fare quote, a phone, a received-from, a form of payment, and a ticketing arrangement all on file (plus a deposit on file for a 10+ name group)

### 12. Ticket issuance

| Command | Does |
|---|---|
| `TKTT` | Issue ticket number(s) |
| `TKTV` | Void issued ticket(s) — same-day, no penalty; the fare quote stays on file |
| `TKTR` | Refund issued ticket(s) — blocked for a nonrefundable fare basis |
| `WFR{TICKET#}` | Exchange an issued ticket after a fare/itinerary change |

**Terminology**
- **Validating carrier** — the airline whose numeric code prefixes the issued ticket number(s); taken from the first segment
- **Ticketing vs. ticketing arrangement** — the arrangement (`7TAW`/`7TAX`) only sets a deadline; `TKTT` is the entry that actually issues ticket numbers, and requires the PNR to already be saved (has an RLOC)
- **Void** — a same-day ticket reversal with no penalty; unlike a refund, the fare quote and ticketing arrangement stay valid, so `TKTT` can reissue immediately
- **Refund** — cancelling issued ticket(s) and voiding the fare quote with them; blocked outright if the fare basis isn't refundable
- **Exchange** — applying an already-issued ticket's value toward a newly re-priced itinerary, showing either an additional collection (ADCOLL) or a non-refundable residual, then reissuing a new ticket number

### 13. Documents

| Command | Does |
|---|---|
| `EM` | End transaction, generate an itinerary document (no fare/payment) |
| `EMI` | End transaction, generate an invoice document (adds fare summary, form of payment, ticket numbers if issued) |
| `EMT` | End transaction, generate an e-ticket notification document |

**Terminology**
- **Itinerary/invoice document** — a customer-facing formatted document (browser: printable page/PDF in a new tab; CLI: formatted terminal block), distinct from the PNR display an agent sees — `EM`/`EMI`/`EMT` are end-transaction entries like `ER`/`ET`, requiring the same completeness, and clear the work area on success

### 14. Retrieve &amp; review

| Command | Does |
|---|---|
| `*R` or `*` | Redisplay the current PNR |
| `*H` | Show the PNR's chronological activity history |
| `*{LOCATOR}` | Retrieve a saved PNR by its record locator |

**Terminology**
- **Activity log / PNR history** — the timestamped, sine-stamped record of every action taken on a PNR, viewed with `*H`, separate from the record-locator lookup done with `*{LOCATOR}`

### 15. Divide a PNR

| Command | Does |
|---|---|
| `SP{N}` | Divide passenger `N` out of the PNR into a new, separately-locatored PNR |
| `SP{N},{M}` | Divide multiple passengers out at once |

**Terminology**
- **Divide** — splitting one or more passengers out of a PNR into a brand-new PNR; the itinerary and contact/ticketing details are copied to both, but each needs its own fresh fare quote (and reissue, if already ticketed) afterward since the party size changed on both sides — each side prices for its own remaining/moved headcount, not the original combined party. A passenger's own seat assignment (if tied to them — see step 8) moves with them; an unattributed seat assignment is dropped from both sides

### 16. Queues

| Command | Does |
|---|---|
| `QE{N}` | Place the saved PNR on queue `N`; clears the work area |
| `QC` | Show a count of PNRs on every non-empty queue |
| `QC{N}` | Show the count of PNRs on queue `N` specifically |
| `QN{N}` | Retrieve the next (first-in) PNR off queue `N` into the work area |

**Terminology**
- **Queue** — a numbered bucket of PNRs awaiting follow-up work; the backbone of real-world agent workflow, distinct from `*{LOCATOR}` retrieval which requires already knowing the exact record locator
- **Queue count** — how many PNRs are currently sitting on a given queue, shown by `QC`
- **Working a queue** — repeatedly entering `QN{N}` to pull PNRs off a queue one at a time, in the order they were placed there
- **Schedule change** — an airline-side change to a booked segment's time, discovered automatically: it auto-queues the PNR to queue **1** and shows a note on its next redisplay until re-priced
- **Flight cancellation** — the airline drops a booked, confirmed (`HK`) flight entirely; the segment's status flips to `UN` and the PNR auto-queues to queue **2**. Unlike a schedule change, `WP` refuses to re-price while the dead segment is still on file — cancel it with `X{n}` and sell a replacement first
- **Waitlist clearing** — a waitlisted (`HL`) segment clearing to confirmed (`HK`), discovered the same way via queue **18** — no re-pricing needed, since the fare and flight are unchanged
