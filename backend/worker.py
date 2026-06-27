from arq.connections import RedisSettings
from core.config import settings
from tasks.dummy import dummy_task
from tasks.extract_bill import extract_bill_task

class WorkerSettings:
    functions = [dummy_task, extract_bill_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
