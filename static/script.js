document.getElementById("searchForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const origin = document.getElementById("origin").value;
    const destination = document.getElementById("destination").value;
    const priority = document.getElementById("priority").value;
    const preference = document.getElementById("preference").value;

    document.getElementById("status").innerHTML = "AI is comparing your flight options...";
    document.getElementById("results").innerHTML = "";

    const response = await fetch("/api/search", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            origin,
            destination,
            priority,
            preference
        })
    });

    const data = await response.json();

    document.getElementById("status").innerHTML = data.ai_enabled
        ? "AI advice generated successfully."
        : "Demo AI mode. Add OPENAI_API_KEY in Render for real AI-generated advice.";

    document.getElementById("results").innerHTML = data.results.map((flight, index) => `
        <div class="card">
            <div class="top">
                <span class="rank">#${index + 1}</span>
                <span class="price">$${flight.price}</span>
            </div>

            <h2>${flight.title}</h2>

            <p><strong>Airline:</strong> ${flight.airline}</p>
            <p><strong>Route:</strong> ${data.origin} → ${data.destination}</p>
            <p><strong>Travel Time:</strong> ${flight.duration}</p>
            <p><strong>Stops:</strong> ${flight.stops === 0 ? "Nonstop" : flight.stops + " stop"}</p>
            <p><strong>Comfort:</strong> ${flight.comfort}</p>

            <div class="ai-box">
                <strong>AI Travel Advice</strong>
                <p>${flight.ai_advice}</p>
            </div>

            <div class="buttons">
                <a href="${flight.google_link}" target="_blank">Check on Google Flights</a>
                <a class="green" href="${flight.expedia_link}" target="_blank">Check / Buy Ticket</a>
            </div>
        </div>
    `).join("");
});
