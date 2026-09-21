# Architecture Notebook — Incremental Backend Analysis

> Maintained incrementally. One module at a time. No re-reading without need.

## 0. Project Map (Structure Only — Batch 1)

```
Major-Project/
├── apps/api      — FastAPI (Python 3.11, async SQLAlchemy, ChromaDB, LangGraph)
│   ├── main.py           — entry + app factory
│   ├── core/             — config, auth, middleware, errors, rate_limit, deps, security
│   ├── db/               — models.py + model_defs/ + session.py  (SQLAlchemy async)
│   ├── routers/          — 11 routers (auth, documents, kb, chat, dashboard, agents, mcp, meetings, projects, sharing, webhooks)
│   ├── services/         — business logic mirror of routers (12 files)
│   ├── schemas/          — Pydantic request/response
│   ├── pipelines/        — ingestion, chunking, embeddings, parser, agent_pipeline, llm_client
│   ├── migrations/       — alembic (001-004)
│   ├── tests/            — 20 test files
│   ├── pyproject.toml / requirements.txt / uv.lock / alembic.ini / docker-compose.yml
│   └── init_db.py
├── apps/web      — Next.js 15 (App Router, Tailwind, Zustand, reagraph)
│   ├── src/app/(app)     — agents, chat, dashboard, documents, graph, mcp, meetings, projects, webhooks
│   ├── src/components/features/* — 1:1 with app routes
│   ├── src/hooks, stores, lib, middleware.ts
│   └── package.json, tailwind, next.config
├── apps/packages/shared-types
├── infra         — schema.sql (Postgres/Supabase), docker-compose.yml
├── docs          — SPEC.md, HOW_IT_WORKS.md, TODO.md, adr/
├── research/
├── BUILD_BRIEF.md (locked)
├── CONTEXT.md    (glossary + design system)
└── AGENTS.md     (agent guardrails)
```

**Framework detection:** FastAPI + SQLAlchemy async + Pydantic v2 + Supabase Auth + Chroma PersistentClient + OpenAI-compatible LLMs (qwen/qwen3.8-27b). Single ORM confirmed. Vector isolation via where={"project_id": ...}.

## 1. Inventory — Files Inspected

| # | File | Purpose | Status |
|---|------|---------|--------|
| 1 | apps/api/main.py | App factory, middleware order, router registration, /health, /system/status | Complete (68 lines) |
| 2 | apps/api/core/config.py | Centralized Settings (BaseSettings), env validation, MOCK_AUTH guard, DB/LLM/Chroma/Meet/CORS | Complete (68 lines) |
| 3 | apps/api/requirements.txt | 30 deps: fastapi, uvicorn, sqlalchemy[asyncio], supabase, chromadb, langgraph, mcp, openai, slowapi, playwright etc | Complete |
| 4 | apps/web/package.json | Next 15, React 19, Zustand, TanStack Query, reagraph, supabase-js | Complete |
| 5 | infra/schema.sql | Postgres schema (profiles, projects, project_members, documents, chunks, entities, mentions, relationships…) | Partial (head 80) |
| 6 | apps/api/core/deps.py | Project resolution, _ensure_user_and_project, get_project_id | In Progress (partial read ~60 lines) |

**Pending (dependency-flow order):**
- core/config.py → main.py → db/session.py → core/deps.py → core/errors.py → core/auth_middleware.py → core/security.py → routers/* → services/* → pipelines/* → db/models → tests

## 2. Module Responsibilities (so far)

- **main.py:** Thin composition root. Correct middleware order: SecurityHeaders → GlobalAuth → CORS. 11 routers mounted. Rate limiter wired via app.state. No business logic — good.

- **core/config.py:** Single Settings object. Two model_validators: _force_sqlite_in_dev (ENVIRONMENT=development forces sqlite+aiosqlite) and _reject_mock_in_prod. Concern: _force_sqlite_in_dev silently overrides DATABASE_URL even when user explicitly sets it in dev; should be documented or allow opt-out. CORS_ORIGINS defaults to localhost:3000 only.

- **core/deps.py:** Resolves project_id from user membership, auto-creates profile + default project. Uses deterministic UUID5 from user string id. Executed per-request via Depends.

## 3. Dependency Relationships

```
main.py → core/{config, errors, rate_limit, auth_middleware, security_headers}
      → routers/* → services/* → db/session + db/models + pipelines
      → core/deps → core/security (get_current_user) → db/session
```

## 4. API Request Flow (draft)

```
Client → SecurityHeadersMiddleware → GlobalAuthMiddleware (sets request.state.user)
       → CORSMiddleware → RateLimit (slowapi) → Router → deps.get_project_id
       → Service → DB (SQLAlchemy async) + Chroma + LLM
       → Pydantic schema → JSON
Error path: AppError → app_error_handler → JSONResponse
```

## 5. Database Access Flow (draft)

```
SQLAlchemy async engine (db/session.py) → async_session_factory → AsyncSession
  → models.py / model_defs/* → Postgres (prod) / SQLite (dev forced)
ChromaDB PersistentClient(path=CHROMA_PATH) → knowledge_base collection → where filter by project_id
```

## 6. Identified Problems (preliminary — to validate as we read)

- [P1] core/config.py: _force_sqlite_in_dev silently overrides DATABASE_URL — breaks docker-compose Postgres in dev. Needs explicit opt-in or warning.
- [P2] main.py: routers imported eagerly; no versioning (/api/v1). 11 routers flat under / — will need versioning later.
- [P3] deps.py: uses deterministic UUID5 from user string; potential collision risk if Supabase ids are already UUIDs? Needs inspection of full file.
- [P4] No centralized validation layer visible yet — need to check schemas/ + security_utils.
- [P5] Chroma single collection + where filter — verify isolation enforced everywhere (check services/knowledge.py, embeddings.py).
- [P6] No structured logging correlation ID seen yet — check core/task_queue.py, services.
- [Pending] Check for N+1, blocking ops, error leakage, secret exposure, pagination gaps — need service + pipeline reads.

## 7. Proposed Target Structure (draft — subject to validation)

Keep layered modular monolith — no need for clean/DDD overkill at this scale. Improvements:

```
apps/api/
├── app/                  # composition root (currently main.py)
├── core/                 # config, security, middleware, errors, deps
│   ├── config.py
│   ├── security/         # auth, oauth, rate_limit, headers consolidated
│   └── deps.py
├── api/
│   └── v1/               # versioned router aggregation
├── modules/              # domain modules (documents, chat, knowledge, agents, etc.)
│   ├── documents/{router, service, schemas, repository}
│   └── ...
├── db/                   # session, models, migrations
├── pipelines/            # ingestion, chunking, embeddings, llm
├── services/             # cross-cutting services (audit, sharing, webhooks)
└── tests/
```

But: Do NOT move files yet. Validate existing patterns first (sample 2-3 routers/services) to decide disciplined vs transitional.

## 8. Refactoring Status

| Module | Analysis | Refactor | Tests |
|--------|----------|----------|-------|
| Project structure + config | Complete | Pending | — |
| Entry + middleware | Complete | Pending | — |
| deps + auth | In Progress | — | — |
| routers/services | Pending | — | — |
| pipelines | Pending | — | — |
| db/models | Pending | — | — |

## 9. Next File to Inspect

**db/session.py** — to confirm engine creation, pool config, async_session_factory lifecycle, and whether dev SQLite override is consistent with config.

Reason: config forces SQLite in dev; session.py is where the engine is built. Must see if it respects that or duplicates logic, and check connection pooling for prod.

Alternative if session.py is trivial: **core/errors.py** next (error handling centralization), then **core/auth_middleware.py**.

---
*Last updated: 2026-09-19 — Batch 1 (structure + entry + config)*
