from pathlib import Path
from typing import Dict, Iterable, List, Optional

from llama_index.core import Settings, StorageContext, load_index_from_storage

from ingestion.index_builder import get_local_embed_model


def apply_active_filters(planned_query: str, active_filters: Optional[Iterable[str]]) -> str:
    filters = [item.strip() for item in (active_filters or []) if item and item.strip()]
    if not filters:
        return planned_query.strip()
    return f"{planned_query.strip()} {' '.join(filters)}".strip()


def _resolve_source(metadata: Dict) -> str:
    return metadata.get("file_name") or metadata.get("filename") or metadata.get("source") or "Unknown"


def retrieve_chunks(
    persist_dir: Path,
    planned_query: str,
    active_filters: Optional[Iterable[str]] = None,
    top_k: int = 5,
) -> List[Dict]:
    Settings.embed_model = get_local_embed_model()
    storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
    index = load_index_from_storage(storage_context)

    query_text = apply_active_filters(planned_query=planned_query, active_filters=active_filters)
    retriever = index.as_retriever(similarity_top_k=top_k)
    nodes = retriever.retrieve(query_text)

    chunks: List[Dict] = []
    for rank, node_with_score in enumerate(nodes, start=1):
        node = getattr(node_with_score, "node", node_with_score)
        metadata = dict(getattr(node, "metadata", {}) or {})
        score = getattr(node_with_score, "score", None)

        chunks.append(
            {
                "rank": rank,
                "score": round(float(score), 4) if score is not None else None,
                "source": _resolve_source(metadata),
                "page": metadata.get("page") or metadata.get("page_label") or "N/A",
                "doc_id": metadata.get("doc_id", "unknown"),
                "chunk_id": metadata.get("chunk_id", "unknown"),
                "text": node.get_content(),
                "metadata": metadata,
            }
        )
    return chunks

