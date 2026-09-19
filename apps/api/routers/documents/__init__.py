"""Documents router package."""

from .router import router
from . import ingestion_tasks, validation  # noqa: F401

__all__ = ["router"]
