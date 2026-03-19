from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.exceptions import AppError, app_exception_handler


def create_app() -> FastAPI:
    application = FastAPI(title="StudyPilot API", version="0.1.0")
    application.add_exception_handler(AppError, app_exception_handler)
    application.include_router(api_router)

    @application.get("/health")
    async def health_check():
        return {"status": "ok"}

    return application


app = create_app()
