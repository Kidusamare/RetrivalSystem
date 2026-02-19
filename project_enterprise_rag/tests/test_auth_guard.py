import unittest

from db.session import run_migrations
from services.job_service import bootstrap_api_keys, verify_api_key


class AuthGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()
        bootstrap_api_keys(["unit-test-key"])

    def test_verify_api_key_accepts_seeded_value(self):
        self.assertTrue(verify_api_key("unit-test-key"))

    def test_verify_api_key_rejects_invalid_value(self):
        self.assertFalse(verify_api_key("definitely-wrong"))


if __name__ == "__main__":
    unittest.main()
