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

---

### 5. Price the itinerary

Format: `WP` (once segments and at least one name are on the PNR)

```
WP
```
Prices the itinerary and shows a base fare, itemized taxes, and total — this is stored on the PNR as a fare quote and is **required before ticketing**. `WPNCS` prices the lowest fare regardless of seat availability (informational only).

---

### 6. Add a contact phone number

Format: `9` + phone number + `-` + location code (`A`=Agency, `H`=Home, `B`=Business, `C`/`M`=Cell, `F`=Fax, `HTL`=Hotel)

```
9214555-1234-A
```

---

### 7. Add "received from" (who the booking request came from)

Format: `6` + text

```
6JSMITH
```

---

### 8. Add a ticketing arrangement

```
7TAW/
```
This means "ticket at will" (no ticketing deadline). There's also `7TAX16AUG/1800` to set a ticketing time limit of Aug 16 at 6:00 PM.

---

### 9. End the transaction (save the booking)

```
ER
```
This saves the PNR and gives you a **6-character record locator** — your confirmation code. `ER` redisplays the saved PNR; `ET` saves it and clears the screen for a new booking.

---

### 10. Look up the booking again later

```
*ABC123
```
(using the actual locator you were given)

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
| Price itinerary | `WP` | `WP` |
| Add phone | `9{NUMBER}-{LOC}` | `9214555-1234-A` |
| Add received-from | `6{TEXT}` | `6JSMITH` |
| Add ticketing | `7TAW/` | `7TAW/` |
| Save booking | `ER` or `ET` | `ER` |
| Redisplay PNR | `*R` or `*` | `*R` |
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
WP
9214555-1234-A
6JSMITH
7TAW/
ER
```
