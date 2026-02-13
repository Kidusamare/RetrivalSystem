from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Tuple


@dataclass(frozen=True)
class LocalSettings:
    project_root: Path
    storage_dir: Path
    registry_path: Path
    top_k: int = 5
    chunk_size: int = 700
    chunk_overlap: int = 80
    max_filter_suggestions: int = 8
    allowed_extensions: Tuple[str, ...] = (
        ".txt",
        ".md",
        ".pdf",
        ".docx",
        ".csv",
        ".json",
        ".html",
    )


@lru_cache(maxsize=1)
def get_settings() -> LocalSettings:
    project_root = Path(__file__).resolve().parents[1]
    storage_dir = project_root / "storage"
    registry_path = storage_dir / "file_registry.json"
    return LocalSettings(
        project_root=project_root,
        storage_dir=storage_dir,
        registry_path=registry_path,
    )


def resolve_paths(settings: LocalSettings) -> LocalSettings:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    if not settings.registry_path.exists():
        settings.registry_path.write_text('{"files": []}\n', encoding="utf-8")
    return replace(settings)

