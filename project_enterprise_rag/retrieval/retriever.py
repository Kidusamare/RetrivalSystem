from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from retrieval.scoring import (
    apply_active_filters,
    compute_keyword_overlap,
    fuse_scores,
    paginate_records,
    parse_active_filters,
    sort_chunk_records,
)


def search_chunks(
    persist_dir: Path,
    planned_query: str,
    query_terms: Optional[Sequence[str]] = None,
    active_filters: Optional[Iterable[str]] = None,
    mode: str = "hybrid",
    sort_by: str = "relevance",
    page: int = 1,
    page_size: int = 10,
) -> Dict:
    # Import lazily so unit tests for scoring can run without llama_index installed.
    from retrieval.runtime_engine import search_chunks as runtime_search_chunks

    return runtime_search_chunks(
        persist_dir=persist_dir,
        planned_query=planned_query,
        query_terms=query_terms,
        active_filters=active_filters,
        mode=mode,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )


def retrieve_chunks(
    persist_dir: Path,
    planned_query: str,
    active_filters: Optional[Iterable[str]] = None,
    top_k: int = 5,
) -> List[Dict]:
    result = search_chunks(
        persist_dir=persist_dir,
        planned_query=planned_query,
        active_filters=active_filters,
        mode="hybrid",
        sort_by="relevance",
        page=1,
        page_size=max(1, int(top_k)),
    )
    return result["chunks"]


__all__ = [
    "apply_active_filters",
    "compute_keyword_overlap",
    "fuse_scores",
    "paginate_records",
    "parse_active_filters",
    "retrieve_chunks",
    "search_chunks",
    "sort_chunk_records",
]
