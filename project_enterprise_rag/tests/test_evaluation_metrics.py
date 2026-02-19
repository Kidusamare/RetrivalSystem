import unittest

from evaluation.metrics import precision_at_k


class EvaluationMetricsTests(unittest.TestCase):
    def test_precision_at_k_counts_hits_with_unique_relevant_set(self):
        score = precision_at_k(
            predicted_doc_ids=["a", "b", "c", "d"],
            relevant_doc_ids=["b", "d", "x"],
            k=4,
        )
        self.assertEqual(score, 0.5)

    def test_precision_at_k_empty_predictions(self):
        score = precision_at_k(predicted_doc_ids=[], relevant_doc_ids=["a"], k=10)
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
