# Architecture Refactoring Plan — AI Knowledge Graph Builder

## 1. Audit Summary

### What Copilot Did (branch `copilot/refactor-project-architecture`)
- Split `apps/api/db/models.py` (462-line monolith) → `db/model_defs/` (6 domain files)
- Split `apps/api/schemas/__init__.py` (314-line monolith) → `schemas/` (8 domain files)
- **Did NOT touch:** routers, services, pipelines, core, frontend, tests, configs

### What Remains Unfinished
The Copilot branch was a partial scaffolding pass. The deeper architectural problems were not addressed.

---

## 2. Architectural Issues Identified

### Backend Issues

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| B1 | **Monolithic frontend pages** — `agents/page.tsx` is 1154 lines, `graph/page.tsx` is 432 lines, `chat/page.tsx` is 383 lines. No component extraction, no hooks, no feature folders. | HIGH | `apps/web/src/app/` |
| B2 | **No feature-based organization in frontend** — flat `components/` with only 11 files (6 are shadcn/ui). All business logic lives inside page files. | HIGH | `apps/web/src/components/` |
| B3 | **Backend services are function dumps** — `services/agents.py` (413 lines), `services/chat.py` (400 lines), `services/memory.py` (392 lines). No class structure, no interfaces. | MEDIUM | `apps/api/services/` |
| B4 | **Backend pipelines mix concerns** — `pipelines/agent_pipeline.py` (564 lines) handles LangGraph orchestration, task state, and SSE events in one file. | MEDIUM | `apps/api/pipelines/` |
| B5 | **`core/` is a grab bag** — config, auth, security, rate limiting, task queue, error handling, middleware all in one flat directory (11 files). Some belong in separate modules. | MEDIUM | `apps/api/core/` |
| B6 | **No shared types between frontend/backend** — `apps/packages/shared-types/` is empty (only `package.json`). Types are duplicated across Python schemas and TypeScript interfaces. | LOW | `apps/packages/` |
| B7 | **Research scripts are loose** — `research/` has 4 ad-hoc scripts with no structure, no tests. | LOW | `research/` |
| B8 | **SSE subscriber pattern is scattered** — in-memory SSE subscribers live inside `routers/documents.py` (lines 28-57) and `core/task_queue.py`. No central real-time event bus. | LOW | Multiple files |
| B9 | **Tests are flat** — 22 test files in a single directory, no grouping by domain, no conftest fixtures. | LOW | `apps/api/tests/` |

### Frontend-Specific Issues

| # | Issue | Severity | Location |
|---|-------|----------|----------|
| F1 | **Page files contain all logic** — data fetching, state management, UI rendering, API calls, and error handling all in one file. No separation. | HIGH | All `page.tsx` files |
| F2 | **No shared UI patterns** — `DashboardHeader` is used in 8+ pages but imported directly. No layout wrappers or shared shells. | MEDIUM | `apps/web/src/components/` |
| F3 | **No feature hooks** — data fetching (useEffect + fetch) is repeated in every page. No `useDocuments()`, `useChat()`, `useGraph()` hooks. | MEDIUM | All pages |
| F4 | **Stores are minimal** — only 2 Zustand stores (`graph.ts`, `project.ts`). Chat state, document state, agent state all live in local useState. | MEDIUM | `apps/web/src/stores/` |
| F5 | **No TypeScript types file** — interfaces are defined inline in each page file (e.g., `DashboardData`, `ChatMessage`, `Agent`). Duplicated across files. | MEDIUM | All pages |

---

## 3. Proposed Target Structure

### Backend (`apps/api/`)

```
apps/api/
├── main.py                          # FastAPI app entry (unchanged)
├── alembic.ini
├── requirements.txt
├── pyproject.toml
├── init_db.py
│
├── core/                            # ── Infrastructure layer ──
│   ├── __init__.py
│   ├── config.py                    # Settings (unchanged)
│   ├── errors.py                    # Error hierarchy (unchanged)
│   ├── deps.py                      # FastAPI dependencies (unchanged)
│   ├── security.py                  # JWT/auth (unchanged)
│   ├── security_utils.py            # Input sanitization (unchanged)
│   ├── security_headers.py          # CSP middleware (unchanged)
│   ├── auth_middleware.py            # Auth middleware (unchanged)
│   ├── rate_limit.py                # SlowAPI limiter (unchanged)
│   ├── task_queue.py                # asyncio task management (unchanged)
│   └── oauth.py                     # MCP OAuth (unchanged)
│
├── db/                              # ── Data layer ──
│   ├── __init__.py
│   ├── session.py                   # Engine, session factory (unchanged)
│   ├── models.py                    # Re-export barrel (unchanged)
│   └── model_defs/                  # Domain-split models (Copilot did this)
│       ├── __init__.py
│       ├── base.py
│       ├── agents.py
│       ├── chat.py
│       ├── documents.py
│       ├── integrations.py
│       ├── knowledge.py
│       └── projects.py
│
├── schemas/                         # ── Pydantic schemas (Copilot did this) ──
│   ├── __init__.py                  # Re-export barrel
│   ├── agents.py
│   ├── chat.py
│   ├── dashboard.py
│   ├── documents.py
│   ├── entities.py
│   ├── graph.py
│   ├── mcp.py
│   └── search.py
│
├── routers/                         # ── HTTP layer (thin) ──
│   ├── __init__.py
│   ├── auth.py
│   ├── documents.py
│   ├── kb.py
│   ├── chat.py
│   ├── dashboard.py
│   ├── agents.py
│   ├── mcp.py
│   ├── meetings.py
│   ├── projects.py
│   ├── sharing.py
│   └── webhooks.py
│
├── services/                        # ── Business logic ──
│   ├── __init__.py
│   ├── documents.py
│   ├── knowledge.py
│   ├── chat.py
│   ├── dashboard.py
│   ├── agents.py
│   ├── memory.py
│   ├── embeddings.py
│   ├── mcp.py
│   ├── sharing.py
│   ├── webhooks.py
│   ├── audit.py
│   └── google_meet.py
│
├── pipelines/                       # ── Data processing ──
│   ├── __init__.py
│   ├── ingestion.py
│   ├── parser.py
│   ├── chunking.py
│   ├── embeddings.py
│   ├── entity_extraction.py
│   ├── llm_client.py
│   ├── agent_pipeline.py
│   ├── agent_refinement.py
│   └── agent_tools.py
│
├── migrations/                      # ── Alembic ──
│   ├── env.py
│   └── versions/
│
└── tests/                           # ── Test suite ──
    ├── __init__.py
    ├── conftest.py                  # Shared fixtures (NEW)
    ├── test_auth.py
    ├── test_documents.py
    ├── test_chunking.py
    ├── test_entity_extraction.py
    ├── test_knowledge.py
    ├── test_chat.py
    ├── test_dashboard.py
    ├── test_agents.py
    ├── test_mcp.py
    ├── test_memory.py
    ├── test_audit.py
    ├── test_idor.py
    ├── test_oauth.py
    ├── test_rate_limit.py
    ├── test_security_utils.py
    ├── test_llm_config.py
    ├── test_refinement_loop.py
    ├── test_integration.py
    └── test_integration_quick.py
```

**Backend decision: Keep the current structure.** The backend is already well-organized into `core/`, `db/`, `schemas/`, `routers/`, `services/`, `pipelines/`. The Copilot branch correctly split models and schemas. The routers are thin, services handle logic, pipelines handle data processing. This is a clean layered architecture. No restructuring needed.

### Frontend (`apps/web/`)

This is where the major refactoring is needed.

**Current state:** Every page file is a monolith (200-1154 lines) containing all data fetching, state, and UI.

**Target state:** Feature-based organization with shared hooks, types, and components.

```
apps/web/src/
├── app/                             # ── Next.js App Router ──
│   ├── layout.tsx                   # Root layout (unchanged)
│   ├── page.tsx                     # Landing (unchanged)
│   ├── globals.css
│   ├── error.tsx
│   ├── global-error.tsx
│   ├── not-found.tsx
│   │
│   ├── auth/                        # Auth pages (unchanged)
│   │   ├── callback/
│   │   ├── demo-login/
│   │   ├── signin/
│   │   ├── signout/
│   │   └── signup/
│   │
│   ├── (app)/                       # ── Authenticated layout group ──
│   │   ├── layout.tsx               # Dashboard shell with header (NEW)
│   │   ├── dashboard/
│   │   │   └── page.tsx             # Thin page → uses components
│   │   ├── documents/
│   │   │   ├── page.tsx
│   │   │   └── [id]/
│   │   │       └── page.tsx
│   │   ├── chat/
│   │   │   └── page.tsx
│   │   ├── graph/
│   │   │   └── page.tsx
│   │   ├── agents/
│   │   │   └── page.tsx
│   │   ├── mcp/
│   │   │   └── page.tsx
│   │   ├── meetings/
│   │   │   └── page.tsx
│   │   ├── webhooks/
│   │   │   └── page.tsx
│   │   ├── projects/
│   │   │   └── page.tsx
│   │   ├── contact/
│   │   │   └── page.tsx
│   │   └── terms/
│   │       └── page.tsx
│   │
│   └── demo/
│       └── page.tsx
│
├── components/                      # ── Shared UI ──
│   ├── ui/                          # shadcn/ui (unchanged)
│   │   ├── badge.tsx
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── input.tsx
│   │   └── table.tsx
│   ├── motion/                      # Animation components (unchanged)
│   │   ├── animated-list.tsx
│   │   ├── motion-button.tsx
│   │   └── reveal.tsx
│   ├── layout/                      # ── Layout components (NEW grouping) ──
│   │   ├── dashboard-header.tsx     # MOVED from components/
│   │   ├── public-header.tsx        # MOVED from components/
│   │   └── project-switcher.tsx     # MOVED from components/
│   ├── shared/                      # ── Shared widgets (NEW grouping) ──
│   │   ├── ErrorBoundary.tsx        # MOVED from components/
│   │   ├── StatusPill.tsx           # MOVED from components/
│   │   ├── status-indicator.tsx     # MOVED from components/
│   │   ├── UploadDropzone.tsx       # MOVED from components/
│   │   └── theme-provider.tsx       # MOVED from components/
│   │   └── theme-toggle.tsx         # MOVED from components/
│   │
│   ├── features/                    # ── Feature components (ALL NEW) ──
│   │   ├── dashboard/
│   │   │   ├── StatsGrid.tsx        # Extracted from dashboard/page.tsx
│   │   │   ├── PipelineHealth.tsx   # Extracted
│   │   │   ├── FailedDocuments.tsx  # Extracted
│   │   │   ├── QuickLinks.tsx       # Extracted
│   │   │   └── RecentActivity.tsx   # Extracted
│   │   ├── documents/
│   │   │   ├── DocumentList.tsx     # Extracted from documents/page.tsx
│   │   │   ├── DocumentUpload.tsx   # Extracted
│   │   │   ├── DocumentDetail.tsx   # Extracted from documents/[id]/page.tsx
│   │   │   └── DocumentChunks.tsx   # Extracted
│   │   ├── chat/
│   │   │   ├── ChatWindow.tsx       # Extracted from chat/page.tsx
│   │   │   ├── ChatMessage.tsx      # Extracted
│   │   │   ├── ChatInput.tsx        # Extracted
│   │   │   └── Citations.tsx        # Extracted
│   │   ├── graph/
│   │   │   ├── GraphView.tsx        # Extracted from graph/page.tsx
│   │   │   ├── EntityPanel.tsx      # Extracted
│   │   │   ├── GraphControls.tsx    # Extracted
│   │   │   └── entity-colors.ts     # Extracted constants
│   │   ├── agents/
│   │   │   ├── AgentList.tsx        # Extracted from agents/page.tsx (1154 lines!)
│   │   │   ├── AgentRunner.tsx      # Extracted
│   │   │   ├── AgentTaskLog.tsx     # Extracted
│   │   │   ├── AgentCreator.tsx     # Extracted
│   │   │   └── AgentTypeCard.tsx    # Extracted
│   │   ├── mcp/
│   │   │   ├── MCPConnectionList.tsx
│   │   │   └── MCPOAuthFlow.tsx
│   │   ├── meetings/
│   │   │   └── MeetingBot.tsx
│   │   ├── webhooks/
│   │   │   ├── WebhookList.tsx
│   │   │   └── WebhookForm.tsx
│   │   └── projects/
│   │       └── ProjectList.tsx
│   │
│   └── providers/                   # ── Context providers (NEW) ──
│       └── auth-provider.tsx        # Supabase auth context (NEW)
│
├── hooks/                           # ── Custom hooks (ALL NEW) ──
│   ├── useAuth.ts                   # Supabase auth hook
│   ├── useDocuments.ts              # Document CRUD + SSE
│   ├── useChat.ts                   # Chat session + streaming
│   ├── useGraph.ts                  # Graph data + entity selection
│   ├── useAgents.ts                 # Agent CRUD + task polling
│   ├── useDashboard.ts              # Dashboard summary
│   ├── useMCP.ts                    # MCP connections
│   ├── useWebhooks.ts               # Webhook CRUD
│   └── useProject.ts                # Project switching (wraps store)
│
├── lib/                             # ── Utilities (mostly unchanged) ──
│   ├── api/
│   │   └── client.ts               # API fetcher (unchanged)
│   ├── supabase/
│   │   ├── client.ts                # Browser client (unchanged)
│   │   └── server.ts                # Server client (unchanged)
│   ├── types.ts                     # ── Shared TypeScript types (NEW) ──
│   ├── utils.ts                     # cn() helper (unchanged)
│   └── validators.ts               # Zod schemas (unchanged)
│
├── stores/                          # ── Zustand stores ──
│   ├── project.ts                   # Project state (unchanged)
│   ├── graph.ts                     # Graph state (unchanged)
│   ├── chat.ts                      # Chat state (NEW — extracted from page)
│   ├── documents.ts                 # Document state (NEW — extracted from page)
│   └── agents.ts                    # Agent state (NEW — extracted from page)
│
└── middleware.ts                     # Auth + security (unchanged)
```

---

## 4. File Migration Plan

### Phase 1: Frontend Type Definitions (no behavior change)

**Goal:** Create `lib/types.ts` with all shared TypeScript interfaces.

| New File | Source | What |
|----------|--------|------|
| `lib/types.ts` | Inline in pages | All shared interfaces: `Document`, `Entity`, `Relationship`, `ChatMessage`, `ChatSession`, `Agent`, `AgentTask`, `DashboardData`, `GraphNode`, `GraphEdge`, `MCPConnection`, `Webhook` |

### Phase 2: Custom Hooks Extraction (no behavior change)

**Goal:** Extract data-fetching + state logic from pages into reusable hooks.

| New File | Extracted From | Lines Saved |
|----------|---------------|-------------|
| `hooks/useAuth.ts` | Repeated `createClient()` + `getSession()` pattern | ~40 lines per page |
| `hooks/useDocuments.ts` | `documents/page.tsx` useEffect + fetch | ~80 lines |
| `hooks/useChat.ts` | `chat/page.tsx` session + streaming logic | ~150 lines |
| `hooks/useGraph.ts` | `graph/page.tsx` fetch + state | ~100 lines |
| `hooks/useAgents.ts` | `agents/page.tsx` CRUD + polling | ~200 lines |
| `hooks/useDashboard.ts` | `dashboard/page.tsx` polling fetch | ~60 lines |
| `hooks/useMCP.ts` | `mcp/page.tsx` connection management | ~80 lines |
| `hooks/useWebhooks.ts` | `webhooks/page.tsx` CRUD | ~60 lines |
| `hooks/useProject.ts` | Wraps `useProjectStore` with auto-load | ~20 lines |

### Phase 3: Feature Component Extraction (no behavior change)

**Goal:** Extract UI blocks from monolithic pages into focused components.

| New File | Extracted From | Lines |
|----------|---------------|-------|
| `features/dashboard/StatsGrid.tsx` | `dashboard/page.tsx` lines 81-89, 131-140 | ~30 |
| `features/dashboard/PipelineHealth.tsx` | `dashboard/page.tsx` lines 143-174 | ~35 |
| `features/dashboard/FailedDocuments.tsx` | `dashboard/page.tsx` lines 176-194 | ~20 |
| `features/dashboard/RecentActivity.tsx` | `dashboard/page.tsx` lines 216-242 | ~30 |
| `features/chat/ChatWindow.tsx` | `chat/page.tsx` main UI | ~150 |
| `features/chat/ChatMessage.tsx` | `chat/page.tsx` message rendering | ~40 |
| `features/chat/ChatInput.tsx` | `chat/page.tsx` input form | ~30 |
| `features/graph/GraphView.tsx` | `graph/page.tsx` reagraph canvas | ~80 |
| `features/graph/EntityPanel.tsx` | `graph/page.tsx` entity detail sidebar | ~60 |
| `features/graph/GraphControls.tsx` | `graph/page.tsx` search + depth | ~40 |
| `features/agents/AgentList.tsx` | `agents/page.tsx` agent listing | ~100 |
| `features/agents/AgentRunner.tsx` | `agents/page.tsx` run + trace view | ~150 |
| `features/agents/AgentCreator.tsx` | `agents/page.tsx` create form | ~80 |
| `features/documents/DocumentList.tsx` | `documents/page.tsx` table | ~60 |
| `features/documents/DocumentDetail.tsx` | `documents/[id]/page.tsx` | ~80 |

### Phase 4: Layout Group (minor change)

**Goal:** Create `(app)/layout.tsx` authenticated shell to eliminate repeated `DashboardHeader` imports.

| New File | Purpose |
|----------|---------|
| `app/(app)/layout.tsx` | Authenticated shell: header + project switcher + sidebar |

### Phase 5: Component Reorganization (file moves only)

**Goal:** Group existing flat components into `layout/` and `shared/` subdirectories.

| Move From | Move To |
|-----------|---------|
| `components/dashboard-header.tsx` | `components/layout/dashboard-header.tsx` |
| `components/public-header.tsx` | `components/layout/public-header.tsx` |
| `components/project-switcher.tsx` | `components/layout/project-switcher.tsx` |
| `components/ErrorBoundary.tsx` | `components/shared/ErrorBoundary.tsx` |
| `components/StatusPill.tsx` | `components/shared/StatusPill.tsx` |
| `components/status-indicator.tsx` | `components/shared/status-indicator.tsx` |
| `components/UploadDropzone.tsx` | `components/shared/UploadDropzone.tsx` |
| `components/theme-provider.tsx` | `components/shared/theme-provider.tsx` |
| `components/theme-toggle.tsx` | `components/shared/theme-toggle.tsx` |

### Phase 6: Page Simplification

**Goal:** Rewrite each page as a thin composition layer (~50-80 lines).

Each page becomes:
1. Import page-level component
2. Wrap in layout if needed
3. Pass props

Before: `dashboard/page.tsx` = 248 lines
After: `dashboard/page.tsx` ≈ 30 lines + 5 feature components

---

## 5. What NOT to Change

| Area | Reason |
|------|--------|
| Backend structure | Already well-organized (routers → services → pipelines → db) |
| `core/` files | Each file is focused and appropriately sized |
| Backend schemas | Copilot already split these correctly |
| Backend models | Copilot already split these correctly |
| `infra/` | Schema + docker-compose are fine |
| `docs/` | Reference docs, not code |
| `middleware.ts` | Auth middleware is correct |
| `lib/api/client.ts` | Single API client, works well |
| `lib/supabase/` | Client + server setup is correct |
| `stores/project.ts` + `stores/graph.ts` | Already extracted |
| shadcn/ui components | Generated, don't touch |
| Motion components | Small, focused, don't touch |
| Test files | Domain tests are fine, just need a conftest.py |
| `apps/packages/shared-types/` | Empty package, leave for now |

---

## 6. Execution Order

1. **Create `lib/types.ts`** — all shared TypeScript interfaces
2. **Create hooks** — `useAuth`, `useDocuments`, `useChat`, `useGraph`, `useAgents`, `useDashboard`, `useMCP`, `useWebhooks`, `useProject`
3. **Extract feature components** — one feature folder at a time (dashboard → documents → chat → graph → agents → mcp → meetings → webhooks → projects)
4. **Create `(app)/layout.tsx`** — authenticated shell
5. **Move flat components** to `layout/` and `shared/`
6. **Simplify pages** — rewrite as thin composition layers
7. **Update all imports** — fix every `@/components/X` to new paths
8. **Run `npm run typecheck`** — verify no type errors
9. **Run `npm run build`** — verify no build errors

---

## 7. Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking imports | Update all imports atomically per phase. Run typecheck after each. |
| Next.js routing breaks | Use `(app)` route group — does not change URLs. |
| Behavior regression | Each extraction is pure refactor — same JSX, same logic, just moved. |
| Circular imports | hooks → lib/types only. No hook imports another hook. Components import hooks, not vice versa. |

---

## 8. Expected Outcomes

| Metric | Before | After |
|--------|--------|-------|
| Largest page file | 1154 lines (agents) | ~80 lines |
| Avg page file size | ~300 lines | ~50 lines |
| Shared types | 0 (inline everywhere) | 1 central file |
| Custom hooks | 0 | 9 |
| Feature components | 0 | ~25 |
| Import clarity | Flat `@/components/X` | `@/components/features/X/Y` |

---

## 9. Copilot Branch Status

The `copilot/refactor-project-architecture` branch has:
- ✅ Split `db/models.py` → `db/model_defs/` (6 files)
- ✅ Split `schemas/__init__.py` → `schemas/` (8 files)
- ❌ Did NOT refactor frontend
- ❌ Did NOT extract hooks
- ❌ Did NOT create types file
- ❌ Did NOT reorganize components
- ❌ Did NOT simplify pages

**This plan completes what Copilot started.**
