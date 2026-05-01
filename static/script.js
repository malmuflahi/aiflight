document.getElementById("searchForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const payload = {
        origin: document.getElementById("origin").value,
        destination: document.getElementById("destination").value,
        tripType: document.getElementById("tripType").value,
        departDate: document.getElementById("departDate").value,
        returnDate: document.getElementById("returnDate").value,
        adults: document.getElementById("adults").value,
        children: document.getElementById("children").value,
        infants: document.getElementById("infants").value,
        priority: document.getElementById("priority").value,
        preference: document.getElementById("preference").value
    };

    if (!payload.departDate) {
        alert("Please choose a departure date.");
        return;
    }

    if (payload.tripType === "roundtrip" && !payload.returnDate) {
        alert("Please choose a return date.");
        return;
    }

    document.getElementById("status").innerHTML = "AIFLight is comparing value, time, and stress...";
    document.getElementById("results").innerHTML = "";

    const response = await fetch("/api/search", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await response.json();

    document.getElementById("status").innerHTML = data.ai_enabled
        ? "Smart recommendations ready."
        : "Smart demo mode active. Add OPENAI_API_KEY for fully dynamic AI advice.";

    document.getElementById("results").innerHTML = data.results.map((flight, index) => `
        <div class="card ${index === 0 ? "recommended" : ""}">
            ${index === 0 ? `<div class="recommended-badge">Recommended for you</div>` : ""}

            <div class="card-top">
                <span class="rank">#${index + 1}</span>
                <span class="price">$${flight.price}</span>
            </div>

            <h2>${flight.title}</h2>
            <p class="badge-line">${flight.badge}</p>

            <div class="details">
                <p><strong>Airline:</strong> ${flight.airline}</p>
                <p><strong>Route:</strong> ${data.trip.origin} → ${data.trip.destination}</p>
                <p><strong>Trip:</strong> ${data.trip.trip_type === "roundtrip" ? "Round trip" : "One way"}</p>
                <p><strong>Departure:</strong> ${data.trip.depart_date}</p>
                ${data.trip.trip_type === "roundtrip" ? `<p><strong>Return:</strong> ${data.trip.return_date}</p>` : ""}
                <p><strong>Passengers:</strong> ${data.trip.adults} adult(s), ${data.trip.children} child(ren), ${data.trip.infants} infant(s)</p>
                <p><strong>Travel time:</strong> ${flight.duration}</p>
                <p><strong>Stops:</strong> ${flight.stops === 0 ? "Nonstop" : flight.stops + " stop"}</p>
                <p><strong>Stress level:</strong> ${flight.stress}</p>
            </div>

            <div class="advice-box">
                <strong>What you gain & trade off</strong>
                <p>${flight.advice}</p>
            </div>

            <div class="buttons">
                <a href="${flight.links.google}" target="_blank">View on Google Flights</a>
                <a href="${flight.links.kayak}" target="_blank">View on Kayak</a>
                <a href="${flight.links.skyscanner}" target="_blank">View on Skyscanner</a>
                <a class="green" href="${flight.links.expedia}" target="_blank">Check / Buy Ticket</a>
            </div>
        </div>
    `).join("");
});
