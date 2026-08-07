from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error. All custom errors inherit from this."""

    status_code: int = 500
    detail: str = "Internal server error"
    error_code: str = "internal_error"

    def __init__(self, detail: str | None = None):
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    error_code = "not_found"


class DocumentNotFoundError(NotFoundError):
    detail = "Document not found"
    error_code = "document_not_found"


class EntityNotFoundError(NotFoundError):
    detail = "Entity not found"
    error_code = "entity_not_found"


class SessionNotFoundError(NotFoundError):
    detail = "Chat session not found"
    error_code = "session_not_found"


class AgentNotFoundError(NotFoundError):
    detail = "Agent not found"
    error_code = "agent_not_found"


class TaskNotFoundError(NotFoundError):
    detail = "Agent task not found"
    error_code = "task_not_found"


class PermissionDeniedError(AppError):
    status_code = 403
    detail = "You do not have permission to perform this action"
    error_code = "permission_denied"


class IngestionFailedError(AppError):
    status_code = 500
    detail = "Document ingestion failed"
    error_code = "ingestion_failed"


class ValidationError(AppError):
    status_code = 422
    detail = "Validation error"
    error_code = "validation_error"


class RateLimitError(AppError):
    status_code = 429
    detail = "Rate limit exceeded"
    error_code = "rate_limit_exceeded"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.detail,
            }
        },
    )
