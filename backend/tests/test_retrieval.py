"""Retrieval: fusion arithmetic, ranking behaviour, and the search contract.

The fusion tests are pure and fast. The search tests run against the seeded
policy, so they also assert that ingestion and retrieval agree about the corpus.
"""

import pytest

from services.retrieval import RRF_K, Candidate, fuse, search_policy

pytestmark = pytest.mark.asyncio


def _candidate(id_: str, dense=None, lexical=None) -> Candidate:
    return Candidate(
        id=id_,
        section_header=f"Header {id_}",
        text_content=f"Body of {id_}",
        page_number=1,
        dense_rank=dense,
        lexical_rank=lexical,
    )


# --- fusion ----------------------------------------------------------------

async def test_fusion_rewards_agreement_between_retrievers():
    """A passage both retrievers found should outrank one only dense found."""
    dense = [_candidate("both", dense=2), _candidate("dense-only", dense=1)]
    lexical = [_candidate("both", lexical=1)]

    ranked = fuse(dense, lexical)

    assert ranked[0].id == "both"
    assert ranked[0].dense_rank == 2 and ranked[0].lexical_rank == 1


async def test_fusion_score_matches_the_rrf_formula():
    ranked = fuse([_candidate("a", dense=1)], [_candidate("a", lexical=3)])
    expected = 1.0 / (RRF_K + 1) + 1.0 / (RRF_K + 3)
    assert ranked[0].fusion_score == pytest.approx(expected)


async def test_fusion_deduplicates_and_keeps_both_ranks():
    ranked = fuse([_candidate("x", dense=4)], [_candidate("x", lexical=9)])
    assert len(ranked) == 1
    assert ranked[0].dense_rank == 4
    assert ranked[0].lexical_rank == 9


async def test_fusion_handles_an_empty_retriever():
    """Lexical search legitimately returns nothing for an all-stopword query."""
    ranked = fuse([_candidate("a", dense=1)], [])
    assert [c.id for c in ranked] == ["a"]
    assert ranked[0].fusion_score == pytest.approx(1.0 / (RRF_K + 1))


async def test_fusion_of_nothing_is_nothing():
    assert fuse([], []) == []


# --- search contract -------------------------------------------------------

@pytest.fixture
async def seeded_policy_id(session):
    from sqlalchemy import select

    from models import Policy

    policy = (
        await session.execute(
            select(Policy).where(Policy.insurer_name == "Meridian Health Assurance")
        )
    ).scalars().first()

    if policy is None:
        pytest.skip("seeded demo policy not present; run scripts/seed.py")
    return str(policy.id)


async def test_search_returns_at_most_top_k(seeded_policy_id):
    results = await search_policy(
        policy_id=seeded_policy_id, query="room rent limit", top_k=3
    )
    assert 0 < len(results) <= 3


async def test_every_result_carries_retrieval_provenance(seeded_policy_id):
    """A result must say how it surfaced, or the evaluation cannot be trusted."""
    results = await search_policy(policy_id=seeded_policy_id, query="room rent", top_k=3)

    for candidate in results:
        provenance = candidate.provenance()
        assert set(provenance) == {
            "dense_rank", "lexical_rank", "fusion_score", "rerank_score"
        }
        assert provenance["dense_rank"] or provenance["lexical_rank"], (
            "a result must have been found by at least one retriever"
        )


async def test_lexical_stage_finds_an_exact_clause_reference(seeded_policy_id):
    """The case that motivated OR-ing query terms rather than AND-ing them."""
    results = await search_policy(
        policy_id=seeded_policy_id, query="section 9.3", top_k=5, use_reranker=False
    )
    headers = [c.section_header for c in results]
    assert any(h and h.startswith("9.3") for h in headers), headers


async def test_rare_term_is_retrievable(seeded_policy_id):
    results = await search_policy(policy_id=seeded_policy_id, query="anaesthetist", top_k=5)
    headers = [c.section_header for c in results]
    assert any(h and "ANAESTHETIST" in h for h in headers), headers


async def test_unknown_policy_returns_nothing_rather_than_erroring(session):
    import uuid

    results = await search_policy(policy_id=str(uuid.uuid4()), query="room rent", top_k=5)
    assert results == []


async def test_disabling_stages_changes_the_ranking(seeded_policy_id):
    """The evaluation's switches must actually switch something."""
    query = "Private duty nurse charges"

    dense_only = await search_policy(
        policy_id=seeded_policy_id, query=query, top_k=5,
        use_lexical=False, use_reranker=False,
    )
    full = await search_policy(policy_id=seeded_policy_id, query=query, top_k=5)

    assert dense_only and full
    assert full[0].rerank_score is not None
    assert dense_only[0].rerank_score is None
