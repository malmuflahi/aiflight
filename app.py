import os
import requests
from flask import Flask, render_template, request, jsonify
import openai

app = Flask(__name__)

# ✅ Load API key from Render (NOT hardcoded)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


@app.route("/")
def home():
    return render_template("index.html")


# ✅ Build booking links (Google Flights + Kayak)
def build_booking_links(origin, destination, trip_type, depart_date, return_date, adults):

    # Google Flights
    google = f"https://www.google.com/travel/flights?q=flights%20from%20{origin}%20to%20{destination}%20on%20{depart_date}"

    if trip_type == "round" and return_date:
        google += f"%20return%20{destination}%20to%20{origin}%20on%20{return_date}"

    # Kayak
    kayak = f"https://www.kayak.com/flights/{origin}-{destination}/{depart_date}"

    if trip_type == "round" and return_date:
        kayak += f"/{return_date}"

    return {
        "google": google,
        "kayak": kayak
    }


# ✅ Fake real-like flight generator (until API connected)
def generate_flights(origin, destination):
    return [
        {
            "airline": "Delta Airlines",
            "price": 420,
            "duration": "6h 20m",
            "stops": 0,
            "tag": "Fastest Option"
        },
        {
            "airline": "United Airlines",
            "price": 350,
            "duration": "8h 10m",
            "stops": 1,
            "tag": "Best Value"
        },
        {
            "airline": "JetBlue",
            "price": 290,
            "duration": "9h 30m",
            "stops": 1,
            "tag": "Cheapest Option"
        }
    ]


@app.route("/search", methods=["POST"])
def search():

    data = request.json

    origin = data.get("origin")
    destination = data.get("destination")
    depart_date = data.get("depart_date")
    return_date = data.get("return_date")
    trip_type = data.get("trip_type")  # one-way or round

    adults = int(data.get("adults", 1))
    kids = int(data.get("kids", 0))
    infants = int(data.get("infants", 0))

    # ✅ Generate flights (replace later with real API)
    flights = generate_flights(origin, destination)

    # ✅ Build booking links
    links = build_booking_links(origin, destination, trip_type, depart_date, return_date, adults)

    # ✅ AI explanation (SAFE)
    ai_text = "AI unavailable"

    if OPENAI_API_KEY:
        try:
            prompt = f"""
User trip:
From {origin} to {destination}
Depart: {depart_date}
Return: {return_date}
Passengers: {adults} adults, {kids} kids, {infants} infants

Flights:
{flights}

Explain:
- Best option
- Trade-offs
- Which one reduces stress
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )

            ai_text = response.choices[0].message.content

        except Exception as e:
            ai_text = f"AI error: {str(e)}"

    return jsonify({
        "flights": flights,
        "ai": ai_text,
        "links": links
    })


if __name__ == "__main__":
    app.run(debug=True)
