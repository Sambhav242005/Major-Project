"""Meet package — re-exports for backwards compatibility."""

from .analysis import ANALYSIS_PROMPT, analyze_transcript, run_meeting_bot
from .browser import PLAYWRIGHT_AVAILABLE, _run_blocking, join_and_record
from .errors import GoogleMeetError
from .recording import _record_system_audio
from .transcription import _to_wav, transcribe_audio

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
