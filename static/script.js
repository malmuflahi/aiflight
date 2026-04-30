document.getElementById("searchForm").addEventListener("submit", function(e) {
    e.preventDefault();

    let from = document.getElementById("from").value;
    let to = document.getElementById("to").value;

    let result = `
        <h2>Best flight</h2>
        <p>${from} → ${to}</p>
        <p>Price: $550</p>
        <p>AI Score: 92/100</p>
    `;

    document.getElementById("results").innerHTML = result;
});
