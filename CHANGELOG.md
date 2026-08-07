# Changelog

## Phase 0 — Scaffolding + Hardening (2026-08-07)

### Built
- Repository structure: `/apps/web`, `/apps/api`, `/apps/packages/shared-types`, `/infra`
- FastAPI backend skeleton with all 8 routers (auth, documents, kb, chat, dashboard, agents, mcp, meetings)
- SQLAlchemy models for all 14 tables
- Alembic migration setup with initial schema migration
- Supabase SQL schema file (`infra/schema.sql`) with RLS policies and auto-profile trigger
- Core config (Pydantic Settings), JWT auth dependency, database session management
- Next.js 15 app with App Router, Tailwind CSS, custom design tokens
- Supabase Auth wired end-to-end: sign in, sign up, OAuth callback, sign out, middleware-protected routes
- Dashboard page with upload zone, stat cards, quick links
- Shared-types package for generating TypeScript types from FastAPI OpenAPI schema
- docker-compose.yml for local Postgres

### Architecture (hardening pass)
- `CONTEXT.md` — domain glossary with 16 terms and relationships
- `docs/adr/001-supabase-over-neo4j.md` — graph storage decision
- `docs/adr/002-chromadb-single-collection.md` — vector store strategy
- `docs/adr/003-supabase-auth.md` — auth decision
- `docs/surfaces.md` — locked/editable/append-only/human surfaces
- `apps/api/core/errors.py` — error hierarchy (AppError → NotFound/PermissionDenied/IngestionFailed/etc.)
- `apps/api/schemas/__init__.py` — Pydantic request/response models for all routers
- `apps/api/services/` — domain service layer stubs (documents, knowledge, chat, dashboard, agents)
- `apps/api/tests/test_auth.py` — first TDD tests (4 tests for JWT validation)

### Bug Fixes
- `core/security.py` — JWT now uses RS256 with JWKS key fetch (was HS256 with raw URL string)
- `infra/schema.sql` — MCP connections RLS policy fixed (referenced non-existent `pm` alias)
- `apps/web/src/app/auth/signout/route.ts` — redirect now uses `request.nextUrl.origin` (was pointing to Supabase dashboard)
- `apps/api/requirements.txt` — removed duplicate httpx, added authlib
- Added missing `__init__.py` to core, db, agents, mcp, models, pipelines, tests, schemas, services

### Deliberately Deferred
- Full ingestion pipeline (Phase 1)
- Entity/relation extraction (Phase 2)
- Chat streaming with RAG (Phase 2)
- Dashboard real data queries (Phase 3)
- Knowledge Graph Explorer with React Flow (Phase 3)
- LangGraph agents (Phase 4)
- MCP server/client (Phase 5)

### Self-Improvement Notes
- Failure 1: JWT used HS256 with URL string as key — fixed by fetching JWKS and using RS256
- Failure 2: SQL alias bug in RLS policy — caught during architecture review, fixed inline
- Failure 3: Signout redirected to Supabase URL — fixed with request.nextUrl.origin
- Lesson: Architecture review before implementation catches structural bugs early

## Phase 7 — Mock Auth + Frontend Testing (2026-08-08)

### Built
- Mock auth fallback for development without real Supabase
  - Backend: `MOCK_AUTH=true` config, `routers/auth.py` `/mock-login` endpoint
  - Frontend: Supabase client mock mode, sign-in page mock login button
  - Middleware: mock session cookie support
- Full integration test suite (13/13 passing)
  - Backend health, OpenAPI spec, mock login, auth guard (401)
  - All 9 frontend pages serving (200)

### Bug Fixes
- Sign-in page: added mock login button for dev mode
- Supabase clients: mock mode bypass for server/browser clients
- Frontend .env: `NEXT_PUBLIC_MOCK_AUTH=true` enabled

### Verification Results
- Backend: 13 unit tests passing
- Integration: 13/13 tests passing
- TypeScript: 0 errors
- Frontend: All 9 pages rendering (200)
- Auth flow: Mock login → cookie → dashboard access working

## Phase 7b — Security Test Coverage + Router Sanitization (2026-08-08)

### Built
- `tests/test_security_utils.py` — 42 tests covering sanitize_input, detect_injection, sanitize_for_llm, sanitize_filename, validate_project_id
- `tests/test_oauth.py` — 15 tests covering OAuthToken, MCPOAuthClient (all 3 flows), create_oauth_client

### Router Hardening
- `routers/documents.py` — `sanitize_filename()` applied to upload filename before storage
- `routers/chat.py` — `sanitize_input()` applied to chat messages
- `routers/kb.py` — `sanitize_input()` applied to search queries

### Bug Fixes
- `core/security_utils.py` — `validate_project_id()` now handles None/non-string (was raising TypeError)
- `core/oauth.py` — `create_oauth_client()` now handles None auth_config (was raising AttributeError)
- Integration tests — MOCK_AUTH mode skips JWT-rejection assertions (auth bypassed in dev mode)

### Verification Results
- Backend: 114/114 tests passing (was 47)
- All sanitization + OAuth flows tested

## Phase 7c — Playwright E2E Testing (2026-08-08)

### Built
- `apps/web/playwright.config.ts` — chromium project, headless, 1 worker, baseURL localhost:3000
- `apps/web/e2e/auth.spec.ts` — 5 tests: signin renders, signup renders, mock login → dashboard, protected route redirect, sign out
- `apps/web/e2e/pages.spec.ts` — 7 tests: dashboard, documents, graph, agents, mcp, chat pages + sidebar nav
- `test:e2e` npm script added

### Installed
- `@playwright/test` + chromium browser (via local `.bin\playwright.cmd`)

### Bug Fixes
- `src/lib/supabase/server.ts` — added `signOut()` to mock client (missing → sign out route 500'd)
- E2E helpers — set `mock-session` cookie via `page.context().addCookies()` for cross-test persistence

### Verification Results
- Playwright E2E: 12/12 passing
- Auth flow: mock login → dashboard, sign out → signin, protected route redirect all verified in real browser
- Visual inspection: all 8 pages screenshots reviewed

## Phase 7d — UI Polish + Chat Page (2026-08-08)

### Built
- `src/app/chat/page.tsx` — Chat page with message input, send button, empty state, mock responses

### UI Fixes
- All sub-pages (documents, graph, agents, mcp) now have consistent nav bar with Documents, Chat, Graph, Agents, MCP, Sign out links
- Dashboard nav bar updated to include Agents + MCP links
- Chat page has ← Dashboard back link + Documents, Graph, Sign out nav

### Visual Inspection
- Signin: centered, Fraunces "Welcome back", amber CTA, clean layout
- Dashboard: full nav, "Failed to load dashboard" expected (no DB)
- Documents: upload dropzone, nav bar, "Failed to load documents" expected
- Graph: left sidebar with search/depth slider/legend, React Flow canvas, empty state
- Agents: nav bar, "No agents yet" empty state, Create Agent CTA
- MCP: nav bar, Sender/Receiver tabs, Google Meet Sync section
- Chat: nav bar, empty state message, bottom input bar

### Remaining Demo Notes
- "Failed to load dashboard/documents" — expected without real Supabase/DB connection
- With real Supabase credentials + DB, all pages will show live data

## Phase 7e — Public Pages + Landing (2026-08-08)

### Built
- `src/app/page.tsx` — Full landing page: hero ("Transform Documents Into Navigable Knowledge"), 3-step How It Works, Built With tech stack badges, CTA, header/footer
- `src/app/contact/page.tsx` — Contact form (name/email/message) + project details section
- `src/app/terms/page.tsx` — 7-section Terms of Service (acceptance, service description, accounts, content, acceptable use, liability, changes)
- `src/app/demo/page.tsx` — 7-step interactive demo guide with CTAs linking to each feature (signup → upload → dashboard → graph → chat → agents → MCP)
- `src/middleware.ts` — Updated to allow `/contact`, `/terms`, `/demo` routes without auth

### UI/UX
- All public pages have consistent header with Demo, Contact, Sign in, Sign up (amber CTA)
- All public pages have footer with Terms of Service + Contact links
- Authenticated pages have full nav (Documents, Chat, Graph, Agents, MCP, Sign out)
- Landing page hero uses Fraunces display font with amber accent for "Navigable Knowledge"

### Demo Auto-Login
- `src/app/auth/demo-login/route.ts` — GET + POST handlers; sets `mock-session` cookie and redirects to `/dashboard`
- Landing page "Try the Demo" button submits POST form to `/auth/demo-login`
- Demo page CTAs use GET form action to `/auth/demo-login`
- Sign-in page shows "Try Demo (Auto-Login)" button alongside real auth
- Middleware allows all public routes (`/`, `/demo`, `/contact`, `/terms`) without session cookie

### Verification Results
- Playwright E2E: 12/12 passing
- Backend unit tests: 114/114 passing
- Visual inspection: all 12 pages (8 app + 4 public) reviewed via screenshots
- TypeScript: clean
- Vitest config added (`vitest.config.ts`) to exclude e2e from unit test runner
