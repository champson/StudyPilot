from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    AdminLoginRequest,
    AuthResponse,
    MeResponse,
    TokenLoginRequest,
)
from app.schemas.common import SuccessResponse
from app.services.auth import admin_login, refresh_user_token, token_login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token-login", response_model=SuccessResponse[AuthResponse])
@limiter.limit("10/minute")
async def login_with_token(
    request: Request, body: TokenLoginRequest, db: AsyncSession = Depends(get_db)
):
    result = await token_login(db, body.token, body.role)
    return SuccessResponse(data=result)


@router.post("/admin-login", response_model=SuccessResponse[AuthResponse])
@limiter.limit("5/minute")
async def login_as_admin(
    request: Request, body: AdminLoginRequest, db: AsyncSession = Depends(get_db)
):
    result = await admin_login(db, body.username, body.password)
    return SuccessResponse(data=result)


@router.get("/me", response_model=SuccessResponse[MeResponse])
async def get_me(user: User = Depends(get_current_user)):
    payload = user._jwt_payload  # type: ignore[attr-defined]
    return SuccessResponse(
        data=MeResponse(
            id=user.id,
            role=user.role,
            nickname=user.nickname,
            phone=user.phone,
            student_id=payload.get("student_id"),
        )
    )


@router.post("/refresh", response_model=SuccessResponse[AuthResponse])
async def refresh_token(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await refresh_user_token(db, user)
    return SuccessResponse(data=result)
