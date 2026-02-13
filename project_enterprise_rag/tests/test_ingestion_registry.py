import tempfile
import unittest
from pathlib import Path

from ingestion.file_registry import register_files


class FileRegistryTests(unittest.TestCase):
    def test_register_files_deduplicates_by_hash(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            registry_path = base / "file_registry.json"

            file_a = base / "a.txt"
            file_b = base / "b.txt"
            file_c = base / "c.txt"
            file_a.write_text("same content", encoding="utf-8")
            file_b.write_text("same content", encoding="utf-8")
            file_c.write_text("different content", encoding="utf-8")

            first = register_files([str(file_a), str(file_b)], registry_path)
            self.assertEqual(len(first["new_files"]), 1)
            self.assertEqual(len(first["existing_files"]), 1)

            second = register_files([str(file_c)], registry_path)
            self.assertEqual(len(second["new_files"]), 1)
            self.assertEqual(len(second["registry"]["files"]), 2)


if __name__ == "__main__":
    unittest.main()

