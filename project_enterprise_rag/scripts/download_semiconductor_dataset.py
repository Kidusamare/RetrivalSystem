#!/usr/bin/env python3
"""
Download a semiconductor-focused patent dataset for local RAG demo use.

Default source (no key):
- Hugging Face datasets server for `NortheasternUniversity/big_patent` rows.

Optional source (requires key):
- USPTO PatentSearch API (`search.patentsview.org`) for metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode

import requests


PATENTSVIEW_API_URL = "https://search.patentsview.org/api/v1/patent/"
HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
PDF_URL_TEMPLATE = "https://patentimages.storage.googleapis.com/pdfs/US{patent_id}.pdf"


CURATED_FILTERS = {
    "Semiconductor Wafer": ["wafer", "substrate", "silicon wafer"],
    "Doped Regions (N-type/P-type)": ["doped", "dopant", "n-type", "p-type", "implant"],
    "Insulating Layers (Dielectric)": ["dielectric", "insulating layer", "oxide", "low-k"],
    "Conductive Interconnects": ["interconnect", "via", "conductive", "metal line"],
    "Encapsulation": ["encapsulation", "passivation", "package", "molding"],
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


@dataclass
class FetchConfig:
    source: str
    api_key: str
    output_dir: Path
    max_records: int
    page_size: int
    max_scan_pages: int
    start_date: str
    download_pdfs: bool
    timeout_seconds: int
    query_seed: str
    hf_dataset: str
    hf_config: str
    hf_split: str


@dataclass
class FetchResult:
    records: List[Dict[str, Any]]
    scanned_pages: int
    scanned_rows: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download semiconductor patent docs for local demo (no API key needed by default).",
    )
    parser.add_argument(
        "--source",
        choices=["hf-big-patent", "patentsview"],
        default="hf-big-patent",
        help="Data source. Default uses Hugging Face rows API and does not require a key.",
    )
    parser.add_argument(
        "--output-dir",
        default="datasets/semiconductor_ip_demo",
        help="Directory to store downloaded dataset artifacts.",
    )
    parser.add_argument("--max-records", type=int, default=60, help="Total records to keep.")
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="Records fetched per request (HF rows API max is 100).",
    )
    parser.add_argument(
        "--max-scan-pages",
        type=int,
        default=60,
        help="Maximum pages to scan while collecting matching records.",
    )
    parser.add_argument(
        "--start-date",
        default="2012-01-01",
        help="Patent date lower bound (only used by patentsview source).",
    )
    parser.add_argument(
        "--query-seed",
        default="semiconductor wafer doped dielectric interconnect encapsulation",
        help="Core query terms used for relevance filtering.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("PATENTSVIEW_API_KEY", ""),
        help="PatentSearch API key (required only when --source patentsview).",
    )
    parser.add_argument(
        "--hf-dataset",
        default="NortheasternUniversity/big_patent",
        help="Hugging Face dataset id used when --source hf-big-patent.",
    )
    parser.add_argument(
        "--hf-config",
        default="h",
        help="Hugging Face dataset config (CPC section proxy). 'h' is electronics/electricity heavy.",
    )
    parser.add_argument(
        "--hf-split",
        default="train",
        help="Hugging Face split to read from.",
    )
    parser.add_argument(
        "--download-pdfs",
        action="store_true",
        help="Attempt to download patent PDFs (supported for patentsview numeric IDs only).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="HTTP timeout in seconds.",
    )
    return parser.parse_args()


def _normalize_text(value: Any) -> str:
    text = str(value or "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_keywords(seed: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9+-]*", seed.lower())
    seen = set()
    keywords: List[str] = []
    for token in tokens:
        if token in STOPWORDS or len(token) < 3:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)
    return keywords


def _matched_keywords(text: str, keywords: List[str]) -> List[str]:
    lower = text.lower()
    return [keyword for keyword in keywords if keyword in lower]


def _tag_filters(*texts: str) -> List[str]:
    haystack = " ".join(texts).lower()
    tags: List[str] = []
    for filter_name, keywords in CURATED_FILTERS.items():
        if any(keyword in haystack for keyword in keywords):
            tags.append(filter_name)
    return tags


def _build_patentsview_query(seed: str, start_date: str) -> Dict[str, Any]:
    return {
        "_and": [
            {"_gte": {"patent_date": start_date}},
            {
                "_or": [
                    {"_text_any": {"patent_title": seed}},
                    {"_text_any": {"patent_abstract": seed}},
                ]
            },
        ]
    }


def _build_patentsview_fields() -> List[str]:
    return [
        "patent_id",
        "patent_title",
        "patent_abstract",
        "patent_date",
        "patent_type",
        "cpc_current.cpc_group_id",
        "cpc_current.cpc_subgroup_id",
        "assignees.assignee_organization",
    ]


def _request_patentsview_patents(
    *,
    api_key: str,
    query: Dict[str, Any],
    fields: List[str],
    page_size: int,
    after: str | None,
    timeout_seconds: int,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {"size": page_size}
    if after:
        options["after"] = after

    params = {
        "q": json.dumps(query, separators=(",", ":")),
        "f": json.dumps(fields, separators=(",", ":")),
        "o": json.dumps(options, separators=(",", ":")),
        "s": json.dumps([{"patent_id": "asc"}], separators=(",", ":")),
    }
    headers = {"X-Api-Key": api_key}
    url = f"{PATENTSVIEW_API_URL}?{urlencode(params)}"
    response = requests.get(url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _to_patentsview_record(raw: Dict[str, Any], query_keywords: List[str]) -> Dict[str, Any]:
    patent_id = _normalize_text(raw.get("patent_id"))
    title = _normalize_text(raw.get("patent_title"))
    abstract = _normalize_text(raw.get("patent_abstract"))

    cpc_current = raw.get("cpc_current") or []
    cpc_groups = []
    for cpc_entry in cpc_current:
        group = _normalize_text(cpc_entry.get("cpc_group_id"))
        subgroup = _normalize_text(cpc_entry.get("cpc_subgroup_id"))
        if group or subgroup:
            cpc_groups.append({"group": group, "subgroup": subgroup})

    assignees = raw.get("assignees") or []
    assignee_orgs = []
    for assignee in assignees:
        org = _normalize_text(assignee.get("assignee_organization"))
        if org:
            assignee_orgs.append(org)

    combined_text = f"{title} {abstract}"
    return {
        "patent_id": patent_id,
        "patent_title": title,
        "patent_abstract": abstract,
        "patent_description_excerpt": "",
        "patent_date": _normalize_text(raw.get("patent_date")),
        "patent_type": _normalize_text(raw.get("patent_type")),
        "assignees": sorted(set(assignee_orgs)),
        "cpc_current": cpc_groups,
        "suggested_filter_tags": _tag_filters(title, abstract),
        "matched_query_keywords": _matched_keywords(combined_text, query_keywords),
        "source": "patentsview",
        "source_url": f"https://patents.google.com/patent/US{patent_id}",
    }


def _fetch_patentsview_records(config: FetchConfig, query_keywords: List[str]) -> FetchResult:
    query = _build_patentsview_query(config.query_seed, config.start_date)
    fields = _build_patentsview_fields()

    collected: List[Dict[str, Any]] = []
    after: str | None = None
    scanned_pages = 0
    scanned_rows = 0

    while len(collected) < config.max_records:
        size = min(config.page_size, config.max_records - len(collected))
        payload = _request_patentsview_patents(
            api_key=config.api_key,
            query=query,
            fields=fields,
            page_size=size,
            after=after,
            timeout_seconds=config.timeout_seconds,
        )
        patents = payload.get("patents") or []
        if not patents:
            break

        scanned_pages += 1
        scanned_rows += len(patents)
        batch = [_to_patentsview_record(item, query_keywords) for item in patents]
        collected.extend(batch)

        after = _normalize_text(batch[-1].get("patent_id"))
        if not after:
            break

    return FetchResult(records=_dedupe_by_patent_id(collected), scanned_pages=scanned_pages, scanned_rows=scanned_rows)


def _request_hf_rows(
    *,
    dataset: str,
    config_name: str,
    split: str,
    offset: int,
    length: int,
    timeout_seconds: int,
) -> Dict[str, Any]:
    params = {
        "dataset": dataset,
        "config": config_name,
        "split": split,
        "offset": offset,
        "length": length,
    }
    response = requests.get(HF_ROWS_URL, params=params, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def _first_sentence(text: str) -> str:
    text = _normalize_text(text)
    if not text:
        return "Untitled patent excerpt"
    parts = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)
    sentence = parts[0]
    if len(sentence) > 180:
        return sentence[:177].rstrip() + "..."
    return sentence


def _to_hf_record(
    raw_row: Dict[str, Any],
    *,
    hf_dataset: str,
    hf_config: str,
    hf_split: str,
    query_keywords: List[str],
) -> Dict[str, Any]:
    row_idx = raw_row.get("row_idx")
    row_payload = raw_row.get("row") or {}

    abstract = _normalize_text(row_payload.get("abstract"))
    description = _normalize_text(row_payload.get("description"))
    title = _first_sentence(abstract or description)

    combined_text = f"{title} {abstract} {description}"
    matched = _matched_keywords(combined_text, query_keywords)

    return {
        "patent_id": f"BIGPATENT-{hf_config}-{hf_split}-{row_idx}",
        "patent_title": title,
        "patent_abstract": abstract,
        "patent_description_excerpt": description[:4000],
        "patent_date": "",
        "patent_type": "utility",
        "assignees": [],
        "cpc_current": [],
        "suggested_filter_tags": _tag_filters(title, abstract, description),
        "matched_query_keywords": matched,
        "source": "hf-big-patent",
        "source_dataset": hf_dataset,
        "source_config": hf_config,
        "source_split": hf_split,
        "source_row_index": row_idx,
        "source_url": f"https://huggingface.co/datasets/{hf_dataset}",
    }


def _fetch_hf_records(config: FetchConfig, query_keywords: List[str]) -> FetchResult:
    collected: List[Dict[str, Any]] = []
    offset = 0
    scanned_pages = 0
    scanned_rows = 0
    page_size = min(config.page_size, 100)

    while len(collected) < config.max_records and scanned_pages < config.max_scan_pages:
        payload = _request_hf_rows(
            dataset=config.hf_dataset,
            config_name=config.hf_config,
            split=config.hf_split,
            offset=offset,
            length=page_size,
            timeout_seconds=config.timeout_seconds,
        )
        rows = payload.get("rows") or []
        if not rows:
            break

        scanned_pages += 1
        scanned_rows += len(rows)

        for raw_row in rows:
            record = _to_hf_record(
                raw_row,
                hf_dataset=config.hf_dataset,
                hf_config=config.hf_config,
                hf_split=config.hf_split,
                query_keywords=query_keywords,
            )
            if record["matched_query_keywords"] or record["suggested_filter_tags"]:
                collected.append(record)
                if len(collected) >= config.max_records:
                    break

        offset += len(rows)
        if len(rows) < page_size:
            break

    return FetchResult(records=_dedupe_by_patent_id(collected), scanned_pages=scanned_pages, scanned_rows=scanned_rows)


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_doc_markdown(path: Path, record: Dict[str, Any]) -> None:
    filter_line = ", ".join(record.get("suggested_filter_tags") or []) or "None"
    matched_line = ", ".join(record.get("matched_query_keywords") or []) or "None"
    assignees = ", ".join(record.get("assignees") or []) or "Unknown"

    cpc = ", ".join(
        [f"{item.get('group', '')}:{item.get('subgroup', '')}" for item in record.get("cpc_current") or []]
    ) or "Unknown"

    patent_id = _normalize_text(record.get("patent_id"))
    if patent_id.isdigit():
        display_patent_id = f"US{patent_id}"
    else:
        display_patent_id = patent_id

    date_value = _normalize_text(record.get("patent_date")) or "Unknown"
    type_value = _normalize_text(record.get("patent_type")) or "Unknown"
    source_value = _normalize_text(record.get("source")) or "Unknown"
    source_url = _normalize_text(record.get("source_url")) or ""

    body_lines = [
        f"# {display_patent_id} - {record.get('patent_title') or 'Untitled'}",
        "",
        f"- Document ID: `{display_patent_id}`",
        f"- Date: `{date_value}`",
        f"- Type: `{type_value}`",
        f"- Source: `{source_value}`",
        f"- Assignees: {assignees}",
        f"- CPC: {cpc}",
        f"- Suggested Filters: {filter_line}",
        f"- Matched Query Keywords: {matched_line}",
    ]

    if source_url:
        body_lines.append(f"- Source URL: {source_url}")

    body_lines.extend(
        [
            "",
            "## Abstract",
            record.get("patent_abstract") or "No abstract provided.",
            "",
            "## Description Excerpt",
            record.get("patent_description_excerpt") or "No description excerpt provided.",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(body_lines), encoding="utf-8")


def _download_pdf(patent_id: str, pdf_path: Path, timeout_seconds: int) -> bool:
    if not patent_id.isdigit():
        return False
    url = PDF_URL_TEMPLATE.format(patent_id=patent_id)
    try:
        response = requests.get(url, timeout=timeout_seconds)
        if response.status_code != 200 or "application/pdf" not in response.headers.get("content-type", ""):
            return False
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(response.content)
        return True
    except requests.RequestException:
        return False


def _dedupe_by_patent_id(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: Dict[str, Dict[str, Any]] = {}
    for record in records:
        patent_id = _normalize_text(record.get("patent_id"))
        if patent_id and patent_id not in deduped:
            deduped[patent_id] = record
    return list(deduped.values())


def _validate_config(args: argparse.Namespace) -> FetchConfig:
    if args.max_records <= 0:
        raise ValueError("--max-records must be > 0")
    if args.page_size <= 0:
        raise ValueError("--page-size must be > 0")
    if args.max_scan_pages <= 0:
        raise ValueError("--max-scan-pages must be > 0")
    if args.source == "patentsview" and not args.api_key:
        raise ValueError(
            "--source patentsview requires PATENTSVIEW_API_KEY (or --api-key). "
            "Use default --source hf-big-patent for no-key download."
        )

    output_dir = Path(args.output_dir).expanduser().resolve()
    return FetchConfig(
        source=args.source,
        api_key=args.api_key,
        output_dir=output_dir,
        max_records=args.max_records,
        page_size=args.page_size,
        max_scan_pages=args.max_scan_pages,
        start_date=args.start_date,
        download_pdfs=args.download_pdfs,
        timeout_seconds=args.timeout_seconds,
        query_seed=args.query_seed,
        hf_dataset=args.hf_dataset,
        hf_config=args.hf_config,
        hf_split=args.hf_split,
    )


def main() -> int:
    args = _parse_args()
    try:
        config = _validate_config(args)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    query_keywords = _extract_keywords(config.query_seed)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    if config.source == "hf-big-patent" and config.download_pdfs:
        print("WARN: --download-pdfs is ignored for hf-big-patent source (no patent IDs available).")

    try:
        if config.source == "patentsview":
            fetch_result = _fetch_patentsview_records(config, query_keywords)
        else:
            fetch_result = _fetch_hf_records(config, query_keywords)
    except requests.HTTPError as exc:
        print(f"ERROR: Remote request failed: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"ERROR: Network error during fetch: {exc}", file=sys.stderr)
        return 1

    records = fetch_result.records
    raw_dir = config.output_dir / "raw"
    docs_dir = config.output_dir / "docs"
    pdfs_dir = config.output_dir / "pdfs"

    _write_json(raw_dir / "curated_filter_options.json", {"filters": list(CURATED_FILTERS.keys())})
    _write_json(raw_dir / "records.json", {"records": records})

    pdf_downloaded = 0
    for record in records:
        patent_id = _normalize_text(record.get("patent_id"))
        doc_name = _safe_filename(patent_id or "record") + ".md"
        _write_doc_markdown(docs_dir / doc_name, record)

        if config.download_pdfs and config.source == "patentsview":
            ok = _download_pdf(
                patent_id=patent_id,
                pdf_path=pdfs_dir / f"US{patent_id}.pdf",
                timeout_seconds=config.timeout_seconds,
            )
            if ok:
                pdf_downloaded += 1

    manifest = {
        "source": config.source,
        "query_seed": config.query_seed,
        "query_keywords": query_keywords,
        "start_date": config.start_date,
        "max_records_requested": config.max_records,
        "records_downloaded": len(records),
        "scanned_pages": fetch_result.scanned_pages,
        "scanned_rows": fetch_result.scanned_rows,
        "pdf_downloaded": pdf_downloaded,
        "output_dir": str(config.output_dir),
        "filters": list(CURATED_FILTERS.keys()),
        "hf_dataset": config.hf_dataset,
        "hf_config": config.hf_config,
        "hf_split": config.hf_split,
    }
    _write_json(config.output_dir / "manifest.json", manifest)

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
