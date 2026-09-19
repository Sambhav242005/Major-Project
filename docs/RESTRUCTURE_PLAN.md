# Backend Restructure Plan — apps/api

> Goal: each file <200 lines, single responsibility, easy to find. Preserve import paths via `__init__.py` re-exports.

## Principles
- Package-per-domain, file-per-concern. Re-export in `__init__.py` so `from X import Y` keeps working.
- One PR per package when executing (atomic, test-gated).
- No BUILD_BRIEF.md change.

## Current Hotspots (wc -l)
- tests/test_memory.py 761, pipelines/agent_pipeline 564, agent_refinement 466, services/agents 413, extraction 401, services/chat 400, memory 392, google_meet 377, routers/agents 358, agent_tools 352, routers/documents 318, webhooks 308, core/oauth 306

## Target Layout

```
apps/api/
  main.py -> app/factory.py + routers/system.py
  core/
    oauth/ tokens.py pkce.py client.py persistence.py factory.py __init__.py
    task_queue/ pubsub.py executor.py __init__.py
    auth_middleware.py deps.py (or core/auth/ middleware.py deps.py)
  pipelines/
    agent/ types.py state.py graph.py executor.py nodes/{lifecycle,llm,eval}.py __init__.py
    refinement/ evaluation.py traces.py skills.py gate.py constants.py __init__.py
    tools/ registry.py search_tools.py knowledge_tools.py write_tools.py __init__.py
    extraction/ ner.py chunking.py llm_extract.py merge.py pipeline.py __init__.py
    ingestion/ notifier.py pipeline.py runner.py __init__.py
    embeddings/ client.py embedding_function.py store.py query.py __init__.py
  services/
    agents/ crud.py skills.py tasks.py executor.py __init__.py
    chat/ sessions.py retrieval.py prompt.py streaming.py __init__.py
    memory/ crud.py search.py checkpoints.py hydration.py __init__.py
    meet/ browser.py recording.py transcription.py analysis.py errors.py __init__.py
    webhooks/ signing.py outbound.py dispatch.py inbound.py __init__.py
    knowledge/ search.py graph.py __init__.py
    documents/ crud.py content.py stats.py __init__.py
    sharing/ permissions.py retrieval.py __init__.py
  routers/
    agents/ schemas.py crud.py execution.py memory.py __init__.py
    documents/ validation.py ingestion_tasks.py router.py __init__.py
    mcp/ schemas.py connections.py oauth_flow.py __init__.py
    system.py
  db/model_defs/
    agents/ core.py memory.py refinement.py __init__.py
    integrations/ mcp.py webhooks.py sharing.py __init__.py
  tests/
    memory/ conftest.py test_store.py test_retrieve_search.py test_lifecycle.py test_hydration.py test_utils.py
```

## Execution Order (parallel-safe batches)
1. Pipelines extraction + tools + refinement + agent (no router/service dep)
2. Services knowledge/documents/sharing (DB only)
3. Services memory/webhooks/meet (isolated)
4. Services chat/agents + core oauth/task_queue
5. Routers agents/documents/mcp + main factory
6. DB model_defs + tests

Each batch: read -> split -> re-export -> py_compile -> pytest held_in 46.

## Future Improvements Included
- P7 N+1 fix in knowledge/graph (batch IN / selectinload)
- P8 indexes migration
- P10 routers/documents retry project scoping
- shared sse pubsub dedup (agents task_queue + documents)
- pgvector for memory search (replace in-python cosine)
- router registry loop in factory
- pagination/sort common schemas

## Verification
- `python -m py_compile` every new file
- `grep -ri prisma apps/web/src` -> 0
- `pytest tests/test_security_utils.py tests/test_llm_config.py` -> 46 pass (held_in)
