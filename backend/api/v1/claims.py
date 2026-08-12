import uuid

from fastapi import APIRouter, File, Query, UploadFile, status

from api.deps import PaginationDep, QueueDep, SessionDep
from api.errors import DependencyUnavailableError, NotFoundError
from schemas import (
    AppealOut,
    ClaimCreated,
    ClaimDetail,
    ClaimItemOut,
    ClaimSummary,
    JobAccepted,
    Page,
    RiskScoreOut,
    RiskSignalOut,
    StartAuditRequest,
)
from services import claims as claim_service
from sqlalchemy import select

from models import AppealDocument

router = APIRouter(prefix="/claims", tags=["claims"])


@router.get(
    "",
    response_model=Page[ClaimSummary],
    summary="List claims, newest first",
)
async def list_claims(session: SessionDep, page: PaginationDep):
    items, next_cursor, has_more = await claim_service.list_claims(
        session, limit=page.limit, cursor=page.cursor
    )
    return Page[ClaimSummary](
        items=[ClaimSummary.model_validate(c) for c in items],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post(
    "",
    response_model=ClaimCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Open a claim from a hospital bill",
    description=(
        "Accepts a bill PDF, opens a claim, and queues extraction. Returns "
        "immediately; follow progress on the returned job id."
    ),
)
async def create_claim(session: SessionDep, queue: QueueDep, file: UploadFile = File(...)):
    payload = await file.read()
    claim, document = await claim_service.create_claim_from_bill(
        session, filename=file.filename, content_type=file.content_type, payload=payload
    )

    # Committed before enqueuing: a worker that picks the job up first would not
    # find the rows it needs.
    await session.commit()

    job = await queue.enqueue_job("extract_bill_task", str(claim.id), str(document.id))
    if job is None:
        raise DependencyUnavailableError("Could not queue extraction; the job queue rejected it.")

    return ClaimCreated(
        claim_id=claim.id,
        reference=claim.reference,
        document_id=document.id,
        job_id=job.job_id,
    )


@router.get(
    "/{claim_id}",
    response_model=ClaimDetail,
    summary="A claim with its line items, findings and risk breakdown",
)
async def get_claim(claim_id: uuid.UUID, session: SessionDep):
    claim = await claim_service.get_claim_detail(session, claim_id)
    risk = claim_service.latest_risk_score(claim)

    return ClaimDetail(
        id=claim.id,
        reference=claim.reference,
        status=claim.status,
        total_billed=claim.total_billed,
        total_approved=claim.total_approved,
        currency=claim.currency,
        created_at=claim.created_at,
        claimant_name=claim.claimant.full_name if claim.claimant else None,
        provider_name=claim.provider.name if claim.provider else None,
        policy_id=claim.policy_id,
        admission_date=claim.admission_date,
        discharge_date=claim.discharge_date,
        failure_reason=claim.failure_reason,
        items=[
            ClaimItemOut(
                id=item.id,
                line_number=item.line_number,
                category=item.category,
                description=item.description,
                procedure_code=item.procedure_code,
                billed_amount=item.billed_amount,
                allowed_amount=item.allowed_amount,
                audit=item.audit_finding,
            )
            for item in sorted(
                claim.items, key=lambda i: (i.line_number or 0, i.created_at)
            )
        ],
        risk=RiskScoreOut.model_validate(risk) if risk else None,
        signals=[RiskSignalOut.model_validate(s) for s in claim_service.sorted_signals(claim)],
    )


@router.post(
    "/{claim_id}/audit",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Adjudicate a claim against a policy",
)
async def start_audit(
    claim_id: uuid.UUID, body: StartAuditRequest, session: SessionDep, queue: QueueDep
):
    await claim_service.assert_auditable(session, claim_id, body.policy_id)

    job = await queue.enqueue_job("audit_claim_task", str(claim_id), str(body.policy_id))
    if job is None:
        raise DependencyUnavailableError("Could not queue the audit.")
    return JobAccepted(job_id=job.job_id)


@router.post(
    "/{claim_id}/appeal",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Draft an appeal for the disputed lines",
)
async def start_appeal(claim_id: uuid.UUID, session: SessionDep, queue: QueueDep):
    await claim_service.assert_appealable(session, claim_id)

    job = await queue.enqueue_job("generate_appeal_task", str(claim_id))
    if job is None:
        raise DependencyUnavailableError("Could not queue appeal generation.")
    return JobAccepted(job_id=job.job_id)


@router.get(
    "/{claim_id}/appeal",
    response_model=AppealOut,
    summary="Fetch the drafted appeal letter",
)
async def get_appeal(claim_id: uuid.UUID, session: SessionDep):
    appeal = (
        await session.execute(
            select(AppealDocument).where(AppealDocument.claim_id == claim_id)
        )
    ).scalars().first()

    if appeal is None:
        raise NotFoundError(
            "No appeal has been drafted for this claim yet."
        )
    return AppealOut.model_validate(appeal)
