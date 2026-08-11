import os
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models import Claim, ClaimItem, ClaimStatus, Document, DocumentStatus
from agents.bill_extractor import extract_bill_data
from core.llm import LLMUnavailableError
from tasks.claim_status import mark_claim
from tasks.progress import publish_progress


async def extract_bill_task(ctx, claim_id: str, document_id: str):
    job_id = ctx.get("job_id", "unknown")
    print(f"Starting extraction for claim {claim_id}")

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            await publish_progress(ctx, job_id, {
                "type": "progress", "status": "error",
                "message": "Uploaded document not found.",
                "claim_id": claim_id, "progress_pct": 0
            })
            return {"status": "failed", "error": "Document not found"}
        pdf_path = document.storage_key
        document.status = DocumentStatus.PARSING
        await session.commit()

    await mark_claim(claim_id, ClaimStatus.EXTRACTING)

    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "started",
        "message": "Reading the medical bill...",
        "claim_id": claim_id, "progress_pct": 5
    })

    # Extract structured data
    try:
        bill_data = await extract_bill_data(pdf_path)
    except LLMUnavailableError as e:
        print(f"Extraction aborted: {e}")
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": str(e),
            "claim_id": claim_id, "progress_pct": 0
        })
        await mark_claim(claim_id, ClaimStatus.LLM_UNAVAILABLE, reason=str(e))
        return {"status": "failed", "reason": "llm_unavailable", "error": str(e)}
    except Exception as e:
        print(f"Extraction failed: {e}")
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": f"Bill extraction failed: {e}",
            "claim_id": claim_id, "progress_pct": 0
        })
        await mark_claim(claim_id, ClaimStatus.FAILED, reason=str(e))
        return {"status": "failed", "error": str(e)}

    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "running",
        "message": "Bill parsed. Saving line items...",
        "claim_id": claim_id, "progress_pct": 70
    })

    # Update Database
    async with AsyncSessionLocal() as session:
        # Fetch the pending claim
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalars().first()

        if not claim:
            print(f"Claim {claim_id} not found.")
            await publish_progress(ctx, job_id, {
                "type": "progress", "status": "error",
                "message": "Claim not found.",
                "claim_id": claim_id, "progress_pct": 0
            })
            return {"status": "failed", "error": "Claim not found"}

        claim.total_billed = float(bill_data.get("total_billed", 0.0))
        claim.status = ClaimStatus.EXTRACTED

        # Insert items
        items = bill_data.get("items", [])
        for line_number, item in enumerate(items, start=1):
            new_item = ClaimItem(
                claim_id=claim.id,
                line_number=line_number,
                category=item.get("category", "Other"),
                description=item.get("description", ""),
                billed_amount=float(item.get("billed_amount", 0.0)),
            )
            session.add(new_item)

        document = await session.get(Document, document_id)
        if document:
            document.status = DocumentStatus.PARSED

        await session.commit()

    # Cleanup file
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    print(f"Claim {claim_id} extracted successfully. Found {len(items)} items.")
    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "completed",
        "message": f"Extraction complete. Found {len(items)} line items.",
        "claim_id": claim_id, "progress_pct": 100, "total_items": len(items)
    })
    return {"status": "success", "total_items": len(items)}
