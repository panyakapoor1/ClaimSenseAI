"""Hybrid retrieval: dense + lexical, fused, then reranked.

The prototype took the top 3 nearest embeddings and passed them to the LLM. That
fails in two ways that matter for policy text:

  * **Lexical precision.** "Clause 4.1" and "cholecystectomy" are near-invisible
    to a 384-dimensional average but are exact lexical matches.
  * **Ranking.** A bi-encoder scores query and passage independently. A
    cross-encoder reads them together and is far better at deciding which of
    several plausible clauses actually answers the question — which is precisely
    the top-1 decision an adjudication rests on.

So: retrieve widely from both sides, fuse, then spend the expensive model only
on the shortlist.
"""

import asyncio
import logging
import threading
from dataclasses import dataclass, field

from sqlalchemy import text

from core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Cross-encoder. Small, CPU-friendly, and trained for exactly this reranking job.
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# How many to pull from each retriever before fusing. Wider than the final k so
# fusion has something to work with; a passage missing from both candidate lists
# can never be recovered by reranking.
CANDIDATE_DEPTH = 25

# Reciprocal-rank-fusion damping. 60 is the value from the original RRF paper and
# is deliberately large: it flattens the curve so a passage ranked 1st by one
# retriever does not automatically beat one ranked 2nd by both.
RRF_K = 60

_reranker = None
_reranker_lock = threading.Lock()


@dataclass
class Candidate:
    id: str
    section_header: str | None
    text_content: str
    page_number: int | None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fusion_score: float = 0.0
    rerank_score: float | None = None
    similarity: float = 0.0

    def provenance(self) -> dict:
        """Why this passage surfaced — shown in evaluation and debugging."""
        return {
            "dense_rank": self.dense_rank,
            "lexical_rank": self.lexical_rank,
            "fusion_score": round(self.fusion_score, 5),
            "rerank_score": None if self.rerank_score is None else round(self.rerank_score, 4),
        }

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "section_header": self.section_header,
            "text_content": self.text_content,
            "page_number": self.page_number,
            "similarity": round(self.similarity, 4),
            "retrieval": self.provenance(),
        }


def _load_reranker():
    """Load the cross-encoder once, on first use.

    Returns None if it cannot be loaded — retrieval then falls back to fusion
    order rather than failing. A degraded ranking is still a useful ranking.
    """
    global _reranker
    with _reranker_lock:
        if _reranker is None:
            try:
                from sentence_transformers import CrossEncoder

                logger.info("Loading reranker %s", RERANKER_MODEL)
                _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
                logger.info("Reranker ready.")
            except Exception as e:
                logger.warning("Reranker unavailable (%s); using fusion order.", e)
                _reranker = False
    return _reranker or None


async def _dense_candidates(policy_id: str, query: str, depth: int) -> list[Candidate]:
    from agents.policy_ingestor import generate_embeddings

    embedding = (await asyncio.to_thread(generate_embeddings, [query]))[0]

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT id, section_header, text_content, page_number,
                           1 - (embedding <=> :embedding) AS similarity
                    FROM document_chunks
                    WHERE policy_id = :policy_id AND embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding
                    LIMIT :depth
                    """
                ),
                {"embedding": str(embedding), "policy_id": policy_id, "depth": depth},
            )
        ).fetchall()

    return [
        Candidate(
            id=str(r[0]),
            section_header=r[1],
            text_content=r[2],
            page_number=r[3],
            dense_rank=rank,
            similarity=float(r[4]),
        )
        for rank, r in enumerate(rows, start=1)
    ]


async def _lexical_candidates(policy_id: str, query: str, depth: int) -> list[Candidate]:
    """BM25-style ranking over the generated tsvector column.

    Terms are OR-ed, not AND-ed. `websearch_to_tsquery` builds a conjunction, so
    "section 9.3" required both lexemes and therefore excluded clause 9.3 itself
    — whose body never uses the word "section". This is candidate generation, not
    final ranking: recall matters here, and fusion plus the cross-encoder decide
    the order afterwards.

    The query is lexed with `to_tsvector` first so stemming and stop-word removal
    match how the column was built, and so punctuation in a real item description
    cannot produce a tsquery syntax error. An all-stopword query yields NULL,
    which matches nothing rather than raising.
    """
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    WITH parsed AS (
                        SELECT to_tsquery(
                            'english',
                            NULLIF(
                                array_to_string(
                                    tsvector_to_array(to_tsvector('english', :q)), ' | '
                                ), ''
                            )
                        ) AS query
                    )
                    SELECT c.id, c.section_header, c.text_content, c.page_number,
                           ts_rank_cd(c.text_search, parsed.query) AS rank
                    FROM document_chunks c, parsed
                    WHERE c.policy_id = :policy_id
                      AND c.text_search @@ parsed.query
                    ORDER BY rank DESC
                    LIMIT :depth
                    """
                ),
                {"q": query, "policy_id": policy_id, "depth": depth},
            )
        ).fetchall()

    return [
        Candidate(
            id=str(r[0]),
            section_header=r[1],
            text_content=r[2],
            page_number=r[3],
            lexical_rank=rank,
        )
        for rank, r in enumerate(rows, start=1)
    ]


def fuse(dense: list[Candidate], lexical: list[Candidate]) -> list[Candidate]:
    """Reciprocal rank fusion.

    Combines by rank rather than score, because the two retrievers' scores are
    not comparable — cosine similarity and ts_rank_cd live on different scales,
    and normalising them would be inventing a relationship that does not exist.
    """
    merged: dict[str, Candidate] = {}

    for candidate in dense + lexical:
        existing = merged.get(candidate.id)
        if existing is None:
            merged[candidate.id] = candidate
        else:
            # Same passage from both retrievers: keep both ranks.
            existing.dense_rank = existing.dense_rank or candidate.dense_rank
            existing.lexical_rank = existing.lexical_rank or candidate.lexical_rank
            existing.similarity = max(existing.similarity, candidate.similarity)

    for candidate in merged.values():
        score = 0.0
        if candidate.dense_rank:
            score += 1.0 / (RRF_K + candidate.dense_rank)
        if candidate.lexical_rank:
            score += 1.0 / (RRF_K + candidate.lexical_rank)
        candidate.fusion_score = score

    return sorted(merged.values(), key=lambda c: c.fusion_score, reverse=True)


def rerank(query: str, candidates: list[Candidate]) -> list[Candidate]:
    """Reorder the shortlist with a cross-encoder, if one is available."""
    model = _load_reranker()
    if model is None or not candidates:
        return candidates

    pairs = [
        (query, f"{c.section_header or ''}\n{c.text_content}".strip())
        for c in candidates
    ]
    try:
        scores = model.predict(pairs)
    except Exception as e:
        logger.warning("Reranking failed (%s); using fusion order.", e)
        return candidates

    for candidate, score in zip(candidates, scores):
        candidate.rerank_score = float(score)

    return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


async def search_policy(
    *,
    policy_id: str,
    query: str,
    top_k: int = 5,
    use_lexical: bool = True,
    use_reranker: bool = True,
    depth: int = CANDIDATE_DEPTH,
) -> list[Candidate]:
    """Retrieve the passages most likely to settle `query` for this policy.

    The `use_lexical` and `use_reranker` switches exist so the evaluation harness
    can measure each stage against the dense-only baseline using this exact code
    path, rather than a reimplementation that might not match.
    """
    dense = await _dense_candidates(policy_id, query, depth)
    lexical = await _lexical_candidates(policy_id, query, depth) if use_lexical else []

    fused = fuse(dense, lexical)

    if use_reranker:
        # Reranking is quadratic in nothing but linear in candidates, and each
        # pair is a full transformer pass — so it runs on the shortlist only.
        shortlist = fused[: max(top_k * 3, 10)]
        shortlist = await asyncio.to_thread(rerank, query, shortlist)
        return shortlist[:top_k]

    return fused[:top_k]


async def search_policy_chunks(query: str, policy_id: str, top_k: int = 5) -> list[dict]:
    """Backwards-compatible shape for existing callers."""
    results = await search_policy(policy_id=policy_id, query=query, top_k=top_k)
    return [c.as_dict() for c in results]
