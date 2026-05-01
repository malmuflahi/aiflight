import os
from urllib.parse import quote_plus
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


AIRPORT_MAP = {
    "egypt": "CAI",
    "cairo": "CAI",
    "new york": "JFK",
    "nyc": "JFK",
    "los angeles": "LAX",
    "la": "LAX",
    "dubai": "DXB",
    "london": "LHR",
    "istanbul": "IST",
    "jeddah": "JED",
    "sanaa": "SAH",
    "aden": "ADE"
}


def normalize_airport(value):
    value = value.strip()
    return AIRPORT_MAP.get(value.lower(), value.upper())


@app.route("/")
def home():
    return render_template("index.html")


def build_links(origin, destination, trip_type, depart_date, return_date, adults, children, infants):
    q = quote_plus(f"flights from {origin} to {destination} on {depart_date}")
    if trip_type == "roundtrip" and return_date:
        q = quote_plus(f"round trip flights from {origin} to {destination} depart {depart_date} return {return_date}")

    google = f"https://www.google.com/travel/flights?q={q}"

    kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"
    if trip_type == "roundtrip" and return_date:
        kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}/{return_date}"

    skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/"
    if trip_type == "roundtrip" and return_date:
        skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/{return_date.replace('-', '')}/"

    return {
        "google": google,
        "kayak": kayak,
        "skyscanner": skyscanner
    }


def decision_cards(priority):
    cards = [
        {
            "title": "AI Price Defense",
            "signal": "Recommended",
            "status": "Track before booking",
            "risk": "Medium",
            "goal": "Best balance",
            "explanation": "Use this when you want AI to compare timing, stress, and booking risk before you spend money."
        },
        {
            "title": "Cheapest Hunt",
            "signal": "Lowest-price search",
            "status": "Compare sites",
            "risk": "Higher stress",
            "goal": "Save money",
            "explanation": "Best when price matters most. You may accept longer routes, layovers, or less convenient timing."
        },
        {
            "title": "Fastest Route Hunt",
            "signal": "Time-first search",
            "status": "Avoid wasted time",
            "risk": "Higher price",
            "goal": "Save time",
            "explanation": "Best when time matters more than money. AI focuses on direct or shorter routes."
        },
        {
            "title": "Low-Stress Flight Hunt",
            "signal": "Comfort-first search",
            "status": "Reduce travel anxiety",
            "risk": "May cost more",
            "goal": "Less stress",
            "explanation": "Best for families, kids, infants, or long international trips where layovers create stress."
        }
    ]

    if priority == "cheapest":
        return [cards[1], cards[0], cards[3], cards[2]]
    if priority == "fastest":
        return [cards[2], cards[0], cards[3], cards[1]]
    if priority == "comfort":
        return [cards[3], cards[0], cards[2], cards[1]]
    return cards


def ai_price_strategy(trip, cards):
    fallback = (
        f"For {trip['origin']} to {trip['destination']}, do not trust one site only. "
        "Compare at least two booking sites, check nearby airports, and avoid waiting too long if prices start rising. "
        "AIFLight is acting as your price-defense layer before you book."
    )

    if not client:
        return fallback

    prompt = f"""
You are AIFLight, an AI price-defense system built to help travelers beat airline pricing swings.

Trip:
{trip}

Decision cards:
{cards}

Write a short premium recommendation.
Do not invent exact live prices or flight durations.
Explain how the user should search, when to buy/wait, and what to compare.
Sound confident and practical.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert flight price strategy AI."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=140,
            temperature=0.65
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    origin = normalize_airport(data.get("origin", "JFK"))
    destination = normalize_airport(data.get("destination", "CAI"))

    trip = {
        "origin": origin,
        "destination": destination,
        "trip_type": data.get("tripType", "oneway"),
        "depart_date": data.get("departDate", ""),
        "return_date": data.get("returnDate", ""),
        "adults": int(data.get("adults", 1)),
        "children": int(data.get("children", 0)),
        "infants": int(data.get("infants", 0)),
        "priority": data.get("priority", "balanced"),
        "preference": data.get("preference", "")
    }

    cards = decision_cards(trip["priority"])
    links = build_links(
        origin,
        destination,
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"],
        trip["adults"],
        trip["children"],
        trip["infants"]
    )

    strategy = ai_price_strategy(trip, cards)

    return jsonify({
        "ai_enabled": bool(client),
        "trip": trip,
        "strategy": strategy,
        "cards": cards,
        "links": links
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "ai_enabled": bool(client)})


if __name__ == "__main__":
    app.run(debug=True)
