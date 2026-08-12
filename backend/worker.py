import asyncio

from core.config import get_redis_settings
from tasks.extract_bill import extract_bill_task
from tasks.ingest_policy import ingest_policy_task
from tasks.audit_claim import audit_claim_task
from tasks.generate_appeal import generate_appeal_task


async def startup(ctx):
    """Warm the models before any job is accepted.

    Otherwise the first job pays for the model downloads, which stalls it for
    minutes and makes the whole pipeline look hung.
    """
    from agents.policy_ingestor import generate_embeddings
    from services.retrieval import _load_reranker

    try:
        await asyncio.to_thread(generate_embeddings, ["warmup"])
        print("Embedding model warm.")
    except Exception as e:
        print(f"Warning: embedding model warmup failed: {e}")

    # The cross-encoder is downloaded on first use. Paying that inside the first
    # audit stalls the job for minutes and looks like a hang.
    try:
        await asyncio.to_thread(_load_reranker)
        print("Reranker warm.")
    except Exception as e:
        print(f"Warning: reranker warmup failed: {e}")


async def shutdown(ctx):
    pass


class WorkerSettings:
    functions = [extract_bill_task, ingest_policy_task, audit_claim_task, generate_appeal_task]
    redis_settings = get_redis_settings()
    on_startup = startup

    # Retries cover transient faults: a provider blip, a database failover, a
    # policy still indexing. Terminal conditions — no API key, an unreadable
    # document — are caught inside the tasks and returned rather than raised,
    # so they consume no attempts and the claim reaches a final state at once.
    max_tries = 4

    # Kills a job that has genuinely hung rather than letting it hold a worker
    # slot forever. Comfortably above a real audit of a long bill.
    job_timeout = 900

    # Completed job results are kept briefly so a caller polling by job id gets
    # an answer, without the queue growing without bound.
    keep_result = 900
    on_shutdown = shutdown
    # Bounded so several concurrent audits cannot saturate the CPU that the
    # embedding and reranking models need.
    max_jobs = 5
