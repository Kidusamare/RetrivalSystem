import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            data = handle.read(chunk_size)
            if not data:
                break
            sha.update(data)
    return sha.hexdigest()


def load_registry(registry_path: Path) -> Dict:
    if not registry_path.exists():
        return {"files": []}
    with registry_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if "files" not in data or not isinstance(data["files"], list):
        return {"files": []}
    return data


def save_registry(registry_path: Path, registry: Dict) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2, ensure_ascii=False)


def list_registered_files(registry_path: Path) -> List[Dict]:
    return load_registry(registry_path)["files"]


def register_files(file_paths: Iterable[str], registry_path: Path) -> Dict:
    registry = load_registry(registry_path)
    existing_by_hash = {item["sha256"]: item for item in registry["files"]}

    new_files: List[Dict] = []
    existing_files: List[Dict] = []

    for raw_path in file_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            continue

        sha = _hash_file(path)
        if sha in existing_by_hash:
            existing_files.append(existing_by_hash[sha])
            continue

        record = {
            "doc_id": sha[:12],
            "path": str(path),
            "file_name": path.name,
            "sha256": sha,
            "size_bytes": path.stat().st_size,
            "indexed_at": _utc_now_iso(),
            "status": "indexed",
        }
        registry["files"].append(record)
        existing_by_hash[sha] = record
        new_files.append(record)

    save_registry(registry_path, registry)
    return {
        "new_files": new_files,
        "existing_files": existing_files,
        "registry": registry,
    }

