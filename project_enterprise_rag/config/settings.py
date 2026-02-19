import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple


@dataclass(frozen=True)
class LocalSettings:
    project_root: Path
    storage_dir: Path
    registry_path: Path
    state_db_path: Path
    index_active_dir: Path
    index_staging_root: Path
    worker_heartbeat_file: Path
    top_k: int = 10
    chunk_size: int = 700
    chunk_overlap: int = 80
    max_filter_suggestions: int = 8
    default_mode: str = "hybrid"
    default_page_size: int = 10
    max_page_size: int = 50
    planner_backend: str = "rules"
    response_backend: str = "none"
    planner_timeout_seconds: int = 12
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_planner_model: str = "qwen3:0.6b"
    ollama_response_model: str = "qwen3:1.7b"
    api_key_seed_values: Tuple[str, ...] = ("dev-local-key",)
    worker_poll_seconds: int = 3
    worker_heartbeat_ttl_seconds: int = 30
    worker_name: str = "worker-1"
    patentsview_api_url: str = "https://search.patentsview.org/api/v1/patent/"
    patentsview_timeout_seconds: int = 45
    patentsview_retries: int = 3
    patentsview_api_key: str = ""
    ingestion_deep_memory_enabled: bool = False
    deep_memory_buffer_size: int = 1
    deep_memory_breakpoint_percentile: int = 95
    ops_api_base_url: str = "http://127.0.0.1:8000"
    ops_api_key: str = "dev-local-key"
    supported_modes: Tuple[str, ...] = ("hybrid", "semantic", "keyword")
    supported_sorts: Tuple[str, ...] = ("relevance", "source", "date")
    allowed_extensions: Tuple[str, ...] = (
        ".txt",
        ".md",
        ".pdf",
        ".docx",
        ".csv",
        ".json",
        ".html",
    )


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _str_env(name: str, default: str) -> str:
    raw = os.getenv(name)
    return raw.strip() if raw and raw.strip() else default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    cleaned = raw.strip().lower()
    if cleaned in {"1", "true", "yes", "y", "on"}:
        return True
    if cleaned in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _csv_env(name: str, default: str) -> Tuple[str, ...]:
    raw = os.getenv(name, default)
    values: List[str] = []
    seen = set()
    for token in (raw or "").split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        values.append(cleaned)
    if not values:
        return ("dev-local-key",)
    return tuple(values)


@lru_cache(maxsize=1)
def get_settings() -> LocalSettings:
    project_root = Path(__file__).resolve().parents[1]
    storage_dir = project_root / "storage"
    registry_path = storage_dir / "file_registry.json"
    state_db_path = storage_dir / "state.db"
    index_active_dir = storage_dir / "index_active"
    index_staging_root = storage_dir / "index_staging"
    worker_heartbeat_file = storage_dir / "worker_heartbeat.json"

    default_mode = _str_env("DEFAULT_SEARCH_MODE", "hybrid").lower()
    if default_mode not in ("hybrid", "semantic", "keyword"):
        default_mode = "hybrid"

    planner_backend = _str_env("PLANNER_BACKEND", "rules").lower()
    if planner_backend not in ("rules", "local_llm"):
        planner_backend = "rules"

    response_backend = _str_env("RESPONSE_BACKEND", "none").lower()
    if response_backend not in ("none", "local_llm"):
        response_backend = "none"

    return LocalSettings(
        project_root=project_root,
        storage_dir=storage_dir,
        registry_path=registry_path,
        state_db_path=state_db_path,
        index_active_dir=index_active_dir,
        index_staging_root=index_staging_root,
        worker_heartbeat_file=worker_heartbeat_file,
        top_k=_int_env("DEFAULT_TOP_K", 10),
        chunk_size=_int_env("CHUNK_SIZE", 700),
        chunk_overlap=_int_env("CHUNK_OVERLAP", 80),
        max_filter_suggestions=_int_env("MAX_FILTER_SUGGESTIONS", 8),
        default_mode=default_mode,
        default_page_size=_int_env("DEFAULT_PAGE_SIZE", 10),
        max_page_size=_int_env("MAX_PAGE_SIZE", 50),
        planner_backend=planner_backend,
        response_backend=response_backend,
        planner_timeout_seconds=_int_env("PLANNER_TIMEOUT_SECONDS", 12),
        ollama_base_url=_str_env("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_planner_model=_str_env("OLLAMA_MODEL_PLANNER", "qwen3:0.6b"),
        ollama_response_model=_str_env("OLLAMA_MODEL_RESPONSE", "qwen3:1.7b"),
        api_key_seed_values=_csv_env("API_KEYS", "dev-local-key"),
        worker_poll_seconds=_int_env("WORKER_POLL_SECONDS", 3),
        worker_heartbeat_ttl_seconds=_int_env("WORKER_HEARTBEAT_TTL_SECONDS", 30),
        worker_name=_str_env("WORKER_NAME", "worker-1"),
        patentsview_api_url=_str_env("PATENTSVIEW_API_URL", "https://search.patentsview.org/api/v1/patent/"),
        patentsview_timeout_seconds=_int_env("PATENTSVIEW_TIMEOUT_SECONDS", 45),
        patentsview_retries=_int_env("PATENTSVIEW_RETRIES", 3),
        patentsview_api_key=_str_env("PATENTSVIEW_API_KEY", ""),
        ingestion_deep_memory_enabled=_bool_env("INGESTION_DEEP_MEMORY_ENABLED", False),
        deep_memory_buffer_size=_int_env("DEEP_MEMORY_BUFFER_SIZE", 1),
        deep_memory_breakpoint_percentile=max(1, min(99, _int_env("DEEP_MEMORY_BREAKPOINT_PERCENTILE", 95))),
        ops_api_base_url=_str_env("OPS_API_BASE_URL", "http://127.0.0.1:8000"),
        ops_api_key=_str_env("OPS_API_KEY", "dev-local-key"),
    )


def resolve_paths(settings: LocalSettings) -> LocalSettings:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.index_active_dir.mkdir(parents=True, exist_ok=True)
    settings.index_staging_root.mkdir(parents=True, exist_ok=True)
    if not settings.registry_path.exists():
        settings.registry_path.write_text('{"files": []}\n', encoding="utf-8")
    return replace(settings)


def get_state_db_url(settings: LocalSettings) -> str:
    return f"sqlite:///{settings.state_db_path}"
