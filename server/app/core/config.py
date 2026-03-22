import warnings

from pydantic_settings import BaseSettings

_INSECURE_DEFAULTS = {
    "JWT_SECRET_KEY": "change-me-to-a-random-secret",
    "SHARE_TOKEN_SECRET": "change-me-share-secret",
    "ADMIN_PASSWORD": "changeme",
}


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://studypilot:studypilot@localhost:5432/studypilot"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET_KEY: str = "change-me-to-a-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days

    ADMIN_PHONE: str = "admin"
    ADMIN_PASSWORD: str = "changeme"

    UPLOAD_DIR: str = "./uploads"
    SHARE_TOKEN_SECRET: str = "change-me-share-secret"
    SHARE_TOKEN_EXPIRE_DAYS: int = 7

    DASHSCOPE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    MODEL_CONFIG_PATH: str = "config/model_config.yaml"
    OCR_SYNC_FALLBACK: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    def warn_insecure_defaults(self) -> None:
        for field, default_value in _INSECURE_DEFAULTS.items():
            if getattr(self, field) == default_value:
                warnings.warn(
                    f"SECURITY: {field} is using its default value. "
                    f"Set {field} in environment or .env before deploying.",
                    stacklevel=2,
                )


settings = Settings()
settings.warn_insecure_defaults()
