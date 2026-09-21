"""Meet analysis — LLM summarization and full bot pipeline."""

import json
import logging
from datetime import datetime, timezone

from .browser import _run_blocking, join_and_record
from .errors import GoogleMeetError
from .transcription import transcribe_audio

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a meeting analyst. Given the transcript of a Google Meet, produce:

1. **Summary** — a concise abstract (2-3 sentences)
2. **Key points** — bullet list of the main points discussed
3. **Action items** — bullet list of who does what next (if mentioned)
4. **Sentiment** — one word: positive, neutral, or negative, plus one line why

Return ONLY valid JSON in this format:
{{
  "summary": "...",
  "key_points": ["...", "..."],
  "action_items": ["...", "..."],
  "sentiment": "positive|neutral|negative",
  "sentiment_reason": "..."
}}

Transcript:
{transcript}"""


async def analyze_transcript(transcript: str) -> dict:
    """Summarize the transcript with the project's LLM client."""
    if not transcript.strip():
        return {
            "summary": "No speech was detected in the recording.",
            "key_points": [],
            "action_items": [],
            "sentiment": "neutral",
            "sentiment_reason": "Empty transcript.",
        }

    from pipelines.llm_client import chat_completion

    prompt = ANALYSIS_PROMPT.format(transcript=transcript[:20000])
    messages = [
        {"role": "system", "content": "You are a meeting analyst. Output only valid JSON."},
        {"role": "user", "content": prompt},
    ]
    try:
        response = await chat_completion(
            messages=messages,
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=1500,
        )
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
        return {"summary": response[:500], "key_points": [], "action_items": [], "sentiment": "neutral"}
    except Exception as e:
        logger.exception("Meeting analysis failed: %s", e)
        return {
            "summary": "Meeting analysis failed: " + str(e),
            "key_points": [],
            "action_items": [],
            "sentiment": "neutral",
        }


async def run_meeting_bot(meet_link: str, duration_seconds: int = 60, progress=None) -> dict:
    """Full pipeline: join -> record -> transcribe -> analyze."""
    async def emit(step: str, status: str, **kwargs):
        if progress:
            await progress({
                "step": step,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **kwargs,
            })

    await emit("initialize", "running", detail="Preparing Google Meet bot")

    if not meet_link or "meet.google.com" not in meet_link:
        raise GoogleMeetError("A valid Google Meet link is required (e.g. https://meet.google.com/xxx-xxxx-xxx)")

    await emit("join", "running", detail=f"Joining {meet_link} for {duration_seconds}s")
    audio_path = await _run_blocking(join_and_record, meet_link, duration_seconds)
    await emit("join", "completed", detail=f"Recording saved to {audio_path}")

    await emit("transcribe", "running", detail="Transcribing audio")
    transcript = await _run_blocking(transcribe_audio, audio_path)
    await emit("transcribe", "completed", detail=f"{len(transcript)} chars transcribed")

    await emit("analyze", "running", detail="Generating summary, key points, action items, sentiment")
    analysis = await analyze_transcript(transcript)
    await emit("analyze", "completed", detail="Analysis complete")

    result = {
        "meeting_url": meet_link,
        "duration_seconds": duration_seconds,
        "recording_path": audio_path,
        "transcript": transcript[:20000],
        "summary": analysis.get("summary", ""),
        "key_points": analysis.get("key_points", []),
        "action_items": analysis.get("action_items", []),
        "sentiment": analysis.get("sentiment", "neutral"),
        "sentiment_reason": analysis.get("sentiment_reason", ""),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    await emit("complete", "completed", output=result)
    return result
