# Evaluation

Measured numbers only. Every figure here was produced by a script in this
repository, against data in this repository, and can be reproduced by running
that script. Nothing is estimated, projected, or copied from a paper.

---

## Retrieval

**What is measured.** Whether the policy clause that should settle a question is
actually retrieved, and how highly it ranks. Retrieval quality is the ceiling on
everything downstream: a clause that never surfaces cannot be cited, no matter
how good the reasoning on top of it is.

### How to reproduce

```bash
docker compose run --rm fastapi python scripts/seed.py
docker compose run --rm fastapi python evaluation/run_retrieval_eval.py
```

The harness calls `services.retrieval.search_policy` — the same function the
adjudicator uses — with its lexical and reranking stages switched on and off. It
is not a reimplementation, so the numbers describe what actually ships.

### Setup

| | |
|---|---|
| Corpus | 24 clauses of the seeded demo policy (`scripts/seed.py`) |
| Questions | 42 hand-labelled (`evaluation/retrieval_set.py`) |
| Question mix | 24 semantic paraphrase · 10 exact-reference/rare-term · 8 distractor |
| Embedding | `all-MiniLM-L6-v2`, 384-dim, cosine |
| Lexical | PostgreSQL `tsvector`, `ts_rank_cd`, OR-ed query lexemes |
| Fusion | Reciprocal rank fusion, k=60 |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2`, CPU |
| top_k | 5 |

### Results

| Configuration | recall@5 | P@1 | MRR | median | p95 |
|---|---|---|---|---|---|
| dense-only (baseline) | 0.952 | 0.786 | 0.861 | 46 ms | 72 ms |
| hybrid | 0.976 | 0.810 | 0.879 | 53 ms | 138 ms |
| **hybrid + rerank** | **1.000** | **0.905** | **0.952** | 552 ms | 809 ms |

Improvement over the baseline: recall@5 **+0.048**, P@1 **+0.119**, MRR **+0.091**.

### Recall@5 by question type

| Configuration | semantic (24) | lexical (10) | distractor (8) |
|---|---|---|---|
| dense-only | 24/24 | 8/10 | 8/8 |
| hybrid | 23/24 | **10/10** | 8/8 |
| hybrid + rerank | 24/24 | 10/10 | 8/8 |

### What the numbers say

**The lexical stage exists for the 10 questions dense retrieval could not
answer.** Exact references (`section 9.3`) and rare terms (`anaesthetist`) carry
almost no signal in a 384-dimensional average but are precise lexical matches.
Adding lexical search took that category from 8/10 to 10/10.

**Query terms are OR-ed, not AND-ed.** `websearch_to_tsquery` builds a
conjunction, so `section 9.3` required both lexemes — and excluded clause 9.3
itself, whose body never uses the word "section". This is candidate generation,
not final ranking; recall is what matters at this stage, and fusion plus the
reranker decide the order.

**Hybrid alone cost one semantic question, which the reranker recovered.**
Widening the candidate pool admits near-misses. That is the trade the reranker
is there to pay for, and it is why the two stages are reported separately rather
than as one number.

**Reranking is where precision comes from, and it costs ~10× the latency.**
P@1 rose 0.786 → 0.905 while median latency went 46 ms → 552 ms. For a
background adjudication job that is a good trade; it would not be for an
interactive search box.

### Honest limits

- **n = 42 on a 24-clause corpus.** These numbers characterise behaviour on a
  known, small corpus. They are not a benchmark result and should not be quoted
  as a general accuracy figure.
- **The questions and the policy were written by the same author.** Wording
  overlap between question and clause is plausible in a way it would not be with
  real user queries.
- **recall@5 of 1.000 means the eval no longer discriminates at k=5.** The next
  useful measurement is a larger corpus, not a better score on this one. An
  earlier version of this evaluation ran against a 6-clause corpus where
  recall@5 was near-guaranteed; the corpus was expanded specifically because
  that made the metric meaningless.
- **No groundedness or citation-correctness numbers yet.** Adjudications now
  record the `chunk_id` they relied on, which is the mechanism those metrics
  need, but the labelled set for them does not exist. Deferred rather than
  approximated.

---

## Not yet measured

Listed so their absence is explicit rather than implied.

| Area | Status |
|---|---|
| Groundedness / citation correctness | Mechanism in place (`audit_findings.chunk_id`), no labelled set |
| Adjudication accuracy | No labelled ground truth for line-item verdicts |
| Risk model | No model yet |
| OCR character accuracy | OCR path tested for function, not measured for accuracy |
| End-to-end latency | Instrumented via `/metrics`; no target agreed |
