import unittest

from retrieval.retriever import compute_keyword_overlap, fuse_scores


class RetrieverHybridTests(unittest.TestCase):
    def test_keyword_overlap_detects_matches(self):
        overlap, matched = compute_keyword_overlap(
            "Semiconductor dielectric interconnect stack.",
            ["semiconductor", "dielectric", "coolant"],
        )
        self.assertAlmostEqual(overlap, 2 / 3, places=3)
        self.assertIn("semiconductor", matched)
        self.assertIn("dielectric", matched)

    def test_hybrid_fusion_balances_signals(self):
        semantic_only = fuse_scores(semantic_score=0.9, keyword_overlap=0.0, mode="hybrid")
        keyword_only = fuse_scores(semantic_score=0.0, keyword_overlap=0.9, mode="hybrid")
        self.assertGreater(semantic_only, keyword_only)
        self.assertAlmostEqual(semantic_only, 0.585, places=3)


if __name__ == "__main__":
    unittest.main()
