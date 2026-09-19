# Architecture Notebook — Incremental Backend Analysis

> Maintained incrementally. One module at a time. No re-reading without need.
> Plow-ahead mode: autonomous bounded edits with two-split evidence gate + filesystem archive.

## 0. Project Map (Structure Only — Batch 1)

```
Major-Project/
├── apps/api      — FastAPI (Python 3.11, async SQLAlchemy, ChromaDB, LangGraph)
│   ├── main.py           — entry + app factory (68 lines, clean composition root)
│   ├── core/             — config, auth, middleware, errors, rate_limit, deps, security
│   ├── db/               — models.py re-export + model_defs/7 domain files + session.py  (SQLAlchemy async)
│   ├── routers/          — 11 routers (auth, documents, kb, chat, dashboard, agents, mcp, meetings, projects, sharing, webhooks)
│   ├── services/         — 12 service modules (mirror of routers + audit/memory)
│   ├── schemas/          — Pydantic request/response
│   ├── pipelines/        — ingestion, chunking, embeddings, parser, agent_pipeline, llm_client
│   ├── migrations/       — alembic 001-004
│   ├── tests/            — 20 test files
│   └── pyproject.toml / requirements.txt (30 deps) / alembic.ini
├── apps/web      — Next.js 15 (App Router, Tailwind, Zustand, reagraph)
├── infra         — schema.sql (Postgres/Supabase, RLS) + docker-compose.yml
└── docs          — SPEC.md verified, TODO.md, HOW_IT_WORKS.md, adr/
```

Framework: FastAPI + SQLAlchemy async + Pydantic v2 + Supabase Auth + Chroma PersistentClient + OpenAI-compatible LLMs (qwen/qwen3.8-27b). Single ORM confirmed. Vector isolation via where={"project_id": ...}. Middleware order SecurityHeaders → GlobalAuth → CORS is correct.

## 1. Inventory — Files Inspected (dependency-flow order)

| # | File | Lines | Purpose | Status |
|---|------|-------|---------|--------|
| 1 | apps/api/main.py | 68 | App factory, middleware order, router registration | Complete |
| 2 | apps/api/core/config.py | 69 | Centralized Settings (BaseSettings), validators | Complete → fixed c0001 |
| 3 | apps/api/db/session.py | 40 | Engine + async_sessionmaker + Base + get_db | Complete → fixed c0002 |
| 4 | apps/api/core/errors.py | 81 | AppError hierarchy + app_error_handler | Complete (clean, no leakage) |
| 5 | apps/api/core/security.py | 90 | Supabase JWT RS256, JWKS fetch, User, get_current_user | Complete → fixed c0003 |
| 6 | apps/api/core/auth_middleware.py | 100 | GlobalAuthMiddleware, PUBLIC_ROUTES, MOCK_AUTH bypass | Complete (duplication noted, cache fix propagates) |
| 7 | apps/api/core/deps.py | ~110 | _ensure_user_and_project, get_project_id (UUID5 deterministic) | Partial (head 60) — collision risk noted |
| 8 | apps/api/db/models.py + model_defs/* | 30-53 each | Domain models: Profile/Project/Member, Document/Chunk, Entity/Mention/Relationship | Complete (FKs ok, no indexes beyond PK/UC) |
| 9 | apps/api/routers/documents/ | feature router + ingestion tasks | Upload (202), list, get, status, chunks, entities, delete, retry, SSE stream | Complete (strong task refs, todo storage) |
| 10 | apps/api/services/documents/ | feature package | Upload/status/list/delete/chunks/entities + counts | Complete → fixed c0004 |
| 11 | apps/api/pipelines/ingestion/ | feature package | Parse→chunk→embed→store→extract, _offload via run_in_executor | Complete (correctly offloops sync work) |
| 12 | apps/api/routers/kb.py | 60 | search/entities/chunks/graph | Complete (sanitize_input + top_k guard) |
| 13 | apps/api/services/knowledge/ | feature package | search + get_entity + get_graph + get_entity_chunks (N+1) | Complete → fixed c0005 |
| 14 | apps/api/pipelines/embeddings/ | feature package | Chroma PersistentClient, OpenAICompatibleEmbedding, upsert/query/delete | Complete (where filter isolation ok) |

Pending low-priority: routers/chat, agents, mcp, meetings, webhooks + services/chat etc. Samples show disciplined vs transitional: routers delegate to services (good), but some routers contain business logic (documents retry branch). Overall Transitional.

## 2. Dependency Relationships

```
main.py → core/{config, errors, rate_limit, auth_middleware, security_headers}
      → routers/* → services/* → db/session + db/models + pipelines
      → core/deps → core/security (get_current_user) → db/session
pipelines/ingestion → pipelines/{parser, chunking, embeddings, entity_extraction} → services/documents → db
```

## 3. API Request Flow

```
Client → SecurityHeadersMiddleware → GlobalAuthMiddleware (state.user_id) → CORS → slowapi limiter
       → Router (Depends[get_project_id, get_current_user, get_db]) → Service → DB (async) + Chroma + LLM
       → Pydantic schema → JSON
Error: AppError → app_error_handler → {"error":{"code","message"}} (no stack leak)
```

## 4. Database Access Flow

```
create_async_engine(DATABASE_URL) → async_sessionmaker(expire_on_commit=False)
  → get_db yields AsyncSession, commits on success, rolls back on exception
  → Postgres (prod, pool_pre_ping) / SQLite (dev, check_same_thread=False)
Chroma PersistentClient(path=CHROMA_PATH) → knowledge_base collection (cosine) → where={"project_id":...}
```

## 5. Identified Problems (validated)

| ID | Location | Problem | Impact | Fixed? |
|----|----------|---------|--------|--------|
| P1 | core/config.py:_force_sqlite_in_dev | Silently overwrote DATABASE_URL even when docker-compose Postgres was set | Dev Postgres broken | c0001 |
| P2 | db/session.py:_get_engine | echo=True for sqlite, no pool_pre_ping, no check_same_thread | Perf + noisy logs | c0002 |
| P3 | core/security.py:_fetch_jwks | No TTL, no timeout | Stale keys, hang | c0003 |
| P4 | core/auth_middleware.py + security.py | Duplicated JWT decode | DRY risk (cache fix shared) | Partial |
| P5 | services/documents/ | Duplicated _doc dict, unbounded list_documents | DRY, DoS | c0004 |
| P6 | services/knowledge/search.py | N+1 — 2N queries per search | Latency | c0005 |
| P7 | services/knowledge/graph.py | N+1 per relationship | Same pattern | Pending |
| P8 | db/model_defs/* | Only PK/unique indexes | Slow scans | Pending migration |
| P9 | main.py | No API versioning | Future breakage | Deferred |
| P10 | routers/documents/router.py:retry | Direct db.get without project scoping | Hardening needed | Deferred |

## 6. Target Structure — Restructured 2026-09-19 (multi-agent)

All hotspots >300 lines split into <200-line focused modules, with `__init__.py` re-exports preserving import paths.

```
apps/api/
  app/factory.py           — create_app() (extracted from main.py)
  main.py                  — shim: from app.factory import create_app
  core/
    oauth/ tokens.py pkce.py client.py persistence.py factory.py
    task_queue/ pubsub.py executor.py
    (auth_middleware, deps, errors, config, security remain)
  pipelines/
    agent/ types.py state.py graph.py executor.py nodes/{lifecycle,llm,eval}.py
    refinement/ constants.py evaluation.py traces.py skills.py gate.py
    tools/ registry.py search_tools.py knowledge_tools.py write_tools.py
    extraction/ ner.py chunking.py llm_extract.py merge.py pipeline.py
    ingestion/ notifier.py pipeline.py runner.py
    embeddings/ client.py embedding_function.py store.py query.py
  services/
    agents/ crud.py skills.py tasks.py executor.py
    chat/ sessions.py retrieval.py prompt.py streaming.py
    memory/ crud.py search.py checkpoints.py hydration.py
    meet/ browser.py recording.py transcription.py analysis.py
    webhooks/ signing.py outbound.py dispatch.py inbound.py
    knowledge/ search.py graph.py
    documents/ crud.py content.py stats.py
    sharing/ permissions.py retrieval.py
  routers/
    agents/ schemas.py crud.py execution.py memory.py
    documents/ validation.py ingestion_tasks.py router.py
    mcp/ schemas.py connections.py oauth_flow.py
    system.py              — /health + /system/status
  db/model_defs/
    agents/ core.py memory.py refinement.py
    integrations/ mcp.py webhooks.py sharing.py audit.py
  tests/memory/ conftest.py test_store.py test_retrieve_search.py test_lifecycle.py test_hydration.py test_utils.py
```
All original `.py` shims kept where files were deleted (agent_pipeline, agent_refinement, agent_tools, entity_extraction, ingestion, embeddings, knowledge, documents, memory, sharing, webhooks, google_meet, oauth, task_queue, routes). Largest file now 196 lines (routers/projects.py, untouched — optional next batch).

Execution: 4 parallel exploration agents + 7 execution agents (pipelines×2, services×2, core/routers, db+tests, factory). Plan: docs/RESTRUCTURE_PLAN.md.

## 7. Self-Improvement Loop Applied

- Locked: evaluator (pytest), runtime budgets/permissions, branch protection, BUILD_BRIEF.md
- Editable: core/config.py, db/session.py, core/security.py, services/documents/, services/knowledge/ (one per candidate) + restructure packages (new)
- Archive: search-run/candidates/c0001..c0005 (harness.py + scores.json + traces/ + lineage.txt), frontier.json, rejected.jsonl
- Gate: held_in 46 tests no-regression ∧ held_out no-regression (partial, full suite blocked by missing deps). No rationale acceptance.
- Raw traces retained (proposer greps archive, not summarized)

## 8. Bounded Edit Log

| Candidate | Surface | Pattern | Fix | Scores | Decision |
|-----------|---------|---------|-----|--------|----------|
| c0001 | core/config.py | SQLite override | Only force when no postgres URL | 46/46 | ACCEPT |
| c0002 | db/session.py | Echo/pool | Conditional echo, pool_pre_ping, check_same_thread | 46/46 | ACCEPT |
| c0003 | core/security.py | JWKS cache | TTL 3600s + timeout 5s | 42/42 | ACCEPT |
| c0004 | services/documents/ | Dup + unbounded | _doc_to_dict + limit/offset guard | 46/46 | ACCEPT |
| c0005 | services/knowledge/search.py | N+1 search | Batch IN queries (2 vs 2N) | 42/42 | ACCEPT |
| restructure | 30+ files | God-file split | Packages + shims, each <200 lines | 128/128* | ACCEPT |

* restructure gate: 46 held_in + 82 targeted (documents, oauth, memory, entity_extraction, chunking, audit, rate_limit) = 128 passed. Full suite 185/203 passed; 18 pre-existing failures (auth/chat/idor/knowledge) confirmed via stash baseline.

All edits: py_compile OK, grep guards OK (prisma 0, chunk_index present, qwen intact).

## 9. Verification

- py_compile: all files OK (find + py_compile exit 0)
- pytest held_in: 46 passed — no regression
- pytest targeted: 128 passed (security_utils, llm_config, documents, oauth, memory/*, entity_extraction, chunking, audit, rate_limit)
- grep: prisma 0, BUILD_BRIEF untouched
- Remaining debt: P7, P8, P9, P10 — tracked as pending candidates; restructure plan doc: docs/RESTRUCTURE_PLAN.md

## 10. Future Improvements (from restructure plan)

- P7 batch IN fix in knowledge/graph (get_entity, get_entity_chunks)
- P8 composite indexes migration
- P10 routers/documents retry project scoping
- shared sse pubsub dedup (task_queue + documents ingestion_tasks)
- pgvector for memory search (replace in-python cosine)
- router registry loop in app/factory.py
- pagination/sort common schemas

---
*Last updated: 2026-09-19 — Batch 8 (multi-agent restructure: 4 explorers + 7 executors, 30+ files split, 128 targeted tests passed)*
