"""Meet browser — Playwright join and login helpers."""

import asyncio
import logging
import time
from pathlib import Path

from core.config import settings

from .errors import GoogleMeetError

logger = logging.getLogger(__name__)

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.sync_api import TimeoutError as PWTimeoutError
    from playwright.sync_api import sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("playwright not installed — Google Meet agent will be limited to mock mode")


def _run_blocking(fn, *args):
    """Run a blocking sync call off the event loop (thread pool)."""
    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, fn, *args)


def join_and_record(meet_link: str, duration_seconds: int) -> str:
    """Join the Google Meet with the bot account and record system audio."""
    if not PLAYWRIGHT_AVAILABLE:
        raise GoogleMeetError(
            "playwright is not installed. Run: pip install playwright"
        )

    from .recording import _record_system_audio

    audio_dir = Path(settings.MEET_AUDIO_DIR)
    audio_dir.mkdir(parents=True, exist_ok=True)
    out_path = audio_dir / f"meeting_{int(time.time())}.wav"

    profile_dir = settings.MEET_CHROME_PROFILE

    with sync_playwright() as p:
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

            if "accounts.google.com" in page.url or page.locator("#identifierId").count():
                if not settings.MEET_EMAIL or not settings.MEET_PASSWORD:
                    raise GoogleMeetError(
                        "No bot session in profile. Log into the bot account in "
                        f"{profile_dir or 'the profile'} once, or set MEET_EMAIL + MEET_PASSWORD."
                    )
                _login_with_credentials(page)

            _click_join(page)

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
    page.wait_for_timeout(8000)


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
