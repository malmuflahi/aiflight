let passengers = {
    adults: 1,
    children: 0,
    infants: 0
};

document.querySelectorAll(".choice").forEach(button => {
    button.addEventListener("click", () => {
        const group = button.dataset.group;
        const value = button.dataset.value;

        document.querySelectorAll(`.choice[data-group="${group}"]`).forEach(btn => {
            btn.classList.remove("active");
        });

        button.classList.add("active");
        document.getElementById(group).value = value;

        if (group === "tripType") {
            document.getElementById("returnWrap").style.display = value === "roundtrip" ? "block" : "none";
        }
    });
});

document.querySelectorAll("[data-counter]").forEach(button => {
    button.addEventListener("click", () => {
        const key = button.dataset.counter;
        const action = button.dataset.action;

        if (action === "+") passengers[key]++;
        if (action === "-") passengers[key]--;

        if (key === "adults" && passengers[key] < 1) passengers[key] = 1;
        if (key !== "adults" && passengers[key] < 0) passengers[key] = 0;

        document.getElementById(`${key}Value`).textContent = passengers[key];
    });
});

document.getElementById("returnWrap").style.display = "none";

document.getElementById("searchForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const payload = {
        origin: document.getElementById("origin").value,
        destination: document.getElementById("destination").value,
        tripType: document.getElementById("tripType").value,
        departDate: document.getElementById("departDate").value,
        returnDate: document.getElementById("returnDate").value,
        adults: passengers.adults,
        children: passengers.children,
        infants: passengers.infants,
        priority: document.getElementById("priority").value,
        cabin: document.getElementById("cabin").value,
        seat: document.getElementById("seat").value,
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

    document.getElementById("status").innerHTML = "AI is building your price-defense strategy...";
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
