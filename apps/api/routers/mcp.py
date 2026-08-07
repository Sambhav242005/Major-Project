"""MCP router — manage MCP connections, test connectivity, search KB tool."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
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


@router.get("/connections")
async def list_connections(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all MCP connections."""
    project_id = "00000000-0000-0000-0000-000000000001"
    conns = await mcp_service.list_connections(db, project_id)
    return {"connections": conns}


@router.post("/connections")
async def create_connection(
    req: MCPConnectionCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new MCP connection."""
    project_id = "00000000-0000-0000-0000-000000000001"

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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an MCP connection."""
    project_id = "00000000-0000-0000-0000-000000000001"
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
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an MCP connection."""
    project_id = "00000000-0000-0000-0000-000000000001"
    deleted = await mcp_service.delete_connection(db, connection_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"deleted": True}


@router.post("/connections/{connection_id}/test")
async def test_connection(
    connection_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test an MCP connection."""
    project_id = "00000000-0000-0000-0000-000000000001"
    result = await mcp_service.test_connection(db, connection_id, project_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/search")
async def mcp_search(
    req: MCPSearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search knowledge base via MCP tool interface."""
    project_id = "00000000-0000-0000-0000-000000000001"
    results = await mcp_service.search_knowledge_base(
        db=db, project_id=project_id,
        query=req.query, top_k=req.top_k,
    )
    return {"results": results, "query": req.query}
