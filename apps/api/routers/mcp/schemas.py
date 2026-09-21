"""Pydantic schemas for MCP router."""

from pydantic import BaseModel


class MCPConnectionCreateRequest(BaseModel):
    direction: str  # "sender" | "receiver"
    name: str
    endpoint_url: str | None = None
    auth_config: dict = {}


class MCPConnectionUpdateRequest(BaseModel):
    name: str | None = None
    endpoint_url: str | None = None
    auth_config: dict | None = None
    status: str | None = None


class MCPSearchRequest(BaseModel):
    query: str
    top_k: int = 5
