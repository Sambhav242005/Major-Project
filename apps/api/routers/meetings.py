"""Meetings router — client-side meeting recording analysis.

The browser records the meeting audio locally (getDisplayMedia + MediaRecorder)
and uploads it here. This endpoint transcribes and analyzes it, returning a
summary, key points, action items, and sentiment — no bot account needed.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.config import settings
from core.security import get_current_user, User
from db.session import get_db
from db.models import AuditLog
from services.audit import write_audit_log
from core.deps import _user_uuid

router = APIRouter()

logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 50 * 1024 * 1024  # 50MB


@router.post("/analyze")
async def analyze_meeting_audio(
    file: UploadFile = File(...),
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Transcribe + analyze a client-recorded meeting audio file.

    Accepts webm/wav/mp4 (whatever the browser MediaRecorder produced).
    Returns summary, key points, action items, sentiment, transcript.
    """
    content = await file.read(MAX_AUDIO_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio exceeds 50MB limit")

    # Save to a temp file for the transcription pipeline
    tmp_dir = Path(settings.MEET_AUDIO_DIR)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "meeting.webm").suffix or ".webm"
    audio_path = tmp_dir / f"client_{uuid.uuid4().hex}{suffix}"
    audio_path.write_bytes(content)

    from services.google_meet import transcribe_audio, analyze_transcript, GoogleMeetError

    try:
        # Transcribe (SpeechRecognition handles wav/wav-compressed best)
        transcript = await asyncio.to_thread(transcribe_audio, str(audio_path))
    except GoogleMeetError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=422, detail=f"Transcription failed: {e}")

    try:
        analysis = await analyze_transcript(transcript)
    except GoogleMeetError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Keep the file for re-analysis; return everything to the client
    identifier = uuid.uuid4()
    result = {
        "id": str(identifier),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": file.filename,
        "transcript": transcript[:20000],
        "summary": analysis.get("summary", ""),
        "key_points": analysis.get("key_points", []),
        "action_items": analysis.get("action_items", []),
        "sentiment": analysis.get("sentiment", "neutral"),
        "sentiment_reason": analysis.get("sentiment_reason", ""),
    }
    await write_audit_log(db, project_id, _user_uuid(user.id), "meeting.analyzed", "meeting", identifier, result)
    await db.commit()
    return result


@router.post("/sync")
async def sync_meetings(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Legacy mock sync — kept for API compatibility."""
    return {
        "status": "no_connection",
        "message": "Use the client-side recorder on the Meetings page instead.",
        "meetings_imported": 0,
    }


@router.get("")
async def list_meetings(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
):
    """List persisted analyses belonging to the selected project."""
    rows = await db.execute(select(AuditLog).where(
        AuditLog.project_id == uuid.UUID(project_id),
        AuditLog.action == "meeting.analyzed",
    ).order_by(AuditLog.created_at.desc()).limit(limit))
    return {"meetings": [row.meta for row in rows.scalars().all() if isinstance(row.meta, dict)]}
