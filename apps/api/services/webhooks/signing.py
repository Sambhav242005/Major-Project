"""Webhook signing — HMAC and outbound signature helpers."""

import hashlib
import hmac

MAX_RETRIES = 3
RETRY_DELAYS = [60, 300, 1800]  # 1min, 5min, 30min
MAX_PAYLOAD_SIZE = 65536  # 64KB


def _sign_payload(payload: str, secret: str) -> str:
    """Create HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_inbound_signature(
    payload: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 signature for inbound webhook."""
    expected = _sign_payload(payload.decode("utf-8"), secret)
    return hmac.compare_digest(f"sha256={expected}", signature)
