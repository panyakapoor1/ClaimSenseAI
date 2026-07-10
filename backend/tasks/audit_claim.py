from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models.claim import Claim, ClaimItem, AuditFinding
from agents.claim_auditor import audit_claim_item
import asyncio

async def audit_claim_task(ctx, claim_id: str, policy_id: str):
    """
    Background task to audit an entire claim item by item.
    """
    print(f"Starting audit for claim {claim_id} against policy {policy_id}")

    async with AsyncSessionLocal() as session:
        # Fetch all claim items for this claim
        result = await session.execute(
            select(ClaimItem).where(ClaimItem.claim_id == claim_id)
        )
        claim_items = result.scalars().all()

        if not claim_items:
            print(f"No items found for claim {claim_id}")
            return {"status": "error", "message": "No claim items found."}

        audit_findings = []

        # Process each item sequentially to avoid overwhelming the LLM rate limit
        # (Groq is fast enough that sequential is fine for a single claim)
        for item in claim_items:
            print(f"Auditing item: {item.category} - {item.description}")
            
            # Call our Claim Auditor agent
            llm_decision = await audit_claim_item(item=item, policy_id=policy_id)

            # Create the AuditFinding record
            finding = AuditFinding(
                claim_item_id=item.id,
                status=llm_decision.get("status", "APPROVED"),
                reason=llm_decision.get("reason", "No reason provided."),
                policy_clause_cited=llm_decision.get("policy_clause_cited"),
                original_clause_text=llm_decision.get("original_clause_text"),
                page_number=llm_decision.get("page_number"),
                confidence=llm_decision.get("confidence", 0.0)
            )
            
            # Add to session
            session.add(finding)
            audit_findings.append(finding)

            # Sleep briefly to respect API rate limits (just in case)
            await asyncio.sleep(0.5)
        
        # Update the parent claim status
        claim = await session.get(Claim, claim_id)
        if claim:
            claim.status = "AUDIT_COMPLETE"
            
        await session.commit()
        print(f"Audit completed for claim {claim_id}. {len(audit_findings)} findings saved.")
        
        return {"status": "success", "total_items_audited": len(audit_findings)}
