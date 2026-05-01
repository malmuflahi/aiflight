from flask import Flask, render_template, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


@app.route("/")
def home():
    return render_template("index.html")


def build_booking_links(origin, destination, trip_type, depart_date, return_date, adults, children, infants):
    google = (
        f"https://www.google.com/travel/flights?q=flights%20from%20{origin}%20to%20{destination}"
        f"%20on%20{depart_date}"
    )

    kayak = (
        f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"
    )

    skyscanner = (
        f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/{depart_date.replace('-', '')}/"
    )

    expedia = (
        f"https://www.expedia.com/Flights-Search?trip={trip_type}"
        f"&leg1=from:{origin},to:{destination},departure:{depart_date}TANYT"
        f"&passengers=adults:{adults},children:{children},infantinlap:{infants}"
        f"&options=cabinclass:economy&mode=search"
    )

    if trip_type == "roundtrip" and return_date:
        google += f"%20return%20{return_date}"
        kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}/{return_date}"
        skyscanner = (
            f"https://www.skyscanner.com/transport/flights/{origin.lower()}/{destination.lower()}/"
            f"{depart_date.replace('-', '')}/{return_date.replace('-', '')}/"
        )
        expedia = (
            f"https://www.expedia.com/Flights-Search?trip=roundtrip"
            f"&leg1=from:{origin},to:{destination},departure:{depart_date}TANYT"
            f"&leg2=from:{destination},to:{origin},departure:{return_date}TANYT"
            f"&passengers=adults:{adults},children:{children},infantinlap:{infants}"
            f"&options=cabinclass:economy&mode=search"
        )

    return {
        "google": google,
        "kayak": kayak,
        "skyscanner": skyscanner,
        "expedia": expedia
    }


def generate_smart_options(priority):
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
        extra_time = round(option["hours"] - fastest["hours"], 1)
        savings = fastest["price"] - option["price"]
        return f"You save about ${savings} by choosing this option, but your trip is about {extra_time} hours longer. This is best if price matters more than speed."

    if option["type"] == "fast":
        extra_cost = option["price"] - cheapest["price"]
        time_saved = round(cheapest["hours"] - option["hours"], 1)
        return f"You pay about ${extra_cost} more, but you save around {time_saved} hours and avoid extra travel stress. Best if time matters most."

    if option["type"] == "comfort":
        return "This option is designed to reduce travel stress. It avoids extra stops and keeps the schedule smoother."

    return "This is the best balance between price, time, and comfort. It helps you avoid overpaying while still keeping the trip smooth."


def ai_advice(option, options, data):
    if not client:
        return fallback_advice(option, options)

    prompt = f"""
You are AIFLight, a premium AI travel advisor.

User trip:
From: {data["origin"]}
To: {data["destination"]}
Trip type: {data["trip_type"]}
Departure: {data["depart_date"]}
Return: {data["return_date"]}
Adults: {data["adults"]}
Children: {data["children"]}
Infants: {data["infants"]}
Preference: {data["preference"]}

Option:
{option}

All options:
{options}

Write a short, confident explanation.
Focus on what the traveler gains and what they trade off.
Mention savings, time saved, stress, stops, and confidence.
Do not say this is fake or demo.
Do not sound robotic.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a premium travel decision assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=110,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback_advice(option, options)


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    trip_data = {
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

    options = generate_smart_options(trip_data["priority"])

    links = build_booking_links(
        trip_data["origin"],
        trip_data["destination"],
        trip_data["trip_type"],
        trip_data["depart_date"],
        trip_data["return_date"],
        trip_data["adults"],
        trip_data["children"],
        trip_data["infants"]
    )

    results = []
    for option in options:
        option["advice"] = ai_advice(option, options, trip_data)
        option["links"] = links
        results.append(option)

    return jsonify({
        "ai_enabled": bool(client),
        "trip": trip_data,
        "results": results
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "ai_enabled": bool(client)})


if __name__ == "__main__":
    app.run(debug=True)
