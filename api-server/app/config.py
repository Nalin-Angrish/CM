import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://cloudmgr:changeme_in_production@database:5432/cloudmgr",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    jwt_expiration_minutes: int = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))
    llm_service_url: str = os.getenv("LLM_SERVICE_URL", "http://llm-service:8001")
    mcp_server_url: str = os.getenv("MCP_SERVER_URL", "http://mcp-server:8002")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    max_resources_per_user: int = int(os.getenv("MAX_RESOURCES_PER_USER", "20"))

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
