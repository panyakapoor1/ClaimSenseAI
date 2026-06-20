import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://claimsense:securepassword@localhost:5432/claimsensedb")

settings = Settings()
