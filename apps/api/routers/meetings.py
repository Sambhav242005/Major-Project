"""Meetings router — client-side meeting recording analysis.

The browser records the meeting audio locally (getDisplayMedia + MediaRecorder)
and uploads it here. This endpoint transcribes and analyzes it, returning a
summary, key points, action items, and sentiment — no bot account needed.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.security import get_current_user, User
from db.session import get_db

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
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=400, detail="Audio exceeds 50MB limit")

    # Save to a temp file for the transcription pipeline
    tmp_dir = Path(__file__).resolve().parent.parent / "meet_recordings"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "meeting.webm").suffix or ".webm"
    audio_path = tmp_dir / f"client_{user.id.replace('-', '')[:8]}_{int(__import__('time').time())}{suffix}"
    audio_path.write_bytes(content)

    from services.google_meet import transcribe_audio, analyze_transcript, GoogleMeetError

    try:
        # Transcribe (SpeechRecognition handles wav/wav-compressed best)
        transcript = transcribe_audio(str(audio_path))
    except GoogleMeetError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=422, detail=f"Transcription failed: {e}")

    analysis = await analyze_transcript(transcript)

    # Keep the file for re-analysis; return everything to the client
    return {
        "filename": file.filename,
        "audio_path": str(audio_path),
        "transcript": transcript[:20000],
        "summary": analysis.get("summary", ""),
        "key_points": analysis.get("key_points", []),
        "action_items": analysis.get("action_items", []),
        "sentiment": analysis.get("sentiment", "neutral"),
        "sentiment_reason": analysis.get("sentiment_reason", ""),
    }


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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List analyzed meetings (in-memory for now)."""
    return {"meetings": []}
