"""MCP router — manage MCP connections, OAuth flows, test connectivity, search KB.

Aligned with MCP 2026-07-28 spec: stateless core, hardened OAuth 2.0 + PKCE.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.deps import get_project_id
from core.security import get_current_user, User
from core.oauth import create_oauth_client
from db.session import get_db
from services import mcp as mcp_service

router = APIRouter()


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


# --- CRUD ---


@router.get("/connections")
async def list_connections(
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all MCP connections."""
    conns = await mcp_service.list_connections(db, project_id)
    return {"connections": conns}


@router.post("/connections")
async def create_connection(
    req: MCPConnectionCreateRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new MCP connection."""
    if req.direction not in ("sender", "receiver"):
        raise HTTPException(status_code=400, detail="direction must be 'sender' or 'receiver'")

    conn = await mcp_service.create_connection(
        db=db, project_id=project_id,
        direction=req.direction, name=req.name,
        endpoint_url=req.endpoint_url, auth_config=req.auth_config,
    )
    return {"connection": conn}


@router.patch("/connections/{connection_id}")
async def update_connection(
    connection_id: str,
    req: MCPConnectionUpdateRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an MCP connection."""
    conn = await mcp_service.update_connection(
        db=db, connection_id=connection_id, project_id=project_id,
        name=req.name, endpoint_url=req.endpoint_url,
        auth_config=req.auth_config, status=req.status,
    )
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"connection": conn}


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an MCP connection."""
    deleted = await mcp_service.delete_connection(db, connection_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"deleted": True}


# --- OAuth 2.0 + PKCE (MCP 2026-07-28) ---


@router.get("/connections/{connection_id}/authorize")
async def authorize_connection(
    connection_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start OAuth 2.0 + PKCE flow — returns the authorization URL to redirect the user to."""
    conn = await mcp_service.get_connection(db, connection_id, project_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    auth_config = conn.auth_config or {}
    oauth_client = create_oauth_client(auth_config)
    if not oauth_client:
        raise HTTPException(status_code=400, detail="OAuth not configured for this connection")
    if not oauth_client.authorize_url:
        raise HTTPException(status_code=400, detail="oauth_authorize_url required for PKCE flow")

    state = f"{project_id}:{connection_id}"
    auth_url = oauth_client.create_authorization_url(state=state)

    # Store PKCE verifier in auth_config temporarily
    auth_config["_pkce_verifier"] = oauth_client._pkce.code_verifier
    await mcp_service.update_connection(
        db=db, connection_id=connection_id, project_id=project_id,
        auth_config=auth_config,
    )

    return {"authorization_url": auth_url, "state": state}


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """OAuth 2.0 callback — exchanges code for token and persists to DB."""
    if ":" not in state:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    project_id, connection_id = state.split(":", 1)

    conn = await mcp_service.get_connection(db, connection_id, project_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    auth_config = conn.auth_config or {}
    oauth_client = create_oauth_client(auth_config)
    if not oauth_client:
        raise HTTPException(status_code=400, detail="OAuth not configured")

    # Restore PKCE verifier
    pkce_verifier = auth_config.pop("_pkce_verifier", None)
    if pkce_verifier:
        from core.oauth import PKCEChallenge
        oauth_client._pkce = PKCEChallenge()
        oauth_client._pkce.code_verifier = pkce_verifier

    redirect_uri = auth_config.get("oauth_redirect_uri", "")
    token = await oauth_client.exchange_code(code, redirect_uri)

    # Persist token to DB
    await oauth_client.save_token_to_db(db, connection_id)

    # Update connection status
    await mcp_service.update_connection(
        db=db, connection_id=connection_id, project_id=project_id,
        status="connected",
    )

    return {"status": "connected", "expires_at": token.expires_at}


@router.get("/connections/{connection_id}/token")
async def get_token_status(
    connection_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if a valid token exists for this connection."""
    from db.models import MCPAuthToken
    from sqlalchemy import select

    stmt = (
        select(MCPAuthToken)
        .where(MCPAuthToken.connection_id == connection_id)
        .order_by(MCPAuthToken.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()

    if not row:
        return {"has_token": False}

    from datetime import datetime, timezone
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    return {
        "has_token": True,
        "expired": expires_at < now,
        "expires_at": expires_at.isoformat(),
        "scope": row.scope,
    }


# --- Test + Search ---


@router.post("/connections/{connection_id}/test")
async def test_connection(
    connection_id: str,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test an MCP connection — uses persisted token if available."""
    conn = await mcp_service.get_connection(db, connection_id, project_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Try loading persisted token first
    auth_config = conn.auth_config or {}
    oauth_client = create_oauth_client(auth_config)
    if oauth_client:
        await oauth_client.load_token_from_db(db, connection_id)

    result = await mcp_service.test_connection(db, connection_id, project_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/search")
async def mcp_search(
    req: MCPSearchRequest,
    project_id: str = Depends(get_project_id),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search knowledge base via MCP tool interface."""
    results = await mcp_service.search_knowledge_base(
        db=db, project_id=project_id,
        query=req.query, top_k=req.top_k,
    )
    return {"results": results, "query": req.query}
