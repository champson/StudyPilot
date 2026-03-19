from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import AuthResponse, UserInfo


async def token_login(db: AsyncSession, token: str, role: str) -> AuthResponse:
    stmt = select(User).where(User.invite_token == token, User.role == role)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise AppError("AUTH_INVALID_TOKEN", "Token 无效或已被停用", status_code=401)

    student_id = await _resolve_student_id(db, user)
    jwt_data = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role,
        "student_id": student_id,
    }
    expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    access_token = create_access_token(jwt_data, timedelta(minutes=expire_minutes))

    return AuthResponse(
        access_token=access_token,
        expires_in=expire_minutes * 60,
        user=UserInfo(
            id=user.id, role=user.role, nickname=user.nickname, student_id=student_id
        ),
    )


async def admin_login(db: AsyncSession, username: str, password: str) -> AuthResponse:
    stmt = select(User).where(User.phone == username, User.role == "admin")
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise AppError("AUTH_WRONG_PASSWORD", "用户名或密码错误", status_code=401)
    if not verify_password(password, user.password_hash):
        raise AppError("AUTH_WRONG_PASSWORD", "用户名或密码错误", status_code=401)

    jwt_data = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": "admin",
        "student_id": None,
    }
    expire_minutes = 1440  # 24h for admin
    access_token = create_access_token(jwt_data, timedelta(minutes=expire_minutes))

    return AuthResponse(
        access_token=access_token,
        expires_in=expire_minutes * 60,
        user=UserInfo(id=user.id, role=user.role, nickname=user.nickname, student_id=None),
    )


async def refresh_user_token(db: AsyncSession, user: User) -> AuthResponse:
    student_id = await _resolve_student_id(db, user)
    expire_minutes = 1440 if user.role == "admin" else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    jwt_data = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role,
        "student_id": student_id,
    }
    access_token = create_access_token(jwt_data, timedelta(minutes=expire_minutes))

    return AuthResponse(
        access_token=access_token,
        expires_in=expire_minutes * 60,
        user=UserInfo(id=user.id, role=user.role, nickname=user.nickname, student_id=student_id),
    )


async def _resolve_student_id(db: AsyncSession, user: User) -> int | None:
    if user.role == "student":
        from app.models.student_profile import StudentProfile

        stmt = select(StudentProfile.id).where(StudentProfile.user_id == user.id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()
        return row
    if user.role == "parent":
        return user.linked_student_id
    return None
