import uuid

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from api.deps import QueueDep, SessionDep
from api.errors import DependencyUnavailableError
from schemas import ClauseMatch, ClauseSearchResponse, PolicyCreated, PolicySummary
from services import policies as policy_service

router = APIRouter(prefix="/policies", tags=["policies"])


@router.get("", response_model=list[PolicySummary], summary="List ingested policies")
async def list_policies(session: SessionDep):
    return [PolicySummary.model_validate(p) for p in await policy_service.list_policies(session)]


@router.post(
    "",
    response_model=PolicyCreated,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a policy document",
    description="Accepts a policy PDF and queues clause extraction and embedding.",
)
async def create_policy(
    session: SessionDep,
    queue: QueueDep,
    file: UploadFile = File(...),
    insurer_name: str = Form("Unknown"),
    policy_name: str = Form("Unknown"),
):
    payload = await file.read()
    policy, document = await policy_service.create_policy_from_upload(
        session,
        filename=file.filename,
        content_type=file.content_type,
        payload=payload,
        insurer_name=insurer_name,
        policy_name=policy_name,
    )

    await session.commit()

    job = await queue.enqueue_job("ingest_policy_task", str(policy.id), str(document.id))
    if job is None:
        raise DependencyUnavailableError("Could not queue policy ingestion.")

    return PolicyCreated(policy_id=policy.id, document_id=document.id, job_id=job.job_id)


@router.get(
    "/{policy_id}/clauses",
    response_model=ClauseSearchResponse,
    summary="Semantic search over a policy's clauses",
)
async def search_clauses(
    policy_id: uuid.UUID,
    session: SessionDep,
    q: str = Query(min_length=2, description="Natural-language question or item description."),
    top_k: int = Query(5, ge=1, le=25),
):
    # Confirms the policy exists so an unknown id is a 404 rather than an
    # empty result set that reads as "this policy has no matching clauses".
    await policy_service.get_policy(session, policy_id)

    from agents.rag_retriever import search_policy_chunks

    results = await search_policy_chunks(query=q, policy_id=str(policy_id), top_k=top_k)
    return ClauseSearchResponse(
        query=q, results=[ClauseMatch(**r) for r in results]
    )
