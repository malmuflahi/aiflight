document.getElementById("searchForm").addEventListener("submit", function(e) {
    e.preventDefault();

    const from = document.getElementById("from").value.toUpperCase();
    const to = document.getElementById("to").value.toUpperCase();
    const priority = document.getElementById("priority").value;

    const flights = [
        {
            title: "Best Overall Option",
            airline: "Comfort Airways",
            price: 650,
            time: "6h 30m",
            hours: 6.5,
            stops: "Nonstop",
            score: "94/100",
            explanation: "This is the best balance between price, travel time, and comfort. You save money while keeping the trip smooth and easy."
        },
        {
            title: "Cheapest Option",
            airline: "Budget Air",
            price: 550,
            time: "8h 20m",
            hours: 8.3,
            stops: "1 stop",
            score: "88/100",
            explanation: "This is the lowest price available. You save around $100 compared with the best overall option, but your trip is about 1 hour and 50 minutes longer."
        },
        {
            title: "Fastest Option",
            airline: "Direct Flight",
            price: 890,
            time: "5h 45m",
            hours: 5.75,
            stops: "Nonstop",
            score: "96/100",
            explanation: "This is the fastest route available. You arrive sooner with no stops, but it costs more. Best choice when time matters more than money."
        },
        {
            title: "Comfort Option",
            airline: "Premium Route",
            price: 720,
            time: "6h 10m",
            hours: 6.15,
            stops: "Nonstop",
            score: "91/100",
            explanation: "This option minimizes stops and long layovers, giving you a smoother and more comfortable journey."
        }
    ];

    let sorted = flights;

    if (priority === "cheapest") {
        sorted = [flights[1], flights[0], flights[3], flights[2]];
    } else if (priority === "fastest") {
        sorted = [flights[2], flights[3], flights[0], flights[1]];
    } else if (priority === "comfort") {
        sorted = [flights[3], flights[0], flights[2], flights[1]];
    } else {
        sorted = [flights[0], flights[1], flights[3], flights[2]];
    }

    const googleFlightsLink = `https://www.google.com/travel/flights?q=flights%20from%20${from}%20to%20${to}`;
    const expediaLink = `https://www.expedia.com/Flights-Search?trip=oneway&leg1=from:${from},to:${to}`;

    document.getElementById("results").innerHTML = sorted.map((flight, index) => `
        <div class="card">
            <div class="rank">#${index + 1}</div>
            <h2>${flight.title}</h2>

            <p><strong>Airline:</strong> ${flight.airline}</p>
            <p><strong>Route:</strong> ${from} → ${to}</p>
            <p><strong>Price:</strong> $${flight.price}</p>
            <p><strong>Travel Time:</strong> ${flight.time}</p>
            <p><strong>Stops:</strong> ${flight.stops}</p>
            <p><strong>AI Score:</strong> ${flight.score}</p>

            <div class="insight">
                <strong>AI Insight:</strong>
                <p>${flight.explanation}</p>
            </div>

            <div class="buttons">
                <a class="bookBtn" href="${googleFlightsLink}" target="_blank">Check on Google Flights</a>
                <a class="bookBtn secondary" href="${expediaLink}" target="_blank">Check / Buy Ticket</a>
            </div>
        </div>
    `).join("");
});
