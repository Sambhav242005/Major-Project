# AI Knowledge Graph Builder

A full-stack web application that transforms documents into a navigable knowledge graph using AI. Upload documents, extract entities and relationships, explore them in an interactive graph, and chat with your knowledge base.

**Semester project** — Built with Next.js, FastAPI, Supabase, and ChromaDB.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), Tailwind CSS, shadcn/ui, Zustand, TanStack Query |
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), Pydantic v2 |
| Auth | Supabase Auth (Google OAuth + email/password) |
| Database | PostgreSQL (Supabase) prod / SQLite (dev forced via `ENVIRONMENT=development`) — SQLAlchemy is the single ORM; no frontend DB |
| Vector Store | ChromaDB (`PersistentClient`, single `knowledge_base` collection, `where={"project_id": ...}` isolation) |
| LLM | OpenAI-compatible (Groq / Ollama) — `LLM_CHAT_MODEL` / `LLM_EXTRACT_MODEL` default `qwen/qwen3.8-27b`, embeddings `qwen3-embedding:4b` |
| Agents | LangGraph |
| MCP | Model Context Protocol (FastMCP) |

---

## Prerequisites

- **Node.js** 18+ and npm
- **Python** 3.11+ and pip (or uv)
- **Supabase** account (free tier works) — [supabase.com](https://supabase.com)
- **OpenAI API key** — [platform.openai.com](https://platform.openai.com) (or run Ollama locally)
- **Git**

---

## Quick Start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd MajorProject

# Frontend
cd apps/web
npm install

# Backend
cd ../api
pip install -r requirements.txt
# or: uv pip install -r requirements.txt
```

### 2. Set up environment variables

```bash
# Backend
cp apps/api/.env.example apps/api/.env
# Edit apps/api/.env with your values

# Frontend
cp apps/web/.env.example apps/web/.env.local
# Edit apps/web/.env.local with your values
```

### 3. Set up Supabase

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **Settings → API** and copy:
   - Project URL
   - `anon` public key
   - `service_role` secret key
3. Go to **Authentication → Providers** and enable **Google** (optional, for OAuth)
4. Run the database schema:
   - Go to **SQL Editor** in Supabase dashboard
   - Paste contents of `infra/schema.sql`
   - Click **Run**

### 4. Start the services

**Option A: Docker (recommended for PostgreSQL)**

```bash
cd infra
docker compose up -d
```

**Option B: Local PostgreSQL**

Ensure PostgreSQL is running on `localhost:5432` with a database named `akgb`.

### 5. Run the apps

```bash
# Terminal 1 — Backend (port 8000)
cd apps/api
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend (port 3000)
cd apps/web
npm run dev
```

### 6. Open

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **API docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Development Modes

### Mock Auth (no Supabase needed)

For quick local development without setting up Supabase:

```bash
# Backend .env
MOCK_AUTH=true

# Frontend .env.local
NEXT_PUBLIC_MOCK_AUTH="true"
```

- Click **"Try Demo (Auto-Login)"** on the sign-in page to skip auth
- No Google OAuth or Supabase project required

### LLM Provider (OpenAI-compatible)

```bash
# Groq example (cloud, OpenAI-compatible)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=gsk-...
LLM_CHAT_MODEL=qwen/qwen3.8-27b
LLM_EXTRACT_MODEL=qwen/qwen3.8-27b
EMBEDDING_BASE_URL=https://api.groq.com/openai/v1
EMBEDDING_MODEL=qwen3-embedding:4b

# Ollama example (local, no API key)
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:4b-instruct
EMBEDDING_BASE_URL=http://localhost:11434/v1
# Ensure Ollama is running: ollama serve
```

---

## Project Structure

```
MajorProject/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── core/               # Config, auth, security, error handling
│   │   ├── db/                 # SQLAlchemy models, session
│   │   ├── pipelines/          # Ingestion, LLM, embeddings, agents
│   │   ├── routers/            # API route handlers
│   │   ├── services/           # Business logic
│   │   ├── tests/              # pytest test suite
│   │   └── main.py             # FastAPI app entry
│   └── web/                    # Next.js frontend
│       ├── src/
│       │   ├── app/            # App Router pages
│       │   ├── components/     # UI components (shadcn/ui + custom)
│   │   ├── lib/            # Supabase client, validators, API client
│       │   ├── stores/         # Zustand stores
│       │   └── middleware.ts   # Auth + security middleware
│       └── e2e/                # Playwright E2E tests
├── infra/
│   ├── schema.sql              # Supabase PostgreSQL schema
│   └── docker-compose.yml      # Local PostgreSQL
├── CHANGELOG.md                # Build log (append-only)
└── BUILD_BRIEF.md              # Project specification
```

---

## Testing

### Backend (pytest)

```bash
cd apps/api
python -m pytest tests/ -v
```

### Frontend (Playwright E2E)

```bash
cd apps/web
npx playwright install chromium   # first time only
npx playwright test
```

### Type checking

```bash
cd apps/web
npx tsc --noEmit
```

---

## Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Import repo in [vercel.com](https://vercel.com)
3. Set environment variables in Vercel dashboard
4. Deploy

### Backend (Railway / Fly.io / Render)

1. Ensure `DATABASE_URL` points to a hosted PostgreSQL (e.g., Supabase, Neon, Railway)
2. Set all environment variables
3. Deploy with: `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## Environment Variables Reference

### Backend (`apps/api/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development` or `production` (dev forces `sqlite+aiosqlite:///./akgb.db`) |
| `SUPABASE_URL` | Yes* | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes* | — | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes* | — | Supabase service role key |
| `SUPABASE_JWKS_URL` | Yes* | — | JWKS endpoint for JWT validation |
| `MOCK_AUTH` | No | `false` | Bypass Supabase auth (dev only, fail-fast in prod) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://…` (prod) | PostgreSQL (prod); dev forced to SQLite `akgb.db` |
| `CHROMA_PATH` | No | `./chroma_data` | ChromaDB storage path |
| `LLM_API_KEY` | No | — | LLM API key (Groq / OpenAI) |
| `LLM_BASE_URL` | No | `http://localhost:11434/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | No | `qwen3:4b-instruct` | Base LLM model |
| `LLM_CHAT_MODEL` | No | `qwen/qwen3.8-27b` | Chat/RAG model |
| `LLM_EXTRACT_MODEL` | No | `qwen/qwen3.8-27b` | Entity extraction model |
| `EMBEDDING_API_KEY` | No | — | Embeddings API key |
| `EMBEDDING_BASE_URL` | No | `http://localhost:11434/v1` | Embeddings base URL |
| `EMBEDDING_MODEL` | No | `qwen3-embedding:4b` | Embeddings model |
| `CORS_ORIGINS` | No | `localhost:3000` | Allowed CORS origins (JSON array) |

\* Required unless `MOCK_AUTH=true`

### Frontend (`apps/web/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes* | — | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes* | — | Supabase anon key |
| `NEXT_PUBLIC_MOCK_AUTH` | No | `false` | Enable demo auto-login |
| `NEXT_PUBLIC_APP_URL` | No | `localhost:3000` | App base URL |

\* Required unless `NEXT_PUBLIC_MOCK_AUTH=true`

---

## License

This is a college semester project. Not licensed for production use.
