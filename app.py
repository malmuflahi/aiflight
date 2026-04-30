from flask import Flask, render_template, request, jsonify
import os
import requests
from datetime import datetime

app = Flask(__name__)

AMADEUS_CLIENT_ID = os.getenv("AMADEUS_CLIENT_ID", "")
AMADEUS_CLIENT_SECRET = os.getenv("AMADEUS_CLIENT_SECRET", "")
AMADEUS_BASE_URL = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")

def get_amadeus_token():
    if not AMADEUS_CLIENT_ID or not AMADEUS_CLIENT_SECRET:
        return None

    url = f"{AMADEUS_BASE_URL}/v1/security/oauth2/token"
    response = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_CLIENT_ID,
            "client_secret": AMADEUS_CLIENT_SECRET,
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()["access_token"]

def demo_results(origin, destination, depart_date, adults, cabin):
    return [
        {
            "airline": "AIA Demo Air",
            "price": 548,
            "currency": "USD",
            "duration": "18h 15m",
            "stops": 2,
            "departure": f"{depart_date} 21:30",
            "arrival": f"{depart_date} +1 day 22:45",
            "cabin": cabin,
            "booking_note": "Demo result. Connect Amadeus API keys for live prices.",
        },
        {
            "airline": "AIA Direct",
            "price": 790,
            "currency": "USD",
            "duration": "10h 55m",
            "stops": 0,
            "departure": f"{depart_date} 11:15",
            "arrival": f"{depart_date} 22:10",
            "cabin": cabin,
            "booking_note": "Fastest demo result.",
        },
        {
            "airline": "AIA Comfort",
            "price": 615,
            "currency": "USD",
            "duration": "12h 40m",
            "stops": 1,
            "departure": f"{depart_date} 08:45",
            "arrival": f"{depart_date} 23:25",
            "cabin": cabin,
            "booking_note": "Best balance demo result.",
        },
    ]

def parse_duration_hours(duration):
    # Handles simple demo strings and Amadeus ISO durations roughly.
    if not duration:
        return 99
    d = duration.upper().replace("PT", "")
    hours = 0
    minutes = 0
    if "H" in d:
        try:
            hours = int(d.split("H")[0].split()[-1])
        except Exception:
            hours = 0
    if "M" in d:
        try:
            minutes_part = d.split("H")[-1].replace("M", "").strip()
            minutes = int(minutes_part) if minutes_part.isdigit() else 0
        except Exception:
            minutes = 0
    if "h" in duration.lower():
        try:
            hours = int(duration.lower().split("h")[0])
        except Exception:
            pass
    return hours + minutes / 60

def rank_results(flights, priority):
    ranked = []
    for flight in flights:
        hours = parse_duration_hours(str(flight.get("duration", "")))
        price = float(flight.get("price", 9999))
        stops = int(flight.get("stops", 0))

        score = 100
        score -= price / 35
        score -= stops * 12
        score -= hours * 1.2

        if priority == "cheapest":
            score -= price / 25
        elif priority == "fastest":
            score -= hours * 4
            score -= stops * 10
        elif priority == "comfort":
            score -= stops * 22
            if stops == 0:
                score += 18
        else:
            if stops <= 1:
                score += 8
            if price < 700:
                score += 8

        flight["ai_score"] = max(1, round(score))
        if priority == "cheapest":
            flight["ai_reason"] = "Ranked high because it keeps the price low compared with the other options."
        elif priority == "fastest":
            flight["ai_reason"] = "Ranked high because it reduces travel time and avoids unnecessary stops."
        elif priority == "comfort":
            flight["ai_reason"] = "Ranked high because it focuses on fewer stops and a smoother trip."
        else:
            flight["ai_reason"] = "Ranked high because it balances price, time, and stop count."

        ranked.append(flight)

    ranked.sort(key=lambda x: x["ai_score"], reverse=True)
    return ranked[:6]

def live_amadeus_search(origin, destination, depart_date, adults, cabin):
    token = get_amadeus_token()
    if not token:
        return None

    url = f"{AMADEUS_BASE_URL}/v2/shopping/flight-offers"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": origin.upper(),
        "destinationLocationCode": destination.upper(),
        "departureDate": depart_date,
        "adults": adults,
        "currencyCode": "USD",
        "travelClass": cabin.upper(),
        "max": 20,
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    flights = []
    for offer in payload.get("data", []):
        itinerary = offer.get("itineraries", [{}])[0]
        segments = itinerary.get("segments", [])
        if not segments:
            continue

        first = segments[0]
        last = segments[-1]
        carrier = first.get("carrierCode", "Airline")
        price = float(offer.get("price", {}).get("grandTotal", 0))

        flights.append({
            "airline": carrier,
            "price": price,
            "currency": offer.get("price", {}).get("currency", "USD"),
            "duration": itinerary.get("duration", "N/A"),
            "stops": max(0, len(segments) - 1),
            "departure": first.get("departure", {}).get("at", ""),
            "arrival": last.get("arrival", {}).get("at", ""),
            "cabin": cabin,
            "booking_note": "Live Amadeus search result. Booking requires additional approved API flow.",
        })

    return flights

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/search", methods=["POST"])
def search():
    data = request.get_json(force=True)

    origin = data.get("origin", "NYC").strip().upper()
    destination = data.get("destination", "DXB").strip().upper()
    depart_date = data.get("depart_date", "").strip()
    adults = int(data.get("adults", 1))
    priority = data.get("priority", "balanced")
    cabin = data.get("cabin", "ECONOMY")

    if not depart_date:
        return jsonify({"error": "Departure date is required."}), 400

    try:
        flights = live_amadeus_search(origin, destination, depart_date, adults, cabin)
        mode = "live"
        if not flights:
            flights = demo_results(origin, destination, depart_date, adults, cabin)
            mode = "demo"
    except Exception as exc:
        flights = demo_results(origin, destination, depart_date, adults, cabin)
        mode = "demo_fallback"

    ranked = rank_results(flights, priority)
    return jsonify({
        "brand": "AIAirplane.com",
        "mode": mode,
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
        "results": ranked
    })

@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "brand": "AIAirplane.com",
        "amadeus_keys_detected": bool(AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET)
    })

if __name__ == "__main__":
    app.run(debug=True)