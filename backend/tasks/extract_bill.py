import asyncio
import datetime

from sqlalchemy.future import select

from agents.bill_extractor import extract_bill_data
from agents.document_parser import chunk_document, document_text, parse_pdf
from agents.fact_locator import locate_amount, locate_text
from core.database import AsyncSessionLocal
from core.llm import LLMUnavailableError
from models import (
    Claim,
    ClaimItem,
    ClaimStatus,
    Document,
    DocumentChunk,
    DocumentPage,
    DocumentStatus,
    ExtractedFact,
    FactKind,
)
from services import storage
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
                "claim_id": claim_id, "progress_pct": 0,
            })
            return {"status": "failed", "error": "Document not found"}
        storage_key = document.storage_key
        document.status = DocumentStatus.PARSING
        await session.commit()

    await mark_claim(claim_id, ClaimStatus.EXTRACTING)
    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "started",
        "message": "Reading the medical bill...",
        "claim_id": claim_id, "progress_pct": 5,
    })

    # --- parse (with OCR fallback) -----------------------------------------
    try:
        payload = await asyncio.to_thread(storage.get, storage_key)
        pages = await asyncio.to_thread(parse_pdf, payload)
        passages = await asyncio.to_thread(chunk_document, pages)
    except Exception as e:
        print(f"Parsing failed: {e}")
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": f"Could not read the document: {e}",
            "claim_id": claim_id, "progress_pct": 0,
        })
        await mark_claim(claim_id, ClaimStatus.FAILED, reason=str(e))
        return {"status": "failed", "error": str(e)}

    ocr_pages = sum(1 for p in pages if p.from_ocr)
    text = document_text(pages)

    if not text.strip():
        reason = (
            "No readable text was found in this document, even after OCR. "
            "It may be blank, encrypted, or an unsupported image format."
        )
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error", "message": reason,
            "claim_id": claim_id, "progress_pct": 0,
        })
        await mark_claim(claim_id, ClaimStatus.FAILED, reason=reason)
        return {"status": "failed", "error": reason}

    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "running",
        "message": (
            f"Read {len(pages)} page(s)"
            + (f", {ocr_pages} via OCR" if ocr_pages else "")
            + ". Extracting line items..."
        ),
        "claim_id": claim_id, "progress_pct": 35,
    })

    # --- extract structure --------------------------------------------------
    try:
        bill_data = await extract_bill_data(text)
    except LLMUnavailableError as e:
        print(f"Extraction aborted: {e}")
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error", "message": str(e),
            "claim_id": claim_id, "progress_pct": 0,
        })
        await mark_claim(claim_id, ClaimStatus.LLM_UNAVAILABLE, reason=str(e))
        return {"status": "failed", "reason": "llm_unavailable", "error": str(e)}
    except Exception as e:
        print(f"Extraction failed: {e}")
        await publish_progress(ctx, job_id, {
            "type": "progress", "status": "error",
            "message": f"Bill extraction failed: {e}",
            "claim_id": claim_id, "progress_pct": 0,
        })
        await mark_claim(claim_id, ClaimStatus.FAILED, reason=str(e))
        return {"status": "failed", "error": str(e)}

    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "running",
        "message": "Locating each charge on the page...",
        "claim_id": claim_id, "progress_pct": 70,
    })

    # --- persist, with provenance ------------------------------------------
    items = bill_data.get("items", []) or []
    facts_located = 0

    async with AsyncSessionLocal() as session:
        claim = (
            await session.execute(select(Claim).where(Claim.id == claim_id))
        ).scalars().first()

        if not claim:
            await publish_progress(ctx, job_id, {
                "type": "progress", "status": "error", "message": "Claim not found.",
                "claim_id": claim_id, "progress_pct": 0,
            })
            return {"status": "failed", "error": "Claim not found"}

        claim.total_billed = float(bill_data.get("total_billed") or 0.0)
        claim.admission_date = _as_date(bill_data.get("admission_date"))
        claim.discharge_date = _as_date(bill_data.get("discharge_date"))
        claim.status = ClaimStatus.EXTRACTED

        for page in pages:
            session.add(
                DocumentPage(
                    document_id=document_id,
                    page_number=page.page_number,
                    text_content=page.text,
                    width=page.width,
                    height=page.height,
                    from_ocr=page.from_ocr,
                )
            )

        chunk_by_page: dict[int, DocumentChunk] = {}
        for passage in passages:
            bbox = passage.bbox
            chunk = DocumentChunk(
                document_id=document_id,
                ordinal=passage.ordinal,
                page_number=passage.page_number,
                section_header=passage.section_header,
                text_content=passage.text,
                bbox_x0=bbox[0] if bbox else None,
                bbox_y0=bbox[1] if bbox else None,
                bbox_x1=bbox[2] if bbox else None,
                bbox_y1=bbox[3] if bbox else None,
            )
            session.add(chunk)
            chunk_by_page.setdefault(passage.page_number, chunk)

        await session.flush()

        for line_number, item in enumerate(items, start=1):
            description = (item.get("description") or "").strip()
            billed = float(item.get("billed_amount") or 0.0)

            session.add(
                ClaimItem(
                    claim_id=claim.id,
                    line_number=line_number,
                    category=item.get("category") or "Other",
                    description=description,
                    procedure_code=item.get("procedure_code"),
                    quantity=_as_float(item.get("quantity")),
                    unit_price=_as_float(item.get("unit_price")),
                    billed_amount=billed,
                    service_date=_as_date(item.get("service_date")),
                )
            )

            # Locate the charge on the page. A fact that cannot be found keeps a
            # lower confidence and no box, rather than being given a guessed one.
            located = locate_amount(pages, billed) or locate_text(pages, description)
            if located:
                facts_located += 1

            session.add(
                ExtractedFact(
                    claim_id=claim.id,
                    document_id=document_id,
                    chunk_id=chunk_by_page.get(located.page_number).id if located and chunk_by_page.get(located.page_number) else None,
                    kind=FactKind.AMOUNT,
                    label=description or f"Line {line_number}",
                    value_text=description,
                    value_number=billed,
                    value_date=item.get("service_date"),
                    page_number=located.page_number if located else None,
                    confidence=0.9 if located else 0.4,
                    extra={
                        "line_number": line_number,
                        "category": item.get("category"),
                        "bbox": list(located.bbox) if located else None,
                        "located": bool(located),
                    },
                )
            )

        for label, kind, value in [
            ("Provider", FactKind.PROVIDER, bill_data.get("provider_name")),
            ("Claimant", FactKind.PERSON, bill_data.get("claimant_name")),
        ]:
            if not value:
                continue
            located = locate_text(pages, str(value))
            session.add(
                ExtractedFact(
                    claim_id=claim.id,
                    document_id=document_id,
                    kind=kind,
                    label=label,
                    value_text=str(value),
                    page_number=located.page_number if located else None,
                    confidence=0.9 if located else 0.4,
                    extra={"bbox": list(located.bbox) if located else None,
                           "located": bool(located)},
                )
            )

        document = await session.get(Document, document_id)
        if document:
            document.status = DocumentStatus.PARSED
            document.page_count = len(pages)

        await session.commit()

    print(
        f"Claim {claim_id} extracted: {len(items)} items, "
        f"{facts_located}/{len(items)} located on the page."
    )
    await publish_progress(ctx, job_id, {
        "type": "progress", "status": "completed",
        "message": (
            f"Extraction complete. {len(items)} line items"
            + (f", {ocr_pages} page(s) read via OCR" if ocr_pages else "")
            + "."
        ),
        "claim_id": claim_id, "progress_pct": 100,
        "total_items": len(items), "ocr_pages": ocr_pages,
    })
    return {
        "status": "success",
        "total_items": len(items),
        "located": facts_located,
        "ocr_pages": ocr_pages,
    }


def _as_date(value) -> datetime.date | None:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
