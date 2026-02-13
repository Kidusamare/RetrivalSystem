import unittest

from retrieval.query_planner import extract_keywords, plan_query


class QueryPlannerTests(unittest.TestCase):
    def test_plan_query_removes_stopwords(self):
        plan = plan_query("What is the role of semiconductor coolant fuse systems?")
        self.assertIn("semiconductor", plan["keywords"])
        self.assertIn("coolant", plan["keywords"])
        self.assertIn("fuse", plan["keywords"])
        self.assertNotIn("what", plan["keywords"])
        self.assertNotIn("the", plan["keywords"])

    def test_planned_query_roundtrip(self):
        keywords = extract_keywords("generative ai patents")
        self.assertGreater(len(keywords), 0)
        plan = plan_query("generative ai patents")
        self.assertIn("generative ai patents", plan["planned_query"])


if __name__ == "__main__":
    unittest.main()

