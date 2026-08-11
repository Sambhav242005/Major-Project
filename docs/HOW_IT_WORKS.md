# How the AI Knowledge Graph Builder Works

A complete guide to the codebase — architecture, the two environments, every database table, and how the knowledge graph is stored and built. Written for a developer who has never seen the project.

---

## 1. What This Project Is

A full-stack web app that turns documents into a **navigable knowledge graph**:

1. **Upload** a document (PDF, DOCX, TXT, images).
2. The backend **parses → chunks → embeds → extracts entities and relationships** (LLM + spaCy).
3. You can **explore the graph**, **search semantically**, and **chat** with your knowledge base (RAG with citations).
4. Extras: **agents** (LangGraph), **MCP** (documented but only partially built — CRUD + OAuth exist, the protocol layer doesn't; see §11), **webhooks**, **project sharing**.

The repository root holds two applications plus infrastructure:

```
MajorProject/
├── apps/
│   ├── api/          # Python FastAPI backend (port 8000) — all business logic
│   └── web/          # Next.js 15 frontend (port 3000) — UI
├── infra/
│   ├── schema.sql        # PostgreSQL schema (Supabase/cloud)
│   └── docker-compose.yml # Local PostgreSQL (optional)
├── docs/             # ADRs + this guide
├── research/         # Research notes
├── akgb.db           # SQLite dev database (backend)
├── BUILD_BRIEF.md    # Project specification
├── CONTEXT.md        # Domain glossary + key relationships
└── CHANGELOG.md      # Build log
```

---

## 2. High-Level Architecture

```
┌────────────────────┐        REST/SSE (JWT)        ┌─────────────────────┐
│   Next.js UI       │ ◄──────────────────────────► │   FastAPI Backend   │
│  (React 19,        │                              │  (Python 3.11)      │
│   Zustand, TanStack│                              │  routers → services │
│   Query, reagraph) │                              │  → pipelines        │
└────────────────────┘                              └─────────┬───────────┘
                                                              │
                     ┌────────────────────────────────────────┼──────────────────────────┐
                     ▼                                        ▼                          ▼
            ┌──────────────────┐                   ┌──────────────────┐        ┌──────────────────┐
            │  Relational DB   │                   │  ChromaDB        │        │  LLM             │
            │  (SQLite dev /   │                   │  (vector store,  │        │  (OpenAI-compat: │
            │   PostgreSQL prod│                   │   on disk)       │        │   Ollama/Groq)   │
            └──────────────────┘                   └──────────────────┘        └──────────────────┘
```

- **Frontend → Backend**: every data call goes through `apps/web/src/lib/api/client.ts` (`apiFetch`), which injects the Supabase JWT as a `Bearer` token and appends `?project_id=` when a project is active.
- **Backend → DB**: SQLAlchemy 2.0 async ORM (`db/models.py` + `db/session.py`). Query pattern is `select(...)` + `await db.execute(...)` — no raw SQL.
- **Backend → ChromaDB**: chunk vectors live in a single `knowledge_base` collection with `{project_id, document_id, page_number}` metadata; per-project isolation via `where={"project_id": ...}`.
- **Backend → LLM**: `pipelines/llm_client.py` talks to any OpenAI-compatible endpoint (`LLM_BASE_URL`/`EMBEDDING_BASE_URL` — Ollama by default, Groq works too).

### The two pipelines (the heart of the app)

**Ingestion pipeline** (`apps/api/pipelines/ingestion.py`) — runs in the background after upload:

```
parse → chunk → embed → store chunk rows → extract entities/relations → mark processed
```

**Retrieval / RAG pipeline** (`apps/api/services/chat.py`) — runs per chat message:

```
embed question → Chroma top-k=8 → find entities in chunks → expand 1 hop via relationships
→ build prompt (sources + entity context + history) → stream LLM answer over SSE → persist + citations
```

---

## 3. The Two Environments (and Why There Are Two)

The project deliberately supports **two run modes** — this is the "two env" thing. They are selected with the `ENVIRONMENT` variable on the backend (`apps/api/.env`), and mostly by which env files you copy.

### 3.1 Development (`ENVIRONMENT=development`)

- **Database: SQLite** — `core/config.py` *forces* `DATABASE_URL = "sqlite+aiosqlite:///./akgb.db"` whenever `ENVIRONMENT == "development"`. The file is `apps/api/akgb.db` (and a root `akgb.db` in older runs). Zero setup, tables created automatically by `python init_db.py` (or at first run).
- **Auth: Mock** — `MOCK_AUTH=true` accepts *any* Bearer token and maps it to the demo user `a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11`. The frontend `src/lib/supabase/client.ts` swaps in a fake Supabase client and `middleware.ts` checks a `mock-session` cookie instead of real sessions. The UI shows **"Try Demo (Auto-Login)"**.
- **LLM: local Ollama** by default (`LLM_BASE_URL=http://localhost:11434/v1`, model `qwen3:4b-instruct`).

Why: a student can clone the repo and run **the entire stack without any cloud account** — no Supabase, no API keys.

### 3.2 Production (`ENVIRONMENT=production`)

- **Database: PostgreSQL** — real `DATABASE_URL=postgresql+asyncpg://...` (Supabase or any host). Schema in `infra/schema.sql`.
- **Auth: Supabase** — real JWT validation against the project's JWKS endpoint (`SUPABASE_JWKS_URL`), audience `authenticated`.
- **LLM: OpenAI/Groq** — set `LLM_API_KEY` + provider endpoints.

Why: PostgreSQL is multi-user safe, network-accessible, and survives restarts properly — what you want when the evaluator/viva demo runs against a deployed instance. The backend **refuses to start** with `production + MOCK_AUTH=true` (`core/config.py` fail-fast validator), and the web app fails its production build if `NEXT_PUBLIC_MOCK_AUTH=true` — the guardrails make it impossible to accidentally deploy the demo mode.

### 3.3 Why *both* are needed

| | Development | Production |
|---|---|---|
| DB | SQLite file, zero install | PostgreSQL (Supabase) |
| Auth | Mock demo login | Supabase Auth (Google OAuth / email) |
| LLM | Ollama local, free | OpenAI/Groq API keys |
| Setup cost | ~2 minutes | cloud accounts + env vars |
| Used for | daily development, demos offline | the real deployed demo |

One codebase, two `.env` files (`apps/api/.env` + `apps/web/.env.local`), one `ENVIRONMENT` flag switches behavior. There are also **two real .env files on the frontend**: `.env` (committed example) vs `.env.local` (your real secrets, gitignored).

---

## 4. Database Layer: Prisma vs SQLAlchemy (Important)

**Prisma (frontend, `apps/web`)**: `@prisma/client` v7 and `better-sqlite3` are installed and `DATABASE_URL="file:./dev.db"` is documented in `apps/web/.env.example`, **but there is no `schema.prisma` and no Prisma code is imported anywhere in `src/`** — it is a *declared but not yet wired up* dependency. The skill docs under `apps/web/.agents/skills/prisma-*` (prisma-postgres-setup, prisma-database-setup, prisma-upgrade-v7) show the intent: connect the frontend to Prisma (SQLite locally, Prisma Postgres in production). Today the frontend talks to the backend API only — Prisma is the planned next step, not the current storage layer.

**SQLAlchemy (backend, `apps/api/db/`)**: this is the **real, working ORM**:

- `db/models.py` — every table as a Python class (see §5).
- `db/session.py` — async engine + session factory. `get_db()` yields a session per request, commits on success, rolls back on error. `async_session_factory` is exported for **background tasks** (ingestion, agents) which must open their own session because Starlette tears down the request's dependency session after the response.
- `init_db.py` — `Base.metadata.create_all` builds all tables (SQLite dev).
- `migrations/` + `alembic.ini` — Alembic migrations (the path for schema changes).

Why SQLAlchemy: async-first (needed for streaming chat + concurrent ingestion), and it lets the same models run on SQLite in dev and PostgreSQL in prod.

---

## 5. Data Model — Every Table

All tables are in `apps/api/db/models.py` (SQLAlchemy) and mirrored in `infra/schema.sql` (SQL for Supabase). UUID primary keys everywhere, `created_at` timestamps, JSON columns for flexible data.

### Core knowledge graph tables

**`profiles`** — one row per user, extends auth identity. `id` (UUID), `full_name`, `created_at`.

**`projects`** — top-level container. Everything belongs to a project. `owner_id` → profiles.

**`project_members`** — access control. Composite PK `(project_id, user_id)`, `role` ∈ owner/editor/viewer. Every API call resolves `project_id` through this table (`core/deps.py` → `get_project_id`): explicit `?project_id=` query param wins; single-project users auto-detect; brand-new users get a default project "My Knowledge Base" auto-created.

**`documents`** — one row per uploaded file. Lifecycle status: `pending → processing → processed | failed`. Fields: filename, file_type (MIME), storage_path, page_count, error_message, uploaded_at, processed_at.

**`document_chunks`** — the ~600-token segments of a document. Each has `chunk_index`, `page_number`, `text`, `token_count`, and **`chroma_id`** — the ID of its vector in ChromaDB (`"{document_id}_chunk_{index}"`). This column is the bridge between the relational DB and the vector store.

**`entities`** — a named thing: person, organization, concept, location, date, other. **Unique per (project_id, name, type)** — that's the dedup rule. Has description and `first_seen_document_id`.

**`entity_mentions`** — one row per *occurrence* of an entity in a chunk. Links `entity_id` + `document_id` + `chunk_id`, with `mention_text` and `confidence` (0.8 for spaCy). This is the entity ↔ document/chunk bridge used for "where is this entity mentioned" and for graph expansion in chat.

**`relationships`** — the **edges** of the graph. `source_entity_id → target_entity_id` (both FK to entities), `relation_type` (e.g. `works_at`, `located_in`, `co_occurs_with`), description, confidence, `source_document_id`.

### Chat tables

**`chat_sessions`** — a conversation thread: project_id, user_id, title.
**`chat_messages`** — user/assistant/system message: content + `citations` (JSON array of `{index, chunk_id, document_id, filename, page_number}` — the clickable source chips).

### Agent tables

**`agents`** — an automated task runner: name, type, config (JSON), status, last_checkpoint, last_active_at.
**`agent_tasks`** — one execution of an agent: input/output (JSON), status (queued/running/completed/failed), `trace` (JSON — the step-by-step LangGraph trace shown in the UI), timestamps, error.
**`agent_memory`** — working/episodic/semantic memories with optional embedding JSON.
**`agent_checkpoints`** — state snapshots for resumable runs.
**`agent_skills`** — learned skills with success/failure counters.
**`agent_run_traces`** — detailed run logs: input/output text, tool calls, scores.
**`refinement_eval_sets` / `refinement_logs`** — held-in/held-out eval sets and self-refinement history (advanced agent learning).

### MCP tables

**`mcp_connections`** — external integration, `direction` ∈ sender (this app exposed as an MCP server) / receiver (this app calling external MCP servers, e.g. Google Meet). Holds endpoint_url, auth_config (JSON).
**`mcp_auth_tokens`** — persisted OAuth tokens (access + refresh) so connections survive restarts.

### Extras

**`audit_log`** — every mutating action: actor, action, resource, metadata, timestamp (drives the dashboard activity feed).
**`project_memory_shares`** — cross-project memory sharing with read/read_write permission.
**`webhook_subscriptions` / `webhook_deliveries`** — outbound webhooks (e.g. `document.processed`, `chat.completed`, `agent.completed`) with retry tracking.
**`inbound_webhooks`** — named/slugged inbound webhook endpoints.

### Table relationships at a glance

```
Project 1──* Document 1──* DocumentChunk
Project 1──* Entity 1──* EntityMention *──1 DocumentChunk
Entity 1──* Relationship *──1 Entity   (source_entity_id / target_entity_id)
Project 1──* ChatSession 1──* ChatMessage
Project 1──* Agent 1──* AgentTask, AgentMemory, AgentCheckpoint, AgentSkill, AgentRunTrace
Project 1──* MCPConnection 1──* MCPAuthToken
Project 1──* WebhookSubscription 1──* WebhookDelivery
```

---

## 6. How the Graph Is Stored and Built

### Storage — Postgres rows, not a graph database

The graph is **not** Neo4j. The deliberate architecture decision (see `docs/adr/001-supabase-over-neo4j.md` and `BUILD_BRIEF.md` §2):

- **Vertices = rows in `entities`** (one per unique name+type per project).
- **Edges = rows in `relationships`** (source_entity_id → target_entity_id + relation_type).
- **Traversal happens in memory with NetworkX** (`apps/api/services/knowledge.py`): on each graph request, all project entities + relationships are loaded and assembled into a `nx.DiGraph()` (nodes carry name/type/description; edges carry relation_type/confidence), then a **k-hop subgraph** is extracted around a chosen entity.

Why this design: for the MVP's few-thousand-entity graphs, a full graph database is overkill — Postgres rows are easy to query, back up, and explain in a viva. The relationship table is shaped so a future Neo4j migration is straightforward.

### What it takes to create a graph (the ingestion flow)

1. **Upload** → `POST /documents` (rate-limited 30/min) validates MIME type + 25 MB cap, inserts a `documents` row with `status=pending`, and fires a background `asyncio` task (`ingest_document`). The API returns `202` immediately — the UI polls/SSE-watches the status.
2. **Parse** → `pipelines/parser.py`: PyMuPDF for PDFs, python-docx for DOCX, Tesseract OCR for images/scanned PDFs. Produces `{text, page_number}` pages.
3. **Chunk** → `pipelines/chunking.py`: ~600-token segments with 80-token overlap, keeping page numbers. (CPU-bound work is offloaded via `run_in_executor` so the event loop stays responsive.)
4. **Embed** → `pipelines/embeddings.py`: each chunk is embedded (OpenAI-compatible endpoint) and upserted into ChromaDB `knowledge_base` collection with metadata `{project_id, document_id, chunk_index, page_number}`; ID = `"{document_id}_chunk_{index}"`.
5. **Store chunks** → one `document_chunks` row per chunk (with `chroma_id`).
6. **Extract entities & relationships** → `pipelines/entity_extraction.py`:
   - **spaCy NER** (`en_core_web_sm`) finds raw entities, mapped to our types (PERSON→person, ORG→organization, GPE/LOC→location, DATE/TIME→date, …).
   - **LLM** (batched ~1200-token passages, temperature 0.1) returns structured JSON: `{entities: [...], relationships: [...]}`. Output parsed defensively (strips ```json fences).
   - **Merge + dedup** by normalized name; **upsert into `entities`** (unique per project/name/type).
   - **Mentions**: for every chunk, spaCy re-runs and writes one `entity_mentions` row per occurrence → this is what connects entities to chunks/pages.
   - **Relationships**: LLM edges are inserted (deduped on source/target/type). **Fallback**: if the LLM returns no relationships (or errors), `co_occurs_with` edges are derived between every pair of entities mentioned in the same chunk — the graph stays navigable no matter what.
   - Entity extraction failure is **non-fatal** — the document still finishes as `processed`.
7. **Finish** → status `processed`, `processed_at` set; fires `document.processed` webhook. Any hard failure → `status=failed` + `error_message`, and the row is individually retryable (`POST /documents/{id}/retry` re-submits the file).

Live progress is streamed to the UI via **SSE** (`GET /documents/{id}/stream`) — stage events `processing → parsing → chunking → embedding → extracting_entities → complete`.

### How the graph is *read*

- `GET /kb/graph?entity_id=X&depth=2` → NetworkX subgraph → JSON `{nodes, edges}` → **reagraph** (`GraphCanvas`, force-directed layout) in `apps/web/src/app/graph/page.tsx`, colored by entity type, with search, type filters, depth slider, and a details panel (entity info + source sections).
- `GET /kb/entities/{id}` → entity + mentions count + incoming/outgoing relationships.
- `GET /kb/entities/{id}/chunks` → the chunks that mention it (for citations / "source sections" panel).
- **Chat uses graph expansion** (`services/chat.py`): retrieve top-8 chunks → find entities mentioned in them → pull **neighboring entities** via `relationships` (1 hop) → both are injected into the prompt as "Related entities" / "Connected concepts". That's the knowledge-graph value-add over plain RAG.

---

## 7. Request Lifecycle (end to end)

1. **Auth**: browser → Supabase (or mock) gets a session. `middleware.ts` protects routes; `GlobalAuthMiddleware` on the backend requires a Bearer JWT on everything except whitelisted public routes (`/health`, `/auth/...`, `/docs`). In mock mode any token is accepted. SSE endpoints fall back to `?token=` query param because EventSource can't set headers.
2. **Project context**: `core/deps.py::get_project_id` resolves the project from `?project_id=` + membership check in `project_members` (403 if not a member), else auto-detect/auto-create.
3. **Request → router → service → DB**: routers (thin, in `apps/api/routers/`) → services (business logic, `apps/api/services/`) → SQLAlchemy models. Pydantic schemas in `schemas/` validate input/output.
4. **Background work**: ingestion (`_start_ingestion`) and agent runs (`core/task_queue.py`) are `asyncio.create_task` with **strong references kept** in module-level sets — a documented gotcha: without the strong ref, the event loop garbage-collects the pending task mid-run ("Task was destroyed but it is pending") and uploads stay stuck at `pending` forever.
5. **Live updates**: SSE streams for document status and agent task traces (in-memory subscriber queues, event replay for late joiners, cleanup on stream close).

---

## 8. Key Env Variables Quick Reference

Backend `apps/api/.env` (from `core/config.py`):

| Variable | Dev | Prod | Purpose |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | Switches DB + docs URL; prod rejects MOCK_AUTH |
| `DATABASE_URL` | forced to SQLite | `postgresql+asyncpg://…` | Database connection |
| `MOCK_AUTH` | `true` | `false` | Skip Supabase JWT validation |
| `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY/JWKS_URL` | optional | required | Supabase auth |
| `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` | Ollama local | OpenAI/Groq | Text generation |
| `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` | Ollama local | OpenAI/Groq | Embeddings |
| `CHROMA_PATH` | `./chroma_data` | `./chroma_data` | Vector store location |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | frontend URL | CORS allowlist |

Frontend `apps/web/.env.local`:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Prisma (planned) — `file:./dev.db` dev, Postgres prod |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase auth (not needed in mock mode) |
| `NEXT_PUBLIC_MOCK_AUTH` | `"true"` enables demo auto-login |
| `NEXT_PUBLIC_APP_URL` | App base URL |

---

## 9. How to Run It

```bash
# Backend (Terminal 1)
cd apps/api
cp .env.example .env            # dev defaults work out of the box (mock auth + SQLite + Ollama)
uvicorn main:app --reload --port 8000

# Frontend (Terminal 2)
cd apps/web
cp .env.example .env.local
npm install
npm run dev                      # http://localhost:3000

# Optional: local Postgres instead of SQLite
cd infra && docker compose up -d
```

Open `http://localhost:3000` → "Try Demo (Auto-Login)" → upload a PDF → watch it process → explore graph / chat. API docs: `http://localhost:8000/docs`.

> **Note**: `CONTEXT.md` says the user (owner) manages server lifecycle personally — don't start/stop servers for them.

---

## 10. Where the Interesting Code Lives

| Concern | Location |
|---|---|
| Backend entry + middleware + routers | `apps/api/main.py`, `apps/api/core/auth_middleware.py`, `apps/api/routers/` |
| DB models / session | `apps/api/db/models.py`, `apps/api/db/session.py`, `apps/api/init_db.py` |
| Ingestion pipeline | `apps/api/pipelines/ingestion.py` (+ `parser.py`, `chunking.py`, `embeddings.py`, `entity_extraction.py`, `llm_client.py`) |
| Graph traversal (NetworkX) | `apps/api/services/knowledge.py` |
| Chat / RAG + graph expansion | `apps/api/services/chat.py`, `apps/api/routers/chat.py` |
| Agents | `apps/api/pipelines/agent_pipeline.py`, `apps/api/core/task_queue.py`, `apps/api/services/agents.py`, `memory.py` |
| MCP | `apps/api/routers/mcp.py`, `apps/api/services/mcp.py`, `apps/api/core/oauth.py` — **CRUD + OAuth only; no FastMCP server or MCP client exists yet** (see `docs/SPEC.md §12`) |
| Webhooks | `apps/api/services/webhooks.py`, `apps/api/routers/webhooks.py` |
| Auth / project scoping | `apps/api/core/security.py`, `apps/api/core/deps.py`, `apps/api/core/config.py` |
| Graph UI | `apps/web/src/app/graph/page.tsx` (reagraph), `apps/web/src/stores/graph.ts` |
| Chat UI (SSE streaming) | `apps/web/src/app/chat/page.tsx` |
| API client / auth client | `apps/web/src/lib/api/client.ts`, `apps/web/src/lib/supabase/client.ts`, `apps/web/src/middleware.ts` |
| Project switch / state | `apps/web/src/stores/project.ts` (Zustand + localStorage) |

---

## 11. Common Questions

- **Why SQLite AND Postgres?** Zero-friction dev vs. real multi-user deployment — same ORM models, one env flag.
- **Why Prisma if nothing uses it?** It's the documented plan for the frontend's own DB access (SQLite now → Prisma Postgres later). Dependencies + env are ready; `schema.prisma` and client wiring don't exist yet.
- **Why NetworkX instead of Neo4j?** MVP graph sizes don't justify a graph server; rows in Postgres are simpler to back up/query, and the schema is Neo4j-migration-ready.
- **Why one ChromaDB collection?** Single `knowledge_base` collection with `where={"project_id": ...}` metadata filtering — simpler to operate, projects can't bleed into each other.
- **Why is ingestion async?** So upload returns instantly, the dashboard shows real status (pending→processing→processed/failed) via SSE, and the server stays free for chat streaming.
- **What makes chat "graph-aware"?** Beyond vector search, it pulls entities from retrieved chunks, expands to their one-hop neighbors through `relationships`, and feeds that context to the LLM — answers surface connected concepts, not just matched text.
- **Where's the MCP server?** Nowhere yet. `core/oauth.py` (OAuth 2.0 client + PKCE) and the `/mcp/connections` CRUD are real, but the FastMCP server and MCP client were never written — `apps/api/mcp/` is an empty package. Details + build plan: `docs/SPEC.md §12` and `docs/TODO.md §2.1`.
