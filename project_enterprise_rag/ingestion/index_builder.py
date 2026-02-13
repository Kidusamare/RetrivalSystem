from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

from llama_index.core import Settings, StorageContext, VectorStoreIndex, load_index_from_storage
from llama_index.core.schema import BaseNode
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


INDEX_FILES = (
    "docstore.json",
    "index_store.json",
    "default__vector_store.json",
)


@lru_cache(maxsize=1)
def get_local_embed_model() -> HuggingFaceEmbedding:
    return HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")


def _index_exists(persist_dir: Path) -> bool:
    return all((persist_dir / file_name).exists() for file_name in INDEX_FILES)


def load_or_create_index(persist_dir: Path) -> Optional[VectorStoreIndex]:
    persist_dir.mkdir(parents=True, exist_ok=True)
    Settings.embed_model = get_local_embed_model()

    if _index_exists(persist_dir):
        storage_context = StorageContext.from_defaults(persist_dir=str(persist_dir))
        return load_index_from_storage(storage_context)
    return None


def upsert_chunks(
    index: Optional[VectorStoreIndex],
    nodes: Iterable[BaseNode],
) -> Optional[VectorStoreIndex]:
    node_list = list(nodes)
    if not node_list:
        return index

    Settings.embed_model = get_local_embed_model()
    if index is None:
        return VectorStoreIndex(nodes=node_list, embed_model=get_local_embed_model())

    index.insert_nodes(node_list)
    return index


def persist_index(index: Optional[VectorStoreIndex], persist_dir: Path) -> None:
    if index is None:
        return
    persist_dir.mkdir(parents=True, exist_ok=True)
    index.storage_context.persist(persist_dir=str(persist_dir))

