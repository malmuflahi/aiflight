let state = {
    passengers: { adults: 1, children: 0, infants: 0 }
};

const returnWrap = document.getElementById("returnWrap");
const returnDate = document.getElementById("returnDate");

document.querySelectorAll(".choice").forEach(btn => {
    btn.onclick = () => {
        const { group, value } = btn.dataset;

        document.querySelectorAll(`[data-group="${group}"]`)
            .forEach(b => b.classList.remove("active"));

        btn.classList.add("active");

        document.getElementById(group).value = value;

        if (group === "tripType") {
            returnWrap.style.display = value === "roundtrip" ? "block" : "none";
            if (value !== "roundtrip") returnDate.value = "";
        }
    };
});

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

        document.getElementById(counter+"Value").textContent = next[counter];
    };
});
