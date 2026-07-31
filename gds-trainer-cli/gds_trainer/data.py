"""Reference/constant tables, ported verbatim from script.js."""

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
AIRLINES = ["AA", "UA", "DL", "WN", "B6", "AS", "NK", "F9"]
AIRLINE_NUMERIC_CODES = {
    "AA": "001", "UA": "016", "DL": "006", "WN": "526",
    "B6": "279", "AS": "027", "NK": "487", "F9": "351",
}
EQUIP = ["738", "73G", "320", "321", "32N", "E75", "CR9", "777", "788", "319"]
CLASSES = ["F", "J", "C", "Y", "B", "M"]

CLASS_FARE_MULT = {"F": 5.5, "J": 4.2, "C": 3.6, "Y": 1.6, "B": 1.3, "M": 1.0}

TAX_POOL = [
    {"code": "US", "label": "U.S. TRANSPORTATION TAX"},
    {"code": "XF", "label": "PASSENGER FACILITY CHARGE"},
    {"code": "AY", "label": "SEPTEMBER 11TH SECURITY FEE"},
    {"code": "ZP", "label": "PASSENGER SERVICE CHARGE"},
    {"code": "YQ", "label": "CARRIER-IMPOSED SURCHARGE"},
    {"code": "YR", "label": "CARRIER-IMPOSED SURCHARGE"},
]

SSR_CODES = {
    "WCHR": "WHEELCHAIR - CAN WALK TO/FROM SEAT",
    "WCHS": "WHEELCHAIR - MUST BE CARRIED SHORT DISTANCE",
    "WCHC": "WHEELCHAIR - IMMOBILE, CARRIED TO SEAT",
    "VGML": "VEGETARIAN MEAL",
    "BBML": "BABY MEAL",
    "CHML": "CHILD MEAL",
    "KSML": "KOSHER MEAL",
    "MOML": "MUSLIM MEAL",
    "DBML": "DIABETIC MEAL",
    "BLND": "BLIND PASSENGER",
    "DEAF": "DEAF PASSENGER",
    "UMNR": "UNACCOMPANIED MINOR",
    "PETC": "PET IN CABIN",
    "BSCT": "BASSINET REQUEST",
    "SPML": "SPECIAL MEAL - SEE FREE TEXT",
    "XBAG": "EXTRA BAGGAGE",
}

CARD_TYPES = {
    "VI": "VISA", "CA": "MASTERCARD", "AX": "AMERICAN EXPRESS",
    "DC": "DINERS CLUB", "DS": "DISCOVER", "JC": "JCB",
}

PHONE_LOC_CODES = ["A", "H", "B", "C", "M", "F", "HTL"]
