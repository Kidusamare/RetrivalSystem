from __future__ import annotations

from typing import Any, Dict, List

from llama_index.core import Document

from config.settings import get_settings, resolve_paths
from connectors.patentsview.client import fetch_patents
from connectors.patentsview.types import PatentsViewQuery
from db.models import Document as DocumentModel
from db.session import session_scope
from ingestion.chunker import chunk_documents
from ingestion.index_builder import load_or_create_index, persist_index, upsert_chunks
from services.index_state import activate_staging_index, prepare_staging_index_dir
from services.job_service import record_index_generation, update_job_progress, upsert_documents_and_chunks


def _existing_patent_keys() -> set[str]:
    with session_scope() as session:
        rows = session.query(DocumentModel.doc_key).filter(DocumentModel.doc_key.like("patent:%")).all()
        return {row[0] for row in rows}


def handle_patentsview_sync(job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    settings = resolve_paths(get_settings())
    query_payload = payload.get("query") or {}
    options = payload.get("options") or {}
    deep_memory_requested = options.get("deep_memory")
    deep_memory_enabled = (
        settings.ingestion_deep_memory_enabled
        if deep_memory_requested is None
        else bool(deep_memory_requested)
    )

    keywords = [token.strip() for token in (query_payload.get("keywords") or []) if str(token).strip()]
    if not keywords:
        raise ValueError("PatentsView sync requires at least one non-empty keyword.")

    max_records = int(query_payload.get("max_records") or 200)
    if max_records < 1:
        raise ValueError("PatentsView max_records must be >= 1.")

    dedupe_mode = str(options.get("dedupe") or "patent_id").strip().lower()
    if dedupe_mode != "patent_id":
        raise ValueError("Unsupported dedupe mode for patents. Allowed value: patent_id")

    retries = int(options.get("retries") or settings.patentsview_retries)
    if retries < 1:
        raise ValueError("PatentsView retries must be >= 1.")

    connector_request = {
        "base_url": settings.patentsview_api_url,
        "keywords": keywords,
        "max_records": max_records,
        "timeout_seconds": settings.patentsview_timeout_seconds,
        "retries": retries,
        "dedupe": dedupe_mode,
    }

    update_job_progress(job_id, 0.05, "Validated PatentsView query")

    patents = fetch_patents(
        base_url=settings.patentsview_api_url,
        api_key=settings.patentsview_api_key,
        query=PatentsViewQuery(keywords=keywords, max_records=max_records),
        timeout_seconds=settings.patentsview_timeout_seconds,
        retries=retries,
    )

    if not patents:
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "connector_request": connector_request,
            "connector_summary": {
                "fetched_records": 0,
                "new_records": 0,
                "already_indexed_records": 0,
            },
            "message": "PatentsView returned no records.",
        }

    update_job_progress(job_id, 0.25, f"Fetched {len(patents)} patent records")

    existing_keys = _existing_patent_keys()
    new_patents = [record for record in patents if f"patent:{record.patent_id}" not in existing_keys]
    already_indexed_records = max(0, len(patents) - len(new_patents))

    if not new_patents:
        return {
            "ingested_files_count": 0,
            "chunks_added": 0,
            "new_files": [],
            "connector_request": connector_request,
            "connector_summary": {
                "fetched_records": len(patents),
                "new_records": 0,
                "already_indexed_records": already_indexed_records,
            },
            "message": "All fetched patent records were already indexed.",
        }

    docs: List[Document] = []
    for record in new_patents:
        payload_doc = record.to_document()
        metadata = dict(payload_doc["metadata"])
        metadata["doc_id"] = record.patent_id
        metadata["source_path"] = payload_doc["metadata"]["source_url"]
        metadata["source_modified_at"] = record.date
        docs.append(Document(text=payload_doc["text"], metadata=metadata))

    nodes = chunk_documents(
        documents=docs,
        chunk_size=int(options.get("chunk_size") or settings.chunk_size),
        chunk_overlap=int(options.get("chunk_overlap") or settings.chunk_overlap),
        deep_memory=deep_memory_enabled,
        deep_memory_buffer_size=settings.deep_memory_buffer_size,
        deep_memory_breakpoint_percentile=settings.deep_memory_breakpoint_percentile,
    )

    for index, node in enumerate(nodes, start=1):
        metadata = dict(node.metadata or {})
        doc_id = metadata.get("doc_id") or "unknown"
        metadata["chunk_id"] = f"{doc_id}_chunk_{index}"
        node.metadata = metadata

    update_job_progress(job_id, 0.55, "Built patent chunks")

    staging_dir = prepare_staging_index_dir(settings, job_id)
    record_index_generation(f"gen_{job_id}_staging", str(staging_dir), "staging")

    index = load_or_create_index(staging_dir)
    index = upsert_chunks(index, nodes)
    persist_index(index, staging_dir)

    active_dir = activate_staging_index(settings, staging_dir)
    record_index_generation(f"gen_{job_id}_active", str(active_dir), "active")

    documents_rows = []
    for record in new_patents:
        documents_rows.append(
            {
                "id": record.patent_id,
                "source_type": "patentsview",
                "doc_key": f"patent:{record.patent_id}",
                "doc_id": record.patent_id,
                "file_name": f"US{record.patent_id}.md",
                "source_path": record.source_url,
                "sha256": None,
                "patent_id": record.patent_id,
                "metadata_json": {
                    "title": record.title,
                    "patent_date": record.date,
                    "source": "patentsview",
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
    update_job_progress(job_id, 0.95, "Recorded patents metadata")

    return {
        "ingested_files_count": len(new_patents),
        "chunks_added": len(nodes),
        "deep_memory_enabled": deep_memory_enabled,
        "new_files": [{"doc_id": item.patent_id, "file_name": f"US{item.patent_id}.md"} for item in new_patents],
        "connector_request": connector_request,
        "connector_summary": {
            "fetched_records": len(patents),
            "new_records": len(new_patents),
            "already_indexed_records": already_indexed_records,
        },
        "active_index_dir": str(active_dir),
        "message": f"Indexed {len(new_patents)} patent records, added {len(nodes)} chunk(s).",
    }
