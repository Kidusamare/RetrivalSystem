from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from llama_index.core import Settings, StorageContext, load_index_from_storage

from ingestion.index_builder import get_local_embed_model
from retrieval.filter_suggester import build_facets
from retrieval.query_planner import extract_keywords
from retrieval.scoring import (
    apply_active_filters,
    compute_keyword_overlap,
    extract_date_value,
    fuse_scores,
    node_key,
    normalize_semantic_scores,
    paginate_records,
    parse_active_filters,
    record_passes_structured_filters,
    resolve_source,
    sort_chunk_records,
)


def _record_from_node(node, semantic_score_raw: float, query_terms: Sequence[str]) -> Dict:
    metadata = dict(getattr(node, "metadata", {}) or {})
    text = node.get_content() if hasattr(node, "get_content") else str(node)
    keyword_overlap, matched_terms = compute_keyword_overlap(text=text, query_terms=query_terms)
    date_value, date_ts = extract_date_value(metadata)

    return {
        "source": resolve_source(metadata),
        "page": metadata.get("page") or metadata.get("page_label") or "N/A",
        "date": date_value,
        "date_ts": date_ts,
        "doc_id": metadata.get("doc_id", "unknown"),
        "chunk_id": metadata.get("chunk_id", "unknown"),
        "text": text,
        "metadata": metadata,
        "semantic_score_raw": float(semantic_score_raw or 0.0),
        "keyword_overlap": keyword_overlap,
        "matched_terms": matched_terms,
        "record_key": node_key(metadata=metadata, text=text),
    }


def _load_all_nodes(index) -> List:
    docs = getattr(index.storage_context.docstore, "docs", {})
    nodes = []
    for node in docs.values():
        if hasattr(node, "get_content"):
            content = node.get_content()
            if content:
                nodes.append(node)
    return nodes


def _semantic_candidates(index, query_text: str, candidate_k: int) -> List[Dict]:
    retriever = index.as_retriever(similarity_top_k=max(1, candidate_k))
    nodes = retriever.retrieve(query_text)
    results: List[Dict] = []
    for item in nodes:
        node = getattr(item, "node", item)
        score = float(getattr(item, "score", 0.0) or 0.0)
        results.append({"node": node, "semantic_score_raw": score})
    return results


def _keyword_candidates(all_nodes: List, query_terms: Sequence[str], min_overlap: float = 0.0) -> List[Dict]:
    results: List[Dict] = []
    for node in all_nodes:
        text = node.get_content() if hasattr(node, "get_content") else ""
        overlap, _matched = compute_keyword_overlap(text=text, query_terms=query_terms)
        if overlap <= min_overlap:
            continue
        results.append({"node": node, "semantic_score_raw": 0.0})
    return results


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
    Settings.embed_model = get_local_embed_model()
    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = load_index_from_storage(storage_context)

    parsed_filters = parse_active_filters(active_filters)
    normalized_query = apply_active_filters(planned_query=planned_query, active_filters=parsed_filters["tokens"])
    base_terms = list(query_terms or extract_keywords(normalized_query))
    effective_terms = base_terms + parsed_filters["keywords"]

    candidate_k = max(page * page_size * 6, 80)
    all_nodes = _load_all_nodes(index)

    mode = (mode or "hybrid").lower()
    if mode not in {"hybrid", "semantic", "keyword"}:
        mode = "hybrid"

    candidates: List[Dict] = []
    if mode in {"hybrid", "semantic"}:
        candidates.extend(_semantic_candidates(index=index, query_text=normalized_query, candidate_k=candidate_k))

    if mode in {"hybrid", "keyword"}:
        keyword_candidates = _keyword_candidates(
            all_nodes=all_nodes,
            query_terms=effective_terms,
            min_overlap=0.0 if mode == "keyword" else 0.05,
        )
        candidates.extend(keyword_candidates)

    deduped: Dict[str, Dict] = {}
    for candidate in candidates:
        record = _record_from_node(
            node=candidate["node"],
            semantic_score_raw=candidate["semantic_score_raw"],
            query_terms=effective_terms,
        )
        key = record["record_key"]
        existing = deduped.get(key)
        if existing is None or record["semantic_score_raw"] > existing["semantic_score_raw"]:
            deduped[key] = record

    filtered_records = [
        record for record in deduped.values() if record_passes_structured_filters(record, parsed_filters)
    ]

    normalize_semantic_scores(filtered_records)

    for record in filtered_records:
        score = fuse_scores(
            semantic_score=float(record.get("semantic_score") or 0.0),
            keyword_overlap=float(record.get("keyword_overlap") or 0.0),
            mode=mode,
        )
        record["score"] = round(score, 6)

    sorted_records = sort_chunk_records(filtered_records, sort_by=sort_by)

    pagination = paginate_records(sorted_records, page=page, page_size=page_size)
    paged = pagination["items"]
    for idx, record in enumerate(paged, start=1 + (pagination["page"] - 1) * pagination["page_size"]):
        record["rank"] = idx

    facets = build_facets(
        chunks=sorted_records,
        query_terms=effective_terms,
        top_term_k=8,
        top_value_k=10,
    )

    return {
        "chunks": paged,
        "ranked_chunks": sorted_records,
        "normalized_query": normalized_query,
        "mode": mode,
        "sort_by": sort_by,
        "page": pagination["page"],
        "page_size": pagination["page_size"],
        "total_results": pagination["total_results"],
        "total_pages": pagination["total_pages"],
        "facets": facets,
        "active_filter_tokens": parsed_filters["tokens"],
    }
