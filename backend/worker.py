from arq.connections import RedisSettings
from core.config import settings
from tasks.dummy import dummy_task

class WorkerSettings:
    functions = [dummy_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
