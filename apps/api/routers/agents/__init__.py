"""Agents router package — aggregates sub-routers and re-exports."""

from fastapi import APIRouter

router = APIRouter()

# Import submodules for side-effect route registration
from . import crud, execution, memory, schemas  # noqa: F401, E402

__all__ = ["router"]
