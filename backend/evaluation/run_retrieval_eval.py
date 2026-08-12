"""Measure retrieval configurations against the labelled set.

Runs the same `services.retrieval.search_policy` the application uses, with the
lexical and reranking stages switched on and off, so the comparison describes
what actually ships rather than a parallel implementation.

    docker compose run --rm fastapi python evaluation/run_retrieval_eval.py

Reports, for each configuration:
  recall@k     — share of questions whose correct clause appeared in the top k
  precision@1  — share whose top result was correct
  MRR          — mean reciprocal rank of the first correct result
  latency      — median and p95 per query

Recall@k is the ceiling on everything downstream: a clause that never surfaces
cannot be cited, no matter how good the reasoning is.
"""

import asyncio
import json
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from core.database import AsyncSessionLocal
from evaluation.retrieval_set import CASES
from models import Policy
from services.retrieval import search_policy

TOP_K = 5

CONFIGURATIONS = [
    ("dense-only (baseline)", {"use_lexical": False, "use_reranker": False}),
    ("hybrid", {"use_lexical": True, "use_reranker": False}),
    ("hybrid + rerank", {"use_lexical": True, "use_reranker": True}),
]


async def _seeded_policy_id() -> str | None:
    async with AsyncSessionLocal() as session:
        policy = (
            await session.execute(
                select(Policy).where(Policy.insurer_name == "Meridian Health Assurance")
            )
        ).scalars().first()
        return str(policy.id) if policy else None


def _rank_of_first_relevant(results, relevant: list[str]) -> int | None:
    for position, candidate in enumerate(results, start=1):
        if candidate.section_header in relevant:
            return position
    return None


async def evaluate(policy_id: str, label: str, options: dict) -> dict:
    hits_at_k = 0
    hits_at_1 = 0
    reciprocal_ranks: list[float] = []
    latencies: list[float] = []
    failures: list[dict] = []

    for case in CASES:
        started = time.perf_counter()
        results = await search_policy(
            policy_id=policy_id, query=case.query, top_k=TOP_K, **options
        )
        latencies.append(time.perf_counter() - started)

        rank = _rank_of_first_relevant(results, case.relevant)

        if rank is not None:
            hits_at_k += 1
            reciprocal_ranks.append(1.0 / rank)
            if rank == 1:
                hits_at_1 += 1
        else:
            reciprocal_ranks.append(0.0)
            failures.append({
                "query": case.query,
                "kind": case.kind,
                "expected": case.relevant,
                "got": [c.section_header for c in results[:3]],
            })

    total = len(CASES)
    latencies.sort()

    return {
        "configuration": label,
        "n": total,
        "recall_at_k": hits_at_k / total,
        "precision_at_1": hits_at_1 / total,
        "mrr": statistics.mean(reciprocal_ranks),
        "median_latency_ms": statistics.median(latencies) * 1000,
        "p95_latency_ms": latencies[int(len(latencies) * 0.95) - 1] * 1000,
        "misses": failures,
    }


def _by_kind(results_by_config: dict[str, list[dict]]) -> None:
    """Break the score down by question type.

    An aggregate can hide the thing worth knowing: if hybrid only helps lexical
    questions, that is a more useful finding than a single averaged number.
    """
    kinds = sorted({c.kind for c in CASES})
    print("\nRecall@%d by question type" % TOP_K)
    print(f"  {'configuration':<24}" + "".join(f"{k:>14}" for k in kinds))

    for label, per_case in results_by_config.items():
        row = f"  {label:<24}"
        for kind in kinds:
            subset = [r for r in per_case if r["kind"] == kind]
            hit = sum(1 for r in subset if r["rank"] is not None)
            row += f"{hit}/{len(subset):<12}"
        print(row)


async def main() -> int:
    policy_id = await _seeded_policy_id()
    if not policy_id:
        print(
            "The seeded demo policy is not present. Run:\n"
            "  docker compose run --rm fastapi python scripts/seed.py",
            file=sys.stderr,
        )
        return 1

    print(f"Evaluating retrieval over {len(CASES)} labelled questions (top_k={TOP_K})\n")

    reports = []
    per_config_cases: dict[str, list[dict]] = {}

    for label, options in CONFIGURATIONS:
        # Per-case detail, for the breakdown by question type.
        cases = []
        for case in CASES:
            results = await search_policy(
                policy_id=policy_id, query=case.query, top_k=TOP_K, **options
            )
            cases.append({
                "kind": case.kind,
                "rank": _rank_of_first_relevant(results, case.relevant),
            })
        per_config_cases[label] = cases

        report = await evaluate(policy_id, label, options)
        reports.append(report)

        print(
            f"{report['configuration']:<24} "
            f"recall@{TOP_K} {report['recall_at_k']:.3f}   "
            f"P@1 {report['precision_at_1']:.3f}   "
            f"MRR {report['mrr']:.3f}   "
            f"median {report['median_latency_ms']:.0f}ms   "
            f"p95 {report['p95_latency_ms']:.0f}ms"
        )

    _by_kind(per_config_cases)

    baseline, final = reports[0], reports[-1]
    print("\nAgainst the dense-only baseline:")
    for metric in ("recall_at_k", "precision_at_1", "mrr"):
        delta = final[metric] - baseline[metric]
        print(f"  {metric:<16} {baseline[metric]:.3f} -> {final[metric]:.3f}  ({delta:+.3f})")

    if final["misses"]:
        print(f"\nRemaining misses ({len(final['misses'])}):")
        for miss in final["misses"]:
            print(f"  [{miss['kind']}] {miss['query']}")
            print(f"      expected {miss['expected']}, got {miss['got']}")

    out = pathlib.Path(__file__).parent / "results" / "retrieval.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"\nWritten to {out}")

    improved = (
        final["recall_at_k"] >= baseline["recall_at_k"]
        and final["mrr"] > baseline["mrr"]
    )
    print(
        "\nGATE: hybrid + rerank beats dense-only"
        if improved
        else "\nGATE FAILED: no improvement over the baseline"
    )
    return 0 if improved else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
