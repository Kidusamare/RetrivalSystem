from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from config.settings import get_settings, resolve_paths
from ingestion.chunker import attach_chunk_metadata, chunk_documents
from ingestion.file_registry import register_files
from ingestion.index_builder import load_or_create_index, persist_index, upsert_chunks
from ingestion.parser import load_documents_from_files
from services.index_state import activate_staging_index, prepare_staging_index_dir
from services.job_service import record_index_generation, update_job_progress, upsert_documents_and_chunks


def _normalize_paths(file_paths: Iterable[str]) -> Tuple[List[str], List[str]]:
    normalized: List[str] = []
    missing_or_invalid: List[str] = []
    seen = set()
    for raw_path in file_paths or []:
        cleaned = (raw_path or "").strip()
        if not cleaned:
            continue
        resolved_path = Path(cleaned).expanduser().resolve()
        path = str(resolved_path)
        if path in seen:
            continue
        seen.add(path)
        if not resolved_path.exists() or not resolved_path.is_file():
            missing_or_invalid.append(path)
            continue
        normalized.append(path)
    return normalized, missing_or_invalid


def _doc_lookup(records: List[Dict[str, Any]]) -> Dict[str, str]:
    lookup = {}
    for record in records:
        lookup[record["path"]] = record["doc_id"]
        lookup[record["file_name"]] = record["doc_id"]
    return lookup


def handle_local_file_ingestion(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    settings = resolve_paths(get_settings())
    options = payload.get("options") or {}
    dedupe_mode = str(options.get("dedupe") or "sha256").strip().lower()
    deep_memory_requested = options.get("deep_memory")
    deep_memory_enabled = (
        settings.ingestion_deep_memory_enabled
        if deep_memory_requested is None
        else bool(deep_memory_requested)
    )
    if dedupe_mode != "sha256":
        raise ValueError("Unsupported dedupe mode for local files. Allowed value: sha256")

    file_paths, missing_paths = _normalize_paths(payload.get("file_paths") or [])

    update_job_progress(job_id, 0.05, "Validated file paths")

    if not file_paths:
        if missing_paths:
            preview = ", ".join(missing_paths[:5])
            raise ValueError(f"No valid files found. Missing or invalid paths: {preview}")
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "message": "No files provided.",
        }

    registration = register_files(file_paths, settings.registry_path)
    new_records = registration["new_files"]
    if not new_records:
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "skipped_missing_files": missing_paths,
            "existing_files": registration["existing_files"],
            "total_registered_files": len(registration["registry"]["files"]),
            "message": "All files were already indexed.",
        }

    update_job_progress(job_id, 0.2, "Registered new files")

    docs = load_documents_from_files(
        file_paths=[item["path"] for item in new_records],
        allowed_extensions=settings.allowed_extensions,
    )
    nodes = chunk_documents(
        documents=docs,
        chunk_size=int(options.get("chunk_size") or settings.chunk_size),
        chunk_overlap=int(options.get("chunk_overlap") or settings.chunk_overlap),
        deep_memory=deep_memory_enabled,
        deep_memory_buffer_size=settings.deep_memory_buffer_size,
        deep_memory_breakpoint_percentile=settings.deep_memory_breakpoint_percentile,
    )
    nodes = attach_chunk_metadata(nodes, _doc_lookup(new_records))

    update_job_progress(job_id, 0.45, "Chunked documents")

    staging_dir = prepare_staging_index_dir(settings, job_id)
    record_index_generation(f"gen_{job_id}_staging", str(staging_dir), "staging")

    index = load_or_create_index(staging_dir)
    index = upsert_chunks(index, nodes)
    persist_index(index, staging_dir)

    update_job_progress(job_id, 0.7, "Persisted staging index")

    active_dir = activate_staging_index(settings, staging_dir)
    record_index_generation(f"gen_{job_id}_active", str(active_dir), "active")

    documents_rows = []
    for record in new_records:
        documents_rows.append(
            {
                "id": record["doc_id"],
                "source_type": "local_file",
                "doc_key": f"sha256:{record['sha256']}",
                "doc_id": record["doc_id"],
                "file_name": record["file_name"],
                "source_path": record["path"],
                "sha256": record["sha256"],
                "patent_id": None,
                "metadata_json": {
                    "size_bytes": record.get("size_bytes"),
                    "indexed_at": record.get("indexed_at"),
                },
            }
        )

    chunks_rows = []
    for node in nodes:
        metadata = dict(node.metadata or {})
        chunk_id = str(metadata.get("chunk_id") or "")
        doc_id = str(metadata.get("doc_id") or "unknown")
        chunks_rows.append(
            {
                "chunk_id": chunk_id,
                "document_id": doc_id,
                "doc_id": doc_id,
                "content": node.get_content(),
                "metadata_json": metadata,
            }
        )

    upsert_documents_and_chunks(documents=documents_rows, chunks=chunks_rows)
    update_job_progress(job_id, 0.95, "Recorded metadata state")

    return {
        "ingested_files_count": len(new_records),
        "chunks_added": len(nodes),
        "deep_memory_enabled": deep_memory_enabled,
        "new_files": new_records,
        "skipped_missing_files": missing_paths,
        "existing_files": registration["existing_files"],
        "total_registered_files": len(registration["registry"]["files"]),
        "active_index_dir": str(active_dir),
        "message": f"Indexed {len(new_records)} file(s), added {len(nodes)} chunk(s).",
    }
