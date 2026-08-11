# Project Specification — AI Knowledge Graph Builder

Authoritative spec of what the system actually is, how it's built, and every deliberate deviation between the documentation and the real implementation. Companion to `HOW_IT_WORKS.md` (how it works) and `TODO.md` (what's left).

---

## 1. Project Overview

**Name:** AI Knowledge Graph Builder (AKGB)
**Type:** Full-stack semester major project (MVP, demo-able)
**One-line description:** Upload documents → the system extracts a knowledge graph (entities + relationships) → explore it visually, search it semantically, and chat with it (RAG with citations). Extended with agents (LangGraph), MCP exposure, webhooks, and Google Meet ingestion.

**Demo moments that define "done" (from BUILD_BRIEF.md §1):**

1. Upload a real PDF → watch it move `pending → processing → processed` in the UI.
2. Ask a question in chat → streamed answer with clickable citations that jump to source pages.
3. Open the graph view → see extracted entities and their connections.
4. Trigger an agent → see a step-by-step run log.
5. Connect an external MCP client (e.g. Claude Desktop) → call `search_knowledge_base` and get real results.
6. Dashboard shows mid-upload and mid-failure states honestly.

---

## 2. Tech Stack (Actual, Verified Against Code)

| Layer | Technology | Where verified |
|---|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript, Tailwind, Zustand, TanStack Query (installed) | `apps/web/package.json` |
| Graph visualization | **reagraph** (force-directed canvas) | `apps/web/src/app/graph/page.tsx` |
| Backend | Python 3.11+, FastAPI (async), SQLAlchemy 2.0 async ORM, Pydantic v2 | `apps/api/requirements.txt`, `apps/api/db/` |
| Relational DB | **SQLite in dev (forced), PostgreSQL (Supabase) in production** | `apps/api/core/config.py` |
| Vector store | ChromaDB (`PersistentClient`, single `knowledge_base` collection) | `apps/api/pipelines/embeddings.py` |
| Auth | **Supabase Auth (JWT validation) in prod; mock auth in dev** | `apps/api/core/security.py` |
| LLM | OpenAI-compatible endpoints — Groq (current `.env`) / Ollama (defaults) | `apps/api/core/config.py`, `apps/api/.env` |
| Entities (NER) | spaCy `en_core_web_sm` + LLM structured extraction | `apps/api/pipelines/entity_extraction.py` |
| Graph traversal | NetworkX (in-memory `DiGraph` subgraphs) | `apps/api/services/knowledge.py` |
| Agents | LangGraph + in-memory asyncio task queue | `apps/api/pipelines/agent_pipeline.py`, `core/task_queue.py` |
| MCP | Official MCP Python SDK, OAuth 2.0 + PKCE, persisted tokens | `apps/api/core/oauth.py`, `services/mcp.py` |
| Background jobs | FastAPI `asyncio.create_task` (no Celery/RQ) | `apps/api/routers/documents.py`, `core/task_queue.py` |
| File parsing | PyMuPDF (PDF), python-docx (DOCX), Tesseract OCR (images) | `apps/api/pipelines/parser.py` |
| Webhooks | HTTP outbound with retry table (`webhook_deliveries`) | `apps/api/services/webhooks.py` |

> **Documented but NOT implemented:** Prisma (see §5), Supabase Storage (TODO in code), Redis/queue (documented upgrade path only), Vitest/React Testing Library (devDependency only, no tests).

---

## 3. Architecture

### 3.1 High-level flow

```
Next.js UI ──(REST + SSE, Bearer JWT, ?project_id=)──► FastAPI API
                                                       ├── routers/ (thin HTTP)
                                                       ├── services/ (business logic)
                                                       ├── pipelines/ (ingestion, RAG, agents)
                                                       │
             Relational DB (SQLite/Postgres) ◄─────────┤ SQLAlchemy async ORM
             ChromaDB (vectors) ◄──────────────────────┤ embeddings.py
             LLM (Groq/Ollama) ◄───────────────────────┤ llm_client.py
```

### 3.2 The two pipelines

**Ingestion** (`pipelines/ingestion.py`): `parse → chunk (~600 tokens, 80 overlap) → embed → upsert ChromaDB + chunk rows → extract entities/relationships (spaCy + LLM + dedup) → status=processed`. Background asyncio task; SSE progress stream; failure → `status=failed` + retry endpoint.

**RAG / chat** (`services/chat.py`): embed question → Chroma top-8 (project-filtered) → entities in chunks → **1-hop graph expansion** via relationships → prompt (sources + entity context + history) → streamed LLM answer over SSE → persist message + citations. Prompt-injection guard via `security_utils.py`.

### 3.3 Request lifecycle

1. `middleware.ts` (frontend) protects routes; `GlobalAuthMiddleware` (backend) requires Bearer JWT except public routes (`/health`, `/system/status`, `/docs`, `/openapi.json`, `/auth/...`, OPTIONS preflight). SSE falls back to `?token=` (EventSource can't set headers).
2. `core/deps.py::get_project_id` resolves project: explicit `?project_id=` (membership-checked) → single-project auto-detect → auto-create default project → 400 if ambiguous.
3. Router → service → ORM → DB. `get_db()` session commits/rolls back per request.
4. Background work (ingestion, agent runs) opens **its own session** via `async_session_factory` (request session dies after response) and keeps a **strong asyncio task reference** (prevents GC killing the task mid-run).

### 3.4 Real-time (SSE)

- Document progress: `GET /documents/{id}/stream` — stages `processing → parsing → chunking → embedding → extracting_entities → complete` (in-memory subscriber queues).
- Agent traces: `core/task_queue.py` — step events with replay for late subscribers, cleanup on close.

---

## 4. Data Model (All Tables)

All tables: `apps/api/db/models.py` (SQLAlchemy, working) mirroring `infra/schema.sql` (Supabase). UUID PKs, JSON columns for flexible data.

| Table | Purpose | Key columns |
|---|---|---|
| `profiles` | User row (app-side identity) | id, full_name, created_at |
| `projects` | Top-level container, everything scoped to it | name, owner_id |
| `project_members` | Access control (owner/editor/viewer) | (project_id, user_id) PK, role |
| `documents` | Uploaded files, lifecycle status | status (pending/processing/processed/failed), file_type, storage_path, error_message |
| `document_chunks` | ~600-token segments | chunk_index, page_number, text, **chroma_id** (bridge to vector store) |
| `entities` | Graph vertices | name, type, description, **UNIQUE (project_id, name, type)** — dedup rule |
| `entity_mentions` | Entity ↔ chunk occurrences | entity_id, document_id, chunk_id, mention_text, confidence |
| `relationships` | Graph edges | source_entity_id → target_entity_id, relation_type, confidence, source_document_id |
| `chat_sessions` | Conversation threads | project_id, user_id, title |
| `chat_messages` | User/assistant messages | role, content, **citations (JSON array)** |
| `agents` | Automated task runners | type, config (JSON), status |
| `agent_tasks` | Agent executions | input/output (JSON), status, **trace (JSON)** |
| `agent_memory` | Working/episodic/semantic memories | memory_type, content, embedding |
| `agent_checkpoints` | Resumable state snapshots | state (JSON) |
| `agent_skills` | Learned skills w/ counters | skill_type, content, success/failure counts |
| `agent_run_traces` | Detailed run logs | input/output_text, tool_calls, scores |
| `refinement_eval_sets` / `refinement_logs` | Self-improvement eval harness | split (held_in/held_out), before/after JSON |
| `mcp_connections` | External MCP integrations | direction (sender/receiver), endpoint_url, auth_config |
| `mcp_auth_tokens` | Persisted OAuth tokens | access_token, refresh_token, expires_at |
| `project_memory_shares` | Cross-project memory sharing | permission (read/read_write) |
| `audit_log` | Every mutating action | action, resource_type/id, meta |
| `webhook_subscriptions` | Outbound webhook config | event_type, url, secret, active |
| `webhook_deliveries` | Webhook attempt log w/ retry | response_status, attempts, success, next_retry_at |
| `inbound_webhooks` | Inbound webhook endpoints | slug (unique), handler, config |

### Key relationships

```
Project 1──* Document 1──* DocumentChunk
Project 1──* Entity 1──* EntityMention *──1 DocumentChunk
Entity 1──* Relationship *──1 Entity
Project 1──* ChatSession 1──* ChatMessage
Project 1──* Agent 1──* AgentTask | AgentMemory | AgentCheckpoint | AgentSkill | AgentRunTrace
Project 1──* MCPConnection 1──* MCPAuthToken
Project 1──* WebhookSubscription 1──* WebhookDelivery
```

---

## 5. Prisma — Why It's Not Being Used (The Honest Story)

**Short version:** Prisma was scaffolded, then **removed** in the latest commit (`8c72299`). The dependencies remain installed and the docs still mention it, but nothing uses it. This is a docs-vs-code inconsistency.

**The full evidence (from git history):**

- `4e780e5 first commit` contained a complete, working Prisma setup:
  - `apps/web/prisma/schema.prisma` — SQLite datasource, `Document` + `Chunk` models.
  - `apps/web/prisma/migrations/20260807181421_init/migration.sql` — the created tables.
  - `apps/web/prisma.config.ts` — Prisma 7 config reading `DATABASE_URL`.
  - `apps/web/src/lib/prisma.ts` — `PrismaClient` singleton with the better-sqlite3 driver adapter.
  - `apps/web/dev.db` — the SQLite database file it created.
- `8c72299 feat: multi-project management, API error resilience, and robustness fixes` **deleted** all five of those files (115 lines removed: schema, migration, config, client, db file).
- What remained: `@prisma/client`, `@prisma/adapter-better-sqlite3`, `prisma`, `better-sqlite3` in `package.json`, `DATABASE_URL="file:./dev.db"` in `apps/web/.env` + `.env.example`, and `/src/generated/prisma` in `apps/web/.gitignore`.
- `apps/web/.agents/skills/prisma-*` (in .claude/.continue/.windsurf too) are just skill docs — Prisma's own onboarding material, not project code.

**Why it was removed (reconstructed from the commit itself):** the commit is titled "multi-project management, API error resilience, and robustness fixes" — the frontend stopped talking to its own database and now talks to the backend API (`src/lib/api/client.ts`, project store). A frontend-local Prisma DB is redundant when the backend owns all data; the schema it carried (`Document`/`Chunk` only) duplicated the backend's real schema and would have drifted.

**Why it looks like it's still in use (doc confusion):** `README.md` lists "SQLite (local dev for Prisma)" and `apps/web/.env.example` documents `DATABASE_URL`. Both are stale — README even describes `apps/web/prisma/` in the structure, which no longer exists.

**Bottom line for your friend:** if they search for "Prisma" they'll find dependencies, env vars, and skill docs — but zero `import` statements. Prisma is dead code / a documented intention, not the storage layer. SQLAlchemy on the backend is the one true ORM.

---

## 6. Where User Data & Auth Actually Live

**There is no bespoke user table with credentials.** Identity and credentials are handled by **Supabase Auth** (production) or **mock auth** (development). The app's own DB only keeps a `profiles` row per user for app-level attributes.

| What | Where it lives | Details |
|---|---|---|
| User credentials (email/password, Google OAuth) | **Supabase Auth service** (cloud) | Frontend `@supabase/ssr`; never stored in the app DB |
| Session tokens | Browser cookies (`sb-access-token`, `sb-refresh-token`) / JWT in memory | `apps/web/src/middleware.ts` refreshes via `@supabase/ssr`; backend `core/security.py` validates |
| Mock dev session | Hardcoded demo user | `a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11` / mock@example.com — in `supabase/client.ts`, `core/auth_middleware.py`, `core/security.py`, `routers/auth.py` (mock-login sets the cookies) |
| App-side profile row | `profiles` table (app DB) | created on first request via `core/deps.py::_ensure_user_and_project` (deterministic UUID from user id, namespace `a1b2c3d4-e5f6-7890-abcd-ef1234567890`) |
| Project membership / roles | `project_members` table (app DB) | checked on every request (`get_project_id`, 403 if not a member) |
| MCP OAuth tokens | `mcp_auth_tokens` table (app DB) | tokens exchanged via `core/oauth.py`, persisted across restarts |
| Audit trail | `audit_log` table (app DB) | every mutating action |

So: **credentials → Supabase (or mock); app identity, roles, and everything else → the app's own database via SQLAlchemy.** The backend is the only place that validates tokens; the frontend's job is just to obtain and carry the session.

---

## 7. Why the Frontend Needs Env Files

`apps/web/.env` / `.env.local` exist for **four reasons** — three real, one stale:

1. **Supabase keys (real):** `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — required by `src/lib/supabase/client.ts`, `server.ts`, and `middleware.ts` to talk to Supabase Auth. These are `NEXT_PUBLIC_*` because the browser needs them (safe — they're public keys). Without them the frontend **cannot build** in real-auth mode.
2. **Mock auth flag (real):** `NEXT_PUBLIC_MOCK_AUTH="true"` switches the whole auth layer to demo mode (`client.ts` returns a fake Supabase client, `middleware.ts` checks the `mock-session` cookie, `auth/demo-login/route.ts` signs in). Build fails if it's `true` in production.
3. **App URL (real, minor):** `NEXT_PUBLIC_APP_URL` — base URL used by the frontend.
4. **Prisma `DATABASE_URL` (stale):** documented for the Prisma setup that was deleted in `8c72299` (§5). Currently **read by nothing** — grep the codebase: no `process.env.DATABASE_URL` consumer exists in `apps/web/src`. The backend's `DATABASE_URL` (in `apps/api/.env`) is the one that matters.

**Why backend envs don't cover these:** the backend never sees `NEXT_PUBLIC_*` vars, and the frontend runs in the user's browser (needs public keys at runtime) plus Next's build time. `NEXT_PUBLIC_*` vars are inlined into the client bundle at build time — hence they must be present when `next build` runs (e.g. Vercel dashboard for deploy).

---

## 8. Docs vs Actual Implementation — Verified Gaps

Cross-checked `README.md`, `BUILD_BRIEF.md`, `CONTEXT.md`, `docs/adr/*`, `.env.example` files against the code.

| # | Claim (doc) | Reality (code) | Verdict |
|---|---|---|---|
| 1 | "SQLite (local dev for Prisma)" + `apps/web/prisma/` structure | Prisma deleted in `8c72299`; no `schema.prisma` anywhere | **Stale docs** |
| 2 | `DATABASE_URL` env var for frontend | No consumer in `apps/web/src` | **Stale env** |
| 3 | "Supabase Storage" for files (`storage_path`) | `storage_path` is just a generated path string; `documents.py` has `# TODO: Upload to Supabase Storage` — files live only in request memory; retry requires re-uploading | **Not implemented** |
| 4 | Backend LLM: OpenAI / Ollama | `apps/api/.env` uses **Groq** (OpenAI-compatible) with model `qwen/qwen3.6-27b`; embeddings from local Ollama | **Differs from README defaults** (code supports both; env differs) |
| 5 | ChromaDB "on disk, no separate service" | True — `PersistentClient(path=CHROMA_PATH)` | ✅ Matches |
| 6 | Postgres + NetworkX over Neo4j | True — ADR-0001, `services/knowledge.py` | ✅ Matches |
| 7 | Supabase Auth w/ backend JWT validation | True — ADR-0003, `core/security.py` | ✅ Matches |
| 8 | Single Chroma collection w/ project filter | True — ADR-0002, `embeddings.py` | ✅ Matches |
| 9 | Chat streaming over SSE with citations | True — `services/chat.py` + `app/chat/page.tsx` | ✅ Matches |
| 10 | Background tasks via FastAPI BackgroundTasks (brief §2) | Actually `asyncio.create_task` + strong refs (`documents.py`, `task_queue.py`) — deliberate fix for middleware dropping BackgroundTasks | **Deviation, documented in code comments** |
| 11 | Testing: Vitest + RTL frontend | Vitest/RTL in devDependencies only; **no frontend unit tests exist** | **Not implemented** |
| 12 | Alembic migrations path | Present (`migrations/001_initial_schema.py`) but dev uses `init_db.py` `create_all` | ✅ Present / dev shortcut |
| 13 | Frontend graph lib "React Flow" (brief) | Actually **reagraph** | **Deviation** |
| 14 | LLM model `llama3.1` / `gpt-4o-mini` (README) | Current env: `qwen/qwen3.6-27b` (Groq); chat/extraction hardcode `llama-3.3-70b-versatile` | **Stale README** |
| 15 | Rate limiting on upload/chat | Yes — slowapi: uploads 30/min, chat 60/min | ✅ Matches |
| 16 | Backend `MOCK_AUTH` fails fast in prod | True — `config.py` model validator | ✅ Matches |
| 17 | Frontend build fails with mock auth in prod | Partially — `next.config.ts` behavior; middleware would use mock in prod if env set | **Mostly matches** |
| 18 | `profiles` row per user | True — `core/deps.py` upsert | ✅ Matches |

**Stale-doc cleanup TODO:** `README.md` (Prisma, model names, LLM defaults), `apps/web/.env` + `.env.example` (Prisma `DATABASE_URL`), root `akgb.db` (stale dev artifact).

---

## 9. API Surface (Routers)

All under `apps/api/routers/`, prefix per `main.py`:

| Router | Prefix | Notable endpoints |
|---|---|---|
| auth | `/auth` | `GET /me`, `POST /mock-login` (dev only) |
| documents | `/documents` | `POST` (upload, 202, rate-limited), `GET`, `GET /{id}`, `GET /{id}/status`, `GET /{id}/chunks`, `GET /{id}/entities`, `DELETE /{id}`, `POST /{id}/retry`, `GET /{id}/stream` (SSE) |
| kb | `/kb` | `GET /search`, `GET /entities/{id}`, `GET /entities/{id}/chunks`, `GET /graph` (depth 1–3) |
| chat | `/chat` | `POST /sessions`, `GET /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/messages` (SSE, 60/min) |
| dashboard | `/dashboard` | `GET /summary` |
| agents | `/agents` | CRUD + `POST /{id}/run`, `GET /{id}/tasks/{task_id}` (SSE trace) |
| mcp | `/mcp` | `GET/POST/DELETE /connections`, `GET /connections/{id}/authorize` (PKCE), `GET /callback`, `POST /search`, `POST /connections/{id}/test` |
| meetings | `/meetings` | Meet sync endpoints (client-side recorder + legacy bot agent) |
| projects | `/projects` | Multi-project CRUD + members |
| sharing | `/projects/{project_id}/shares` | Cross-project memory sharing |
| webhooks | `/webhooks` | Subscriptions + deliveries |

Plus public: `GET /health`, `GET /system/status`.

---

## 10. Security Model

- **Auth**: JWT (RS256, audience `authenticated`) validated against Supabase JWKS, cached in memory (`core/security.py`). Mock mode accepts any token — **rejected at startup in production**.
- **Authorization**: project membership + role via `project_members` (checked in `get_project_id`, `assert_agent_in_project` uses 404 to avoid probing). Note: **RLS exists in `infra/schema.sql` but is not enforced locally** — SQLite dev ignores it; defense-in-depth is the FastAPI layer.
- **Input**: sanitization (`sanitize_input`, filename sanitization), prompt-injection pattern detection (`detect_injection`), MIME allowlist + 25 MB cap on uploads.
- **Rate limiting**: slowapi (30/min upload, 60/min chat, 10/min mock-login).
- **Secrets**: env files gitignored; service-role key never reaches the frontend bundle.
- **CORS**: explicit origins list (default `localhost:3000`).

---

## 11. Deployment Model

- **Frontend**: Vercel — build-time envs: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_MOCK_AUTH=false`, `NEXT_PUBLIC_APP_URL`.
- **Backend**: Railway/Render/Fly.io — `ENVIRONMENT=production`, `DATABASE_URL` → Postgres, Supabase keys, `LLM_*` + `EMBEDDING_*`, `CORS_ORIGINS` = frontend URL. Run `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- **DB**: Supabase cloud (`infra/schema.sql`), ChromaDB directory must be persistent volume.

---

## 12. Subsystem Audit — Real vs Stub (verified line-by-line)

Same audit done for MCP (§13), applied to every other major subsystem. **Legend:** ✅ real & wired · ⚠️ partial / broken wiring · ❌ missing · 🔸 planned-only.

### 12.1 Auth & OAuth — ✅ real, one bug

| Piece | Status | Evidence |
|---|---|---|
| Supabase JWT validation (RS256, JWKS cached) | ✅ | `core/security.py` |
| Mock auth (dev) + prod fail-fast | ✅ | `config.py` validator; `routers/auth.py` |
| Global middleware + public-route allowlist | ✅ | `core/auth_middleware.py` |
| Frontend: signin/signup pages, OAuth callback, demo-login, signout, middleware | ✅ | `src/app/auth/*`, `src/middleware.ts`, `src/lib/supabase/{client,server}.ts` |
| Project membership / role checks | ✅ | `core/deps.py`, `routers/projects.py` (rename owner/editor-only) |
| OAuth 2.0 client (client-credentials + PKCE + refresh + persistence) | ✅ | `core/oauth.py` — full-featured, generic |
| **Bug — rate limiter reads wrong state key:** `core/rate_limit.py::_rate_limit_key` reads `request.state.user`, but `GlobalAuthMiddleware` sets `request.state.user_id`. The key falls back to **IP for every authenticated user** (never `user:{id}`), so per-user limits don't work as intended | ⚠️ | `rate_limit.py` vs `auth_middleware.py` |
| **Nits:** `demo-login/route.ts` sets `mock-session` with `httpOnly:false`; `supabase/server.ts` mock user id is `"mock-user-001"` while backend mock id is `"a0eebc99-…"` — cosmetic mismatch, works because backend mock accepts any token | ⚠️ | `src/app/auth/demo-login/route.ts`, `src/lib/supabase/server.ts` |

### 12.2 Webhooks — ⚠️ outbound built, **scheduler missing, inbound half-broken**

| Piece | Status | Evidence |
|---|---|---|
| Outbound: subscriptions CRUD, `fire_event` on document.processed/failed, chat.completed, agent.completed/failed, entity.extracted | ✅ | `services/webhooks.py`, `routers/webhooks.py`; fired from `ingestion.py`, `chat.py`, `task_queue.py`, `entity_extraction.py` |
| HMAC-SHA256 signing + verification | ✅ | `_sign_payload`, `verify_inbound_signature` |
| Delivery log + retry schedule (1m/5m/30m, 3 attempts) | ✅ | `webhook_deliveries`, `dispatch_delivery` |
| **`dispatch_pending_deliveries` is never scheduled** — only a manual `POST /webhooks/retry-pending` (admin endpoint, no auth). Retries only happen when someone calls it | ⚠️ | callers = router only |
| **Inbound `ingest_document` handler is a stub** — downloads the file, then returns without creating a document or ingesting | ❌ | `_handle_ingest_document` (`# simplified for now`) |
| Inbound `mcp_receive` handler is functional (creates virtual doc → chunks → Chroma) | ✅ | `_handle_mcp_receive` |
| Inbound endpoint `POST /webhooks/inbound/{slug}` — **public, signature never verified in the router** (`verify_inbound_signature` exists but is unused), `mcp_receive`/`trigger_agent` accept any unauthenticated POST | ⚠️ | `routers/webhooks.py:inbound_webhook` |

### 12.3 Agents, Memory & Refinement — ✅ fully built

| Piece | Status | Evidence |
|---|---|---|
| LangGraph pipeline (6 agent types, trace, retry, tool-calling) | ✅ | `pipelines/agent_pipeline.py` |
| Tool registry (5 tools) + reserved-kwarg stripping + generic tool errors | ✅ | `pipelines/agent_tools.py` |
| Background execution + SSE trace streaming | ✅ | `core/task_queue.py`, `routers/agents.py` |
| Memory (working/episodic/semantic) + checkpoints + skills | ✅ | `services/memory.py`, models |
| Self-improvement: rule-based eval → run traces → refinement cycle → skills | ✅ | `pipelines/agent_refinement.py` |
| Cross-project memory sharing (read/read_write) + router | ✅ | `services/sharing.py`, `routers/sharing.py` |

### 12.4 Dashboard, Projects, Meetings — ✅ built (small gaps)

| Piece | Status | Evidence |
|---|---|---|
| Dashboard summary (real DB counts, activity from `audit_log`, pipeline health) | ✅ | `services/dashboard.py` |
| **`audit_log` is never written** — table + dashboard query exist, but no router/service/pipeline writes an entry (grep: zero `AuditLog(` writers) | ⚠️ | recent activity feed is **always empty** |
| Projects CRUD + membership | ✅ | `routers/projects.py` |
| Meetings: client-side recorder → `/meetings/analyze` (transcribe + summarize), sync stub, in-memory listing | ⚠️ | `routers/meetings.py`; results never enter the KB (§12.2) |

### 12.5 Search / RAG / Graph — ✅ fully built

| Piece | Status | Evidence |
|---|---|---|
| Semantic search (Chroma + Postgres enrichment) | ✅ | `services/knowledge.py` |
| Graph traversal (NetworkX k-hop subgraphs) | ✅ | `services/knowledge.py::get_graph` |
| RAG chat with 1-hop graph expansion + citations + SSE | ✅ | `services/chat.py` |

### 12.6 Migrations & Observability — ⚠️ gaps

| Piece | Status | Evidence |
|---|---|---|
| Alembic: config + `001_initial_schema.py` exist | ✅ | `migrations/` |
| **Alembic migration drift** — `001_initial_schema.py` is frozen at first-commit state; new tables (`agent_memory`, `agent_checkpoints`, `agent_skills`, `agent_run_traces`, `mcp_auth_tokens`, `webhook_*`, `project_memory_shares`, `inbound_webhooks`, `refinement_*`, `mcp_connections` changes) **were never added as migrations**; dev works only via `init_db.py` `create_all`, prod SQLite-vs-Postgres drift risk | ⚠️ | `migrations/versions/001_initial_schema.py` vs `db/models.py` |
| **`structlog` in requirements but unused** — no `request_id` threading anywhere (grep: zero imports); Sentry not configured; `api.log` exists | ⚠️ | `requirements.txt`, `main.py` |
| `core/errors.py` AppError hierarchy + handler | ✅ | used by routers |

### 12.7 Security hardening — ✅ built (two nits)

| Piece | Status | Evidence |
|---|---|---|
| Security headers (CSP, nosniff, frame-deny, permissions-policy) | ✅ | `core/security_headers.py` |
| Input sanitization + prompt-injection detection | ✅ | `core/security_utils.py` |
| Rate limits (upload 30/min, chat 60/min, mock-login 10/min) | ✅ (per-user key bug, §12.1) | `routers/*.py` |
| **CSP `connect-src` hardcodes `http://localhost:8000`** — breaks any deployed backend origin until edited | ⚠️ | `security_headers.py` |
| **`GET /documents/{id}/stream` SSE accepts token via `?token=` query param** — tokens can leak into access logs/proxies; documented EventSource limitation, but worth noting | ⚠️ | `routers/documents.py` |

---

## 13. MCP — What Exists, What Doesn't

MCP is a **major missing piece**: the database/CRUD/UI exists, but the actual MCP protocol layers were never built. This section separates what's real from what's only documented.

### 12.1 What MCP is supposed to do (brief + ADR-0004)

Two directions:

- **Sender** — this platform exposed as an MCP *server* so external AI clients (e.g. Claude Desktop) can call tools like `search_knowledge_base` over the MCP protocol.
- **Receiver** — this platform acting as an MCP *client* calling external MCP servers (e.g. Google Meet) to pull data into the knowledge base.

Per the MCP 2026-07-28 spec (ADR-0004): stateless core, Streamable HTTP transport, hardened OAuth 2.0 + PKCE.

### 12.2 What is ACTUALLY implemented (verified)

| Piece | Status | Where |
|---|---|---|
| `mcp_connections` + `mcp_auth_tokens` tables | ✅ Real | `apps/api/db/models.py` |
| Connection CRUD (list/create/update/delete/test) | ✅ Real | `routers/mcp.py`, `services/mcp.py` |
| OAuth 2.0 client: **client-credentials** + **authorization-code + PKCE**, token refresh, DB persistence | ✅ Real | `core/oauth.py` (306 lines) |
| PKCE endpoints: `/mcp/connections/{id}/authorize`, `/mcp/callback`, `/mcp/connections/{id}/token` | ✅ Real | `routers/mcp.py` |
| `POST /mcp/search` (REST endpoint calling `services/knowledge.search`) | ✅ Real | `routers/mcp.py`, `services/mcp.py` |
| MCP Connections UI (sender/receiver tabs, test/delete, Google Meet Sync button) | ✅ Real | `apps/web/src/app/mcp/page.tsx` |
| **A real MCP server (FastMCP)** — the sender that external clients would connect to | ❌ **Never existed** | no `FastMCP`/`mcp.server` imports anywhere; `apps/api/mcp/` contains only an empty `__init__.py` |
| **A real MCP client** (SDK `ClientSession` / tool calls / transcript pull) | ❌ **Never existed** | no `ClientSession` imports; grep finds nothing |
| `GET/POST/DELETE /mcp/tasks` (long-running task extension) | ❌ Planned only | ADR-0004 "Phase 2" |
| `POST /mcp/apps` (interactive app extension) | ❌ Planned only | ADR-0004 "Phase 3" |

**Verdict:** `core/oauth.py` is a complete, well-built OAuth *client library* (generic — it would work against any provider) and the REST CRUD is complete — but **nothing speaks the MCP protocol**. `test_connection` is just `GET endpoint_url` with an auth header, not an MCP handshake. `POST /mcp/search` is a plain REST endpoint, not an MCP tool served over the protocol. A reviewer who greps for `FastMCP` will find nothing.

**Root cause:** the OAuth/CRUD half was built as "MCP-adjacent" plumbing (commit `3ed35ff` "feat(mcp): upgrade to MCP 2026-07-28 spec — PKCE auth + token persistence") but the protocol half — `apps/api/mcp/server.py` / `client.py` (the files the build brief §9 explicitly requires) — was never written.

### 12.3 The gap in one diagram

```
BRIEF/ADR target:                    ACTUAL codebase:
                                   
external client ──MCP──► FastMCP    external client ──(nothing)──► ???
                         server                                   
                                   
external MCP ──MCP──► ClientSession apps/api/mcp/ = empty __init__.py
server          client              only OAuth lib + REST CRUD exists
                                    + Google Meet recorder (NOT MCP)
```

### 12.4 What's needed to complete it

1. **Sender (FastMCP server):** new `apps/api/mcp/server.py` exposing `search_knowledge_base`, `ask_question`, `list_documents`, `get_entity` tools (signatures defined in BUILD_BRIEF §9), mounted as an ASGI app (per ADR-0004, Streamable HTTP transport), auth: API key / OAuth per project, connection URL surfaced in the UI (currently absent — the page has no "connection URL / API key" display).
2. **Receiver (client):** new `apps/api/mcp/client.py` using the SDK's `ClientSession` + the existing `core/oauth.py` tokens to call external tools (e.g. Google Meet transcript) — then feed results into the ingestion pipeline (`file_type='meeting_transcript'` per brief §9).
3. **E2E test:** connect Claude Desktop / Claude Code to the dev server over stdio and confirm `search_knowledge_base` returns real data (brief's demo moment #5).
4. Wire Google Meet's current result (client-side recorder → `POST /meetings/analyze`) so transcripts actually enter the knowledge base — today `analyze` returns JSON to the UI only; `/meetings/sync` is a stub returning `{"status": "no_connection", ...}`.

---

## 14. Agents & Memory (Short Tour — the "extra" layer)

- **Agents** (`pipelines/agent_pipeline.py`): LangGraph `StateGraph` per agent type — `summarizer`, `extractor`, `qa`, `reviewer`, `researcher` (web search via DuckDuckGo), `google_meet` (legacy bot). Nodes: build prompt → maybe tool-call → LLM → evaluate → post-process; max 3 tool iterations, 3 retries; every step appended to a `trace` shown in the UI via SSE.
- **Agent tools** (`pipelines/agent_tools.py`): decorator registry — `web_search`, `search_chunks`, `get_entity`, `get_document_chunks`, `store_entities`. Reserved kwargs (`project_id`, `db`) are stripped from LLM-provided args (prompt-injection hardening); tool errors return generic text, never internal exception details.
- **Memory** (`services/memory.py`): three types — `working` (auto-expires ~24h), `episodic` (past runs), `semantic` (facts). Scoped by `(project_id, agent_id)`. Stored in `agent_memory`; injected into the next run's prompt as `_memory_context`.
- **Self-improvement** (`pipelines/agent_refinement.py`): rule-based score per run → `store_run_trace` (agent_run_traces) → `run_refinement_cycle` may generate a "skill" (agent_skills) or refinement log (refinement_logs) when held-in/held-out evals improve. Fully wired through `task_queue.py` + `routers/agents.py`.
- **Note:** the Google Meet *agent* type (`join_and_record` via Playwright CDP) is **legacy** per commit `bc29077` — the primary path is the **client-side recorder** (`POST /meetings/analyze`), which does NOT touch MCP at all.

---

## 15. Known Deviations from the Original Brief (Conscious)

1. **Neo4j → Postgres + NetworkX** (ADR-0001) — accepted, documented.
2. **ChromaDB over a dedicated vector store** (ADR-0002) — accepted.
3. **Supabase Auth over bespoke auth** (ADR-0003) — accepted.
4. **FastAPI BackgroundTasks → asyncio.create_task** — robustness fix (middleware was dropping background tasks; uploads stuck at `pending`).
5. **React Flow → reagraph** — swapped during graph UI build.
6. **Prisma removed from frontend** — backend API is the single data source.
7. **MCP 2026-07-28 spec** — stateless core, Streamable HTTP, OAuth 2.0 + PKCE (ADR-0004). **Partial:** OAuth/CRUD done; FastMCP server + MCP client never built (see §12).
8. **LLM provider** — OpenAI-compatible base URL pattern; Groq/Ollama interchangeable (README's hardcoded OpenAI/Ollama names are stale).
9. **Google Meet integration** — brief planned "MCP receiver pulls Meet transcripts"; reality is a **client-side recorder** (`POST /meetings/analyze`) with the Meet bot agent marked legacy, and `/meetings/sync` is a stub.
