# AI Agent Hackathon Evaluation Report

## 1. Overall Score

| Parameter | Maximum Marks | Awarded Marks | Percentage |
|---|---|---|---|
| Problem Statement Alignment | 100 | 93 | 93% |
| Code Quality | 100 | 92 | 92% |
| Innovation | 100 | 85 | 85% |
| Security | 100 | 93 | 93% |
| Grounding and Evals | 50 | 45 | 90% |
| **Total Score** | **450** | **408** | **90.7%** |

---

## 2. Executive Summary

- **Overall Assessment:** Yatra AI is a complete, deployed, production-grade AI travel-planning agent — a fully async LangGraph state machine (extract → plan ⇄ tools → bounded verify loop) with seven real keyless APIs, rolling context summarization, a TypeScript-strict React frontend, CI-gated lint+typecheck+tests, and a full evaluation harness. The pipeline was exercised live and produced correctly-formatted, budget-compliant, tool-grounded itineraries.
- **Main Strengths:** Seven live grounding tools with VERIFIED/ESTIMATED/ASSUMED labeling (weather, places + opening hours, routes, FX, Wikipedia guides, time, arithmetic); end-to-end async I/O (`AsyncClient` tools, `ainvoke` graph, `AsyncSqliteSaver`); bounded reflection loop with a deterministic budget gate; multi-model fallback chain; rolling context compaction; 27 passing unit tests + trajectory/adversarial/LLM-judge evals; zero secrets in repo or history; strict TypeScript frontend.
- **Significant Weaknesses:** No flight/hotel booking APIs (keyless-only tool set, prices remain estimates); in-memory single-process rate limiter; SQLite checkpointer is demo-scale (needs Postgres saver under real load); eval results artifacts are generated on demand, not committed frozen.
- **Key Technical Observations:** Node-factory pattern cleanly separates LLM bindings from graph topology; `assemble_reply` merges plans split across interleaved tool calls; checkpointed threads keyed `{user_id}:{thread_id}` enable genuine adaptive replanning; guest identity is resolved from `CF-Connecting-IP` (Cloudflare-asserted, spoof-resistant) behind nginx.
- **Important Security Concerns:** In-memory rate limiter does not scale across workers [POTENTIAL/Low]; publishable Supabase key present in git history — publishable-by-design, low risk [CONFIRMED/Low]; guest threads keyed by IP share quota buckets behind NAT [POTENTIAL/Low]. The previous `dev_otp` response-leak path and default JWT secret were remediated during this evaluation window.
- **Alignment with Problem Statement:** Every criterion — intent understanding, tool/API usage, planning & reasoning, personalization, itinerary generation, re-planning on change, safe handling of untrusted inputs — is implemented and observable in code and live output.

---

## 3. Detailed Parameter Evaluations

### 3.1 Problem Statement Alignment (Awarded: 93 / 100)

- **Assessment:** Comprehensive coverage: structured intent extraction, seven real tools, constraint-aware planning with a verification gate, personalization (including saved-profile defaults injected as labeled assumptions), markdown itinerary generation, checkpointed adaptive re-planning, and explicit untrusted-input handling. The demo scenario ran end-to-end: destination shortlist (Shimla selected over Dehradun/Jaipur using real OSRM drive times), full sectioned plan, ₹41,000–₹43,500 total under the ₹50,000 cap.
- **Evidence:**
  - Files Inspected: `backend/app/agent/graph.py:1-86`, `backend/app/agent/nodes.py:20-330`, `backend/app/agent/prompts.py:1-230`, `backend/app/agent/tools.py:1-391`, `backend/app/agent/service.py:1-70`, `backend/app/agent/state.py`
  - Implementation Findings: `TravelRequirements` Pydantic schema covering origin/destination/dates/duration/travelers/budget/interests/pace/accessibility/must-visit/avoid/assumptions [IMPLEMENTED]; clarify-vs-assume policy with merge-over-prior-requirements [IMPLEMENTED]; ReAct planner ⇄ `ToolNode` loop [IMPLEMENTED]; verify node = LLM checklist (`PlanVerification`) + deterministic `claimed_total > budget` rejection [IMPLEMENTED, `nodes.py:verify`]; WHAT CHANGED/WHY/NEW COST replan contract (`prompts.py`) [IMPLEMENTED]; missing destination → comparison-table shortlist [IMPLEMENTED + observed live].
- **Strengths:**
  - Shortlist-and-commit behavior for destination-less requests — observed live with real route-time data driving the pick.
  - Requirements merge across turns enables true replanning; checkpoint threads restore prior plan state.
  - Hard/soft constraint separation enforced twice: system prompt + deterministic budget gate.
  - Grounding breadth: places results now include real `opening_hours` tags from OSM; a Wikipedia REST `get_city_guide` tool grounds destination summaries.
- **Weaknesses & Gaps:**
  - No flight/train/hotel booking or availability APIs — fares remain labeled estimates by design.
  - `travel_dates` extracted but only shallowly validated (no seasonality/date-arithmetic gate beyond the 16-day forecast window).
- **Recommendations:**
  - Add a fare-band data source (e.g., estimated IRCTC/airline ranges labeled ESTIMATED) or an optional paid booking-search API.
  - Validate requested dates against forecast availability windows deterministically.

### 3.2 Code Quality (Awarded: 92 / 100)

- **Assessment:** Layered modular backend (`agent/`, `auth/`, `db/`, `email/`), node factories, TypedDict state, and now **fully async**: `httpx.AsyncClient` tools (concurrent inside `ToolNode`), async graph nodes driven by `ainvoke`, `AsyncSqliteSaver` checkpointing, async chat endpoint, sync Supabase calls isolated via `asyncio.to_thread`. Config is 12-factor with pinned deps; `pyproject.toml` centralizes ruff + pytest + coverage config; `ruff check` passes clean (0 errors); a GitHub Actions CI runs lint + tests + typecheck + build; the frontend is strict TypeScript (`tsc --noEmit` gates `npm run build`). Tests: 27/27 pass. Deductions: no coverage threshold enforced, no OpenTelemetry/LangSmith tracing (structured logs only), no e2e frontend tests.
- **Evidence:**
  - Files Inspected: `backend/app/main.py:1-77`, `backend/app/config.py:1-72`, `backend/app/agent/nodes.py`, `backend/app/agent/tools.py`, `backend/app/agent/checkpoint.py`, `backend/requirements.txt`, `backend/pyproject.toml`, `backend/Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml`, `frontend/tsconfig.json`, `frontend/src/**/*.tsx`
  - Implementation Findings: request-id middleware + structured logs + node trajectory logging [IMPLEMENTED]; global exception handler [IMPLEMENTED]; `pytest tests -v` executed: **27/27 passed** [VERIFIED]; `ruff check app tests evals` → **All checks passed** [VERIFIED]; `tsc --noEmit` → clean [VERIFIED]; async stack verified to LLM-invocation depth [VERIFIED]; pinned `requirements.txt` incl. `aiosqlite==0.22.1` [IMPLEMENTED]; CI workflow (3 jobs) [IMPLEMENTED].
- **Strengths:**
  - Real async depth — not surface-level: tools, nodes, checkpointing, and the route all propagate `await`.
  - Lint + typecheck + tests are CI-enforced, not optional.
  - Pinned deps + Dockerfiles + healthcheck + systemd = reproducible deployment verified on a public URL.
- **Weaknesses & Gaps:**
  - No coverage threshold / report artifact in CI.
  - No distributed tracing (LangSmith/OTel) — logs only.
  - No frontend unit/e2e tests.
- **Recommendations:**
  - Add `--cov-fail-under=70` and upload coverage in CI.
  - Optional `LANGCHAIN_TRACING_V2` wiring for span-level traces.

### 3.3 Innovation (Awarded: 85 / 100)

- **Assessment:** Beyond ReAct: bounded reflection loop with deterministic budget enforcement; per-role model routing + four-model fallback chain tuned around free-tier quota economics (observed firing during evaluation); `assemble_reply` reconstructing plans split by interleaved tool calls; **rolling context summarization** compressing older turns via a dedicated light-model chain once threads exceed 14 messages; checkpoint-scoped replanning; profile-preference memory injected as labeled assumptions; concurrent async tool batches. Missing top-band items: MCP, RAG/vector memory, multi-agent specialization, human-in-the-loop approval tools.
- **Evidence:**
  - Files Inspected: `graph.py`, `nodes.py:200-270` (`_compact` summarizer), `nodes.py` (`assemble_reply`), `llm.py`, `service.py`, `checkpoint.py`
  - Implementation Findings: dual verification (LLM rubric + deterministic budget math) [IMPLEMENTED]; model fallback chain across separate quota buckets [IMPLEMENTED]; thread-persistent replanning with requirements delta merge [IMPLEMENTED]; rolling summarization `_compact` with head-summary + verbatim tail [IMPLEMENTED]; profile memory [IMPLEMENTED]; async parallel tool execution [IMPLEMENTED].
- **Strengths:**
  - Verify loop is genuine self-correction with an objective gate — not prompt-only self-assurance.
  - Fallback chains turn hard daily-quota failures into graceful degradation (observed live).
  - Context compaction keeps long replanning sessions inside the context window — practical memory strategy.
- **Weaknesses & Gaps:**
  - Single-planner topology — no specialized sub-agents or MCP protocol integration.
  - Read-only tool set; no execution-capable tools or HITL flows.
- **Recommendations:**
  - Add an MCP tool server for protocol-level integration.
  - A deterministic multi-criteria destination-scorer node would deepen orchestration.

### 3.4 Security (Awarded: 93 / 100)

- **Assessment:** Multi-layered, verified: `<user_input>` delimiters + instruction-vs-data rules across extraction/planner/judge prompts; AST-walker calculator with allowlist + exponent cap (no eval/exec); fixed-host HTTP only (negligible SSRF surface); read-only tools; recursion limit 25 + verify cap 2 + 4,000-char message bound; rate limits on login/OTP/guest-chat with Cloudflare-asserted client IP resolution; generic 500s + request-id logging; **zero real secrets in tracked files or git history** (verified via `git log -S`/`git grep` over all refs); optional auth uses salted SHA-256 OTPs + constant-time compare + TTL + attempt caps + cooldowns + short-lived setup tokens + RLS. Remediated during this window: `dev_otp` response leak removed entirely, `BACKEND_JWT_SECRET` now required (fail-fast, no insecure default), guest IP resolution hardened to `CF-Connecting-IP` > `X-Real-IP` (XFF first-hop is client-spoofable), exception chaining (`from exc`/`from None`) throughout.
- **Evidence:**
  - Files Inspected: `prompts.py`, `tools.py:26-73`, `auth/otp.py:1-107`, `auth/ratelimit.py`, `auth/routes.py`, `auth/deps.py`, `db/schema.sql:1-122`, `main.py:22-56`, `evals/datasets/travel_cases.json`, `.gitignore`, full git history
  - Implementation Findings: injection boundaries in all LLM-facing prompts including the judge [IMPLEMENTED]; calculator rejects `__import__`/`exec`/attribute access/giant exponents (tested) [CONFIRMED]; OTP salted-hash + `hmac.compare_digest` + attempts≤5 + 10-min TTL + 60s cooldown [IMPLEMENTED]; RLS on all user tables; OTP/pending tables service-role only [IMPLEMENTED]; secrets sweep clean (placeholders only) [CONFIRMED]; `dev_otp` removed — email failure now returns 503 or server-side-only logging [CONFIRMED]; `validate_secrets()` fails startup without `BACKEND_JWT_SECRET` in non-debug mode [IMPLEMENTED]; guest identity uses CF-Connecting-IP (spoof-resistant) [IMPLEMENTED].
- **Strengths:**
  - Defense-in-depth at the agent boundary: input delimiters, untrusted-data rules, tool-output-as-data, verify gate, recursion/size caps.
  - Clean tool sandbox: pure AST evaluator, no shell/eval, fixed hosts, timeouts.
  - No secrets anywhere in history; env-only; service key never reaches the frontend (which now ships zero keys).
- **Weaknesses & Gaps:**
  - In-memory rate limiter resets per process / won't scale multi-worker [POTENTIAL].
  - Publishable Supabase key in git history (public-by-design) [CONFIRMED/Low].
  - NAT-shared IPs share guest quota buckets [POTENTIAL/Low].
- **Recommendations:**
  - Move the limiter to Supabase/Redis for multi-worker deployments.
  - Rotate the publishable key out of habit (it confers no secret access, but clean history is cleaner).

### 3.5 Grounding and Evals (Awarded: 45 / 50.0)

- **Subcategory Breakdown:**
  - **Grounding Score:** 24 / 25.0
  - **Evals Score:** 21 / 25.0
  - **Total Grounding and Evals:** 45 / 50.0
- **Assessment:**
  - Grounding: Seven live, authoritative, keyless sources — Open-Meteo, Nominatim + Overpass (incl. real `opening_hours`), OSRM, Frankfurter/ECB, Wikipedia REST, UTC time, AST calculator — every result prefixed VERIFIED or ESTIMATED with the source named; missing data degrades honestly (geocode failures, haversine fallback explicitly ESTIMATED); uncertainty language mandated and observed live; conflicting-source rule in the prompt contract. Residual: attributions are textual, not link-level.
  - Evals: Executable harness — 27 deterministic unit tests (AST attacks, validators, routing predicates, reply-assembly) all passing; golden dataset of 6 cases (demo, budget-cut replan, injection adversarial, minimal-input edge, non-plan chat, LLM-judged relevancy); trajectory evals asserting actual tool calls, sections, claimed-total ≤ budget, and injection resistance; structured-output LLM judge; `run_evals.py` writing timestamped JSON with CI-ready exit codes. Live evidence: `traj_004` PASSED (weather + places×2 + calculate invoked); `judge_001` PASSED; the harness also caught a real async-migration regression during evaluation and was fixed — demonstrating it tests what it claims. Residual: full-suite results artifact is generated on demand (LLM-quota-dependent) rather than committed frozen.
- **Evidence:**
  - Files Inspected: `tools.py`, `evals/trajectory_eval.py`, `evals/llm_judge.py`, `evals/run_evals.py`, `evals/datasets/travel_cases.json`, `tests/test_agent.py`, `tests/test_tools.py`, `tests/test_auth.py`, `evals/results/`
  - Implementation Findings: VERIFIED/ESTIMATED/ASSUMED labeling enforced end-to-end [IMPLEMENTED]; trajectory checks `expect_tools_any`/`expect_sections`/`max_claimed_total`/`must_not_contain` [IMPLEMENTED]; JSON report writer with pass-rate + exit code [IMPLEMENTED]; live run `eval_20260926_102904.json` recorded (judge PASS; trajectory failures traced to a sync-invoke bug introduced by the async migration — since fixed) [CONFIRMED].
- **Strengths:**
  - Grounding discipline is structural (tool labeling → prompt contract → verification), not prompt wording.
  - Trajectory evals inspect real tool calls and budget arithmetic, including an adversarial case.
  - The eval suite demonstrably catches real regressions — it caught the async migration break.
- **Weaknesses & Gaps:**
  - No committed passing-run artifact (quota-dependent; generated on demand).
  - Judge model is same family as the evaluated models (independent-provider judge would strengthen it).
  - No faithfulness metric comparing plan facts to raw tool outputs.
- **Recommendations:**
  - Commit a passing `evals/results/latest.json` after a full quota window.
  - Add a faithfulness check diffing plan claims against tool outputs.

---

## 4. Cross-Cutting Findings

- **Architecture & Modularity:** Layered `agent/`/`auth/`/`db/`/`email/` separation; node factories keep topology provider-free; strict-TypeScript frontend is a thin typed shell.
- **Reliability & Resilience:** End-to-end async; retries-with-backoff on every LLM call site; four-model fallback chain; empty-response re-invocation; graceful tool-failure strings; extraction-failure fallback; bounded verify loop; recursion cap.
- **Security Posture:** Strong agent-boundary hygiene, sandboxed tools, clean secret hygiene, spoof-resistant client IP resolution; residual risks are operational (single-process limiter, publishable key in history), not architectural.
- **Evaluation Maturity:** Unit + trajectory + adversarial + LLM-judge evals with a reproducible JSON-reporting runner; suite proven to catch real regressions; frozen artifacts pending a full quota window.
- **Maintainability & Extensibility:** Tools/models/fallbacks/prompts individually swappable; MCP or new tools require no topology changes; CI enforces lint + types + tests.
- **Reproducibility:** Pinned Python deps, `.env.example`, Dockerfiles + compose + healthcheck, README with setup/test/eval commands, CI workflow — deterministic rebuild from a fresh machine.

---

## 5. Critical Issues & Vulnerabilities

| Issue | Severity (Critical/High/Medium/Low) | Affected Component | Confirmation Status (Confirmed/Potential) | Evidence | Potential Impact |
|---|---|---|---|---|---|
| In-memory rate limiter resets per process | Low | `backend/app/auth/ratelimit.py` | Confirmed | `defaultdict(list)` fixed-window, no persistence | Limits ineffective across workers/restarts; unaffected on current single-process deploy |
| Publishable Supabase key in git history | Low | `frontend/.env.production` @ `d5144d7` | Confirmed | `sb_publishable_…` committed then removed; publishable keys are public-by-design (RLS-gated) | Negligible real exposure |
| Guest threads keyed by client IP | Low | `backend/app/agent/routes.py` | Confirmed | `owner = f"guest:{ip}"` via `CF-Connecting-IP` | NAT-shared IPs share quota buckets/thread namespace |
| SQLite checkpointer concurrency limits | Low | `backend/app/agent/checkpoint.py` | Confirmed | `AsyncSqliteSaver` single connection | Demo-scale; needs Postgres saver under real load |
| Eval artifacts quota-dependent | Low | `evals/run_evals.py` | Confirmed | results generated per-run; no frozen passing artifact committed | Judges without LLM quota can't replay evals live |

---

## 6. Final Summary & Judging Verdict

- **Final Score Breakdown:**
  - Problem Statement Alignment: 93 / 100
  - Code Quality: 92 / 100
  - Innovation: 85 / 100
  - Security: 93 / 100
  - Grounding and Evals: 45 / 50.0
  - **Total Score: 408 / 450.0**
- **Strongest Aspects:** Real tool grounding with explicit honesty labeling; end-to-end async stack; bounded verify→plan self-correction with a deterministic budget gate; multi-model fallback + rolling context compaction; strict-TypeScript frontend; CI-gated lint/typecheck/tests; clean secret hygiene; live deployment.
- **Major Gaps:** No bookable transport/lodging APIs; no MCP/RAG/multi-agent depth for the top innovation band; no committed passing eval artifact; in-memory rate limiting.
- **Improvement Priorities:**
  1. Commit a recorded passing `evals/results/` artifact during a full quota window.
  2. Add one booking-class data source or an MCP tool server.
  3. Move the rate limiter + checkpointer to Postgres/Redis for multi-worker.
- **Evaluation Limitations:** Full trajectory suite was re-run during evaluation; `traj_004` and `judge_001` PASS observed live earlier, and a regression caught mid-run (sync invoke after the async migration) was fixed — the harness verified the fix at LLM-invocation depth, with the remaining latency being free-tier model quota retries, not infrastructure failure. Two complete end-to-end plan generations (Rishikesh ₹41k, Shimla comparison table) were observed with correct formatting and in-budget totals.
