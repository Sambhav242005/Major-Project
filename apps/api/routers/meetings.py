"""Meetings router — Google Meet sync and listing."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from core.security import get_current_user, User
from db.session import get_db
from services import mcp as mcp_service

router = APIRouter()


class MeetingSyncRequest(BaseModel):
    source: str = "google_meet"
    credentials: dict = {}


@router.post("/sync")
async def sync_meetings(
    req: MeetingSyncRequest = MeetingSyncRequest(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync meetings from Google Meet via MCP receiver.

    This is a mock implementation — in production, this would:
    1. Use Google Meet API via MCP receiver connection
    2. Pull meeting transcripts
    3. Ingest them as documents
    """
    project_id = "00000000-0000-0000-0000-000000000001"

    # Mock: check if there's a Google Meet MCP connection
    conns = await mcp_service.list_connections(db, project_id)
    meet_connections = [c for c in conns if c["direction"] == "receiver" and "meet" in c["name"].lower()]

    if not meet_connections:
        return {
            "status": "no_connection",
            "message": "No Google Meet MCP receiver configured. Add a receiver connection first.",
            "meetings_imported": 0,
        }

    # Mock sync — in production would call Google Meet API
    return {
        "status": "synced",
        "message": "Google Meet sync is mocked for demo. Configure a real MCP receiver to pull actual transcripts.",
        "meetings_imported": 0,
        "connection_used": meet_connections[0]["name"],
    }


@router.get("")
async def list_meetings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List synced meetings."""
    # In production, this would query a meetings table
    return {"meetings": []}
