from __future__ import annotations

from typing import Dict, Iterable, List, cast

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.core.schema import BaseNode, Document

from ingestion.index_builder import get_local_embed_model


def _chunk_with_sentence_splitter(
    documents: Iterable[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> List[BaseNode]:
    splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.get_nodes_from_documents(list(documents))


def _annotate_deep_memory_links(nodes: List[BaseNode]) -> List[BaseNode]:
    if not nodes:
        return nodes

    for index, node in enumerate(nodes):
        metadata = dict(node.metadata or {})
        metadata["deep_memory_mode"] = "semantic"
        metadata["deep_memory_position"] = index + 1
        metadata["deep_memory_prev_node_id"] = str(nodes[index - 1].node_id) if index > 0 else None
        metadata["deep_memory_next_node_id"] = str(nodes[index + 1].node_id) if index + 1 < len(nodes) else None
        node.metadata = metadata
    return nodes


def _chunk_with_deep_memory(
    documents: Iterable[Document],
    *,
    buffer_size: int,
    breakpoint_percentile_threshold: int,
) -> List[BaseNode]:
    docs = list(documents)
    if not docs:
        return []

    embed_model = get_local_embed_model()
    splitter = SemanticSplitterNodeParser(
        buffer_size=max(1, int(buffer_size)),
        breakpoint_percentile_threshold=max(1, min(99, int(breakpoint_percentile_threshold))),
        embed_model=embed_model,
    )
    pipeline = IngestionPipeline(transformations=[splitter, embed_model])
    nodes = cast(List[BaseNode], pipeline.run(documents=docs))
    return _annotate_deep_memory_links(nodes)


def chunk_documents(
    documents: Iterable[Document],
    chunk_size: int,
    chunk_overlap: int,
    *,
    deep_memory: bool = False,
    deep_memory_buffer_size: int = 1,
    deep_memory_breakpoint_percentile: int = 95,
) -> List[BaseNode]:
    docs = list(documents)
    if not docs:
        return []

    if bool(deep_memory):
        return _chunk_with_deep_memory(
            docs,
            buffer_size=deep_memory_buffer_size,
            breakpoint_percentile_threshold=deep_memory_breakpoint_percentile,
        )

    return _chunk_with_sentence_splitter(
        docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


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
