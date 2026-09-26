# Yatra AI ✈️

An autonomous AI travel-planning agent: LangGraph + Groq planning engine,
FastAPI backend with Supabase Auth + Resend email OTP, and a React frontend.

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
        │                  Tools: Open-Meteo weather, OSM/Nominatim places,
        ▼                  OSRM routes, Frankfurter FX, AST calculator
Resend API (OTP emails)
```

- **Auth flow**: name+email → Resend OTP → username/password setup → login
  (username+password, no OTP on subsequent logins) → forgot-password OTP flow.
- **Data isolation**: Row Level Security on `users`, `travel_profiles`,
  `saved_trips`. `email_otps` / `pending_registrations` are service-role only.
- **Agent**: extracts structured requirements, researches with real tools,
  drafts the plan, then a verification node checks budget/feasibility and
  loops back with feedback if it fails. Conversations persist via SQLite
  checkpointer (`thread_id`) for adaptive replanning.

## Setup

### 1. Database

In the Supabase dashboard → SQL Editor, run `backend/app/db/schema.sql`.

### 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase, Resend, Groq keys
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_URL + Supabase publishable key
npm run dev            # http://localhost:5173
```

## Environment variables

| Var | Where | Purpose |
|---|---|---|
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | backend | admin + service ops |
| `SUPABASE_PUBLISHABLE_KEY` | both | user-level Supabase access |
| `RESEND_API_KEY` / `RESEND_FROM_EMAIL` | backend | OTP emails |
| `GROQ_API_KEY` / `GROQ_MODEL` | backend | planning LLM |
| `BACKEND_JWT_SECRET` | backend | signup setup tokens |
| `VITE_API_URL` | frontend | backend base URL |

No key? `DEBUG=true` with no Resend key logs OTPs to the backend console and
returns them as `dev_otp` so the flow works end-to-end locally.

## Security notes

- Secret/service-role key is used only server-side; the frontend holds only
  the publishable key.
- Passwords are hashed by Supabase Auth (bcrypt); OTPs are salted SHA-256.
- Rate limiting on OTP and login endpoints; OTP expires in 10 min, max 5
  attempts.
- The agent treats user input and tool output as untrusted data; budget is
  a hard constraint enforced by a verification node + a deterministic
  numeric check.
