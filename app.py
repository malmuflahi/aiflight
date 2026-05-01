import os
from flask import Flask, render_template, request, jsonify
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


@app.route("/")
def home():
    return render_template("index.html")


def build_booking_links(origin, destination, trip_type, depart_date, return_date, adults, children, infants):
    google = f"https://www.google.com/travel/flights?q=flights%20from%20{origin}%20to%20{destination}%20on%20{depart_date}"
    kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"
    skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/"

    if trip_type == "roundtrip" and return_date:
        google += f"%20return%20{return_date}"
        kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}/{return_date}"
        skyscanner = f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/{return_date.replace('-', '')}/"

    return {
        "google": google,
        "kayak": kayak,
        "skyscanner": skyscanner
    }


def generate_options(priority):
    options = [
        {
            "title": "Best Value",
            "badge": "Recommended for you",
            "airline": "Smart Pick",
            "price": 650,
            "duration": "6h 30m",
            "hours": 6.5,
            "stops": 0,
            "stress": "Low",
            "type": "best"
        },
        {
            "title": "Cheapest Option",
            "badge": "Save the most",
            "airline": "Budget Route",
            "price": 550,
            "duration": "8h 20m",
            "hours": 8.3,
            "stops": 1,
            "stress": "Medium",
            "type": "cheap"
        },
        {
            "title": "Fastest Option",
            "badge": "Fastest arrival",
            "airline": "Direct Route",
            "price": 890,
            "duration": "5h 45m",
            "hours": 5.75,
            "stops": 0,
            "stress": "Low",
            "type": "fast"
        },
        {
            "title": "Least Stress",
            "badge": "Comfort pick",
            "airline": "Comfort Route",
            "price": 720,
            "duration": "6h 10m",
            "hours": 6.15,
            "stops": 0,
            "stress": "Very Low",
            "type": "comfort"
        }
    ]

    if priority == "cheapest":
        return sorted(options, key=lambda x: x["price"])
    if priority == "fastest":
        return sorted(options, key=lambda x: x["hours"])
    if priority == "comfort":
        return sorted(options, key=lambda x: (x["stops"], x["hours"]))
    return options


def fallback_advice(option, options):
    cheapest = min(options, key=lambda x: x["price"])
    fastest = min(options, key=lambda x: x["hours"])

    if option["type"] == "cheap":
        savings = fastest["price"] - option["price"]
        extra_time = round(option["hours"] - fastest["hours"], 1)
        return f"You save about ${savings}, but your trip is about {extra_time} hours longer. This is best if price matters more than speed."

    if option["type"] == "fast":
        extra_cost = option["price"] - cheapest["price"]
        time_saved = round(cheapest["hours"] - option["hours"], 1)
        return f"You pay about ${extra_cost} more, but you save around {time_saved} hours and avoid extra travel stress."

    if option["type"] == "comfort":
        return "This option reduces travel stress with no stops and a smoother schedule."

    return "This is the best balance between price, time, and comfort. It helps you avoid overpaying while keeping the trip smooth."


def ai_advice(option, options, trip):
    if not client:
        return fallback_advice(option, options)

    prompt = f"""
You are AIFLight, a premium AI travel advisor.

Trip:
From: {trip["origin"]}
To: {trip["destination"]}
Trip type: {trip["trip_type"]}
Departure: {trip["depart_date"]}
Return: {trip["return_date"]}
Adults: {trip["adults"]}
Children: {trip["children"]}
Infants: {trip["infants"]}
Preference: {trip["preference"]}

Flight option:
{option}

All options:
{options}

Write a short, confident explanation.
Explain what the traveler gains and what they trade off.
Mention savings, time saved, stops, comfort, and stress.
Do not say demo or fake.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a smart premium travel decision assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=120,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback_advice(option, options)


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    trip = {
        "origin": data.get("origin", "JFK").upper().strip(),
        "destination": data.get("destination", "LAX").upper().strip(),
        "trip_type": data.get("tripType", "oneway"),
        "depart_date": data.get("departDate", ""),
        "return_date": data.get("returnDate", ""),
        "adults": int(data.get("adults", 1)),
        "children": int(data.get("children", 0)),
        "infants": int(data.get("infants", 0)),
        "priority": data.get("priority", "balanced"),
        "preference": data.get("preference", "")
    }

    options = generate_options(trip["priority"])

    links = build_booking_links(
        trip["origin"],
        trip["destination"],
        trip["trip_type"],
        trip["depart_date"],
        trip["return_date"],
        trip["adults"],
        trip["children"],
        trip["infants"]
    )

    results = []
    for option in options:
        option["advice"] = ai_advice(option, options, trip)
        option["links"] = links
        results.append(option)

    return jsonify({
        "ai_enabled": bool(client),
        "trip": trip,
        "results": results
    })


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": bool(client)
    })


if __name__ == "__main__":
    app.run(debug=True)
