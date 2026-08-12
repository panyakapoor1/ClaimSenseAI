import asyncio

from sqlalchemy.future import select

from agents.document_parser import chunk_document, parse_pdf
from agents.policy_ingestor import generate_embeddings
from core.database import AsyncSessionLocal
from models import Document, DocumentChunk, DocumentPage, DocumentStatus, Policy
from services import storage


async def ingest_policy_task(ctx, policy_id: str, document_id: str):
    """Parse a policy PDF into pages and retrievable, embedded passages.

    Pages are persisted alongside the passages so a citation can be shown in the
    context of the page it came from, rather than as a floating quotation.
    """
    print(f"Starting policy ingestion for policy {policy_id}")

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            print(f"Document {document_id} not found.")
            return {"status": "failed", "error": "Document not found"}

        storage_key = document.storage_key
        document.status = DocumentStatus.PARSING
        await session.commit()

    try:
        payload = await asyncio.to_thread(storage.get, storage_key)

        # Parsing is CPU-bound and OCR especially so; keep it off the event loop
        # or the worker's Redis heartbeat starves and the job is killed mid-run.
        pages = await asyncio.to_thread(parse_pdf, payload)
        passages = await asyncio.to_thread(chunk_document, pages)

        ocr_pages = sum(1 for p in pages if p.from_ocr)
        print(
            f"Parsed {len(pages)} page(s) into {len(passages)} passage(s); "
            f"{ocr_pages} page(s) required OCR"
        )

        if not passages:
            await _mark_document_failed(
                document_id,
                "No readable text was found, even after OCR. The file may be blank "
                "or an unsupported image format.",
            )
            return {"status": "failed", "error": "No text extracted"}

        texts = [p.text for p in passages]
        embeddings = await asyncio.to_thread(generate_embeddings, texts)

        async with AsyncSessionLocal() as session:
            policy = (
                await session.execute(select(Policy).where(Policy.id == policy_id))
            ).scalars().first()
            if not policy:
                print(f"Policy {policy_id} not found.")
                return {"status": "failed", "error": "Policy not found"}

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

            for passage, embedding in zip(passages, embeddings):
                bbox = passage.bbox
                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        policy_id=policy.id,
                        ordinal=passage.ordinal,
                        page_number=passage.page_number,
                        section_header=passage.section_header,
                        text_content=passage.text,
                        bbox_x0=bbox[0] if bbox else None,
                        bbox_y0=bbox[1] if bbox else None,
                        bbox_x1=bbox[2] if bbox else None,
                        bbox_y1=bbox[3] if bbox else None,
                        embedding=embedding,
                    )
                )

            document = await session.get(Document, document_id)
            document.status = DocumentStatus.PARSED
            document.page_count = len(pages)

            await session.commit()

        print(f"Policy {policy_id} ingested: {len(passages)} passages stored.")

    except Exception as e:
        print(f"Policy ingestion failed: {e}")
        await _mark_document_failed(document_id, str(e))
        return {"status": "failed", "error": str(e)}

    return {
        "status": "success",
        "total_chunks": len(passages),
        "pages": len(pages),
        "ocr_pages": ocr_pages,
    }


async def _mark_document_failed(document_id: str, reason: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            document = await session.get(Document, document_id)
            if document:
                document.status = DocumentStatus.FAILED
                document.parse_error = reason
                await session.commit()
    except Exception as e:
        print(f"Warning: could not mark document {document_id} as FAILED: {e}")
