import json
import os
import re
from datetime import datetime, timedelta
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
DUFFEL_ACCESS_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY and OpenAI else None

AIRPORT_MAP = {
    "egypt": "CAI", "cairo": "CAI",
    "new york": "JFK", "nyc": "JFK",
    "manhattan": "JFK", "brooklyn": "JFK",
    "lga": "LGA", "jfk": "JFK", "ewr": "EWR",
    "boston": "BOS", "bos": "BOS",
    "london": "LHR", "londen": "LHR", "lhr": "LHR", "heathrow": "LHR",
    "houston": "IAH", "iah": "IAH", "hou": "HOU",
    "dallas": "DFW", "arlington": "DFW", "dfw": "DFW",
    "dubai": "DXB", "los angeles": "LAX", "la": "LAX",
    "san francisco": "SFO", "sfo": "SFO",
    "chicago": "ORD", "ord": "ORD",
    "miami": "MIA", "mia": "MIA",
    "atlanta": "ATL", "atl": "ATL",
    "paris": "CDG", "cdg": "CDG",
    "rome": "FCO", "fco": "FCO",
    "tokyo": "HND", "hnd": "HND",
    "toronto": "YYZ", "yyz": "YYZ"
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

def normalize_airport(value):
    value = (value or "").strip()
    if not value:
        return ""

    key = re.sub(r"[^a-z0-9 ]+", " ", value.lower())
    key = re.sub(r"\s+", " ", key).strip()
    if key in AIRPORT_MAP:
        return AIRPORT_MAP[key]

    if re.fullmatch(r"[a-zA-Z]{3}", value):
        return value.upper()

    for name, code in sorted(AIRPORT_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", key):
            return code

    return value.upper()

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
    trip["event_context"] = trip.get("event_context") if isinstance(trip.get("event_context"), dict) else {}
    return trip

def coerce_optional_count(value, default=None, minimum=0):
    if value in ("", None):
        return default
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(count, 9))

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

    if "tomorrow" in text:
        return [(today + timedelta(days=1)).strftime("%Y-%m-%d")]

    months = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12
    }

    found = []
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

def detect_date_window(text):
    text = (text or "").lower()
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

def detect_world_cup_texas_request(text):
    lower = (text or "").lower()
    if "world cup" not in lower or "texas" not in lower:
        return False
    return any(word in lower for word in ("first", "earliest", "only one", "one match", "1 match"))

def resolve_world_cup_texas_trip(text):
    if not detect_world_cup_texas_request(text):
        return {}

    lower = (text or "").lower()
    match_date = datetime.strptime(WORLD_CUP_TEXAS_FIRST_MATCH["date"], "%Y-%m-%d").date()
    depart_date = (match_date - timedelta(days=1)).strftime("%Y-%m-%d")
    return_date = (match_date + timedelta(days=1)).strftime("%Y-%m-%d")

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
    lower = text.lower()
    updates = {}

    route_stop = r"(?:[.,]|$|\s+on|\s+next|\s+in|\s+with|\s+and|\s+come\s+back|\s+return)"
    route_match = re.search(rf"\bfrom\s+([a-zA-Z .]+?)\s+(?:to|for)\s+([a-zA-Z .]+?){route_stop}", lower)
    if route_match:
        updates["origin"] = normalize_airport(route_match.group(1))
        if not is_place_pronoun(route_match.group(2)):
            updates["destination"] = normalize_airport(route_match.group(2))
    else:
        to_match = re.search(rf"\b(?:to|for)\s+([a-zA-Z .]+?){route_stop}", lower)
        if to_match and not is_place_pronoun(to_match.group(1)):
            updates["destination"] = normalize_airport(to_match.group(1))

        from_match = re.search(rf"\bfrom\s+([a-zA-Z .]+?){route_stop}", lower)
        if from_match:
            updates["origin"] = normalize_airport(from_match.group(1))

    if "round trip" in lower or "roundtrip" in lower or "coming back" in lower or "return" in lower:
        updates["trip_type"] = "roundtrip"
    elif "one way" in lower or "one-way" in lower or "single" in lower:
        updates["trip_type"] = "oneway"

    dates = parse_chat_date(lower)
    if dates:
        updates["depart_date"] = dates[0]
        if len(dates) > 1:
            updates["return_date"] = dates[1]
            updates["trip_type"] = "roundtrip"
    else:
        window = detect_date_window(lower)
        if window:
            updates["date_window"] = window

    adult_match = re.search(r"\b(\d+)\s+(?:adult|adults|passenger|passengers|people|person|traveler|travelers)\b", lower)
    child_match = re.search(r"\b(\d+)\s+(?:child|children|kid|kids)\b", lower)
    infant_match = re.search(r"\b(\d+)\s+(?:infant|infants|baby|babies)\b", lower)
    if adult_match:
        updates["adults"] = int(adult_match.group(1))
    elif "solo" in lower or "alone" in lower or "just me" in lower:
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

    if "comfort" in lower or "comfortable" in lower or "low stress" in lower:
        updates["priority"] = "comfort"
    elif "money" in lower and ("not" in lower or "no concern" in lower or "flexible" in lower):
        updates["priority"] = "comfort"
    elif "cheap" in lower or "lowest price" in lower or "budget" in lower:
        updates["priority"] = "cheapest"
    elif "fast" in lower or "quick" in lower:
        updates["priority"] = "fastest"

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
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract flight search details from a travel chat. Return JSON only. "
                        "Use these keys: origin, destination, trip_type, depart_date, return_date, "
                        "date_window, adults, children, infants, priority, cabin, seat, preference. "
                        "Use IATA airport codes when obvious. London or londen should be LHR. "
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
    if not is_valid_date(trip.get("depart_date")):
        if trip.get("date_window"):
            missing.append(f"exact departure date in {trip['date_window']}")
        else:
            missing.append("exact departure date")
    if trip.get("trip_type") not in ("oneway", "roundtrip"):
        missing.append("one-way or round trip")
    if trip.get("trip_type") == "roundtrip" and not is_valid_date(trip.get("return_date")):
        missing.append("return date")
    if not trip.get("adults"):
        missing.append("number of adults")
    if not trip.get("cabin"):
        missing.append("cabin")
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
    if trip.get("trip_type"):
        parts.append("round trip" if trip["trip_type"] == "roundtrip" else "one way")
    if trip.get("adults"):
        parts.append(f"{trip['adults']} adult(s)")
    if trip.get("cabin"):
        parts.append(f"{trip['cabin']} cabin")
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

    if len(missing) == 1:
        needed = missing[0]
    else:
        needed = ", ".join(missing[:-1]) + f", and {missing[-1]}"

    return f"I noted {summary}. I still need {needed}. Send that and I will pull live prices."

def prepare_chat_search_trip(trip):
    priority = trip.get("priority") or "balanced"
    return {
        "origin": trip["origin"],
        "destination": trip["destination"],
        "trip_type": trip["trip_type"],
        "depart_date": trip["depart_date"],
        "return_date": trip.get("return_date", ""),
        "adults": parse_passenger_count(trip.get("adults"), default=1, minimum=1),
        "children": parse_passenger_count(trip.get("children"), default=0),
        "infants": parse_passenger_count(trip.get("infants"), default=0),
        "priority": priority,
        "cabin": trip["cabin"],
        "seat": trip.get("seat") or "none",
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
            "explanation": f"{tradeoff} Flight time: {format_minutes(best.get('duration_minutes'))}."
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
            "explanation": f"Flight time: {format_minutes(offer.get('duration_minutes'))}. Offer expires at {offer.get('expires_at') or 'provider-controlled time'}."
        })

        if len(cards) == 3:
            break

    return cards

def ai_strategy(trip, offers, reason):
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
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are AIFlight, a flight price-defense algorithm."},
                {"role": "user", "content": f"Trip: {trip}\nDuffel offers: {offers}\nDeterministic recommendation: {fallback}\nReason if empty: {reason}\nWrite a short, direct recommendation for one best flight. Mention useful tradeoffs like saving money for a longer trip when supported by the data. Do not invent prices, airlines, or flight details."}
            ],
            max_tokens=150,
            temperature=0.45
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    history = data.get("history") if isinstance(data.get("history"), list) else []

    if not message:
        return jsonify({"error": "Message is required."}), 400

    current_trip = coerce_chat_trip(data.get("trip") or {})
    rule_updates = rule_extract_trip_details(message)
    ai_updates = ai_extract_trip_details(message, current_trip, history)
    updates = {**rule_updates, **{key: value for key, value in ai_updates.items() if value not in ("", None)}}
    if rule_updates.get("event_context"):
        updates.update(rule_updates)
    trip = merge_trip_updates(current_trip, updates)

    missing = missing_chat_fields(trip)
    if missing:
        return jsonify({
            "complete": False,
            "reply": followup_reply(trip, missing),
            "trip": trip,
            "missing": missing,
            "ai_enabled": bool(client),
            "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN)
        })

    search_trip = prepare_chat_search_trip(trip)
    links = build_search_links(
        search_trip["origin"],
        search_trip["destination"],
        search_trip["trip_type"],
        search_trip["depart_date"],
        search_trip["return_date"]
    )

    offers, reason = fetch_duffel_offers(search_trip)
    if offers:
        cards = cards_from_offers(offers, search_trip)
    else:
        cards = fallback_cards(search_trip, links, reason)

    strategy = ai_strategy(search_trip, offers, reason)
    plan = trip_plan_line(search_trip)
    if offers:
        reply = f"{plan} I found live prices and picked the strongest option: {cards[0]['signal']}. {strategy}".strip()
    else:
        reply = f"{plan} {strategy}".strip()

    return jsonify({
        "complete": True,
        "reply": reply,
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
        "trip": search_trip,
        "strategy": strategy,
        "cards": cards,
        "offers": offers,
        "links": links,
        "reason": reason
    })

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(silent=True) or {}

    trip = {
        "origin": normalize_airport(data.get("origin", "LGA")),
        "destination": normalize_airport(data.get("destination", "BOS")),
        "trip_type": data.get("tripType", "oneway"),
        "depart_date": data.get("departDate", ""),
        "return_date": data.get("returnDate", ""),
        "adults": parse_passenger_count(data.get("adults", 1), default=1, minimum=1),
        "children": parse_passenger_count(data.get("children", 0)),
        "infants": parse_passenger_count(data.get("infants", 0)),
        "priority": data.get("priority", "balanced"),
        "cabin": data.get("cabin", "economy"),
        "seat": data.get("seat", "none"),
        "preference": data.get("preference", "")
    }

    if not trip["origin"] or not trip["destination"]:
        return jsonify({"error": "Origin and destination are required."}), 400

    if not is_valid_date(trip["depart_date"]):
        return jsonify({"error": "A valid departure date is required."}), 400

    if trip["trip_type"] == "roundtrip" and not is_valid_date(trip["return_date"]):
        return jsonify({"error": "A valid return date is required for round trips."}), 400

    print("Trip search:", trip, flush=True)

    links = build_search_links(
        trip["origin"],
        trip["destination"],
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"]
    )

    offers, reason = fetch_duffel_offers(trip)

    if offers:
        cards = cards_from_offers(offers, trip)
    else:
        cards = fallback_cards(trip, links, reason)

    strategy = ai_strategy(trip, offers, reason)

    return jsonify({
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN),
        "trip": trip,
        "strategy": strategy,
        "cards": cards,
        "offers": offers,
        "links": links,
        "reason": reason
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": bool(client),
        "duffel_enabled": bool(DUFFEL_ACCESS_TOKEN)
    })

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
