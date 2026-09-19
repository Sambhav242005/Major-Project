"""Meet transcription — speech-to-text via ffmpeg + speech_recognition."""

import shutil
import subprocess
from pathlib import Path

from .errors import GoogleMeetError


def transcribe_audio(audio_path: str) -> str:
    """Transcribe audio via speech_recognition + Google Web Speech API."""
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
            return ""
        except sr.RequestError as e:
            raise GoogleMeetError(f"Speech recognition service error: {e}")
    finally:
        if wav_path != audio_path and Path(wav_path).exists():
            Path(wav_path).unlink(missing_ok=True)


def _to_wav(audio_path: str) -> str:
    """Convert any audio to 16kHz mono PCM WAV via ffmpeg."""
    src = Path(audio_path)
    if src.suffix.lower() in {".wav", ".aiff", ".aif", ".flac"}:
        return audio_path

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
