# TODO — What's Left in the AI Knowledge Graph Builder

Actionable remaining work, ordered by demo value. Each item: **what**, **why**, **where**, **effort**. Verified against current code (commit `f97533e` — code at `bb97cbf` + docs sync; Prisma removal/build-brief fixes pending verification). Prior commit was `8c72299`. Research health sync `2026-09-03` adds §2.22–§2.28 + §3.6 based on Docs2KG / GraphRAG / Zep / TempAgent / Jarnac 2025 / FactGenius / Kolli et al. gap analysis and pinned/protected proposal — full URLs in `docs/RESEARCH_PROBLEM.md §11`.

**Legend:** `[BUG]` broken/risky now · `[MISSING]` documented but absent · `[STALE]` docs/code mismatch · `[HARDEN]` polish/robustness · `[NICE]` stretch · `[RESEARCH]` research contribution (not required for BUILD_BRIEF demo, required for hypothesis test)

---

## 1. Unfinished & Stale — Fix First (confuses people reading the repo)

### 1.1 Prisma — decide and clean up `[STALE]` ✅ DONE — Option B executed (this sync)
- **What happened:** Prisma was fully scaffolded in `4e780e5` (schema, migration, `prisma.config.ts`, `src/lib/prisma.ts`, `dev.db`) and **deleted in `8c72299`**. Dependencies, env vars, and docs remained until this sync.
- **Why it mattered:** a reader found `@prisma/client`, `DATABASE_URL="file:./dev.db"`, and skill docs and assumed Prisma is the DB — it wasn't. See `docs/SPEC.md §5` for the full evidence.
- **Fix applied:** **Option B — Remove Prisma entirely:** removed `@prisma/client`, `@prisma/adapter-better-sqlite3`, `prisma`, `better-sqlite3`, `@types/better-sqlite3` from `apps/web/package.json`, `DATABASE_URL` from `apps/web/.env.example`, `/src/generated/prisma` from `apps/web/.gitignore`, and `prisma/` references + LLM env tables from `README.md` and `docs/HOW_IT_WORKS.md`. `BUILD_BRIEF.md` Graph visualization and Chroma metadata also corrected (`React Flow → reagraph`, `chunk_id → chunk_index`).
- **Where:** `apps/web/package.json`, `apps/web/.env.example`, `apps/web/.gitignore`, `README.md`, `docs/HOW_IT_WORKS.md`, `BUILD_BRIEF.md`.
- **Verified:** `grep -r prisma apps/web/src → 0`, `grep -E prisma apps/web/package.json → 0`, `grep DATABASE_URL apps/web/.env.example → 0`.

### 1.2 Stale README `[STALE]` ✅ DONE — fixed in this sync
- **What was:** README claimed Prisma/SQLite frontend DB, `llama3.1`/`gpt-4o-mini` LLM defaults, and the `apps/web/prisma/` directory.
- **Fix applied:** tech-stack DB row → `PostgreSQL prod / SQLite dev forced via ENVIRONMENT`, Vector Store → `PersistentClient single knowledge_base`, LLM → `OpenAI-compatible qwen/qwen3.8-27b`; LLM Provider block → Groq/Ollama examples with `LLM_CHAT_MODEL`/`EMBEDDING_*`; `lib/` prisma reference removed; `prisma/` tree removed; backend/frontend env tables rewritten to match `core/config.py` (see `docs/SPEC.md §8`).
- **Where:** `README.md`, `apps/web/.env.example`, `docs/HOW_IT_WORKS.md`, `BUILD_BRIEF.md`.

### 1.3 Stale root `akgb.db` `[STALE]` — verified absent
- **What:** was a committed SQLite file at repo root in older runs (live dev DB is `apps/api/akgb.db`, now gitignored via `*.db`). `find . -name "*.db"` and `git ls-files | grep db` both return empty — no committed file exists today.
- **Fix:** no deletion needed; verify and close. Keep `*.db` in `.gitignore`.

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

### 2.13 Rate limiter per-user key bug `[BUG]` ✅ DONE — PR #1 merged (`a030a0d`)
- **What was:** `core/rate_limit.py::_rate_limit_key` read `request.state.user`, but `GlobalAuthMiddleware` sets `request.state.user_id`. Result: every authenticated request was keyed by **IP**.
- **Fix applied:** now reads `request.state.user_id` (see `apps/api/core/rate_limit.py:16`) with `ip:` fallback; added `apps/api/tests/test_rate_limit.py` (per-user vs per-IP buckets).
- **PR:** #1 `fix: use user id for rate limiting` — `task-2.13-rate-limiter` → `main`.
- **Effort:** tiny (one line + test) — completed.

### 2.14 Webhook scheduler missing + inbound half-broken `[MISSING]`
- **What:** outbound webhooks are real (signing, retries, delivery log), but `dispatch_pending_deliveries` is **never scheduled** — retries only run on a manual, unauthenticated `POST /webhooks/retry-pending`. Inbound `ingest_document` handler is a stub (downloads, then nothing); the public `POST /webhooks/inbound/{slug}` endpoint **never verifies the HMAC signature** (`verify_inbound_signature` is dead code) — any unauthenticated POST can trigger `mcp_receive`/`trigger_agent` and write to the KB.
- **Fix:** schedule retry dispatch (background loop or on-startup task); implement `_handle_ingest_document`; require `X-Webhook-Signature` verification on the inbound route.
- **Effort:** small–medium.

### 2.15 `audit_log` never written `[MISSING]` ✅ DONE — PR #2 merged (`d5ff01f`)
- **What was:** dashboard's "recent activity" read `audit_log`, but nothing wrote it.
- **Fix applied:** added `apps/api/services/audit.py::write_audit_log` and wired it into project create (`routers/projects.py:136`), document upload/delete (`routers/documents.py:113,220`), share grant (`services/sharing.py:52,75`), chat `send_message` (`services/chat.py:373` + `services/audit.py`); `apps/api/tests/test_audit.py` added.
- **PR:** #2 `feat: add audit logging` — `task-2.15-audit-log` → `main`.
- **Effort:** small — completed.

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

### 2.20 LLM provider consistency `[HARDEN]` ✅ DONE — PR #3 merged (`b98d6d9` + `85a3567`)
- **What was:** chat (`services/chat.py`) and entity extraction (`pipelines/entity_extraction.py`) hardcoded `model="llama-3.3-70b-versatile"` instead of using settings; note about qwen reasoning tokens was a comment workaround.
- **Fix applied:** made configurable via `LLM_CHAT_MODEL` / `LLM_EXTRACT_MODEL` in `apps/api/core/config.py:44-45` (default `qwen/qwen3.8-27b`), updated `services/chat.py:349` and `pipelines/entity_extraction.py:136`, added `apps/api/.env.example` entries and `apps/api/tests/test_llm_config.py`.
- **PR:** #3 `feat: make llm models configurable` — `task-2.20-configurable-llm` → `main` (follow-up `85a3567 fix review feedback for llm config and comments`).
- **Effort:** small — completed.

### 2.21 Error handling for SSE in UI `[HARDEN]`
- **What:** chat page treats a non-OK `/messages` response as a generic failure; backend errors during stream are caught, but mid-stream network drops show only the generic message. Document-status SSE has keepalives but no client-side reconnection.
- **Fix:** surface `ApiRequestError` details in chat; add SSE reconnect/backoff on the documents page.
- **Effort:** small–medium.

### 2.22 Knowledge Health Mechanism — continuous reliability `[MISSING]` `[RESEARCH]` — core gap
- **What exists:** ingestion is append-only `pipelines/ingestion.py:46` `parse→chunk(600/80)→embed→store chunks→extract entities/relations→processed` (`pipelines/entity_extraction.py:240`). `EntityMention.confidence 0.8` and `Relationship.confidence 0.7` are hardcoded constants (`pipelines/entity_extraction.py:339,368`); `services/knowledge.py:135` loads all `entities`/`relationships` into `nx.DiGraph` per request with no filter; `services/chat.py:263` retrieval is `top_k=8` vector → entity mention → 1-hop expand — no health check. No `conflict`/`stale`/`disputed` concept anywhere (grep `conflict|stale|health.*entity` → 0 outside `services/dashboard.py:112` pipeline health).
- **Why it matters:** Papers solve pieces (see `docs/RESEARCH_PROBLEM.md §11` URLs: Docs2KG→KG, GraphRAG→retrieval, Zep/Graphiti→temporal KG memory, TempAgent→temporal QA, Jarnac 2025 https://drops.dagstuhl.de/entities/document/10.4230/TGDK.3.1.3 →uncertainty survey, FactGenius https://aclanthology.org/2024.fever-1.30/ + Kolli https://aclanthology.org/2025.winlp-main.19/ →KG fact verification) but none jointly handle **heterogeneity + update + contradiction + staleness together** before a stateless agent retrieves. Current system is `Documents → KG (assumed reliable) → Agent`. `docs/RESEARCH_PROBLEM.md:67` research question and `§4 Build→Monitor→Verify→Repair` loop are unimplemented — hypothesis `§7` (“evidence-backed, continuously validated KG > conventional RAG when conflicting/outdated”) is untestable without this.
- **Fix (minimal additive, reuse `async_session_factory` + strong `asyncio.Task` refs `core/task_queue.py`):**
  1. Define health signals formally: `evidence_coverage` (sentences supporting edge), `contradiction_group` (same `(source,target)` incompatible `relation_type`), `temporal_validity` (`valid_until`), `confidence` (calibrated, not constant), `source_reliability` (`documents.uploaded_by`/type).
  2. Add `knowledge_health_checks` table `id, project_id, entity_id|relationship_id, issue_type enum(conflict|stale|invalid|low_evidence), severity, evidence_json, status enum(open|requires_review|resolved), created_at` + extend `entities`/`relationships` with `health_status enum(asserted|disputed|stale|deprecated)`, `verification_status enum(unverified|supported|contradicted)`.
  3. Note: do NOT claim `stateless` or generic `self-healing` as novelty (`docs/RESEARCH_PROBLEM.md:118`); novelty is joint health scoring + repair before retrieval.
- **Where:** new `pipelines/kg_health.py` + `services/knowledge_health.py` + `pipelines/health_scanner.py`; migration in `2.16`; see `docs/SPEC.md §12` audit for insertion points.
- **Effort:** large (days) — gated by `2.16` + `2.24`.

### 2.23 Pinned / Protected knowledge tag `[MISSING]` `[RESEARCH]` — your proposal
- **What:** No way to mark important facts as human-verified. Today newer noisy doc could silently supersede a curated fact because recency/`valid_until` would win if implemented.
- **Why it matters:** For `Q4 Revenue = $5.2M` style facts, auto-overwrite is hazardous. User asked for `unchange`/`important` tag that only allows overwrite on **conflict + explicit user Accept**, never on outdated alone. This makes health `human-gated` not fully autonomous — correct for evaluation integrity.
- **Fix (conflict-only overwrite, not staleness):**
  - Schema: `entities`/`relationships` add `is_pinned bool default false`, `pinned_by uuid FK profiles.id`, `pinned_at timestamptz`, `pinned_reason text` (e.g., “Board-approved”). Only `owner`/`editor` (`project_members.role` `db/models.py:73`, `core/deps.py:get_project_id`) may pin; pin/unpin writes `audit_log` via `services/audit.py`.
  - Logic: post-extraction nudge `pipelines/ingestion.py:136` groups `(source,target)` → if `is_pinned` in group → emit `knowledge_health_checks {issue_type=conflict, status=requires_review}` instead of auto `superseded_by`; periodic scanner `services/knowledge_health.py` **exempts pinned** from stale auto-retire (flag `stale` for visibility only, never auto `deprecated`).
  - UX: dashboard/graph “Requires Review” inbox shows `Pinned "X works_at Y (doc A p.3)" vs New "X works_at Z (doc B p.1)"` with sentence evidence; actions `Keep pinned / Overwrite pinned / Keep both as disputed`. Overwrite → `UPDATE … superseded_by=old_id, last_validated_at=now(), verification_status=supported` + old row `deprecated` (monotonic). Keep → new edge `disputed/contradicted`. Avoid chat-time blocking.
  - Guard: warn if >5% entities pinned; require `pinned_reason`; show `pinned_count` trend in dashboard.
- **Where:** `db/models.py`, `pipelines/kg_health.py`, `services/knowledge_health.py`, `apps/web/src/app/graph/page.tsx` + dashboard review queue.
- **Effort:** small (schema+branch) but must ship before any auto-supersede logic in `2.22`.

### 2.24 Sentence-level evidence linking `[MISSING]` `[RESEARCH]`
- **What:** Citations today are block-level `chat_messages.citations JSON {index, chunk_id(chroma_id), document_id, filename, page_number}` (`db/models.py:171`, `services/chat.py:219` `text[:800]` truncation) and `entity_mention.chunk_id` chunk-level (~600 tokens). Not sentence provenance. `docs/RESEARCH_PROBLEM.md:114` explicitly calls this the trust pivot.
- **Why it matters:** Jarnac `uncertainty` + FactGenius `evidence verification` both need per-sentence → chunk/char-range mapping to judge support; current `citation precision` metric unmeasurable.
- **Fix:** `entity_mentions` add `span_start int, span_end int, sentence_text text, extraction_source enum(spacy|llm|both)`; add `relationship_evidence` M2M `relationship_id, chunk_id, evidence_type enum(supporting|contradicting), sentence_span int4range, created_at PK(relationship_id,chunk_id)` to complement `relationships.source_document_id` (currently doc-level only). `pipelines/entity_extraction.py:90 EXTRACT_PROMPT` must ask LLM for `evidence_sentence` + `char_span`; spacy pass provides `ent.text` as fallback. `document_chunks.section_index` (`db/models.py` exists but never written in `pipelines/chunking.py`) fix to populate.
- **Where:** `db/models.py`, `pipelines/entity_extraction.py`, `pipelines/chunking.py`, `services/knowledge.py:222 get_entity_chunks`, `services/chat.py:219 _format_source_block`.
- **Effort:** medium (prompt+schema+ingestion plumbing).

### 2.25 Temporal validity & stale detection `[MISSING]` `[RESEARCH]`
- **What:** No `valid_from/valid_until/last_seen_at/updated_at` on `entities`/`relationships`; `created_at` is insertion-only; `documents.uploaded_at/processed_at` exist but not propagated to KG freshness; no `document.effective_date` (doc-internal date vs ingestion date). Cannot answer “is this knowledge stale?” TempAgent/TempQA show temporal QA alone is not novelty — joint use as health signal is.
- **Fix:** `relationships` add `valid_from timestamptz, valid_until timestamptz, last_seen_at timestamptz default now(), updated_at timestamptz, superseded_by uuid FK relationships.id`; `documents` add `effective_date timestamptz, supersedes_document_id uuid FK documents.id, version int`; Chroma metadatas `+created_at, embedding_model`. Scanner flags `valid_until < now → stale` + `document supersession chain`; but **pinned exempt** per `2.23`. Never auto-delete — `deprecated` with reason.
- **Where:** `db/models.py`, `pipelines/kg_health.py`, `infra/schema.sql` (via Alembic).
- **Effort:** medium — requires LLM date normalization + doc version UX.

### 2.26 Source reliability scoring `[HARDEN]` `[RESEARCH]`
- **What:** No `documents.source_type` (upload vs OCR vs `meeting_transcript` `2.2`) / `source_trust_score` / `uploader_reputation`; `uploaded_by` stored but not scored; all sources weighted equal. `Relationship.confidence` never calibrated by source count vs quality.
- **Fix:** `documents` add `source_reliability float default 1.0` + `source_type text`; health score = `confidence * evidence_count * source_reliability * temporal_decay`. Calibrate LLM to emit per-edge confidence in `EXTRACT_PROMPT` instead of hardcoded `0.7`; spacy `0.8` replaced with length/context-aware score.
- **Where:** `db/models.py`, `pipelines/entity_extraction.py:339,368`, `pipelines/embeddings.py:105` ranking (future).
- **Effort:** small.

### 2.27 Health scanner & RAG verification gate `[MISSING]` `[RESEARCH]`
- **What:** No monitor→verify→repair loop. `docs/RESEARCH_PROBLEM.md:79` diagram `Build→monitor→detect(Conflict|Stale|Invalid)→Evidence Check→Repair/Reject→KG→Agent` has no code.
- **Fix (3 insertion points, minimal churn):**
  1. **Post-extraction nudge (inline):** after `pipelines/ingestion.py:136` `extract_entities_from_chunks()` success → `pipelines/kg_health.py:enqueue_check(document_id, project_id)` for `confidence<0.5 && mention_count==1` invalid, `(source,target)` group differing `relation_type` conflict, overlapping entities with newer `uploaded_at` stale.
  2. **Periodic scanner (background loop at startup):** `services/knowledge_health.py` + `pipelines/health_scanner.py` scheduled via `asyncio.create_task` strong refs (`core/task_queue.py` pattern) scanning `Relationship GROUP BY (source,target)` → `CONFLICT`, `last_seen_at < now-90d` → `STALE`, pinned exempt.
  3. **Retrieval-time verifier (RAG gate):** between `services/chat.py:263 query_chunks(top_k=8)` → `_get_entity_context` → `_expand_via_graph(1 hop)` and prompt assembly, filter `score` outliers, tag `citations[].trust="disputed"|"pinned"`; SYSTEM_PROMPT `services/chat.py:21` add conflict surfacing instruction (today `Answer ONLY based on sources` with no conflict handling).
- **Where:** `pipelines/ingestion.py`, `services/chat.py:263-272`, `core/task_queue.py` scheduling, `services/knowledge.py`.
- **Effort:** medium (2–3d) — depends on `2.22`/`2.24`.

### 2.28 Knowledge health dashboard surface `[MISSING]` `[RESEARCH]`
- **What:** `services/dashboard.py:112` only `pipeline_health {queue_depth, failed_count, success_rate}` + `failed_documents[:5]`; no KG health. `audit_log` writers exist (PR #2) but no `kg.health_detected/kg.repaired/kg.pinned` events.
- **Fix:** extend `GET /dashboard/summary` with `knowledge_health {total_entities, orphan_entities(0 mentions), dangling_relationships, avg_confidence, conflict_pairs, stale_pinned_pending, last_scan_at, trend}` backed by `knowledge_health_checks`; add review inbox table in UI; wire `audit_log` writes for pin/unpin/repair.
- **Where:** `services/dashboard.py`, `apps/web/src/app/dashboard/page.tsx`, `services/audit.py`.
- **Effort:** small.

---

## 3. Build-Brief Items Not Yet Done

### 3.1 Load testing `[MISSING]`
- Locust/k6 harness for concurrent uploads + chat (p50/p95/p99). Brief §11.

### 3.2 Retrieval quality eval harness `[MISSING]` — blocks any research claim
- Hand-labeled Q/A pairs against fixture docs; recall@k, citation precision, hallucination spot-check. Brief §11 — a strong viva talking point. `docs/RESEARCH_PROBLEM.md:189` warns no defensible measurement without it.
- **Note:** `3.2` stays the *base RAG* harness (current `top_k=8` + graph expansion). Health comparison builds on it in `3.6`.

### 3.3 Security test pass `[MISSING]`
- Prompt-injection fixture doc test, auth-bypass attempts, oversized/disallowed file types, rate-limit verification. (Some tests exist under `apps/api/tests/` — e.g. `test_security_utils.py` — but the full pass is unverified.)

### 3.4 Observability `[HARDEN]`
- `structlog` is in requirements but verify JSON logging + `request_id` threading is actually wired; Sentry not configured.

### 3.5 Chroma index cleanup on document delete `[HARDEN]`
- `delete_document_chunks` exists in `pipelines/embeddings.py` — confirm `DELETE /documents/{id}` actually calls it (documents service currently only deletes the row; entities/relationships/mentions cleanup also unverified). Deletion currently leaks vectors/entities (`services/documents.py:123` only `db.delete(doc)` — no `delete_document_chunks` nor orphan `entities`/`relationships` pruning; retry stacks duplicates — see SPEC audit).

### 3.6 Research benchmark — controlled health evaluation `[MISSING]` `[RESEARCH]` — paper's core
- **Why:** Without this, `2.22`/`2.23` cannot be shown to beat conventional RAG. User’s gap analysis explicitly calls for a controlled benchmark: same documents → `Normal RAG vs Our System (+health)`.
- **Fix:** Build 20–30 fixture docs injecting 5 types: `update` (supersedes), `contradiction` (same `(source,target)` incompatible `relation_type`), `stale` (old date superseded by newer), `duplicate` (same fact multi-doc support), `uncertain/low-evidence` (single mention, OCR-noisy) — reuse `research/` pattern (`research/indian_protests_2026.txt`).
- Hand-label 15–20 Q/A pairs with `expected_answer + supporting chunk_id/page + relation_ids` (extend `3.2` fixture set). Add `eval/kg_health_eval.py` alongside `eval/retrieval_harness.py`.
- **Baselines:** plain RAG (no graph), current GraphRAG (no health — `services/chat.py:169` 1-hop), +health (`2.27` gate). Optional Zep citation baseline but not re-implemented.
- **Metrics:** `recall@k`, `citation precision` (sentence-level via `2.24`), `evidence correctness`, `contradiction detection P/R`, `stale detection P/R`, `false-positive retire rate`, `factual accuracy (LLM-as-judge)`, `latency`, `cost`; gate acceptance `held_in_delta>0 && held_out_delta>=0` (`pipelines/agent_refinement.py:280` pattern).
- **Ablations:** w/o temporal, w/o contradiction, w/o evidence, w/o source reliability, w/o pinned — shows joint value.
- **Where:** `apps/api/eval/` + `research/fixtures/`; consumes `refinement_eval_sets` (`db/models.py`) or new `kg_eval_runs`.
- **Effort:** medium (2–3d) — depends on `2.24`; strongest demo after `2.22`.

---

## 4. Known Bugs / Robustness Notes (from code comments & commits)

- **`[BUG]` Background task GC:** fixed pattern (strong refs) but every new background path must keep it (`task_queue.py`, `documents.py` comments).
- **`[BUG]` Request-session reuse:** background tasks must open their own session via `async_session_factory` — request sessions die with the response (fix already applied to ingestion; keep pattern for new tasks).
- **`[HARDEN]` `get_document_chunks` truncates text to 200 chars** — fine for lists, but the document detail page may need full text.
- **`[HARDEN]` Entity-chunk dedup on the graph page** keys on `filename|page` — chunk-level duplicates after re-processing are intentionally collapsed; verify it doesn't hide real distinct sections.
- **`[NICE]` Prisma skill docs under `apps/web/.agents/skills/prisma-*`** (also `.claude/`, `.continue/`, `.windsurf/`) — if Prisma is removed, these stay (they're skill docs), but `apps/web/.gitignore`'s `/src/generated/prisma` line should go.
- **`[HARDEN]` Delete/retry leaks KG state:** `DELETE /documents/{id}` does not call `pipelines/embeddings.py:177 delete_document_chunks` nor prune orphan `entities`/`relationships`/`mentions`; `POST /documents/{id}/retry` resets `status=pending` but never `DELETE FROM document_chunks WHERE document_id=...` — stacks duplicates. `Chroma upsert` is idempotent via `chroma_id` but Postgres diverges. Must handle pinned exempt.

---

## 5. Suggested Order (Demo-first)

| Priority | Item | Why |
|---|---|---|
| P0 | **2.1 MCP protocol (FastMCP server + client)** | demo moment #5 (Claude Desktop → `search_knowledge_base`) is impossible today; also ADR-0004 Phases 2–3 |
| P0 | **2.3 Supabase Storage** | upload→preview→delete loop is a demo moment; currently the file vanishes after processing |
| P0 | **1.1 Prisma decision + cleanup** | repo coherence for the viva; do B unless you want frontend-local state |
| P0 | **1.2 README refresh** | docs match reality when the evaluator reads them |
| P1 | **2.16 Alembic migrations regenerated** | `2.22–2.28` all need migrations; prod deploy via `alembic upgrade head` is stale until fixed |
| P1 | **2.24 Sentence-level evidence** | provenance foundation for health + citation precision; unblocks `3.6` measurability |
| P1 | **2.22 Knowledge Health Mechanism + 2.23 Pinned tag** | research core — joint signal before retrieval; pinned must ship first to avoid auto-overwrite hazard |
| P1 | **3.2 Base retrieval eval harness** | without it no reliability claim is defensible (`docs/RESEARCH_PROBLEM.md:189`) |
| P1 | **3.6 Research health benchmark** | controlled fixture (20–30 docs, 5 injection types) + baselines/abstractions — strongest viva talking point after health |
| P1 | **2.27 Scanner + RAG gate** | post-extraction nudge + periodic loop + retrieval verifier (pinned exempt) |
| P1 | **2.2 Meet results into KB** | turns the meeting recorder from a demo gadget into an ingestion source |
| P1 | ~~**2.13 rate-limiter fix**~~ ✅ PR #1 done | one line; viva question "does rate limiting actually work per user?" — **merged** |
| P1 | ~~**2.15 `audit_log` writers**~~ ✅ PR #2 done | dashboard activity feed is empty; dashboard is demo moment #1 — **merged** |
| P1 | **2.14 webhook scheduler + inbound auth** | unauthenticated inbound webhook can write to the KB — real risk |
| P1 | ~~2.20 LLM model config~~ ✅ PR #3 done | removes hardcoded model + reasoning-model hazard — **merged** |
| P1 | **2.28 Health dashboard surface** | `pipeline_health → knowledge_health` extension + Requires Review inbox |
| P1 | 4 bug list sweep (delete cleanup, chunk text, SSE reconnect) | robustness questions in viva |
| P2 | **2.25 Temporal validity**, **2.26 Source reliability** | temporal/stale already partly covered by `2.27`; calibrate after pinned ships |
| P2 | 2.17 structlog, 2.18 CSP, 2.19 frontend tests, 3.1 load test, 3.3 security pass | brief compliance + hardening |
| P2 | 3.4 observability | nice-to-have |
| P2 | 1.3 root akgb.db removal | tidy-up |

---

## 6. How to Verify Each Fix

- Prisma removal: `cd apps/web && grep -ri prisma src/` → no matches; `npx tsc --noEmit` passes.
- Storage: upload → check Supabase bucket via dashboard → delete doc → bucket emptied.
- LLM config: set `LLM_CHAT_MODEL` → chat streams with it (no `<think>` stall).
- Tests: `cd apps/api && python -m pytest tests/ -v`; `cd apps/web && npx vitest run` (once tests exist).
- E2E: `cd apps/web && npx playwright test` (chromium installed).
- **Pinned not auto-retired:** create pinned edge → ingest contradicting doc → `knowledge_health_checks` shows `requires_review`, edge stays `asserted`; outdated `valid_until` does NOT auto `deprecated` pinned.
- **Conflict only:** outdated doc without contradiction → no overwrite of pinned; conflict doc → one-time prompt appears.
- **Evidence:** `get_entity_chunks` returns `sentence_text + span_start/end` that substr-matches `DocumentChunk.text`; citation `trust` includes `pinned|disputed`.
- **Health metrics:** `GET /dashboard/summary` contains `knowledge_health.last_scan_at` + `conflict_pairs` + `pinned_count`.
- **Benchmark:** `python -m eval.retrieval_harness` + `python -m eval.kg_health_eval` report `recall@k / citation precision / contradiction P/R / factual accuracy Δ vs RAG`.
