import unittest
import uuid

from sqlalchemy import select

from db.models import Chunk, Document
from db.session import run_migrations, session_scope
from services.job_service import upsert_documents_and_chunks


class DocumentDedupeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        run_migrations()

    def test_upsert_documents_dedupes_patent_id_and_maps_chunks(self):
        token = uuid.uuid4().hex[:10]
        patent_id = f"P{token}"
        first_doc_id = f"doc_a_{token}"
        second_doc_id = f"doc_b_{token}"
        first_chunk_id = f"chunk_a_{token}"
        second_chunk_id = f"chunk_b_{token}"

        upsert_documents_and_chunks(
            documents=[
                {
                    "id": first_doc_id,
                    "source_type": "patentsview",
                    "doc_key": f"patent:{patent_id}",
                    "doc_id": first_doc_id,
                    "file_name": f"{first_doc_id}.md",
                    "source_path": "https://example.org/one",
                    "sha256": None,
                    "patent_id": patent_id,
                    "metadata_json": {},
                }
            ],
            chunks=[
                {
                    "chunk_id": first_chunk_id,
                    "document_id": first_doc_id,
                    "doc_id": first_doc_id,
                    "content": "chunk one",
                    "metadata_json": {},
                }
            ],
        )

        upsert_documents_and_chunks(
            documents=[
                {
                    "id": second_doc_id,
                    "source_type": "patentsview",
                    "doc_key": f"legacy:{patent_id}",
                    "doc_id": second_doc_id,
                    "file_name": f"{second_doc_id}.md",
                    "source_path": "https://example.org/two",
                    "sha256": None,
                    "patent_id": patent_id,
                    "metadata_json": {"updated": True},
                }
            ],
            chunks=[
                {
                    "chunk_id": second_chunk_id,
                    "document_id": second_doc_id,
                    "doc_id": second_doc_id,
                    "content": "chunk two",
                    "metadata_json": {},
                }
            ],
        )

        with session_scope() as session:
            docs = session.execute(select(Document).where(Document.patent_id == patent_id)).scalars().all()
            self.assertEqual(len(docs), 1)
            canonical_id = docs[0].id

            second_chunk = session.execute(select(Chunk).where(Chunk.chunk_id == second_chunk_id)).scalar_one()
            self.assertEqual(second_chunk.document_id, canonical_id)
            self.assertEqual(second_chunk.doc_id, canonical_id)


if __name__ == "__main__":
    unittest.main()
