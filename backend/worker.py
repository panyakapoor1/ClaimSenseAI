from arq.connections import RedisSettings
from core.config import settings
from tasks.dummy import dummy_task
from tasks.extract_bill import extract_bill_task
from tasks.ingest_policy import ingest_policy_task

class WorkerSettings:
    functions = [dummy_task, extract_bill_task, ingest_policy_task]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    # Increase timeout for embedding generation (large PDFs can take time)
    max_jobs = 5
    job_timeout = 600
