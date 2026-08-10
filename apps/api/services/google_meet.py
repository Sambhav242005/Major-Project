"""Google Meet agent — join a meeting, record audio, transcribe, and summarize.

Adapted from https://github.com/dhruvldrp9/Google-Meet-Bot, integrated as a
native agent type. Uses the project's existing LLM client (Groq) instead of
OpenAI, and runs the blocking browser/audio work in a thread executor so the
event loop stays responsive.

Browser automation uses Playwright driving the user's installed Chrome via
CDP (channel="chrome") with a persistent profile — same model as Playwright's
launch_persistent_context. The bot account is logged in ONCE by hand in that
profile; every run reuses the session, so Google never sees automation login.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

# Optional heavy deps — imported lazily so the API boots without them
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("playwright not installed — Google Meet agent will be limited to mock mode")


class GoogleMeetError(Exception):
    """Raised when the Google Meet bot fails."""


def _run_blocking(fn, *args):
    """Run a blocking sync call off the event loop (thread pool)."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, fn, *args)


# --- Join + record (Playwright, like Playwright drives Chrome via CDP) ---

def join_and_record(meet_link: str, duration_seconds: int) -> str:
    """Join the Google Meet with the bot account and record system audio.

    Uses Playwright to drive the user's installed Chrome (channel="chrome")
    with a persistent profile — the same model as Playwright's
    launch_persistent_context. Log into the bot account ONCE in that profile
    (or via MEET_EMAIL/MEET_PASSWORD as a fallback first-run), and every
    subsequent run reuses the session.

    Returns the path to the recorded audio file.
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise GoogleMeetError(
            "playwright is not installed. Run: pip install playwright"
        )

    audio_dir = Path(settings.MEET_AUDIO_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"meeting_{int(time.time())}.wav"

    profile_dir = settings.MEET_CHROME_PROFILE

    with sync_playwright() as p:
        # launch_persistent_context = Playwright's way of driving Chrome with
        # a real profile (cookies, sessions) via CDP. channel="chrome" uses
        # the already-installed Chrome, no browser download.
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir or str(audio_dir / "_profile"),
            channel="chrome",
            headless=False,
            args=[
                "--mute-audio",
                "--use-fake-ui-for-media-stream",
                "--allow-running-insecure-content",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(meet_link, timeout=60000)
            page.wait_for_timeout(5000)

            # If the persistent profile has no session, log in with
            # MEET_EMAIL/MEET_PASSWORD (first run only).
            if "accounts.google.com" in page.url or page.locator("#identifierId").count():
                if not settings.MEET_EMAIL or not settings.MEET_PASSWORD:
                    raise GoogleMeetError(
                        "No bot session in profile. Log into the bot account in "
                        f"{profile_dir or 'the profile'} once, or set MEET_EMAIL + MEET_PASSWORD."
                    )
                _login_with_credentials(page)

            _click_join(page)

            # Recording runs while the page stays open (Meet in background).
            logger.info("Recording %s seconds from %s", duration_seconds, meet_link)
            _record_system_audio(out_path, duration_seconds)
            return str(out_path)
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def _login_with_credentials(page):
    """Fallback login — fills Gmail credentials via Playwright locators."""
    page.goto("https://accounts.google.com/", timeout=60000)
    page.locator("#identifierId").fill(settings.MEET_EMAIL)
    page.locator("#identifierNext").click()
    page.locator('input[name="Passwd"]').fill(settings.MEET_PASSWORD)
    page.locator("#passwordNext").click()
    page.wait_for_timeout(8000)  # let the redirect settle


def _click_join(page):
    """Click the join button — label varies by meet type."""
    selectors = [
        "button[aria-label*='Join now']",
        "button[aria-label*='Ask to join']",
        "button:has-text('Ask to join')",
        "button:has-text('Join now')",
    ]
    for sel in selectors:
        btn = page.locator(sel).first
        if btn.count():
            try:
                btn.click(timeout=3000)
                page.wait_for_timeout(3000)
                return
            except Exception:
                continue
    logger.warning("Could not find a join button — the meeting may have started without us")


def _record_system_audio(out_path: Path, duration_seconds: int):
    """Record system audio via ffmpeg (cross-platform loopback).

    Requires ffmpeg with the correct loopback device for the OS.
    """
    ffmpeg = "ffmpeg"
    if os.name == "nt":  # Windows
        # Try the virtual loopback device first (VB-Cable / virtual-audio-capturer);
        # fall back to the default microphone so a demo still records something.
        cmd = [
            ffmpeg, "-y",
            "-f", "dshow", "-i", "audio=virtual-audio-capturer",
            "-t", str(duration_seconds),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("virtual-audio-capturer not found — falling back to default microphone")
            cmd = [
                ffmpeg, "-y",
                "-f", "dshow", "-i", "audio=Microphone",
                "-t", str(duration_seconds),
                str(out_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GoogleMeetError(
                "Audio recording failed — install VB-Cable (virtual loopback) "
                f"or a microphone. Details: {result.stderr[-300:]}"
            )
    elif os.uname().sysname == "Darwin":  # macOS: blackhole loopback
        cmd = [
            ffmpeg, "-y",
            "-f", "avfoundation", "-i", ":0",
            "-t", str(duration_seconds),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GoogleMeetError(f"Audio recording failed: {result.stderr[-500:]}")
    else:  # Linux: pulse audio loopback
        cmd = [
            ffmpeg, "-y",
            "-f", "pulse", "-i", "default",
            "-t", str(duration_seconds),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GoogleMeetError(f"Audio recording failed: {result.stderr[-500:]}")

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise GoogleMeetError("Audio recording produced an empty file")


# --- Transcription ---

def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio via speech_recognition + Google Web Speech API.

    The file can be any browser-recorded format (webm/opus, mp4/m4a, wav):
    it is converted to PCM WAV via ffmpeg first, since SpeechRecognition can
    only read WAV/AIFF/FLAC natively. Returns the raw transcript text.
    """
    try:
        import speech_recognition as sr
    except ImportError:
        raise GoogleMeetError(
            "speech_recognition not installed. Run: pip install SpeechRecognition pydub"
        )

    wav_path = _to_wav(audio_path)
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio = recognizer.record(source)

        try:
            return recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return ""  # no speech detected
        except sr.RequestError as e:
            raise GoogleMeetError(f"Speech recognition service error: {e}")
    finally:
        # Clean up the converted copy (never touch the original)
        if wav_path != audio_path and Path(wav_path).exists():
            Path(wav_path).unlink(missing_ok=True)


def _to_wav(audio_path: str) -> str:
    """Convert any audio to 16kHz mono PCM WAV via ffmpeg.

    SpeechRecognition/pydub can only read WAV/AIFF/FLAC, so browser-produced
    webm/opus or m4a must be decoded first. If the file is already WAV, it is
    returned unchanged.
    """
    src = Path(audio_path)
    if src.suffix.lower() in {".wav", ".aiff", ".aif", ".flac"}:
        return audio_path

    import shutil
    import subprocess

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise GoogleMeetError(
            "ffmpeg not found on PATH — install ffmpeg to transcode browser "
            "audio (webm/mp4) to WAV."
        )

    out = src.with_name(f"{src.stem}_conv.wav")
    result = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), "-ar", "16000", "-ac", "1", str(out)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not out.exists():
        raise GoogleMeetError(
            f"Audio conversion failed (unsupported format): {result.stderr[-300:]}"
        )
    return str(out)


# --- Analysis (summary / key points / action items / sentiment) ---

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
    """Full pipeline: join -> record -> transcribe -> analyze.

    progress: optional async callable(event_dict) for trace events.
    """
    async def emit(step: str, status: str, **kwargs):
        if progress:
            await progress({
                "step": step,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                **kwargs,
            })

    await emit("initialize", "running", detail="Preparing Google Meet bot")

    # Validate input
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
        "generated_at": datetime.utcnow().isoformat(),
    }
    await emit("complete", "completed", output=result)
    return result
