"""Provider status, protocol checks and project isolation release regressions."""
import json
import socket
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_status_reports_actual_provider_without_claiming_connectivity(monkeypatch):
    from routers.system import system_status, settings
    monkeypatch.setattr(settings, "MOCK_AUTH", False)
    monkeypatch.setattr(settings, "AUTH_PROVIDER", "local")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "chatgpt")
    monkeypatch.setattr(settings, "CHATGPT_CREDENTIALS_PATH", "")
    result = await system_status()
    assert result["auth_mode"] == "local"
    assert result["llm"]["provider"] == "chatgpt"
    assert result["llm"]["configured"] is False
    assert result["llm"]["connectivity"] == "not_checked"
    assert result["capabilities"]["meetings_sync"] is False
    # The chat model selector derives unavailable-provider reasons from this.
    assert result["capabilities"]["chatgpt"] is False


@pytest.mark.asyncio
async def test_status_reports_server_connected_chatgpt(monkeypatch):
    from routers.system import system_status, settings
    monkeypatch.setattr(settings, "CHATGPT_CREDENTIALS_PATH", "protected/credentials.json")
    result = await system_status()
    assert result["capabilities"]["chatgpt"] is True


@pytest.mark.asyncio
async def test_mcp_checks_protocol_and_tools_instead_of_http200(monkeypatch):
    from services import mcp_probe
    original_client = httpx.AsyncClient
    methods = []
    def handler(request):
        body = json.loads(request.content)
        methods.append(body["method"])
        if body["method"] == "initialize":
            return httpx.Response(200, headers={"mcp-session-id": "session1"}, json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}}})
        assert request.headers["Mcp-Session-Id"] == "session1"
        assert request.headers["MCP-Protocol-Version"] == "2025-06-18"
        if body["method"] == "notifications/initialized":
            return httpx.Response(202)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 2, "result": {"tools": [{"name": "search"}]}})
    def transport_handler(request):
        if request.method == "DELETE":
            return httpx.Response(200)
        return handler(request)
    monkeypatch.setattr(mcp_probe, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(mcp_probe.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(transport_handler), **kwargs))
    result = await mcp_probe.probe_mcp("https://example.com/mcp", {})
    assert result == {"protocol_version": "2025-06-18", "tool_count": 1}
    assert methods == ["initialize", "notifications/initialized", "tools/list"]


@pytest.mark.asyncio
async def test_mcp_rejects_plain_web_page(monkeypatch):
    from services import mcp_probe
    original_client = httpx.AsyncClient
    monkeypatch.setattr(mcp_probe, "validate_public_https_url", AsyncMock())
    monkeypatch.setattr(mcp_probe.httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text="hello website")), **kwargs))
    with pytest.raises(ValueError):
        await mcp_probe.probe_mcp("https://example.com", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("address", ["127.0.0.1", "192.168.1.100", "169.254.169.254", "::1"])
async def test_outbound_urls_reject_private_and_metadata_hosts(monkeypatch, address):
    from core import outbound
    monkeypatch.setattr(outbound.socket, "getaddrinfo", lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (address, 443))])
    with pytest.raises(ValueError, match="public IP"):
        await outbound.validate_public_https_url("https://untrusted.example/mcp")


def test_mcp_responses_hide_credentials():
    from services.mcp import public_auth_config
    assert public_auth_config({"oauth_client_id": "public", "oauth_client_secret": "secret", "token": "bearer", "_pkce_verifier": "private"}) == {"oauth_client_id": "public"}


@pytest.mark.asyncio
async def test_agent_stream_rejects_task_from_other_project(monkeypatch):
    from routers.agents import execution
    monkeypatch.setattr(execution.agent_service, "get_task", AsyncMock(return_value=None))
    subscribe = MagicMock()
    monkeypatch.setattr(execution, "subscribe_task", subscribe)
    with pytest.raises(HTTPException) as exc:
        await execution.stream_agent_task("agent", "task", "project", MagicMock(), MagicMock())
    assert exc.value.status_code == 404
    subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_webhook_toggle_cannot_update_other_project():
    from routers.webhooks import update_subscription, SubscriptionUpdate
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock(execute=AsyncMock(return_value=result))
    with pytest.raises(HTTPException) as exc:
        await update_subscription(uuid.uuid4(), SubscriptionUpdate(active=False), str(uuid.uuid4()), db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_memory_sharing_rejects_nonmembers_and_viewer_writes():
    from routers.sharing import require_project_member
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db = MagicMock(execute=AsyncMock(return_value=result))
    user = MagicMock(id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        await require_project_member(db, str(uuid.uuid4()), user)
    assert exc.value.status_code == 404
    result.scalar_one_or_none.return_value = MagicMock(role="viewer")
    with pytest.raises(HTTPException) as exc:
        await require_project_member(db, str(uuid.uuid4()), user, write=True)
    assert exc.value.status_code == 403


def test_headless_deployment_does_not_offer_desktop_meeting_bot(monkeypatch):
    from services.agents import crud
    monkeypatch.setattr(crud, "os", SimpleNamespace(name="posix", environ={}))
    assert "google_meet" not in {item["type"] for item in crud.list_agent_types()}
    assert "qa" in {item["type"] for item in crud.list_agent_types()}
