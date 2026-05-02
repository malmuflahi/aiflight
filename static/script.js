* { box-sizing: border-box; }

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f5fbff;
    color: #0f172a;
}

.hero {
    background:
        radial-gradient(circle at top right, #38bdf8, transparent 35%),
        linear-gradient(135deg, #020617, #082f49);
    color: white;
    padding: 34px 22px 70px;
}

nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 44px;
}

.logo {
    font-size: 30px;
    font-weight: 900;
}

.pill {
    background: rgba(255,255,255,.14);
    border: 1px solid rgba(255,255,255,.25);
    padding: 9px 13px;
    border-radius: 999px;
    font-weight: 800;
    font-size: 13px;
}

h1 {
    font-size: 48px;
    line-height: .95;
    margin: 0 0 18px;
    letter-spacing: -1.5px;
}

.hero p {
    font-size: 18px;
    line-height: 1.6;
    color: #dbeafe;
}

main {
    max-width: 1120px;
    margin: auto;
}

.search-card {
    background: white;
    margin: -38px 18px 24px;
    padding: 26px;
    border-radius: 32px;
    box-shadow: 0 30px 70px rgba(2, 132, 199, .20);
}

.search-card h2 {
    font-size: 32px;
    margin-bottom: 6px;
    color: #082f49;
}

.helper, .small-note {
    color: #64748b;
}

form {
    display: grid;
    gap: 20px;
}

.grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 14px;
}

input, select, textarea {
    width: 100%;
    margin-top: 6px;
    padding: 16px;
    border-radius: 18px;
    border: 1px solid #cbd5e1;
    font-size: 16px;
}

textarea {
    min-height: 98px;
}

.choice-section {
    display: grid;
    gap: 12px;
}

.choice-section h3 {
    margin: 0;
    font-size: 22px;
    color: #082f49;
}

.choice-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 12px;
}

.choice {
    border: 2px solid #dbeafe;
    background: white;
    color: #082f49;
    border-radius: 22px;
    padding: 20px;
    font-size: 18px;
    font-weight: 900;
    text-align: left;
    box-shadow: 0 10px 25px rgba(15, 23, 42, .05);
}

.choice.big {
    min-height: 112px;
}

.choice span {
    display: block;
    margin-top: 8px;
    color: #64748b;
    font-size: 14px;
    font-weight: 700;
}

.choice.active {
    border-color: #0ea5e9;
    background: linear-gradient(135deg, #e0f2fe, #ffffff);
    box-shadow: 0 18px 35px rgba(14, 165, 233, .18);
}

.passenger-grid {
    display: grid;
    gap: 12px;
}

.counter {
    border: 1px solid #dbeafe;
    border-radius: 22px;
    padding: 18px;
    background: #f8fbff;
}

.counter span {
    display: block;
    font-weight: 900;
    margin-bottom: 12px;
    color: #082f49;
}

.counter div {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.counter button {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    border: none;
    background: #0ea5e9;
    color: white;
    font-size: 24px;
    font-weight: 900;
}

.counter strong {
    font-size: 24px;
}

.submit-btn {
    background: linear-gradient(135deg, #0284c7, #38bdf8);
    color: white;
    border: none;
    border-radius: 20px;
    padding: 18px;
    font-size: 18px;
    font-weight: 900;
    box-shadow: 0 20px 35px rgba(14, 165, 233, .25);
}

#status {
    margin: 22px 18px;
    font-weight: 900;
    color: #0369a1;
}

.strategy-box {
    margin: 0 18px 24px;
    background: #082f49;
    color: white;
    border-radius: 28px;
    padding: 24px;
    box-shadow: 0 20px 45px rgba(15, 23, 42, .18);
}

.strategy-box p {
    color: #dbeafe;
    line-height: 1.7;
}

.strategy-box small {
    color: #7dd3fc;
    font-weight: 800;
}

.results {
    display: grid;
    gap: 20px;
    padding: 0 18px 50px;
}

.card {
    background: white;
    border: 1px solid #dbeafe;
    border-radius: 28px;
    padding: 24px;
    box-shadow: 0 18px 45px rgba(15, 23, 42, .08);
}

.card.featured {
    border: 2px solid #0ea5e9;
}

.ribbon {
    display: inline-block;
    background: #0ea5e9;
    color: white;
    padding: 10px 14px;
    border-radius: 999px;
    font-weight: 900;
    margin-bottom: 12px;
}

.card h2 {
    font-size: 30px;
    color: #082f49;
    margin-bottom: 4px;
}

.signal {
    color: #0284c7;
    font-weight: 900;
}

.metrics {
    display: grid;
    gap: 10px;
    margin: 18px 0;
}

.metrics div {
    background: #f0f9ff;
    border-radius: 16px;
    padding: 14px;
}

.metrics strong {
    display: block;
    color: #0369a1;
    margin-bottom: 5px;
}

.explain {
    line-height: 1.65;
    color: #334155;
}

.buttons {
    display: grid;
    gap: 10px;
    margin-top: 18px;
}

.buttons a {
    text-align: center;
    background: #0284c7;
    color: white;
    padding: 14px;
    border-radius: 16px;
    text-decoration: none;
    font-weight: 900;
}

@media (min-width: 800px) {
    .grid, .choice-grid.two {
        grid-template-columns: repeat(2, 1fr);
    }

    .choice-grid {
        grid-template-columns: repeat(4, 1fr);
    }

    .passenger-grid {
        grid-template-columns: repeat(3, 1fr);
    }

    .results {
        grid-template-columns: repeat(2, 1fr);
    }

    .metrics {
        grid-template-columns: repeat(3, 1fr);
    }

    h1 {
        font-size: 68px;
        max-width: 850px;
    }
}
