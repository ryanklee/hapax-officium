"""shared/knowledge_search.py — Qdrant semantic search & knowledge artifact reads.

Reusable by query agents, demo pipeline, or any consumer needing
semantic search over Qdrant collections and access to knowledge artifacts.
No pydantic-ai dependency.
"""

from __future__ import annotations

import logging

from shared.profile_store import ProfileStore

log = logging.getLogger("shared.knowledge_search")


def search_profile(
    query: str,
    *,
    dimension: str | None = None,
    limit: int = 5,
) -> str:
    """Semantic search over operator profile facts."""
    try:
        store = ProfileStore()
        results = store.search(query, dimension=dimension, limit=limit)
    except Exception as e:
        return f"Profile search error: {e}"

    if not results:
        dim_note = f" in dimension '{dimension}'" if dimension else ""
        return f"No profile facts found matching '{query}'{dim_note}."

    lines = [f"Found {len(results)} profile facts:", ""]
    for r in results:
        lines.append(
            f"- [{r['dimension']}/{r['key']}] {r['value']} "
            f"(confidence: {r['confidence']:.2f}, score: {r['score']:.2f})"
        )

    return "\n".join(lines)
