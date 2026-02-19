import unittest

from retrieval.filter_suggester import build_facets


class FacetGenerationTests(unittest.TestCase):
    def test_build_facets_returns_term_source_doc(self):
        chunks = [
            {
                "text": "Semiconductor wafer with dielectric layer and interconnect.",
                "source": "chip_a.md",
                "doc_id": "doc-a",
            },
            {
                "text": "Interconnect reliability and dielectric encapsulation details.",
                "source": "chip_a.md",
                "doc_id": "doc-a",
            },
            {
                "text": "Coolant routing for semiconductor package.",
                "source": "chip_b.md",
                "doc_id": "doc-b",
            },
        ]

        facets = build_facets(chunks=chunks, query_terms=["semiconductor"], top_term_k=5, top_value_k=5)

        self.assertIn("term", facets)
        self.assertIn("source_file", facets)
        self.assertIn("doc_id", facets)
        self.assertTrue(any(row["token"].startswith("source:") for row in facets["source_file"]))
        self.assertTrue(any(row["token"].startswith("doc:") for row in facets["doc_id"]))


if __name__ == "__main__":
    unittest.main()
