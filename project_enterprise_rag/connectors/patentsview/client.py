from __future__ import annotations

import json
import time
from typing import List
from urllib.parse import urlencode

import requests

from connectors.patentsview.types import PatentRecord, PatentsViewQuery


def _build_query_payload(keywords: List[str]) -> dict:
    phrase = " ".join([token.strip() for token in keywords if token and token.strip()])
    return {
        "_or": [
            {"_text_any": {"patent_title": phrase}},
            {"_text_any": {"patent_abstract": phrase}},
        ]
    }


def _build_fields() -> List[str]:
    return ["patent_id", "patent_title", "patent_abstract", "patent_date"]


def _request_once(*, base_url: str, api_key: str, query_payload: dict, fields: List[str], page_size: int, after: str | None, timeout_seconds: int) -> dict:
    options = {"size": page_size}
    if after:
        options["after"] = after

    params = {
        "q": json.dumps(query_payload, separators=(",", ":")),
        "f": json.dumps(fields, separators=(",", ":")),
        "o": json.dumps(options, separators=(",", ":")),
        "s": json.dumps([{"patent_id": "asc"}], separators=(",", ":")),
    }

    headers = {}
    if api_key:
        headers["X-Api-Key"] = api_key

    url = f"{base_url}?{urlencode(params)}"
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def fetch_patents(*, base_url: str, api_key: str, query: PatentsViewQuery, timeout_seconds: int = 45, retries: int = 3) -> List[PatentRecord]:
    query_payload = _build_query_payload(query.keywords)
    fields = _build_fields()

    after = None
    collected: List[PatentRecord] = []

    while len(collected) < max(1, int(query.max_records)):
        page_size = min(100, query.max_records - len(collected))

        payload = None
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                payload = _request_once(
                    base_url=base_url,
                    api_key=api_key,
                    query_payload=query_payload,
                    fields=fields,
                    page_size=page_size,
                    after=after,
                    timeout_seconds=timeout_seconds,
                )
                break
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < retries:
                    time.sleep(0.5 * attempt)

        if payload is None:
            raise RuntimeError(f"PatentsView request failed after retries: {last_exc}")

        patents = payload.get("patents") or []
        if not patents:
            break

        for raw in patents:
            patent_id = str(raw.get("patent_id") or "").strip()
            if not patent_id:
                continue
            record = PatentRecord(
                patent_id=patent_id,
                title=str(raw.get("patent_title") or "").strip(),
                abstract=str(raw.get("patent_abstract") or "").strip(),
                date=str(raw.get("patent_date") or "").strip(),
                source_url=f"https://patents.google.com/patent/US{patent_id}",
            )
            collected.append(record)

        after = str((patents[-1] or {}).get("patent_id") or "").strip()
        if not after:
            break

    deduped = {}
    for record in collected:
        deduped[record.patent_id] = record
    return list(deduped.values())[: query.max_records]
