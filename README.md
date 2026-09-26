# Yatra AI ✈️

An autonomous AI travel-planning agent: LangGraph planning engine
(extract → plan ⇄ tools → verify loop), FastAPI backend, React frontend.
No sign-up needed — open the app and start planning.

## Architecture

```
React frontend (Vite)
        │   REST /api/chat
        ▼
   FastAPI backend
        │
        ▼
   LangGraph agent:
   extract → plan ⇄ tools → verify (bounded loop)
        │
        ▼
   Tools: Open-Meteo weather, OSM/Overpass places,
   OSRM routes, Frankfurter FX, AST calculator
```

- **Frictionless UX**: no accounts — the planner is public, and saved trips
  live in the browser (`localStorage`), including a re-plan link that
  restores the conversation thread.
- **Agent**: extracts structured requirements, researches with real tools,
  drafts the plan, then a verification node checks budget/feasibility and
  loops back with feedback (bounded). Conversations persist via SQLite
  checkpointer (`thread_id`) for adaptive replanning.
- **LLM resilience**: per-role models (planner vs. extract/verify) with a
  multi-model fallback chain and exponential-backoff retries — the agent
  keeps working when a single model's quota or health fails.
- **Optional backend auth**: the backend additionally ships a complete
  Supabase + Resend OTP auth API (`/api/auth/*`) for deployments that want
  accounts — the shipped frontend simply doesn't require it.

## Setup

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Gemini (or Groq) + Supabase/Resend keys
uvicorn app.main:app --reload --port 8100
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL only
npm run dev            # http://localhost:5173
```

### 3. Docker (all-in-one)

```bash
docker compose up --build   # frontend :80, backend :8100
```

## Tests & evals

```bash
cd backend
python -m pytest tests -v          # 27 unit tests (no network/LLM needed)
python -m evals.run_evals          # live trajectory + LLM-judge evals
python -m evals.run_evals --quick  # trajectory only, no judge calls
```

`evals/` includes a golden dataset (`evals/datasets/travel_cases.json`)
covering the demo scenario, adaptive replanning (budget-cut), a prompt
injection adversarial case, minimal-input edge case, conversational input,
and an LLM-judged relevancy case. Trajectory evals assert which tools were
actually called, required plan sections, and that the claimed total
respects the hard budget. Results are written to `evals/results/`.

## Environment variables

| Var | Where | Purpose |
|---|---|---|
| `GEMINI_API_KEY` + `GEMINI_MODEL` / `GEMINI_LIGHT_MODEL` | backend | planning LLM |
| `GEMINI_FALLBACK_MODELS` | backend | comma-separated fallback chain |
| `GROQ_API_KEY` / `GROQ_MODEL` | backend | alternate LLM provider |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | backend | optional auth/data APIs |
| `SUPABASE_PUBLISHABLE_KEY` | backend | user-level Supabase access |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | backend | optional OTP emails |
| `BACKEND_JWT_SECRET` | backend | optional auth tokens |
| `VITE_API_URL` | frontend | backend base URL |

## Security notes

- The agent treats user input and tool output as untrusted data
  (`<user_input>` boundaries, instruction-vs-data rules in the system
  prompt); the calculator is AST-safe (no `eval`); graph recursion is
  capped; verification re-checks budgets deterministically.
- Guest traffic is rate-limited per IP; all external HTTP calls carry
  timeouts; client-facing errors never expose stack traces
  (request-id logging is server-side only).
- Backend auth uses salted SHA-256 OTPs, bcrypt-hashed passwords via
  Supabase Auth, RLS isolation, and rate limiting — when enabled.
