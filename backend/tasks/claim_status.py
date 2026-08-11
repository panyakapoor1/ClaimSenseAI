from core.database import AsyncSessionLocal
from models.claim import Claim


async def mark_claim(claim_id: str, status: str) -> None:
    """Move a claim to a terminal status so the UI shows why it stopped.

    Without this a failed pipeline leaves the claim on PENDING forever, which
    reads as "still working" rather than "this went wrong".

    Never raises: it runs on the failure path, and a bookkeeping error here must
    not mask the original problem being reported.
    """
    try:
        async with AsyncSessionLocal() as session:
            claim = await session.get(Claim, claim_id)
            if claim:
                claim.status = status
                await session.commit()
    except Exception as e:
        print(f"Warning: could not mark claim {claim_id} as {status}: {e}")
