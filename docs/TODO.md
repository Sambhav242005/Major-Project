# TODO — AI Knowledge Graph Builder

This file separates repository problems, product features, research work, hardening, and verification. Items are ordered by practical priority, not just discovery order.

## Index

### Parallel hardening delivery (2026-10-25)

Implemented on local integration branch `feat/old-todo-hardening`, with separate
worker branches `feat/document-storage`, `fix/webhook-security-retries`, and
`fix/schema-migration-gaps`. Combined isolated verification: **225 tests passed**.
Independent review findings were repaired, including bounded webhook bodies,
cancellation-safe persistence, restrictive preview CSP and concurrent recovery.
No servers were managed; no push or main merge performed. Browser/live PostgreSQL
checks and the explicitly listed operational limitations remain pending.

### Today's focus and new feature plan (2026-10-25)

**Recommended task today: 2.23, model selection from the top header.** Reuse the
existing per-message provider/model controls, make the displayed model actionable,
and verify that the next message uses the selected model. This is a bounded,
visible improvement; do not attempt all four new features in one day. If time
remains, trace the final chat request assembly to prepare 2.24. Durable storage
and webhook security remain release priorities.

**New feature sequence:** `2.23 Header model selector → 2.24 Model request
inspector → 2.25 GitHub repository ingestion → 2.26 Multimedia ingestion`.
Storage and deletion/retry cleanup must be ready before promising durable source
previews or reliable re-ingestion. These are planned items, not completed work.

Chat now offers per-message provider/model selection (server configuration,
OpenAI API, Groq, OpenRouter, Google Gemini, or server-connected ChatGPT). Gemini
uses Google's OpenAI-compatible streaming endpoint. Hosted provider keys
are entered in the UI and remain in page/request memory; selections reset on
navigation. Offline tests cover validation, credential isolation, concurrent
provider routing and streaming propagation. Verify the controls in a running
browser and complete real generation with each available provider/account.

PR #34 review: the isolated Pi stack, local accounts, ChatGPT OAuth, CPU MiniLM,
schema revision 008 and ingestion failure recovery have offline coverage. Login
limits now separate LAN clients through an authenticated private web proxy;
sign-out uses the public app origin, and failed generation terminates with an
error without saving or announcing a completed answer. API CSP follows configured
origins. Exact frozen research artifacts remain independently auditable.

Before release, the operator must configure a separate `AUTH_PROXY_SECRET` in
`infra/pi/.env`, rebuild the web image and recreate only the AKGB containers;
the agent does not manage services. Verify real account provisioning/sign-in,
ChatGPT authorization and completed generation, MiniLM runtime/latency, document
processing, two-account isolation, independent client login limits, public-origin
sign-out, persistence and backup restoration. These live checks remain pending.
Existing UUID5-based profile data requires an explicit migration before this
identity change; the documented deployment targets a fresh database. PR #34 has been
merged into `main`; this does not mark the live deployment checks complete.
See [SPEC §8.1](SPEC.md#81-pr-34-review-changes-by-file) for the review's file-by-file
change map and recorded validation results. PR #33's already-reviewed deployment
and CI parent is included because `main` was behind `develop`.

| Priority | Area | Summary | Status / dependency |
|---|---|---|---|
| P0 | Verification | Private local originals exist; lifecycle improvements are in the hardening branch. | Original-access, retry/delete and compensation tests; browser checks pending. |
| P0 | Feature | MCP has CRUD/OAuth plumbing but no real MCP server or client. | Large feature; required only if Claude Desktop integration is mandatory. |
| P1 | Verification | Alembic revisions reach 009 with legacy audit backfill. | Offline schema/data checks pass; PostgreSQL runtime validation pending. |
| P1 | Feature | Google Meet output never enters the knowledge base. | Needed for an end-to-end meeting demo. |
| P1 | Research | No sentence-level evidence, contradiction detection, or stale-knowledge evaluation exists. | Core research scope; build in dependency order. |
| P1 | Verification | Signed inbound requests and bounded retry scheduling implemented in hardening branch. | Provision inbound secrets; live checks and replay/DNS hardening remain. |
| P1 | Quality | No controlled retrieval or knowledge-health benchmark exists. | Blocks defensible research claims. |
| P2 | Hardening | Frontend SSE recovery, CSP configuration, observability, and unit tests need work. | Important polish after the core demo path. |
| P2 | Stretch | Load testing, source reliability scoring, and advanced temporal modeling. | Defer unless core scope is complete. |

### Recommended execution order

`Storage → migrations → webhook security → base retrieval evaluation → sentence evidence → minimal knowledge health → benchmark → optional MCP`

**Legend:** `[BUG]` broken/risky now · `[MISSING]` documented but absent · `[STALE]` docs/code mismatch · `[HARDEN]` polish/robustness · `[NICE]` stretch · `[RESEARCH]` research contribution (not required for BUILD_BRIEF demo, required for hypothesis test)

---

## 1. Problems and stale documentation

These items make the repository misleading or expose a concrete product risk.

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

## 2. Product features and missing capabilities

These are user-facing capabilities or integrations that are incomplete.

### Core product features

### 2.1 MCP — the actual MCP protocol was never built `[MISSING]` — biggest demo risk
- **What exists:** `mcp_connections`/`mcp_auth_tokens` tables, connection CRUD, a full OAuth 2.0 client (`core/oauth/` — client-credentials + PKCE + refresh + DB persistence), PKCE endpoints, `POST /mcp/search` (REST), and the MCP Connections UI.
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

### 2.3 Durable uploaded originals `[HARDEN]` — implemented, live checks pending
- **Verified baseline:** `services/documents/storage.py` saves private originals under `document_originals/{project_uuid}/{document_uuid}` beside `CHROMA_PATH`. Upload persists bytes, retry can load them without re-upload, and deletion removes the original. Supabase Storage is not the current implementation.
- **Implemented:** authorized `GET /documents/{id}/original` (download by default, `?download=false` for safe inline formats), upload failure cleanup, cancellation-safe mutations, serialized retry/delete, and recovery that preserves concurrent winning mutations. Failed deletes after vector removal restore originals and mark surviving metadata failed/retryable. Older uploads without stored originals still need a re-upload. Frontend original-file buttons are a separate follow-up.
- **Acceptance:** upload → authorized original access → file-free retry → deletion, with cross-project isolation and derived-data cleanup checks. Back up originals with the database and vectors. Browser checks remain operator-managed.
- **Status:** isolated regression checks and independent review passed. Filesystem/SQL/vector operations are not atomic across hard crashes; unavailable disk/DB can prevent best-effort recovery.

### Platform and reliability features

#### 2.12 RLS not actually enforced `[HARDEN]`
- **What:** `infra/schema.sql` defines row-level security policies keyed off `project_members`, but the app talks to the DB with full access (SQLite dev ignores RLS entirely; prod uses the backend's connection, not anon/service-role client).
- **Fix:** document the RLS story accurately; optionally verify policies on Supabase. Backend membership checks are the current real enforcement (fine for MVP, but the brief promised RLS as first-line defense).
- **Effort:** small (doc) / medium (verify).

#### 2.13 Rate limiter per-user key bug `[BUG]` ✅ DONE — PR #1 merged (`a030a0d`)
- **What was:** `core/rate_limit.py::_rate_limit_key` read `request.state.user`, but `GlobalAuthMiddleware` sets `request.state.user_id`. Result: every authenticated request was keyed by **IP**.
- **Fix applied:** now reads `request.state.user_id` (see `apps/api/core/rate_limit.py:16`) with `ip:` fallback; added `apps/api/tests/test_rate_limit.py` (per-user vs per-IP buckets).
- **PR:** #1 `fix: use user id for rate limiting` — `task-2.13-rate-limiter` → `main`.
- **Effort:** tiny (one line + test) — completed.

#### 2.14 Webhook signatures and retry scheduler `[HARDEN]` — implemented, live checks pending
- **Implemented on worker branch:** raw-body HMAC before parsing/side effects; a narrow inbound POST JWT exemption; owner/editor authorization for manual retries; bounded lifespan retry scheduler with owned sessions, strong task reference and awaited cancellation. Download ingestion now saves originals and queues the normal pipeline with size/type/HTTPS checks.
- **Operator requirement:** provision a strong `config.secret` on each inbound webhook through database administration; no configuration UI/API exists. Missing secrets fail closed. Send `X-Webhook-Signature: sha256=<HMAC-SHA256 of exact request bytes>`.
- **Remaining limits:** at-least-once delivery, no inbound timestamp/replay deduplication, shared DNS-check/re-resolution gap, and single-process SQLite serialization. PostgreSQL row locks support concurrent dispatchers. Live provider delivery remains unverified.
- **Status:** targeted tests and independent review passed, including bounded streamed request bodies and cancellation-safe ingestion persistence. Prior wording incorrectly called inbound public: global JWT middleware previously blocked it.

#### 2.15 `audit_log` never written `[MISSING]` ✅ DONE — PR #2 merged (`d5ff01f`)
- **What was:** dashboard's "recent activity" read `audit_log`, but nothing wrote it.
- **Fix applied:** added `apps/api/services/audit.py::write_audit_log` and wired it into project create (`routers/projects.py:136`), document upload/delete (`routers/documents.py:113,220`), share grant (`services/sharing.py:52,75`), chat `send_message` (`services/chat.py:373` + `services/audit.py`); `apps/api/tests/test_audit.py` added.
- **PR:** #2 `feat: add audit logging` — `task-2.15-audit-log` → `main`.
- **Effort:** small — completed.

#### 2.16 Alembic schema parity and legacy audit details `[HARDEN]`
- **Audit:** revisions 001–008 already represent all 26 ORM tables with matching declared columns/types/nullability/keys. The frozen-001 claim was stale. Intentional differences include migration-only indexes, SQL defaults, and legacy `audit_log.metadata`.
- **Implemented:** revision 009 copies legacy `metadata` into missing `meta` (SQL NULL or JSON null), preserving existing values and retaining legacy conflicts. The Supabase SQL bootstrap now also declares `meta`. Independent review passed.
- **Verified:** offline PostgreSQL fresh/008→009 SQL generation and declared-schema comparison; temporary-database backfill/idempotence/data-preserving downgrade tests. Actual PostgreSQL upgrade/reflection remains pending; no server was started.
- **Separate gap:** `infra/schema.sql` is a 21-table Supabase bootstrap, missing five current tables (`agent_memory`, `agent_checkpoints`, `project_memory_shares`, `mcp_auth_tokens`, `local_accounts`). Use Alembic for the current application schema; its local identity model intentionally differs from Supabase's `auth.users` FK/trigger. Full bootstrap alignment is deferred.

#### 2.17 Observability: structlog unused, no request_id `[HARDEN]`
- **What:** `structlog` is in requirements but zero imports; no request-id threading; Sentry not configured.
- **Fix:** wire structlog + a middleware that stamps `request_id` onto logs (brief §12 asks for this); or drop the dep.
- **Effort:** small–medium.

#### 2.18 API CSP configured origins `[HARDEN]` ✅ DONE — PR #34 merged (`08ddb05`)
- **What changed:** API response `connect-src` now includes `'self'` and configured `CORS_ORIGINS`, with a LAN-origin regression test.
- **Scope:** this header belongs to API responses; frontend document CSP remains a separate deployment concern.

#### 2.19 Frontend unit tests `[MISSING]`
- **What:** Vitest configuration and utility tests already exist, including `src/lib/utils.test.ts`; the earlier zero-tests claim was stale. React Testing Library component coverage and broader store/API validation still need work.
- **Fix:** extend meaningful store/validator/API tests and add component tests for user-facing states.
- **Effort:** medium.

#### 2.20 LLM provider consistency `[HARDEN]` ✅ DONE — PR #3 merged (`b98d6d9` + `85a3567`)
- **What was:** chat (`services/chat/`) and entity extraction (`pipelines/extraction/`) hardcoded `model="llama-3.3-70b-versatile"` instead of using settings; note about qwen reasoning tokens was a comment workaround.
- **Fix applied:** made configurable via `LLM_CHAT_MODEL` / `LLM_EXTRACT_MODEL` in `apps/api/core/config.py:44-45` (default `qwen/qwen3.8-27b`), updated `services/chat.py:349` and `pipelines/entity_extraction.py:136`, added `apps/api/.env.example` entries and `apps/api/tests/test_llm_config.py`.
- **PR:** #3 `feat: make llm models configurable` — `task-2.20-configurable-llm` → `main` (follow-up `85a3567 fix review feedback for llm config and comments`).
- **Effort:** small — completed.

#### 2.21 Error handling for SSE in UI `[HARDEN]`
- **What:** chat page treats a non-OK `/messages` response as a generic failure; backend errors during stream are caught, but mid-stream network drops show only the generic message. Document-status SSE has keepalives but no client-side reconnection.
- **Fix:** surface `ApiRequestError` details in chat; add SSE reconnect/backoff on the documents page.
- **Effort:** small–medium.

#### 2.22 Embedding provider portability `[HARDEN]` ✅ DONE — issue #6
- **What was:** `OpenAICompatibleEmbeddingFunction` was the only embedding path, so Gemini's native API was unusable; `get_embedding_function()` swallowed every exception and returned `None`, letting Chroma fall back to its own default EF and silently mix vector spaces; the `knowledge_base` collection recorded nothing about which model wrote its vectors.
- **Fix applied:** `EMBEDDING_PROVIDER` (`openai` | `gemini`) in `core/config.py` with fail-fast validation; `GeminiEmbeddingFunction` using native `:batchEmbedContents` (not `:embedContent`, which aggregates texts into one vector) with asymmetric `RETRIEVAL_DOCUMENT`/`RETRIEVAL_QUERY` task types, manual L2 normalization for truncated `gemini-embedding-001` output, and 429/5xx backoff honouring `Retry-After`, capped by a 60s total wall-clock budget per call (the retry loop blocks a worker thread with no asyncio timeout); `get_embedding_function(task)` is task-scoped and never returns `None`; ingestion and search now embed explicitly so one collection serves both task types; collection carries an `embedding_fingerprint` and raises `EmbeddingSpaceMismatchError` instead of mixing spaces. Tests: `apps/api/tests/test_embedding_providers.py` (52). Docs: README provider section + re-embed procedure, `apps/api/.env.example`, SPEC §8 rows 4 and 8.
- **Open:** legacy collections (created before fingerprints) adopt the current fingerprint on the `openai` provider for backward compatibility; switching provider on such a collection is refused and needs the documented re-embed. Because a pre-fingerprint collection records nothing about which model wrote its vectors, adoption is an *assumption* (logged as a warning): a model change shipped in the same deploy as this upgrade would go undetected. The fingerprint cannot detect it — only provider switches are guaranteed to be caught.
- **Effort:** medium — completed.

### 2.23 Change chat model from the top header `[MISSING]` — P1, today's task
- **Goal:** clicking the provider/model displayed in the top header opens a selector; the user can change the model before sending the next message.
- **Plan:** locate the header and existing per-message controls; share their selection state and provider validation rather than adding a second routing path. Show the active provider/model, configured default, and unavailable-provider reasons. Keep credentials in page/request memory under the existing policy; do not persist keys in browser storage or logs.
- **Behavior:** selection applies to subsequent sends; an in-flight answer keeps its original model. Preserve the chosen model while navigating within the current chat view where practical; cross-navigation/account persistence is a separate decision. Record the resolved provider/model on each answer so later header changes do not mislabel old responses.
- **Done when:** mouse and keyboard selection work, the header matches the next request's resolved model, default/custom models validate correctly, and switching during streaming does not change the running request. Check credential isolation and concurrent requests; complete a live generation with an available provider using user-managed services.

### 2.24 Inspect the data sent to the chat model `[MISSING]` — P1
- **Goal:** a per-message “Model request” view shows what the application actually supplied to the generation provider.
- **Phase 1:** trace retrieval, prompt construction, provider adaptation, and the final outbound request. Capture a sanitized snapshot at the final application transport boundary, tied to the assistant message/request ID. Show ordered system/user/assistant messages, included history, retrieved chunk text and source IDs, graph context, attachments, tool definitions/results if present, resolved provider/model, generation settings, truncation decisions, and estimated token counts clearly labeled as estimates.
- **Phase 2:** add the read-only inspector with expandable sections and copy/download of the sanitized payload. Show text exactly as sent; represent binary/base64 attachments with MIME type, size, and a permission-checked preview instead of dumping binary data. Distinguish a draft preview from an actual sent request, and show failed/cancelled attempts accurately. For multi-call flows, show each outbound request separately.
- **Privacy:** exclude authorization headers, API keys, OAuth tokens, signed-URL secrets, and hidden reasoning. Restrict snapshots to authorized project/chat access; prefer short-lived snapshots initially and define explicit retention/deletion before persistent storage. The view covers application-visible outbound data; provider-internal processing is outside its scope.
- **Done when:** a transport-level test compares the sanitized captured payload with the outbound request, including history/context truncation, provider-specific adaptation, attachments, and failure cases; verify another account cannot read it. Embedding/extraction request inspection can follow as a separately labeled extension.

### 2.25 Ingest a GitHub repository into the knowledge base `[MISSING]` — P1
- **Goal:** import repository documentation and source files into a selected project's normal document/chunk/entity pipeline with traceable citations.
- **Phase 1, public repositories:** accept a GitHub repository URL and optional branch/ref plus include/exclude paths. Resolve the ref to a commit SHA, show a preview of files/count/bytes, and import an explicit allowlist of text/code formats. Exclude binaries, generated/build/vendor directories, dependency caches, secret-like files, and oversized files; enforce repository/file/count limits. Validate hosts and redirects; do not execute imported code, hooks, installers, or repository instructions.
- **Provenance:** retain owner/repository, commit SHA, path, content hash, and line ranges; citations open the pinned commit/file lines. Track an import job with progress, per-file errors, cancellation, and source metadata. Preserve project membership checks and treat repository text as untrusted retrieval content.
- **Phase 2, updates:** manual re-sync compares hashes and handles changed/deleted files without duplicate chunks, vectors, or orphan graph state. Define how source deletion affects chat citations and shared entities. Requires verified deletion/retry cleanup and compatible schema migrations.
- **Phase 3, private repositories:** add explicit authenticated access with least-privilege repository permissions and server-side credential protection; verify access at import/re-sync and prevent cross-project leakage. Scheduled sync and submodules are deferred.
- **Done when:** a small fixture repository imports once, answers cite the correct commit/path/lines, re-import is idempotent, changed/deleted files reconcile correctly, limits/cancellation work, and private credentials never enter model requests or traces.

### 2.26 Multimedia support `[MISSING]` — P1 foundation, P2 advanced
- **Scope:** support images, audio, and video as knowledge sources, with original previews and evidence citations. Track direct chat attachments separately from ingestion so users know whether an attachment becomes searchable project knowledge.
- **Phase 1, inventory and storage:** inspect existing image/OCR and meeting transcription paths before adding parsers. Finish durable private source storage, authorized previews, MIME/content validation, size/duration limits, deletion, and retry cleanup. Display supported formats and processing status.
- **Phase 2, images and audio:** extract OCR text from images; transcribe audio with timestamps and speaker labels when available. Feed derived text through normal ingestion while retaining its link to the original image/audio. Cite image regions/pages where available and audio time ranges; label machine-generated descriptions/transcripts and allow review of uncertain extraction.
- **Phase 3, video:** extract a timestamped transcript and sampled keyframes under duration/frame/cost limits; combine OCR/frame descriptions with transcript evidence, deduplicate repeated frames, and cite playable time ranges. Reuse the audio path and run heavy processing in bounded background jobs with independent database sessions and strong task references.
- **Phase 4, direct multimodal chat:** allow temporary image/audio/video attachments only for providers/models that explicitly support the format. Show capability and size restrictions before send; offer an explicit transcript/OCR fallback when native input is unavailable. Include attachment metadata and derived text in 2.24, with clear retention and delete behavior.
- **Done when:** one image, audio clip, and short video each produce searchable evidence with a working source preview/time citation; unsupported formats fail clearly, retries do not duplicate data, deletion removes originals/derived artifacts, and project isolation holds. Test native chat attachments only against supported available models. Provider selection and cost limits must be decided before enabling paid processing.

## 3. Research features and evaluation

These items define the research contribution and the evidence needed to defend it.

### 3.1 Knowledge Health Mechanism — continuous reliability `[MISSING]` `[RESEARCH]`
- **What exists:** ingestion is append-only `pipelines/ingestion/pipeline.py` `parse→chunk(600/80)→embed→store chunks→extract entities/relations→processed` (`pipelines/extraction/pipeline.py`). `EntityMention.confidence 0.8` and `Relationship.confidence 0.7` are hardcoded constants (`pipelines/extraction/`); `services/knowledge/` loads all `entities`/`relationships` into `nx.DiGraph` per request with no filter; `services/chat/` retrieval is `top_k=8` vector → entity mention → 1-hop expand — no health check. No `conflict`/`stale`/`disputed` concept anywhere.
- **Why it matters:** Papers solve pieces (see `docs/RESEARCH_PROBLEM.md §11` URLs: Docs2KG→KG, GraphRAG→retrieval, Zep/Graphiti→temporal KG memory, TempAgent→temporal QA, Jarnac 2025 https://drops.dagstuhl.de/entities/document/10.4230/TGDK.3.1.3 →uncertainty survey, FactGenius https://aclanthology.org/2024.fever-1.30/ + Kolli https://aclanthology.org/2025.winlp-main.19/ →KG fact verification) but none jointly handle **heterogeneity + update + contradiction + staleness together** before a stateless agent retrieves. Current system is `Documents → KG (assumed reliable) → Agent`. `docs/RESEARCH_PROBLEM.md:67` research question and `§4 Build→Monitor→Verify→Repair` loop are unimplemented — hypothesis `§7` (“evidence-backed, continuously validated KG > conventional RAG when conflicting/outdated”) is untestable without this.
- **Fix (minimal additive, reuse `async_session_factory` + strong `asyncio.Task` refs `core/task_queue/`):**
  1. Define health signals formally: `evidence_coverage` (sentences supporting edge), `contradiction_group` (same `(source,target)` incompatible `relation_type`), `temporal_validity` (`valid_until`), `confidence` (calibrated, not constant), `source_reliability` (`documents.uploaded_by`/type).
  2. Add `knowledge_health_checks` table `id, project_id, entity_id|relationship_id, issue_type enum(conflict|stale|invalid|low_evidence), severity, evidence_json, status enum(open|requires_review|resolved), created_at` + extend `entities`/`relationships` with `health_status enum(asserted|disputed|stale|deprecated)`, `verification_status enum(unverified|supported|contradicted)`.
  3. Note: do NOT claim `stateless` or generic `self-healing` as novelty (`docs/RESEARCH_PROBLEM.md:118`); novelty is joint health scoring + repair before retrieval.
- **Where:** new `pipelines/kg_health.py` + `services/knowledge_health.py` + `pipelines/health_scanner.py`; migration in `2.16`; see `docs/SPEC.md §12` audit for insertion points.
- **Effort:** large (days) — gated by `2.16` + `3.3`.

### 3.2 Pinned / Protected knowledge tag `[MISSING]` `[RESEARCH]`
- **What:** No way to mark important facts as human-verified. Today newer noisy doc could silently supersede a curated fact because recency/`valid_until` would win if implemented.
- **Why it matters:** For `Q4 Revenue = $5.2M` style facts, auto-overwrite is hazardous. User asked for `unchange`/`important` tag that only allows overwrite on **conflict + explicit user Accept**, never on outdated alone. This makes health `human-gated` not fully autonomous — correct for evaluation integrity.
- **Fix (conflict-only overwrite, not staleness):**
  - Schema: `entities`/`relationships` add `is_pinned bool default false`, `pinned_by uuid FK profiles.id`, `pinned_at timestamptz`, `pinned_reason text` (e.g., “Board-approved”). Only `owner`/`editor` (`project_members.role` `db/models.py:73`, `core/deps.py:get_project_id`) may pin; pin/unpin writes `audit_log` via `services/audit.py`.
  - Logic: post-extraction nudge `pipelines/ingestion.py:136` groups `(source,target)` → if `is_pinned` in group → emit `knowledge_health_checks {issue_type=conflict, status=requires_review}` instead of auto `superseded_by`; periodic scanner `services/knowledge_health.py` **exempts pinned** from stale auto-retire (flag `stale` for visibility only, never auto `deprecated`).
  - UX: dashboard/graph “Requires Review” inbox shows `Pinned "X works_at Y (doc A p.3)" vs New "X works_at Z (doc B p.1)"` with sentence evidence; actions `Keep pinned / Overwrite pinned / Keep both as disputed`. Overwrite → `UPDATE … superseded_by=old_id, last_validated_at=now(), verification_status=supported` + old row `deprecated` (monotonic). Keep → new edge `disputed/contradicted`. Avoid chat-time blocking.
  - Guard: warn if >5% entities pinned; require `pinned_reason`; show `pinned_count` trend in dashboard.
- **Where:** `db/models.py`, `pipelines/kg_health.py`, `services/knowledge_health.py`, `apps/web/src/app/graph/page.tsx` + dashboard review queue.
- **Effort:** small (schema+branch) but must ship before any auto-supersede logic in `3.1`.

### 3.3 Sentence-level evidence linking `[MISSING]` `[RESEARCH]`
- **What:** Citations today are block-level `chat_messages.citations JSON {index, chunk_id(chroma_id), document_id, filename, page_number}` (`db/models.py:171`, `services/chat.py:219` `text[:800]` truncation) and `entity_mention.chunk_id` chunk-level (~600 tokens). Not sentence provenance. `docs/RESEARCH_PROBLEM.md:114` explicitly calls this the trust pivot.
- **Why it matters:** Jarnac `uncertainty` + FactGenius `evidence verification` both need per-sentence → chunk/char-range mapping to judge support; current `citation precision` metric unmeasurable.
- **Fix:** `entity_mentions` add `span_start int, span_end int, sentence_text text, extraction_source enum(spacy|llm|both)`; add `relationship_evidence` M2M `relationship_id, chunk_id, evidence_type enum(supporting|contradicting), sentence_span int4range, created_at PK(relationship_id,chunk_id)` to complement `relationships.source_document_id` (currently doc-level only). `pipelines/entity_extraction.py:90 EXTRACT_PROMPT` must ask LLM for `evidence_sentence` + `char_span`; spacy pass provides `ent.text` as fallback. `document_chunks.section_index` (`db/models.py` exists but never written in `pipelines/chunking.py`) fix to populate.
- **Where:** `db/models.py`, `pipelines/entity_extraction.py`, `pipelines/chunking.py`, `services/knowledge.py:222 get_entity_chunks`, `services/chat.py:219 _format_source_block`.
- **Effort:** medium (prompt+schema+ingestion plumbing).

### 3.4 Temporal validity & stale detection `[MISSING]` `[RESEARCH]`
- **What:** No `valid_from/valid_until/last_seen_at/updated_at` on `entities`/`relationships`; `created_at` is insertion-only; `documents.uploaded_at/processed_at` exist but not propagated to KG freshness; no `document.effective_date` (doc-internal date vs ingestion date). Cannot answer “is this knowledge stale?” TempAgent/TempQA show temporal QA alone is not novelty — joint use as health signal is.
- **Fix:** `relationships` add `valid_from timestamptz, valid_until timestamptz, last_seen_at timestamptz default now(), updated_at timestamptz, superseded_by uuid FK relationships.id`; `documents` add `effective_date timestamptz, supersedes_document_id uuid FK documents.id, version int`; Chroma metadatas `+created_at, embedding_model`. Scanner flags `valid_until < now → stale` + `document supersession chain`; but **pinned exempt** per `3.2`. Never auto-delete — `deprecated` with reason.
- **Where:** `db/models.py`, `pipelines/kg_health.py`, `infra/schema.sql` (via Alembic).
- **Effort:** medium — requires LLM date normalization + doc version UX.

### 3.5 Source reliability scoring `[HARDEN]` `[RESEARCH]`
- **What:** No `documents.source_type` (upload vs OCR vs `meeting_transcript` `2.2`) / `source_trust_score` / `uploader_reputation`; `uploaded_by` stored but not scored; all sources weighted equal. `Relationship.confidence` never calibrated by source count vs quality.
- **Fix:** `documents` add `source_reliability float default 1.0` + `source_type text`; health score = `confidence * evidence_count * source_reliability * temporal_decay`. Calibrate LLM to emit per-edge confidence in `EXTRACT_PROMPT` instead of hardcoded `0.7`; spacy `0.8` replaced with length/context-aware score.
- **Where:** `db/models.py`, `pipelines/entity_extraction.py:339,368`, `pipelines/embeddings.py:105` ranking (future).
- **Effort:** small.

### 3.6 Health scanner & RAG verification gate `[MISSING]` `[RESEARCH]`
- **What:** No monitor→verify→repair loop. `docs/RESEARCH_PROBLEM.md:79` diagram `Build→monitor→detect(Conflict|Stale|Invalid)→Evidence Check→Repair/Reject→KG→Agent` has no code.
- **Fix (3 insertion points, minimal churn):**
  1. **Post-extraction nudge (inline):** after `pipelines/ingestion/pipeline.py` extraction success → `pipelines/kg_health.py:enqueue_check(document_id, project_id)` for `confidence<0.5 && mention_count==1` invalid, `(source,target)` group differing `relation_type` conflict, overlapping entities with newer `uploaded_at` stale.
  2. **Periodic scanner (background loop at startup):** `services/knowledge_health.py` + `pipelines/health_scanner.py` scheduled via `asyncio.create_task` strong refs (`core/task_queue/` pattern) scanning `Relationship GROUP BY (source,target)` → `CONFLICT`, `last_seen_at < now-90d` → `STALE`, pinned exempt.
  3. **Retrieval-time verifier (RAG gate):** between `services/chat/retrieval.py` query and prompt assembly, filter `score` outliers, tag `citations[].trust="disputed"|"pinned"`; add conflict surfacing instruction (today `Answer ONLY based on sources` with no conflict handling).
- **Where:** `pipelines/ingestion/`, `services/chat/`, `core/task_queue/` scheduling, `services/knowledge/`.
- **Effort:** medium (2–3d) — depends on `3.1`/`3.3`.

### 3.7 Knowledge health dashboard surface `[MISSING]` `[RESEARCH]`
- **What:** `services/dashboard.py:112` only `pipeline_health {queue_depth, failed_count, success_rate}` + `failed_documents[:5]`; no KG health. `audit_log` writers exist (PR #2) but no `kg.health_detected/kg.repaired/kg.pinned` events.
- **Fix:** extend `GET /dashboard/summary` with `knowledge_health {total_entities, orphan_entities(0 mentions), dangling_relationships, avg_confidence, conflict_pairs, stale_pinned_pending, last_scan_at, trend}` backed by `knowledge_health_checks`; add review inbox table in UI; wire `audit_log` writes for pin/unpin/repair.
- **Where:** `services/dashboard.py`, `apps/web/src/app/dashboard/page.tsx`, `services/audit.py`.
- **Effort:** small.

---

## 4. Build-brief compliance

### 4.1 Load testing `[MISSING]`
- Locust/k6 harness for concurrent uploads + chat (p50/p95/p99). Brief §11.

### 4.2 Retrieval quality eval harness `[MISSING]` — blocks any research claim
- Hand-labeled Q/A pairs against fixture docs; recall@k, citation precision, hallucination spot-check. Brief §11 — a strong viva talking point. `docs/RESEARCH_PROBLEM.md:189` warns no defensible measurement without it.
- **Note:** `4.2` stays the *base RAG* harness (current `top_k=8` + graph expansion). Health comparison builds on it in `4.6`.

### 4.3 Security test pass `[MISSING]`
- Prompt-injection fixture doc test, auth-bypass attempts, oversized/disallowed file types, rate-limit verification. (Some tests exist under `apps/api/tests/` — e.g. `test_security_utils.py` — but the full pass is unverified.)

### 4.4 Observability `[HARDEN]`
- `structlog` is in requirements but verify JSON logging + `request_id` threading is actually wired; Sentry not configured.

### 4.5 Chroma index cleanup on document delete `[HARDEN]`
- Baseline `services/documents/crud.py` already removes vectors, document chunks/mentions and source-document relationships; ingestion replaces earlier document evidence on retry. The old row-only/duplicate-retry claim was stale. Shared/orphan entity retention remains a separate policy. This wave verifies original-file cleanup and recoverable failure ordering across filesystem, SQL and vectors; cross-store crash atomicity remains unresolved.

### 4.6 Research benchmark — controlled health evaluation `[MISSING]` `[RESEARCH]` — paper's core
- **Why:** Without this, `3.1`/`3.2` cannot be shown to beat conventional RAG. User’s gap analysis explicitly calls for a controlled benchmark: same documents → `Normal RAG vs Our System (+health)`.
- **Fix:** Build 20–30 fixture docs injecting 5 types: `update` (supersedes), `contradiction` (same `(source,target)` incompatible `relation_type`), `stale` (old date superseded by newer), `duplicate` (same fact multi-doc support), `uncertain/low-evidence` (single mention, OCR-noisy) — reuse `research/` pattern (`research/indian_protests_2026.txt`).
- Hand-label 15–20 Q/A pairs with `expected_answer + supporting chunk_id/page + relation_ids` (extend `3.2` fixture set). Add `eval/kg_health_eval.py` alongside `eval/retrieval_harness.py`.
- **Baselines:** plain RAG (no graph), current GraphRAG (no health — `services/chat.py:169` 1-hop), +health (`3.6` gate). Optional Zep citation baseline but not re-implemented.
- **Metrics:** `recall@k`, `citation precision` (sentence-level via `3.3`), `evidence correctness`, `contradiction detection P/R`, `stale detection P/R`, `false-positive retire rate`, `factual accuracy (LLM-as-judge)`, `latency`, `cost`; gate acceptance `held_in_delta>0 && held_out_delta>=0` (`pipelines/agent_refinement.py:280` pattern).
- **Ablations:** w/o temporal, w/o contradiction, w/o evidence, w/o source reliability, w/o pinned — shows joint value.
- **Where:** `apps/api/eval/` + `research/fixtures/`; consumes `refinement_eval_sets` (`db/models.py`) or new `kg_eval_runs`.
- **Effort:** medium (2–3d) — depends on `3.3`; strongest demo after `3.1`.

---

## 5. Hardening and robustness notes

- **`[BUG]` Background task GC:** fixed pattern (strong refs) but every new background path must keep it (`task_queue.py`, `documents.py` comments).
- **`[BUG]` Request-session reuse:** background tasks must open their own session via `async_session_factory` — request sessions die with the response (fix already applied to ingestion; keep pattern for new tasks).
- **`[HARDEN]` `get_document_chunks` truncates text to 200 chars** — **fixed (#29).** Confirmed no list-view caller exists: the only consumer of `GET /documents/{id}/chunks` is the detail page (`documents/[id]/page.tsx`), which renders the whole chunk, so the 200-char clip silently hid content. `services/documents/content.py` now returns `text` in full plus a `text_truncated` flag; `text_preview_chars` is available as an opt-in for future list/preview payloads.
- **`[HARDEN]` Entity-chunk dedup on the graph page** keyed on `filename|page` — **fixed (#29).** Distinct sections on one page are common (chunking splits at 600 tokens, so a dense page yields several chunks), so the key merged real content. Chunking is deterministic, so a retry of the same bytes reproduces the same `chunk_index` — keying on `document_id|chunk_index` collapses re-processing duplicates while preserving genuinely different sections. `chunk_index` is a position within one document's chunk list (`pipelines/chunking.py`), so it must be scoped by `document_id`: keying on `filename` still merged two uploads both named `report.pdf`. `GET /kb/entities/{id}/chunks` now returns `chunk_index` + `document_id`; the filter moved to `dedupeEntityChunks` in `apps/web/src/lib/utils.ts` (unit-tested in `src/lib/utils.test.ts`).
- **`[NICE]` Prisma skill docs under `apps/web/.agents/skills/prisma-*`** (also `.claude/`, `.continue/`, `.windsurf/`) — if Prisma is removed, these stay (they're skill docs), but `apps/web/.gitignore`'s `/src/generated/prisma` line should go.
- **`[HARDEN]` Delete/retry cross-store recovery:** cleanup and retry replacement already exist; finish lifecycle regressions and report filesystem/SQL/vector crash-consistency limits. Retain shared entities intentionally until an orphan-retention/pinned policy is defined; do not equate retained entity rows with leaked document evidence.

---

## 6. Priority roadmap

| Priority | Item | Why |
|---|---|---|
| P0 | **2.1 MCP protocol (FastMCP server + client)** | demo moment #5 (Claude Desktop → `search_knowledge_base`) is impossible today; also ADR-0004 Phases 2–3 |
| Verify | **2.3 Durable originals lifecycle** | original endpoint and failure/concurrency handling implemented; frontend controls and live verification pending |
| Done | **1.1 Prisma cleanup** | completed; retain removal checks |
| Done | **1.2 README refresh** | completed; continue syncing behavior changes |
| Verify | **2.16 Migration verification** | 009 audit backfill passed offline checks; live PostgreSQL upgrade pending |
| P1 | **3.3 Sentence-level evidence** | provenance foundation for health + citation precision; unblocks `4.6` measurability |
| P1 | **3.1 Knowledge Health Mechanism + 3.2 Pinned tag** | research core — joint signal before retrieval; pinned must ship first to avoid auto-overwrite hazard |
| P1 | **4.2 Base retrieval eval harness** | without it no reliability claim is defensible (`docs/RESEARCH_PROBLEM.md:189`) |
| P1 | **4.6 Research health benchmark** | controlled fixture (20–30 docs, 5 injection types) + baselines/abstractions — strongest viva talking point after health |
| P1 | **3.6 Scanner + RAG gate** | post-extraction nudge + periodic loop + retrieval verifier (pinned exempt) |
| P1 | **2.2 Meet results into KB** | turns the meeting recorder from a demo gadget into an ingestion source |
| P1 | ~~**2.13 rate-limiter fix**~~ ✅ PR #1 done | one line; viva question "does rate limiting actually work per user?" — **merged** |
| P1 | ~~**2.15 `audit_log` writers**~~ ✅ PR #2 done | dashboard activity feed is empty; dashboard is demo moment #1 — **merged** |
| Verify | **2.14 webhook scheduler + inbound auth** | implementation, regressions and review complete; provision secrets and perform live checks |
| P1 | ~~2.20 LLM model config~~ ✅ PR #3 done | removes hardcoded model + reasoning-model hazard — **merged** |
| P1 | **3.7 Health dashboard surface** | `pipeline_health → knowledge_health` extension + Requires Review inbox |
| P1 | 4 bug list sweep (delete cleanup, chunk text, SSE reconnect) | robustness questions in viva |
| P2 | **3.4 Temporal validity**, **3.5 Source reliability** | temporal/stale already partly covered by `3.6`; calibrate after pinned ships |
| P2 | 2.17 structlog, 2.19 frontend tests, 4.1 load test, 4.3 security pass | brief compliance + hardening |
| P2 | 4.4 observability | nice-to-have |
| P2 | 1.3 root akgb.db removal | tidy-up |

---

## 7. Verification checklist

- Prisma removal: `cd apps/web && grep -ri prisma src/` → no matches; `npx tsc --noEmit` passes.
- Storage: upload → confirm private original → authorized original access → file-free retry → delete → verify original/evidence cleanup and project isolation.
- LLM config: set `LLM_CHAT_MODEL` → chat streams with it (no `<think>` stall).
- Tests: `cd apps/api && python -m pytest tests/ -v`; `cd apps/web && npx vitest run` (once tests exist).
- E2E: `cd apps/web && npx playwright test` (chromium installed).
- **Pinned not auto-retired:** create pinned edge → ingest contradicting doc → `knowledge_health_checks` shows `requires_review`, edge stays `asserted`; outdated `valid_until` does NOT auto `deprecated` pinned.
- **Conflict only:** outdated doc without contradiction → no overwrite of pinned; conflict doc → one-time prompt appears.
- **Evidence:** `get_entity_chunks` returns `sentence_text + span_start/end` that substr-matches `DocumentChunk.text`; citation `trust` includes `pinned|disputed`.
- **Health metrics:** `GET /dashboard/summary` contains `knowledge_health.last_scan_at` + `conflict_pairs` + `pinned_count`.
- **Benchmark:** `python -m eval.retrieval_harness` + `python -m eval.kg_health_eval` report `recall@k / citation precision / contradiction P/R / factual accuracy Δ vs RAG`.
