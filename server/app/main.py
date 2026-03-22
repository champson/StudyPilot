from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import AppError, app_exception_handler
from app.core.limiter import RateLimitExceeded, _rate_limit_exceeded_handler, limiter
from app.core.logging import RequestIDMiddleware, get_logger, setup_logging
from app.core.redis import get_redis_client


def create_app() -> FastAPI:
    setup_logging()
    logger = get_logger(__name__)

    application = FastAPI(title="StudyPilot API", version="0.1.0")

    # Configure rate limiter
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware order matters: last added = first executed
    # CORS middleware (handles preflight requests)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # RequestID middleware (added last so it executes first)
    application.add_middleware(RequestIDMiddleware)

    application.add_exception_handler(AppError, app_exception_handler)
    application.include_router(api_router)

    @application.get("/health")
    async def health_check():
        checks: dict[str, str] = {}

        # Database connectivity
        try:
            async with async_session_factory() as db:
                await db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as e:
            logger.warning("health_check_db_error", error=str(e))
            checks["database"] = "error"

        # Redis connectivity
        try:
            redis = get_redis_client()
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as e:
            logger.warning("health_check_redis_error", error=str(e))
            checks["redis"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            {"status": "ok" if all_ok else "degraded", "checks": checks},
            status_code=200 if all_ok else 503,
        )

    return application


app = create_app()
