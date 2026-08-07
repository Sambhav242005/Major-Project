# Editable Surfaces — Build Process Control

## Locked (cannot modify during build)

- `CONTEXT.md` domain glossary — only update when domain terms crystallize, not during implementation
- `docs/adr/` — architecture decisions, append-only (new ADRs only, never edit existing)
- `BUILD_BRIEF.md` — source of truth for requirements, don't modify
- `infra/schema.sql` — schema is source of truth, only modify via Alembic migrations

## Editable (can modify freely)

- `apps/api/routers/` — HTTP layer, adapts to service changes
- `apps/api/services/` — business logic, evolves each phase
- `apps/api/pipelines/` — ingestion/retrieval/extraction logic
- `apps/api/agents/` — LangGraph agent definitions
- `apps/api/mcp/` — MCP server/client
- `apps/api/schemas/` — request/response models
- `apps/api/core/` — config, security, errors
- `apps/web/src/` — frontend components and pages
- `apps/api/tests/` — test files

## Append-Only

- `CHANGELOG.md` — phase summaries, failure mines, lessons learned
- `apps/api/tests/` — tests only grow, never delete passing tests
- `audit_log` table — runtime audit trail

## Human-Controlled

- Supabase project creation and schema migration (manual SQL Editor)
- Environment variable setup (.env files)
- Vercel/Railway deployment configuration
- Phase completion decisions (human verifies before marking done)
