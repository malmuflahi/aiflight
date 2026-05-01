from flask import Flask, render_template, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


@app.route("/")
def home():
    return render_template("index.html")


def demo_flights(origin, destination):
    return [
        {
            "title": "Best Overall",
            "airline": "Comfort Airways",
            "price": 650,
            "duration": "6h 30m",
            "hours": 6.5,
            "stops": 0,
            "comfort": "High",
        },
        {
            "title": "Cheapest",
            "airline": "Budget Air",
            "price": 550,
            "duration": "8h 20m",
            "hours": 8.3,
            "stops": 1,
            "comfort": "Medium",
        },
        {
            "title": "Fastest",
            "airline": "Direct Flight",
            "price": 890,
            "duration": "5h 45m",
            "hours": 5.75,
            "stops": 0,
            "comfort": "High",
        },
        {
            "title": "Comfort Pick",
            "airline": "Premium Route",
            "price": 720,
            "duration": "6h 10m",
            "hours": 6.15,
            "stops": 0,
            "comfort": "Very High",
        },
    ]


def fallback_ai_advice(flight, flights, user_preference):
    cheapest = min(flights, key=lambda x: x["price"])
    fastest = min(flights, key=lambda x: x["hours"])

    save_vs_fastest = fastest["price"] - flight["price"]
    time_extra = round(flight["hours"] - fastest["hours"], 1)

    if flight["title"] == "Cheapest":
        return f"You save about ${save_vs_fastest} compared with the fastest option, but the trip takes around {time_extra} more hours. Good choice if saving money matters more than arriving early."

    if flight["title"] == "Fastest":
        return f"This is the fastest option and avoids wasted travel time. It costs more, but it is the best choice if time matters more than money."

    if flight["title"] == "Comfort Pick":
        return "This option focuses on a smoother trip with fewer stops and better comfort. It is a strong choice if you want less stress during travel."

    return "This is the best balance between price, time, and comfort. It gives you a smart middle ground without overpaying."


def get_ai_advice(origin, destination, flight, flights, user_preference):
    if not client:
        return fallback_ai_advice(flight, flights, user_preference)

    prompt = f"""
You are AIFLight, a professional AI travel advisor.

Route: {origin} to {destination}
Customer preference: {user_preference}

Flight option:
{flight}

All flight options:
{flights}

Write one short helpful explanation.
Compare price, time, stops, and value.
Use natural English.
Do not sound robotic.
Example style:
"You can save $120 by taking a flight that is only 1 hour longer."
or
"Paying $90 more saves you 2 hours and avoids a layover."
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a smart, honest, professional travel advisor."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=90,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return fallback_ai_advice(flight, flights, user_preference)


@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    origin = data.get("origin", "JFK").upper().strip()
    destination = data.get("destination", "LAX").upper().strip()
    user_preference = data.get("preference", "Best overall flight").strip()
    priority = data.get("priority", "balanced")

    flights = demo_flights(origin, destination)

    if priority == "cheapest":
        flights = sorted(flights, key=lambda x: x["price"])
    elif priority == "fastest":
        flights = sorted(flights, key=lambda x: x["hours"])
    elif priority == "comfort":
        flights = sorted(flights, key=lambda x: (x["stops"], -x["price"]))
    else:
        flights = sorted(flights, key=lambda x: abs(x["price"] - 650) + x["hours"] * 20)

    google_link = f"https://www.google.com/travel/flights?q=flights%20from%20{origin}%20to%20{destination}"
    expedia_link = f"https://www.expedia.com/Flights-Search?trip=oneway&leg1=from:{origin},to:{destination}"

    results = []
    for flight in flights:
        flight["ai_advice"] = get_ai_advice(origin, destination, flight, flights, user_preference)
        flight["google_link"] = google_link
        flight["expedia_link"] = expedia_link
        results.append(flight)

    return jsonify({
        "origin": origin,
        "destination": destination,
        "results": results,
        "ai_enabled": bool(client)
    })


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "ai_enabled": bool(client)})


if __name__ == "__main__":
    app.run(debug=True)
