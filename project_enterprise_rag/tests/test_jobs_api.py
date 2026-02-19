import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional in minimal host envs
    TestClient = None

from db.session import run_migrations
from services.job_service import bootstrap_api_keys, enqueue_job

if TestClient is not None:
    from api_app import app


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class JobsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        bootstrap_api_keys(["unit-test-key"])

    def setUp(self):
        self.client = TestClient(app)
        self.headers = {"X-API-Key": "unit-test-key"}

    def tearDown(self):
        self.client.close()

    def test_list_jobs_rejects_invalid_status_filter(self):
        response = self.client.get("/v1/jobs", params={"status": "invalid"}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        payload = response.json()
        self.assertEqual(payload["detail"]["error_type"], "validation_error")

    def test_list_jobs_accepts_valid_status_filter(self):
        enqueue_job("local_files_ingest", {"file_paths": [], "options": {}})
        response = self.client.get("/v1/jobs", params={"status": "queued"}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("jobs", payload)


if __name__ == "__main__":
    unittest.main()
