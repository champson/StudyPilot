from fastapi.responses import JSONResponse

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    limiter = Limiter(key_func=get_remote_address)
except ImportError:
    class RateLimitExceededError(Exception):
        pass

    RateLimitExceeded = RateLimitExceededError

    class NoopLimiter:
        def limit(self, _value: str):
            def decorator(func):
                return func

            return decorator

    limiter = NoopLimiter()

    async def _rate_limit_exceeded_handler(_request, _exc):
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "SYS_RATE_LIMITED",
                    "message": "请求过于频繁",
                    "detail": {},
                }
            },
        )
