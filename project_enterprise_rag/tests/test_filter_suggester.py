import unittest

from retrieval.filter_suggester import suggest_filters


class FilterSuggesterTests(unittest.TestCase):
    def test_suggest_filters_top_k(self):
        chunks = [
            {"text": "Semiconductor cooling design with coolant loops and valve stack."},
            {"text": "Fuse protection and coolant pump behavior in chip systems."},
            {"text": "Patent claims mention coolant channels and thermal management."},
        ]
        suggestions = suggest_filters(chunks, query_terms=["semiconductor"], top_k=5)
        self.assertLessEqual(len(suggestions), 5)
        self.assertTrue(any(term in suggestions for term in ("coolant", "fuse")))

    def test_suggest_filters_excludes_query_terms(self):
        chunks = [{"text": "semiconductor semiconductor fuse coolant"}]
        suggestions = suggest_filters(chunks, query_terms=["semiconductor"], top_k=5)
        self.assertNotIn("semiconductor", suggestions)


if __name__ == "__main__":
    unittest.main()

