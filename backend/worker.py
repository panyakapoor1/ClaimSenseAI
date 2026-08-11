import asyncio

from core.config import get_redis_settings
from tasks.extract_bill import extract_bill_task
from tasks.ingest_policy import ingest_policy_task
from tasks.audit_claim import audit_claim_task
from tasks.generate_appeal import generate_appeal_task


async def startup(ctx):
    """Warm the embedding model before any job is accepted.

    Otherwise the first policy ingestion pays for the model download inside a job,
    which stalls that job for minutes and makes the whole pipeline look hung.
    """
    from agents.policy_ingestor import generate_embeddings

    try:
        await asyncio.to_thread(generate_embeddings, ["warmup"])
        print("Embedding model warm.")
    except Exception as e:
        print(f"Warning: embedding model warmup failed: {e}")


async def shutdown(ctx):
    pass


class WorkerSettings:
    functions = [extract_bill_task, ingest_policy_task, audit_claim_task, generate_appeal_task]
    redis_settings = get_redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    # Increase timeout for embedding generation (large PDFs can take time)
    max_jobs = 5
    job_timeout = 600
