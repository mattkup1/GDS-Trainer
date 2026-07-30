# Booking Your First Flight — Step by Step

Open `index.html` in a browser to start. Everything is typed at the `>` prompt and submitted with **Enter**. Commands aren't case-sensitive, but Sabre convention is ALL CAPS.

---

### 1. Sign in

```
SI
```
Confirms sign-in with a demo agent sine and pseudo city code (PCC). Nothing else works until you're signed in.

---

### 2. Search flight availability

Format: `A` + day + month + origin + destination (or `1` in place of `A` — both are real Sabre entries)

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
Sells **1 seat in Y class from line 4** of the availability display you just pulled up. The simulator confirms the segment and shows your PNR so far (currently just that flight segment).

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

### 5. Add special service requests / other service info (optional)

Format: `3{SSRCODE}` for a service request (meals, wheelchair, etc.), optionally with a passenger number and free text: `3{SSRCODE}-{PAX#}/{TEXT}`. Format: `3OSI{AIRLINE}{TEXT}` for other-service-info free text to a carrier.

```
3VGML
3WCHR-1/AISLE SEAT PREFERRED
3OSIAA VIP PASSENGER
```

Common SSR codes: `WCHR`/`WCHS`/`WCHC` (wheelchair), `VGML`/`BBML`/`CHML`/`KSML`/`MOML`/`DBML`/`SPML` (meals), `BLND`/`DEAF` (accessibility), `UMNR` (unaccompanied minor), `PETC` (pet in cabin), `BSCT` (bassinet), `XBAG` (extra baggage).

---

### 6. Assign a seat (optional)

Format: `4{N}` to display the seat map for itinerary segment N, then `4{N}-{SEAT}` to assign one.

```
41
41-14A
```

---

### 7. Price the itinerary

Format: `WP` (once segments and at least one name are on the PNR)

```
WP
```
Prices the itinerary and shows a base fare, itemized taxes, and total — this is stored on the PNR as a fare quote and is **required before ticketing**. `WPNCS` prices the lowest fare regardless of seat availability (informational only).

---

### 8. Add a contact phone number

Format: `9` + phone number + `-` + location code (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)

```
9214555-1234-A
```

---

### 9. Add "received from" (who the booking request came from)

Format: `6` + text

```
6JSMITH
```

---

### 10. Add a ticketing arrangement

```
7TAW/
```
This means "ticket at will" (no ticketing deadline). There's also `7TAX16AUG/1800` to set a ticketing time limit of Aug 16 at 6:00 PM.

---

### 11. Add a form of payment

Format: `FPCASH`, `FPCHECK`, or `FPCC{TYPE}{CARDNUMBER}/{MMYY}` for a credit card (`TYPE` is `VI`=Visa, `CA`=MasterCard, `AX`=Amex, `DC`=Diners Club, `DS`=Discover, `JC`=JCB).

```
FPCASH
```
or
```
FPCCVI4111111111111111/1225
```
Just like real Sabre, the PNR can't be saved without a form of payment on file. Card numbers are masked to the last 4 digits once stored.

---

### 12. End the transaction (save the booking)

```
ER
```
This saves the PNR and gives you a **6-character record locator** — your confirmation code. `ER` redisplays the saved PNR; `ET` saves it and clears the screen for a new booking.

---

### 13. Issue the ticket (optional)

```
TKTT
```
This is the step people often assume `ER` already did — it doesn't. Saving a PNR (`ER`/`ET`) and **ticketing** it are two different things in real Sabre, exactly like here: the "ticketing arrangement" you added in step 10 just sets a deadline (or "ticket at will"), it doesn't issue anything. `TKTT` is the actual ticketing entry — it requires the PNR to already be saved (has a record locator) and to have a fare quote, ticketing arrangement, and form of payment on file, and it generates a real-format ticket number (airline numeric code + serial) per passenger, including infants.

If you change the itinerary after ticketing (sell or cancel a segment), the ticket(s) are automatically voided along with the fare quote — you'll need to `WP` and `TKTT` again before saving.

---

### 14. Look up the booking again later

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
| Add SSR | `3{SSRCODE}[-{PAX#}][/{TEXT}]` | `3VGML` |
| Add OSI | `3OSI{AL}{TEXT}` | `3OSIAA VIP PASSENGER` |
| Add frequent flyer number | `3FQTV{AL}{NUMBER}` | `3FQTVAA1234567` |
| Seat map / assign seat | `4{N}` / `4{N}-{SEAT}` | `41` / `41-14A` |
| Decode airport code | `DC{CODE}` | `DCORD` |
| Search airports by name | `DAN{TEXT}` | `DANCHICAGO` |
| Price itinerary | `WP` | `WP` |
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
