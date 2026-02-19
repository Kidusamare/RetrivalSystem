import argparse
import importlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import ops.cli as cli


class OpsCliTests(unittest.TestCase):
    def test_cli_import_keeps_evaluation_runner_lazy(self):
        sys.modules.pop("evaluation.runner", None)
        importlib.reload(cli)
        self.assertNotIn("evaluation.runner", sys.modules)

    def test_parser_includes_phase5_ops_commands(self):
        parser = cli.build_parser()
        sub_actions = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
        self.assertEqual(len(sub_actions), 1)
        commands = set(sub_actions[0].choices.keys())
        for name in {"ingest-files", "sync-patentsview", "job-status", "list-jobs", "evaluate"}:
            self.assertIn(name, commands)

    @patch("ops.cli.time.sleep", return_value=None)
    @patch("ops.cli._get")
    def test_job_status_watch_until_terminal(self, mock_get, _mock_sleep):
        mock_get.side_effect = [
            {"id": "job_1", "status": "running", "progress": 0.2},
            {"id": "job_1", "status": "succeeded", "progress": 1.0},
        ]
        args = SimpleNamespace(
            base_url="http://127.0.0.1:8000",
            api_key="unit-test-key",
            job_id="job_1",
            watch=True,
            interval=0.1,
            timeout=30.0,
        )

        rc = cli.cmd_job_status(args)

        self.assertEqual(rc, 0)
        self.assertEqual(mock_get.call_count, 2)

    @patch("ops.cli.time.sleep", return_value=None)
    @patch("ops.cli.time.monotonic")
    @patch("ops.cli._get")
    def test_job_status_watch_timeout(self, mock_get, mock_monotonic, _mock_sleep):
        mock_get.return_value = {"id": "job_2", "status": "running", "progress": 0.4}
        mock_monotonic.side_effect = [0.0, 0.6, 1.1]
        args = SimpleNamespace(
            base_url="http://127.0.0.1:8000",
            api_key="unit-test-key",
            job_id="job_2",
            watch=True,
            interval=0.1,
            timeout=1.0,
        )

        rc = cli.cmd_job_status(args)

        self.assertEqual(rc, 2)

    @patch("ops.cli._get", return_value={"jobs": []})
    def test_list_jobs_builds_status_query(self, mock_get):
        args = SimpleNamespace(
            base_url="http://127.0.0.1:8000",
            api_key="unit-test-key",
            status="queued",
            limit=15,
        )

        rc = cli.cmd_list_jobs(args)

        self.assertEqual(rc, 0)
        called_path = mock_get.call_args.args[2]
        self.assertIn("status=queued", called_path)
        self.assertIn("limit=15", called_path)

    @patch("ops.cli._post", return_value={"job_id": "job_1", "status": "queued"})
    def test_ingest_files_payload_supports_deep_memory(self, mock_post):
        args = SimpleNamespace(
            base_url="http://127.0.0.1:8000",
            api_key="unit-test-key",
            files=["/tmp/a.md"],
            chunk_size=700,
            chunk_overlap=80,
            deep_memory=True,
        )

        rc = cli.cmd_ingest_files(args)

        self.assertEqual(rc, 0)
        payload = mock_post.call_args.args[3]
        self.assertTrue(payload["options"]["deep_memory"])

    @patch("ops.cli._post", return_value={"job_id": "job_2", "status": "queued"})
    def test_patentsview_payload_supports_deep_memory(self, mock_post):
        args = SimpleNamespace(
            base_url="http://127.0.0.1:8000",
            api_key="unit-test-key",
            keywords=["semiconductor"],
            max_records=50,
            chunk_size=700,
            chunk_overlap=80,
            deep_memory=True,
        )

        rc = cli.cmd_sync_patentsview(args)

        self.assertEqual(rc, 0)
        payload = mock_post.call_args.args[3]
        self.assertTrue(payload["options"]["deep_memory"])


if __name__ == "__main__":
    unittest.main()
