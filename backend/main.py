from fastapi import FastAPI, Request, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from arq import create_pool
from core.config import settings, get_redis_settings
from core.database import AsyncSessionLocal
from core.llm import LLM_AVAILABLE, LLM_MODEL
from models.user import User
from models.claim import Claim, ClaimItem, AuditFinding
from sqlalchemy.future import select
import redis.asyncio as aioredis
import os
import uuid
import json


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ClaimSense AI Backend Starting...")
    app.state.redis_pool = await create_pool(get_redis_settings())
    # Separate raw redis connection for Pub/Sub
    app.state.redis_pubsub = aioredis.from_url(settings.redis_url, decode_responses=True)
    
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
    await app.state.redis_pubsub.close()
    app.state.redis_pool.close()
    await app.state.redis_pool.wait_closed()

app = FastAPI(
    title="ClaimSense AI",
    description="Multi-Agent RAG-Based Insurance Claim Auditor",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "service": "ClaimSense AI API"}

@app.get("/health")
async def health_check():
    # Report AI availability so the frontend can label a degraded state rather
    # than letting uploads fail one at a time with no explanation.
    return {"status": "healthy", "llm_available": LLM_AVAILABLE, "llm_model": LLM_MODEL if LLM_AVAILABLE else None}

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

@app.post("/upload-policy/")
async def upload_policy(request: Request, file: UploadFile = File(...), insurer_name: str = "Unknown", policy_name: str = "Unknown"):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
        
    async with AsyncSessionLocal() as session:
        from models.policy import Policy
        result = await session.execute(select(User).limit(1))
        user = result.scalars().first()
        
        policy = Policy(
            user_id=user.id,
            insurer_name=insurer_name,
            policy_name=policy_name
        )
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        
    # Enqueue background ingestion task
    job = await request.app.state.redis_pool.enqueue_job(
        "ingest_policy_task",
        str(policy.id),
        file_path
    )
    
    return {
        "status": "processing",
        "policy_id": str(policy.id),
        "job_id": job.job_id
    }

@app.get("/search-policy/{policy_id}")
async def search_policy(policy_id: str, q: str):
    from agents.rag_retriever import search_policy_chunks
    results = await search_policy_chunks(query=q, policy_id=policy_id, top_k=5)
    return {"query": q, "results": results}

@app.post("/audit-claim/")
async def audit_claim(request: Request, claim_id: str, policy_id: str):
    """
    Enqueues a background task to audit a parsed claim against an ingested policy using RAG + LLM.
    """
    job = await request.app.state.redis_pool.enqueue_job("audit_claim_task", claim_id, policy_id)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to enqueue audit task")
    return {"status": "processing", "claim_id": claim_id, "policy_id": policy_id, "job_id": job.job_id}

@app.get("/audit-results/{claim_id}")
async def get_audit_results(claim_id: str):
    """
    Fetches the generated audit findings for a specific claim.
    """
    async with AsyncSessionLocal() as session:
        # Check if claim exists
        claim = await session.get(Claim, claim_id)
        if not claim:
            raise HTTPException(status_code=404, detail="Claim not found")

        # Fetch claim items along with their audit findings
        result = await session.execute(
            select(ClaimItem).where(ClaimItem.claim_id == claim_id)
        )
        items = result.scalars().all()
        
        # We need to manually fetch the findings for these items since we don't have eager loading setup here
        # or we can query AuditFinding directly
        findings_result = await session.execute(
            select(AuditFinding).where(AuditFinding.claim_item_id.in_([item.id for item in items]))
        )
        findings = findings_result.scalars().all()
        
        # Map findings to items
        finding_map = {f.claim_item_id: f for f in findings}
        
        response_items = []
        for item in items:
            finding = finding_map.get(item.id)
            response_items.append({
                "item_id": str(item.id),
                "category": item.category,
                "description": item.description,
                "billed_amount": item.billed_amount,
                "audit": {
                    "status": finding.status if finding else "PENDING",
                    "reason": finding.reason if finding else None,
                    "policy_clause_cited": finding.policy_clause_cited if finding else None,
                    "original_clause_text": finding.original_clause_text if finding else None,
                    "page_number": finding.page_number if finding else None,
                    "confidence": finding.confidence if finding else None
                } if finding else None
            })

        return {
            "claim_id": str(claim.id),
            "claim_status": claim.status,
            "total_billed": claim.total_billed,
            "items": response_items
        }

@app.get("/claims/")
async def list_claims():
    """
    Lists all claims in the system.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Claim).order_by(Claim.created_at.desc())
        )
        claims = result.scalars().all()
        return [
            {
                "id": str(c.id),
                "status": c.status,
                "total_billed": c.total_billed,
                "created_at": c.created_at
            }
            for c in claims
        ]

@app.post("/generate-appeal/")
async def generate_appeal(request: Request, claim_id: str):
    """
    Enqueues a background task to generate an appeal letter for a claim with rejected items.
    """
    job = await request.app.state.redis_pool.enqueue_job("generate_appeal_task", claim_id)
    if not job:
        raise HTTPException(status_code=500, detail="Failed to enqueue appeal task")
    return {"status": "processing", "claim_id": claim_id, "job_id": job.job_id}

@app.get("/appeal/{claim_id}")
async def get_appeal(claim_id: str):
    """
    Fetches the generated appeal letter for a specific claim.
    """
    from models.claim import AppealDocument
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AppealDocument).where(AppealDocument.claim_id == claim_id)
        )
        appeal = result.scalars().first()
        if not appeal:
            raise HTTPException(status_code=404, detail="Appeal letter not found or not generated yet")
        
        return {
            "claim_id": claim_id,
            "appeal_text": appeal.content,
            "created_at": appeal.created_at
        }

@app.websocket("/ws/tasks/{job_id}")
async def websocket_task_updates(websocket: WebSocket, job_id: str):
    """
    WebSocket endpoint to stream real-time progress updates for a background task.
    Uses Redis Pub/Sub to listen for updates published by ARQ workers.
    """
    await websocket.accept()
    redis_conn = websocket.app.state.redis_pubsub
    pubsub = redis_conn.pubsub()
    channel = f"job_updates:{job_id}"
    
    try:
        await pubsub.subscribe(channel)
        # Send initial connection confirmation
        await websocket.send_json({"type": "connected", "job_id": job_id, "channel": channel})
        
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                # If the task signals completion, close the socket
                if data.get("status") in ("completed", "error"):
                    break
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for job {job_id}")
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        # Breaking out of the loop leaves the socket open otherwise, so the client
        # sits waiting on a stream that will never produce another frame.
        try:
            await websocket.close()
        except RuntimeError:
            pass  # already closed by the client disconnecting
