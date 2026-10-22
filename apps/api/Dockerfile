# Build from the apps/api directory. Supply provider credentials at runtime.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/data \
    PIP_NO_CACHE_DIR=1 \
    ENVIRONMENT=production \
    MOCK_AUTH=false \
    CHROMA_PATH=/data/chroma \
    MEET_AUDIO_DIR=/data/meet_recordings

WORKDIR /app

# OCR and uploaded-audio transcription use these existing application tools.
# The headed Google Meet bot additionally needs Chrome and host audio; this
# image does not provide or claim support for that desktop workflow.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr ffmpeg libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
# SQLite's driver is imported by the existing modules/tests; the English model
# is loaded at import time by pipelines/extraction/ner.py. Both are recorded in
# the existing research runtime, rather than introducing a new application API.
RUN python -m pip install --no-cache-dir -r requirements.txt \
    aiosqlite==0.22.1 \
    https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# SpeechRecognition needs the system FLAC encoder on ARM (its bundled encoder
# targets other architectures). Keep this separate from the Python dependency
# layer so the deployment fix does not reinstall the model/runtime packages.
RUN apt-get update \
    && apt-get install -y --no-install-recommends flac \
    && rm -rf /var/lib/apt/lists/*

# Explicit source allowlist keeps tests, experiments, .env and local state out
# of the image even if the build context later gains additional files.
COPY app ./app
COPY core ./core
COPY db ./db
COPY pipelines ./pipelines
COPY routers ./routers
COPY schemas ./schemas
COPY services ./services
COPY migrations ./migrations
COPY scripts/chatgpt_login.py ./scripts/chatgpt_login.py
COPY scripts/create_local_user.py ./scripts/create_local_user.py
COPY main.py alembic.ini ./

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --home-dir /data app \
    && mkdir -p /data/chroma /data/meet_recordings \
    && chown -R 10001:10001 /data

# A mounted volume must separately grant UID 10001 write permission; a mount
# hides the image's /data ownership. See the deployment runbook before hosting.
USER 10001:10001

EXPOSE 8000

# Liveness only: /health does not test database, LLM or embedding readiness.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=4).read()" || exit 1

# Do not silently host an ephemeral SQLite database in production. PostgreSQL
# migrations are an operator-reviewed step, never run automatically here.
CMD ["sh", "-c", ": \"${DATABASE_URL:?Set DATABASE_URL to a postgresql+asyncpg URL}\"; case \"$DATABASE_URL\" in postgresql+asyncpg://*) ;; *) echo 'DATABASE_URL must use postgresql+asyncpg' >&2; exit 1 ;; esac; if [ \"${AUTH_PROVIDER:-supabase}\" = supabase ]; then : \"${SUPABASE_URL:?Set the real Supabase project URL}\"; : \"${SUPABASE_ANON_KEY:?Set the real Supabase anon key}\"; fi; mkdir -p \"$CHROMA_PATH\" \"$MEET_AUDIO_DIR\" && test -w \"$CHROMA_PATH\" && test -w \"$MEET_AUDIO_DIR\" || { echo 'Runtime data directories must be writable by UID 10001' >&2; exit 1; }; exec uvicorn main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
