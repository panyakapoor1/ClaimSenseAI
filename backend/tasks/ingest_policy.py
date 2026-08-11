from sqlalchemy import text
from sqlalchemy.future import select
from core.database import AsyncSessionLocal
from models.policy import Policy, PolicyChunk
from agents.policy_ingestor import extract_policy_text, generate_embeddings
import os


async def ingest_policy_task(ctx, policy_id: str, pdf_path: str):
    """Background task: Extract text from policy PDF, generate embeddings, and store chunks."""
    print(f"Starting policy ingestion for policy {policy_id}")

    try:
        import asyncio
        # 1. Extract and chunk the PDF text
        chunks = await asyncio.to_thread(extract_policy_text, pdf_path)
        print(f"Extracted {len(chunks)} chunks from policy PDF")

        if not chunks:
            print(f"No meaningful text extracted from {pdf_path}")
            return {"status": "failed", "error": "No text extracted from PDF"}

        # 2. Generate embeddings for all chunks in a single batch
        texts = [c["text_content"] for c in chunks]
        embeddings = await asyncio.to_thread(generate_embeddings, texts)
        print(f"Generated {len(embeddings)} embeddings (dim={len(embeddings[0])})")

        # 3. Store chunks + embeddings in PostgreSQL via pgvector
        async with AsyncSessionLocal() as session:
            # Verify the policy exists
            result = await session.execute(
                select(Policy).where(Policy.id == policy_id)
            )
            policy = result.scalars().first()

            if not policy:
                print(f"Policy {policy_id} not found.")
                return {"status": "failed", "error": "Policy not found"}

            for chunk_data, embedding in zip(chunks, embeddings):
                chunk = PolicyChunk(
                    policy_id=policy.id,
                    page_number=chunk_data["page_number"],
                    section_header=chunk_data["section_header"],
                    text_content=chunk_data["text_content"],
                    embedding=embedding
                )
                session.add(chunk)

            await session.commit()

        print(f"Policy {policy_id} ingested successfully. Stored {len(chunks)} chunks with embeddings.")

    except Exception as e:
        print(f"Policy ingestion failed: {e}")
        return {"status": "failed", "error": str(e)}

    # Cleanup uploaded file
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    return {"status": "success", "total_chunks": len(chunks)}
