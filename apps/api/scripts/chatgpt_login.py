"""Explicit user-run, loopback-only ChatGPT sign-in for Pi/Unix deployments."""

import argparse
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.chatgpt_oauth import (  # noqa: E402
    AuthorizationAttempt, ChatGPTOAuthError, INITIAL_CLIENT, authorization_url,
    complete_authorization, load_host_id, read_private_json, save_authorized_account,
)
import httpx  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Continue with ChatGPT (explicit local OAuth callback listener)")
    parser.add_argument("--directory", type=Path, default=Path.home() / ".config" / "akgb" / "chatgpt")
    parser.add_argument("--account", default="personal", help="Separate stable registration label; letters, digits, hyphens and underscores")
    parser.add_argument("--port", type=int, default=0, help="Loopback callback port; 0 selects an unused port")
    parser.add_argument("--no-browser", action="store_true", help="Print a sign-in URL without identity-token hints (use SSH loopback forwarding)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.account):
        parser.error("Use a simple account label, not a path.")
    path = args.directory.expanduser() / (args.account + ".json")
    try:
        host_id = load_host_id(path.parent)
        previous = read_private_json(path) if path.exists() else None
        if previous and previous.get("ext_agent_host_id") != host_id:
            raise ChatGPTOAuthError("This account registration belongs to another host.")
        result = {}

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Callback URLs contain authorization codes.

            def do_GET(self):
                if urlsplit(self.path).path != "/auth/callback" or result:
                    self.send_error(404)
                    return
                result["url"] = attempt.redirect_uri + "?" + urlsplit(self.path).query
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.end_headers()
                self.wfile.write(b"Authorization received. Return to the terminal for validation.")

        with HTTPServer(("127.0.0.1", args.port), Callback) as server:
            attempt = AuthorizationAttempt(redirect_uri=f"http://127.0.0.1:{server.server_port}/auth/callback", host_id=host_id,
                                           client_id=previous["client_id"] if previous else INITIAL_CLIENT,
                                           expected_subject=previous["subject"] if previous else None)
            url = authorization_url(attempt, previous=None if args.no_browser else previous)
            if args.no_browser:
                print("Continue with ChatGPT. Open this URL in your own browser:")
                print(url)
                print(f"Callback port: {server.server_port}. For remote sign-in, forward this port to the Pi over SSH.")
            elif not webbrowser.open(url):
                raise ChatGPTOAuthError("System browser could not be opened. Rerun with --no-browser and SSH forwarding.")
            server.timeout = 1
            deadline = time.monotonic() + 300
            while not result and time.monotonic() < deadline:
                server.handle_request()
            if not result:
                raise ChatGPTOAuthError("Sign-in timed out; start a fresh attempt.")

        async def exchange():
            async with httpx.AsyncClient(timeout=30) as client:
                record = await complete_authorization(attempt, result["url"], client)
            await save_authorized_account(path, record)

        asyncio.run(exchange())
        print(f"ChatGPT account validated and saved privately as '{args.account}'.")
        print(f"Credential path: {path}")
        return 0
    except ChatGPTOAuthError as error:
        # These messages are controlled diagnostics, never endpoint response bodies.
        print(str(error), file=sys.stderr)
        return 1
    except OSError:
        print("Sign-in failed. Check private storage and loopback port availability.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
