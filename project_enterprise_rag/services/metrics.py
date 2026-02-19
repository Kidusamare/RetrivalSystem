from __future__ import annotations

from collections import defaultdict
from threading import Lock


_lock = Lock()
_counters = defaultdict(int)
_durations = defaultdict(float)


def inc_counter(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def observe_duration(name: str, value: float) -> None:
    with _lock:
        _durations[name] += float(value)


def render_metrics() -> str:
    lines = []
    with _lock:
        for name, value in sorted(_counters.items()):
            lines.append(f"{name} {value}")
        for name, value in sorted(_durations.items()):
            lines.append(f"{name}_seconds_sum {value:.6f}")
    return "\n".join(lines) + "\n"
