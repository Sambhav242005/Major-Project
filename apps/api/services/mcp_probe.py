"""A bounded MCP initialize/tool-discovery check, not arbitrary tool execution."""
import json

import httpx

from core.outbound import validate_public_https_url


async def _rpc(client, endpoint, headers, identifier, method, params):
    async with client.stream("POST", endpoint, headers=headers, json={
        "jsonrpc": "2.0", "id": identifier, "method": method, "params": params,
    }) as response:
        response.raise_for_status()
        session = response.headers.get("mcp-session-id")
        chunks = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > 1024 * 1024:
                raise ValueError("MCP response exceeded 1 MB")
            chunks.append(chunk)
            raw = b"".join(chunks).decode("utf-8", errors="ignore")
            if response.headers.get("content-type", "").startswith("text/event-stream"):
                for event in raw.replace("\r\n", "\n").split("\n\n")[:-1]:
                    data = "\n".join(line[5:].strip() for line in event.splitlines() if line.startswith("data:"))
                    if not data:
                        continue
                    message = json.loads(data)
                    if message.get("id") == identifier:
                        if "error" in message:
                            raise ValueError("MCP server rejected the request")
                        return message["result"], session
        if not response.headers.get("content-type", "").startswith("text/event-stream"):
            message = json.loads(b"".join(chunks))
            if message.get("jsonrpc") != "2.0" or message.get("id") != identifier or "result" not in message:
                raise ValueError("Endpoint did not return a valid MCP JSON-RPC response")
            return message["result"], session
        raise ValueError("MCP stream ended without a matching response")


async def probe_mcp(endpoint: str, authorization: dict[str, str]) -> dict:
    await validate_public_https_url(endpoint)
    headers = {"Accept": "application/json, text/event-stream", **authorization}
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as client:
        initialized, session = await _rpc(client, endpoint, headers, 1, "initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "akgb-connection-check", "version": "1.0"},
        })
        if not isinstance(initialized, dict) or initialized.get("protocolVersion") != "2025-06-18":
            raise ValueError("MCP server did not negotiate supported protocol 2025-06-18")
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        if session:
            headers["Mcp-Session-Id"] = session
        response = await client.post(endpoint, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        response.raise_for_status()
        tool_count = None
        if "tools" in initialized.get("capabilities", {}):
            tools, _ = await _rpc(client, endpoint, headers, 2, "tools/list", {})
            if not isinstance(tools, dict) or not isinstance(tools.get("tools"), list):
                raise ValueError("MCP server returned an invalid tool list")
            tool_count = len(tools["tools"])
        if session:
            try:
                await client.delete(endpoint, headers=headers)
            except httpx.HTTPError:
                pass
        return {"protocol_version": initialized["protocolVersion"], "tool_count": tool_count}
