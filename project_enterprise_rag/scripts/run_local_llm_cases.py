#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List

import requests


def _contains_any(text: str, needles: List[str]) -> bool:
    lowered = (text or "").lower()
    return any((needle or "").lower() in lowered for needle in needles)


def _post(base_url: str, api_key: str, path: str, payload: Dict) -> Dict:
    response = requests.post(
        base_url.rstrip("/") + path,
        headers={"X-API-Key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


def run_cases(base_url: str, api_key: str, cases_path: Path) -> int:
    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases = payload.get("cases") or []
    if not cases:
        print(f"No cases found in {cases_path}", file=sys.stderr)
        return 2

    failures = 0
    for case in cases:
        case_id = case.get("id", "unknown")
        print(f"\\n[case] {case_id}")
        plan_req = case.get("plan_request") or {}
        search_req = case.get("search_request") or {}
        expected = case.get("expected_signals") or {}

        try:
            plan_resp = _post(base_url, api_key, "/v1/search/plan", plan_req)
            search_resp = _post(base_url, api_key, "/v1/search", search_req)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  FAIL: request error: {exc}")
            continue

        planned_query = str(plan_resp.get("planned_query") or "")
        answer = str(search_resp.get("answer") or "")
        chunk_text = " ".join(str(chunk.get("text") or "") for chunk in (search_resp.get("chunks") or []))
        response_text = f"{answer} {chunk_text}".strip()

        plan_needles = expected.get("planned_query_contains_any") or []
        response_needles = expected.get("response_mentions_any") or []

        plan_ok = _contains_any(planned_query, plan_needles) if plan_needles else True
        response_ok = _contains_any(response_text, response_needles) if response_needles else True

        if plan_ok and response_ok:
            print("  PASS")
        else:
            failures += 1
            print("  FAIL")
            print(f"    planned_query: {planned_query}")
            print(f"    planner_needles: {plan_needles}")
            print(f"    response_needles: {response_needles}")
            print(f"    answer_preview: {answer[:220]}")

    if failures:
        print(f"\\nCompleted with {failures} failing case(s).", file=sys.stderr)
        return 1

    print("\\nAll local-LLM cases passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local-LLM planner/response test cases against /v1 API.")
    parser.add_argument(
        "--cases",
        default="datasets/semiconductor_ip_demo/test_cases/local_llm_cases.json",
        help="Path to case file",
    )
    parser.add_argument("--base-url", default=os.getenv("OPS_API_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.getenv("OPS_API_KEY", "dev-local-key"))
    args = parser.parse_args()

    return run_cases(
        base_url=args.base_url,
        api_key=args.api_key,
        cases_path=Path(args.cases),
    )


if __name__ == "__main__":
    raise SystemExit(main())
