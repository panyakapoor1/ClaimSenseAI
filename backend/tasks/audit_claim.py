"""Adjudicate a claim against a policy.

The prototype coordinated with the extraction job by polling: two 60×2s loops
sleeping until the claim reached EXTRACTED and the policy had chunks. That is a
race condition with a timeout attached: two minutes wasted in the worst happy
case, a silent give-up in the slow one, and the ordering rules written down
nowhere.

This task now checks once and returns. If extraction is still running, the job
that produces the line items re-enqueues this one on completion; if the policy is
still indexing, the job asks arq to redeliver it later. Work is triggered by the
event that makes it possible rather than by a worker sleeping on it.
"""

import asyncio

from arq import Retry
from sqlalchemy import delete, func, select
from sqlalchemy.orm import selectinload

from agents.claim_auditor import audit_claim_item
from core.database import AsyncSessionLocal
from core.llm import LLMUnavailableError
from models import (
    AdjudicationStatus,
    AuditFinding,
    Claim,
    ClaimItem,
    ClaimStatus,
    DocumentChunk,
    EventKind,
    ExtractedFact,
    ModelVersion,
    Policy,
    RiskScore,
    RiskSignal,
)
from services import claim_state
from services import risk as risk_engine
from tasks.claim_status import mark_claim as _mark_claim
from tasks.progress import publish_progress as _publish_progress

# How many times to wait for policy indexing before treating it as broken.
MAX_INDEX_WAITS = 5


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
    """Adjudicate every line item, then score the claim.

    Safe to run more than once: prior findings, signals and scores are replaced
    rather than appended to, so a retry or a deliberate re-audit leaves exactly
    one verdict per line.
    """
    job_id = ctx.get("job_id", "unknown")
    try:
        return await _run_audit(ctx, job_id, claim_id, policy_id)
    except Retry:
        raise  # arq's own signal to redeliver; not a failure
    except LLMUnavailableError as e:
        # Configuration, not a transient fault. Retrying cannot conjure a key.
        print(f"Audit aborted for claim {claim_id}: {e}")
        await _mark_claim(claim_id, ClaimStatus.LLM_UNAVAILABLE, reason=str(e))
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error", "message": str(e),
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

    # --- prerequisites, checked once, never polled --------------------------
    async with AsyncSessionLocal() as session:
        claim = (
            await session.execute(select(Claim).where(Claim.id == claim_id))
        ).scalars().first()

        if claim is None:
            return {"status": "error", "message": "Claim not found."}

        if claim.status in (ClaimStatus.RECEIVED, ClaimStatus.EXTRACTING):
            # Extraction is still running. Record which policy to use and stand
            # down; extract_bill_task enqueues this again when it finishes.
            claim.policy_id = claim.policy_id or policy_id
            await session.commit()
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "running",
                "message": "Waiting for the bill to finish extracting; the audit "
                           "will start automatically.",
                "claim_id": claim_id, "progress_pct": 3,
            })
            print(f"Claim {claim_id} is still extracting; audit deferred to that job.")
            return {"status": "deferred", "reason": "extraction_in_progress"}

        if claim.status in (ClaimStatus.FAILED, ClaimStatus.LLM_UNAVAILABLE):
            message = f"Claim is {claim.status.value}; fix the cause and re-run."
            return {"status": "error", "reason": "claim_failed", "message": message}

    # Policy ingestion runs concurrently and may still be embedding. That is
    # transient, so ask arq to redeliver rather than sleeping inside the worker.
    async with AsyncSessionLocal() as session:
        chunk_count = await session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.policy_id == policy_id
            )
        )

    if not chunk_count:
        attempt = ctx.get("job_try", 1)
        if attempt <= MAX_INDEX_WAITS:
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "running",
                "message": "Waiting for the policy to finish indexing...",
                "claim_id": claim_id, "progress_pct": 4,
            })
            print(f"Policy {policy_id} has no passages yet; redelivering (try {attempt}).")
            raise Retry(defer=attempt * 5)

        reason = ("The policy has no indexed passages, so the claim cannot be "
                  "adjudicated against it.")
        await _mark_claim(claim_id, ClaimStatus.FAILED, reason=reason)
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "error", "message": reason,
            "claim_id": claim_id, "progress_pct": 0,
        })
        return {"status": "error", "message": reason}

    # --- adjudicate ---------------------------------------------------------
    async with AsyncSessionLocal() as session:
        claim = await session.get(Claim, claim_id)
        claim.policy_id = policy_id
        await claim_state.transition(
            session, claim, ClaimStatus.AUDITING,
            detail=f"Against policy {policy_id}.",
        )
        await session.commit()

    await _publish_progress(ctx, job_id, {
        "type": "progress", "status": "started", "message": "Starting claim audit...",
        "claim_id": claim_id, "progress_pct": 5,
    })

    async with AsyncSessionLocal() as session:
        claim_items = (
            await session.execute(
                select(ClaimItem)
                .where(ClaimItem.claim_id == claim_id)
                .order_by(ClaimItem.line_number)
            )
        ).scalars().all()

        if not claim_items:
            reason = "No line items were extracted, so there is nothing to audit."
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "error", "message": reason,
                "claim_id": claim_id, "progress_pct": 0,
            })
            await _mark_claim(claim_id, ClaimStatus.FAILED, reason=reason)
            return {"status": "error", "message": reason}

        # Idempotency: clear prior verdicts so a re-run replaces rather than
        # duplicates. The unique constraint on claim_item_id rejects the second
        # insert otherwise, which is precisely why it exists.
        #
        # Issued as a bulk DELETE rather than by deleting loaded objects: the
        # unit of work is free to order object-level deletes after the inserts
        # in the same flush, which is exactly the collision being avoided.
        await session.execute(
            delete(AuditFinding).where(
                AuditFinding.claim_item_id.in_([item.id for item in claim_items])
            )
        )
        await session.flush()

        total = len(claim_items)
        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": f"Found {total} items to audit.", "progress_pct": 5,
        })

        findings = 0
        for index, item in enumerate(claim_items, start=1):
            print(f"Auditing item: {item.category} - {item.description}")
            await _publish_progress(ctx, job_id, {
                "type": "progress", "status": "running",
                "message": f"Auditing item {index}/{total}: {item.category} - {item.description}",
                "progress_pct": int(5 + (index / total) * 85),
            })

            decision = await audit_claim_item(item=item, policy_id=policy_id)

            session.add(
                AuditFinding(
                    claim_item_id=item.id,
                    chunk_id=decision.get("chunk_id"),
                    status=_coerce_status(decision.get("status")),
                    reason=decision.get("reason", "No reason provided."),
                    policy_clause_cited=decision.get("policy_clause_cited"),
                    original_clause_text=decision.get("original_clause_text"),
                    page_number=_coerce_page(decision.get("page_number")),
                    capped_amount=_coerce_float(decision.get("capped_amount")),
                    confidence=_coerce_float(decision.get("confidence")) or 0.0,
                )
            )
            findings += 1

            # Paced to stay inside the provider's rate limit.
            await asyncio.sleep(0.5)

        await session.flush()

        await _publish_progress(ctx, job_id, {
            "type": "progress", "status": "running",
            "message": "Scoring risk signals...", "progress_pct": 92,
        })
        scored = await _score_risk(session, claim_id, policy_id)

        claim = await session.get(Claim, claim_id)
        await claim_state.transition(
            session, claim, ClaimStatus.AUDIT_COMPLETE,
            summary=f"Adjudicated {findings} line item(s)",
            payload={"findings": findings, **scored},
        )
        await claim_state.record(
            session, claim,
            kind=EventKind.AI_FINDING,
            summary=f"Risk scored {scored['score']:.0f}/100 ({scored['band']})",
            detail=f"{scored['signals']} rule(s) fired.",
            payload=scored,
        )

        await session.commit()

    print(f"Audit completed for claim {claim_id}. {findings} findings saved.")
    await _publish_progress(ctx, job_id, {
        "type": "progress", "status": "completed",
        "message": (
            f"Audit complete. {findings} findings, "
            f"risk {scored['score']:.0f}/100 ({scored['band']})."
        ),
        "progress_pct": 100,
        "total_items_audited": findings,
        "risk_score": scored["score"],
        "risk_band": scored["band"],
    })

    return {"status": "success", "total_items_audited": findings, "risk": scored}


async def _score_risk(session, claim_id: str, policy_id: str) -> dict:
    """Run the rules engine and persist its signals and score.

    Previous signals and scores are cleared first: re-auditing replaces the
    assessment rather than accumulating a second copy of every rule that fired.
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

    # Same reasoning as the findings above: replace, and do it with statements
    # whose ordering relative to the inserts is not left to the unit of work.
    await session.execute(delete(RiskSignal).where(RiskSignal.claim_id == claim_id))
    await session.execute(delete(RiskScore).where(RiskScore.claim_id == claim_id))
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
