"""Read-only repo-intelligence workflow surface output contract.

This module converts an accepted explicit workflow context into a small,
operator-visible output contract. It carries handoff/source metadata only; it
does not embed Markdown body text, inject prompts, write artifacts, expose MCP
tools, or call adapters.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]

SCHEMA_VERSION = "1"
ARTIFACT_KIND = "repo_intelligence_read_only_workflow_surface"
SUPPORT_TIER = "beta_read_only_workflow_surface"
MODE = "operator_visible_read_only_context_pointer"
CONSUMER = "workflow_runtime"

_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
_NAMESPACE_RE = re.compile(r"^repo_chunk::[^:]+::[^:]+::$")
_CHUNK_HEADING_RE = re.compile(r"^### \d+\. `(?P<path>.+):(?P<start>\d+)-(?P<end>\d+)`$")

_SAFETY_FALSE_FIELDS = {
    "hidden_prompt_injection": "safety_hidden_prompt_injection_not_false",
    "mcp_tool_exposure": "safety_mcp_tool_exposure_not_false",
    "root_export": "safety_root_export_not_false",
    "context_compiler_auto_feed": "safety_context_compiler_auto_feed_not_false",
    "vector_writes": "safety_vector_writes_not_false",
    "artifact_writes": "safety_artifact_writes_not_false",
    "live_adapter_execution": "safety_live_adapter_execution_not_false",
    "support_widening": "safety_support_widening_not_false",
    "production_platform_claim": "safety_production_platform_claim_not_false",
}


def build_repo_intelligence_read_only_workflow_surface(
    resolved_context: Mapping[str, Any] | None,
    *,
    project_root: Path,
) -> JsonDict:
    """Build a read-only workflow surface contract from accepted context.

    Disabled context is a no-op. Enabled-but-unaccepted context fails closed.
    Accepted context must still prove a current handoff file, matching digest,
    valid namespace, source artifact hashes, and current source chunks. The
    returned payload intentionally excludes Markdown content; callers may only
    pass the handoff Markdown as visible operator input.
    """
    if not resolved_context or resolved_context.get("enabled") is not True:
        return {
            "status": "disabled",
            "enabled": False,
            "decision": "repo_intelligence_read_only_workflow_surface_not_enabled",
        }

    findings: list[str] = []
    if _string(resolved_context.get("status")) != "accepted":
        findings.append("workflow_context_not_accepted")
    if _string(resolved_context.get("decision")) != "accepted_repo_intelligence_workflow_context":
        findings.append("workflow_context_decision_not_accepted")
    if _string(resolved_context.get("support_tier")) != "beta_explicit_read_only_workflow_context":
        findings.append("workflow_context_support_tier_invalid")
    if resolved_context.get("support_widening") is not False:
        findings.append("workflow_context_support_widening_not_false")
    if resolved_context.get("production_platform_claim") is not False:
        findings.append("workflow_context_production_platform_claim_not_false")
    if resolved_context.get("live_adapter_execution_allowed") is not False:
        findings.append("workflow_context_live_adapter_execution_allowed_not_false")

    context = _mapping(resolved_context.get("context"))
    source_metadata = _mapping(resolved_context.get("source_metadata"))
    safety = _mapping(resolved_context.get("safety"))
    _require_false_fields(safety, _SAFETY_FALSE_FIELDS, findings)

    if _string(context.get("mode")) != "visible_operator_handoff":
        findings.append("context_mode_not_visible_operator_handoff")
    if _string(context.get("consumer")) != CONSUMER:
        findings.append("context_consumer_not_workflow_runtime")
    if context.get("operator_visible") is not True:
        findings.append("context_operator_visible_not_true")
    if context.get("automatic_prompt_injection") is not False:
        findings.append("context_automatic_prompt_injection_not_false")
    if context.get("context_compiler_auto_feed") is not False:
        findings.append("context_context_compiler_auto_feed_not_false")
    if context.get("write_context_artifacts") is not False:
        findings.append("context_write_context_artifacts_not_false")
    if _string(context.get("handoff_support_tier")) != "beta_explicit_handoff":
        findings.append("context_handoff_support_tier_invalid")

    namespace = _string(source_metadata.get("vector_namespace_key_prefix"))
    repo_chunks_sha256 = _string(source_metadata.get("repo_chunks_sha256"))
    vector_index_sha256 = _string(source_metadata.get("repo_vector_index_manifest_sha256"))
    freshness_state = _string(source_metadata.get("freshness_state"))
    stale_candidates = source_metadata.get("stale_candidates")
    if not _NAMESPACE_RE.fullmatch(namespace):
        findings.append("namespace_invalid")
    if not _HEX64_RE.fullmatch(repo_chunks_sha256):
        findings.append("repo_chunks_sha256_invalid")
    if not _HEX64_RE.fullmatch(vector_index_sha256):
        findings.append("repo_vector_index_manifest_sha256_invalid")
    if freshness_state != "current_only":
        findings.append("freshness_state_not_current_only")
    if stale_candidates != 0:
        findings.append("stale_candidates_not_zero")

    handoff_path = _resolve_handoff_path(_string(context.get("handoff_path")), project_root.resolve())
    if handoff_path is None:
        findings.append("handoff_path_escape")
    elif not handoff_path.is_file():
        findings.append("handoff_file_missing")

    markdown = ""
    actual_sha256 = ""
    if handoff_path is not None and handoff_path.is_file():
        markdown = handoff_path.read_text(encoding="utf-8")
        actual_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    expected_sha256 = _string(context.get("markdown_sha256"))
    if not _HEX64_RE.fullmatch(expected_sha256):
        findings.append("handoff_sha256_invalid")
    elif actual_sha256 and actual_sha256 != expected_sha256:
        findings.append("handoff_sha256_mismatch")

    retrieved_sources = _chunk_sources(markdown) if markdown else []
    if not retrieved_sources:
        findings.append("retrieved_sources_missing")
    _validate_retrieved_sources(retrieved_sources, source_metadata=source_metadata, findings=findings)

    if findings:
        return {
            "schema_version": SCHEMA_VERSION,
            "artifact_kind": ARTIFACT_KIND,
            "status": "blocked",
            "enabled": True,
            "decision": "blocked_repo_intelligence_read_only_workflow_surface",
            "findings": sorted(set(findings)),
            "source": {
                "workflow_context_status": resolved_context.get("status", "unknown"),
                "workflow_context_decision": resolved_context.get("decision", "unknown"),
                "handoff_path": str(handoff_path) if handoff_path is not None else _string(context.get("handoff_path")),
                "markdown_sha256": actual_sha256 or expected_sha256,
                "vector_namespace_key_prefix": namespace,
                "freshness_state": freshness_state,
                "stale_candidates": stale_candidates,
            },
            "surface": _surface_contract(),
            "safety": {field: False for field in _SAFETY_FALSE_FIELDS},
            "support_widening": False,
            "production_platform_claim": False,
            "live_adapter_execution_allowed": False,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "status": "accepted",
        "enabled": True,
        "decision": "accepted_repo_intelligence_read_only_workflow_surface",
        "support_tier": SUPPORT_TIER,
        "source": {
            "workflow_context_decision": resolved_context["decision"],
            "workflow_context_support_tier": resolved_context["support_tier"],
            "handoff_support_tier": context["handoff_support_tier"],
            "handoff_path": str(handoff_path),
            "markdown_sha256": actual_sha256,
            "vector_namespace_key_prefix": namespace,
            "repo_chunks_sha256": repo_chunks_sha256,
            "repo_vector_index_manifest_sha256": vector_index_sha256,
            "freshness_state": freshness_state,
            "stale_candidates": 0,
            "retrieved_chunks": len(retrieved_sources),
        },
        "retrieved_sources": retrieved_sources,
        "surface": _surface_contract(),
        "safety": {field: False for field in _SAFETY_FALSE_FIELDS},
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution_allowed": False,
    }


def _surface_contract() -> JsonDict:
    return {
        "mode": MODE,
        "consumer": CONSUMER,
        "operator_visible": True,
        "requires_visible_agent_input": True,
        "includes_markdown_body": False,
        "automatic_prompt_injection": False,
        "context_compiler_auto_feed": False,
        "write_context_artifacts": False,
    }


def _validate_retrieved_sources(
    retrieved_sources: list[JsonDict],
    *,
    source_metadata: Mapping[str, Any],
    findings: list[str],
) -> None:
    metadata_paths = [_string(item) for item in _list(source_metadata.get("source_paths"))]
    metadata_hashes = [_string(item) for item in _list(source_metadata.get("content_sha256"))]
    if [source["source_path"] for source in retrieved_sources] != metadata_paths:
        findings.append("source_metadata_source_paths_mismatch")
    if [source["content_sha256"] for source in retrieved_sources] != metadata_hashes:
        findings.append("source_metadata_content_sha256_mismatch")
    for source in retrieved_sources:
        source_path = Path(source["source_path"])
        if source_path.is_absolute() or ".." in source_path.parts:
            findings.append("source_path_escape")
        if source["start_line"] > source["end_line"]:
            findings.append("invalid_line_range")
        if not _HEX64_RE.fullmatch(source["content_sha256"]):
            findings.append("content_sha256_invalid")


def _chunk_sources(markdown: str) -> list[JsonDict]:
    lines = markdown.splitlines()
    sources: list[JsonDict] = []
    for index, line in enumerate(lines):
        match = _CHUNK_HEADING_RE.match(line)
        if match is None:
            continue
        metadata: dict[str, str] = {}
        for table_line in lines[index + 1 :]:
            if table_line.startswith("### ") or table_line.startswith("## "):
                break
            if not table_line.startswith("|"):
                continue
            cells = [cell.strip().replace("\\|", "|") for cell in table_line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0] in {"---", "Field"}:
                continue
            if set(cells[0]) == {"-"}:
                continue
            metadata[cells[0]] = cells[1]
        sources.append(
            {
                "source_path": match.group("path"),
                "start_line": int(match.group("start")),
                "end_line": int(match.group("end")),
                "content_sha256": metadata.get("Content SHA256", ""),
            }
        )
    return sources


def _require_false_fields(
    payload: Mapping[str, Any],
    required_false_fields: Mapping[str, str],
    findings: list[str],
) -> None:
    for field, finding in required_false_fields.items():
        if payload.get(field) is not False:
            findings.append(finding)


def _resolve_handoff_path(value: str, root: Path) -> Path | None:
    if not value:
        return None
    raw = Path(value)
    candidate = raw if raw.is_absolute() else root / raw
    resolved = candidate.resolve()
    if not _is_relative_to(resolved, root):
        return None
    return resolved


def _mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
