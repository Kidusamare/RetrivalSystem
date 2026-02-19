import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional in minimal host envs
    TestClient = None

from db.models import Job
from db.session import run_migrations, session_scope
from services.job_service import bootstrap_api_keys

if TestClient is not None:
    from api_app import app


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class Phase34ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        bootstrap_api_keys(["unit-test-key"])

    def setUp(self):
        self.client = TestClient(app)
        self.headers = {"X-API-Key": "unit-test-key"}

    def tearDown(self):
        self.client.close()

    def test_query_plan_compat_contract(self):
        response = self.client.post(
            "/query/plan",
            headers=self.headers,
            json={"user_query": "semiconductor interconnect reliability"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("planned_query", "keywords", "backend_used", "rationale"):
            self.assertIn(key, payload)

    def test_query_search_compat_contract(self):
        response = self.client.post(
            "/query/search",
            headers=self.headers,
            json={"user_query": "semiconductor interconnect reliability"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        for key in ("chunks", "facet_choices", "suggested_filters", "total_chunks", "planner_backend", "response_backend"):
            self.assertIn(key, payload)

    def test_patentsview_ingestion_default_dedupe(self):
        response = self.client.post(
            "/v1/ingestions/patentsview",
            headers=self.headers,
            json={"query": {"keywords": ["semiconductor"], "max_records": 5}},
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]

        with session_scope() as session:
            row = session.get(Job, job_id)
            self.assertIsNotNone(row)
            self.assertEqual(row.payload_json["options"]["dedupe"], "patent_id")

    def test_patentsview_ingestion_rejects_invalid_dedupe(self):
        response = self.client.post(
            "/v1/ingestions/patentsview",
            headers=self.headers,
            json={
                "query": {"keywords": ["semiconductor"], "max_records": 5},
                "options": {"dedupe": "sha256"},
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_file_ingestion_accepts_deep_memory_option(self):
        response = self.client.post(
            "/v1/ingestions/files",
            headers=self.headers,
            json={
                "file_paths": [],
                "options": {"deep_memory": True},
            },
        )
        self.assertEqual(response.status_code, 200)
        job_id = response.json()["job_id"]

        with session_scope() as session:
            row = session.get(Job, job_id)
            self.assertIsNotNone(row)
            self.assertEqual(row.payload_json["options"]["dedupe"], "sha256")
            self.assertTrue(row.payload_json["options"]["deep_memory"])


if __name__ == "__main__":
    unittest.main()
