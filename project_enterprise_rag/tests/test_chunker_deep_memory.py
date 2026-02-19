import unittest
from unittest.mock import patch

try:
    from llama_index.core import Document
    from llama_index.core.schema import TextNode
except ModuleNotFoundError:  # pragma: no cover - optional in minimal host envs
    Document = None
    TextNode = None

if Document is not None:
    from ingestion.chunker import _annotate_deep_memory_links, chunk_documents


@unittest.skipIf(Document is None, "llama_index is not installed in this environment")
class DeepMemoryChunkerTests(unittest.TestCase):
    @patch("ingestion.chunker._chunk_with_deep_memory")
    def test_chunk_documents_routes_to_deep_memory_pipeline(self, mock_deep):
        mock_deep.return_value = [TextNode(text="semantic chunk", metadata={})]
        docs = [Document(text="semiconductor interconnect reliability", metadata={"doc_id": "d1"})]

        nodes = chunk_documents(
            documents=docs,
            chunk_size=700,
            chunk_overlap=80,
            deep_memory=True,
            deep_memory_buffer_size=2,
            deep_memory_breakpoint_percentile=90,
        )

        self.assertEqual(len(nodes), 1)
        mock_deep.assert_called_once()
        call = mock_deep.call_args
        self.assertEqual(call.kwargs["buffer_size"], 2)
        self.assertEqual(call.kwargs["breakpoint_percentile_threshold"], 90)

    @patch("ingestion.chunker._chunk_with_sentence_splitter")
    def test_chunk_documents_routes_to_sentence_splitter_when_disabled(self, mock_sentence):
        mock_sentence.return_value = [TextNode(text="sentence chunk", metadata={})]
        docs = [Document(text="wafer process", metadata={"doc_id": "d2"})]

        nodes = chunk_documents(
            documents=docs,
            chunk_size=700,
            chunk_overlap=80,
            deep_memory=False,
        )

        self.assertEqual(len(nodes), 1)
        mock_sentence.assert_called_once()

    def test_deep_memory_annotations_add_linked_context(self):
        nodes = [
            TextNode(text="chunk 1", metadata={}),
            TextNode(text="chunk 2", metadata={}),
            TextNode(text="chunk 3", metadata={}),
        ]

        annotated = _annotate_deep_memory_links(nodes)

        self.assertEqual(annotated[0].metadata["deep_memory_mode"], "semantic")
        self.assertEqual(annotated[0].metadata["deep_memory_position"], 1)
        self.assertIsNone(annotated[0].metadata["deep_memory_prev_node_id"])
        self.assertIsNotNone(annotated[0].metadata["deep_memory_next_node_id"])

        self.assertEqual(annotated[1].metadata["deep_memory_position"], 2)
        self.assertIsNotNone(annotated[1].metadata["deep_memory_prev_node_id"])
        self.assertIsNotNone(annotated[1].metadata["deep_memory_next_node_id"])

        self.assertEqual(annotated[2].metadata["deep_memory_position"], 3)
        self.assertIsNotNone(annotated[2].metadata["deep_memory_prev_node_id"])
        self.assertIsNone(annotated[2].metadata["deep_memory_next_node_id"])


if __name__ == "__main__":
    unittest.main()
