import unittest
from unittest.mock import patch

import requests

from connectors.patentsview.client import fetch_patents
from connectors.patentsview.types import PatentsViewQuery


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class PatentsViewClientTests(unittest.TestCase):
    @patch("connectors.patentsview.client.requests.get")
    def test_fetch_patents_dedupes_by_patent_id(self, mock_get):
        mock_get.side_effect = [
            _FakeResponse(
                {
                    "patents": [
                        {
                            "patent_id": "123",
                            "patent_title": "Semiconductor interconnect stack",
                            "patent_abstract": "Dielectric barrier for vias",
                            "patent_date": "2020-01-01",
                        },
                        {
                            "patent_id": "123",
                            "patent_title": "Duplicate",
                            "patent_abstract": "Duplicate",
                            "patent_date": "2020-01-01",
                        },
                    ]
                }
            ),
            _FakeResponse({"patents": []}),
        ]

        rows = fetch_patents(
            base_url="https://search.patentsview.org/api/v1/patent/",
            api_key="",
            query=PatentsViewQuery(keywords=["semiconductor"], max_records=10),
            timeout_seconds=10,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].patent_id, "123")
        self.assertIn("patents.google.com", rows[0].source_url)

    @patch("connectors.patentsview.client.requests.get")
    def test_fetch_patents_retries_then_succeeds(self, mock_get):
        mock_get.side_effect = [
            requests.Timeout("network timeout"),
            _FakeResponse(
                {
                    "patents": [
                        {
                            "patent_id": "999",
                            "patent_title": "Retry success",
                            "patent_abstract": "Bounded retries worked",
                            "patent_date": "2021-02-03",
                        }
                    ]
                }
            ),
        ]

        rows = fetch_patents(
            base_url="https://search.patentsview.org/api/v1/patent/",
            api_key="",
            query=PatentsViewQuery(keywords=["retry"], max_records=1),
            timeout_seconds=10,
            retries=2,
        )

        self.assertEqual(mock_get.call_count, 2)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].patent_id, "999")


if __name__ == "__main__":
    unittest.main()
