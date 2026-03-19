from pydantic_settings import BaseSettings


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

    DEBUG: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
