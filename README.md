# AI Knowledge Graph Builder

A full-stack web application that transforms documents into a navigable knowledge graph using AI. Upload documents, extract entities and relationships, explore them in an interactive graph, and chat with your knowledge base.

**Semester project** — Built with Next.js, FastAPI, Supabase, and ChromaDB.

The [controlled QA experiment](experiments/controlled_qa/README.md) provides the
research-only verifier, synthetic benchmark, original execution traces and an
offline scoring replay. It documents the negative results and evaluation limits;
it does not enable graph repair or change the production chat route.

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

### Embedding Providers

Embeddings are chosen with `EMBEDDING_PROVIDER`.

Native Ollama support includes `embeddinggemma-2`: set
`EMBEDDING_PROVIDER=ollama`, `OLLAMA_BASE_URL=http://localhost:11434` and
`EMBEDDING_MODEL=embeddinggemma-2:740m`. The adapter calls `/api/embed` in
batches with `truncate=false`, validates one finite vector per input, and
supports optional `EMBEDDING_OUTPUT_DIM` (128/256/512/768 for EmbeddingGemma 2).
This path embeds text, including transcripts and frame descriptions; raw
multimodal embeddings are not assumed. Changing the provider, model or
dimension requires the existing re-embedding procedure below.

Audio/video knowledge ingestion is opt-in. Install ffmpeg/ffprobe and provision
a Whisper-compatible transcription service supporting `verbose_json` segments
and an Ollama vision model separately; this application never starts services
or downloads those models. Set `MEDIA_INGESTION_ENABLED=true`,
`WHISPER_BASE_URL` to the service's API root (for example a local `/v1` root),
`WHISPER_MODEL` to its installed Whisper model ID, and `VLM_MODEL` to the
installed Ollama vision tag. Optional `WHISPER_API_KEY` authenticates the service.
Do not point at a paid provider without configuring it intentionally.

WAV/MP3/FLAC audio and MP4/WebM video (25MB maximum) then use normal document
upload, durable originals, retry and deletion. Whisper segments and sampled
VLM frame descriptions retain their model, timestamps and machine-generated
labels through chunking, retrieval and chat citations. Document detail offers
an authorized playback load button, transcript captions and timestamp seeking.
Apply migration **013** before using this backend on an existing database.
The default limit is 600 seconds, up to 12 sampled frames and a 120-second
processing budget including queue wait; at most two media jobs process at once.
Video without audio uses frames only. Decoder/model failures use the ordinary
failed-document state. Speaker diarization, native multimodal chat and direct
raw-media embedding remain separate work. The Meetings analysis workflow is
unchanged.

```bash
# openai (default) — any OpenAI-compatible /embeddings endpoint
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=http://localhost:11434/v1   # or https://api.groq.com/openai/v1
EMBEDDING_MODEL=qwen3-embedding:4b

# gemini — Google Gemini's native API, no Ollama or GPU needed
EMBEDDING_PROVIDER=gemini
GEMINI_API_KEY=...
EMBEDDING_MODEL=gemini-embedding-001
# optional: truncate stored vectors (Matryoshka) to shrink the index
EMBEDDING_OUTPUT_DIM=768
```

The Gemini provider calls `:batchEmbedContents` (not `:embedContent`, which
aggregates several texts into one vector) and uses asymmetric retrieval task
types: chunks are embedded as `RETRIEVAL_DOCUMENT`, search queries as
`RETRIEVAL_QUERY`. It retries rate limits with backoff, within a 60s total
time budget per call.

**`gemini-embedding-2` note:** Embeddings 2 has no `taskType` field — the API
rejects it. For that model the provider instead prefixes the text
(`task: search result | query: …` for queries, `title: none | text: …` for
chunks), per Google's guidance. Embeddings 1 (`gemini-embedding-001`) sends
`taskType` and passes text through untouched.

#### Switching embedding providers

Vectors from different providers or models are **not comparable**, so the
backend refuses to mix them: the `knowledge_base` collection records which
model produced its vectors and raises a clear error on mismatch instead of
returning irrelevant chunks.

To switch, re-embed the existing knowledge base:

1. Stop the API.
2. Delete the contents of `CHROMA_PATH` (default `./chroma_data`). Postgres
   chunk text is untouched.
3. Start the API and re-upload each document — or call
   `POST /documents/{id}/retry` — so chunks are embedded with the new model.

---

## Project Structure

```
MajorProject/
├── apps/
│   ├── api/                    # FastAPI backend
│   │   ├── core/               # Config, auth, security, error handling
│   │   ├── db/                 # SQLAlchemy models, session
│   │   ├── pipelines/          # Ingestion, extraction, embeddings, agents
│   │   ├── routers/            # API route handlers and feature routers
│   │   ├── services/           # Feature-oriented business logic
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

Two legacy scripts, `test_integration.py` and
`test_integration_quick.py`, require a separately managed local server. The
push/PR workflow in `.github/workflows/ci.yml` excludes those scripts and runs
the other tests from a temporary directory with isolated SQLite/Chroma paths
and mock authentication. This prevents loading the checkout's real `.env` or
modifying its local database. Do not interpret these checks as live provider,
Supabase, or browser end-to-end validation.

CI has separate backend, frontend and offline research jobs. It runs Python
compilation, pytest, ESLint, TypeScript, Vitest, a production Next.js build,
and the frozen research integrity/reproduction checks. JUnit and build
diagnostics are uploaded as workflow artifacts. Production compilation uses
public placeholders with mock authentication disabled; there is no deployment
job. See the workflow for the exact isolated commands.

### Frontend unit tests (Vitest)

```bash
cd apps/web
npm run test          # single run
npm run test:watch    # watch mode
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

The [PR #34 review change map](docs/SPEC.md#81-pr-34-review-changes-by-file)
documents the affected files, reasons for each fix and validation results.
Pending live deployment checks remain tracked in [TODO](docs/TODO.md).

### Raspberry Pi 5 (isolated deployment)

The current Pi release serves HTTPS on **9900**, with the API diagnostic port
**9901 bound to loopback**. PostgreSQL, Chroma and the frontend's internal port
are not published. Personal ChatGPT authorization uses a temporary loopback
callback; it is independent of application login and MCP resource authentication.
Set `LOCAL_AUTH_ALLOW_SIGNUP=true` only when public local registration is wanted.
Local signup stores password hashes and creates isolated accounts; it does not
verify email ownership or provide an email password-reset service. Demo login is
disabled. New uploads retain private originals for retry; earlier uploads may
still need their original file supplied again.

`POST /mcp` implements authenticated stateless Streamable HTTP with three
read-only tools: `search_knowledge_base`, `fetch_document`, and
`get_knowledge_graph`. Send a user Bearer token, the JSON/SSE Accept header and
the selected `project_id`. Browser ChatGPT connector OAuth is not supplied by
the model-provider sign-in. Outbound connection tests perform MCP initialization
and tool discovery; arbitrary external tool execution/import is not implemented.

#### Automatic updates from main

After an initial verified deployment, `infra/pi/watch_main.py` checks GitHub
every three minutes and deploys a changed `main` revision only after its
**Continuous integration** workflow succeeds. It extracts application and
infrastructure files into `.release/releases/<sha>`, validates the AKGB service,
port and storage boundaries, builds tagged images, makes a private database dump,
applies migrations, recreates only AKGB application containers, and checks HTTPS
health and the sign-in page. Failed candidates leave a log and restore previous
application containers; database migrations are **not** automatically reversed.
The smoke check is not proof of every provider-dependent feature.

The optional `infra/pi/updater.compose.yaml` runs this updater without inbound
ports and with restart-after-reboot enabled. It needs the AKGB directory and the
Docker control socket. Its deployment policy limits changes to AKGB, but Docker
socket access is powerful and is not an operating-system security sandbox.
Keep the updater image/configuration private and reviewed. The deployment must
seed `.release/current.json` before starting it. `main_sha` records the last
observed main revision when the initial tested build comes from a feature branch.
Merging reviewed changes into `main` then triggers the normal update path.

```sh
cd /home/pulkit26/akgb/infra/pi
docker compose -f updater.compose.yaml up -d --build
docker compose -f updater.compose.yaml logs --tail 50 -f updater
```

These commands manage the separate `akgb-updater` project. Stop it independently
with `docker compose -f updater.compose.yaml stop` before manually stopping the
application for maintenance. No host Caddy, cron, systemd, router or DNS changes
are required. The gateway supports the configured public hostname and LAN IP;
the operator forwards only TCP 9900. Port 9901 remains loopback-only.

The configuration in `infra/pi/compose.yaml` prepares a separate `akgb` Docker
Compose project: Next.js, one FastAPI worker, PostgreSQL 16 and persistent API
data. Local accounts and application tables live in the dedicated Pi database;
Supabase is optional. The template selects personal ChatGPT-plan OAuth for generation and
CPU MiniLM for embeddings. No MCP server
is required for these model calls. Release gates include ARM64 builds, isolated
tests, actual ingestion/model calls, and a database backup restoration check.

1. Confirm the Pi runs a 64-bit OS and has Docker/Compose, sufficient disk and
   free memory. Put the reviewed application checkout under a dedicated directory
   on `/home`, keeping reports, manuscripts, references, local `.env` files and
   research workspaces out of the deployment transfer. Do not replace existing
   Caddy, tunnel, database or application services.
2. Copy `infra/pi/.env.example` to a private `infra/pi/.env`. Keep
   `AUTH_PROVIDER=local`; generate an independent `LOCAL_AUTH_SECRET` with
   `openssl rand -hex 32`. Local accounts use salted password hashes and signed,
   expiring access tokens; signup is disabled by default. Set
   `LOCAL_AUTH_ALLOW_SIGNUP=true` for the private LAN registration flow. Supabase variables can stay
   empty. Keep `MOCK_AUTH=false` in production.
3. Authorize a fresh AKGB ChatGPT registration using the included OAuth tool.
   This is a personal/self-hosted integration, subject to account eligibility,
   granted permissions and plan limits. Do not expose the owner's inference
   connection through unrestricted public signup. A public/shared service needs
   an appropriate per-user authorization design or a provider API account.
   Application login and ChatGPT inference authorization are separate.
   Never copy Codex login tokens into application configuration.
   Build the API image first with
   `docker build -t akgb-api:staging apps/api` from the repository root. In a
   visible SSH session with `ssh -L 54147:127.0.0.1:54147 pi`, run:

   ```bash
   docker run --rm --network host --mount type=volume,src=akgb_api_data,dst=/data \
     akgb-api:staging python scripts/chatgpt_login.py \
     --directory /data/chatgpt --account credentials --port 54147 --no-browser
   ```

   Open the printed authorization URL in the browser on the computer running
   SSH, sign in yourself, and approve only the intended permissions. The callback
   travels over SSH to a temporary loopback listener on the Pi. Tokens stay in
   the named API volume as UID 10001, with private permissions and serialized
   refresh. Stop if registration, scope, signature or identity validation fails.
   The tool requires Unix private-file storage and does not store credentials
   on Windows. It supports separate records through `--account`; this deployment
   uses only the explicitly selected `credentials.json` account.
   Choose an available model from the authenticated account's `/v1/models`
   catalog for `LLM_CHAT_MODEL` and `LLM_EXTRACT_MODEL`; verify a completed
   Responses request before release. Generation parameters unsupported by the
   plan route are omitted; these are deployment settings, not a rerun of the
   frozen research experiment.
   `EMBEDDING_PROVIDER=local`, `EMBEDDING_MODEL=all-MiniLM-L6-v2` runs on CPU,
   downloads weights on first use and returns 384-dimensional vectors. Long
   chunks are split into MiniLM token windows and pooled, preserving all windows.
   Benchmark its latency and retrieval on the Pi; it is a different embedding
   space from the original research model. Start with a fresh index.
4. Generate the database password with `openssl rand -hex 32`; place it in `.env`
   as `POSTGRES_PASSWORD`. Use a hex password because it is embedded in a database
   URL. Generate another independent `openssl rand -hex 32` value as
   `AUTH_PROXY_SECRET`, separate from `LOCAL_AUTH_SECRET`. Compose passes it only
   to the API and web servers. Caddy overwrites `X-AKGB-Client-IP` with the socket
   IP and strips incoming `X-AKGB-Proxy-Secret`; the web login proxy adds its own
   secret. The API then enforces ten login attempts per minute per LAN client,
   rather than one shared bucket for the web container. Keep the web container
   private behind this gateway; deployments without this trusted hop retain the
   socket-IP limit. Rebuild the web image and have the operator recreate the AKGB
   containers after configuring this new secret; do not alter other services.
   Set `PUBLIC_HOST=wg.pulkitworks.info`,
   `APP_URL=https://wg.pulkitworks.info:9900` and `API_URL=/api`.
   Relative API URLs keep requests on the browser's HTTPS origin. Compose sets
   server-only `AUTH_ALLOWED_ORIGINS` and backend `CORS_ORIGINS` to the public
   origin and `https://${LAN_IP}:${WEB_PORT}`. Only those exact origins can submit
   local login/logout requests; LAN and public addresses have separate cookies.
   Protect the file with `chmod 600 .env`. Never publish `docker compose config`
   output: it expands credentials. Validate using `docker compose config --quiet`.
5. From `infra/pi`, build with `docker compose build`. ARM64 dependency support is
   established only when this succeeds on the Pi. Build with the real public
   URLs: `NEXT_PUBLIC_*` changes require rebuilding the web image. Check free disk
   during the build; Docker's default image storage may be on the smaller root
   filesystem even when the checkout is on `/home`. Do not relocate Docker's
   global storage or prune other projects without separate approval.
6. After approval to start the new AKGB services, run `docker compose up -d postgres`.
   Against this **empty, dedicated** database run
   `docker compose run --rm --no-deps api alembic upgrade head`.
   Use Alembic alone: do not also apply `infra/schema.sql` or stamp that older
   bootstrap schema as current. Check the migration version with
   `docker compose run --rm --no-deps api alembic current`.
7. Start the application with `docker compose up -d api web gateway`. The new
   gateway binds **192.168.1.100:9900** for HTTPS on both configured hostnames.
   The API's diagnostic port
   remains **127.0.0.1:9901**. PostgreSQL and the web container have no published
   ports. Check `docker compose ps` and API `/health`.
   The named API volume must permit UID 10001 to write `/data/chroma` and
   `/data/meet_recordings`; verify actual ownership rather than bypassing the
   non-root runtime. Never run multiple API workers sharing this embedded Chroma
   directory.
   Create an actual account with
   `docker compose exec -it api python scripts/create_local_user.py --email YOUR_EMAIL`.
   The CLI prompts privately for the password and confirmation. No account or
   password is shipped in the repository.
8. The independent gateway uses a local certificate authority. Copy only its
   **public** root certificate with
   `docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./akgb-lan-root.crt`.
   Transfer it over SSH and explicitly trust it on each intended LAN client;
   never export `root.key`. Verify with
   `curl --cacert akgb-lan-root.crt https://192.168.1.100:9900/api/health`.
   Do not use `curl -k` as proof of valid HTTPS. Existing host Caddy, DNS, routing
   and port forwarding remain unchanged and operator-managed.
   For publicly trusted domain HTTPS, obtain a certificate using DNS validation
   (no inbound 80/443 required). Store the full chain and private key in the
   persistent gateway volume at `/data/akgb/public/fullchain.pem` and
   `/data/akgb/public/key.pem`, with the private key readable only by its owner.
   Set `PUBLIC_TLS=/data/akgb/public/fullchain.pem /data/akgb/public/key.pem` in
   the private Pi `.env`; validate Caddy, then recreate only the AKGB gateway.
   The LAN IP retains its private-CA certificate. `PUBLIC_TLS=internal` is the
   explicit fallback and requires client trust; it is not public browser trust.
   Manual DNS issuance requires manual renewal before certificate expiry.
   Keep ACME accounts, certificate keys and backups out of Git. Deployment health
   checks use the verified LAN HTTPS endpoint, independent of router forwarding.
9. Verify real signup/sign-in, default-project creation, document upload and
   processing, graph retrieval, streamed answers with citations, and agent
   execution. Test a second account for isolation. Verify embedding and chat
   calls separately: `/health` proves only HTTP liveness. Check persistence after
   recreating just the AKGB containers. Existing installations using UUID5-derived
   profile IDs require an explicit data migration before this identity fix;
   this procedure targets a new database.
10. Back up the application database using `pg_dump` and the API volume while
    application writes are stopped; preserve the private configuration separately
    with restricted access. Prove restoration before calling the deployment
    complete. To roll back, restore a compatible image/configuration and database
    backup together. Do not use `docker compose down -v`: it deletes AKGB data.

Original uploads are stored privately in `document_originals` beside `CHROMA_PATH`
(for `/data/chroma`, originals live in `/data/document_originals`). Include this
directory in API-volume backups alongside vectors and the database; older uploads
without saved originals still require re-uploading for retry.

The isolated stack does not complete restart-safe background jobs, real MCP
transport, meeting-to-KB ingestion or the research-only
verification policy. Uploaded meeting analysis now honors the configured audio
directory; live transcription still requires a separate integration check.

Moving the database to hosted Supabase later is a separate choice from changing
the login provider. Restore PostgreSQL data into a dedicated compatible schema,
set `DATABASE_URL` to its asyncpg connection and verify schema/access policies.
To adopt Supabase Auth, set `AUTH_PROVIDER=supabase`, configure URL/anon/JWKS,
and rebuild the frontend with the matching public provider. Existing local
accounts do not automatically become Supabase users: explicitly preserve/remap
their profile UUIDs and memberships. Do not auto-link accounts by email or apply
the old bootstrap SQL over the migrated application tables.

References: [Next.js standalone output](https://nextjs.org/docs/15/app/api-reference/config/next-config-js/output),
[Supabase signing keys](https://supabase.com/docs/guides/auth/signing-keys),
[Chroma process constraints](https://cookbook.chromadb.dev/core/system_constraints/),
and [ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source).

### Alternative cloud staging

No cloud deployment exists as of 21 October 2026. The following is a staging
plan. The backend Dockerfile and Railway configuration have been statically
checked, but the image has not been built or run; a passing application CI
run does not validate the container or establish a live release.

### Backend (Railway staging)

1. Review and merge the release PR through the repository's branch workflow.
   Create a Railway service with **Root Directory `/apps/api`** and,
   independently, **Config File `/apps/api/railway.json`**. Its Dockerfile uses
   the API directory as the build context and listens on Railway's `PORT`.
2. Create the actual Supabase staging project. Review `infra/schema.sql`
   against the ORM and migrations before applying schema changes; do not
   blindly apply both full schema and migration history. Record the schema
   version and verify authenticated CRUD against staging. The image does not
   run migrations automatically.
3. Set `ENVIRONMENT=production`, `MOCK_AUTH=false`, an external
   `DATABASE_URL=postgresql+asyncpg://...`, and real Supabase URL/anon/JWKS
   settings. Keep service-role and provider credentials backend-only. Configure
   reachable chat/extraction and embedding endpoints with compatible model
   IDs; container `localhost` is not the developer's Ollama installation.
4. Attach a persistent volume at `/data`, retaining `CHROMA_PATH=/data/chroma`
   and `MEET_AUDIO_DIR=/data/meet_recordings`. **Resolve and test volume write
   access before release:** the image runs as UID/GID 10001, whereas Railway
   volume mounts are root-owned by default. Image-directory ownership does not
   change a mounted volume's ownership. The startup check fails if the runtime
   data paths are not writable. Do not silently switch to root or ephemeral
   vector storage to bypass this gate. Use one replica for this local-Chroma
   topology and verify persistence across a redeploy.
5. Build and smoke-test the image, then deploy staging and record its URL.
   `/health` is HTTP liveness only; separately test database writes, real JWT
   authentication, embedding calls and chat generation. The image includes OCR
   and uploaded-audio dependencies; it does not provide the desktop Chrome and
   host-audio environment required by the headed Google Meet bot. Uploaded
   meeting analysis is also unsupported in this image until its hard-coded
   `/app/meet_recordings` write path is changed to honor `MEET_AUDIO_DIR` and
   tested with the non-root runtime; installing ffmpeg alone does not fix it.

Railway's [monorepo settings](https://docs.railway.com/deployments/monorepo),
[config reference](https://docs.railway.com/config-as-code/reference),
[volumes](https://docs.railway.com/volumes) and
[health checks](https://docs.railway.com/deployments/healthchecks) describe the
provider-side configuration and its limits.

### Frontend (Vercel staging) and release checks

1. Import the reviewed repository branch into Vercel with Root Directory
   `apps/web` and Next.js defaults. Before building, set the real
   `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`,
   `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_APP_URL`, and
   `NEXT_PUBLIC_MOCK_AUTH=false`. Public values are compiled into browser
   bundles; changing them requires a rebuild. Never put backend secrets in
   `NEXT_PUBLIC_*` variables.
2. Configure the backend `CORS_ORIGINS` as a JSON array containing the exact
   frontend HTTPS origin. Configure Supabase's site/redirect allowlist for the
   chosen frontend URL. Record both actual service URLs after deployment.
3. Verify sign-in and project isolation, upload a known document, wait for
   processing, inspect its graph and citations, and execute an agent task.
   Confirm persistence after redeployment and retain smoke-test evidence.
4. Reconcile Jira, replace the proposed deployment diagram with the actual
   topology, and complete peer review and handover. Durable raw-upload storage,
   real MCP transport, OAuth hardening and meeting-to-KB ingestion remain
   separate implementation gaps; hosting does not complete them.

See Vercel's [monorepo setup](https://vercel.com/docs/monorepos) and
[environment-variable guidance](https://vercel.com/docs/environment-variables).

---

## Environment Variables Reference

### Backend (`apps/api/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENVIRONMENT` | No | `development` | `development` or `production` (dev forces `sqlite+aiosqlite:///./akgb.db`) |
| `AUTH_PROVIDER` | No | `supabase` | `local` for administrator-created Pi accounts; `supabase` for managed Auth |
| `LOCAL_AUTH_ALLOW_SIGNUP` | No | `false` | Explicitly enable local registration; keep disabled when administrator-provisioned accounts are required |
| `LOCAL_AUTH_SECRET` | Local auth | — | Independent signing secret of at least 32 random characters; backend only |
| `AUTH_PROXY_SECRET` | Pi stack | — | Separate secret of at least 32 random characters, shared only with the web server to authenticate forwarded login client IPs; optional outside this proxy topology |
| `LOCAL_AUTH_TOKEN_TTL_SECONDS` | No | `3600` | Local-session lifetime; 60–86400 seconds |
| `LLM_PROVIDER` | No | `openai` | Existing compatible API or `chatgpt` personal OAuth Responses route |
| `CHATGPT_CREDENTIALS_PATH` | ChatGPT auth | — | Private Unix credential record; never a Codex credential file |
| `SUPABASE_URL` | Yes* | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes* | — | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes* | — | Supabase service role key |
| `SUPABASE_JWKS_URL` | No | Derived from `SUPABASE_URL` | Optional JWKS endpoint override for JWT validation |
| `MOCK_AUTH` | No | `false` | Bypass Supabase auth (dev only, fail-fast in prod) |
| `DATABASE_URL` | Yes | `postgresql+asyncpg://…` (prod) | PostgreSQL (prod); dev forced to SQLite `akgb.db` |
| `CHROMA_PATH` | No | `./chroma_data` | ChromaDB storage path |
| `LLM_API_KEY` | No | — | LLM API key (Groq / OpenAI) |
| `LLM_BASE_URL` | No | `http://localhost:11434/v1` | OpenAI-compatible base URL |
| `LLM_MODEL` | No | `qwen3:4b-instruct` | Base LLM model |
| `LLM_CHAT_MODEL` | No | `qwen/qwen3.8-27b` | Chat/RAG model |
| `LLM_EXTRACT_MODEL` | No | `qwen/qwen3.8-27b` | Entity extraction model |
| `EMBEDDING_API_KEY` | No | — | Embeddings API key (also fallback for `GEMINI_API_KEY`) |
| `EMBEDDING_BASE_URL` | No | `http://localhost:11434/v1` | Embeddings base URL (OpenAI-compatible provider) |
| `EMBEDDING_MODEL` | No | `qwen3-embedding:4b` | Embeddings model |
| `EMBEDDING_PROVIDER` | No | `openai` | `openai`, `gemini`, `ollama` native embeddings, or explicit `local` CPU MiniLM |
| `EMBEDDING_OUTPUT_DIM` | No | — | Truncated output dimensionality, e.g. `768`; changing it requires re-embedding |
| `EMBEDDING_BATCH_SIZE` | No | `100` | Texts per Gemini `:batchEmbedContents` request |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Native Ollama API root for embeddings and video vision |
| `MEDIA_INGESTION_ENABLED` | No | `false` | Enable audio/video knowledge ingestion after runtimes are configured |
| `WHISPER_BASE_URL` | For media | empty | Whisper-compatible API root; receives `/audio/transcriptions` requests |
| `WHISPER_MODEL` | No | `whisper-1` | Installed Whisper model ID; must support timestamped `verbose_json` segments |
| `WHISPER_API_KEY` | No | empty | Server-only transcription service credential |
| `VLM_MODEL` | For video | empty | Installed Ollama vision model tag |
| `MEDIA_MAX_DURATION_SECONDS` | No | `600` | Maximum accepted source duration, 1–3600 seconds |
| `MEDIA_MAX_FRAMES` | No | `12` | Maximum sampled video frames, 1–60 |
| `MEDIA_PROCESS_TIMEOUT_SECONDS` | No | `120` | Decoder/model processing budget including queue wait, 1–600 seconds |
| `GEMINI_API_KEY` | No | — | Gemini API key (falls back to `EMBEDDING_API_KEY`) |
| `GEMINI_BASE_URL` | No | `https://generativelanguage.googleapis.com/v1beta` | Gemini native API base URL |
| `GITHUB_API_BASE_URL` | No | `https://api.github.com` | GitHub edition: API host; the only accepted value is the bare `https://api.github.com` origin |
| `GITHUB_IMPORT_MAX_TOTAL_BYTES` | No | `52428800` | GitHub edition: total bytes an import may accept across all files (50 MB) |
| `GITHUB_IMPORT_MAX_FILES` | No | `2000` | GitHub edition: maximum files per import |
| `GITHUB_IMPORT_MAX_FILE_BYTES` | No | `2097152` | GitHub edition: maximum bytes for a single file (2 MB) |
| `CORS_ORIGINS` | No | `localhost:3000` | Allowed CORS origins (JSON array) |

\* Required for the Supabase deployment path when `AUTH_PROVIDER=supabase` and `MOCK_AUTH=false`; local accounts do not require a Supabase account.

### Frontend (`apps/web/.env.local`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Yes* | — | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes* | — | Supabase anon key |
| `NEXT_PUBLIC_MOCK_AUTH` | No | `false` | Enable demo auto-login |
| `NEXT_PUBLIC_AUTH_PROVIDER` | No | `supabase` | Build-time choice: `local` administrator-created accounts or `supabase` |
| `API_INTERNAL_URL` | No | `NEXT_PUBLIC_API_URL`, then `http://localhost:8000` | Server-only API address for local login and session verification; Pi uses `http://api:8000` |
| `AUTH_PROXY_SECRET` | Pi stack | — | Server-only counterpart to the API secret; never use a `NEXT_PUBLIC_` prefix or expose the web server outside the trusted gateway |
| `AUTH_ALLOWED_ORIGINS` | No | `NEXT_PUBLIC_APP_URL` | Server-only JSON array of exact origins allowed for local authentication; malformed values fail closed |
| `NEXT_PUBLIC_APP_URL` | No | `localhost:3000` | App base URL |
| `NEXT_PUBLIC_API_URL` | Yes for hosting | `http://localhost:8000` | Browser API base; Pi uses same-origin `/api`; set before building |

\* Required when using Supabase auth with `NEXT_PUBLIC_MOCK_AUTH=false`; not required when `NEXT_PUBLIC_AUTH_PROVIDER=local`.

---

## Contributing

> `main` is protected: `required_pull_request_reviews=1`, `dismiss_stale_reviews=true`, `enforce_admins=false`. Only the owner (`Sambhav242005`, admin) can push directly to `main` — everyone else (including AI agents acting as collaborators) **must** use a feature branch + PR. See `AGENTS.md` for agent-specific guardrails.

### 1. Pick an issue & create a branch

```bash
git checkout main && git pull origin main
git checkout -b feat/short-description   # feat/ | fix/ | docs/ | chore/ | refactor/ | test/
# e.g. feat/graph-depth-slider, fix/chunk-page-number, docs/spec-sync
```

Branch naming: `type/kebab-case`. Keep branches short-lived — one concern per branch.

### 2. Make changes & commit

- Follow **Conventional Commits**: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:` — subject ≤50 chars, imperative mood.
- Keep commits atomic. Do not mix unrelated changes in one commit.
- **Do not edit `BUILD_BRIEF.md`** — it is the locked semester spec. If you think it needs a change, open an issue first.
- Prisma is gone (`8c72299` + `c5f225c`) — do not reintroduce `@prisma/*`, `better-sqlite3`, or `apps/web/prisma`. Frontend has no DB; backend is SQLAlchemy only.
- Document new env vars in **both** `README.md#Environment Variables Reference` and the corresponding `.env.example`.

### 3. Verify before opening a PR

```bash
# No Prisma regression
grep -ri "prisma" apps/web/src && echo "FAIL" || echo "OK"

# Backend tests (add tests alongside your feature)
cd apps/api && python -m pytest tests/ -q
# or targeted: python -m pytest tests/test_chunking.py -v

# Frontend typecheck (when node_modules present)
cd apps/web && npm run typecheck

# Frontend unit tests (pure functions / hooks; E2E stays in test:e2e)
cd apps/web && npm run test

# If you touched retrieval/ingestion, re-check
grep -R -n "chunk_index" apps/api/pipelines/embeddings/
grep -n "qwen/qwen3.8" apps/api/core/config.py docs/SPEC.md
```

If you changed behavior, update `docs/SPEC.md` (§8 gaps table) and `docs/TODO.md` atomically — not `BUILD_BRIEF.md`.

### 4. Push & open a PR

```bash
git push origin feat/short-description
gh pr create --base main --title "feat: concise summary" --body "Closes #<issue>"
```

- Describe **what** and **why**, not just what. Link the issue.
- Keep the PR focused — one feature/fix per PR. Small PRs get reviewed faster.

### 5. Review & merge

- **If you are not the owner:** you cannot merge — the owner must approve (1 approval required, stale reviews are dismissed, conversation must be resolved). Do not use `admin` override.
- **If you are the owner:** you may bypass (admin bypass enabled) but prefer `gh pr merge --squash` via PR anyway for history. Never `push --force` to `main` (`allow_force_pushes=false`).
- After merge, clean up:

```bash
git checkout main && git pull origin main
git branch -d feat/short-description
git push origin --delete feat/short-description
```

### 6. Branch protection in one glance

| Who | Can push directly to `main` | Must use PR | Can merge PR |
|---|---|---|---|
| Owner (`Sambhav242005`) | Yes (admin bypass) | No (but recommended) | Yes (after review if self-opened, instant if just docs) |
| Collaborator / AI agent | No | Yes | No — needs owner approval |

Check protection: `gh api repos/Sambhav242005/Major-Project/branches/main/protection --jq '{pr: .required_pull_request_reviews.required_approving_review_count, enforce: .enforce_admins.enabled}'`

### 7. Questions or stuck?

Open an issue → label `question` / `bug`. For major design changes, check `docs/RESEARCH_PROBLEM.md` (research framing) and `CONTEXT.md` (ubiquitous language) before proposing.

---

## License

This is a college semester project. Not licensed for production use.
