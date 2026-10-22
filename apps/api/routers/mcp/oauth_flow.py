"""MCP OAuth flow endpoints."""

import secrets
import time
import uuid

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.oauth import PKCEChallenge, create_oauth_client
from core.security import User, get_current_user
from db.models import MCPAuthToken
from db.session import get_db
from services import mcp as mcp_service
from core.outbound import validate_public_https_url

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

    auth_config = dict(conn.auth_config or {})
    try:
        for key in ("oauth_token_url", "oauth_authorize_url"):
            if auth_config.get(key):
                await validate_public_https_url(auth_config[key])
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    oauth_client = create_oauth_client(auth_config)
    if not oauth_client:
        raise HTTPException(status_code=400, detail="OAuth not configured for this connection")
    if not oauth_client.authorize_url:
        raise HTTPException(status_code=400, detail="oauth_authorize_url required for PKCE flow")

    state = f"{project_id}:{connection_id}:{secrets.token_urlsafe(32)}"
    auth_url = oauth_client.create_authorization_url(state=state)

    auth_config["_pkce_verifier"] = oauth_client._pkce.code_verifier
    auth_config["_oauth_state"] = state
    auth_config["_oauth_state_expires"] = time.time() + 600
    await mcp_service.update_connection(
        db=db, connection_id=connection_id, project_id=project_id,
        auth_config=auth_config,
    )

    await oauth_client.close()
    return {"authorization_url": auth_url, "state": state}


@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """OAuth 2.0 callback — exchanges code for token and persists to DB."""
    if len(state.split(":")) != 3:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    project_id, connection_id, _ = state.split(":", 2)
    try:
        uuid.UUID(project_id)
        uuid.UUID(connection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    conn = await mcp_service.get_connection(db, connection_id, project_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")

    auth_config = dict(conn.auth_config or {})
    if (not secrets.compare_digest(str(auth_config.get("_oauth_state", "")), state)
            or auth_config.get("_oauth_state_expires", 0) < time.time()):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    auth_config.pop("_oauth_state", None)
    auth_config.pop("_oauth_state_expires", None)
    oauth_client = create_oauth_client(auth_config)
    if not oauth_client:
        raise HTTPException(status_code=400, detail="OAuth not configured")

    pkce_verifier = auth_config.pop("_pkce_verifier", None)
    if pkce_verifier:
        oauth_client._pkce = PKCEChallenge()
        oauth_client._pkce.code_verifier = pkce_verifier

    redirect_uri = auth_config.get("oauth_redirect_uri", "")
    conn.auth_config = auth_config
    await db.flush()
    try:
        token = await oauth_client.exchange_code(code, redirect_uri)
    finally:
        await oauth_client.close()

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
    if not await mcp_service.get_connection(db, connection_id, project_id):
        raise HTTPException(status_code=404, detail="Connection not found")
    stmt = (
        select(MCPAuthToken)
        .where(MCPAuthToken.connection_id == uuid.UUID(connection_id))
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
