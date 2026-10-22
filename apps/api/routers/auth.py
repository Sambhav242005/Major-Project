from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from core.security import get_current_user, User
from core.config import settings
from core.rate_limit import limiter, local_login_rate_limit_key
from db.session import get_db

router = APIRouter()


class LocalLogin(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LocalSignup(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=1024)
    full_name: str = Field(default="", max_length=200)


@router.post("/local-login")
@limiter.limit("10/minute", key_func=local_login_rate_limit_key)
async def local_login(request: Request, response: Response, credentials: LocalLogin, db: AsyncSession = Depends(get_db)):
    if settings.AUTH_PROVIDER != "local":
        raise HTTPException(status_code=403, detail="Local authentication is disabled")
    from core.local_auth import authenticate, create_access_token

    account = await authenticate(db, credentials.email, credentials.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token, expires_at = create_access_token(account.id, account.email)
    user = {"id": str(account.id), "email": account.email}
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "session": {"access_token": token, "user": user, "expires_at": expires_at,
                                      "expires_in": settings.LOCAL_AUTH_TOKEN_TTL_SECONDS, "token_type": "bearer"}}


@router.post("/local-signup")
@router.post("/signup")
@limiter.limit("5/minute", key_func=local_login_rate_limit_key)
async def local_signup(request: Request, response: Response, credentials: LocalSignup, db: AsyncSession = Depends(get_db)):
    if settings.AUTH_PROVIDER != "local" or not settings.LOCAL_AUTH_ALLOW_SIGNUP:
        raise HTTPException(status_code=403, detail="Public registration is disabled. Ask the administrator to create an account.")
    from core.local_auth import create_account, create_access_token

    try:
        account = await create_account(db, credentials.email, credentials.password, credentials.full_name)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except IntegrityError:
        # The unique constraint also handles simultaneous requests for one email.
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account already exists for this email.") from None
    token, expires_at = create_access_token(account.id, account.email)
    await db.commit()
    user = {"id": str(account.id), "email": account.email}
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "session": {"access_token": token, "user": user, "expires_at": expires_at,
                                      "expires_in": settings.LOCAL_AUTH_TOKEN_TTL_SECONDS, "token_type": "bearer"}}


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
    if not settings.MOCK_AUTH or settings.ENVIRONMENT != "development":
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
