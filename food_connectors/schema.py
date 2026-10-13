"""Common product schema shared by all adapters."""
from __future__ import annotations
import datetime as _dt, re
from dataclasses import dataclass, field, asdict

NUTRIENTS = ("kcal", "protein", "fat", "satfat", "carbs", "sugar", "fiber", "salt")

@dataclass
class Product:
    source: str                 # adapter id, e.g. "gurkerl"
    store: str                  # retailer / shop name
    name: str
    brand: str | None = None
    price_eur: float | None = None
    unit_price_eur: float | None = None   # per unit below
    unit: str | None = None               # "kg", "l", "Stk"
    size_g: float | None = None           # pack size in g / ml
    nutrition_100g: dict = field(default_factory=dict)  # keys from NUTRIENTS
    ean: str | None = None
    image_url: str | None = None
    producer: str | None = None
    producer_id: str | None = None        # Identitätskennzeichen, e.g. "AT 40047 EG"
    origin: str | None = None
    category: str | None = None
    source_url: str | None = None
    source_id: str | None = None
    fetched_at: str = field(default_factory=lambda: _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"))
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

ID_RE = re.compile(r"\b(?:AT|DE|IT|HU|PL|CZ|SK|SI|NL|BE|FR|ES|DK)[ -]?[A-Z0-9.-]{2,12}[ -](?:EG|EWG|EC|CE)\b")

def find_producer_id(text: str | None) -> str | None:
    if not text: return None
    ids = sorted(set(m.group(0) for m in ID_RE.finditer(text)))
    return ", ".join(ids) or None

def parse_size_g(text: str | None) -> float | None:
    if not text: return None
    t = text.lower().replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", t)
    mult = 1.0
    if m:
        mult = float(m.group(1)); v, u = float(m.group(2)), m.group(3)
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|l)\b", t)
        if not m: return None
        v, u = float(m.group(1)), m.group(2)
    return round(mult * v * (1000 if u in ("kg", "l") else 1), 1)

READY_MEAL_RE = re.compile(r"gulasch|chili|eintopf|suppentopf|lasagne|curry|risotto|geschnetzelt|bolognese|ripperl|spieß|spiess|knödel mit|fleckerl|gericht|menü|menu|bowl|pfanne|stroganoff|frikassee|paella|moussaka|tikka|masala|nasi|bami|gnocchi|tortellini|ravioli|spätzle|schmarrn|cannelloni|braten|roulade|fleischlaibchen|cevapcici|pasta|nudeln mit|reis mit|linsen|bohnen|erbsen|suppe|dal|ramen|chicken|hendl|huhn|pute", re.I)
NOT_MEAL_RE = re.compile(r"\bfix\b|fix für|würz|gewürz|sauce|soße|sosse|basis|pulver|instant|bouillon|brühwürfel|rohe?|geschnitten|faschiert|filet|frisch(?:fleisch)?|chips|snack|riegel|aufstrich|tupper|hundefutter|katze", re.I)

def looks_like_ready_meal(name: str, category: str | None = None) -> bool:
    s = f"{name} {category or ''}"
    return bool(READY_MEAL_RE.search(s)) and not NOT_MEAL_RE.search(name)
