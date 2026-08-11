# TODO — What's Left in the AI Knowledge Graph Builder

Actionable remaining work, ordered by demo value. Each item: **what**, **why**, **where**, **effort**. Verified against the current code (commit `8c72299`).

**Legend:** `[BUG]` broken/risky now · `[MISSING]` documented but absent · `[STALE]` docs/code mismatch · `[HARDEN]` polish/robustness · `[NICE]` stretch

---

## 1. Unfinished & Stale — Fix First (confuses people reading the repo)

### 1.1 Prisma — decide and clean up `[STALE]`
- **What happened:** Prisma was fully scaffolded in `4e780e5` (schema, migration, `prisma.config.ts`, `src/lib/prisma.ts`, `dev.db`) and **deleted in `8c72299`**. Dependencies, env vars, and docs remain.
- **Why it matters:** a reader finds `@prisma/client`, `DATABASE_URL="file:./dev.db"`, and skill docs and assumes Prisma is the DB — it isn't. See `docs/SPEC.md §5` for the full evidence.
- **Where:** `apps/web/package.json` (deps), `apps/web/.env`, `apps/web/.env.example`, `apps/web/.gitignore` (`/src/generated/prisma`), `README.md` §Tech Stack + §Project Structure.
- **Options:**
  - **A — Re-enable Prisma (frontend-local):** recreate `prisma/schema.prisma`, `prisma.config.ts`, `src/lib/prisma.ts` (all were in git history — recoverable). Use it for lightweight frontend data (settings, UI prefs). Needs `npx prisma migrate dev` to recreate `dev.db`.
  - **B — Remove Prisma entirely (recommended):** drop the 4 packages, the `DATABASE_URL` line from both env files, the `.gitignore` line; fix `README.md` (tech-stack table, structure tree, env table). The backend SQLAlchemy layer owns all data; frontend talks to the API.
- **Effort:** A: medium · B: small.

### 1.2 Stale README `[STALE]`
- **What:** README still claims Prisma/SQLite frontend DB, `llama3.1`/`gpt-4o-mini` LLM defaults, and the `apps/web/prisma/` directory.
- **Fix:** align with reality — SQLAlchemy/SQLite backend, Groq/Ollama OpenAI-compatible provider pattern, actual env tables (see `docs/SPEC.md §8`).

### 1.3 Stale root `akgb.db` `[STALE]`
- **What:** a committed SQLite file at repo root — leftover from an older backend run (the live dev DB is `apps/api/akgb.db`).
- **Fix:** delete (it's gitignored-adjacent cruft; verify nothing references it: `grep -r "akgb.db" apps/` first).

---

## 2. Real Implementation Gaps

### 2.1 MCP — the actual MCP protocol was never built `[MISSING]` — biggest demo risk
- **What exists:** `mcp_connections`/`mcp_auth_tokens` tables, connection CRUD, a full OAuth 2.0 client (`core/oauth.py` — client-credentials + PKCE + refresh + DB persistence), PKCE endpoints, `POST /mcp/search` (REST), and the MCP Connections UI.
- **What's missing:** a **real MCP server (FastMCP)** — grep `apps/api` for `FastMCP`/`mcp.server`: zero hits; `apps/api/mcp/` contains only an empty `__init__.py`. And a **real MCP client** — no `ClientSession` anywhere. `test_connection` is just `GET endpoint_url`; nothing speaks the MCP protocol. See `docs/SPEC.md §12`.
- **Why it matters:** demo moment #5 ("connect Claude Desktop → call `search_knowledge_base`") **cannot work today**. Also `docs/adr/004` promises Tasks/Apps extensions (Phases 2–3) that don't exist.
- **Fix:**
  1. `apps/api/mcp/server.py` — FastMCP server exposing `search_knowledge_base`, `ask_question`, `list_documents`, `get_entity` (signatures in BUILD_BRIEF §9); mount as ASGI app (Streamable HTTP per ADR-0004); per-project API key/OAuth auth.
  2. `apps/api/mcp/client.py` — SDK `ClientSession` + `core/oauth.py` tokens to call external MCP servers.
  3. UI: show the sender connection URL / API key on the MCP page (currently absent).
  4. E2E: connect Claude Desktop to the dev server, verify `search_knowledge_base` returns real data.
- **Effort:** large (days) — biggest remaining feature.

### 2.2 Google Meet results never enter the knowledge base `[MISSING]`
- **What:** `POST /meetings/analyze` transcribes + summarizes client-recorded audio and returns JSON **to the UI only** — it never creates a `documents` row or feeds the ingestion pipeline. `/meetings/sync` is a stub returning `{"status": "no_connection", ...}`.
- **Fix (per brief §9):** tag it `file_type='meeting_transcript'` and push into the normal ingestion pipeline.
- **Effort:** medium.

### 2.3 Supabase Storage for uploaded files `[MISSING]` — highest demo risk
- **What:** `POST /documents` computes `storage_path` and inserts a `documents` row, but the file bytes are **never persisted** — only held in memory during ingestion. `services/documents.py` even carries `# TODO: Upload to Supabase Storage (Phase 1 step: add storage client)`.
- **Consequences:** document detail page can't show the original file; deleting a document doesn't free anything; `POST /documents/{id}/retry` requires the client to re-upload the file (a 400 if not sent).
- **Fix:** add `supabase` storage client usage — upload bytes to private bucket at `projects/{project_id}/documents/{doc_id}/`, serve via short-lived signed URLs, delete on `DELETE /documents/{id}`.
- **Effort:** medium.

### 2.12 RLS not actually enforced `[HARDEN]`
- **What:** `infra/schema.sql` defines row-level security policies keyed off `project_members`, but the app talks to the DB with full access (SQLite dev ignores RLS entirely; prod uses the backend's connection, not anon/service-role client).
- **Fix:** document the RLS story accurately; optionally verify policies on Supabase. Backend membership checks are the current real enforcement (fine for MVP, but the brief promised RLS as first-line defense).
- **Effort:** small (doc) / medium (verify).

### 2.13 Rate limiter per-user key bug `[BUG]` — easy win
- **What:** `core/rate_limit.py::_rate_limit_key` reads `request.state.user`, but `GlobalAuthMiddleware` sets `request.state.user_id`. Result: every authenticated request is keyed by **IP**, so per-user limits (30/min upload, 60/min chat) effectively become per-IP.
- **Fix:** read `request.state.user_id` (fall back to IP for anonymous routes). Add a test asserting two users get separate buckets.
- **Effort:** tiny (one line + test).

### 2.14 Webhook scheduler missing + inbound half-broken `[MISSING]`
- **What:** outbound webhooks are real (signing, retries, delivery log), but `dispatch_pending_deliveries` is **never scheduled** — retries only run on a manual, unauthenticated `POST /webhooks/retry-pending`. Inbound `ingest_document` handler is a stub (downloads, then nothing); the public `POST /webhooks/inbound/{slug}` endpoint **never verifies the HMAC signature** (`verify_inbound_signature` is dead code) — any unauthenticated POST can trigger `mcp_receive`/`trigger_agent` and write to the KB.
- **Fix:** schedule retry dispatch (background loop or on-startup task); implement `_handle_ingest_document`; require `X-Webhook-Signature` verification on the inbound route.
- **Effort:** small–medium.

### 2.15 `audit_log` never written `[MISSING]`
- **What:** the dashboard's "recent activity" reads `audit_log`, but nothing writes it (grep for `AuditLog(` writers: zero). The activity feed is **always empty**.
- **Fix:** add a small `audit` helper and call it on mutating actions (document upload/delete, chat send, agent run, project create, share grant…), or drop the feed.
- **Effort:** small.

### 2.16 Alembic migrations frozen at first commit `[HARDEN]`
- **What:** `migrations/001_initial_schema.py` predates ~10 tables (agent_memory, checkpoints, skills, run_traces, mcp_auth_tokens, webhook_*, project_memory_shares, inbound_webhooks, refinement_*) added since. Dev works only because `init_db.py` runs `create_all`; any Postgres deploy via `alembic upgrade head` gets a **stale schema**.
- **Fix:** regenerate the initial migration (or add follow-ups) to match `db/models.py`; verify `alembic upgrade head` against Postgres.
- **Effort:** small–medium.

### 2.17 Observability: structlog unused, no request_id `[HARDEN]`
- **What:** `structlog` is in requirements but zero imports; no request-id threading; Sentry not configured.
- **Fix:** wire structlog + a middleware that stamps `request_id` onto logs (brief §12 asks for this); or drop the dep.
- **Effort:** small–medium.

### 2.18 CSP hardcodes `localhost:8000` `[HARDEN]`
- **What:** `core/security_headers.py` sets `connect-src 'self' http://localhost:8000` — breaks a deployed backend origin until edited.
- **Fix:** derive from settings (`CORS_ORIGINS` / an API URL setting).
- **Effort:** tiny.

### 2.19 Frontend unit tests `[MISSING]`
- **What:** brief requires Vitest + React Testing Library; `vitest`, `@testing-library/react`, `@testing-library/jest-dom` sit in devDependencies with a `vitest.config.ts` — **zero test files** (`apps/web/src` has none).
- **Fix:** add Vitest config usage + a first test suite (stores, validators, api client helpers).
- **Effort:** medium.

### 2.20 LLM provider consistency `[HARDEN]`
- **What:** chat (`services/chat.py`) and entity extraction (`entity_extraction.py`) **hardcode** `model="llama-3.3-70b-versatile"` instead of using `settings.LLM_MODEL`; reasoning-model note (qwen3.6-27b burns tokens in `<think>` blocks) is a code-comment workaround.
- **Fix:** make the chat/extraction model configurable (`LLM_CHAT_MODEL` / `LLM_EXTRACT_MODEL`), keep the fast-model default for chat UX.
- **Effort:** small.

### 2.21 Error handling for SSE in UI `[HARDEN]`
- **What:** chat page treats a non-OK `/messages` response as a generic failure; backend errors during stream are caught, but mid-stream network drops show only the generic message. Document-status SSE has keepalives but no client-side reconnection.
- **Fix:** surface `ApiRequestError` details in chat; add SSE reconnect/backoff on the documents page.
- **Effort:** small–medium.

---

## 3. Build-Brief Items Not Yet Done

### 3.1 Load testing `[MISSING]`
- Locust/k6 harness for concurrent uploads + chat (p50/p95/p99). Brief §11.

### 3.2 Retrieval quality eval harness `[MISSING]`
- Hand-labeled Q/A pairs against fixture docs; recall@k, citation precision, hallucination spot-check. Brief §11 — a strong viva talking point.

### 3.3 Security test pass `[MISSING]`
- Prompt-injection fixture doc test, auth-bypass attempts, oversized/disallowed file types, rate-limit verification. (Some tests exist under `apps/api/tests/` — e.g. `test_security_utils.py` — but the full pass is unverified.)

### 3.4 Observability `[HARDEN]`
- `structlog` is in requirements but verify JSON logging + `request_id` threading is actually wired; Sentry not configured.

### 3.5 Chroma index cleanup on document delete `[HARDEN]`
- `delete_document_chunks` exists in `pipelines/embeddings.py` — confirm `DELETE /documents/{id}` actually calls it (documents service currently only deletes the row; entities/relationships/mentions cleanup also unverified).

---

## 4. Known Bugs / Robustness Notes (from code comments & commits)

- **`[BUG]` Background task GC:** fixed pattern (strong refs) but every new background path must keep it (`task_queue.py`, `documents.py` comments).
- **`[BUG]` Request-session reuse:** background tasks must open their own session via `async_session_factory` — request sessions die with the response (fix already applied to ingestion; keep pattern for new tasks).
- **`[HARDEN]` `get_document_chunks` truncates text to 200 chars** — fine for lists, but the document detail page may need full text.
- **`[HARDEN]` Entity-chunk dedup on the graph page** keys on `filename|page` — chunk-level duplicates after re-processing are intentionally collapsed; verify it doesn't hide real distinct sections.
- **`[NICE]` Prisma skill docs under `apps/web/.agents/skills/prisma-*`** (also `.claude/`, `.continue/`, `.windsurf/`) — if Prisma is removed, these stay (they're skill docs), but `apps/web/.gitignore`'s `/src/generated/prisma` line should go.

---

## 5. Suggested Order (Demo-first)

| Priority | Item | Why |
|---|---|---|
| P0 | **2.1 MCP protocol (FastMCP server + client)** | demo moment #5 (Claude Desktop → `search_knowledge_base`) is impossible today; also ADR-0004 Phases 2–3 |
| P0 | **2.3 Supabase Storage** | upload→preview→delete loop is a demo moment; currently the file vanishes after processing |
| P0 | **1.1 Prisma decision + cleanup** | repo coherence for the viva; do B unless you want frontend-local state |
| P0 | **1.2 README refresh** | docs match reality when the evaluator reads them |
| P1 | **2.2 Meet results into KB** | turns the meeting recorder from a demo gadget into an ingestion source |
| P1 | **2.13 rate-limiter fix** | one line; viva question "does rate limiting actually work per user?" |
| P1 | **2.15 `audit_log` writers** | dashboard activity feed is empty; dashboard is demo moment #1 |
| P1 | **2.14 webhook scheduler + inbound auth** | unauthenticated inbound webhook can write to the KB — real risk |
| P1 | 3.2 Retrieval eval harness | strongest technical talking point |
| P1 | 2.20 LLM model config | removes hardcoded model + reasoning-model hazard |
| P1 | 4 bug list sweep (delete cleanup, chunk text, SSE reconnect) | robustness questions in viva |
| P2 | 2.16 Alembic migrations, 2.17 structlog, 2.18 CSP, 2.19 frontend tests, 3.1 load test, 3.3 security pass | brief compliance + hardening |
| P2 | 3.4 observability | nice-to-have |
| P2 | 1.3 root akgb.db removal | tidy-up |

---

## 6. How to Verify Each Fix

- Prisma removal: `cd apps/web && grep -ri prisma src/` → no matches; `npx tsc --noEmit` passes.
- Storage: upload → check Supabase bucket via dashboard → delete doc → bucket emptied.
- LLM config: set `LLM_CHAT_MODEL` → chat streams with it (no `<think>` stall).
- Tests: `cd apps/api && python -m pytest tests/ -v`; `cd apps/web && npx vitest run` (once tests exist).
- E2E: `cd apps/web && npx playwright test` (chromium installed).
