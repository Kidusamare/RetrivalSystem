from __future__ import annotations

import shutil
from pathlib import Path

from config.settings import LocalSettings


INDEX_FILES = (
    "docstore.json",
    "index_store.json",
    "default__vector_store.json",
)


def index_dir_ready(index_dir: Path) -> bool:
    return all((index_dir / file_name).exists() for file_name in INDEX_FILES)


def get_runtime_index_dir(settings: LocalSettings) -> Path:
    if index_dir_ready(settings.index_active_dir):
        return settings.index_active_dir
    if index_dir_ready(settings.storage_dir):
        return settings.storage_dir
    return settings.index_active_dir


def prepare_staging_index_dir(settings: LocalSettings, job_id: str) -> Path:
    staging_dir = settings.index_staging_root / job_id
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    runtime_dir = get_runtime_index_dir(settings)
    if runtime_dir.exists() and index_dir_ready(runtime_dir):
        for name in INDEX_FILES:
            source = runtime_dir / name
            if source.exists():
                shutil.copy2(source, staging_dir / name)

    return staging_dir


def activate_staging_index(settings: LocalSettings, staging_dir: Path) -> Path:
    active_dir = settings.index_active_dir
    backup_dir = settings.storage_dir / "index_backup"

    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    active_dir.parent.mkdir(parents=True, exist_ok=True)
    if active_dir.exists():
        active_dir.rename(backup_dir)

    staging_dir.rename(active_dir)

    if backup_dir.exists():
        shutil.rmtree(backup_dir)

    return active_dir
