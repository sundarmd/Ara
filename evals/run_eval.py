#!/usr/bin/env python3
"""
Lightweight HTTP/SSE eval runner for Ara.

The golden file is YAML-compatible JSON, so this runner stays stdlib-only.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INSUFFICIENT_CONTEXT_MARKERS = [
    "insufficient context",
    "not enough information",
    "do not have enough",
    "cannot determine",
    "can't determine",
]


@dataclass
class EvalResult:
    case_id: str
    passed: bool
    failures: list[str]


def load_cases(path: Path) -> list[dict[str, Any]]:
    try:
        cases = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"{path} must be YAML-compatible JSON so evals run without extra dependencies: {exc}"
        ) from exc

    if not isinstance(cases, list):
        raise SystemExit(f"{path} must contain a list of eval cases")

    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise SystemExit(f"case {index} must be an object")
        if not case.get("id"):
            raise SystemExit(f"case {index} is missing id")
        if not case.get("question"):
            raise SystemExit(f"case {case.get('id', index)} is missing question")
        if not isinstance(case.get("expect", {}), dict):
            raise SystemExit(f"case {case['id']} expect must be an object")

    return cases


def parse_sse_line(line: bytes) -> dict[str, Any] | None:
    text = line.decode("utf-8").strip()
    if not text.startswith("data: "):
        return None

    payload = text[6:]
    if not payload or payload == "[DONE]":
        return None
    return json.loads(payload)


def run_chat_case(
    api_url: str,
    case: dict[str, Any],
    timeout: float,
    api_key: str | None,
) -> dict[str, Any]:
    body = {
        "messages": [
            {
                "role": "user",
                "content": case["question"],
            }
        ],
    }
    if case.get("bank"):
        body["bank"] = case["bank"]
    if case.get("asset_class"):
        body["asset_class"] = case["asset_class"]

    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    if api_key:
        headers["X-API-Key"] = api_key

    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/chat/stream",
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    answer_parts: list[str] = []
    complete_event: dict[str, Any] = {}
    error_event: dict[str, Any] | None = None

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                event = parse_sse_line(raw_line)
                if not event:
                    continue
                if event.get("type") == "token":
                    answer_parts.append(event.get("content", ""))
                elif event.get("type") == "complete":
                    complete_event = event
                elif event.get("type") == "error":
                    error_event = event
                    break
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {exc.code}: {error_body}"}
    except urllib.error.URLError as exc:
        return {"error": f"Request failed: {exc.reason}"}

    if error_event:
        return {"error": error_event.get("message", "unknown stream error")}

    answer = complete_event.get("answer") or "".join(answer_parts)
    return {
        "answer": answer,
        "sources": complete_event.get("sources") or [],
        "recommendations": complete_event.get("recommendations") or [],
    }


def check_case(case: dict[str, Any], payload: dict[str, Any]) -> EvalResult:
    failures: list[str] = []
    expect = case.get("expect", {})

    if payload.get("error"):
        return EvalResult(case["id"], False, [payload["error"]])

    answer = str(payload.get("answer") or "")
    answer_lower = answer.lower()
    sources = payload.get("sources") or []
    recommendations = payload.get("recommendations") or []

    min_sources = expect.get("min_sources")
    if min_sources is not None and len(sources) < int(min_sources):
        failures.append(f"expected at least {min_sources} sources, got {len(sources)}")

    min_recommendations = expect.get("min_recommendations")
    if min_recommendations is not None and len(recommendations) < int(min_recommendations):
        failures.append(
            f"expected at least {min_recommendations} recommendations, got {len(recommendations)}"
        )

    for needle in expect.get("answer_must_include", []):
        if str(needle).lower() not in answer_lower:
            failures.append(f"answer missing required text: {needle}")

    include_any = [str(item).lower() for item in expect.get("answer_must_include_any", [])]
    if include_any and not any(item in answer_lower for item in include_any):
        failures.append(f"answer missing any of: {', '.join(include_any)}")

    if expect.get("insufficient_context"):
        markers = include_any or DEFAULT_INSUFFICIENT_CONTEXT_MARKERS
        if not any(marker in answer_lower for marker in markers):
            failures.append("answer did not signal insufficient context")

    required_fields = expect.get("required_recommendation_fields", [])
    for index, recommendation in enumerate(recommendations, start=1):
        missing = [field for field in required_fields if not recommendation.get(field)]
        if missing:
            failures.append(f"recommendation {index} missing fields: {', '.join(missing)}")

    return EvalResult(case["id"], not failures, failures)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Ara golden-question evals")
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--questions", default="evals/golden_questions.yaml")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate eval file only")
    args = parser.parse_args()

    cases = load_cases(Path(args.questions))
    if args.dry_run:
        print(json.dumps({"status": "ok", "case_count": len(cases)}, indent=2))
        return 0

    results: list[EvalResult] = []
    for case in cases:
        payload = run_chat_case(args.api_url, case, args.timeout, args.api_key)
        results.append(check_case(case, payload))

    summary = {
        "passed": sum(1 for result in results if result.passed),
        "failed": sum(1 for result in results if not result.passed),
        "results": [
            {
                "id": result.case_id,
                "passed": result.passed,
                "failures": result.failures,
            }
            for result in results
        ],
    }
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
