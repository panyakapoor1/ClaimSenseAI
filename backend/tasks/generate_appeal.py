import asyncio
import json
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from core.database import AsyncSessionLocal
from models.claim import Claim, ClaimItem, AuditFinding, AppealDocument
from agents.appeal_generator import generate_appeal_letter

async def _publish_progress(ctx, job_id: str, data: dict):
    """Publish a progress update to Redis Pub/Sub for WebSocket streaming."""
    try:
        redis = ctx.get("redis") or ctx.get("pool")
        if redis:
            await redis.publish(f"job_updates:{job_id}", json.dumps(data))
    except Exception as e:
        print(f"Warning: Failed to publish progress: {e}")

async def generate_appeal_task(ctx, claim_id: str):
    """
    ARQ task to generate an appeal letter for a claim that has been audited.
    """
    job_id = ctx.get("job_id", "unknown")
    print(f"[{claim_id}] Starting Appeal Generation...")
    await _publish_progress(ctx, job_id, {
        "type": "progress", "status": "started",
        "message": "Starting appeal letter generation...", "progress_pct": 0
    })

    async with AsyncSessionLocal() as db:
        # Fetch claim, items, and audit findings
        result = await db.execute(
            select(Claim)
            .options(selectinload(Claim.items).selectinload(ClaimItem.audit_finding))
            .filter(Claim.id == claim_id)
        )
        claim = result.scalars().first()

        if not claim:
            print(f"[{claim_id}] Claim not found.")
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "error", "message": "Claim not found"
            })
            return {"status": "error", "reason": "Claim not found"}

        if claim.status != "AUDIT_COMPLETE":
            print(f"[{claim_id}] Claim is not audited yet. Status: {claim.status}")
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "error", "message": "Claim not audited yet"
            })
            return {"status": "error", "reason": "Claim not audited"}

        # Collect disputed items
        disputed_items = []
        for item in claim.items:
            if item.audit_finding and item.audit_finding.status != "APPROVED":
                disputed_items.append({
                    "category": item.category,
                    "description": item.description,
                    "billed_amount": item.billed_amount,
                    "audit_status": item.audit_finding.status,
                    "audit_reason": item.audit_finding.reason,
                    "policy_clause": item.audit_finding.policy_clause_cited,
                    "clause_text": item.audit_finding.original_clause_text
                })

        if not disputed_items:
            print(f"[{claim_id}] No disputed items found. Appeal generation skipped.")
            claim.status = "NO_APPEAL_NEEDED"
            await db.commit()
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "completed",
                "message": "All items approved — no appeal needed.", "progress_pct": 100
            })
            return {"status": "success", "message": "No appeal needed"}

        print(f"[{claim_id}] Found {len(disputed_items)} disputed items. Generating letter...")
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": f"Found {len(disputed_items)} disputed items. Generating appeal letter...",
            "progress_pct": 40
        })
        
        # Call the LLM agent
        appeal_content = await generate_appeal_letter(disputed_items)

        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": "Saving appeal letter to database...", "progress_pct": 90
        })

        # Save to DB
        appeal_doc = AppealDocument(claim_id=claim.id, content=appeal_content)
        db.add(appeal_doc)

        claim.status = "APPEAL_GENERATED"
        await db.commit()

    print(f"[{claim_id}] Appeal generation complete.")
    await _publish_progress(ctx, job_id, {
        "type": "progress", "status": "completed",
        "message": "Appeal letter generated successfully.", "progress_pct": 100
    })
    return {"status": "success"}
