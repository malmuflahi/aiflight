let tripState = {};
let chatHistory = [];

const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatLog = document.getElementById("chatLog");
const notesList = document.getElementById("notesList");
const statusBox = document.getElementById("status");
const strategyBox = document.getElementById("strategy");
const resultsBox = document.getElementById("results");
const sendButton = document.getElementById("sendButton");
const tripOptionButtons = document.querySelectorAll("[data-trip-option]");
const quickDepartDate = document.getElementById("quickDepartDate");
const quickReturnDate = document.getElementById("quickReturnDate");
const quickReturnWrap = document.getElementById("quickReturnWrap");

let selectedTripType = "oneway";

function escapeHTML(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function safeURL(value) {
    const text = String(value || "");
    return text.startsWith("https://") ? text : "#";
}

function appendMessage(role, text, extraClass = "") {
    const message = document.createElement("div");
    message.className = `chat-message ${role} ${extraClass}`.trim();
    message.innerHTML = `<p>${escapeHTML(text)}</p>`;
    chatLog.appendChild(message);
    chatLog.scrollTop = chatLog.scrollHeight;
    return message;
}

function showStatus(text, isError = false) {
    statusBox.innerHTML = `<p class="${isError ? "status-error" : "status-msg"}">${escapeHTML(text)}</p>`;
}

function clearOutput() {
    strategyBox.innerHTML = "";
    resultsBox.innerHTML = "";
}

function labelValue(label, value) {
    return `
        <div class="note-row">
            <span>${escapeHTML(label)}</span>
            <strong>${escapeHTML(value || "Needed")}</strong>
        </div>
    `;
}

function passengerSummary(trip) {
    const adults = trip.adults ? `${trip.adults} adult(s)` : "";
    const children = trip.children ? `${trip.children} child(ren)` : "";
    const infants = trip.infants ? `${trip.infants} infant(s)` : "";
    return [adults, children, infants].filter(Boolean).join(", ");
}

function renderNotes(trip = {}) {
    const event = trip.event_context || {};
    const route = trip.origin && trip.destination ? `${trip.origin} -> ${trip.destination}` : "";
    const date = trip.depart_date || (trip.date_window ? `${trip.date_window}, exact date needed` : "");
    const tripType = trip.trip_type === "roundtrip" ? "Round trip" : trip.trip_type === "oneway" ? "One way" : "";
    const returnDate = trip.trip_type === "roundtrip" ? trip.return_date : "Not needed";
    const priority = trip.priority ? trip.priority.replace("_", " ") : "";
    const cabin = trip.cabin ? trip.cabin.replace("_", " ") : "Economy default";

    notesList.innerHTML = [
        labelValue("Event", event.match ? `${event.match}, ${event.date}` : "None"),
        labelValue("Route", route),
        labelValue("Departure", date),
        labelValue("Trip type", tripType),
        labelValue("Return", returnDate),
        labelValue("Passengers", passengerSummary(trip)),
        labelValue("Cabin", cabin),
        labelValue("Priority", priority || "Balanced if not specified")
    ].join("");
}

function setDateMinimums() {
    const today = new Date().toISOString().slice(0, 10);
    quickDepartDate.min = today;
    quickReturnDate.min = today;
}

function syncDatePickerToTripState() {
    tripState = {
        ...tripState,
        trip_type: selectedTripType
    };

    if (quickDepartDate.value) {
        tripState.depart_date = quickDepartDate.value;
    } else {
        delete tripState.depart_date;
    }

    if (selectedTripType === "roundtrip") {
        if (quickReturnDate.value) {
            tripState.return_date = quickReturnDate.value;
        } else {
            delete tripState.return_date;
        }
    } else {
        delete tripState.return_date;
    }

    renderNotes(tripState);
}

function setTripType(nextType) {
    selectedTripType = nextType;

    tripOptionButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.tripOption === nextType);
    });

    quickReturnWrap.classList.toggle("hidden", nextType !== "roundtrip");
    if (nextType !== "roundtrip") {
        quickReturnDate.value = "";
    }

    syncDatePickerToTripState();
}

function applyTripStateToDatePicker(trip = {}) {
    selectedTripType = trip.trip_type === "roundtrip" ? "roundtrip" : "oneway";

    tripOptionButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.tripOption === selectedTripType);
    });

    quickReturnWrap.classList.toggle("hidden", selectedTripType !== "roundtrip");
    quickDepartDate.value = trip.depart_date || "";
    quickReturnDate.value = selectedTripType === "roundtrip" ? (trip.return_date || "") : "";

    if (quickDepartDate.value) {
        quickReturnDate.min = quickDepartDate.value;
    }
}

tripOptionButtons.forEach(button => {
    button.addEventListener("click", () => setTripType(button.dataset.tripOption));
});

quickDepartDate.addEventListener("change", () => {
    if (quickDepartDate.value) {
        quickReturnDate.min = quickDepartDate.value;
        if (quickReturnDate.value && quickReturnDate.value < quickDepartDate.value) {
            quickReturnDate.value = "";
        }
    }
    syncDatePickerToTripState();
});

quickReturnDate.addEventListener("change", syncDatePickerToTripState);

function renderStrategy(data) {
    const trip = data.trip || {};
    strategyBox.innerHTML = `
        <div class="strategy-box">
            <h2>Best flight strategy</h2>
            <p>${escapeHTML(data.strategy || data.reply)}</p>
            <small>${escapeHTML(trip.origin)} -> ${escapeHTML(trip.destination)}</small>
        </div>
    `;
}

function renderResults(data) {
    const cards = data.cards || [];
    const links = data.links || {};

    resultsBox.innerHTML = cards.map((card, index) => `
        <article class="result-card ${index === 0 ? "featured" : ""}">
            ${index === 0 ? `<div class="ribbon">Best Pick</div>` : ""}

            <h2>${escapeHTML(card.title)}</h2>
            <p class="signal">${escapeHTML(card.signal)}</p>

            <div class="metrics">
                <div><strong>Status</strong><span>${escapeHTML(card.status)}</span></div>
                <div><strong>Goal</strong><span>${escapeHTML(card.goal)}</span></div>
                <div><strong>Risk</strong><span>${escapeHTML(card.risk)}</span></div>
            </div>

            <p class="explain">${escapeHTML(card.explanation)}</p>

            <div class="buttons">
                <a href="${safeURL(links.google)}" target="_blank" rel="noopener noreferrer">Google</a>
                <a href="${safeURL(links.kayak)}" target="_blank" rel="noopener noreferrer">Kayak</a>
                <a href="${safeURL(links.skyscanner)}" target="_blank" rel="noopener noreferrer">Skyscanner</a>
            </div>
        </article>
    `).join("");
}

async function sendChatMessage(message) {
    syncDatePickerToTripState();
    appendMessage("user", message);
    chatHistory.push({ role: "user", content: message });

    const typing = appendMessage("assistant", "Taking notes...", "typing");
    showStatus("AIFlight is reading the trip and checking what is missing.");
    clearOutput();
    sendButton.disabled = true;
    sendButton.textContent = "Thinking";

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                trip: tripState,
                history: chatHistory
            })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || "Request failed");
        }

        typing.remove();
        tripState = data.trip || tripState;
        applyTripStateToDatePicker(tripState);
        renderNotes(tripState);

        appendMessage("assistant", data.reply);
        chatHistory.push({ role: "assistant", content: data.reply });

        if (data.complete) {
            showStatus(data.offers && data.offers.length ? "Live prices found." : "Search complete, but no live fare was returned.");
            renderStrategy(data);
            renderResults(data);
        } else {
            showStatus("AIFlight is waiting for the missing trip details.");
        }
    } catch (error) {
        typing.remove();
        appendMessage("assistant", error.message || "Something went wrong. Try again.");
        showStatus(error.message || "Something went wrong. Try again.", true);
    } finally {
        sendButton.disabled = false;
        sendButton.textContent = "Send";
        chatInput.focus();
    }
}

chatForm.addEventListener("submit", async event => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    chatInput.value = "";
    await sendChatMessage(message);
});

setDateMinimums();
setTripType("oneway");
appendMessage("assistant", "Tell me the trip in your own words. I will turn it into a flight plan, ask only for what is missing, then show the best live price I can find.");
