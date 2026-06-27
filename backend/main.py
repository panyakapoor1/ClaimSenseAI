from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from contextlib import asynccontextmanager
from arq import create_pool
from arq.connections import RedisSettings
from core.config import settings
from core.database import AsyncSessionLocal
from models.user import User
from models.claim import Claim
from sqlalchemy.future import select
from pydantic import BaseModel
import os
import uuid

class TaskRequest(BaseModel):
    task_name: str
    delay_seconds: int = 5

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ClaimSense AI Backend Starting...")
    app.state.redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    
    # Seed a dummy user for testing if one doesn't exist
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            user = User(email="test@claimsense.ai")
            session.add(user)
            await session.commit()
            print(f"Created dummy user: {user.id}")
            
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
    return {"status": "online", "service": "ClaimSense AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/test-task")
async def create_test_task(req: TaskRequest, request: Request):
    job = await request.app.state.redis_pool.enqueue_job("dummy_task", req.task_name, req.delay_seconds)
    return {"status": "enqueued", "job_id": job.job_id}

@app.post("/upload-bill/")
async def upload_bill(request: Request, file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        
        # Create a pending claim
        claim = Claim(
            user_id=user.id,
            total_billed=0.0,
            status="PENDING"
        )
        session.add(claim)
        await session.commit()
        await session.refresh(claim)
        
    # Enqueue task
    job = await request.app.state.redis_pool.enqueue_job(
        "extract_bill_task", 
        str(claim.id), 
        file_path
    )
    
    return {
        "status": "processing",
        "claim_id": str(claim.id),
        "job_id": job.job_id
    }
