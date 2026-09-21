"""MCP connection CRUD + test + search endpoints."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_project_id
from core.oauth import create_oauth_client
from core.security import User, get_current_user
from db.session import get_db
from services import mcp as mcp_service

from . import router
from .schemas import MCPConnectionCreateRequest, MCPConnectionUpdateRequest, MCPSearchRequest


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
        db=db, project_id=project_id, query=req.query, top_k=req.top_k,
    )
    return {"results": results, "query": req.query}
