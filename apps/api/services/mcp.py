"""MCP service — manage MCP connections (sender/receiver) and Google Meet sync."""

import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.oauth import create_oauth_client
from db.models import MCPConnection


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
            "auth_config": c.auth_config or {},
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
        "auth_config": conn.auth_config,
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
        conn.auth_config = auth_config
    if status is not None:
        conn.status = status

    await db.flush()
    return {
        "id": str(conn.id),
        "direction": conn.direction,
        "name": conn.name,
        "endpoint_url": conn.endpoint_url,
        "auth_config": conn.auth_config,
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

    try:
        headers = {}

        # Use OAuth if configured
        oauth_client = create_oauth_client(conn.auth_config or {})
        if oauth_client:
            try:
                token = await oauth_client.get_client_credentials_token()
                headers.update(oauth_client.get_auth_header())
            except Exception as e:
                return {"status": "error", "error": f"OAuth failed: {e}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(conn.endpoint_url, headers=headers)
            if resp.status_code == 200:
                conn.status = "connected"
                await db.flush()
                return {"status": "connected", "status_code": resp.status_code, "oauth": bool(oauth_client)}
            else:
                conn.status = "error"
                await db.flush()
                return {"status": "error", "status_code": resp.status_code}
    except Exception as e:
        conn.status = "error"
        await db.flush()
        return {"status": "error", "error": str(e)}


async def search_knowledge_base(
    db: AsyncSession,
    project_id: str,
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """Search the knowledge base (called by MCP sender tool)."""
    from services.knowledge import search
    return await search(db, query=query, project_id=project_id, top_k=top_k)
