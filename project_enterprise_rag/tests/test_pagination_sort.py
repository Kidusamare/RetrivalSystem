import unittest

from retrieval.retriever import paginate_records, sort_chunk_records


class PaginationSortTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            {"source": "b_file.txt", "score": 0.7, "date_ts": 100},
            {"source": "a_file.txt", "score": 0.9, "date_ts": 300},
            {"source": "c_file.txt", "score": 0.8, "date_ts": 200},
        ]

    def test_sort_by_source(self):
        sorted_rows = sort_chunk_records(self.records, sort_by="source")
        self.assertEqual([row["source"] for row in sorted_rows], ["a_file.txt", "b_file.txt", "c_file.txt"])

    def test_sort_by_date_desc(self):
        sorted_rows = sort_chunk_records(self.records, sort_by="date")
        self.assertEqual([row["date_ts"] for row in sorted_rows], [300, 200, 100])

    def test_pagination_bounds(self):
        page = paginate_records(self.records, page=2, page_size=2)
        self.assertEqual(page["page"], 2)
        self.assertEqual(page["total_pages"], 2)
        self.assertEqual(len(page["items"]), 1)


if __name__ == "__main__":
    unittest.main()
