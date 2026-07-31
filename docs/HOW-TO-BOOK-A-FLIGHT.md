# Booking Your First Flight — Step by Step

Open `../web/index.html` in a browser to start. Everything is typed at the `>` prompt and submitted with **Enter**. Commands aren't case-sensitive, but standard GDS convention is ALL CAPS.

---

### 1. Sign in

```
SI
```
Confirms sign-in with a demo agent sine and pseudo city code (PCC). Nothing else works until you're signed in.

---

### 2. Search flight availability

Format: `A` + day + month + origin + destination (or `1` in place of `A` — both are real GDS entries)

```
A15AUGDFWORD
```
This requests flights from **DFW** (Dallas/Ft Worth) to **ORD** (Chicago O'Hare) on **August 15**. You'll get back a numbered list of flights, each with airline, flight number, seats open per class (F/J/C/Y/B/M), departure/arrival times.

> Any real-world IATA airport code works — the simulator ships with data for ~6,000 airports worldwide.

---

### 3. Sell a seat from the list

Format: `0` + line number + class letter + number of seats

```
04Y1
```
Sells **1 seat in Y class from line 4** of the availability display you just pulled up. The simulator confirms the segment and shows your PNR so far (currently just that flight segment). Selling reduces that class's remaining seat count for the rest of the session — sell it down to 0 and the next sell in that class waitlists (status `HL`) instead of being blocked.

You can also sell a specific flight directly, without pulling up availability first (a "long sell"). Format: `0` + airline + flight number + class + date + origin/destination + status code + party size:

```
0AA100Y15AUGDFWORDNN1
```

---

### 4. Add the passenger's name

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

---

### 5. Add passenger travel documents (APIS) (optional)

Format: `3DOCS` + document type + `/` + issuing country + `/` + number + `/` + nationality + `/` + date of birth + `/` + sex + `/` + expiry date + `-` + passenger number

```
3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1
```
This is Advance Passenger Information (APIS) / Secure Flight-style data, tied to a specific passenger by number (`-1` above means passenger 1 in the name field). `TYPE` is `P` for passport. Dates are `DDMONYY`, sex is `M` or `F`.

---

### 6. Add special service requests / other service info (optional)

Format: `3{SSRCODE}` for a service request (meals, wheelchair, etc.), optionally with a passenger number and free text: `3{SSRCODE}-{PAX#}/{TEXT}`. Format: `3OSI{AIRLINE}{TEXT}` for other-service-info free text to a carrier.

```
3VGML
3WCHR-1/AISLE SEAT PREFERRED
3OSIAA VIP PASSENGER
```

Common SSR codes: `WCHR`/`WCHS`/`WCHC` (wheelchair), `VGML`/`BBML`/`CHML`/`KSML`/`MOML`/`DBML`/`SPML` (meals), `BLND`/`DEAF` (accessibility), `UMNR` (unaccompanied minor), `PETC` (pet in cabin), `BSCT` (bassinet), `XBAG` (extra baggage).

A frequent flyer number can optionally carry a loyalty tier:

```
3FQTVAA1234567/GLD
```
Tiers: `SLV` (Silver), `GLD` (Gold), `PLT` (Platinum), `DIA` (Diamond).

To add an agency-internal note that isn't sent to the airline (distinct from OSI, which is carrier-facing):

```
5VIP CLIENT - HANDLE WITH CARE
```

---

### 7. Assign a seat (optional)

Format: `4{N}` to display the seat map for itinerary segment N, then `4{N}-{SEAT}` to assign one.

```
41
41-14A
```

---

### 8. Price the itinerary

Format: `WP` (once segments and at least one name are on the PNR)

```
WP
```
Prices the itinerary and shows a base fare, itemized taxes, a total, and fare rules (change fee, refundability, advance-purchase requirement) — this is stored on the PNR as a fare quote and is **required before ticketing**. `WPNCS` prices the lowest fare regardless of seat availability (informational only).

To apply a negotiated/corporate fare code, append it after a slash:

```
WP/ACME01
```
An unrecognized code is rejected with the list of valid codes; a valid one applies its discount to the base fare and is noted on the quote.

---

### 9. Add a contact phone number

Format: `9` + phone number + `-` + location code (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)

```
9214555-1234-A
```

---

### 10. Add "received from" (who the booking request came from)

Format: `6` + text

```
6JSMITH
```

---

### 11. Add a ticketing arrangement

```
7TAW/
```
This means "ticket at will" (no ticketing deadline). There's also `7TAX16AUG/1800` to set a ticketing time limit of Aug 16 at 6:00 PM.

---

### 12. Add a form of payment

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

### 13. End the transaction (save the booking)

```
ER
```
This saves the PNR and gives you a **6-character record locator** — your confirmation code. `ER` redisplays the saved PNR; `ET` saves it and clears the screen for a new booking.

---

### 14. Issue the ticket (optional)

```
TKTT
```
This is the step people often assume `ER` already did — it doesn't. Saving a PNR (`ER`/`ET`) and **ticketing** it are two different things in a real GDS, exactly like here: the "ticketing arrangement" you added in step 11 just sets a deadline (or "ticket at will"), it doesn't issue anything. `TKTT` is the actual ticketing entry — it requires the PNR to already be saved (has a record locator) and to have a fare quote, ticketing arrangement, and form of payment on file, and it generates a real-format ticket number (airline numeric code + serial) per passenger, including infants.

If you change the itinerary after ticketing (sell or cancel a segment), the ticket(s) are automatically voided along with the fare quote — you'll need to `WP` and `TKTT` again before saving.

---

### 15. Look up the booking again later

```
*ABC123
```
(using the actual locator you were given)

To see the full chronological history of everything that's been added, changed, or cancelled on the PNR:

```
*H
```

---

## Quick reference

| Step | Command | Example |
|---|---|---|
| Sign in | `SI` | `SI` |
| Search flights | `A{DD}{MON}{ORIG}{DEST}` | `A15AUGDFWORD` |
| Sell from list | `0{LINE}{CLASS}{SEATS}` | `04Y1` |
| Long/direct sell | `0{AL}{FLT}{CLASS}{DD}{MON}{ORIG}{DEST}{STATUS}{SEATS}` | `0AA100Y15AUGDFWORDNN1` |
| Add name | `-{SURNAME}/{GIVEN} {TITLE}` | `-SMITH/JOHN MR` |
| Add multiple passengers | `-{N}{SURNAME}/{G1} {T1}/{G2} {T2}` | `-2SMITH/JOHN MR/JANE MRS` |
| Add lap infant | `-...(INF{SURNAME}/{GIVEN}/{DOB})` | `-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)` |
| Add travel document (APIS) | `3DOCS{TYPE}/{CTY}/{NUM}/{NATL}/{DOB}/{SEX}/{EXP}-{PAX#}` | `3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1` |
| Add SSR | `3{SSRCODE}[-{PAX#}][/{TEXT}]` | `3VGML` |
| Add OSI | `3OSI{AL}{TEXT}` | `3OSIAA VIP PASSENGER` |
| Add frequent flyer number (+ tier) | `3FQTV{AL}{NUMBER}[/{TIER}]` | `3FQTVAA1234567/GLD` |
| Add general remark | `5{TEXT}` | `5VIP CLIENT` |
| Seat map / assign seat | `4{N}` / `4{N}-{SEAT}` | `41` / `41-14A` |
| Decode airport code | `DC{CODE}` | `DCORD` |
| Search airports by name | `DAN{TEXT}` | `DANCHICAGO` |
| Price itinerary (+ corporate code) | `WP[/{CORPCODE}]` | `WP` or `WP/ACME01` |
| Add phone | `9{NUMBER}-{LOC}` | `9214555-1234-A` |
| Add received-from | `6{TEXT}` | `6JSMITH` |
| Add ticketing | `7TAW/` | `7TAW/` |
| Add form of payment | `FPCASH`, `FPCHECK`, `FPCC{TYPE}{NUM}/{MMYY}` | `FPCASH` |
| Save booking | `ER` or `ET` | `ER` |
| Issue ticket | `TKTT` | `TKTT` |
| Redisplay PNR | `*R` or `*` | `*R` |
| Show PNR activity history | `*H` | `*H` |
| Retrieve saved PNR | `*{LOCATOR}` | `*ABC123` |
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

### 2. Shop for availability

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

### 3. Sell the itinerary

| Command | Does |
|---|---|
| `0{LINE}{CLASS}{SEATS}` | Sell from an availability line |
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

### 4. Add passenger data (name field &amp; documents)

| Command | Does |
|---|---|
| `-{SURNAME}/{GIVEN} {TITLE}` | Add a name |
| `-{N}{SURNAME}/{G1} {T1}/{G2} {T2}` | Add multiple passengers sharing a surname in one entry |
| `-...(INF{SURNAME}/{GIVEN}/{DOB})` | Attach a lap infant to the name just added |
| `3DOCS{TYPE}/{CTY}/{NUM}/{NATL}/{DOB}/{SEX}/{EXP}-{PAX#}` | Add a travel document (APIS) for a passenger |

**Terminology**
- **Name field** — the passenger name(s) on the PNR; required before pricing
- **Lap infant** — an infant traveling on an adult's lap rather than in their own seat; doesn't count against the party size/seats-sold limit
- **DOB format** — `DDMONYY`, e.g. `12JAN26`
- **APIS** (Advance Passenger Information) — passport/nationality/date-of-birth data governments require for international travel, tied to a specific passenger by number

### 5. Special service requests / other service info

| Command | Does |
|---|---|
| `3{SSRCODE}[-{PAX#}][/{TEXT}]` | Add a special service request |
| `3OSI{AL}{TEXT}` | Add other-service-info free text to a carrier |
| `3FQTV{AL}{NUMBER}[/{TIER}]` | Add a frequent flyer number, optionally with a loyalty tier |
| `5{TEXT}` | Add a general remark (agency-internal, not sent to the carrier) |

**Terminology**
- **SSR** (Special Service Request) — a coded request to the airline: meals, wheelchair assistance, unaccompanied minor, extra baggage, etc.
- **OSI** (Other Service Info) — free-text information sent to a carrier that isn't a coded SSR
- **FQTV** — frequent flyer number, stored as a special kind of SSR; can carry a loyalty tier (`SLV`/`GLD`/`PLT`/`DIA`)
- **General remark** — an agency-internal note on the PNR, distinct from OSI (which the carrier sees)

### 6. Seat selection

| Command | Does |
|---|---|
| `4{N}` | Display the seat map for segment `N` |
| `4{N}-{SEAT}` | Assign a seat on segment `N` |

**Terminology**
- **Seat map** — the row/column grid of open (`.`) and occupied (`X`) seats for a segment

### 7. Price the itinerary

| Command | Does |
|---|---|
| `WP` | Price the itinerary |
| `WPNCS` | Price at the lowest fare, regardless of seat availability (informational only) |
| `WP/{CORPCODE}`, `WPNCS/{CORPCODE}` | Price using a negotiated/corporate fare code |

**Terminology**
- **Fare quote** — the stored pricing result on the PNR; required before ticketing, and cleared automatically if the itinerary changes afterward
- **Fare basis** — the short code summarizing the fare's class and trip type (e.g. `YOW` = Y class, one-way)
- **Base fare** — the pre-tax fare amount
- **Taxes/fees** — the itemized government and carrier charges added on top of the base fare
- **Fare rules** — the change fee, refundability, and advance-purchase requirement shown with every fare quote, keyed off the itinerary's class
- **Corporate/negotiated fare code** — an account code that unlocks a discounted fare tier

### 8. Add contact &amp; booking info

| Command | Does |
|---|---|
| `9{NUMBER}-{LOC}` | Add a phone number |
| `9/{CTY}{NUMBER}-{LOC}` | Add a phone number, out-of-area (with city code) |
| `6{TEXT}` | Add "received from" |

**Terminology**
- **Phone field** — the contact number(s) on the PNR; required before end transaction
- **Location code** — the phone type suffix (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)
- **Received From (RF)** — who requested the booking; required before end transaction, same as a phone field

### 9. Ticketing arrangement &amp; form of payment

| Command | Does |
|---|---|
| `7TAW/` | Ticketing at will (no deadline) |
| `7TAW{DD}{MON}/{HHMM}` | Ticketing at will, queued to a date/time |
| `7TAX{DD}{MON}/{HHMM}` | Ticketing time limit |
| `FPCASH` | Form of payment: cash |
| `FPCHECK` | Form of payment: check |
| `FPCC{TYPE}{CARDNUM}/{MMYY}` | Form of payment: credit card |

**Terminology**
- **Ticketing arrangement** — the deadline (or lack of one) by which the PNR must be ticketed; not the same as ticketing itself
- **Ticket at will** — no fixed ticketing deadline
- **Time limit** — a fixed date/time by which the PNR must be ticketed or it's expected to cancel
- **Form of payment (FOP)** — how the ticket will be paid for; required before end transaction. Card numbers are masked to the last 4 digits once stored

### 10. End transaction

| Command | Does |
|---|---|
| `ER` | End transaction, redisplay the saved PNR |
| `ET` | End transaction, clear the work area for a new booking |
| `IG` | Ignore the PNR (discard unsaved work) |

**Terminology**
- **RLOC** (Record Locator) — the 6-character confirmation code assigned the first time a PNR is end-transacted
- **End transaction** — saving the PNR; requires a segment, a name, a fare quote, a phone, a received-from, a form of payment, and a ticketing arrangement all on file

### 11. Ticket issuance

| Command | Does |
|---|---|
| `TKTT` | Issue ticket number(s) |

**Terminology**
- **Validating carrier** — the airline whose numeric code prefixes the issued ticket number(s); taken from the first segment
- **Ticketing vs. ticketing arrangement** — the arrangement (`7TAW`/`7TAX`) only sets a deadline; `TKTT` is the entry that actually issues ticket numbers, and requires the PNR to already be saved (has an RLOC)

### 12. Retrieve &amp; review

| Command | Does |
|---|---|
| `*R` or `*` | Redisplay the current PNR |
| `*H` | Show the PNR's chronological activity history |
| `*{LOCATOR}` | Retrieve a saved PNR by its record locator |

**Terminology**
- **Activity log / PNR history** — the timestamped, sine-stamped record of every action taken on a PNR, viewed with `*H`, separate from the record-locator lookup done with `*{LOCATOR}`
