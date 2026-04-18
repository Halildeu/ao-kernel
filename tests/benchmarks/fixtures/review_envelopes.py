"""Canned envelopes for `governed_review` scenario.

codex-stub manifest carries two output_parse rules
(`review_findings` + `commit_message`); happy envelopes must
populate both (review benchmark asserts review_findings; stub
commit_message satisfies the walker but is not consumed).

Negative variant intentionally OMITS the review_findings field
(and commit_message) so the walker raises AdapterOutputParseError
→ driver surfaces `error.category=output_parse_failed`.
"""

from __future__ import annotations

from typing import Any


def review_agent_happy(
    *,
    score: float = 0.85,
    severity_distribution: tuple[tuple[str, str], ...] = (
        ("warning", "Minor style issue"),
        ("info", "Consider adding a docstring"),
    ),
) -> dict[str, Any]:
    findings = [
        {
            "file": "src/foo.py",
            "line": 7 + idx,
            "severity": severity,
            "message": msg,
            "suggestion": f"See review guide §{idx + 1}",
        }
        for idx, (severity, msg) in enumerate(severity_distribution)
    ]
    summary = f"Reviewed 1 file; produced {len(findings)} finding(s)."
    return {
        "status": "ok",
        "review_findings": {
            "schema_version": "1",
            "findings": findings,
            "summary": summary,
            "score": score,
        },
        "commit_message": {
            "schema_version": "1",
            "subject": "Acknowledge review",
            "body": "Stub commit_message; review benchmark does not consume.",
        },
        "cost_actual": {
            "tokens_input": 320,
            "tokens_output": 180,
            "time_seconds": 4.1,
        },
    }


def review_agent_missing_payload() -> dict[str, Any]:
    """Envelope that LOOKS ok but omits BOTH output_parse payloads.

    `_walk_output_parse` will raise `AdapterOutputParseError`
    (missing json_path key), the driver translates that into
    `_StepFailed(category="output_parse_failed")`.
    """
    return {
        "status": "ok",
        "cost_actual": {
            "tokens_input": 40,
            "tokens_output": 0,
            "time_seconds": 0.2,
        },
    }


__all__ = ["review_agent_happy", "review_agent_missing_payload"]
