import asyncio
import os

from sqlalchemy.future import select

from agents.policy_ingestor import extract_policy_text, generate_embeddings
from core.database import AsyncSessionLocal
from models import Document, DocumentChunk, DocumentStatus, Policy


async def ingest_policy_task(ctx, policy_id: str, document_id: str):
    """Parse a policy PDF into retrievable, embedded chunks.

    Takes a document id rather than a filesystem path: the path now lives on the
    Document row, so the task does not need to know how documents are stored and
    keeps working when P4 moves them to object storage.
    """
    print(f"Starting policy ingestion for policy {policy_id}")

    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            print(f"Document {document_id} not found.")
            return {"status": "failed", "error": "Document not found"}

        pdf_path = document.storage_key
        document.status = DocumentStatus.PARSING
        await session.commit()

    try:
        chunks = await asyncio.to_thread(extract_policy_text, pdf_path)
        print(f"Extracted {len(chunks)} chunks from policy PDF")

        if not chunks:
            await _mark_document_failed(document_id, "No text could be extracted from the PDF.")
            return {"status": "failed", "error": "No text extracted from PDF"}

        texts = [c["text_content"] for c in chunks]
        embeddings = await asyncio.to_thread(generate_embeddings, texts)
        print(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")

        async with AsyncSessionLocal() as session:
            policy = (
                await session.execute(select(Policy).where(Policy.id == policy_id))
            ).scalars().first()

            if not policy:
                print(f"Policy {policy_id} not found.")
                return {"status": "failed", "error": "Policy not found"}

            pages = set()
            for ordinal, (chunk_data, embedding) in enumerate(zip(chunks, embeddings)):
                page_number = _as_int(chunk_data.get("page_number"))
                if page_number is not None:
                    pages.add(page_number)

                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        policy_id=policy.id,
                        ordinal=ordinal,
                        page_number=page_number,
                        section_header=chunk_data.get("section_header"),
                        text_content=chunk_data["text_content"],
                        embedding=embedding,
                    )
                )

            document = await session.get(Document, document_id)
            document.status = DocumentStatus.PARSED
            document.page_count = max(pages) if pages else None

            await session.commit()

        print(f"Policy {policy_id} ingested. Stored {len(chunks)} chunks with embeddings.")

    except Exception as e:
        print(f"Policy ingestion failed: {e}")
        await _mark_document_failed(document_id, str(e))
        return {"status": "failed", "error": str(e)}

    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    return {"status": "success", "total_chunks": len(chunks)}


def _as_int(value) -> int | None:
    """Page numbers arrive from the extractor as strings; the column is an int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
