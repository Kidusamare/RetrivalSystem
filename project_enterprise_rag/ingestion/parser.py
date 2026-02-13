from pathlib import Path
from typing import Iterable, Sequence

from llama_index.core import Document, SimpleDirectoryReader


def validate_supported_file(path: str, allowed_extensions: Sequence[str]) -> Path:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        raise FileNotFoundError(f"File does not exist: {file_path}")
    if file_path.suffix.lower() not in set(ext.lower() for ext in allowed_extensions):
        raise ValueError(f"Unsupported file type: {file_path.suffix} ({file_path.name})")
    return file_path


def load_documents_from_files(
    file_paths: Iterable[str],
    allowed_extensions: Sequence[str],
) -> list[Document]:
    documents: list[Document] = []

    for path in file_paths:
        file_path = validate_supported_file(path, allowed_extensions)
        loaded = SimpleDirectoryReader(input_files=[str(file_path)]).load_data()

        for doc in loaded:
            metadata = dict(doc.metadata or {})
            metadata["source_path"] = str(file_path)
            metadata["file_name"] = file_path.name
            documents.append(Document(text=doc.text, metadata=metadata))

    return documents

