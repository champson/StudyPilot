from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, detail: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}


async def app_exception_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "detail": exc.detail}},
    )
