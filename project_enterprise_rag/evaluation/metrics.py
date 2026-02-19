from __future__ import annotations

from typing import Iterable, Sequence


def precision_at_k(predicted_doc_ids: Sequence[str], relevant_doc_ids: Iterable[str], k: int = 10) -> float:
    predictions = [str(doc_id) for doc_id in predicted_doc_ids][: max(1, int(k))]
    if not predictions:
        return 0.0

    relevant = {str(doc_id) for doc_id in relevant_doc_ids}
    hits = sum(1 for doc_id in predictions if doc_id in relevant)
    denom = max(1, min(int(k), len(predictions)))
    return hits / denom
