"""Reference/constant tables, loaded from spec/reference-data.json - shared with the
browser edition (see spec/README.md). Public names kept as-is so commands.py/dispatcher.py
imports don't change.
"""

from __future__ import annotations

import json
from pathlib import Path

_SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"
_DATA = json.loads((_SPEC_DIR / "reference-data.json").read_text(encoding="utf-8"))
_AIRLINES_DATA = json.loads((_SPEC_DIR / "airlines.json").read_text(encoding="utf-8"))

MONTHS = _DATA["months"]
WEEKDAYS = _DATA["weekdays"]
# spec/airlines.json (code -> {name, numericCode}) - kept as three derived
# views since that's how callers already import these names.
AIRLINES = list(_AIRLINES_DATA.keys())
AIRLINE_NUMERIC_CODES = {code: info["numericCode"] for code, info in _AIRLINES_DATA.items()}
AIRLINE_NAMES = {code: info["name"] for code, info in _AIRLINES_DATA.items()}
EQUIP = _DATA["equipment"]
SEAT_LAYOUTS = _DATA["seatLayouts"]
CLASSES = _DATA["classes"]
CLASS_FARE_MULT = _DATA["classFareMultipliers"]
TAX_POOL = _DATA["taxPool"]
FARE_FORMULA = _DATA["fareFormula"]
SCHEDULE_CHANGE = _DATA["scheduleChange"]
WAITLIST_CLEAR = _DATA["waitlistClear"]
SSR_CODES = _DATA["ssrCodes"]
CARD_TYPES = _DATA["cardTypes"]
QUEUE_CATEGORIES = _DATA["queueCategories"]
PHONE_LOC_CODES = _DATA["phoneLocationCodes"]
DOCUMENT_TYPES = _DATA["documentTypes"]
LOYALTY_TIERS = _DATA["loyaltyTiers"]
FARE_RULES = _DATA["fareRules"]
CORPORATE_CODES = _DATA["corporateCodes"]
EMAIL_DOCUMENTS = _DATA["emailDocuments"]
SEGMENT_STATUS_LABELS = _DATA["segmentStatusLabels"]
