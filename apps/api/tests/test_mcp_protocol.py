"""Read-only MCP wire contract, errors and project-scoped tool dispatch."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.config import settings
from core.deps import get_project_id
from db.session import get_db
from routers.mcp import router
from routers.mcp import protocol as module

PROJECT = str(uuid.uuid4())
HEADERS = {"Authorization": "Bearer test", "Accept": "application/json, text/event-stream"}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix="/mcp")
    app.dependency_overrides[get_project_id] = lambda: PROJECT
    db = AsyncMock()
    async def database():
        yield db
    app.dependency_overrides[get_db] = database
    with TestClient(app) as value:
        yield value


def call(client, method, params=None):
    return client.post("/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})


def test_initialize_and_tools(client):
    data = call(client, "initialize", {"protocolVersion": "2025-06-18"}).json()
    assert data["result"]["protocolVersion"] == "2025-06-18"
    tools = call(client, "tools/list").json()["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"search_knowledge_base", "fetch_document", "get_knowledge_graph"}
    assert all(tool["annotations"]["readOnlyHint"] for tool in tools)


def test_auth_origin_accept_and_version(client, monkeypatch):
    assert client.post("/mcp", json={}).status_code == 401
    assert client.post("/mcp", headers={"Authorization": "Bearer x"}, json={}).status_code == 406
    assert client.post("/mcp", headers={**HEADERS, "Origin": "https://attacker.invalid"}, json={}).status_code == 403
    assert client.post("/mcp", headers={**HEADERS, "MCP-Protocol-Version": "invalid"}, json={}).status_code == 400
    assert client.get("/mcp").status_code == 405


def test_notifications_errors_and_size(client):
    assert client.post("/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    assert call(client, "unsupported").json()["error"]["code"] == -32601
    assert call(client, "tools/call", {"name": "unknown"}).json()["error"]["code"] == -32602
    assert call(client, "tools/call", {"name": "search_knowledge_base", "arguments": {"query": "x", "top_k": 999}}).json()["error"]["code"] == -32602
    assert client.post("/mcp", headers=HEADERS, json=[]).json()["error"]["code"] == -32600
    assert client.post("/mcp", headers={**HEADERS, "Content-Type": "application/json"}, content=b"x" * 65537).status_code == 413


def test_search_is_project_scoped(client, monkeypatch):
    search = AsyncMock(return_value=[{"text": "verified evidence"}])
    monkeypatch.setattr(module.knowledge, "search", search)
    result = call(client, "tools/call", {"name": "search_knowledge_base", "arguments": {"query": "question", "top_k": 3}}).json()
    assert result["result"]["isError"] is False
    assert search.await_args.args[1:] == ("question", PROJECT, 3)


def test_missing_document_and_invalid_uuid(client):
    result = call(client, "tools/call", {"name": "fetch_document", "arguments": {"document_id": "invalid"}}).json()
    assert result["error"]["code"] == -32602
