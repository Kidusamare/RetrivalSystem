from pathlib import Path
from typing import Dict, List

from config.settings import get_settings
from retrieval.retriever import retrieve_chunks
from services.index_state import get_runtime_index_dir
from services.rag_service import search_chunks_service

DEFAULT_PERSIST_DIR = str(get_runtime_index_dir(get_settings()))
DEFAULT_TOP_K = get_settings().top_k


def get_query_engine(persist_dir: str, top_k: int = DEFAULT_TOP_K):
    class _RetrieverWrapper:
        def __init__(self, persist_path: str, limit: int):
            self.persist_path = persist_path
            self.limit = limit

        def retrieve(self, query: str):
            return retrieve_chunks(
                persist_dir=Path(self.persist_path),
                planned_query=query,
                top_k=self.limit,
            )

    return _RetrieverWrapper(persist_dir, top_k)


def get_rag_answer(
    query: str,
    persist_dir: str = DEFAULT_PERSIST_DIR,
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict]:
    result = search_chunks_service(
        user_query=query,
        planned_query=query,
        active_filters=[],
        top_k=top_k,
    )
    return result["chunks"]
