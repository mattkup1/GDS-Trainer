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

Format: `A` + day + month + origin + destination

```
A15AUGDFWORD
```
This requests flights from **DFW** (Dallas/Ft Worth) to **ORD** (Chicago O'Hare) on **August 15**. You'll get back a numbered list of flights, each with airline, flight number, seats open per class (F/J/C/Y/B/M), departure/arrival times.

> Any 3-letter code works as an airport — it doesn't have to be a real one.

---

### 3. Sell a seat from the list

Format: `0` + line number + class letter + number of seats

```
04Y1
```
Sells **1 seat in Y class from line 4** of the availability display you just pulled up. The simulator confirms the segment and shows your PNR so far (currently just that flight segment).

---

### 4. Add the passenger's name

Format: `-` + SURNAME + `/` + GIVEN NAME + TITLE

```
-SMITH/JOHN MR
```

---

### 5. Add a contact phone number

Format: `9` + any phone text

```
9DFW555-1234-A
```

---

### 6. Add "received from" (who the booking request came from)

Format: `P` + text

```
PJSMITH
```

---

### 7. Add a ticketing arrangement

```
TAW/
```
This means "ticket at will" (no ticketing deadline). There's also `TAU16AUG/1800` to set a ticketing deadline of Aug 16 at 6:00 PM.

---

### 8. End the transaction (save the booking)

```
ER
```
This saves the PNR and gives you a **6-character record locator** — your confirmation code. `ER` redisplays the saved PNR; `ET` saves it and clears the screen for a new booking.

---

### 9. Look up the booking again later

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
| Add name | `-{SURNAME}/{GIVEN} {TITLE}` | `-SMITH/JOHN MR` |
| Add phone | `9{TEXT}` | `9DFW555-1234-A` |
| Add received-from | `P{TEXT}` | `PJSMITH` |
| Add ticketing | `TAW/` | `TAW/` |
| Save booking | `ER` or `ET` | `ER` |
| Redisplay PNR | `*R` or `*` | `*R` |
| Retrieve saved PNR | `*{LOCATOR}` | `*ABC123` |
| Cancel an item | `X{N}` | `X2` |
| Discard unsaved work | `IG` | `IG` |
| Full command list | `HELP` | `HELP` |

**Full walkthrough, start to finish:**
```
SI
A15AUGDFWORD
04Y1
-SMITH/JOHN MR
9DFW555-1234-A
PJSMITH
TAW/
ER
```
