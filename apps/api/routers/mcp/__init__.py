"""MCP router package — aggregates sub-routers."""

from fastapi import APIRouter

router = APIRouter()

from . import connections, oauth_flow, schemas  # noqa: F401, E402

__all__ = ["router"]
