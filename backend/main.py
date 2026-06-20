from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings
from pydantic import BaseModel

class TaskRequest(BaseModel):
    task_name: str
    delay_seconds: int = 5

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ClaimSense AI Backend Starting...")
    app.state.redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    print("ClaimSense AI Backend Shutting Down...")
    app.state.redis_pool.close()
    await app.state.redis_pool.wait_closed()

app = FastAPI(
    title="ClaimSense AI",
    description="Multi-Agent RAG-Based Insurance Claim Auditor",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "ClaimSense AI API",
        "message": "Welcome to the autonomous insurance advocate."
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/test-task")
async def create_test_task(req: TaskRequest, request: Request):
    job = await request.app.state.redis_pool.enqueue_job("dummy_task", req.task_name, req.delay_seconds)
    return {"status": "enqueued", "job_id": job.job_id}
