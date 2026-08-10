from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from core.security import get_current_user, User
from core.config import settings
from core.rate_limit import limiter

router = APIRouter()


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email}


@router.post("/mock-login")
@limiter.limit("10/minute")
async def mock_login(request: Request, response: Response):
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
        "id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
        "email": "mock@example.com",
        "access_token": "mock-token-for-development",
        "refresh_token": "mock-refresh-token",
    }

    response = JSONResponse(content={"user": mock_user, "session": mock_user})

    # Secure cookies in non-dev environments; dev may use plaintext localhost
    secure_cookies = settings.ENVIRONMENT != "development"

    # Set cookies that the Supabase client expects
    response.set_cookie(
        key="sb-access-token",
        value="mock-token-for-development",
        httponly=True,
        secure=secure_cookies,
        samesite="lax",
        max_age=3600,
    )
    response.set_cookie(
        key="sb-refresh-token",
        value="mock-refresh-token",
        httponly=True,
        secure=secure_cookies,
        samesite="lax",
        max_age=86400,
    )

    return response
