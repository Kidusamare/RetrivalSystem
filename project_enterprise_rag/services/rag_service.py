from pathlib import Path
from typing import Dict, Iterable, List, Optional

from config.settings import get_settings, resolve_paths
from ingestion.chunker import attach_chunk_metadata, chunk_documents
from ingestion.file_registry import list_registered_files, register_files
from ingestion.index_builder import load_or_create_index, persist_index, upsert_chunks
from ingestion.parser import load_documents_from_files
from retrieval.formatter import format_api_chunk, format_chunk_card
from retrieval.highlighter import build_highlight_terms, highlight_text
from retrieval.query_planner import extract_keywords, plan_query_mode
from retrieval.retriever import search_chunks
from services.index_state import get_runtime_index_dir, index_dir_ready
from synthesis.answer_builder import build_cited_answer


def _index_ready(settings) -> bool:
    runtime_dir = get_runtime_index_dir(settings)
    return index_dir_ready(runtime_dir)


def _to_doc_lookup(records: List[Dict]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for record in records:
        lookup[record["path"]] = record["doc_id"]
        lookup[record["file_name"]] = record["doc_id"]
    return lookup


def _normalize_paths(file_paths: Iterable[str]) -> List[str]:
    normalized = []
    seen = set()
    for raw_path in file_paths or []:
        path = str(Path(raw_path).expanduser().resolve())
        if path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return normalized


def _normalize_terms(values: Optional[Iterable[str]]) -> List[str]:
    output: List[str] = []
    seen = set()
    for value in values or []:
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output



def _clamp_page_size(settings, requested: Optional[int], fallback: Optional[int]) -> int:
    size = requested or fallback or settings.default_page_size
    size = max(1, int(size))
    return min(size, settings.max_page_size)


def ingest_files_service(file_paths: Iterable[str]) -> Dict:
    settings = resolve_paths(get_settings())
    target_index_dir = settings.index_active_dir
    normalized_paths = _normalize_paths(file_paths)
    if not normalized_paths:
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "existing_files": [],
            "total_registered_files": len(list_registered_files(settings.registry_path)),
            "message": "No files provided.",
        }

    registration = register_files(normalized_paths, settings.registry_path)
    new_records = registration["new_files"]

    if not new_records:
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "existing_files": registration["existing_files"],
            "total_registered_files": len(registration["registry"]["files"]),
            "message": "All files were already indexed.",
        }

    new_paths = [record["path"] for record in new_records]
    documents = load_documents_from_files(
        file_paths=new_paths,
        allowed_extensions=settings.allowed_extensions,
    )
    nodes = chunk_documents(
        documents=documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        deep_memory=settings.ingestion_deep_memory_enabled,
        deep_memory_buffer_size=settings.deep_memory_buffer_size,
        deep_memory_breakpoint_percentile=settings.deep_memory_breakpoint_percentile,
    )
    nodes = attach_chunk_metadata(nodes, doc_id_lookup=_to_doc_lookup(new_records))

    index = load_or_create_index(target_index_dir)
    index = upsert_chunks(index, nodes)
    persist_index(index, target_index_dir)

    return {
        "ingested_files_count": len(new_records),
        "chunks_added": len(nodes),
        "deep_memory_enabled": settings.ingestion_deep_memory_enabled,
        "new_files": new_records,
        "existing_files": registration["existing_files"],
        "total_registered_files": len(registration["registry"]["files"]),
        "message": f"Indexed {len(new_records)} file(s), added {len(nodes)} chunk(s).",
    }


def plan_query_service(
    user_query: str,
    mode: Optional[str] = None,
    planner_backend: Optional[str] = None,
    include_terms: Optional[Iterable[str]] = None,
    exclude_terms: Optional[Iterable[str]] = None,
    active_filters: Optional[Iterable[str]] = None,
) -> Dict:
    settings = get_settings()
    effective_mode = (mode or settings.default_mode).lower()
    if effective_mode not in settings.supported_modes:
        effective_mode = settings.default_mode

    effective_backend = (planner_backend or settings.planner_backend).lower()
    if effective_backend not in {"rules", "local_llm"}:
        effective_backend = "rules"

    return plan_query_mode(
        user_query=user_query,
        mode=effective_mode,
        planner_backend=effective_backend,
        constraints={
            "include_terms": _normalize_terms(include_terms),
            "exclude_terms": _normalize_terms(exclude_terms),
            "active_filters": _normalize_terms(active_filters),
        },
        local_llm_config={
            "base_url": settings.ollama_base_url,
            "model": settings.ollama_planner_model,
            "timeout_seconds": settings.planner_timeout_seconds,
        },
    )


def search_chunks_service(
    user_query: str,
    planned_query: Optional[str] = None,
    active_filters: Optional[Iterable[str]] = None,
    top_k: Optional[int] = None,
    mode: Optional[str] = None,
    sort_by: Optional[str] = None,
    page: int = 1,
    page_size: Optional[int] = None,
    planner_backend: Optional[str] = None,
    response_backend: Optional[str] = None,
    include_terms: Optional[Iterable[str]] = None,
    exclude_terms: Optional[Iterable[str]] = None,
) -> Dict:
    settings = resolve_paths(get_settings())

    active_filter_tokens = _normalize_terms(active_filters)
    effective_mode = (mode or settings.default_mode).lower()
    if effective_mode not in settings.supported_modes:
        effective_mode = settings.default_mode

    effective_sort = (sort_by or "relevance").lower()
    if effective_sort not in settings.supported_sorts:
        effective_sort = "relevance"

    effective_page_size = _clamp_page_size(settings, requested=page_size, fallback=top_k)

    query_plan = plan_query_service(
        user_query=user_query,
        mode=effective_mode,
        planner_backend=planner_backend,
        include_terms=include_terms,
        exclude_terms=exclude_terms,
        active_filters=active_filter_tokens,
    )
    effective_query = (planned_query or query_plan["planned_query"]).strip()
    keywords = query_plan.get("keywords") or extract_keywords(effective_query)

    response_mode = (response_backend or settings.response_backend).lower()
    if response_mode not in {"none", "local_llm"}:
        response_mode = "none"

    runtime_index_dir = get_runtime_index_dir(settings)

    if not _index_ready(settings):
        return {
            "user_query": user_query,
            "planned_query": effective_query,
            "normalized_query": effective_query,
            "keywords": keywords,
            "include_terms": query_plan.get("include_terms", []),
            "exclude_terms": query_plan.get("exclude_terms", []),
            "planner_backend": query_plan.get("backend_used", "rules"),
            "response_backend": response_mode,
            "mode": effective_mode,
            "sort_by": effective_sort,
            "page": 1,
            "page_size": effective_page_size,
            "total_pages": 1,
            "total_results": 0,
            "active_filters": active_filter_tokens,
            "facets": {"term": [], "source_file": [], "doc_id": []},
            "facet_choices": [],
            "suggested_filters": [],
            "chunks": [],
            "chunk_cards": [],
            "answer": None,
            "total_chunks": 0,
            "search_meta": {
                "rationale": query_plan.get("rationale", ""),
                "message": "Index is not ready.",
            },
        }

    search_payload = search_chunks(
        persist_dir=runtime_index_dir,
        planned_query=effective_query,
        query_terms=keywords,
        active_filters=active_filter_tokens,
        mode=effective_mode,
        sort_by=effective_sort,
        page=page,
        page_size=effective_page_size,
    )

    chunks = search_payload["chunks"]
    highlight_terms = build_highlight_terms(keywords, active_filter_tokens)
    for chunk in chunks:
        text = chunk.get("text", "")
        chunk["text_highlighted"] = highlight_text(text, highlight_terms)
        chunk["snippet_highlighted"] = highlight_text(text[:420], highlight_terms)
        chunk["semantic_score"] = round(float(chunk.get("semantic_score") or 0.0), 4)
        chunk["keyword_overlap"] = round(float(chunk.get("keyword_overlap") or 0.0), 4)
        chunk["score"] = round(float(chunk.get("score") or 0.0), 4)

    facets = search_payload.get("facets", {"term": [], "source_file": [], "doc_id": []})
    facet_choices = [row["token"] for row in facets.get("term", [])]
    suggested_filters = list(facet_choices)

    answer = build_cited_answer(
        query=user_query,
        chunks=chunks,
        backend=response_mode,
        base_url=settings.ollama_base_url,
        model=settings.ollama_response_model,
        timeout_seconds=settings.planner_timeout_seconds,
    )

    return {
        "user_query": user_query,
        "planned_query": effective_query,
        "normalized_query": search_payload.get("normalized_query", effective_query),
        "keywords": keywords,
        "include_terms": query_plan.get("include_terms", []),
        "exclude_terms": query_plan.get("exclude_terms", []),
        "planner_backend": query_plan.get("backend_used", "rules"),
        "response_backend": response_mode,
        "mode": search_payload.get("mode", effective_mode),
        "sort_by": search_payload.get("sort_by", effective_sort),
        "page": search_payload.get("page", 1),
        "page_size": search_payload.get("page_size", effective_page_size),
        "total_pages": search_payload.get("total_pages", 1),
        "total_results": search_payload.get("total_results", 0),
        "active_filters": search_payload.get("active_filter_tokens", active_filter_tokens),
        "facets": facets,
        "facet_choices": facet_choices,
        "suggested_filters": suggested_filters,
        "chunks": [format_api_chunk(chunk) for chunk in chunks],
        "chunk_cards": [format_chunk_card(chunk) for chunk in chunks],
        "answer": answer,
        "total_chunks": len(chunks),
        "search_meta": {
            "rationale": query_plan.get("rationale", ""),
        },
    }
