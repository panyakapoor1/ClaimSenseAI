from sqlalchemy.future import select
from sqlalchemy import text
from core.database import AsyncSessionLocal
from models.policy import PolicyChunk
from agents.policy_ingestor import generate_embeddings


async def search_policy_chunks(query: str, policy_id: str, top_k: int = 5) -> list[dict]:
    """
    Perform a semantic similarity search against policy chunks using pgvector.
    
    This is the core RAG retrieval function. It:
    1. Converts the user's query into a 384-dim embedding.
    2. Uses pgvector's cosine distance operator (<=>) to find the most relevant policy clauses.
    3. Returns the top-k most similar chunks with their similarity scores.
    """
    # Generate embedding for the search query
    query_embedding = generate_embeddings([query])[0]

    async with AsyncSessionLocal() as session:
        # pgvector cosine distance search
        # The <=> operator computes cosine distance (0 = identical, 2 = opposite)
        result = await session.execute(
            text("""
                SELECT 
                    id,
                    section_header,
                    text_content,
                    page_number,
                    1 - (embedding <=> :query_embedding) AS similarity
                FROM policy_chunks
                WHERE policy_id = :policy_id
                ORDER BY embedding <=> :query_embedding
                LIMIT :top_k
            """),
            {
                "query_embedding": str(query_embedding),
                "policy_id": policy_id,
                "top_k": top_k
            }
        )

        rows = result.fetchall()

    return [
        {
            "id": str(row[0]),
            "section_header": row[1],
            "text_content": row[2],
            "page_number": row[3],
            "similarity": round(float(row[4]), 4)
        }
        for row in rows
    ]
