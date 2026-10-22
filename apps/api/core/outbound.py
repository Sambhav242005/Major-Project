"""Validate user-configured outbound endpoints before making requests."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlsplit


async def validate_public_https_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Endpoint must be an HTTPS URL without credentials or a fragment")
    addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(address[4][0]).is_global for address in addresses):
        raise ValueError("Endpoint must resolve exclusively to public IP addresses")
