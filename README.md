# Yatra AI ✈️

An autonomous AI travel-planning agent: LangGraph planning engine
(extract → plan ⇄ tools → verify loop), FastAPI backend with Supabase
Auth + Resend email OTP, and a React frontend.

## Architecture

```
React frontend (Vite)                    Supabase (Postgres + Auth)
        │                                        ▲
        │  REST /api/*  ──►  FastAPI backend ────┘
        │                       │                (service key: admin ops,
        │                       ▼                 OTP table, user creation)
        │                  LangGraph agent:      publishable key in browser:
        │                  extract → plan →      RLS-enforced trips/profiles
        │                  verify (loop)
        │                       │
        │                  Tools: Open-Meteo weather, OSM/Overpass places,
        ▼                  OSRM routes, Frankfurter FX, AST calculator
Resend API (OTP emails)
```

- **Auth flow**: username + full name + email + password → Resend OTP →
  account created → login (username+password only afterwards) →
  forgot-password OTP flow. Guests can skip and try the planner instantly.
- **Data isolation**: Row Level Security on `users`, `travel_profiles`,
  `saved_trips`. `email_otps` / `pending_registrations` are service-role only.
- **Agent**: extracts structured requirements (merged with saved profile
  preferences), researches with real tools, drafts the plan, then a
  verification node checks budget/feasibility and loops back with feedback
  (bounded). Conversations persist via SQLite checkpointer (`thread_id`)
  for adaptive replanning.
- **LLM resilience**: per-role models (planner vs. extract/verify) with a
  multi-model fallback chain and exponential-backoff retries — the agent
  keeps working when a single model's quota or health fails.

## Setup

### 1. Database

In the Supabase dashboard → SQL Editor, run `backend/app/db/schema.sql`.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase, Resend, Gemini/Groq keys
uvicorn app.main:app --reload --port 8100
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL + Supabase publishable key
npm run dev            # http://localhost:5173
```

### 4. Docker (all-in-one)

```bash
docker compose up --build   # frontend :80, backend :8100
```

## Tests & evals

```bash
cd backend
python -m pytest tests -v        # 27 unit tests (no network/LLM needed)
python -m evals.run_evals        # live trajectory + LLM-judge evals
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
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | backend | admin + service ops |
| `SUPABASE_PUBLISHABLE_KEY` | both | user-level Supabase access |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | backend | OTP emails |
| `GEMINI_API_KEY` + `GEMINI_MODEL` / `GEMINI_LIGHT_MODEL` | backend | planning LLM |
| `GEMINI_FALLBACK_MODELS` | backend | comma-separated fallback chain |
| `GROQ_API_KEY` / `GROQ_MODEL` | backend | alternate LLM provider |
| `BACKEND_JWT_SECRET` | backend | signup setup tokens |
| `VITE_API_URL` | frontend | backend base URL |

No email key? `DEBUG=true` with a failed/missing Resend send logs OTPs to
the backend console and returns them as `dev_otp` so the flow works
end-to-end in development.

## Security notes

- Secret/service-role key is used only server-side; the frontend holds only
  the publishable key.
- Passwords are hashed by Supabase Auth (bcrypt); OTPs are salted SHA-256,
  expire in 10 min, max 5 attempts, resend cooldown 60s.
- Rate limiting on OTP, login, and guest chat endpoints.
- The agent treats user input and tool output as untrusted data
  (`<user_input>` boundaries, instruction-vs-data rules in the system
  prompt); the calculator is AST-safe (no `eval`); graph recursion is
  capped; verification re-checks budgets deterministically.
- All external HTTP calls carry timeouts; client errors never expose stack
  traces (request-id logging is server-side only).
