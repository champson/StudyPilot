from collections.abc import AsyncGenerator, Callable

import jwt
import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.redis import get_redis_client
from app.models.user import User

security = HTTPBearer()


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    yield get_redis_client()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AppError("AUTH_TOKEN_EXPIRED", "Token 已过期", status_code=401)
    except jwt.InvalidTokenError:
        raise AppError("AUTH_INVALID_TOKEN", "无效的认证令牌", status_code=401)

    user_id = payload.get("user_id")
    if user_id is None:
        raise AppError("AUTH_INVALID_TOKEN", "无效的认证令牌", status_code=401)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise AppError("AUTH_INVALID_TOKEN", "用户不存在", status_code=401)

    # Attach decoded payload for convenience
    user._jwt_payload = payload  # type: ignore[attr-defined]
    return user


def get_student_id(user: User = Depends(get_current_user)) -> int:
    payload = user._jwt_payload  # type: ignore[attr-defined]
    student_id = payload.get("student_id")
    if student_id is None:
        raise AppError("AUTH_NO_STUDENT", "当前用户未关联学生档案", status_code=403)
    return student_id


def require_role(*roles: str) -> Callable:
    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(
                "AUTH_INSUFFICIENT_ROLE",
                f"需要 {'/'.join(roles)} 角色权限",
                status_code=403,
            )
        return user

    return _check


require_student = require_role("student")
require_parent = require_role("parent")
require_admin = require_role("admin")
