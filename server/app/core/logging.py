"""Structured logging and request tracing with structlog."""

import logging
import sys
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings


def setup_logging(log_level: str | None = None) -> None:
    """Configure structlog JSON logging.
    
    Args:
        log_level: Optional log level override. If None, uses DEBUG when settings.DEBUG
                   is True, otherwise INFO.
    """
    if log_level is None:
        log_level = "DEBUG" if settings.DEBUG else "INFO"
    
    # Configure standard logging first (for third-party libraries)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level),
    )
    
    # Quiet down noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Configure structlog
    if settings.DEBUG:
        # Development: human-readable output
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structlog logger instance.
    
    Args:
        name: Optional logger name. If None, uses the calling module's name.
        
    Returns:
        A bound structlog logger.
    """
    return structlog.get_logger(name or __name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID tracing to all requests.
    
    This middleware:
    - Extracts or generates a unique request ID for each request
    - Binds the request ID and other context to structlog's contextvars
    - Logs request start and completion
    - Adds the request ID to the response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Clear and bind context variables for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
        )
        
        logger = structlog.get_logger()
        await logger.ainfo("request_started")
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        await logger.ainfo("request_completed", status_code=response.status_code)
        return response
