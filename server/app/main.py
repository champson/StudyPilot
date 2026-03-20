from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError, app_exception_handler


def create_app() -> FastAPI:
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
        return {"status": "ok"}

    return application


app = create_app()
