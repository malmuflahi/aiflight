import os
from urllib.parse import quote_plus
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import httpx

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

FLIGHT_API_KEY = os.getenv("FLIGHT_API_KEY", "")
FLIGHT_API_ID = os.getenv("FLIGHT_API_ID", "")

AIRPORT_MAP = {
    "egypt": "CAI",
    "cairo": "CAI",
    "new york": "JFK",
    "nyc": "JFK",
    "lga": "LGA",
    "jfk": "JFK",
    "ewr": "EWR",
    "boston": "BOS",
    "bos": "BOS",
    "london": "LHR",
    "lhr": "LHR",
    "dubai": "DXB",
    "los angeles": "LAX",
    "la": "LAX",
}

def normalize_airport(value):
    value = (value or "").strip()
    return AIRPORT_MAP.get(value.lower(), value.upper())

@app.route("/")
def home():
    return render_template("index.html")

def build_links(origin, destination, trip_type, depart_date, return_date):
    google_query = f"flights from {origin} to {destination} on {depart_date}"
    if trip_type == "roundtrip" and return_date:
        google_query = f"round trip flights from {origin} to {destination} depart {depart_date} return {return_date}"

    google = f"https://www.google.com/travel/flights?q={quote_plus(google_query)}"

    kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"
    if trip_type == "roundtrip" and return_date:
        kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}/{return_date}"

    skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/"
    if trip_type == "roundtrip" and return_date:
        skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/{return_date.replace('-', '')}/"

    return {"google": google, "kayak": kayak, "skyscanner": skyscanner}

def fetch_travelpayouts_prices(trip):
    if not FLIGHT_API_KEY:
        print("DEBUG: FLIGHT_API_KEY missing", flush=True)
        return []

    url = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"

    params = {
        "origin": trip["origin"],
        "destination": trip["destination"],
        "departure_at": trip["depart_date"],
        "currency": "usd",
        "sorting": "price",
        "limit": 10,
        "token": FLIGHT_API_KEY,
    }

    if trip["trip_type"] == "roundtrip" and trip["return_date"]:
        params["return_at"] = trip["return_date"]

    print("DEBUG: Travelpayouts request params:", params, flush=True)

    try:
        with httpx.Client(timeout=25) as client_http:
            response = client_http.get(url, params=params)

        print("DEBUG: Travelpayouts status:", response.status_code, flush=True)
        print("DEBUG: Travelpayouts raw response:", response.text[:1000], flush=True)

        response.raise_for_status()
        payload = response.json()

        flights = []
        for item in payload.get("data", []):
            flights.append({
                "price": item.get("price"),
                "airline": item.get("airline", "Airline"),
                "flight_number": item.get("flight_number"),
                "departure_at": item.get("departure_at"),
                "return_at": item.get("return_at"),
                "transfers": item.get("transfers", 0),
                "duration": item.get("duration"),
                "link": item.get("link"),
            })

        print("DEBUG: FLIGHTS:", flights, flush=True)
        return flights

    except Exception as error:
        print("DEBUG: Travelpayouts error:", str(error), flush=True)
        return []

def build_affiliate_link(raw_link):
    if not raw_link:
        return None

    if raw_link.startswith("http"):
        return raw_link

    base = f"https://www.aviasales.com{raw_link}"

    if FLIGHT_API_ID:
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}marker={FLIGHT_API_ID}"

    return base

def build_cards(trip, flights):
    if flights:
        cheapest = min(flights, key=lambda x: x.get("price") or 999999)
        fewest_stops = min(flights, key=lambda x: x.get("transfers", 99))

        return [
            {
                "title": "Lowest Real Fare Found",
                "signal": f"${cheapest.get('price', 'Check price')}",
                "status": "Live API result",
                "goal": "Save money",
                "risk": "Verify before booking",
                "explanation": f"We found a live fare from {trip['origin']} to {trip['destination']}. Compare it before booking because flight prices can change.",
                "booking_link": build_affiliate_link(cheapest.get("link")),
            },
            {
                "title": "Low-Stress Route Check",
                "signal": "Fewer stops",
                "status": "Comfort check",
                "goal": "Reduce stress",
                "risk": "May cost more",
                "explanation": "This option focuses on fewer stops and a smoother route.",
                "booking_link": build_affiliate_link(fewest_stops.get("link")),
            },
            {
                "title": "Price Defense Move",
                "signal": "Compare before buying",
                "status": "Smart check",
                "goal": "Avoid overpaying",
                "risk": "Prices can change",
                "explanation": "Do not trust one site only. Check at least two booking sites before paying.",
                "booking_link": None,
            },
        ]

    return [
        {
            "title": "Live Data Not Returned Yet",
            "signal": "Use search links",
            "status": "Fallback mode",
            "goal": "Still compare real prices",
            "risk": "API may be pending approval",
            "explanation": "Your API key is loaded, but the provider returned no live fares for this search. Use the search links below while approval or route coverage is pending.",
            "booking_link": None,
        },
        {
            "title": "Cheapest Hunt",
            "signal": "Lowest-price search",
            "status": "Compare sites",
            "goal": "Save money",
            "risk": "May include layovers",
            "explanation": "Best when price matters most. Check nearby airports and flexible dates.",
            "booking_link": None,
        },
        {
            "title": "Low-Stress Hunt",
            "signal": "Comfort-first",
            "status": "Reduce stress",
            "goal": "Better route",
            "risk": "May cost more",
            "explanation": "Best for family trips, kids, infants, or long international routes.",
            "booking_link": None,
        },
    ]

def ai_strategy(trip, flights):
    if flights:
        cheapest = min(flights, key=lambda x: x.get("price") or 999999)
        fallback = (
            f"Lowest live fare found is about ${cheapest.get('price')}. "
            "Compare this fare across multiple booking sites before booking."
        )
    else:
        fallback = (
            f"No live fare was returned for {trip['origin']} to {trip['destination']} yet. "
            "Use the booking links to verify real-time prices, and try nearby airports or flexible dates."
        )

    if not client:
        return fallback

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are AIFlight, a flight price defense algorithm."},
                {
                    "role": "user",
                    "content": f"""
Trip:
{trip}

Live flight data:
{flights}

Write a short recommendation.
Do not invent prices or durations.
If no live data exists, say to compare booking sites and try nearby airports.
"""
                }
            ],
            max_tokens=150,
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    except Exception as error:
        print("DEBUG: OpenAI error:", str(error), flush=True)
        return fallback

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    trip = {
        "origin": normalize_airport(data.get("origin", "LGA")),
        "destination": normalize_airport(data.get("destination", "BOS")),
        "trip_type": data.get("tripType", "oneway"),
        "depart_date": data.get("departDate", ""),
        "return_date": data.get("returnDate", ""),
        "adults": int(data.get("adults", 1)),
        "children": int(data.get("children", 0)),
        "infants": int(data.get("infants", 0)),
        "priority": data.get("priority", "balanced"),
        "cabin": data.get("cabin", "economy"),
        "seat": data.get("seat", "none"),
        "preference": data.get("preference", ""),
    }

    print("DEBUG: SEARCH TRIP:", trip, flush=True)

    links = build_links(
        trip["origin"],
        trip["destination"],
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"],
    )

    flights = fetch_travelpayouts_prices(trip)
    cards = build_cards(trip, flights)
    strategy = ai_strategy(trip, flights)

    print("DEBUG: FINAL FLIGHTS COUNT:", len(flights), flush=True)
    print("DEBUG: FINAL CARDS COUNT:", len(cards), flush=True)

    return jsonify({
        "ai_enabled": bool(client),
        "flight_api_enabled": bool(FLIGHT_API_KEY),
        "trip": trip,
        "strategy": strategy,
        "cards": cards,
        "flights": flights,
        "links": links,
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": bool(client),
        "flight_api_enabled": bool(FLIGHT_API_KEY),
    })

if __name__ == "__main__":
    app.run(debug=True)
