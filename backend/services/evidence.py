"""Assembling the evidence behind a claim."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import Document, DocumentPage, ExtractedFact


async def documents_for_claim(
    session: AsyncSession, claim_id: uuid.UUID
) -> list[Document]:
    return list(
        (
            await session.execute(
                select(Document)
                .options(selectinload(Document.pages))
                .where(Document.claim_id == claim_id)
                .order_by(Document.created_at)
            )
        )
        .scalars()
        .all()
    )


async def facts_for_claim(
    session: AsyncSession, claim_id: uuid.UUID
) -> list[ExtractedFact]:
    """Facts ordered so the located, high-confidence ones read first."""
    return list(
        (
            await session.execute(
                select(ExtractedFact)
                .where(ExtractedFact.claim_id == claim_id)
                .order_by(ExtractedFact.confidence.desc(), ExtractedFact.created_at)
            )
        )
        .scalars()
        .all()
    )


def region_for(fact: ExtractedFact) -> dict | None:
    """The highlight rectangle recorded when the value was located."""
    extra = fact.extra or {}
    bbox = extra.get("bbox")
    if not bbox or fact.page_number is None or len(bbox) != 4:
        return None
    return {
        "page_number": fact.page_number,
        "x0": bbox[0],
        "y0": bbox[1],
        "x1": bbox[2],
        "y1": bbox[3],
    }
