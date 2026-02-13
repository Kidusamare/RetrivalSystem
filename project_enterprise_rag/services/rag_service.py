from pathlib import Path
from typing import Dict, Iterable, List, Optional

from config.settings import get_settings, resolve_paths
from ingestion.chunker import attach_chunk_metadata, chunk_documents
from ingestion.file_registry import list_registered_files, register_files
from ingestion.index_builder import load_or_create_index, persist_index, upsert_chunks
from ingestion.parser import load_documents_from_files
from retrieval.filter_suggester import suggest_filters
from retrieval.formatter import format_api_chunk, format_chunk_card
from retrieval.highlighter import build_highlight_terms, highlight_text
from retrieval.query_planner import extract_keywords, plan_query
from retrieval.retriever import retrieve_chunks


def _index_ready(storage_dir: Path) -> bool:
    required = ("docstore.json", "index_store.json", "default__vector_store.json")
    return all((storage_dir / name).exists() for name in required)


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


def ingest_files_service(file_paths: Iterable[str]) -> Dict:
    settings = resolve_paths(get_settings())
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
    )
    nodes = attach_chunk_metadata(nodes, doc_id_lookup=_to_doc_lookup(new_records))

    index = load_or_create_index(settings.storage_dir)
    index = upsert_chunks(index, nodes)
    persist_index(index, settings.storage_dir)

    return {
        "ingested_files_count": len(new_records),
        "chunks_added": len(nodes),
        "new_files": new_records,
        "existing_files": registration["existing_files"],
        "total_registered_files": len(registration["registry"]["files"]),
        "message": f"Indexed {len(new_records)} file(s), added {len(nodes)} chunk(s).",
    }


def plan_query_service(user_query: str) -> Dict:
    return plan_query(user_query)


def search_chunks_service(
    user_query: str,
    planned_query: Optional[str] = None,
    active_filters: Optional[Iterable[str]] = None,
    top_k: Optional[int] = None,
) -> Dict:
    settings = resolve_paths(get_settings())
    effective_top_k = top_k or settings.top_k

    query_plan = plan_query(user_query)
    effective_query = (planned_query or query_plan["planned_query"]).strip()
    keywords = query_plan["keywords"] or extract_keywords(effective_query)

    if not _index_ready(settings.storage_dir):
        return {
            "user_query": user_query,
            "planned_query": effective_query,
            "keywords": keywords,
            "active_filters": list(active_filters or []),
            "suggested_filters": [],
            "chunks": [],
            "chunk_cards": [],
            "total_chunks": 0,
        }

    chunks = retrieve_chunks(
        persist_dir=settings.storage_dir,
        planned_query=effective_query,
        active_filters=active_filters,
        top_k=effective_top_k,
    )

    highlight_terms = build_highlight_terms(keywords, active_filters or [])
    for chunk in chunks:
        chunk["text_highlighted"] = highlight_text(chunk.get("text", ""), highlight_terms)

    suggested_filters = suggest_filters(
        chunks=chunks,
        query_terms=highlight_terms,
        top_k=settings.max_filter_suggestions,
    )

    return {
        "user_query": user_query,
        "planned_query": effective_query,
        "keywords": keywords,
        "active_filters": list(active_filters or []),
        "suggested_filters": suggested_filters,
        "chunks": [format_api_chunk(chunk) for chunk in chunks],
        "chunk_cards": [format_chunk_card(chunk) for chunk in chunks],
        "total_chunks": len(chunks),
    }
