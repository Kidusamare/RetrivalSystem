from typing import Dict, Iterable, List

from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import BaseNode, Document


def chunk_documents(
    documents: Iterable[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> List[BaseNode]:
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.get_nodes_from_documents(list(documents))


def attach_chunk_metadata(
    nodes: Iterable[BaseNode],
    doc_id_lookup: Dict[str, str],
) -> List[BaseNode]:
    updated_nodes: List[BaseNode] = []

    for index, node in enumerate(nodes, start=1):
        metadata = dict(node.metadata or {})
        source_path = metadata.get("source_path")
        file_name = metadata.get("file_name")

        doc_id = (
            doc_id_lookup.get(str(source_path))
            or doc_id_lookup.get(str(file_name))
            or metadata.get("doc_id")
            or "unknown"
        )
        metadata["doc_id"] = doc_id
        metadata["chunk_id"] = f"{doc_id}_chunk_{index}"
        node.metadata = metadata
        updated_nodes.append(node)

    return updated_nodes

