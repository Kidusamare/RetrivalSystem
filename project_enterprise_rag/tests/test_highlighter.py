import unittest

from retrieval.highlighter import build_highlight_terms, highlight_text


class HighlighterTests(unittest.TestCase):
    def test_highlight_text_marks_expected_terms(self):
        terms = build_highlight_terms(["semiconductor", "coolant"], ["fuse"])
        output = highlight_text("Semiconductor coolant fuse architecture.", terms)
        self.assertIn("<mark>Semiconductor</mark>", output)
        self.assertIn("<mark>coolant</mark>", output)
        self.assertIn("<mark>fuse</mark>", output)


if __name__ == "__main__":
    unittest.main()

