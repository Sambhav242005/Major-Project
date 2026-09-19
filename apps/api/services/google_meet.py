"""Shim — re-exports from services.meet for backwards compatibility."""

from services.meet import (
    ANALYSIS_PROMPT,
    PLAYWRIGHT_AVAILABLE,
    GoogleMeetError,
    _run_blocking,
    _to_wav,
    analyze_transcript,
    join_and_record,
    run_meeting_bot,
    transcribe_audio,
)
from services.meet.recording import _record_system_audio

__all__ = [
    "GoogleMeetError",
    "PLAYWRIGHT_AVAILABLE",
    "_run_blocking",
    "join_and_record",
    "_record_system_audio",
    "transcribe_audio",
    "_to_wav",
    "ANALYSIS_PROMPT",
    "analyze_transcript",
    "run_meeting_bot",
]
