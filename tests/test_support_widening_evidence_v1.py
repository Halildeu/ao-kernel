"""V5 Epic 3 E-3-1 invariants: support widening evidence v1.

Schema (recursive strict closure, no remote $ref, recompute_inputs shadow-widening
guard, per-surface-class evidence shapes, const-false guard pins) + the pure
parse/recompute/verify module + the read-only CLI. Infrastructure-only: every
artifact pins support_widening=false; no slice here flips the guard flag.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from ao_kernel._internal.support_widening.evidence import (
    SupportWideningEvidenceError,
    parse_v1,
    recompute_v1,
    verify_v1,
)
from ao_kernel.config import load_default

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCHEMA_NAME = "support-widening-evidence.schema.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / _SCHEMA_NAME

_FORBIDDEN = (
    "support_widening",
    "widening_authorized",
    "live_adapter_execution",
    "production_platform_claim",
    "github_write_authorized",
)


def _schema() -> dict[str, Any]:
    return load_default("schemas", _SCHEMA_NAME)


def _is_valid(payload: dict[str, Any]) -> bool:
    return not list(Draft202012Validator(_schema()).iter_errors(payload))


def _base() -> dict[str, Any]:
    return {
        "schema_version": "support_widening_evidence.v1",
        "artifact_kind": "support_widening_evidence",
        "generated_at": "2026-06-04T10:00:00Z",
        "repo": "Halildeu/ao-kernel",
        "surface_class": "python_version",
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
        "register_authority": "evidence_record_only",
        "github_write_authorized": False,
        "simulated_only": True,
        "live_call_made": False,
        "evidence_dimensions": {"matrix": ["3.11", "3.12", "3.13"], "pytest_passed": True},
        "reviewer_providers": [],
        "recompute_inputs": {"raw_dimensions": {"matrix": ["3.11", "3.12", "3.13"], "pytest_passed": True}},
    }


def _provider() -> dict[str, Any]:
    p = _base()
    p["surface_class"] = "provider"
    dims = {"integration_tests": {"count": 0}, "stub_adapter_ids": ["openai_stub"], "note": "v1 stub"}
    p["evidence_dimensions"] = dims
    p["recompute_inputs"] = {"raw_dimensions": json.loads(json.dumps(dims))}
    return p


# ---- 1. schema health (2) ----------------------------------------------


def test_schema_present_valid_draft_2020_12() -> None:
    assert _SCHEMA_PATH.is_file()
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    assert schema["$id"] == "urn:ao:support-widening-evidence:v1"


def test_base_fixtures_validate() -> None:
    assert _is_valid(_base())
    assert _is_valid(_provider())


# ---- 2. recursive strict closure (AST walk) (1) -------------------------


def _object_nodes(node: Any) -> "list[dict[str, Any]]":
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            out.append(node)
        for value in node.values():
            out.extend(_object_nodes(value))
    elif isinstance(node, list):
        for item in node:
            out.extend(_object_nodes(item))
    return out


def test_recursive_strict_closure_at_every_shape_defining_node() -> None:
    """BLK-schema-strict-recursive: every `type:object` node that DECLARES
    `properties` must carry additionalProperties:false AND unevaluatedProperties:false.

    The only bare `type:object` nodes (no `properties`) are the discriminated
    containers `evidence_dimensions` and `recompute_inputs.raw_dimensions`, whose
    closed shape is delegated to a per-class `$defs` entry via the root `allOf`
    (a base `additionalProperties:false` there would reject the allOf-supplied keys —
    the JSON-Schema sibling-applicator trap). Their effective closure is proven by
    `test_wrong_class_shape_rejected`. This test asserts every shape-DEFINING node is
    closed, and that the bare nodes are exactly the two known delegated containers."""
    schema = _schema()
    nodes = _object_nodes(schema)
    assert nodes, "expected multiple object nodes"
    bare = 0
    for node in nodes:
        if "properties" in node:
            assert node.get("additionalProperties") is False, f"shape node missing additionalProperties:false: {node!r}"
            assert node.get("unevaluatedProperties") is False, (
                f"shape node missing unevaluatedProperties:false: {node!r}"
            )
        else:
            bare += 1
    # exactly two delegated containers: evidence_dimensions + recompute_inputs.raw_dimensions
    assert bare == 2, f"expected exactly 2 bare delegated object nodes, found {bare}"


# ---- 3. no remote $ref (1) ----------------------------------------------


def test_no_remote_ref() -> None:
    """BLK-schema-no-remote-ref: no $ref may be an http(s) URL."""

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                assert not ref.startswith(("http://", "https://")), f"remote $ref forbidden: {ref}"
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(_schema())


# ---- 4. recompute_inputs shadow-widening guard (1) ----------------------


def test_recompute_inputs_schema_no_shadow_widening_key() -> None:
    """BLK-recompute-inputs-no-shadow-widening: the recompute_inputs subschema
    must declare no property whose name matches a widening flag."""
    ri_schema = _schema()["properties"]["recompute_inputs"]

    def _keys(node: Any) -> "list[str]":
        ks: list[str] = []
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                ks.extend(props.keys())
            for v in node.values():
                ks.extend(_keys(v))
        elif isinstance(node, list):
            for it in node:
                ks.extend(_keys(it))
        return ks

    for key in _keys(ri_schema):
        low = key.lower()
        assert not any(
            f in low
            for f in ("support_widening", "widening_authorized", "live_adapter", "production_platform", "github_write")
        ), f"recompute_inputs schema declares a forbidden widening key: {key!r}"


# ---- 5. guard-flag const pins (2) ---------------------------------------


@pytest.mark.parametrize(
    "flag", ["support_widening", "production_platform_claim", "live_adapter_execution", "github_write_authorized"]
)
def test_guard_flags_pinned_false(flag: str) -> None:
    bad = _base()
    bad[flag] = True
    assert not _is_valid(bad), f"{flag}=true must be rejected"


def test_authority_and_simulation_pins() -> None:
    for field, bad in (
        ("register_authority", "release_authority"),
        ("simulated_only", False),
        ("live_call_made", True),
    ):
        payload = _base()
        payload[field] = bad
        assert not _is_valid(payload), f"{field} pin must reject {bad!r}"


# ---- 6. per-surface-class dimensions (2) --------------------------------


def test_each_surface_class_has_a_valid_shape() -> None:
    shapes = {
        "provider": {"integration_tests": {"count": 0}, "stub_adapter_ids": [], "note": "n"},
        "python_version": {"matrix": ["3.11"], "pytest_passed": True},
        "os_platform": {"platform": "linux-x86_64", "smoke_passed": True},
        "db_backend": {"backend": "sqlite_in_memory", "round_trip_passed": True},
        "deployment_topology": {"topology": "library", "isolation_passed": True},
    }
    for sclass, dims in shapes.items():
        payload = _base()
        payload["surface_class"] = sclass
        payload["evidence_dimensions"] = dims
        payload["recompute_inputs"] = {"raw_dimensions": json.loads(json.dumps(dims))}
        assert _is_valid(payload), f"{sclass} valid shape must validate"


def test_wrong_class_shape_rejected() -> None:
    # provider class with python_version shape must fail (per-class allOf)
    payload = _provider()
    payload["evidence_dimensions"] = {"matrix": ["3.11"], "pytest_passed": True}
    assert not _is_valid(payload), "mismatched per-class evidence_dimensions must be rejected"


# ---- 7. module: parse / recompute / verify (5) --------------------------


def test_parse_v1_accepts_valid_and_rejects_flipped_pin() -> None:
    assert parse_v1(_base(), schema=_schema()) == _base()
    bad = _base()
    bad["support_widening"] = True
    with pytest.raises(SupportWideningEvidenceError):
        parse_v1(bad, schema=_schema())


def test_recompute_v1_matches_when_consistent() -> None:
    assert recompute_v1(_base()) == _base()["evidence_dimensions"]


def test_recompute_v1_rejects_mismatch() -> None:
    bad = _base()
    bad["evidence_dimensions"] = {"matrix": ["3.11"], "pytest_passed": False}  # diverges from raw_dimensions
    with pytest.raises(SupportWideningEvidenceError):
        recompute_v1(bad)


def test_recompute_v1_rejects_shadow_widening_key() -> None:
    bad = _base()
    bad["recompute_inputs"]["raw_dimensions"]["support_widening"] = True
    with pytest.raises(SupportWideningEvidenceError):
        recompute_v1(bad)


def test_verify_v1_rehashes_on_disk_ref(tmp_path: Path) -> None:
    import hashlib

    ref_file = tmp_path / "artifact.txt"
    ref_file.write_text("evidence-bytes", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(ref_file.read_bytes()).hexdigest()
    report = verify_v1(_base(), schema=_schema(), on_disk_refs={digest: str(ref_file)})
    assert report["valid"] is True and str(ref_file) in report["refs_verified"]
    # tamper: wrong declared digest must be rejected (recompute-not-trust)
    with pytest.raises(SupportWideningEvidenceError):
        verify_v1(_base(), schema=_schema(), on_disk_refs={"sha256:" + ("0" * 64): str(ref_file)})


# ---- 8. CLI: read-only validate (2) -------------------------------------


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ao_kernel.cli", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_validate_valid_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "ev.json"
    artifact.write_text(json.dumps(_base()), encoding="utf-8")
    proc = _run_cli(["support-widening", "evidence", "validate", str(artifact), "--recompute"])
    assert proc.returncode == 0, proc.stderr
    assert "VALID" in proc.stdout


def test_cli_validate_rejects_flipped_flag(tmp_path: Path) -> None:
    bad = _base()
    bad["support_widening"] = True
    artifact = tmp_path / "bad.json"
    artifact.write_text(json.dumps(bad), encoding="utf-8")
    proc = _run_cli(["support-widening", "evidence", "validate", str(artifact)])
    assert proc.returncode == 1
    assert "INVALID" in proc.stderr


# ---- 9. governance: no workflow mutation (1) ----------------------------


def test_no_workflow_mutation_in_diff() -> None:
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_support_widening_evidence_v1.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-3-1 test not ADDED by this PR (introducer pattern); invariant N/A")
    proc = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", ".github/workflows/"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.skip(f"git diff unavailable: {proc.stderr.strip()}")
    touched = [p for p in proc.stdout.split() if p]
    assert not touched, f"E-3-1 must not touch .github/workflows/. Touched: {touched}"
