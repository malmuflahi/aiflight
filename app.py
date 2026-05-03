import json
import os
import re
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from difflib import get_close_matches
from urllib.parse import quote_plus
from flask import Flask, render_template, request, jsonify

try:
    import httpx
except ImportError:
    httpx = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DUFFEL_ACCESS_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OpenAI else None

@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
        "style-src 'self'; script-src 'self'; form-action 'self'; "
        "base-uri 'self'; frame-ancestors 'none'"
    )
    return response

AIRPORT_MAP = {
    "egypt": "CAI", "eygpt": "CAI", "egpyt": "CAI", "egyptt": "CAI", "cairo": "CAI", "cai": "CAI",
    "new york": "JFK", "newyork": "JFK", "nyc": "JFK",
    "manhattan": "JFK", "brooklyn": "JFK",
    "lga": "LGA", "laguardia": "LGA", "la guardia": "LGA", "jfk": "JFK", "ewr": "EWR",
    "boston": "BOS", "bostn": "BOS", "bos": "BOS",
    "london": "LHR", "londen": "LHR", "lhr": "LHR", "heathrow": "LHR",
    "houston": "IAH", "iah": "IAH", "hou": "HOU",
    "dallas": "DFW", "arlington": "DFW", "dfw": "DFW",
    "dubai": "DXB", "dubia": "DXB", "dubi": "DXB", "dxb": "DXB",
    "los angeles": "LAX", "los angels": "LAX", "los anglees": "LAX", "la": "LAX", "lax": "LAX",
    "san francisco": "SFO", "sfo": "SFO",
    "chicago": "ORD", "ord": "ORD",
    "miami": "MIA", "mia": "MIA",
    "atlanta": "ATL", "atl": "ATL",
    "paris": "CDG", "prs": "CDG", "cdg": "CDG", "orly": "ORY", "ory": "ORY",
    "rome": "FCO", "fco": "FCO",
    "amman": "AMM", "amm": "AMM",
    "tokyo": "HND", "hnd": "HND",
    "toronto": "YYZ", "yyz": "YYZ"
}

TYPO_MAP = {
    "wana": "want",
    "wanna": "want",
    "wnt": "want",
    "fligt": "flight",
    "flght": "flight",
    "frm": "from",
    "fro": "from",
    "wit": "with",
    "wth": "with",
    "frend": "friend",
    "frends": "friends",
    "freind": "friend",
    "freinds": "friends",
    "won": "one",
    "comfrt": "comfort",
    "comft": "comfort",
    "retun": "return",
    "bak": "back",
    "trp": "trip",
    "wrld": "world",
    "worldcup": "world cup",
    "texs": "texas",
    "urgnt": "urgent",
    "adlt": "adult",
    "adlut": "adult",
    "adlts": "adults",
    "adults.": "adults",
    "pariss": "paris",
    "parisss": "paris",
    "prs": "paris",
    "londn": "london",
    "londen": "london",
    "eygpt": "egypt",
    "egpyt": "egypt",
    "dubia": "dubai",
    "dubi": "dubai",
    "newyork": "new york"
}

WORLD_CUP_TEXAS_FIRST_MATCH = {
    "name": "First Texas FIFA World Cup 2026 match",
    "match": "Germany vs Curacao",
    "date": "2026-06-14",
    "venue": "NRG Stadium",
    "fifa_venue": "Houston Stadium",
    "city": "Houston",
    "state": "Texas",
    "airport": "IAH",
    "source": "FIFA and NRG Park schedule"
}

NEARBY_AIRPORTS = {
    "JFK": ["JFK", "EWR", "LGA"],
    "EWR": ["EWR", "JFK", "LGA"],
    "LGA": ["LGA", "JFK", "EWR"],
    "LHR": ["LHR", "LGW"],
    "LGW": ["LGW", "LHR"],
    "CDG": ["CDG", "ORY"],
    "ORY": ["ORY", "CDG"],
    "IAH": ["IAH", "HOU"],
    "HOU": ["HOU", "IAH"]
}

DAY_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7
}

NUMBER_WORDS = {
    **DAY_WORDS,
    "eight": 8,
    "nine": 9,
    "ten": 10
}

PRICE_OBSERVATIONS = []
MAX_PRICE_OBSERVATIONS = 250
FEEDBACK_EVENTS = []
MAX_FEEDBACK_EVENTS = 250
API_EVENTS = deque(maxlen=500)
RATE_LIMIT_BUCKETS = defaultdict(deque)

PLATFORM_LAYERS = [
    "api_gateway",
    "ai_brain_loop",
    "trip_orchestrator",
    "flight_data_platform",
    "data_quality_normalization",
    "feature_engine",
    "ai_ml_intelligence",
    "decision_engine",
    "llm_explanation",
    "results_experience",
    "feedback_learning_loop",
    "monitoring_evals_safety"
]

FLIGHT_PROVIDERS = [
    {"id": "duffel", "name": "Duffel API", "status": "live"},
    {"id": "travelpayouts", "name": "Travelpayouts", "status": "planned"},
    {"id": "future_gds", "name": "Future GDS / direct airline APIs", "status": "planned"},
    {"id": "fallback_links", "name": "Google/Kayak/Skyscanner fallback links", "status": "available"}
]

AIRLINE_PRICING_MODEL = {
    "airline_goal": "Maximize airline revenue per seat and per customer shopping context.",
    "pricing_inputs": [
        "time before departure",
        "remaining capacity and booking pace",
        "route demand and seasonality",
        "day/time of travel",
        "length of stay",
        "competitor prices",
        "customer shopping context",
        "fare bundles, bags, seats, refunds, and flexibility"
    ],
    "weak_points": [
        "one airline cannot recommend a competitor",
        "one airline cannot optimize nearby airports across competitors",
        "one airline is focused on revenue, not traveler value",
        "dynamic bundles can make the lowest fare a worse total deal",
        "forecast errors and low inventory can create unstable prices"
    ],
    "buyer_counter_moves": [
        "compare nearby airports",
        "shift departure and return dates",
        "compare total trip cost, not ticket price only",
        "rank comfort, stops, and timing against savings",
        "watch unstable fares when there is enough time"
    ]
}

EVAL_CASES = [
    {
        "name": "paris_roundtrip",
        "message": "I want to visit Paris from NYC June 10 2026 return June 17 2026 1 adult economy",
        "expected": {"origin": "JFK", "destination": "CDG", "trip_type": "roundtrip"}
    },
    {
        "name": "egypt_typo",
        "message": "go to eygpt from JFK 6/27/2026 one way 1 adult economy",
        "expected": {"origin": "JFK", "destination": "CAI", "trip_type": "oneway"}
    },
    {
        "name": "world_cup_texas",
        "message": "I want to watch the first World Cup match in Texas. Book me a round trip flight from NYC, arrive one day before the match, come back two days after, 1 adult, economy, best value.",
        "expected": {"origin": "JFK", "destination": "IAH", "trip_type": "roundtrip", "depart_date": "2026-06-13", "return_date": "2026-06-16"}
    },
    {
        "name": "london_from_boston",
        "message": "I want to visit London from Boston July 5 2026 return July 12 2026, 2 adults, cheapest economy.",
        "expected": {"origin": "BOS", "destination": "LHR", "trip_type": "roundtrip"}
    },
    {
        "name": "la_week_two_friends",
        "message": "I want to go to la for one week with two friends, comfort",
        "expected": {"destination": "LAX", "trip_type": "roundtrip", "trip_duration_days": 7, "adults": 3, "priority": "comfort"}
    }
]

def utc_now():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

def client_fingerprint():
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"

def trace_step(layer, status, detail, **extra):
    step = {
        "layer": layer,
        "status": status,
        "detail": detail,
        "at": utc_now()
    }
    step.update(extra)
    return step

def record_api_event(endpoint, status, detail="", **extra):
    event = {
        "endpoint": endpoint,
        "status": status,
        "detail": detail,
        "at": utc_now()
    }
    event.update(extra)
    API_EVENTS.append(event)

def json_error(message, status_code=400, code="bad_request"):
    record_api_event(request.path, "blocked", code)
    return jsonify({"error": message, "code": code}), status_code

def rate_limit_key(endpoint):
    return f"{client_fingerprint()}:{endpoint}"

def is_rate_limited(endpoint, limit=30, window_seconds=60):
    now = time.time()
    bucket = RATE_LIMIT_BUCKETS[rate_limit_key(endpoint)]

    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()

    if len(bucket) >= limit:
        return True

    bucket.append(now)
    return False

def detect_abuse_text(text):
    text = str(text or "")
    lower = text.lower()
    blocked_terms = (
        "ignore previous instructions",
        "system prompt",
        "api key",
        "duffel token",
        "openai key"
    )
    if len(text) > 1800:
        return "Message is too long for one trip request."
    if any(term in lower for term in blocked_terms):
        return "I can help with flight planning, but I cannot expose or manipulate system credentials."
    if len(set(text.split())) < 4 and len(text.split()) > 60:
        return "Message looks repetitive. Send one clear trip request."
    return ""

def validate_chat_payload(data):
    if not isinstance(data, dict):
        return None, "Request body must be JSON."

    message = str(data.get("message") or "").strip()
    if not message:
        return None, "Message is required."

    abuse_reason = detect_abuse_text(message)
    if abuse_reason:
        return None, abuse_reason

    history = data.get("history") if isinstance(data.get("history"), list) else []
    trip = coerce_chat_trip(data.get("trip") or {})
    return {
        "message": message,
        "history": history[-12:],
        "trip": trip
    }, ""

def validate_search_trip(data):
    if not isinstance(data, dict):
        return None, "Request body must be JSON."

    trip = {
        "origin": normalize_airport(data.get("origin", "LGA")),
        "destination": normalize_airport(data.get("destination", "BOS")),
        "trip_type": normalize_trip_type(data.get("tripType", data.get("trip_type", "oneway"))) or "oneway",
        "depart_date": data.get("departDate", data.get("depart_date", "")),
        "return_date": data.get("returnDate", data.get("return_date", "")),
        "adults": parse_passenger_count(data.get("adults", 1), default=1, minimum=1),
        "children": parse_passenger_count(data.get("children", 0)),
        "infants": parse_passenger_count(data.get("infants", 0)),
        "priority": normalize_priority(data.get("priority", "balanced")) or "balanced",
        "cabin": normalize_cabin(data.get("cabin", "economy")) or "economy",
        "seat": normalize_seat(data.get("seat", "none")) or "none",
        "preference": str(data.get("preference", "")).strip(),
        "event_context": data.get("event_context", {}) if isinstance(data.get("event_context"), dict) else {}
    }

    if not is_airport_code(trip["origin"]):
        return None, "Origin must be a valid airport or known city."
    if not is_airport_code(trip["destination"]):
        return None, "Destination must be a valid airport or known city."
    if not is_valid_date(trip["depart_date"]):
        return None, "A valid departure date is required."
    if trip["trip_type"] == "roundtrip" and not is_valid_date(trip["return_date"]):
        return None, "A valid return date is required for round trips."

    return trip, ""

def normalize_airport(value):
    value = (value or "").strip()
    if not value:
        return ""

    key = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    key = re.sub(r"\s+", " ", key).strip()
    previous_key = None
    while key and key != previous_key:
        previous_key = key
        key = re.sub(r"^(?:i\s+)?(?:want|need)\s+(?:to\s+)?(?:go\s+)?(?:flight\s+)?(?:to\s+)?", "", key).strip()
        key = re.sub(r"^(?:book\s+me)\s+(?:flight\s+)?(?:to\s+)?", "", key).strip()
        key = re.sub(r"^(?:depart|departure|leaving|leave|start)\s+(?:from\s+)?", "", key).strip()
        key = re.sub(r"^flight\s+(?:to\s+)?", "", key).strip()
        key = re.sub(r"^(?:to|for)\s+", "", key).strip()
        key = re.sub(r"^(?:go|going|fly|flying|travel|traveling|visit|visiting)\s+(?:to\s+)?", "", key).strip()
    if key in AIRPORT_MAP:
        return AIRPORT_MAP[key]

    if re.fullmatch(r"[a-zA-Z]{3}", value):
        return value.upper()

    for name, code in sorted(AIRPORT_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", key):
            return code

    for token in key.split():
        matches = get_close_matches(token, AIRPORT_MAP.keys(), n=1, cutoff=0.82)
        if matches:
            return AIRPORT_MAP[matches[0]]

    return value.upper()

def normalize_user_text(text):
    text = str(text or "").lower()
    text = re.sub(r"[^a-z0-9/., -]+", " ", text)
    tokens = []
    for token in text.split():
        clean = re.sub(r"[^a-z0-9]+", "", token)
        replacement = TYPO_MAP.get(clean)
        if replacement:
            token = replacement
        tokens.append(token)

    normalized = " ".join(tokens)
    normalized = re.sub(r"\bl\s*a\b", "la", normalized)
    normalized = re.sub(r"\bme and my friend\b", "2 adults", normalized)
    normalized = re.sub(r"\bme and one friend\b", "2 adults", normalized)
    normalized = re.sub(r"\bmy friend and me\b", "2 adults", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized

def parse_passenger_count(value, default=0, minimum=0):
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default

    return max(minimum, min(count, 9))

def is_valid_date(value):
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except (TypeError, ValueError):
        return False

def is_airport_code(value):
    return bool(re.fullmatch(r"[A-Z]{3}", value or ""))

def blank_chat_trip():
    return {
        "origin": "",
        "destination": "",
        "trip_type": "",
        "depart_date": "",
        "return_date": "",
        "date_window": "",
        "trip_duration_days": None,
        "adults": None,
        "children": 0,
        "infants": 0,
        "priority": "",
        "cabin": "",
        "seat": "none",
        "preference": "",
        "event_context": {}
    }

def coerce_chat_trip(value):
    trip = blank_chat_trip()
    if isinstance(value, dict):
        for key in trip:
            if key in value:
                trip[key] = value[key]

    trip["origin"] = normalize_airport(trip.get("origin", "")) if trip.get("origin") else ""
    trip["destination"] = normalize_airport(trip.get("destination", "")) if trip.get("destination") else ""
    trip["trip_type"] = normalize_trip_type(trip.get("trip_type", ""))
    trip["depart_date"] = trip.get("depart_date") if is_valid_date(trip.get("depart_date")) else ""
    trip["return_date"] = trip.get("return_date") if is_valid_date(trip.get("return_date")) else ""
    trip["adults"] = coerce_optional_count(trip.get("adults"), minimum=1)
    trip["children"] = coerce_optional_count(trip.get("children"), default=0)
    trip["infants"] = coerce_optional_count(trip.get("infants"), default=0)
    trip["priority"] = normalize_priority(trip.get("priority", ""))
    trip["cabin"] = normalize_cabin(trip.get("cabin", ""))
    trip["seat"] = normalize_seat(trip.get("seat", "none")) or "none"
    trip["preference"] = str(trip.get("preference") or "").strip()
    trip["date_window"] = str(trip.get("date_window") or "").strip()
    trip["trip_duration_days"] = coerce_optional_count(trip.get("trip_duration_days"), default=None, minimum=1, maximum=30)
    trip["event_context"] = trip.get("event_context") if isinstance(trip.get("event_context"), dict) else {}
    return trip

def coerce_optional_count(value, default=None, minimum=0, maximum=9):
    if value in ("", None):
        return default
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(count, maximum))

def normalize_trip_type(value):
    value = str(value or "").lower().replace("-", " ").strip()
    if value in ("oneway", "one way", "single"):
        return "oneway"
    if value in ("roundtrip", "round trip", "return"):
        return "roundtrip"
    return ""

def normalize_priority(value):
    value = str(value or "").lower().strip()
    if value in ("cheapest", "cheap", "lowest", "lowest price", "budget"):
        return "cheapest"
    if value in ("fastest", "fast", "quick", "quickest"):
        return "fastest"
    if value in ("comfort", "comfortable", "low stress", "premium", "flexible"):
        return "comfort"
    if value in ("balanced", "best value", "value"):
        return "balanced"
    return ""

def normalize_cabin(value):
    value = str(value or "").lower().strip()
    if value in ("economy", "coach"):
        return "economy"
    if value in ("premium", "premium economy", "premium_economy"):
        return "premium"
    if value == "business":
        return "business"
    if value == "first":
        return "first"
    return ""

def normalize_seat(value):
    value = str(value or "").lower().strip()
    if value in ("window", "aisle"):
        return value
    return "none"

def parse_chat_date(text):
    text = (text or "").lower()
    today = datetime.now().date()

    iso_dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    valid_iso = [date for date in iso_dates if is_valid_date(date)]
    if valid_iso:
        return valid_iso

    found = []
    for month, day, year in re.findall(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b", text):
        try:
            found.append(datetime(int(year), int(month), int(day)).date().strftime("%Y-%m-%d"))
        except ValueError:
            continue

    if "tomorrow" in text:
        found.append((today + timedelta(days=1)).strftime("%Y-%m-%d"))

    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    month_pattern = "|".join(months)
    patterns = [
        rf"\b({month_pattern})\s+(\d{{1,2}})(?:,?\s*(20\d{{2}}))?\b",
        rf"\b(\d{{1,2}})\s+({month_pattern})(?:,?\s*(20\d{{2}}))?\b"
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text):
            if match[0].isdigit():
                day = int(match[0])
                month = months[match[1]]
                year = int(match[2]) if match[2] else today.year
            else:
                month = months[match[0]]
                day = int(match[1])
                year = int(match[2]) if match[2] else today.year

            try:
                candidate = datetime(year, month, day).date()
            except ValueError:
                continue

            if candidate < today:
                try:
                    candidate = datetime(year + 1, month, day).date()
                except ValueError:
                    continue
            found.append(candidate.strftime("%Y-%m-%d"))

    return found

def parse_flexible_date_range(text):
    text = (text or "").lower()
    today = datetime.now().date()
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    month_pattern = "|".join(months)
    match = re.search(rf"\b({month_pattern})\b(?:\s+any)?\s+(\d{{1,2}})\s*(?:-|to)\s*(\d{{1,2}})(?:,?\s*(20\d{{2}}))?", text)
    if not match:
        return {}

    month = months[match.group(1)]
    start_day = int(match.group(2))
    end_day = int(match.group(3))
    year = int(match.group(4)) if match.group(4) else today.year

    try:
        start = datetime(year, month, start_day).date()
        end = datetime(year, month, end_day).date()
    except ValueError:
        return {}

    if start < today:
        try:
            start = datetime(year + 1, month, start_day).date()
            end = datetime(year + 1, month, end_day).date()
        except ValueError:
            return {}

    duration_match = re.search(r"\b(\d+)\s*(?:day|days|night|nights)\b", text)
    if duration_match:
        stay_days = int(duration_match.group(1))
    elif "one week" in text or "1 week" in text or "week vacation" in text or "week vecation" in text:
        stay_days = 7
    else:
        stay_days = max(1, min(7, (end - start).days))

    return_date = start + timedelta(days=stay_days)
    if return_date > end and "week" not in text:
        return_date = end

    return {
        "depart_date": start.strftime("%Y-%m-%d"),
        "return_date": return_date.strftime("%Y-%m-%d"),
        "trip_type": "roundtrip",
        "date_window": f"{start.strftime('%b')} {start.day}-{end.day} flexible"
    }

def month_name_window(text):
    lower = normalize_user_text(text)
    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }
    month_pattern = "|".join(months)
    match = re.search(rf"\b(?:in|around|during|any\s+day\s+in|sometime\s+in)?\s*({month_pattern})(?:\s+(20\d{{2}}))?\b", lower)
    if not match:
        return ""

    # A named month followed by a day is an exact date, not a flexible window.
    after = lower[match.end():match.end() + 5]
    if re.match(r"\s+\d{1,2}\b", after):
        return ""

    today = datetime.now().date()
    month = months[match.group(1)]
    year = int(match.group(2)) if match.group(2) else today.year
    if datetime(year, month, 28).date() < today:
        year += 1
    return datetime(year, month, 1).strftime("%B %Y")

def representative_date_for_window(window, duration_days=None):
    window = str(window or "")
    match = re.search(r"\b([A-Za-z]+)\s+(20\d{2})\b", window)
    if not match:
        return "", ""

    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }
    month = months.get(match.group(1).lower())
    if not month:
        return "", ""

    year = int(match.group(2))
    depart = datetime(year, month, 10).date()
    duration = max(1, min(30, int(duration_days or 7)))
    return_date = depart + timedelta(days=duration)
    return depart.strftime("%Y-%m-%d"), return_date.strftime("%Y-%m-%d")

def parse_number_token(value, default=None):
    value = str(value or "").lower().strip()
    if value in NUMBER_WORDS:
        return NUMBER_WORDS[value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def parse_trip_duration_days(text):
    lower = (text or "").lower()
    if "one week" in lower or "1 week" in lower or "a week" in lower:
        return 7

    match = re.search(r"\b(?:for|stay|staying|maybe|about|around)?\s*(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s*(?:day|days|night|nights)\b", lower)
    if match:
        return max(1, min(30, parse_number_token(match.group(1), 0)))

    return None

def has_date_evidence(text):
    lower = normalize_user_text(text)
    return bool(parse_chat_date(lower) or parse_flexible_date_range(lower) or detect_date_window(lower))

def has_passenger_evidence(text):
    lower = normalize_user_text(text)
    return bool(re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:adult|adults|passenger|passengers|people|person|traveler|travelers|friend|friends)\b", lower)) or any(
        phrase in lower for phrase in ("solo", "alone", "just me", "me only", "myself", "with my wife", "with my husband", "my partner")
    )

def companion_adult_count(text):
    lower = normalize_user_text(text)
    match = re.search(r"\bme\s+and\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:friend|friends|adult|adults|people|traveler|travelers)\b", lower)
    if match:
        companions = parse_number_token(match.group(1), 0)
        if companions > 0:
            return min(9, companions + 1)

    match = re.search(r"\bwith\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+(?:friend|friends|adult|adults|people|traveler|travelers)\b", lower)
    if not match:
        return None

    companions = parse_number_token(match.group(1), 0)
    if companions <= 0:
        return None
    return min(9, companions + 1)

def detect_date_window(text):
    text = (text or "").lower()
    month_window = month_name_window(text)
    if month_window:
        return month_window
    if "next month" in text:
        return "next month"
    if "next week" in text:
        return "next week"
    if "this month" in text:
        return "this month"
    return ""

def is_place_pronoun(value):
    value = re.sub(r"[^a-z]+", "", (value or "").lower())
    return value in ("there", "their", "thier", "thatplace")

def is_non_place_phrase(value):
    value = (value or "").lower()
    return bool(re.search(r"\b(?:week|weeks|day|days|night|nights|vacation|vecation|adult|adults|price|budget)\b", value))

def normalized_place_candidate(value):
    if is_place_pronoun(value) or is_non_place_phrase(value):
        return ""
    code = normalize_airport(value)
    return code if is_airport_code(code) else ""

def is_missing_info_question(text):
    lower = (text or "").lower()
    if "missing" not in lower and "need" not in lower:
        return False
    return any(term in lower for term in ("what info", "what information", "what am i missing", "what im missing", "what i'm missing", "what do you need"))

def detect_world_cup_texas_request(text):
    lower = normalize_user_text(text)
    if "world cup" not in lower or "texas" not in lower:
        return False
    return any(word in lower for word in ("first", "earliest", "only one", "one match", "1 match"))

def parse_day_offset(value, default=1):
    value = str(value or "").lower().strip()
    if value in DAY_WORDS:
        return DAY_WORDS[value]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def resolve_world_cup_texas_trip(text):
    if not detect_world_cup_texas_request(text):
        return {}

    lower = normalize_user_text(text)
    match_date = datetime.strptime(WORLD_CUP_TEXAS_FIRST_MATCH["date"], "%Y-%m-%d").date()
    depart_offset = 1
    return_offset = 1

    arrive_match = re.search(r"\b(?:arrive|get there|land)\s+(?:the\s+)?(one|two|three|four|five|six|seven|\d+)\s+days?\s+before", lower)
    if arrive_match:
        depart_offset = max(0, min(7, parse_day_offset(arrive_match.group(1), 1)))

    return_match = re.search(r"\b(?:come back|return|fly back|back)\s+(?:after\s+)?(one|two|three|four|five|six|seven|\d+)\s+days?\s*(?:after|later)?", lower)
    if return_match:
        return_offset = max(0, min(14, parse_day_offset(return_match.group(1), 1)))

    depart_date = (match_date - timedelta(days=depart_offset)).strftime("%Y-%m-%d")
    return_date = (match_date + timedelta(days=return_offset)).strftime("%Y-%m-%d")

    updates = {
        "destination": WORLD_CUP_TEXAS_FIRST_MATCH["airport"],
        "depart_date": depart_date,
        "return_date": return_date,
        "trip_type": "roundtrip",
        "priority": "balanced",
        "cabin": "economy",
        "event_context": WORLD_CUP_TEXAS_FIRST_MATCH,
        "preference": text
    }

    if any(term in lower for term in ("nyc", "new york", "jfk", "lga", "ewr")):
        updates["origin"] = "JFK"

    if any(term in lower for term in ("book me", "for me", " i ", "i need", "my flight", "me flight")):
        updates["adults"] = 1

    return updates

def rule_extract_trip_details(message):
    text = (message or "").strip()
    lower = normalize_user_text(text)
    updates = {}

    if is_missing_info_question(lower):
        return {}

    route_stop = r"(?:[.,]|$|\s+\d|\s+from|\s+to|\s+depart|\s+departure|\s+leaving|\s+leave|\s+start|\s+jan|\s+january|\s+feb|\s+february|\s+mar|\s+march|\s+apr|\s+april|\s+may|\s+jun|\s+june|\s+jul|\s+july|\s+aug|\s+august|\s+sep|\s+sept|\s+september|\s+oct|\s+october|\s+nov|\s+november|\s+dec|\s+december|\s+on|\s+next|\s+in|\s+with|\s+for|\s+and|\s+back|\s+come\s+back|\s+return)"
    known_origin_pattern = r"nyc|new york|newyork|jfk|lga|ewr|boston|bostn|bos|la|lax|los angeles|chicago|ord|miami|mia|atlanta|atl"
    embedded_direct_route = re.search(rf"\b({known_origin_pattern})\s+to\s+([a-zA-Z .]+?){route_stop}", lower)
    if embedded_direct_route:
        origin_candidate = normalized_place_candidate(embedded_direct_route.group(1))
        destination_candidate = normalized_place_candidate(embedded_direct_route.group(2))
        if origin_candidate and destination_candidate:
            updates["origin"] = origin_candidate
            updates["destination"] = destination_candidate

    direct_route_match = re.search(rf"\b([a-zA-Z .]+?)\s+to\s+([a-zA-Z .]+?){route_stop}", lower)
    if direct_route_match and not (updates.get("origin") and updates.get("destination")):
        origin_candidate = normalized_place_candidate(direct_route_match.group(1))
        destination_candidate = normalized_place_candidate(direct_route_match.group(2))
        if (
            origin_candidate
            and destination_candidate
        ):
            updates["origin"] = origin_candidate
            updates["destination"] = destination_candidate

    reverse_route_match = re.search(rf"\b(?:visit|go|go to|want|need|fly|travel)\s+([a-zA-Z .]+?)\s+from\s+([a-zA-Z .]+?){route_stop}", lower)
    if reverse_route_match:
        updates["destination"] = normalize_airport(reverse_route_match.group(1))
        updates["origin"] = normalize_airport(reverse_route_match.group(2))

    bare_destination_from = re.search(rf"^\s*([a-zA-Z .]+?)\s+from\s+([a-zA-Z .]+?){route_stop}", lower)
    if bare_destination_from and not updates.get("destination"):
        updates["destination"] = normalize_airport(bare_destination_from.group(1))
        updates["origin"] = normalize_airport(bare_destination_from.group(2))

    bare_destination_depart = re.search(rf"^\s*([a-zA-Z .]+?)\s+(?:depart|departure|leaving|leave|start)\s+([a-zA-Z .]+?){route_stop}", lower)
    if bare_destination_depart and not updates.get("destination"):
        updates["destination"] = normalize_airport(bare_destination_depart.group(1))
        updates["origin"] = normalize_airport(bare_destination_depart.group(2))

    simple_destination_patterns = [
        rf"\b(?:want|need)\s+(?:to\s+)?(?:go|fly|travel|visit)\s+(?:to\s+)?([a-zA-Z .]+?){route_stop}",
        rf"\b(?:want|need|book me)\s+(?:flight\s+)?to\s+([a-zA-Z .]+?){route_stop}",
        rf"\b(?:go|fly|travel|visit|going|flying|traveling|visiting)\s+to\s+([a-zA-Z .]+?){route_stop}",
    ]
    for pattern in simple_destination_patterns:
        simple_destination = re.search(pattern, lower)
        if not simple_destination or "destination" in updates or " from " in f" {simple_destination.group(1)} ":
            continue
        destination_candidate = normalized_place_candidate(simple_destination.group(1))
        if destination_candidate:
            updates["destination"] = destination_candidate
            break

    context_destination = re.search(
        rf"\b(?:meeting|conference|event|wedding|work|trip|vacation)\s+in\s+([a-zA-Z .]+?){route_stop}",
        lower
    )
    if context_destination and "destination" not in updates:
        destination_candidate = normalized_place_candidate(context_destination.group(1))
        if destination_candidate:
            updates["destination"] = destination_candidate

    route_match = re.search(rf"\bfrom\s+([a-zA-Z .]+?)\s+(?:to|for)\s+([a-zA-Z .]+?){route_stop}", lower)
    if route_match:
        updates["origin"] = normalize_airport(route_match.group(1))
        if not is_place_pronoun(route_match.group(2)) and not is_non_place_phrase(route_match.group(2)):
            updates["destination"] = normalize_airport(route_match.group(2))
    else:
        for to_match in re.finditer(rf"\b(?:to|for)\s+(?!go\b|fly\b|travel\b|visit\b)([a-zA-Z .]+?){route_stop}", lower):
            if "destination" in updates or " from " in f" {to_match.group(1)} ":
                continue
            destination_candidate = normalized_place_candidate(to_match.group(1))
            if destination_candidate:
                updates["destination"] = destination_candidate
                break

        from_match = re.search(rf"\bfrom\s+([a-zA-Z .]+?){route_stop}", lower)
        if from_match:
            updates["origin"] = normalize_airport(from_match.group(1))

    origin_followup = re.search(rf"\b(?:depart|departure|leaving|leave|start)\s+(?:from\s+)?([a-zA-Z .]+?){route_stop}", lower)
    if origin_followup:
        updates["origin"] = normalize_airport(origin_followup.group(1))

    city_definition = re.search(r"\b(nyc|new york|newyork|jfk|lga|ewr)\s+(?:is|means)\s+(?:new york|nyc)\b", lower)
    if city_definition:
        updates["origin"] = normalize_airport(city_definition.group(1))

    bare_origin = re.fullmatch(r"\s*(nyc|new york|newyork|jfk|lga|ewr|lax|la|los angeles|lga|laguardia|la guardia|bos|boston|bostn)\s*", lower)
    if bare_origin:
        updates["origin"] = normalize_airport(bare_origin.group(1))

    if "round trip" in lower or "roundtrip" in lower or "coming back" in lower or "come back" in lower or "return" in lower or "vacation" in lower or "vecation" in lower:
        updates["trip_type"] = "roundtrip"
    elif "one way" in lower or "one-way" in lower or "single" in lower:
        updates["trip_type"] = "oneway"

    flexible_dates = parse_flexible_date_range(lower)
    if flexible_dates:
        updates.update(flexible_dates)
    else:
        dates = parse_chat_date(lower)
        if dates:
            updates["depart_date"] = dates[0]
            if len(dates) > 1:
                updates["return_date"] = dates[1]
                updates["trip_type"] = "roundtrip"

    if not updates.get("depart_date"):
        window = detect_date_window(lower)
        if window:
            updates["date_window"] = window

    duration_days = parse_trip_duration_days(lower)
    if duration_days:
        updates["trip_duration_days"] = duration_days
        updates["trip_type"] = "roundtrip"
        if updates.get("depart_date") and not updates.get("return_date"):
            updates["return_date"] = shift_date(updates["depart_date"], duration_days)

    adult_match = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:adult|adults|passenger|passengers|people|person|traveler|travelers)\b", lower)
    child_match = re.search(r"\b(\d+)\s+(?:child|children|kid|kids)\b", lower)
    infant_match = re.search(r"\b(\d+)\s+(?:infant|infants|baby|babies)\b", lower)
    friend_total = companion_adult_count(lower)
    if friend_total:
        updates["adults"] = friend_total
    elif adult_match:
        updates["adults"] = parse_number_token(adult_match.group(1), 1)
    elif (
        "friend" not in lower
        and "friends" not in lower
        and ("solo" in lower or "alone" in lower or "just me" in lower or "me only" in lower or "myself" in lower or re.search(r"\bi\s+(?:want|need|am|will|can|have|only|dont|don t)\b", lower))
    ):
        updates["adults"] = 1
    if child_match:
        updates["children"] = int(child_match.group(1))
    if infant_match:
        updates["infants"] = int(infant_match.group(1))

    if "business" in lower:
        updates["cabin"] = "business"
    elif "first class" in lower or "first-class" in lower:
        updates["cabin"] = "first"
    elif "premium" in lower:
        updates["cabin"] = "premium"
    elif "economy" in lower or "coach" in lower:
        updates["cabin"] = "economy"

    cheapest_intent = bool(re.search(r"\b(?:cheap|cheapest|lowest price|budget)\b", lower))
    comfort_negated = bool(re.search(r"\b(?:dont|don t|do not|don't)\s+care\s+about\s+comfort\b", lower))
    stress_intent = any(term in lower for term in ("stress", "painful", "problems", "rested", "reliable", "bad airline", "not bad airline"))
    pay_more_for_less_risk = ("paying more" in lower or "pay more" in lower or "okay paying more" in lower) and any(term in lower for term in ("avoid", "stress", "problem"))
    value_intent = any(term in lower for term in ("not crazy price", "best value", "smartest", "good deal"))

    if cheapest_intent and not stress_intent:
        updates["priority"] = "cheapest"
    elif "fast" in lower or "quick" in lower or "urgent" in lower:
        updates["priority"] = "fastest"
    elif stress_intent or pay_more_for_less_risk or (("comfort" in lower or "comfortable" in lower or "low stress" in lower) and not comfort_negated):
        updates["priority"] = "comfort"
    elif "money" in lower and ("not" in lower or "no concern" in lower or "flexible" in lower):
        updates["priority"] = "comfort"
    elif value_intent:
        updates["priority"] = "balanced"

    if "window" in lower:
        updates["seat"] = "window"
    elif "aisle" in lower:
        updates["seat"] = "aisle"

    if text:
        updates["preference"] = text

    event_updates = resolve_world_cup_texas_trip(text)
    if event_updates:
        updates.update(event_updates)

    return updates

def ai_extract_trip_details(message, current_trip, history):
    if not client:
        return {}

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract flight search details from a travel chat. Return JSON only. "
                        "Use these keys: origin, destination, trip_type, depart_date, return_date, "
                        "date_window, adults, children, infants, priority, cabin, seat, preference. "
                        "Use IATA airport codes when obvious. London or londen should be LHR. "
                        "Egypt, eygpt, go to Egypt, or go to eygpt should be CAI. "
                        "If the user says next month/week without an exact day, put that phrase in date_window "
                        "and leave depart_date blank. Leave unknown fields null. Current date: "
                        f"{datetime.now().date().isoformat()}."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "current_trip": current_trip,
                        "recent_history": history[-8:] if isinstance(history, list) else [],
                        "new_message": message
                    })
                }
            ],
            max_tokens=350,
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        print("AI extraction fallback:", str(exc), flush=True)
        return {}

def merge_trip_updates(current_trip, updates):
    trip = coerce_chat_trip(current_trip)
    cleaned = coerce_chat_trip(updates)

    for key, value in cleaned.items():
        if key in ("children", "infants"):
            if value is not None:
                trip[key] = value
            continue

        if key == "seat":
            if value and value != "none":
                trip[key] = value
            continue

        if value not in ("", None):
            trip[key] = value

    return coerce_chat_trip(trip)

def missing_chat_fields(trip):
    missing = []
    if not is_airport_code(trip.get("origin")):
        missing.append("departure city or airport")
    if not is_airport_code(trip.get("destination")):
        missing.append("destination city or airport")
    flexible_departure_ok = bool(
        trip.get("date_window")
        and (trip.get("trip_duration_days") or trip.get("trip_type") == "oneway")
    )
    if not is_valid_date(trip.get("depart_date")) and not flexible_departure_ok:
        if trip.get("date_window"):
            missing.append(f"exact departure date in {trip['date_window']}")
        else:
            missing.append("exact departure date")
    if trip.get("trip_type") not in ("oneway", "roundtrip"):
        missing.append("one-way or round trip")
    if (
        trip.get("trip_type") == "roundtrip"
        and not is_valid_date(trip.get("return_date"))
        and not trip.get("trip_duration_days")
    ):
        missing.append("return date")
    if (
        trip.get("trip_type") == "roundtrip"
        and is_valid_date(trip.get("depart_date"))
        and is_valid_date(trip.get("return_date"))
        and trip["return_date"] <= trip["depart_date"]
    ):
        missing.append("return date after departure")
    if not trip.get("adults"):
        missing.append("number of adults")
    return missing

def summarize_chat_trip(trip):
    parts = []
    event_text = event_context_summary(trip)
    if event_text:
        parts.append(event_text)
    if trip.get("origin") and trip.get("destination"):
        parts.append(f"{trip['origin']} to {trip['destination']}")
    elif trip.get("destination"):
        parts.append(f"destination {trip['destination']}")
    if trip.get("depart_date"):
        parts.append(f"departing {trip['depart_date']}")
    elif trip.get("date_window"):
        parts.append(f"travel window {trip['date_window']}")
    if trip.get("trip_duration_days"):
        parts.append(f"{trip['trip_duration_days']} day trip")
    if trip.get("trip_type"):
        parts.append("round trip" if trip["trip_type"] == "roundtrip" else "one way")
    if trip.get("adults"):
        parts.append(f"{trip['adults']} adult(s)")
    parts.append(f"{trip.get('cabin') or 'economy'} cabin")
    if trip.get("priority"):
        parts.append(f"{trip['priority']} priority")
    return ", ".join(parts) if parts else "your trip notes"

def event_context_summary(trip):
    event = trip.get("event_context") or {}
    if not event:
        return ""

    return (
        f"{event.get('name', 'Event')}: {event.get('match')} at "
        f"{event.get('venue')} in {event.get('city')} on {event.get('date')}"
    )

def followup_reply(trip, missing):
    summary = summarize_chat_trip(trip)
    if not missing:
        return "I have enough to search live prices."

    preference = normalize_user_text(trip.get("preference", ""))
    prefix = "I can help."
    if any(term in preference for term in ("urgent", "scared", "fast", "prices are going up")):
        prefix = "I will keep this fast and low-risk."
    elif any(term in preference for term in ("stress", "painful", "rested", "bad airline")):
        prefix = "Got it. I will optimize for a smoother trip, not just the lowest fare."
    elif "cheapest" in preference or "only care about the cheapest" in preference:
        prefix = "Got it. I will rank price first."

    if "departure city or airport" in missing and trip.get("destination"):
        return f"{prefix} I have {summary}. First, where are you flying from?"
    if "departure city or airport" in missing and "destination city or airport" in missing:
        return f"{prefix} Tell me the route first: where are you flying from and where are you going?"
    if "destination city or airport" in missing:
        return f"{prefix} I have {summary}. What city or airport are you going to?"
    if "number of adults" in missing:
        return f"{prefix} I have {summary}. How many adult travelers should I price?"
    if any(field.startswith("exact departure date") for field in missing):
        if trip.get("date_window") and trip.get("trip_duration_days"):
            return f"{prefix} I have {summary}. I can scan {trip['date_window']} for a {trip['trip_duration_days']}-day trip; do you want that flexible search, or do you have an exact departure date?"
        return f"{prefix} I have {summary}. What departure date should I use?"
    if "return date" in missing:
        return f"{prefix} I have {summary}. What return date should I use?"
    if "one-way or round trip" in missing:
        return f"{prefix} I have {summary}. Is this one-way or round trip?"

    needed = missing[0]
    return f"{prefix} I have {summary}. I need {needed} next."

def direct_advisory_reply(message, trip, missing):
    lower = normalize_user_text(message)
    route = summarize_chat_trip(trip)

    if "recommendation" in lower and ("fake" in lower or "trust" in lower):
        return (
            "You should not trust a flight recommendation blindly. AIFlight shows the source of the fare, "
            "the search time, the route/date assumptions, the confidence level, and the tradeoff that made the option win. "
            "A real recommendation must be tied to live fare data or clearly labeled as a strategy, because prices, seats, bags, and refund rules can change before checkout."
        )

    raw_lower = str(message or "").lower()

    price_match = re.search(r"\$\s*[\d,]+(?:\.\d{1,2})?|\b\d{3,5}\b", raw_lower)
    price_label = price_match.group(0).strip() if price_match else "that fare"
    if (price_match or "this flight" in lower) and ("good deal" in lower or "actually" in lower):
        return (
            "A low sticker price is not enough to call it a good deal. I would check total trip cost first: bags, seat selection, refund/change rules, layover length, arrival time, and whether the airline or ticket seller is reliable. "
            f"If {price_label} is nonstop or a clean one-stop with bags included, it may be strong. If it has long layovers, no bags, poor arrival time, or strict basic-economy rules, it may be a trap."
        )

    if "why is this flight cheaper" in lower or "why this flight cheaper" in lower:
        return (
            "A flight is usually cheaper because something in the fare is worse or less flexible: a lower fare class, baggage not included, strict refund rules, weaker arrival time, longer layover, overnight connection, lower-demand departure, or an airline/OTA trying to fill seats. "
            "The smart move is to compare total cost and trip risk, not just the headline price."
        )

    if "price dropped" in lower or "dropped" in lower:
        return (
            "A $300 same-day drop is a strong volatility signal. If the route, dates, airline, baggage, and arrival time are acceptable, I would lean book now rather than waiting for another drop. "
            "Wait only if you are flexible by a few days and the current fare is still above the normal range you expected."
        )

    if "first class" in lower and "tomorrow" in lower and ("300" in lower or "under" in lower):
        return (
            "First class from NYC to Paris tomorrow under $300 is extremely unlikely. That combination fights three pricing forces at once: premium cabin, last-minute departure, and a long-haul international route. "
            "The realistic alternatives are economy/premium economy, one-stop routings, nearby airports, or changing the date. I will not invent a fake deal just to satisfy the target price."
        )

    if "business" in lower and "tomorrow" in lower and ("cheapest" in lower or "pay much" in lower or "nonstop" in lower):
        return (
            "There is a conflict in the request: business class, nonstop, and tomorrow usually means expensive. I can still optimize it, but the smart strategy is to compare nonstop business against premium economy, one-stop business, and nearby airports. "
            f"For live pricing, I need the route and traveler count next. Current notes: {route}."
        )

    if "book now or wait" in lower or ("should i book" in lower and "wait" in lower):
        return (
            f"For {route}, my best no-live-price rule is: book now if the fare is already below your comfort threshold or if your dates are fixed. "
            "Wait only if you can move by 2-3 days and the current fare is not clearly good. With flexible June travel, I would scan several 7-day windows and set a buy threshold instead of guessing from one date."
        )

    if "nyc or boston" in lower or "new york or boston" in lower:
        return (
            "Do not choose Boston just because the ticket is cheaper. The real comparison is ticket savings minus train/flight/parking cost to Boston, extra travel time, missed-work time, and connection risk. "
            "Boston only wins if the fare savings still look meaningful after ground travel and the extra stress."
        )

    if "then rome" in lower or "multi city" in lower or "multi-city" in lower:
        return (
            "That is a multi-city trip, not a simple round trip. I would structure it as NYC -> Paris, Paris -> Rome, then Rome -> NYC. "
            "To price it correctly, I need the travel dates, number of travelers, and whether you want the Paris-to-Rome leg by flight or train."
        )

    if re.search(r"\bto jordan\b|\bjordan\b", lower) and not is_airport_code(trip.get("destination")):
        return (
            "Do you mean Amman, Jordan? The main airport I would use is AMM. "
            "If yes, tell me where you are flying from and your dates, and I will price it as Amman instead of guessing wrong."
        )

    if any(term in lower for term in ("dont want stress", "don t want stress", "okay paying more", "avoid problems")):
        return (
            "Got it. I will weight this as a low-stress trip: nonstop or clean one-stop, reliable airline, sane departure and arrival times, enough connection buffer, and flexible rules when the price difference is reasonable. "
            "Tell me the route and date, and I will rank comfort/risk above cheapest."
        )

    if "only care about the cheapest" in lower or ("cheapest flight" in lower and "comfort" in lower):
        return (
            "Understood. I will switch the scoring to price-first and only reject an option if it has an unusually risky connection or hidden fees that erase the savings. "
            "Send the route and dates, and I will rank the cheapest real options first."
        )

    if "urgent" in lower or "scared prices" in lower or "prices are going up" in lower:
        return (
            f"I will keep this fast. For an urgent trip, I prioritize low-risk flights, clear booking deadlines, and a book-now recommendation when the fare is acceptable. "
            f"Current notes: {route}. The next key detail I need is {missing[0] if missing else 'permission to search live fares'}."
        )

    if "meeting" in lower and "rested" in lower:
        return (
            "For a Monday morning meeting, cheapest is usually the wrong target. I would aim to arrive the day before, avoid tight layovers, and prefer nonstop or a very clean connection so you can sleep and recover. "
            f"Current notes: {route}. Tell me the departure city and date window so I can price the right arrival plan."
        )

    return ""

def ai_followup_reply(message, trip, missing, history):
    fallback = followup_reply(trip, missing)
    if not client:
        return fallback

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AIFlight, a smart travel-agent chat assistant. "
                        "Reply naturally like ChatGPT, not like a form or fixed template. "
                        "Use the structured trip notes as truth. Ask only for the missing fields. "
                        "Do not invent dates, airports, passenger counts, prices, airlines, or tickets. "
                        "Keep the reply short and helpful."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "traveler_message": message,
                        "recent_history": history[-8:] if isinstance(history, list) else [],
                        "known_trip_notes": trip,
                        "missing_fields": missing,
                        "fallback_reply": fallback
                    })
                }
            ],
            max_tokens=180,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print("AI followup fallback:", str(exc), flush=True)
        return fallback

def prepare_chat_search_trip(trip):
    priority = trip.get("priority") or "balanced"
    depart_date = trip.get("depart_date", "")
    return_date = trip.get("return_date", "")
    if not depart_date and trip.get("date_window"):
        depart_date, guessed_return = representative_date_for_window(
            trip.get("date_window"),
            trip.get("trip_duration_days") or 7
        )
        if trip.get("trip_type") == "roundtrip" and not return_date:
            return_date = guessed_return

    if trip.get("trip_type") == "roundtrip" and not return_date and trip.get("trip_duration_days"):
        return_date = shift_date(depart_date, trip["trip_duration_days"])

    return {
        "origin": trip["origin"],
        "destination": trip["destination"],
        "trip_type": trip["trip_type"],
        "depart_date": depart_date,
        "return_date": return_date,
        "adults": parse_passenger_count(trip.get("adults"), default=1, minimum=1),
        "children": parse_passenger_count(trip.get("children"), default=0),
        "infants": parse_passenger_count(trip.get("infants"), default=0),
        "priority": priority,
        "cabin": trip.get("cabin") or "economy",
        "seat": trip.get("seat") or "none",
        "trip_duration_days": trip.get("trip_duration_days"),
        "preference": trip.get("preference", ""),
        "event_context": trip.get("event_context", {})
    }

def trip_plan_line(trip):
    if not trip.get("event_context"):
        return ""

    return (
        f"{event_context_summary(trip)}. I mapped the flight to "
        f"{trip.get('destination')} and planned {trip.get('origin')} -> {trip.get('destination')} "
        f"from {trip.get('depart_date')} to {trip.get('return_date')}."
    )

def trip_ready_line(trip):
    return f"You are not missing any trip details. I have {summarize_chat_trip(trip)}."

def ai_chat_reply(message, trip, offers, cards, links, reason, plan, strategy, history, intelligence=None):
    if offers:
        fallback = f"{plan} I found live prices and picked the strongest option: {cards[0]['signal']}. {strategy}".strip()
    else:
        fallback = f"{plan} {strategy}".strip()

    if not client:
        return fallback

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are AIFlight, a ChatGPT-style travel assistant. "
                        "Write a warm, direct travel-agent answer in natural language. "
                        "Use only the provided trip, event, offers, cards, and strategy. "
                        "Use the price intelligence object to explain buy/wait logic, confidence, and counter-pricing signals. "
                        "If offers exist, clearly show the best price and why it won. "
                        "If no offers exist, explain the search result without pretending prices exist. "
                        "Do not invent match details, prices, airlines, ticket availability, hotels, or booking confirmations. "
                        "Do not say you booked anything; say this is the plan/search result. "
                        "Keep it concise but conversational."
                    )
                },
                {
                    "role": "user",
                    "content": json.dumps({
                        "traveler_message": message,
                        "recent_history": history[-8:] if isinstance(history, list) else [],
                        "trip": trip,
                        "event_summary": event_context_summary(trip),
                        "plan": plan,
                        "offers": offers,
                        "deal_space": trip.get("deal_space", []),
                        "price_intelligence": intelligence or {},
                        "result_cards": cards,
                        "search_links_available": bool(links),
                        "reason_if_no_offers": reason,
                        "deterministic_strategy": strategy,
                        "fallback_reply": fallback
                    })
                }
            ],
            max_tokens=320,
            temperature=0.72
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print("AI chat reply fallback:", str(exc), flush=True)
        return fallback

def apply_duration_to_trip(trip):
    trip = coerce_chat_trip(trip)
    if (
        trip.get("trip_type") == "roundtrip"
        and trip.get("trip_duration_days")
        and is_valid_date(trip.get("depart_date"))
        and not is_valid_date(trip.get("return_date"))
    ):
        trip["return_date"] = shift_date(trip["depart_date"], trip["trip_duration_days"])
    return coerce_chat_trip(trip)

def build_perception(message, local_updates):
    fields_seen = sorted([key for key, value in local_updates.items() if value not in ("", None, {}, [])])
    validation = []

    normalized_message = normalize_user_text(message)

    if not has_date_evidence(normalized_message):
        validation.append("No exact departure date was stated.")
    if "friend" in normalized_message and "adults" not in local_updates:
        validation.append("Friends were mentioned without a clear count.")

    confidence = "high" if fields_seen and not validation else "medium" if fields_seen else "low"
    return {
        "raw_message": message,
        "structured_updates": local_updates,
        "fields_seen": fields_seen,
        "validation": validation,
        "confidence": confidence
    }

def build_world_model(trip, perception, history):
    buyer_advantage = []
    if trip.get("origin") in NEARBY_AIRPORTS or trip.get("destination") in NEARBY_AIRPORTS:
        buyer_advantage.append("nearby airport comparison")
    if trip.get("trip_duration_days") or trip.get("date_window"):
        buyer_advantage.append("date or trip-length flexibility")
    if trip.get("priority") == "comfort":
        buyer_advantage.append("comfort-weighted scoring instead of lowest fare only")
    elif trip.get("priority") == "cheapest":
        buyer_advantage.append("price-weighted scoring with backup tradeoffs")
    else:
        buyer_advantage.append("balanced price/time/stops scoring")

    return {
        "user_preferences": {
            "priority": trip.get("priority") or "balanced",
            "cabin": trip.get("cabin") or "economy",
            "seat": trip.get("seat") or "none",
            "adults": trip.get("adults")
        },
        "current_task": {
            "route": f"{trip.get('origin') or '?'} -> {trip.get('destination') or '?'}",
            "trip_type": trip.get("trip_type") or "unknown",
            "depart_date": trip.get("depart_date") or "",
            "return_date": trip.get("return_date") or "",
            "duration_days": trip.get("trip_duration_days")
        },
        "known_constraints": missing_chat_fields(trip),
        "retrieved_context": {
            "event": event_context_summary(trip),
            "history_items": len(history) if isinstance(history, list) else 0
        },
        "airline_pricing_model": AIRLINE_PRICING_MODEL,
        "buyer_advantage": buyer_advantage,
        "perception_confidence": perception["confidence"]
    }

def safe_ai_trip_merge(message, current_trip, local_updates, ai_trip):
    local_trip = apply_duration_to_trip(merge_trip_updates(current_trip, local_updates))
    if not isinstance(ai_trip, dict):
        return local_trip

    ai_clean = coerce_chat_trip(ai_trip)
    safe_updates = {}
    lower = normalize_user_text(message)
    destination_intent = any(term in lower for term in (" to ", "visit", "go", "fly", "travel", "destination"))
    origin_intent = bool(re.search(r"\b(?:from|depart|departure|leaving|leave|start)\b", lower))

    if not local_trip.get("origin") and is_airport_code(ai_clean.get("origin")) and origin_intent:
        safe_updates["origin"] = ai_clean["origin"]
    if not local_trip.get("destination") and is_airport_code(ai_clean.get("destination")) and destination_intent:
        safe_updates["destination"] = ai_clean["destination"]

    if not local_trip.get("trip_type") and ai_clean.get("trip_type"):
        safe_updates["trip_type"] = ai_clean["trip_type"]

    if has_date_evidence(message) or current_trip.get("depart_date"):
        if ai_clean.get("depart_date") and not local_updates.get("depart_date"):
            safe_updates["depart_date"] = ai_clean["depart_date"]
        if ai_clean.get("date_window") and not local_updates.get("date_window"):
            safe_updates["date_window"] = ai_clean["date_window"]

    if current_trip.get("return_date") or local_updates.get("return_date"):
        if ai_clean.get("return_date") and not local_updates.get("return_date"):
            safe_updates["return_date"] = ai_clean["return_date"]

    if has_passenger_evidence(message) and not local_updates.get("adults") and ai_clean.get("adults"):
        safe_updates["adults"] = ai_clean["adults"]

    for key in ("children", "infants", "priority", "cabin", "seat", "preference", "event_context", "trip_duration_days"):
        if key not in local_updates and ai_clean.get(key) not in ("", None, {}, []):
            safe_updates[key] = ai_clean[key]

    return apply_duration_to_trip(merge_trip_updates(local_trip, safe_updates))

def evaluate_brain_state(message, trip, perception):
    missing = missing_chat_fields(trip)
    warnings = []
    strategy_tests = []

    if not has_date_evidence(message) and not trip.get("depart_date"):
        warnings.append("No departure date evidence; do not search yet.")
    if "friend" in normalize_user_text(message) and not has_passenger_evidence(message):
        warnings.append("Passenger count is ambiguous.")
    if trip.get("origin") in NEARBY_AIRPORTS:
        strategy_tests.append("test nearby origin airports")
    if trip.get("destination") in NEARBY_AIRPORTS:
        strategy_tests.append("test nearby destination airports")
    if trip.get("priority") != "fastest":
        strategy_tests.append("test one-day date shifts")
    strategy_tests.append("rank total traveler value, not airline revenue")

    action = "search_live_fares" if not missing and not warnings else "ask_clarification"
    confidence = "high" if action == "search_live_fares" and perception["confidence"] == "high" else "medium" if trip.get("destination") else "low"
    return {
        "action": action,
        "missing_fields": missing,
        "warnings": warnings,
        "strategy_tests": strategy_tests,
        "confidence": confidence,
        "ready_to_search": action == "search_live_fares"
    }

def build_brain_loop(message, trip, perception, world_model, evaluation):
    return {
        "perceive": {
            "status": "done",
            "confidence": perception["confidence"],
            "fields_seen": perception["fields_seen"],
            "validation": perception["validation"]
        },
        "understand": {
            "status": "done",
            "summary": summarize_chat_trip(trip)
        },
        "build_context": {
            "status": "done",
            "world_model": world_model
        },
        "think": {
            "status": "done",
            "goal": "Decide whether AIFlight has enough verified facts to search live fares.",
            "airline_model": AIRLINE_PRICING_MODEL["airline_goal"],
            "buyer_tests": evaluation["strategy_tests"]
        },
        "decide": {
            "status": evaluation["action"],
            "missing_fields": evaluation["missing_fields"]
        },
        "act": {
            "status": "call_flight_search" if evaluation["ready_to_search"] else "ask_user"
        },
        "evaluate": {
            "status": "done",
            "confidence": evaluation["confidence"],
            "warnings": evaluation["warnings"],
            "best_guess_basis": evaluation["strategy_tests"]
        },
        "refine": {
            "status": "done",
            "rule": "Unsupported assumptions are removed before responding."
        },
        "respond": {
            "status": "ready"
        }
    }

def run_brain_loop(message, current_trip, history, ai_trip=None, ai_reply=""):
    local_updates = rule_extract_trip_details(message)
    perception = build_perception(message, local_updates)
    trip = safe_ai_trip_merge(message, current_trip, local_updates, ai_trip)
    world_model = build_world_model(trip, perception, history)
    evaluation = evaluate_brain_state(message, trip, perception)
    reply = "" if evaluation["ready_to_search"] else followup_reply(trip, evaluation["missing_fields"])

    return {
        "reply": reply or ai_reply,
        "trip": trip,
        "ready_to_search": evaluation["ready_to_search"],
        "missing_fields": evaluation["missing_fields"],
        "brain_loop": build_brain_loop(message, trip, perception, world_model, evaluation),
        "world_model": world_model,
        "self_evaluation": evaluation
    }

def local_agent_brain(message, current_trip):
    return run_brain_loop(message, current_trip, [])

def ai_agent_brain(message, current_trip, history):
    if not client:
        return local_agent_brain(message, current_trip)

    system_prompt = (
        "You are AIFlight, an AI travel agent built to beat airline pricing AI for clients. "
        "Your job is limited to flight deals, flight planning, and price strategy. "
        "Understand airline AI first: airline pricing systems optimize revenue using time before departure, remaining capacity, booking pace, route demand, length of stay, competitor prices, shopping context, and bundles. "
        "AIFlight is buyer-side AI: it beats airline AI by testing nearby airports, date shifts, total trip value, comfort/time tradeoffs, and when to buy or wait. "
        "You are not a form. Do not use fixed template language like 'I noted...' or 'Send that and I will pull live prices.' "
        "Talk naturally like a smart travel agent. "
        "Run this loop before answering: perceive the raw message, understand structured trip facts, build context, decide whether to ask/search, self-check assumptions, then respond. "
        "Maintain the structured trip state from the conversation and the current_trip object. "
        "Convert cities, countries, misspellings, and phrases into IATA airport codes when the intent is clear "
        "(NYC/New York -> JFK unless user chooses LGA/EWR, Egypt/Eygpt/Cairo -> CAI, Paris -> CDG, London/Londen -> LHR). "
        "Los Angeles, LA, or L.A. should be LAX unless the user chooses another airport. "
        "If the user says 'with two friends', adults must be 3 total. "
        "If the user asks what information is missing, answer from current_trip. "
        "Required before live search: origin IATA, destination IATA, departure date YYYY-MM-DD, trip_type oneway or roundtrip, "
        "return date if roundtrip, and adults. Cabin defaults to economy. Priority defaults to balanced. "
        "Never invent or assume a departure date. If the user says 'one week' without a departure date, store trip_duration_days=7 and ask for the departure date. "
        "If a user gives a date range and trip length, choose a sensible departure/return within the range and state the assumption. "
        "Outsmart airline pricing AI legally by asking for/using flexibility: nearby airports, date shifts, lower-stress routes, "
        "time-versus-money tradeoffs, and avoiding unnecessary paid bundles. "
        "If ready_to_search is false, ask only for the important missing details. "
        "If ready_to_search is true, do not invent prices; the backend will search live offers. "
        "Return JSON only with keys: reply, trip, ready_to_search, missing_fields. "
        "trip keys: origin, destination, trip_type, depart_date, return_date, date_window, trip_duration_days, adults, children, infants, priority, cabin, seat, preference, event_context."
    )

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps({
                        "current_date": datetime.now().date().isoformat(),
                        "current_trip": current_trip,
                        "recent_history": history[-10:] if isinstance(history, list) else [],
                        "new_message": message
                    })
                }
            ],
            max_tokens=700,
            temperature=0.45
        )
        brain = json.loads(response.choices[0].message.content)
    except Exception as exc:
        print("AI agent brain fallback:", str(exc), flush=True)
        return local_agent_brain(message, current_trip)

    return run_brain_loop(
        message,
        current_trip,
        history,
        ai_trip=brain.get("trip") if isinstance(brain, dict) else None,
        ai_reply=str(brain.get("reply") or "").strip() if isinstance(brain, dict) else ""
    )


@app.route("/")
def home():
    return render_template("index.html")

def build_search_links(origin, destination, trip_type, depart_date, return_date):
    q = f"flights from {origin} to {destination} on {depart_date}"
    if trip_type == "roundtrip" and return_date:
        q = f"round trip flights from {origin} to {destination} depart {depart_date} return {return_date}"

    google = f"https://www.google.com/travel/flights?q={quote_plus(q)}"
    kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"
    if trip_type == "roundtrip" and return_date:
        kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}/{return_date}"

    skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/"
    if trip_type == "roundtrip" and return_date:
        skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/{return_date.replace('-', '')}/"

    return {"google": google, "kayak": kayak, "skyscanner": skyscanner}

def build_passengers(adults, children, infants):
    passengers = []

    for _ in range(adults):
        passengers.append({"type": "adult"})

    for _ in range(children):
        passengers.append({"type": "child"})

    for _ in range(infants):
        passengers.append({"type": "infant_without_seat"})

    return passengers

def cabin_for_duffel(cabin):
    mapping = {
        "economy": "economy",
        "premium": "premium_economy",
        "business": "business",
        "first": "first"
    }
    return mapping.get(cabin, "economy")

def fetch_duffel_offers(trip):
    if not httpx:
        print("httpx missing", flush=True)
        return [], "missing_httpx"

    if not DUFFEL_ACCESS_TOKEN:
        print("DUFFEL_ACCESS_TOKEN missing", flush=True)
        return [], "missing_token"

    slices = [{
        "origin": trip["origin"],
        "destination": trip["destination"],
        "departure_date": trip["depart_date"]
    }]

    if trip["trip_type"] == "roundtrip" and trip["return_date"]:
        slices.append({
            "origin": trip["destination"],
            "destination": trip["origin"],
            "departure_date": trip["return_date"]
        })

    payload = {
        "data": {
            "slices": slices,
            "passengers": build_passengers(
                trip["adults"],
                trip["children"],
                trip["infants"]
            ),
            "cabin_class": cabin_for_duffel(trip["cabin"])
        }
    }

    headers = {
        "Authorization": f"Bearer {DUFFEL_ACCESS_TOKEN}",
        "Duffel-Version": "v2",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Accept-Encoding": "gzip"
    }

    try:
        with httpx.Client(timeout=35) as http:
            response = http.post(
                "https://api.duffel.com/air/offer_requests?return_offers=true",
                headers=headers,
                json=payload
            )

        print("Duffel status:", response.status_code, flush=True)

        if response.status_code >= 400:
            return [], f"duffel_error_{response.status_code}"

        data = response.json().get("data", {})
        offers = data.get("offers", [])[:8]
        if not offers:
            return [], "no_offers"

        parsed = []
        for offer in offers:
            total_amount = offer.get("total_amount")
            total_currency = offer.get("total_currency", "USD")
            slices_data = offer.get("slices", [])

            first_slice = slices_data[0] if slices_data else {}
            segments = first_slice.get("segments", [])
            first_segment = segments[0] if segments else {}

            airline = (
                first_segment.get("marketing_carrier", {}).get("name")
                or first_segment.get("operating_carrier", {}).get("name")
                or "Airline"
            )

            stops = max(0, len(segments) - 1)
            duration = first_slice.get("duration", "Check on offer")

            parsed.append({
                "id": offer.get("id"),
                "price": total_amount,
                "currency": total_currency,
                "airline": airline,
                "duration": duration,
                "stops": stops,
                "payment_required_by": offer.get("payment_required_by"),
                "expires_at": offer.get("expires_at")
            })

        if not parsed:
            return [], "no_parseable_offers"

        return parsed, "ok"

    except Exception as e:
        print("Duffel exception:", str(e), flush=True)
        return [], "exception"

def shift_date(value, days):
    if not is_valid_date(value):
        return value
    return (datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=days)).strftime("%Y-%m-%d")

def candidate_key(trip):
    return (
        trip.get("origin"),
        trip.get("destination"),
        trip.get("trip_type"),
        trip.get("depart_date"),
        trip.get("return_date"),
        trip.get("cabin")
    )

def build_counter_pricing_candidates(trip):
    base = dict(trip)
    base["search_note"] = "Exact trip"
    candidates = [base]
    seen = {candidate_key(base)}

    def add_candidate(updates, note):
        candidate = dict(trip)
        candidate.update(updates)
        candidate["search_note"] = note
        key = candidate_key(candidate)
        if key in seen:
            return
        seen.add(key)
        candidates.append(candidate)

    if trip.get("priority") != "fastest":
        for delta in (-1, 1):
            updates = {"depart_date": shift_date(trip["depart_date"], delta)}
            if trip.get("trip_type") == "roundtrip" and trip.get("return_date"):
                updates["return_date"] = shift_date(trip["return_date"], delta)
            add_candidate(updates, f"{abs(delta)} day {'earlier' if delta < 0 else 'later'}")

    origin_options = NEARBY_AIRPORTS.get(trip.get("origin"), [trip.get("origin")])
    destination_options = NEARBY_AIRPORTS.get(trip.get("destination"), [trip.get("destination")])

    for origin in origin_options[1:2]:
        add_candidate({"origin": origin}, f"Nearby origin {origin}")

    for destination in destination_options[1:2]:
        add_candidate({"destination": destination}, f"Nearby destination {destination}")

    return candidates[:5]

def is_retryable_provider_reason(reason):
    return reason == "exception" or reason in ("duffel_error_408", "duffel_error_425", "duffel_error_429") or reason.startswith("duffel_error_5")

def fetch_candidate_with_retry(candidate, attempts=2):
    last_offers, last_reason = [], "not_run"

    for attempt in range(1, attempts + 1):
        offers, reason = fetch_duffel_offers(candidate)
        last_offers, last_reason = offers, reason
        if offers or not is_retryable_provider_reason(reason):
            return offers, reason, attempt
        time.sleep(0.25 * attempt)

    return last_offers, last_reason, attempts

def fetch_deal_space_offers(trip):
    if not httpx or not DUFFEL_ACCESS_TOKEN:
        offers, reason = fetch_duffel_offers(dict(trip, search_note="Exact trip"))
        return offers, reason, [{
            "search_note": "Exact trip",
            "origin": trip.get("origin"),
            "destination": trip.get("destination"),
            "depart_date": trip.get("depart_date"),
            "return_date": trip.get("return_date"),
            "reason": reason,
            "offers": len(offers)
        }]

    all_offers = []
    reasons = []
    candidates = build_counter_pricing_candidates(trip)
    candidate_results = []

    with ThreadPoolExecutor(max_workers=min(5, len(candidates))) as executor:
        futures = {
            executor.submit(fetch_candidate_with_retry, candidate): (index, candidate)
            for index, candidate in enumerate(candidates)
        }

        for future in as_completed(futures):
            index, candidate = futures[future]
            try:
                offers, reason, attempts = future.result()
            except Exception as exc:
                print("Provider worker exception:", str(exc), flush=True)
                offers, reason, attempts = [], "exception", 1
            candidate_results.append((index, candidate, offers, reason, attempts))

    for _, candidate, offers, reason, attempts in sorted(candidate_results, key=lambda item: item[0]):
        reasons.append({
            "provider": "duffel",
            "search_note": candidate.get("search_note"),
            "origin": candidate.get("origin"),
            "destination": candidate.get("destination"),
            "depart_date": candidate.get("depart_date"),
            "return_date": candidate.get("return_date"),
            "reason": reason,
            "offers": len(offers),
            "attempts": attempts
        })

        for offer in offers:
            copy = dict(offer)
            copy["provider"] = "duffel"
            copy["search_note"] = candidate.get("search_note", "Exact trip")
            copy["origin"] = candidate.get("origin")
            copy["destination"] = candidate.get("destination")
            copy["depart_date"] = candidate.get("depart_date")
            copy["return_date"] = candidate.get("return_date")
            copy["trip_type"] = candidate.get("trip_type")
            all_offers.append(copy)

    if all_offers:
        return all_offers, "ok", reasons

    return [], reasons[0]["reason"] if reasons else "no_candidates", reasons

def fallback_details(trip, reason):
    route = f"{trip['origin']} to {trip['destination']}"

    if reason == "no_offers":
        return {
            "title": "No Matching Live Fares Yet",
            "signal": "Duffel connected",
            "status": "No offers for this search",
            "goal": "Try nearby airports or dates",
            "risk": "This route/date may not have bookable inventory",
            "explanation": f"Duffel answered successfully, but did not return bookable fares for {route} on this date. Try JFK or EWR instead of LGA, a date a few days later, or a bigger test route like JFK to LHR."
        }

    if reason == "missing_httpx":
        return {
            "title": "Live Search Needs Dependencies",
            "signal": "Install requirements",
            "status": "Missing httpx",
            "goal": "Enable Duffel calls",
            "risk": "No live prices until dependencies are installed",
            "explanation": "The app is running without the httpx package, so it cannot call Duffel. Install requirements.txt in the same Python environment that runs Flask."
        }

    if reason == "missing_token":
        return {
            "title": "Live Search Needs a Duffel Token",
            "signal": "Token missing",
            "status": "Duffel not configured",
            "goal": "Connect live fares",
            "risk": "No live prices until the token is set",
            "explanation": "Set DUFFEL_ACCESS_TOKEN in your local environment or Render environment variables, then restart the app."
        }

    if reason.startswith("duffel_error_"):
        return {
            "title": "Duffel Rejected This Search",
            "signal": reason.replace("_", " "),
            "status": "Duffel API error",
            "goal": "Check route and credentials",
            "risk": "Live fares were not returned",
            "explanation": "Duffel returned an error for this search. Check the server logs for the API response, confirm the airport codes and dates, and verify the token has access."
        }

    return {
        "title": "Live Search Needs Attention",
        "signal": "No offers returned",
        "status": "Search incomplete",
        "goal": "Check live pricing",
        "risk": "No live Duffel offer yet",
        "explanation": f"AIFlight could not get live fares for {route} yet. Try a major route with a future date or check the server logs."
    }

def fallback_cards(trip, links, reason):
    details = fallback_details(trip, reason)

    return [
        {
            "title": details["title"],
            "signal": details["signal"],
            "status": details["status"],
            "goal": details["goal"],
            "risk": details["risk"],
            "explanation": details["explanation"]
        },
        {
            "title": "Best Next Move",
            "signal": "Check trusted sites",
            "status": "Fallback",
            "goal": "Still find real prices",
            "risk": "Prices may change",
            "explanation": "Use the search links below while live pricing is being verified. AIFlight will recommend one best option when offers are available."
        }
    ]

def parse_price(value):
    try:
        return float(value or 999999)
    except (TypeError, ValueError):
        return 999999

def parse_iso_duration(value):
    if not value:
        return None

    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?", value)
    if not match:
        return None

    days, hours, minutes = (int(part or 0) for part in match.groups())
    return days * 1440 + hours * 60 + minutes

def format_minutes(minutes):
    if minutes is None:
        return "duration not listed"

    hours = minutes // 60
    mins = minutes % 60
    if hours and mins:
        return f"{hours}h {mins}m"
    if hours:
        return f"{hours}h"
    return f"{mins}m"

def format_money(currency, amount):
    amount = float(amount)
    if amount >= 999999:
        return f"{currency} unavailable"
    if amount.is_integer():
        return f"{currency} {int(amount):,}"
    return f"{currency} {amount:,.2f}"

def score_offer(offer, lowest_price, shortest_duration, priority):
    price = parse_price(offer.get("price"))
    duration = parse_iso_duration(offer.get("duration")) or shortest_duration or 0
    stops = int(offer.get("stops") or 0)

    price_penalty = 0 if lowest_price <= 0 else ((price - lowest_price) / lowest_price) * 100
    time_penalty = 0 if not shortest_duration else max(0, (duration - shortest_duration) / 30) * 4
    stop_penalty = stops * 14

    weights = {
        "cheapest": (1.45, 0.65, 0.80),
        "fastest": (0.65, 1.45, 0.90),
        "comfort": (0.80, 0.80, 1.55),
        "balanced": (1.00, 1.00, 1.00)
    }
    price_weight, time_weight, stop_weight = weights.get(priority, weights["balanced"])

    return (price_penalty * price_weight) + (time_penalty * time_weight) + (stop_penalty * stop_weight)

def analyze_offers(offers, trip):
    enriched = []

    for offer in offers:
        copy = dict(offer)
        copy["price_value"] = parse_price(offer.get("price"))
        copy["duration_minutes"] = parse_iso_duration(offer.get("duration"))
        enriched.append(copy)

    priced = [offer for offer in enriched if offer["price_value"] < 999999]
    timed = [offer for offer in enriched if offer["duration_minutes"] is not None]

    lowest_price = min((offer["price_value"] for offer in priced), default=999999)
    shortest_duration = min((offer["duration_minutes"] for offer in timed), default=None)

    for offer in enriched:
        offer["ai_score"] = score_offer(
            offer,
            lowest_price,
            shortest_duration,
            trip.get("priority", "balanced")
        )

    ranked = sorted(enriched, key=lambda item: (item["ai_score"], item["price_value"]))
    best = ranked[0]
    cheapest = min(enriched, key=lambda item: item["price_value"])
    fastest = min(enriched, key=lambda item: item["duration_minutes"] or 999999)

    return ranked, best, cheapest, fastest

def tradeoff_line(best, cheapest, fastest):
    best_price = best["price_value"]
    cheapest_price = cheapest["price_value"]
    best_duration = best.get("duration_minutes")
    fastest_duration = fastest.get("duration_minutes")

    if best["id"] != cheapest["id"] and best_price - cheapest_price > 0:
        extra = best_price - cheapest_price
        return f"You could save {format_money(best['currency'], extra)} with {cheapest['airline']}, but AIFlight ranked this higher for the full trip."

    if best["id"] != fastest["id"] and fastest["price_value"] - best_price > 0 and best_duration and fastest_duration:
        savings = fastest["price_value"] - best_price
        extra_minutes = best_duration - fastest_duration
        if extra_minutes > 0:
            return f"You save {format_money(best['currency'], savings)} by taking {format_minutes(extra_minutes)} longer than the fastest offer."

    return "This is the best value after balancing fare, travel time, stops, and your stated preferences."

def route_line(offer):
    route = ""
    if offer.get("origin") and offer.get("destination"):
        route = f"{offer['origin']} to {offer['destination']}"
    if offer.get("depart_date"):
        route = f"{route} on {offer['depart_date']}".strip()
    if offer.get("return_date"):
        route = f"{route}, return {offer['return_date']}".strip()
    return route or "selected route"

def days_until_departure(trip):
    if not is_valid_date(trip.get("depart_date")):
        return None

    depart_date = datetime.strptime(trip["depart_date"], "%Y-%m-%d").date()
    return (depart_date - datetime.now().date()).days

def route_signature(trip):
    return (
        trip.get("origin"),
        trip.get("destination"),
        trip.get("trip_type"),
        trip.get("cabin") or "economy"
    )

def route_observations(trip):
    signature = route_signature(trip)
    return [item for item in PRICE_OBSERVATIONS if item.get("signature") == signature]

def record_price_observation(trip, offers, intelligence):
    if not offers:
        return

    prices = [parse_price(offer.get("price")) for offer in offers]
    prices = [price for price in prices if price < 999999]
    if not prices:
        return

    PRICE_OBSERVATIONS.append({
        "signature": route_signature(trip),
        "observed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "depart_date": trip.get("depart_date"),
        "return_date": trip.get("return_date"),
        "best_price": min(prices),
        "currency": offers[0].get("currency", "USD"),
        "decision": intelligence.get("decision", "")
    })

    del PRICE_OBSERVATIONS[:-MAX_PRICE_OBSERVATIONS]

def median_price(prices):
    if not prices:
        return 999999

    ordered = sorted(prices)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2

def airline_ai_context(trip, offers, deal_space):
    days_out = days_until_departure(trip)
    offer_count = len(offers or [])
    searches_checked = len(deal_space or [])
    factors = []

    if days_out is not None:
        if days_out <= 21:
            factors.append("close-in departure window usually increases urgency pressure")
        elif days_out >= 90:
            factors.append("far-out departure window may still have monitoring room")
        else:
            factors.append("mid-range booking window; price can still move with demand")

    if trip.get("trip_duration_days"):
        factors.append(f"{trip['trip_duration_days']}-day stay affects airline demand segmentation")

    if offer_count <= 2:
        factors.append("low offer count can indicate limited inventory or weak provider coverage")
    elif offer_count >= 5:
        factors.append("multiple offers create a stronger comparison surface")

    if searches_checked > 1:
        factors.append("AIFlight tested variations airlines do not optimize for the traveler")

    if trip.get("priority") == "comfort":
        factors.append("comfort priority reduces exposure to cheap-but-painful fare traps")

    return {
        "airline_goal": AIRLINE_PRICING_MODEL["airline_goal"],
        "likely_pricing_factors": factors,
        "buyer_counter_moves": AIRLINE_PRICING_MODEL["buyer_counter_moves"],
        "weak_points_tested": [
            move for move in AIRLINE_PRICING_MODEL["buyer_counter_moves"]
            if (
                ("nearby" in move and searches_checked > 1)
                or ("shift" in move and searches_checked > 1)
                or ("total" in move)
                or ("comfort" in move and trip.get("priority") == "comfort")
                or ("watch" in move and days_out is not None and days_out > 45)
            )
        ]
    }

def build_price_intelligence(trip, offers, deal_space, reason):
    searches = deal_space or []
    history = route_observations(trip)
    days_out = days_until_departure(trip)
    pricing_context = airline_ai_context(trip, offers, searches)
    source_status = "ok" if offers else reason
    sources = [
        {
            "name": "Duffel live fares",
            "status": source_status,
            "detail": f"{len(offers)} live offer(s) returned"
        },
        {
            "name": "Counter-pricing deal space",
            "status": "active" if searches else "not run",
            "detail": f"{len(searches)} route/date variation(s) checked"
        },
        {
            "name": "Trusted fallback links",
            "status": "ready",
            "detail": "Google Flights, Kayak, and Skyscanner links generated"
        },
        {
            "name": "Session learning memory",
            "status": "active",
            "detail": f"{len(history)} prior observation(s) for this route in this server session"
        }
    ]

    if not offers:
        details = fallback_details(trip, reason)
        return {
            "decision": "Verify setup" if reason in ("missing_token", "missing_httpx") else "Check alternate sources",
            "confidence": "low",
            "best_guess": "Weak best guess",
            "summary": details["explanation"],
            "prediction": "No price forecast yet because live fares were not returned.",
            "personalization": f"Priority is {trip.get('priority') or 'balanced'} and cabin is {trip.get('cabin') or 'economy'}.",
            "pricing_context": pricing_context,
            "sources": sources,
            "signals": [
                details["status"],
                f"Airline-side model: {pricing_context['airline_goal']}",
                "AIFlight did not invent a price because the live fare dataset was empty.",
                "Fallback search links are available while live pricing is verified."
            ],
            "anti_pricing_moves": [
                "Retry with nearby airports if the route is flexible.",
                "Try a one-day date shift to test whether airline pricing changes.",
                "Compare the fallback links before committing money."
            ],
            "metrics": {
                "offers_found": 0,
                "searches_checked": len(searches),
                "days_until_departure": days_out,
                "history_count": len(history)
            }
        }

    ranked, best, cheapest, fastest = analyze_offers(offers, trip)
    prices = [offer["price_value"] for offer in ranked if offer["price_value"] < 999999]
    lowest = min(prices, default=best["price_value"])
    highest = max(prices, default=best["price_value"])
    median = median_price(prices)
    currency = best.get("currency", "USD")
    exact_prices = [
        parse_price(offer.get("price"))
        for offer in offers
        if offer.get("search_note", "Exact trip") == "Exact trip"
    ]
    exact_prices = [price for price in exact_prices if price < 999999]
    exact_low = min(exact_prices, default=None)
    savings_vs_exact = max(0, exact_low - best["price_value"]) if exact_low is not None else 0
    spread = max(0, highest - lowest)
    spread_pct = 0 if lowest <= 0 else spread / lowest
    previous_low = min((item["best_price"] for item in history), default=None)

    signals = [
        f"Airline-side model: {pricing_context['airline_goal']}",
        f"Checked {len(searches)} route/date variation(s), not just the exact request.",
        f"Best candidate came from: {best.get('search_note', 'Exact trip')}."
    ]

    for factor in pricing_context["likely_pricing_factors"]:
        signals.append(f"Pricing factor watched: {factor}.")

    if savings_vs_exact > 0:
        signals.append(f"Counter-pricing found {format_money(currency, savings_vs_exact)} below the best exact-trip fare.")
    if spread_pct >= 0.25:
        signals.append(f"Large fare spread detected: {format_money(currency, spread)} between low and high offers.")
    elif spread > 0:
        signals.append(f"Moderate fare spread detected: {format_money(currency, spread)} across live offers.")
    if previous_low is not None:
        delta = best["price_value"] - previous_low
        if delta > 0:
            signals.append(f"This search is {format_money(currency, delta)} above this session's previous low.")
        elif delta < 0:
            signals.append(f"This search beat this session's previous low by {format_money(currency, abs(delta))}.")
        else:
            signals.append("This search matches this session's previous low.")
    if len(offers) <= 2:
        signals.append("Low offer count: treat this as pricing pressure, not a full market view.")

    anti_moves = []
    if best.get("search_note", "Exact trip") != "Exact trip":
        anti_moves.append(f"Use the winning variation: {best.get('search_note')} - {route_line(best)}.")
    else:
        anti_moves.append("Exact trip is currently competitive; still compare nearby airports before payment.")
    if trip.get("priority") != "fastest":
        anti_moves.append("Keep the one-day date shift open if the fare jumps before checkout.")
    anti_moves.append("Avoid paid bundles until baggage, seat, and refund rules are confirmed.")
    anti_moves.append("Do not refresh the same checkout endlessly; re-run a clean comparison if the price moves.")

    for move in pricing_context["weak_points_tested"]:
        anti_moves.append(f"Buyer-side counter move: {move}.")

    if days_out is not None and days_out <= 21:
        decision = "Buy now if baggage and rules fit"
        prediction = "Close departure window: price risk is tilted upward."
        confidence = "medium"
    elif savings_vs_exact >= 25:
        decision = "Buy the counter-priced option"
        prediction = "The alternate airport/date is already beating the exact request."
        confidence = "high" if len(searches) >= 3 else "medium"
    elif spread_pct >= 0.25:
        decision = "Hold only if flexible, otherwise buy the low fare"
        prediction = "Wide spread means airline pricing is unstable across similar options."
        confidence = "medium"
    elif len(offers) >= 4 and days_out is not None and days_out > 60:
        decision = "Watch 24-48 hours"
        prediction = "There is enough time and offer depth to monitor one more pricing move."
        confidence = "medium"
    else:
        decision = "Buy if this matches the trip goal"
        prediction = "No strong wait signal; protect the current fare if it fits."
        confidence = "medium"

    summary = (
        f"{decision}: AIFlight ranked {best.get('airline', 'the best offer')} at "
        f"{format_money(currency, best['price_value'])}. Median checked fare was "
        f"{format_money(currency, median)}."
    )
    best_guess = (
        "Strong best guess" if confidence == "high"
        else "Reasonable best guess" if confidence == "medium"
        else "Weak best guess"
    )

    return {
        "decision": decision,
        "confidence": confidence,
        "best_guess": best_guess,
        "summary": summary,
        "prediction": prediction,
        "pricing_context": pricing_context,
        "personalization": (
            f"Scoring is weighted for {trip.get('priority') or 'balanced'} priority, "
            f"{trip.get('cabin') or 'economy'} cabin, and {trip.get('adults') or 1} adult traveler(s)."
        ),
        "sources": sources,
        "signals": signals,
        "anti_pricing_moves": anti_moves,
        "metrics": {
            "offers_found": len(offers),
            "searches_checked": len(searches),
            "days_until_departure": days_out,
            "lowest_price": format_money(currency, lowest),
            "median_price": format_money(currency, median),
            "highest_price": format_money(currency, highest),
            "savings_vs_exact": format_money(currency, savings_vs_exact),
            "history_count": len(history)
        }
    }

def cards_from_offers(offers, trip):
    ranked, best, cheapest, fastest = analyze_offers(offers, trip)
    tradeoff = tradeoff_line(best, cheapest, fastest)

    cards = [
        {
            "title": "AIFlight Best Pick",
            "signal": format_money(best["currency"], best["price_value"]),
            "status": f"{best['airline']} - {best['stops']} stop(s)",
            "goal": "Book the strongest overall value",
            "risk": "Fare can expire or baggage rules may change",
            "explanation": f"{tradeoff} Flight time: {format_minutes(best.get('duration_minutes'))}. Search: {best.get('search_note', 'Exact trip')} - {route_line(best)}."
        }
    ]

    for offer in ranked:
        if offer["id"] == best["id"]:
            continue

        label = "Worth Comparing"
        if offer["id"] == cheapest["id"]:
            label = "Cheapest Backup"
        elif offer["id"] == fastest["id"]:
            label = "Fastest Backup"

        cards.append({
            "title": label,
            "signal": format_money(offer["currency"], offer["price_value"]),
            "status": f"{offer['stops']} stop(s)",
            "goal": offer["airline"],
            "risk": "Offer expires",
            "explanation": f"Flight time: {format_minutes(offer.get('duration_minutes'))}. Search: {offer.get('search_note', 'Exact trip')} - {route_line(offer)}. Offer expires at {offer.get('expires_at') or 'provider-controlled time'}."
        })

        if len(cards) == 3:
            break

    return cards

def ai_strategy(trip, offers, reason, intelligence=None):
    if offers:
        ranked, best, cheapest, fastest = analyze_offers(offers, trip)
        fallback = (
            f"AIFlight recommends {best['airline']} at {format_money(best['currency'], best['price_value'])}. "
            f"{tradeoff_line(best, cheapest, fastest)} Check baggage, seats, and ticket rules before booking."
        )
    else:
        fallback_info = fallback_details(trip, reason)
        fallback = fallback_info["explanation"]

    if not client:
        return fallback

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are AIFlight, a flight price-defense algorithm."},
                {"role": "user", "content": f"Trip: {trip}\nDuffel offers: {offers}\nPrice intelligence: {intelligence or {}}\nDeterministic recommendation: {fallback}\nReason if empty: {reason}\nWrite a short, direct recommendation for one best flight. Mention useful tradeoffs like saving money for a longer trip when supported by the data. Do not invent prices, airlines, or flight details."}
            ],
            max_tokens=150,
            temperature=0.45
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback

def provider_status_snapshot():
    providers = []
    for provider in FLIGHT_PROVIDERS:
        item = dict(provider)
        if item["id"] == "duffel":
            item["configured"] = bool(DUFFEL_ACCESS_TOKEN and httpx)
            item["status"] = "live" if item["configured"] else "needs_setup"
        providers.append(item)
    return providers

def orchestrate_chat_trip(message, current_trip, history):
    trace = [
        trace_step("api_gateway", "passed", "Payload accepted, rate limit checked, and input normalized.")
    ]

    brain = ai_agent_brain(message, current_trip, history)
    trip = brain["trip"]
    trace.append(trace_step("trip_orchestrator", "done", "Trip intent converted into structured trip state."))
    trace.append(trace_step("ai_brain_loop", brain.get("self_evaluation", {}).get("action", "done"), "Perceive, understand, context, decision, and self-check completed."))

    missing = missing_chat_fields(trip)
    advisory_reply = direct_advisory_reply(message, trip, missing or brain.get("missing_fields", []))
    if advisory_reply:
        missing_fields = missing or brain["missing_fields"]
        trace.append(trace_step("decision_engine", "advisory", "Answered strategy/advisory prompt without pretending to have live fare data.", missing=missing_fields))
        return {
            "complete": False,
            "reply": advisory_reply,
            "trip": trip,
            "missing": missing_fields,
            "ai_enabled": bool(client),
            "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
            "providers": provider_status_snapshot(),
            "brain_loop": brain.get("brain_loop", {}),
            "world_model": brain.get("world_model", {}),
            "self_evaluation": brain.get("self_evaluation", {}),
            "platform_trace": trace
        }

    if missing or not brain["ready_to_search"]:
        missing_fields = missing or brain["missing_fields"]
        reply = brain["reply"] or ai_followup_reply(message, trip, missing_fields, history)
        trace.append(trace_step("decision_engine", "waiting", "More trip details are required before live pricing.", missing=missing_fields))
        return {
            "complete": False,
            "reply": reply,
            "trip": trip,
            "missing": missing_fields,
            "ai_enabled": bool(client),
            "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
            "providers": provider_status_snapshot(),
            "brain_loop": brain.get("brain_loop", {}),
            "world_model": brain.get("world_model", {}),
            "self_evaluation": brain.get("self_evaluation", {}),
            "platform_trace": trace
        }

    search_trip = prepare_chat_search_trip(trip)
    trace.append(trace_step("data_quality_normalization", "done", "Trip state normalized for provider search."))

    links = build_search_links(
        search_trip["origin"],
        search_trip["destination"],
        search_trip["trip_type"],
        search_trip["depart_date"],
        search_trip["return_date"]
    )

    offers, reason, deal_space = fetch_deal_space_offers(search_trip)
    search_trip["deal_space"] = deal_space
    provider_detail = f"{len(offers)} offer(s) from {len(deal_space)} deal-space search(es)."
    trace.append(trace_step("flight_data_platform", reason, provider_detail, providers=provider_status_snapshot()))

    if offers:
        cards = cards_from_offers(offers, search_trip)
    else:
        cards = fallback_cards(search_trip, links, reason)

    intelligence = build_price_intelligence(search_trip, offers, deal_space, reason)
    record_price_observation(search_trip, offers, intelligence)
    trace.append(trace_step("feature_engine", "done", "Price, time, stops, spread, and session-history features calculated."))
    trace.append(trace_step("ai_ml_intelligence", "done", intelligence["prediction"]))
    trace.append(trace_step("decision_engine", intelligence["decision"], intelligence["summary"], confidence=intelligence["confidence"]))

    strategy = ai_strategy(search_trip, offers, reason, intelligence)
    plan = trip_plan_line(search_trip)
    reply = ai_chat_reply(message, search_trip, offers, cards, links, reason, plan, strategy, history, intelligence)
    trace.append(trace_step("llm_explanation", "done", "Natural-language explanation generated from structured pricing facts."))
    trace.append(trace_step("results_experience", "ready", "Cards, links, intelligence, and decision returned to the UI."))
    trace.append(trace_step("feedback_learning_loop", "ready", "UI can submit feedback for future scoring improvements."))
    trace.append(trace_step("monitoring_evals_safety", "logged", "Request outcome recorded without secrets."))

    return {
        "complete": True,
        "reply": reply,
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
        "trip": search_trip,
        "strategy": strategy,
        "intelligence": intelligence,
        "cards": cards,
        "offers": offers,
        "deal_space": deal_space,
        "providers": provider_status_snapshot(),
        "brain_loop": brain.get("brain_loop", {}),
        "world_model": brain.get("world_model", {}),
        "self_evaluation": brain.get("self_evaluation", {}),
        "platform_trace": trace,
        "links": links,
        "reason": reason
    }

def orchestrate_search_trip(trip):
    trace = [
        trace_step("api_gateway", "passed", "Search payload validated."),
        trace_step("data_quality_normalization", "done", "Airport, date, passenger, cabin, and priority values normalized.")
    ]
    links = build_search_links(
        trip["origin"],
        trip["destination"],
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"]
    )

    offers, reason, deal_space = fetch_deal_space_offers(trip)
    trip["deal_space"] = deal_space
    trace.append(trace_step("flight_data_platform", reason, f"{len(offers)} offer(s) returned.", providers=provider_status_snapshot()))

    cards = cards_from_offers(offers, trip) if offers else fallback_cards(trip, links, reason)
    intelligence = build_price_intelligence(trip, offers, deal_space, reason)
    record_price_observation(trip, offers, intelligence)
    strategy = ai_strategy(trip, offers, reason, intelligence)
    trace.append(trace_step("decision_engine", intelligence["decision"], intelligence["summary"], confidence=intelligence["confidence"]))

    return {
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
        "trip": trip,
        "strategy": strategy,
        "intelligence": intelligence,
        "cards": cards,
        "offers": offers,
        "deal_space": deal_space,
        "providers": provider_status_snapshot(),
        "platform_trace": trace,
        "links": links,
        "reason": reason
    }

def run_trip_understanding_evals():
    results = []
    for case in EVAL_CASES:
        trip = merge_trip_updates(blank_chat_trip(), rule_extract_trip_details(case["message"]))
        expected = case["expected"]
        passed = all(trip.get(key) == value for key, value in expected.items())
        results.append({
            "name": case["name"],
            "passed": passed,
            "expected": expected,
            "actual": {key: trip.get(key) for key in expected}
        })

    return {
        "passed": sum(1 for item in results if item["passed"]),
        "total": len(results),
        "results": results
    }

@app.route("/api/chat", methods=["POST"])
def chat():
    if is_rate_limited("/api/chat", limit=25, window_seconds=60):
        return json_error("Too many requests. Wait a minute and try again.", 429, "rate_limited")

    payload, error = validate_chat_payload(request.get_json(silent=True) or {})
    if error:
        return json_error(error, 400, "invalid_chat_payload")

    response = orchestrate_chat_trip(payload["message"], payload["trip"], payload["history"])
    record_api_event("/api/chat", "ok", "chat completed", complete=response.get("complete"))
    return jsonify(response)

@app.route("/api/search", methods=["POST"])
def search():
    if is_rate_limited("/api/search", limit=20, window_seconds=60):
        return json_error("Too many search requests. Wait a minute and try again.", 429, "rate_limited")

    trip, error = validate_search_trip(request.get_json(silent=True) or {})
    if error:
        return json_error(error, 400, "invalid_search_payload")

    print("Trip search:", trip, flush=True)
    response = orchestrate_search_trip(trip)
    record_api_event("/api/search", "ok", "search completed", offers=len(response.get("offers", [])))
    return jsonify(response)

@app.route("/api/feedback", methods=["POST"])
def feedback():
    if is_rate_limited("/api/feedback", limit=20, window_seconds=60):
        return json_error("Too many feedback requests. Wait a minute and try again.", 429, "rate_limited")

    data = request.get_json(silent=True) or {}
    rating = str(data.get("rating") or "").strip().lower()
    if rating not in ("helpful", "not_helpful"):
        return json_error("Feedback rating must be helpful or not_helpful.", 400, "invalid_feedback")

    FEEDBACK_EVENTS.append({
        "rating": rating,
        "decision": str(data.get("decision") or "")[:120],
        "route": str(data.get("route") or "")[:80],
        "comment": str(data.get("comment") or "")[:500],
        "at": utc_now()
    })
    del FEEDBACK_EVENTS[:-MAX_FEEDBACK_EVENTS]
    record_api_event("/api/feedback", "ok", rating)
    return jsonify({"status": "ok", "feedback_count": len(FEEDBACK_EVENTS)})

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
        "providers": provider_status_snapshot(),
        "layers": PLATFORM_LAYERS
    })

@app.route("/api/metrics")
def metrics():
    status_counts = {}
    for event in API_EVENTS:
        status_counts[event["status"]] = status_counts.get(event["status"], 0) + 1

    return jsonify({
        "status": "ok",
        "events": len(API_EVENTS),
        "status_counts": status_counts,
        "price_observations": len(PRICE_OBSERVATIONS),
        "feedback_events": len(FEEDBACK_EVENTS),
        "providers": provider_status_snapshot(),
        "layers": PLATFORM_LAYERS
    })

@app.route("/api/evals")
def evals():
    results = run_trip_understanding_evals()
    record_api_event("/api/evals", "ok", f"{results['passed']} of {results['total']} passed")
    return jsonify({
        "status": "ok" if results["passed"] == results["total"] else "needs_attention",
        "suite": "trip_understanding",
        **results
    })

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
