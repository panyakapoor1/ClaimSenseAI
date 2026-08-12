from sqlalchemy import func
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models import (
    AdjudicationStatus,
    AuditFinding,
    Claim,
    ClaimItem,
    ClaimStatus,
    DocumentChunk,
    ExtractedFact,
    ModelVersion,
    Policy,
    RiskScore,
    RiskSignal,
)
from services import risk as risk_engine
from sqlalchemy.orm import selectinload
from agents.claim_auditor import audit_claim_item
from core.llm import LLMUnavailableError
from tasks.claim_status import mark_claim as _mark_claim
from tasks.progress import publish_progress as _publish_progress
import asyncio

# Bill extraction and policy ingestion are separate jobs that race with this one.
# Policy ingestion is the slower of the two on a cold worker: the first run
# downloads the all-MiniLM-L6-v2 embedding model before it can embed anything.
_WAIT_ATTEMPTS = 60
_WAIT_INTERVAL_SECONDS = 2


def _coerce_status(value) -> AdjudicationStatus:
    """Map the model's free-text verdict onto the enum.

    Anything unrecognised becomes NEEDS_REVIEW rather than a default verdict: a
    value the model did not actually produce must never be recorded as a
    decision it made.
    """
    try:
        return AdjudicationStatus(str(value).strip().upper())
    except (ValueError, AttributeError):
        return AdjudicationStatus.NEEDS_REVIEW


def _coerce_page(value) -> int | None:
    """Page numbers arrive as strings like "Page 8" or "8"."""
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else None


def _coerce_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def audit_claim_task(ctx, claim_id: str, policy_id: str):
    """Audit an entire claim item by item.

    Any unhandled exception is reported over the progress channel before it
    propagates: otherwise the task dies silently and the UI waits forever on a
    completion frame that will never arrive.
    """
    job_id = ctx.get("job_id", "unknown")
    try:
        return await _run_audit(ctx, job_id, claim_id, policy_id)
    except LLMUnavailableError as e:
        # Configuration problem, not a transient failure. Say so plainly and do
        # not retry: no amount of retrying conjures an API key.
        print(f"Audit aborted for claim {claim_id}: {e}")
        await _mark_claim(claim_id, ClaimStatus.LLM_UNAVAILABLE, reason=str(e))
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": str(e),
            "claim_id": claim_id, "progress_pct": 0,
        })
        return {"status": "error", "reason": "llm_unavailable", "message": str(e)}
    except Exception as e:
        print(f"Audit failed for claim {claim_id}: {e}")
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": f"Audit failed: {e}",
            "claim_id": claim_id, "progress_pct": 0,
        })
        raise


async def _run_audit(ctx, job_id: str, claim_id: str, policy_id: str):
    print(f"Starting audit for claim {claim_id} against policy {policy_id}")
    await _publish_progress(ctx, job_id, {
        "type": "progress", "status": "started", "message": "Starting claim audit...",
        "claim_id": claim_id, "progress_pct": 0
    })

    # Wait for the bill extraction job to finish.
    #
    # Each poll uses its own session on purpose. Polling inside one long-lived
    # session never observes the other worker's commit: the open transaction keeps
    # its original snapshot, and SQLAlchemy's identity map keeps returning the
    # first-loaded Claim with its stale status.
    bill_ready = False
    for attempt in range(_WAIT_ATTEMPTS):
        async with AsyncSessionLocal() as poll_session:
            result = await poll_session.execute(
                select(Claim).where(Claim.id == claim_id)
            )
            claim = result.scalars().first()
            status = claim.status if claim else None

        if status == ClaimStatus.EXTRACTED:
            bill_ready = True
            break
        if status in (ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE):
            break

        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": "Waiting for medical bill extraction...",
            "claim_id": claim_id,
            "progress_pct": int((attempt / _WAIT_ATTEMPTS) * 3),
        })
        await asyncio.sleep(_WAIT_INTERVAL_SECONDS)

    if not bill_ready:
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": "Bill extraction did not complete in time.",
            "claim_id": claim_id, "progress_pct": 0,
        })
        return {"status": "error", "message": "Bill extraction did not complete."}

    # Wait for policy ingestion. Without this the RAG retriever searches an
    # empty chunk table and every finding cites "no relevant policy clause".
    policy_ready = False
    for attempt in range(_WAIT_ATTEMPTS):
        async with AsyncSessionLocal() as poll_session:
            chunk_count = await poll_session.scalar(
                select(func.count()).select_from(DocumentChunk).where(
                    DocumentChunk.policy_id == policy_id
                )
            )
        if chunk_count and chunk_count > 0:
            policy_ready = True
            break

        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": "Waiting for policy ingestion (embedding the policy document)...",
            "claim_id": claim_id,
            "progress_pct": 3 + int((attempt / _WAIT_ATTEMPTS) * 2),
        })
        await asyncio.sleep(_WAIT_INTERVAL_SECONDS)

    if not policy_ready:
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": "Policy ingestion did not complete in time. Cannot audit without policy context.",
            "claim_id": claim_id, "progress_pct": 0,
        })
        return {"status": "error", "message": "Policy ingestion did not complete."}

    async with AsyncSessionLocal() as session:
        # Fetch all claim items for this claim
        result = await session.execute(
            select(ClaimItem).where(ClaimItem.claim_id == claim_id)
        )
        claim_items = result.scalars().all()

        if not claim_items:
            print(f"No items found for claim {claim_id}")
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "error", "message": "No claim items found. Bill extraction failed."
            })
            return {"status": "error", "message": "No claim items found."}

        total = len(claim_items)
        audit_findings = []

        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": f"Found {total} items to audit.", "progress_pct": 5
        })

        # Process each item sequentially to avoid overwhelming the LLM rate limit
        for idx, item in enumerate(claim_items, 1):
            print(f"Auditing item: {item.category} - {item.description}")
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "running",
                "message": f"Auditing item {idx}/{total}: {item.category} - {item.description}",
                "progress_pct": int(5 + (idx / total) * 85)
            })
            
            # Call our Claim Auditor agent
            llm_decision = await audit_claim_item(item=item, policy_id=policy_id)

            # Create the AuditFinding record
            finding = AuditFinding(
                claim_item_id=item.id,
                chunk_id=llm_decision.get("chunk_id"),
                status=_coerce_status(llm_decision.get("status")),
                reason=llm_decision.get("reason", "No reason provided."),
                policy_clause_cited=llm_decision.get("policy_clause_cited"),
                original_clause_text=llm_decision.get("original_clause_text"),
                page_number=_coerce_page(llm_decision.get("page_number")),
                capped_amount=_coerce_float(llm_decision.get("capped_amount")),
                confidence=_coerce_float(llm_decision.get("confidence")) or 0.0,
            )
            
            # Add to session
            session.add(finding)
            audit_findings.append(finding)

            # Sleep briefly to respect API rate limits (just in case)
            await asyncio.sleep(0.5)
        
        await session.flush()

        # --- risk ----------------------------------------------------------
        # Computed from what the pipeline actually found: the line items, the
        # verdicts just written, the located facts and the policy. Deterministic
        # and reproducible — no model involved.
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": "Scoring risk signals...", "progress_pct": 92,
        })

        scored = await _score_risk(session, claim_id, policy_id)

        # Update the parent claim status
        claim = await session.get(Claim, claim_id)
        if claim:
            claim.status = ClaimStatus.AUDIT_COMPLETE
            
        await session.commit()
        print(f"Audit completed for claim {claim_id}. {len(audit_findings)} findings saved.")
        
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "completed",
            "message": (
                f"Audit complete. {len(audit_findings)} findings, "
                f"risk {scored['score']:.0f}/100 ({scored['band']})."
            ),
            "progress_pct": 100,
            "total_items_audited": len(audit_findings),
            "risk_score": scored["score"],
            "risk_band": scored["band"],
        })

        return {
            "status": "success",
            "total_items_audited": len(audit_findings),
            "risk": scored,
        }


async def _score_risk(session, claim_id: str, policy_id: str) -> dict:
    """Run the rules engine and persist its signals and score.

    Previous signals for the claim are cleared first: re-auditing should replace
    the assessment, not accumulate a second copy of every rule that fired.
    """
    items = (
        await session.execute(
            select(ClaimItem)
            .options(selectinload(ClaimItem.audit_finding))
            .where(ClaimItem.claim_id == claim_id)
        )
    ).scalars().all()

    facts = (
        await session.execute(
            select(ExtractedFact).where(ExtractedFact.claim_id == claim_id)
        )
    ).scalars().all()

    claim = await session.get(Claim, claim_id)
    policy = await session.get(Policy, policy_id)

    existing = (
        await session.execute(select(RiskSignal).where(RiskSignal.claim_id == claim_id))
    ).scalars().all()
    for stale in existing:
        await session.delete(stale)
    await session.flush()

    signals = risk_engine.evaluate(claim, list(items), list(facts), policy)
    total, band, breakdown = risk_engine.score(signals)

    version = await _rules_version(session)

    for signal in signals:
        session.add(
            RiskSignal(
                claim_id=claim.id,
                claim_item_id=signal.claim_item_id,
                code=signal.code,
                title=signal.title,
                detail=signal.detail,
                direction=signal.direction,
                weight=signal.weight,
                evidence_refs=signal.evidence_refs,
            )
        )

    session.add(
        RiskScore(
            claim_id=claim.id,
            model_version_id=version.id if version else None,
            score=total,
            band=band,
            signal_count=len(signals),
            breakdown=breakdown,
        )
    )

    print(f"Risk for {claim_id}: {total:.1f} ({band.value}) from {len(signals)} signal(s)")
    return {"score": total, "band": band.value, "signals": len(signals)}


async def _rules_version(session) -> ModelVersion | None:
    """The rules-engine version, recorded against every score it produces."""
    identifier = risk_engine.WEIGHTS_VERSION
    version = (
        await session.execute(
            select(ModelVersion).where(
                ModelVersion.kind == "risk_rules", ModelVersion.identifier == identifier
            )
        )
    ).scalars().first()

    if version is None:
        version = ModelVersion(
            kind="risk_rules",
            identifier=identifier,
            provider="claimsense",
            notes=(
                "Deterministic rules engine. Signals are computed from claim data; "
                "the weights are a stated policy, not learned parameters."
            ),
        )
        session.add(version)
        await session.flush()

    return version
