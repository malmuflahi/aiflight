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
        alert("Choose a departure date.");
        return;
    }

    if (payload.tripType === "roundtrip" && !payload.returnDate) {
        alert("Choose a return date.");
        return;
    }

    document.getElementById("status").innerHTML = "AI is scanning the best price-defense strategy...";
    document.getElementById("strategy").innerHTML = "";
    document.getElementById("results").innerHTML = "";

    const res = await fetch("/api/search", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    document.getElementById("status").innerHTML = data.ai_enabled
        ? "AI price-defense strategy ready."
        : "Smart mode active. Add OPENAI_API_KEY for deeper AI strategy.";

    document.getElementById("strategy").innerHTML = `
        <div class="strategy-box">
            <h2>AI Price Defense Plan</h2>
            <p>${data.strategy}</p>
            <small>Route normalized: ${data.trip.origin} → ${data.trip.destination}</small>
        </div>
    `;

    document.getElementById("results").innerHTML = data.cards.map((card, index) => `
        <div class="card ${index === 0 ? "featured" : ""}">
            ${index === 0 ? `<div class="ribbon">Recommended first</div>` : ""}
            <h2>${card.title}</h2>
            <p class="signal">${card.signal}</p>

            <div class="metrics">
                <div><strong>Status</strong><span>${card.status}</span></div>
                <div><strong>Goal</strong><span>${card.goal}</span></div>
                <div><strong>Risk</strong><span>${card.risk}</span></div>
            </div>

            <p class="explain">${card.explanation}</p>

            <div class="buttons">
                <a href="${data.links.google}" target="_blank">Search Google Flights</a>
                <a href="${data.links.kayak}" target="_blank">Search Kayak</a>
                <a href="${data.links.skyscanner}" target="_blank">Search Skyscanner</a>
            </div>
        </div>
    `).join("");
});
