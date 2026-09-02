# AGENTS.md — Instructions for AI Coding Agents

> This file governs behavior for any AI agent (Muse, Codex, Cursor, etc.) working in this repository. Human contributors should see `README.md#Contributing` — the workflow is the same, but this file adds agent-specific guardrails.

## 0. Golden Rules

- **NEVER start or stop servers (backend, frontend, or any service).** Tell the user to do it. User manages server lifecycle personally. See `CONTEXT.md` Rules.
- **Do not push directly to `main` unless you are the repo owner (`Sambhav242005`).** `main` is protected: `required_pull_request_reviews=1`, `dismiss_stale_reviews=true`, `enforce_admins=false` — owner (admin) can bypass, everyone else (including agents acting as collaborators) **must** use a feature branch + PR.
- **Prefer editing existing files over creating new ones.** Never create markdown docs unless explicitly requested.

## 1. Repository Map

```
apps/api  — FastAPI (Python 3.11, async SQLAlchemy, ChromaDB, LangGraph)
apps/web  — Next.js 15 (App Router, Tailwind, Zustand, reagraph)
infra     — schema.sql (Postgres/Supabase), docker-compose
docs      — SPEC.md (verified spec), HOW_IT_WORKS.md, TODO.md, RESEARCH_PROBLEM.md, adr/
BUILD_BRIEF.md — locked semester spec (do not edit without approval)
CONTEXT.md     — domain glossary + design system
```

- Single ORM: **SQLAlchemy** (backend). Prisma was removed in `8c72299` + docs-sync `c5f225c` — do not reintroduce. Frontend has no DB.
- Vector store: **ChromaDB** `PersistentClient(path=CHROMA_PATH)` single `knowledge_base` collection, isolation via `where={"project_id": ...}`.
- LLM: OpenAI-compatible (`LLM_BASE_URL`/`LLM_CHAT_MODEL`=`qwen/qwen3.8-27b`/`EMBEDDING_MODEL`=`qwen3-embedding:4b`).

## 2. Branch & PR Workflow (must follow branch protection)

```bash
# 1. Create feature branch from main
git checkout main && git pull origin main
git checkout -b feat/short-description  # or fix/, docs/, chore/

# 2. Make atomic commits
git add <intentional-files>
git commit -m "feat: concise summary"
# Conventional Commits: feat|fix|docs|chore|refactor|test

# 3. Push branch and open PR
git push origin feat/short-description
gh pr create --base main --title "feat: ..." --body "Closes #..."

# 4. Wait for review. If you are NOT the owner, you cannot merge — owner must approve (1 approval required, stale dismiss enabled).

# 5. After merge, delete branch
git branch -d feat/short-description
git push origin --delete feat/short-description
```

**Branch naming:** `feat/`, `fix/`, `docs/`, `chore/`, `refactor/`, `test/` + kebab-case.

**Commit message:** Subject ≤50 chars, imperative mood. Body only if "why" isn't obvious.

## 3. What to Check Before Opening a PR

- [ ] `grep -r "prisma" apps/web/src` → 0 hits (Prisma must stay removed)
- [ ] `BUILD_BRIEF.md` untouched unless explicitly approved (it's locked)
- [ ] Env changes documented in `README.md#Environment Variables Reference` and `apps/api/.env.example` / `apps/web/.env.example`
- [ ] Tests: `cd apps/api && python -m pytest tests/ -q` (or targeted file) — add/adjust tests alongside feature, not after
- [ ] Types: `cd apps/web && npm run typecheck` (when node_modules present)
- [ ] Docs: if you changed behavior, update `docs/SPEC.md` (§8 gaps table) and `docs/TODO.md` atomically — not `BUILD_BRIEF.md`

## 4. Code Style & Safety

- **Python:** follow existing `core/config.py`, `pipelines/`, `services/` patterns. Use `sqlalchemy` async (`select(...)`, `await db.execute`). Background tasks must keep strong `asyncio.Task` refs and open their own `async_session_factory` session.
- **TypeScript:** Next.js App Router + Tailwind + shadcn/ui + Zustand. No new DB client in frontend.
- **Security:** respect `project_members` membership checks (`core/deps.py#get_project_id`), sanitize inputs (`core/security_utils.py`), never expose `SUPABASE_SERVICE_ROLE_KEY` to frontend.
- **CORS/CSP:** update `core/security_headers.py` + `core/config.py#CORS_ORIGINS` together when changing origins.

## 5. Agent-Specific Operating Mode

- **Plan mode:** read-only — delegate explore agents, ask clarifying questions, produce a plan file. Do not edit, run write-shaped shell commands, or change configs.
- **Build mode:** you may edit, run tests, and push branches. Still never start/stop servers.
- **When you finish a change:** run verification greps from `docs/SPEC.md` §8 table + targeted `pytest`; summarize what changed and what remains protected (`main`).
- **If blocked:** state the discrepancy and trust evidence-backed claims over speculation — do not guess env vars or URLs.

## 6. Useful Verification Commands

```bash
# Prisma still gone
grep -ri "prisma" apps/web/src && echo "FAIL" || echo "OK"

# Chunk metadata correct
grep -n "chunk_index" apps/api/pipelines/embeddings.py  # 86,92

# LLM config
grep -n "qwen/qwen3.8" apps/api/core/config.py docs/SPEC.md

# Branch protection status
gh api repos/Sambhav242005/Major-Project/branches/main/protection --jq '{pr: .required_pull_request_reviews.required_approving_review_count, enforce: .enforce_admins.enabled, force: .allow_force_pushes.enabled}'

# TODO sync
head -3 docs/TODO.md | grep -E "f97533e|c5f225c"
```

## 7. References

- `README.md#Contributing` — human-contributor workflow (same PR process)
- `docs/SPEC.md` — authoritative spec vs code
- `docs/TODO.md` — what's left, demo-first priority
- `docs/RESEARCH_PROBLEM.md` — project vs research separation, trust-based hypothesis
- `CONTEXT.md` — domain glossary (use ubiquitous language)
