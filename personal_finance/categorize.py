from __future__ import annotations
import json
from decimal import Decimal
from pathlib import Path

DROPDOWN_TYPE_VALUES = ["Fixed", "Variable"]
DROPDOWN_CATEGORY_VALUES = ["Food", "Transportation", "Shopping", "Other", "Health"]
DROPDOWN_CATEGORY = {
    "food": "Food",
    "shopping": "Shopping",
    "supercharging": "Transportation",
    "parking": "Transportation",
    "rideshare": "Transportation",
    "doctor": "Health",
    "healthcare": "Health",
    "rent": "Other",
    "insurance": "Other",
    "cleaning": "Other",
    "fitness": "Other",
    "coworking": "Other",
    "nails": "Other",
    "donation": "Other",
    "utilities": "Other",
    "subscription": "Other",
    "entertainment": "Other",
    "recreation": "Other",
    # startup / unknown intentionally absent -> "" (blank, no dropdown value)
}


def to_dropdown_category(fine: str) -> str:
    """Fold an internal fine category into one of the 5 dropdown values
    (Food/Transportation/Shopping/Other/Health), or "" if it has no valid
    dropdown bucket (e.g. unknown/startup) so the cell is left blank."""
    return DROPDOWN_CATEGORY.get(fine, "")

KNOWN_FIXED = {
    "rent",
    "insurance",
    "cleaning",
    "fitness",
    "coworking",
    "nails",
    "doctor",
    "donation",
    "utilities",
    "supercharging",
    "subscription",
}

STARTUP_KEYWORDS = [
    "retellai",
    "google workspace",
    "svcskhemrajllc",
    "render",
    "claude",
    "openai",
    "github",
    "google drive",
]

CANCELED_KEYWORDS = [
    "associated bank",
    "progressive",
    "green chef",
    "replit",
    "figma",
    "cursor",
    "reclaim",
    "oura",
    "old girls club",
    "1password",
    "bear",
    "google photos",
    "myfitnesspal",
    "notion",
]

DEFAULT_FIXED_RULES = [
    ("justin", "rent"),
    ("rent", "rent"),
    ("tesla insurance", "insurance"),
    ("tidy cleaning", "cleaning"),
    ("equinox", "fitness"),
    ("classpass", "fitness"),
    ("industrious", "coworking"),
    ("nails on the m", "nails"),
    ("vagaro", "nails"),
    ("gupta", "doctor"),
    ("la food bank", "donation"),
    ("utilities", "utilities"),
    ("supercharger", "supercharging"),
    ("netflix", "subscription"),
    ("laundry", "subscription"),
    ("spotify", "subscription"),
    ("surfline", "subscription"),
    ("opal", "subscription"),
    ("google one", "subscription"),
    ("apple.com/bill", "subscription"),
    ("pp*apple.com", "subscription"),
]

# Variable categories: eating out, shopping, entertainment
DEFAULT_VARIABLE_RULES = [
    # Food — groceries + restaurants share one weekly variable budget
    ("whole foods", "food"),
    ("wholefds", "food"),   # WHOLEFDS MON — Teller's truncated Whole Foods string
    ("erewhon", "food"),
    ("trader joe", "food"),
    ("pavilions", "food"),
    ("rainbow acres", "food"),
    ("sprouts", "food"),
    ("target", "shopping"),
    # Eating out — POS prefixes
    ("tst*", "food"),       # Toast POS = always restaurant/cafe
    ("sq *", "food"),       # Square POS = often restaurant
    # Eating out — generic patterns
    ("restaurant", "food"),
    ("cafe", "food"),
    ("café", "food"),
    ("coffee", "food"),
    ("doughnut", "food"),
    ("donut", "food"),
    ("pizza", "food"),
    ("taco", "food"),
    ("sushi", "food"),
    ("ramen", "food"),
    ("burger", "food"),
    ("bbq", "food"),
    ("deli", "food"),
    ("grill", "food"),
    ("kitchen", "food"),
    ("bakery", "food"),
    ("juice", "food"),
    ("smoothie", "food"),
    ("bar ", "food"),
    # Eating out — known chains/spots
    ("kreation", "food"),
    ("doordash", "food"),
    ("ubereats", "food"),
    ("uber eats", "food"),
    ("postmates", "food"),
    ("grubhub", "food"),
    ("chipotle", "food"),
    ("sweetgreen", "food"),
    ("cava", "food"),
    ("starbucks", "food"),
    ("blue bottle", "food"),
    ("mendocino farms", "food"),
    ("sidecar", "food"),
    ("proper", "food"),
    # Shopping
    ("amazon", "shopping"),
    ("amzn", "shopping"),
    ("etsy", "shopping"),
    ("aritzia", "shopping"),
    ("sephora", "shopping"),
    ("nordstrom", "shopping"),
    ("zara", "shopping"),
    ("h&m", "shopping"),
    ("uniqlo", "shopping"),
    ("revolve", "shopping"),
    ("lululemon", "shopping"),
    ("apple store", "shopping"),
    # Healthcare
    ("village eyes optometry", "healthcare"),
    ("medicalctr", "healthcare"),
    ("levi dpm", "healthcare"),
    ("one medical", "healthcare"),
    ("1-800 contacts", "healthcare"),
    ("optometry", "healthcare"),
    ("optometric", "healthcare"),
    ("optical", "healthcare"),
    ("vision center", "healthcare"),
    ("dental", "healthcare"),
    ("dentist", "healthcare"),
    ("pharmacy", "healthcare"),
    ("cvs", "healthcare"),
    ("walgreens", "healthcare"),
    ("medical", "healthcare"),
    ("clinic", "healthcare"),
    ("urgent care", "healthcare"),
    # Transportation
    ("city of santa monica", "parking"),
    ("ips:meters", "parking"),
    ("laz parking", "parking"),
    ("ladot meter", "parking"),
    ("parking", "parking"),
    ("lyft", "rideshare"),
    ("uber", "rideshare"),
    # Entertainment
    ("movie", "entertainment"),
    ("amc ", "entertainment"),
    ("cinemark", "entertainment"),
    ("event", "entertainment"),
    ("experience", "entertainment"),
    ("ticketmaster", "entertainment"),
    ("axs.com", "entertainment"),
    ("eventbrite", "entertainment"),
    ("stubhub", "entertainment"),
]


def normalize(text: str) -> str:
    return (text or "").lower().strip()


# These get populated by load_vendor_rules() at startup.
FIXED_VENDOR_RULES = list(DEFAULT_FIXED_RULES)
VARIABLE_RULES = list(DEFAULT_VARIABLE_RULES)
IGNORED_KEYWORDS: list[str] = []
DEFAULT_IGNORED_KEYWORDS = [
    "chase credit crd autopay",
    "american express ach payment",
]


def load_vendor_rules(rules_path: Path) -> None:
    if not rules_path.exists():
        return
    try:
        rules = json.loads(rules_path.read_text())
    except (json.JSONDecodeError, OSError):
        return
    user_fixed = [(r["match"].lower(), r["category"]) for r in rules.get("fixed", [])]
    user_variable = [(r["match"].lower(), r["category"]) for r in rules.get("variable", [])]
    FIXED_VENDOR_RULES[:0] = user_fixed
    VARIABLE_RULES[:0] = user_variable
    for k in rules.get("startup_keywords", []):
        if k not in STARTUP_KEYWORDS:
            STARTUP_KEYWORDS.append(k.lower())
    for k in rules.get("canceled_keywords", []):
        if k not in CANCELED_KEYWORDS:
            CANCELED_KEYWORDS.append(k.lower())
    for k in rules.get("ignored", []):
        IGNORED_KEYWORDS.append(k.lower())


def is_ignored(description: str) -> bool:
    d = normalize(description)
    return any(k in d for k in DEFAULT_IGNORED_KEYWORDS + IGNORED_KEYWORDS)


def classify(description: str) -> tuple[str, str | None]:
    d = normalize(description)
    for key, cat in FIXED_VENDOR_RULES:
        if key in d:
            return cat, "fixed"
    for key, cat in VARIABLE_RULES:
        if key in d:
            return cat, "variable"
    for key in STARTUP_KEYWORDS:
        if key in d:
            return "startup", None
    return "unknown", None


def normalize_category(category: str) -> str:
    if category in {"eating out", "groceries"}:
        return "food"
    return category


# Explicit display names for common known vendors.
VENDOR_DISPLAY = [
    ("wholefds", "Whole Foods"),
    ("whole foods", "Whole Foods"),
    ("trader joe", "Trader Joe's"),
    ("erewhon", "Erewhon"),
    ("pavilions", "Pavilions"),
    ("sprouts", "Sprouts"),
    ("rainbow acres", "Rainbow Acres"),
    ("amzn", "Amazon"),
    ("amazon", "Amazon"),
    ("apple.com", "Apple"),
    ("apple store", "Apple Store"),
    ("target", "Target"),
    ("starbucks", "Starbucks"),
    ("chipotle", "Chipotle"),
    ("sweetgreen", "Sweetgreen"),
    ("kreation", "Kreation"),
    ("doordash", "DoorDash"),
    ("ubereats", "Uber Eats"),
    ("uber eats", "Uber Eats"),
    ("uber", "Uber"),
    ("lyft", "Lyft"),
    ("postmates", "Postmates"),
    ("grubhub", "Grubhub"),
    ("netflix", "Netflix"),
    ("spotify", "Spotify"),
    ("equinox", "Equinox"),
    ("classpass", "ClassPass"),
    ("industrious", "Industrious"),
    ("village eyes optometry", "Village Eyes Optometry"),
    ("medicalctr", "Medical Center of Santa Monica"),
    ("levi dpm", "Michael J Levi DPM"),
    ("one medical", "One Medical"),
    ("1-800 contacts", "1-800 Contacts"),
    ("cvs", "CVS Pharmacy"),
    ("walgreens", "Walgreens"),
    ("etsy", "Etsy"),
    ("aritzia", "Aritzia"),
    ("sephora", "Sephora"),
    ("nordstrom", "Nordstrom"),
    ("lululemon", "Lululemon"),
    ("uniqlo", "Uniqlo"),
    ("city of santa monica", "City of Santa Monica"),
    ("laz parking", "LAZ Parking"),
    ("ladot meter", "LADOT Meter Parking"),
    ("ips:meters", "City Parking Meter"),
    ("airbnb", "Airbnb"),
]

# Leading point-of-sale / processor prefixes to strip from raw descriptions.
_POS_PREFIXES = ["tst*", "sq *", "sq*", "pp*", "sp ", "cke*"]


def pretty_description(raw: str) -> str:
    """Convert a raw bank description into a clean, readable vendor name."""
    if not raw:
        return ""
    low = raw.lower()
    for key, display in VENDOR_DISPLAY:
        if key in low:
            return display

    s = raw.strip()
    sl = s.lower()
    for pref in _POS_PREFIXES:
        if sl.startswith(pref):
            s = s[len(pref):].lstrip()
            break

    if "*" in s:
        s = s.split("*", 1)[0].strip()

    tokens = s.split()
    cleaned: list[str] = []
    for tok in tokens:
        t = tok.strip()
        bare = t.lstrip("#")
        if bare.isdigit():
            continue
        if t.startswith("#"):
            continue
        if any(ch.isdigit() for ch in t) and any(c in t for c in ("/", ".", "-")):
            continue
        cleaned.append(t)

    while cleaned and sum(c.isdigit() for c in cleaned[-1]) >= max(2, len(cleaned[-1]) - 1):
        cleaned.pop()

    if len(cleaned) >= 3 and cleaned[-1].isupper() and len(cleaned[-1]) == 2 and cleaned[-1].isalpha():
        cleaned.pop()

    out = " ".join(cleaned).strip(" -.,")
    if not out:
        out = s.strip()
    return " ".join(w.capitalize() for w in out.split())


def is_canceled(description: str) -> bool:
    d = normalize(description)
    return any(k in d for k in CANCELED_KEYWORDS)


def is_expense(account_name: str, amount: Decimal) -> bool:
    # Checking: only money OUT (negative) is an expense. Credit cards: positive = charge.
    if account_name == "Chase Main Checking":
        return amount < 0
    return amount > 0
