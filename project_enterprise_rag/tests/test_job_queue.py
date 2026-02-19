import unittest

from db.session import run_migrations
from services.job_service import (
    claim_next_job,
    enqueue_job,
    get_job,
    list_jobs,
    mark_job_succeeded,
)


class JobQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def test_job_queue_lifecycle(self):
        queued = enqueue_job("local_files_ingest", {"file_paths": [], "options": {}})
        self.assertEqual(queued["status"], "queued")

        claimed = claim_next_job("test-worker")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.status, "running")

        mark_job_succeeded(claimed.id, {"message": "ok"})
        final_state = get_job(claimed.id)
        self.assertIsNotNone(final_state)
        self.assertEqual(final_state["status"], "succeeded")

    def test_rejects_unknown_job_type(self):
        with self.assertRaises(ValueError):
            enqueue_job("not-a-job-type", {})

    def test_rejects_invalid_status_filter(self):
        with self.assertRaises(ValueError):
            list_jobs(status="bogus-status")


if __name__ == "__main__":
    unittest.main()
