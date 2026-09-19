"""MCP OAuth flow endpoints."""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.oauth import PKCEChallenge, create_oauth_client
from core.security import User, get_current_user
from db.models import MCPAuthToken
from db.session import get_db
from services import mcp as mcp_service

from . import router


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

    pkce_verifier = auth_config.pop("_pkce_verifier", None)
    if pkce_verifier:
        oauth_client._pkce = PKCEChallenge()
        oauth_client._pkce.code_verifier = pkce_verifier

    redirect_uri = auth_config.get("oauth_redirect_uri", "")
    token = await oauth_client.exchange_code(code, redirect_uri)

    await oauth_client.save_token_to_db(db, connection_id)

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
