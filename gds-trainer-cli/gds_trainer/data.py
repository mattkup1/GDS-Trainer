"""Reference/constant tables, loaded from spec/reference-data.json - shared with the
browser edition (see spec/README.md). Public names kept as-is so commands.py/dispatcher.py
imports don't change.
"""

from __future__ import annotations

import json
from pathlib import Path

_SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"
_DATA = json.loads((_SPEC_DIR / "reference-data.json").read_text(encoding="utf-8"))

MONTHS = _DATA["months"]
WEEKDAYS = _DATA["weekdays"]
AIRLINES = _DATA["airlines"]
AIRLINE_NUMERIC_CODES = _DATA["airlineNumericCodes"]
EQUIP = _DATA["equipment"]
SEAT_LAYOUTS = _DATA["seatLayouts"]
CLASSES = _DATA["classes"]
CLASS_FARE_MULT = _DATA["classFareMultipliers"]
TAX_POOL = _DATA["taxPool"]
FARE_FORMULA = _DATA["fareFormula"]
SSR_CODES = _DATA["ssrCodes"]
CARD_TYPES = _DATA["cardTypes"]
QUEUE_CATEGORIES = _DATA["queueCategories"]
PHONE_LOC_CODES = _DATA["phoneLocationCodes"]
DOCUMENT_TYPES = _DATA["documentTypes"]
LOYALTY_TIERS = _DATA["loyaltyTiers"]
FARE_RULES = _DATA["fareRules"]
CORPORATE_CODES = _DATA["corporateCodes"]
