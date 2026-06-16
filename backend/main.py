from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("ClaimSense AI Backend Starting...")
    yield
    print("ClaimSense AI Backend Shutting Down...")

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
