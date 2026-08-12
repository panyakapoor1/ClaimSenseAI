"""Deprecated shim.

Retrieval moved to `services.retrieval`, which does hybrid search and reranking.
This module remains so that any older import keeps working, and forwards rather
than duplicating the logic — two retrieval implementations would inevitably
diverge and the evaluation numbers would stop describing what actually runs.
"""

from services.retrieval import search_policy_chunks

__all__ = ["search_policy_chunks"]
