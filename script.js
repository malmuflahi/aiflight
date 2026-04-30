const form = document.getElementById("flightForm");
const results = document.getElementById("results");
const statusBox = document.getElementById("status");
const alertForm = document.getElementById("alertForm");
const alertMessage = document.getElementById("alertMessage");

const defaultDate = new Date();
defaultDate.setDate(defaultDate.getDate() + 21);
document.getElementById("depart_date").value = defaultDate.toISOString().split("T")[0];

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  results.innerHTML = "";
  statusBox.textContent = "AIAirplane is searching and ranking flights...";

  const payload = {
    origin: document.getElementById("origin").value,
    destination: document.getElementById("destination").value,
    depart_date: document.getElementById("depart_date").value,
    adults: document.getElementById("adults").value,
    priority: document.getElementById("priority").value,
    cabin: document.getElementById("cabin").value
  };

  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      statusBox.textContent = data.error || "Search failed.";
      return;
    }

    const label = data.mode === "live"
      ? "Live flight results"
      : "Demo mode — add API keys for live airline data";

    statusBox.textContent = `${label}: ${data.origin} → ${data.destination}`;

    results.innerHTML = data.results.map((flight, index) => `
      <article>
        <div class="flightTop">
          <div>
            <h3>#${index + 1} ${flight.airline}</h3>
            <span class="score">AI score ${flight.ai_score}/100</span>
          </div>
          <p class="flightPrice">$${Number(flight.price).toFixed(0)}</p>
        </div>
        <p><strong>${flight.duration}</strong> • ${flight.stops} stop(s) • ${flight.cabin}</p>
        <p class="muted">${flight.departure} → ${flight.arrival}</p>
        <p class="muted">${flight.ai_reason}</p>
        <p class="muted">${flight.booking_note}</p>
      </article>
    `).join("");

  } catch (error) {
    statusBox.textContent = "Website is running, but backend search failed: " + error.message;
  }
});

alertForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value;
  const target = document.getElementById("target").value;
  alertMessage.textContent = `Demo alert saved for ${email}. Target price: $${target}.`;
});