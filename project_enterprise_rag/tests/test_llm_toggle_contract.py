import unittest
from unittest.mock import patch

from retrieval.query_planner import plan_query_mode


class LlmToggleContractTests(unittest.TestCase):
    def test_rules_backend_contract(self):
        plan = plan_query_mode(
            user_query="semiconductor interconnect reliability",
            mode="hybrid",
            planner_backend="rules",
            constraints={"include_terms": ["dielectric"], "exclude_terms": ["memory"]},
        )
        self.assertIn("planned_query", plan)
        self.assertEqual(plan["backend_used"], "rules")
        self.assertIn("dielectric", " ".join(plan["include_terms"]))

    @patch("retrieval.query_planner.generate_query_plan", side_effect=RuntimeError("offline"))
    def test_local_llm_fallback_to_rules(self, _mock_generate):
        plan = plan_query_mode(
            user_query="semiconductor interconnect reliability",
            mode="hybrid",
            planner_backend="local_llm",
            constraints={"include_terms": ["dielectric"], "exclude_terms": ["memory"]},
            local_llm_config={"base_url": "http://127.0.0.1:11434", "model": "qwen3:0.6b", "timeout_seconds": 2},
        )
        self.assertEqual(plan["backend_used"], "rules_fallback")
        self.assertIn("fallback", plan["rationale"].lower())


if __name__ == "__main__":
    unittest.main()
