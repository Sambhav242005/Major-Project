"""Meet recording — system audio capture via ffmpeg."""

import logging
import os
import subprocess
from pathlib import Path

from .errors import GoogleMeetError

logger = logging.getLogger(__name__)


def _record_system_audio(out_path: Path, duration_seconds: int):
    """Record system audio via ffmpeg (cross-platform loopback)."""
    ffmpeg = "ffmpeg"
    if os.name == "nt":
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
    elif os.uname().sysname == "Darwin":
        cmd = [
            ffmpeg, "-y",
            "-f", "avfoundation", "-i", ":0",
            "-t", str(duration_seconds),
            str(out_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise GoogleMeetError(f"Audio recording failed: {result.stderr[-500:]}")
    else:
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
