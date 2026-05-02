import os
from urllib.parse import quote_plus
from flask import Flask, render_template, request, jsonify
from openai import OpenAI
import httpx

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
DUFFEL_ACCESS_TOKEN = os.getenv("DUFFEL_ACCESS_TOKEN", "")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

AIRPORT_MAP = {
    "egypt": "CAI", "cairo": "CAI",
    "new york": "JFK", "nyc": "JFK",
    "lga": "LGA", "jfk": "JFK", "ewr": "EWR",
    "boston": "BOS", "bos": "BOS",
    "london": "LHR", "lhr": "LHR",
    "dubai": "DXB", "los angeles": "LAX", "la": "LAX"
}

def normalize_airport(value):
    value = (value or "").strip()
    return AIRPORT_MAP.get(value.lower(), value.upper())

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
    if not DUFFEL_ACCESS_TOKEN:
        print("DEBUG: DUFFEL_ACCESS_TOKEN missing", flush=True)
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

        print("DEBUG: Duffel status:", response.status_code, flush=True)
        print("DEBUG: Duffel raw:", response.text[:1000], flush=True)

        if response.status_code >= 400:
            return [], f"duffel_error_{response.status_code}"

        data = response.json().get("data", {})
        offers = data.get("offers", [])[:8]

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

        return parsed, "ok"

    except Exception as e:
        print("DEBUG: Duffel exception:", str(e), flush=True)
        return [], "exception"

def fallback_cards(trip, links, reason):
    return [
        {
            "title": "Duffel Search Needs Attention",
            "signal": "No offers returned",
            "status": reason,
            "goal": "Verify setup",
            "risk": "No live Duffel offer yet",
            "explanation": "Duffel did not return offers for this search. Try JFK to LHR with a future date, confirm your token is saved in Render, or check Render logs."
        },
        {
            "title": "Compare Manually",
            "signal": "Use trusted sites",
            "status": "Fallback",
            "goal": "Still find real prices",
            "risk": "Prices may change",
            "explanation": "Use Google Flights, Kayak, or Skyscanner while Duffel setup is being verified."
        }
    ]

def cards_from_offers(offers):
    cheapest = min(offers, key=lambda x: float(x["price"] or 999999))
    fewest_stops = min(offers, key=lambda x: x["stops"])

    cards = [
        {
            "title": "Lowest Duffel Offer",
            "signal": f"{cheapest['currency']} {cheapest['price']}",
            "status": "Duffel offer",
            "goal": "Save money",
            "risk": "Offer can expire",
            "explanation": f"{cheapest['airline']} returned the lowest offer. Verify baggage, seat, and ticket rules before booking."
        },
        {
            "title": "Low-Stress Option",
            "signal": f"{fewest_stops['stops']} stop(s)",
            "status": "Duffel offer",
            "goal": "Reduce stress",
            "risk": "May cost more",
            "explanation": f"{fewest_stops['airline']} has the lowest stop count in this search. Good for families or comfort-focused trips."
        }
    ]

    for offer in offers[:4]:
        cards.append({
            "title": offer["airline"],
            "signal": f"{offer['currency']} {offer['price']}",
            "status": f"{offer['stops']} stop(s)",
            "goal": "Compare offer",
            "risk": "Offer expires",
            "explanation": f"Duration: {offer['duration']}. Offer expires at {offer.get('expires_at') or 'provider-controlled time'}."
        })

    return cards

def ai_strategy(trip, offers, reason):
    if offers:
        cheapest = min(offers, key=lambda x: float(x["price"] or 999999))
        fallback = (
            f"Duffel returned real offers. The lowest offer shown is {cheapest['currency']} {cheapest['price']} "
            f"with {cheapest['airline']}. Compare stops, duration, baggage, and expiration before booking."
        )
    else:
        fallback = (
            f"Duffel returned no offers for {trip['origin']} to {trip['destination']} yet. "
            f"Reason: {reason}. Try a major test route like JFK to LHR and a future date."
        )

    if not client:
        return fallback

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are AIFlight, a flight price-defense algorithm."},
                {"role": "user", "content": f"Trip: {trip}\nDuffel offers: {offers}\nReason if empty: {reason}\nWrite a short, honest recommendation. Do not invent prices."}
            ],
            max_tokens=150,
            temperature=0.45
        )
        return response.choices[0].message.content.strip()
    except Exception:
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
        "preference": data.get("preference", "")
    }

    print("DEBUG: TRIP:", trip, flush=True)

    links = build_search_links(
        trip["origin"],
        trip["destination"],
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"]
    )

    offers, reason = fetch_duffel_offers(trip)

    if offers:
        cards = cards_from_offers(offers)
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
    app.run(debug=True)
