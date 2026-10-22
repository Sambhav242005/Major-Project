"""MCP service — manage MCP connections (sender/receiver) and Google Meet sync."""

import asyncio
import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.oauth import create_oauth_client
from core.outbound import validate_public_https_url
from services.mcp_probe import probe_mcp
from db.models import MCPConnection


def public_auth_config(config: dict) -> dict:
    return {key: value for key, value in config.items()
            if not key.startswith("_") and key not in {"oauth_client_secret", "access_token", "refresh_token", "token"}}


async def list_connections(db: AsyncSession, project_id: str) -> list[dict]:
    """List all MCP connections for a project."""
    stmt = (
        select(MCPConnection)
        .where(MCPConnection.project_id == uuid.UUID(project_id))
        .order_by(MCPConnection.name)
    )
    result = await db.execute(stmt)
    conns = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "direction": c.direction,
            "name": c.name,
            "endpoint_url": c.endpoint_url,
            "auth_config": public_auth_config(c.auth_config or {}),
            "status": c.status,
        }
        for c in conns
    ]


async def get_connection(db: AsyncSession, connection_id: str, project_id: str) -> MCPConnection | None:
    """Get a single MCP connection by ID, scoped to project."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == uuid.UUID(connection_id),
        MCPConnection.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_connection(
    db: AsyncSession,
    project_id: str,
    direction: str,
    name: str,
    endpoint_url: str | None = None,
    auth_config: dict = {},
) -> dict:
    """Create a new MCP connection."""
    conn = MCPConnection(
        id=uuid.uuid4(),
        project_id=uuid.UUID(project_id),
        direction=direction,
        name=name,
        endpoint_url=endpoint_url,
        auth_config=auth_config,
        status="disconnected",
    )
    db.add(conn)
    await db.flush()
    return {
        "id": str(conn.id),
        "direction": conn.direction,
        "name": conn.name,
        "endpoint_url": conn.endpoint_url,
        "auth_config": public_auth_config(conn.auth_config or {}),
        "status": conn.status,
    }


async def update_connection(
    db: AsyncSession,
    connection_id: str,
    project_id: str,
    name: str | None = None,
    endpoint_url: str | None = None,
    auth_config: dict | None = None,
    status: str | None = None,
) -> dict | None:
    """Update an MCP connection."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == uuid.UUID(connection_id),
        MCPConnection.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        return None

    if name is not None:
        conn.name = name
    if endpoint_url is not None:
        conn.endpoint_url = endpoint_url
    if auth_config is not None:
        updates = {key: value for key, value in auth_config.items()
                   if key not in {"token", "oauth_client_secret"} or value}
        conn.auth_config = {**(conn.auth_config or {}), **updates}
    if status is not None:
        conn.status = status

    await db.flush()
    return {
        "id": str(conn.id),
        "direction": conn.direction,
        "name": conn.name,
        "endpoint_url": conn.endpoint_url,
        "auth_config": public_auth_config(conn.auth_config or {}),
        "status": conn.status,
    }


async def delete_connection(db: AsyncSession, connection_id: str, project_id: str) -> bool:
    """Delete an MCP connection."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == uuid.UUID(connection_id),
        MCPConnection.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        return False
    await db.delete(conn)
    await db.flush()
    return True


async def test_connection(db: AsyncSession, connection_id: str, project_id: str) -> dict:
    """Test an MCP connection with OAuth if configured."""
    stmt = select(MCPConnection).where(
        MCPConnection.id == uuid.UUID(connection_id),
        MCPConnection.project_id == uuid.UUID(project_id),
    )
    result = await db.execute(stmt)
    conn = result.scalar_one_or_none()
    if not conn:
        return {"error": "Connection not found"}

    if not conn.endpoint_url:
        return {"error": "No endpoint URL configured"}

    oauth_client = None
    try:
        headers = {}
        auth_config = conn.auth_config or {}
        if auth_config.get("token"):
            headers["Authorization"] = f"Bearer {auth_config['token']}"
        for key in ("oauth_token_url", "oauth_authorize_url"):
            if auth_config.get(key):
                await validate_public_https_url(auth_config[key])
        oauth_client = create_oauth_client(auth_config)
        if oauth_client:
            token = await oauth_client.load_token_from_db(db, connection_id)
            if token is None:
                await oauth_client.get_client_credentials_token()
            headers.update(oauth_client.get_auth_header())
        metadata = await asyncio.wait_for(probe_mcp(conn.endpoint_url, headers), timeout=30)
        conn.status = "connected"
        await db.flush()
        return {"status": "connected", "oauth": bool(oauth_client), **metadata}
    except Exception:
        conn.status = "error"
        await db.flush()
        # Provider responses and endpoint query strings can contain credentials.
        return {"status": "error", "error": "MCP handshake failed. Check the public HTTPS endpoint, protocol support, and authorization."}
    finally:
        if oauth_client:
            await oauth_client.close()


async def search_knowledge_base(
    db: AsyncSession,
    project_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search the knowledge base (called by MCP sender tool)."""
    from services.knowledge import search
    return await search(db, query=query, project_id=project_id, top_k=top_k)
