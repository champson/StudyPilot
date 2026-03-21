import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import async_session_factory
from app.core.exceptions import AppError, app_exception_handler
from app.core.logging import setup_logging
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    setup_logging()

    application = FastAPI(title="StudyPilot API", version="0.1.0")

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
            logger.warning("Health check: database unreachable: %s", e)
            checks["database"] = "error"

        # Redis connectivity
        try:
            redis = get_redis_client()
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as e:
            logger.warning("Health check: redis unreachable: %s", e)
            checks["redis"] = "error"

        all_ok = all(v == "ok" for v in checks.values())
        return JSONResponse(
            {"status": "ok" if all_ok else "degraded", "checks": checks},
            status_code=200 if all_ok else 503,
        )

    return application


app = create_app()
