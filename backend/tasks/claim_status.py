from core.database import AsyncSessionLocal
from models import Claim, ClaimStatus


async def mark_claim(claim_id: str, status: ClaimStatus, *, reason: str | None = None) -> None:
    """Move a claim to a new status, recording why if it stopped.

    Without this a failed pipeline leaves the claim on its previous status, which
    reads as "still working" rather than "this went wrong". `reason` is persisted
    so the UI can say what happened instead of showing a bare FAILED badge.

    Never raises: it runs on the failure path, and a bookkeeping error here must
    not mask the original problem being reported.
    """
    try:
        async with AsyncSessionLocal() as session:
            claim = await session.get(Claim, claim_id)
            if claim:
                claim.status = status
                if reason is not None:
                    claim.failure_reason = reason
                await session.commit()
    except Exception as e:
        print(f"Warning: could not mark claim {claim_id} as {status}: {e}")
