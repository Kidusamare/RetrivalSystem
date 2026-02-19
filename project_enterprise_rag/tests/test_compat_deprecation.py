import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional in minimal host envs
    TestClient = None

if TestClient is not None:
    from api_app import app


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class CompatDeprecationTests(unittest.TestCase):
    def test_legacy_routes_marked_deprecated_in_openapi(self):
        client = TestClient(app)
        response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        paths = spec.get("paths", {})

        targets = [
            ("/query/plan", "post"),
            ("/query/search", "post"),
            ("/ingest", "post"),
            ("/ingest/status", "get"),
        ]
        for path, method in targets:
            route = (paths.get(path) or {}).get(method)
            self.assertIsNotNone(route, msg=f"missing route {method.upper()} {path}")
            self.assertTrue(route.get("deprecated"), msg=f"route not deprecated: {method.upper()} {path}")

        client.close()


if __name__ == "__main__":
    unittest.main()
