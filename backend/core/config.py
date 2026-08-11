import os
from arq.connections import RedisSettings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://claimsense:securepassword@localhost:5432/claimsensedb")

settings = Settings()


def get_redis_settings() -> RedisSettings:
    """arq Redis settings with timeouts that survive a busy worker.

    arq defaults to a 1 second connect timeout. Embedding a policy saturates every
    core for minutes, and a 1 second connect under that load times out and kills the
    worker process mid-job. These values give it room to reconnect instead.
    """
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    redis_settings.conn_timeout = 30
    redis_settings.conn_retries = 10
    redis_settings.conn_retry_delay = 2
    return redis_settings
