const searchForm = document.getElementById("searchForm");
const tripType = document.getElementById("tripType");
const returnField = document.getElementById("returnField");
const swapBtn = document.getElementById("swapBtn");
const smartSearchBtn = document.getElementById("smartSearchBtn");
const smartQuery = document.getElementById("smartQuery");

function updateReturnField() {
    if (tripType.value === "oneway") {
        returnField.style.display = "none";
        document.getElementById("returnDate").value = "";
    } else {
        returnField.style.display = "block";
    }
}

tripType.addEventListener("change", updateReturnField);
updateReturnField();

swapBtn.addEventListener("click", function () {
    const origin = document.getElementById("origin");
    const destination = document.getElementById("destination");

    const temp = origin.value;
    origin.value = destination.value;
    destination.value = temp;
});

smartSearchBtn.addEventListener("click", function () {
    const text = smartQuery.value.trim();

    if (!text) {
        alert("Type a smart search like: New York to Cairo next month under $900");
        return;
    }

    document.getElementById("preference").value = text;
    document.querySelector(".search-card").scrollIntoView({ behavior: "smooth" });
});

searchForm.addEventListener("submit", async function (e) {
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

    document.body.classList.add("is-searching");

    document.getElementById("status").innerHTML = `
        <div class="scanning-box">
            <div class="radar"></div>
            <div>
                <h3>AI is scanning your route...</h3>
                <p>Checking timing, booking-site risk, route stress, and price-defense strategy.</p>
            </div>
        </div>
    `;

    document.getElementById("strategy").innerHTML = "";
    document.getElementById("results").innerHTML = "";

    try {
        const res = await fetch("/api/search", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        document.body.classList.remove("is-searching");

        document.getElementById("status").innerHTML = data.ai_enabled
            ? `<div class="success-status">AI price-defense strategy ready.</div>`
            : `<div class="success-status">Smart mode active. Add OPENAI_API_KEY for deeper AI strategy.</div>`;

        document.getElementById("strategy").innerHTML = `
            <div class="strategy-box">
                <div class="strategy-top">
                    <span>AI Insight</span>
                    <strong>${data.trip.origin} → ${data.trip.destination}</strong>
                </div>

                <h2>Buy smarter, not faster.</h2>
                <p>${data.strategy}</p>

                <div class="insight-grid">
                    <div>
                        <small>Confidence</small>
                        <b>High</b>
                    </div>
                    <div>
                        <small>Booking move</small>
                        <b>Compare first</b>
                    </div>
                    <div>
                        <small>Route risk</small>
                        <b>Medium</b>
                    </div>
                </div>
            </div>
        `;

        document.getElementById("bestPrice").textContent = "AI";
        document.getElementById("cheapPrice").textContent = "$";
        document.getElementById("fastPrice").textContent = "⚡";

        document.getElementById("results").innerHTML = data.cards.map((card, index) => `
            <div class="flight-card ${index === 0 ? "featured" : ""}">
                ${index === 0 ? `<div class="ribbon">Recommended first</div>` : ""}

                <div class="flight-card-head">
                    <div>
                        <h2>${card.title}</h2>
                        <p>${card.signal}</p>
                    </div>
                    <button class="heart-btn" type="button">♡</button>
                </div>

                <div class="flight-route">
                    <div>
                        <strong>${data.trip.origin}</strong>
                        <span>Origin</span>
                    </div>

                    <div class="route-line">
                        <span></span>
                        <b>✈</b>
                        <span></span>
                    </div>

                    <div>
                        <strong>${data.trip.destination}</strong>
                        <span>Destination</span>
                    </div>
                </div>

                <div class="metrics">
                    <div><strong>Status</strong><span>${card.status}</span></div>
                    <div><strong>Goal</strong><span>${card.goal}</span></div>
                    <div><strong>Risk</strong><span>${card.risk}</span></div>
                </div>

                <p class="explain">${card.explanation}</p>

                <div class="buttons">
                    <a href="${data.links.google}" target="_blank">Google Flights</a>
                    <a href="${data.links.kayak}" target="_blank">Kayak</a>
                    <a href="${data.links.skyscanner}" target="_blank">Skyscanner</a>
                </div>
            </div>
        `).join("");

    } catch (error) {
        document.body.classList.remove("is-searching");

        document.getElementById("status").innerHTML = `
            <div class="error-status">
                Something went wrong. Check your server and try again.
            </div>
        `;
    }
});
