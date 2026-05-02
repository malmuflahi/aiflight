let state = {
    passengers: { adults: 1, children: 0, infants: 0 }
};

const form = document.getElementById("searchForm");
const returnWrap = document.getElementById("returnWrap");
const returnDate = document.getElementById("returnDate");
const statusBox = document.getElementById("status");
const strategyBox = document.getElementById("strategy");
const resultsBox = document.getElementById("results");
const button = document.querySelector(".primary-action");

// ---------- Choice Buttons ----------
document.querySelectorAll(".choice").forEach(btn => {
    btn.onclick = () => {
        const { group, value } = btn.dataset;

        document.querySelectorAll(`[data-group="${group}"]`)
            .forEach(b => b.classList.remove("active"));

        btn.classList.add("active");

        const hidden = document.getElementById(group);
        if (hidden) hidden.value = value;

        if (group === "tripType") {
            returnWrap.style.display = value === "roundtrip" ? "block" : "none";
            if (value !== "roundtrip") returnDate.value = "";
        }
    };
});

// ---------- Passenger Counters ----------
document.querySelectorAll("[data-counter]").forEach(btn => {
    btn.onclick = () => {
        const { counter, action } = btn.dataset;
        let next = { ...state.passengers };

        if (action === "+") next[counter]++;
        if (action === "-") next[counter]--;

        if (counter === "adults" && next[counter] < 1) next[counter] = 1;
        if (counter !== "adults" && next[counter] < 0) next[counter] = 0;

        const total = Object.values(next).reduce((a,b)=>a+b,0);
        if (total > 9) return alert("Max 9 passengers");

        state.passengers = next;
        document.getElementById(counter + "Value").textContent = next[counter];
    };
});

// ---------- Helpers ----------
function showStatus(text) {
    statusBox.innerHTML = `<p class="status-msg">${text}</p>`;
}

function showError(text) {
    statusBox.innerHTML = `<p class="status-error">${text}</p>`;
}

// ---------- Submit (THIS FIXES YOUR ISSUE) ----------
form.addEventListener("submit", async function(e) {
    e.preventDefault(); // 🚨 THIS STOPS PAGE REFRESH

    console.log("Submitting search...");

    const payload = {
        origin: document.getElementById("origin").value.trim(),
        destination: document.getElementById("destination").value.trim(),
        tripType: document.getElementById("tripType").value,
        departDate: document.getElementById("departDate").value,
        returnDate: document.getElementById("returnDate").value,
        adults: state.passengers.adults,
        children: state.passengers.children,
        infants: state.passengers.infants,
        priority: document.getElementById("priority").value,
        cabin: document.getElementById("cabin").value,
        seat: document.getElementById("seat").value,
        preference: document.getElementById("preference").value
    };

    showStatus("Analyzing route and defending your fare...");
    strategyBox.innerHTML = "";
    resultsBox.innerHTML = "";

    button.disabled = true;
    button.textContent = "Defending...";

    try {
        const res = await fetch("/api/search", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Request failed");

        const data = await res.json();

        showStatus("Strategy ready.");

        // ---------- Strategy ----------
        strategyBox.innerHTML = `
            <div class="strategy-box">
                <h2>Recommended strategy</h2>
                <p>${data.strategy}</p>
                <small>${data.trip.origin} → ${data.trip.destination}</small>
            </div>
        `;

        // ---------- Results ----------
        resultsBox.innerHTML = data.cards.map((card, i) => `
            <article class="result-card ${i === 0 ? "featured" : ""}">
                ${i === 0 ? `<div class="ribbon">Recommended</div>` : ""}
                
                <h2>${card.title}</h2>
                <p class="signal">${card.signal}</p>

                <div class="metrics">
                    <div><strong>Status</strong><span>${card.status}</span></div>
                    <div><strong>Goal</strong><span>${card.goal}</span></div>
                    <div><strong>Risk</strong><span>${card.risk}</span></div>
                </div>

                <p class="explain">${card.explanation}</p>

                <div class="buttons">
                    <a href="${data.links.google}" target="_blank">Google</a>
                    <a href="${data.links.kayak}" target="_blank">Kayak</a>
                    <a href="${data.links.skyscanner}" target="_blank">Skyscanner</a>
                </div>
            </article>
        `).join("");

    } catch (err) {
        console.error(err);
        showError("Something went wrong. Try again.");
    } finally {
        button.disabled = false;
        button.textContent = "Defend My Fare";
    }
});
