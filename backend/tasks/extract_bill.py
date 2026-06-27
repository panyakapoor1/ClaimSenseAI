import os
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models.claim import Claim, ClaimItem
from agents.bill_extractor import extract_bill_data

async def extract_bill_task(ctx, claim_id: str, pdf_path: str):
    print(f"Starting extraction for claim {claim_id}")
    
    # Extract structured data
    try:
        bill_data = await extract_bill_data(pdf_path)
    except Exception as e:
        print(f"Extraction failed: {e}")
        return {"status": "failed", "error": str(e)}
        
    # Update Database
    async with AsyncSessionLocal() as session:
        # Fetch the pending claim
        result = await session.execute(select(Claim).where(Claim.id == claim_id))
        claim = result.scalars().first()
        
        if not claim:
            print(f"Claim {claim_id} not found.")
            return {"status": "failed", "error": "Claim not found"}
            
        claim.total_billed = float(bill_data.get("total_billed", 0.0))
        claim.status = "EXTRACTED"
        
        # Insert items
        items = bill_data.get("items", [])
        for item in items:
            new_item = ClaimItem(
                claim_id=claim.id,
                category=item.get("category", "Other"),
                description=item.get("description", ""),
                billed_amount=float(item.get("billed_amount", 0.0))
            )
            session.add(new_item)
            
        await session.commit()
    
    # Cleanup file
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        
    print(f"Claim {claim_id} extracted successfully. Found {len(items)} items.")
    return {"status": "success", "total_items": len(items)}
