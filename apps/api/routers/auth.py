from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from core.security import get_current_user, User
from core.config import settings

router = APIRouter()


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


@router.post("/mock-login")
async def mock_login():
    """Mock login endpoint for development testing.

    Returns a fake JWT token and sets cookies for the frontend.
    Only works when MOCK_AUTH=true.
    """
    if not settings.MOCK_AUTH:
        return JSONResponse(
            status_code=403,
            content={"detail": "Mock login disabled. Set MOCK_AUTH=true in .env"},
        )

    # Create a mock user object that the frontend can use
    mock_user = {
        "id": "mock-user-001",
        "email": "mock@example.com",
        "access_token": "mock-token-for-development",
        "refresh_token": "mock-refresh-token",
    }

    response = JSONResponse(content={"user": mock_user, "session": mock_user})

    # Set cookies that the Supabase client expects
    response.set_cookie(
        key="sb-access-token",
        value="mock-token-for-development",
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=3600,
    )
    response.set_cookie(
        key="sb-refresh-token",
        value="mock-refresh-token",
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400,
    )

    return response
