# AIFlight Platform Architecture

AIFlight is moving from a simple flight search tool into a personal travel decision engine.

## Request Flow

1. User
2. Web App
3. API Gateway
4. AI Brain Loop
5. Trip Orchestrator
6. Flight Data Platform
7. Data Quality + Normalization
8. Feature Engine
9. AI / ML Intelligence Layer
10. Decision Engine
11. LLM Explanation Layer
12. Results Experience
13. Feedback + Learning Loop
14. Monitoring / Evals / Safety

## Implemented Now

- API gateway: JSON validation, rate limits, basic abuse checks, security headers.
- AI brain loop: perceive, understand, build context, decide, act, self-evaluate, refine, then respond.
- World model: stores current task, user preferences, known constraints, retrieved context, and confidence before search.
- Assumption guard: unsupported model guesses, especially invented dates and passenger counts, are removed before action.
- Trip orchestrator: one backend path coordinates intent, provider search, scoring, explanation, and UI response.
- Flight data platform: Duffel live fares plus fallback links; provider registry is ready for Travelpayouts and future GDS/direct airline APIs.
- Provider execution: deal-space searches run with retries and parallel workers.
- Normalization: airport, date, passenger, cabin, priority, and offer data are normalized before scoring.
- Feature engine: price spread, median fare, days to departure, exact-trip savings, offer count, and session history.
- Decision engine: buy/wait recommendation, confidence, prediction, and anti-pricing moves.
- LLM explanation: natural language reply is grounded in structured offers and intelligence data.
- Results experience: UI now shows decision, confidence, price signals, sources, metrics, and feedback controls.
- Learning loop: in-memory price observations and feedback endpoint.
- Monitoring: health and metrics endpoints with provider/layer status.
- Evals: `/api/evals` checks trip-understanding hard cases without calling paid flight providers.

## Roadmap

- Add Travelpayouts provider adapter.
- Add persistent database tables for searches, price observations, feedback, and user preferences.
- Add fare-rule and baggage-rule normalization.
- Add historical price ingestion and model training.
- Add user accounts, saved trips, alerts, and authenticated API keys.
- Add scheduled price tracking jobs.
- Add eval suite for trip understanding, provider failures, and recommendation quality.
