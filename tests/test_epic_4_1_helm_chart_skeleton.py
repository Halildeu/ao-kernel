"""V5 Epic 4 E-4-1 Helm chart skeleton invariants.

Ten invariant categories enforce the slice contract:
  1. shape
  2. no_guard_flip (key absence in chart files)
  3. no_workflow_mutation (git diff allowlist)
  4. helm_template_deterministic (3-render SHA256 identity)
  5. values_replicas_min_1 (HARD RULE TEST cluster scale-to-zero YASAK)
  6. no_secret_in_values (regex scan)
  7. evidence_validates (Draft 2020-12 strict)
  8. write_set_exact_match
  9. no_pyproject_change
 10. chart_template_no_live_command

All assertions are concrete (no `assert True`, no `assert callable(x)`,
no bare `except: pass`) per CLAUDE.md test quality gates (BLK-001/002/003).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHART_DIR = _REPO_ROOT / "deploy" / "helm" / "ao-kernel"
_EVIDENCE_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-1-HELM-CHART-SKELETON.v1.json"
_SCHEMA_PATH = _REPO_ROOT / "ao_kernel" / "defaults" / "schemas" / "e-4-1-helm-chart-evidence.schema.v1.json"
_PLAN_DOC_PATH = _REPO_ROOT / ".claude" / "plans" / "E-4-1-HELM-CHART-SKELETON.md"

_GUARD_FLAG_KEYS = (
    "support_widening",
    "production_platform_claim",
    "live_adapter_execution",
)

_LIVE_CLUSTER_COMMANDS = (
    "kubectl apply",
    "helm install",
    "helm upgrade",
)

_SECRET_PATTERNS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{40,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),
    # JWT-shaped (three base64url segments joined by dots, leading "eyJ").
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
)

_EXPECTED_TEMPLATE_FILES = (
    "_helpers.tpl",
    "deployment.yaml",
    "service.yaml",
    "configmap.yaml",
    "serviceaccount.yaml",
    "rbac.yaml",
    "NOTES.txt",
)


def _run_git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=_REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _changed_files_against_origin_main() -> list[str]:
    """Return sorted list of files changed against origin/main."""
    output = _run_git("diff", "--name-only", "origin/main...HEAD")
    files = sorted({line.strip() for line in output.splitlines() if line.strip()})
    return files


# ── 1. shape ───────────────────────────────────────────────────────────


def test_shape_chart_dir_exists() -> None:
    assert _CHART_DIR.is_dir(), f"chart dir missing: {_CHART_DIR}"


def test_shape_chart_yaml_required_fields() -> None:
    content = (_CHART_DIR / "Chart.yaml").read_text(encoding="utf-8")
    # apiVersion v2 (manifest-only check; no YAML parsing dependency added).
    assert re.search(r"^apiVersion:\s*v2\s*$", content, re.MULTILINE), "Chart.yaml apiVersion: v2 missing"
    assert re.search(r"^name:\s*ao-kernel\s*$", content, re.MULTILINE), "Chart.yaml name: ao-kernel missing"
    assert re.search(r'^version:\s*"?[0-9]+\.[0-9]+\.[0-9]+"?\s*$', content, re.MULTILINE), (
        "Chart.yaml semver `version` missing"
    )
    assert re.search(r'^appVersion:\s*"?[0-9]+\.[0-9]+\.[0-9]+"?\s*$', content, re.MULTILINE), (
        "Chart.yaml semver `appVersion` missing"
    )


def test_shape_appversion_matches_ao_kernel_version() -> None:
    import ao_kernel

    content = (_CHART_DIR / "Chart.yaml").read_text(encoding="utf-8")
    expected = ao_kernel.__version__
    pattern = rf'^appVersion:\s*"?{re.escape(expected)}"?\s*$'
    assert re.search(pattern, content, re.MULTILINE), (
        f"Chart.yaml appVersion does not match ao_kernel.__version__ ({expected!r})"
    )


def test_shape_values_yaml_exists() -> None:
    assert (_CHART_DIR / "values.yaml").is_file(), "values.yaml missing"


def test_shape_templates_present() -> None:
    templates_dir = _CHART_DIR / "templates"
    assert templates_dir.is_dir(), "templates/ directory missing"
    for expected in _EXPECTED_TEMPLATE_FILES:
        assert (templates_dir / expected).is_file(), f"templates/{expected} missing"


def test_shape_readme_present() -> None:
    assert (_CHART_DIR / "README.md").is_file(), "chart README.md missing"


def test_shape_values_schema_json_present() -> None:
    assert (_CHART_DIR / "values.schema.json").is_file(), "values.schema.json missing"


# ── 2. no_guard_flip (key absence) ─────────────────────────────────────


def test_no_guard_flag_key_anywhere_in_chart_dir() -> None:
    """Recursive scan: zero matches for any of the three guard flag key strings."""
    hits: list[str] = []
    for path in _CHART_DIR.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for flag in _GUARD_FLAG_KEYS:
            if flag in text:
                hits.append(f"{path}: contains {flag!r}")
    assert hits == [], "guard flag key strings MUST NOT appear in chart dir; found:\n" + "\n".join(hits)


# ── 3. no_workflow_mutation ────────────────────────────────────────────


def test_no_workflow_mutation_in_diff() -> None:
    """git diff against origin/main MUST NOT include .github/workflows/** entries."""
    changed = _changed_files_against_origin_main()
    evidence_path = str(_EVIDENCE_PATH.relative_to(_REPO_ROOT))
    if evidence_path not in changed:
        pytest.skip("E-4-1 workflow mutation invariant applies only when the E-4-1 evidence artifact is in the PR diff")
    workflow_changes = [p for p in changed if p.startswith(".github/workflows/")]
    assert workflow_changes == [], f"workflow files modified in this slice (FORBIDDEN): {workflow_changes}"


# ── 4. helm_template_deterministic ─────────────────────────────────────


def _helm_available() -> bool:
    return shutil.which("helm") is not None


def test_helm_template_deterministic_three_renders() -> None:
    """Three sequential `helm template` renders must produce byte-identical output."""
    if not _helm_available():
        pytest.skip("helm binary not installed")
    digests: list[str] = []
    for _ in range(3):
        proc = subprocess.run(
            [
                "helm",
                "template",
                "test-release",
                str(_CHART_DIR),
                "--namespace",
                "test-ns",
            ],
            check=True,
            capture_output=True,
        )
        digests.append(hashlib.sha256(proc.stdout).hexdigest())
    assert len(set(digests)) == 1, f"helm template idempotency violated: digests={digests}"


# ── 5. values_replicas_min_1 ───────────────────────────────────────────


def test_values_schema_replica_count_minimum_is_one() -> None:
    schema = json.loads((_CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))
    rc_schema = schema.get("properties", {}).get("replicaCount", {})
    assert rc_schema.get("type") == "integer", "replicaCount must be integer"
    assert rc_schema.get("minimum") == 1, (
        "values.schema.json: replicaCount.minimum MUST be 1 (HARD RULE TEST cluster scale-to-zero YASAK)"
    )


def test_values_yaml_default_replica_count_is_one() -> None:
    content = (_CHART_DIR / "values.yaml").read_text(encoding="utf-8")
    match = re.search(r"^replicaCount:\s*(\d+)\s*$", content, re.MULTILINE)
    assert match is not None, "values.yaml top-level replicaCount missing"
    assert int(match.group(1)) >= 1, f"values.yaml replicaCount default must be >= 1; got {match.group(1)}"


# Helm/Kubernetes convention: a small set of slots are operator-extensible
# free-form key/value maps (annotations, labels, nodeSelector, affinity).
# These slots are open by design — the operator supplies arbitrary metadata
# that ao-kernel never interprets. Strict closure applies to every OTHER
# object schema in values.schema.json.
_VALUES_SCHEMA_FREEFORM_PATHS = frozenset(
    {
        "$.properties.serviceAccount.properties.annotations",
        "$.properties.nodeSelector",
        "$.properties.affinity",
        "$.properties.podLabels",
        "$.properties.podAnnotations",
        # E-4-4: ServiceMonitor additionalLabels is a free-form k8s label map
        # (operator labels the ServiceMonitor so a per-tenant Prometheus selects it).
        "$.properties.monitoring.properties.serviceMonitor.properties.additionalLabels",
        # E-4-5: extraFrom items are free-form k8s NetworkPolicyPeer objects
        # (podSelector/namespaceSelector/ipBlock); operator supplies the shape.
        "$.properties.networkPolicy.properties.ingress.properties.extraFrom.items",
    }
)


def test_values_schema_strict_closure_with_documented_freeform_allowlist() -> None:
    """values.schema.json uses additionalProperties:false on every object except
    a documented Helm/Kubernetes free-form map allowlist (annotations, labels,
    nodeSelector, affinity). Every other object MUST be strict-closed."""
    schema = json.loads((_CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))

    def _walk(node: object, path: str) -> list[str]:
        violations: list[str] = []
        if isinstance(node, dict):
            is_object_schema = node.get("type") == "object"
            in_allowlist = path in _VALUES_SCHEMA_FREEFORM_PATHS
            if is_object_schema and not in_allowlist:
                if "additionalProperties" not in node:
                    violations.append(f"{path}: missing additionalProperties:false")
                elif node.get("additionalProperties") is not False:
                    violations.append(
                        f"{path}: additionalProperties is not false (got {node.get('additionalProperties')!r})"
                    )
            for key, value in node.items():
                violations.extend(_walk(value, f"{path}.{key}"))
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                violations.extend(_walk(item, f"{path}[{idx}]"))
        return violations

    violations = _walk(schema, "$")
    assert violations == [], "values.schema.json strict closure violations:\n" + "\n".join(violations)


def test_values_schema_freeform_allowlist_paths_exist_in_schema() -> None:
    """Sanity: every entry in the free-form allowlist actually points at a real
    `type: object` node in values.schema.json. Catches allowlist drift if a
    future schema edit renames or removes a free-form slot."""
    schema = json.loads((_CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))

    def _resolve(node: object, path_tokens: list[str]) -> object | None:
        current: object | None = node
        for token in path_tokens:
            if isinstance(current, dict) and token in current:
                current = current[token]
            else:
                return None
        return current

    missing: list[str] = []
    for allow_path in _VALUES_SCHEMA_FREEFORM_PATHS:
        # "$.properties.x.properties.y" -> ["properties", "x", "properties", "y"]
        tokens = [t for t in allow_path.split(".") if t and t != "$"]
        resolved = _resolve(schema, tokens)
        if not (isinstance(resolved, dict) and resolved.get("type") == "object"):
            missing.append(f"{allow_path}: allowlist entry does not resolve to type:object")
    assert missing == [], "free-form allowlist drift; entries no longer resolve to type:object:\n" + "\n".join(missing)


def test_values_schema_every_array_declares_items() -> None:
    """Every `type: array` node in values.schema.json MUST declare an `items`
    sub-schema (typed shape) so the operator cannot inject untyped entries
    (e.g. rbac.rules=[\"bad\"] or tolerations=[\"bad\"]). Codex post-impl iter-1
    REVISE absorb (thread 019e87c9): bare `type: array` allowed invalid
    Kubernetes/RBAC shapes; this walker prevents regression."""
    schema = json.loads((_CHART_DIR / "values.schema.json").read_text(encoding="utf-8"))

    def _walk(node: object, path: str) -> list[str]:
        violations: list[str] = []
        if isinstance(node, dict):
            if node.get("type") == "array" and "items" not in node:
                violations.append(f"{path}: array without items sub-schema")
            for key, value in node.items():
                violations.extend(_walk(value, f"{path}.{key}"))
        elif isinstance(node, list):
            for idx, item in enumerate(node):
                violations.extend(_walk(item, f"{path}[{idx}]"))
        return violations

    violations = _walk(schema, "$")
    assert violations == [], "values.schema.json has arrays without items (untyped entries allowed):\n" + "\n".join(
        violations
    )


def test_values_schema_rejects_invalid_rbac_rules_and_tolerations_via_helm() -> None:
    """Negative-path runtime gate: helm template MUST reject string entries in
    rbac.rules and tolerations. Codex post-impl iter-1 REVISE absorb (thread
    019e87c9 Finding 1): bare `type: array` accepted invalid shapes;
    typed `items` schemas now enforce Kubernetes structural shape."""
    if not _helm_available():
        pytest.skip("helm binary not installed")
    bad_inputs = (
        ("rbac.rules", "--set-json", 'rbac.rules=["bad"]', "/rbac/rules/0"),
        ("tolerations", "--set", "tolerations[0]=bad", "/tolerations/0"),
    )
    failures: list[str] = []
    for label, flag, payload, expected_path in bad_inputs:
        proc = subprocess.run(
            [
                "helm",
                "template",
                "neg-test",
                str(_CHART_DIR),
                "--namespace",
                "neg-ns",
                flag,
                payload,
            ],
            capture_output=True,
            text=True,
        )
        # helm MUST fail (non-zero exit) and mention the rejected path.
        if proc.returncode == 0:
            failures.append(
                f"{label}: helm template accepted invalid payload {payload!r} "
                f"(returncode 0; expected schema failure at {expected_path})"
            )
        elif expected_path not in (proc.stdout + proc.stderr):
            failures.append(
                f"{label}: helm template failed but error did not reference "
                f"expected path {expected_path!r} for payload {payload!r}; "
                f"stderr={proc.stderr.strip()[:200]}"
            )
    assert failures == [], "\n".join(failures)


# ── 6. no_secret_in_values ─────────────────────────────────────────────


def test_no_secret_in_values_or_templates() -> None:
    """Regex scan over values.yaml + templates for known secret patterns."""
    targets = [_CHART_DIR / "values.yaml"]
    targets.extend((_CHART_DIR / "templates").iterdir())
    targets.append(_CHART_DIR / "README.md")
    targets.append(_CHART_DIR / "Chart.yaml")
    hits: list[str] = []
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(text)
            if match is not None:
                hits.append(f"{path}: pattern {pattern.pattern!r} matched {match.group(0)!r}")
    assert hits == [], "secret pattern detected in chart files:\n" + "\n".join(hits)


def test_values_yaml_secret_refs_only_through_secret_key_ref() -> None:
    """env block must use secretKeyRef indirection; no inline `value: <secret>` heuristic."""
    content = (_CHART_DIR / "values.yaml").read_text(encoding="utf-8")
    # secretKeyRef pattern path is expressed via env.secretRefs section.
    assert "secretRefs" in content, "values.yaml env.secretRefs section missing"
    # secret entries must declare secretName + secretKey fields (referenced indirection).
    # We assert the structural keys are documented in the values block.
    assert "secretName" in content, "values.yaml secretName field missing in env block"
    assert "secretKey" in content, "values.yaml secretKey field missing in env block"


# ── 7. evidence_validates ──────────────────────────────────────────────


def test_evidence_validates_against_schema() -> None:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    evidence = json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(evidence), key=lambda e: e.path)
    assert errors == [], "evidence validation errors:\n" + "\n".join(f"  {list(e.path)} -> {e.message}" for e in errors)


# ── 8. write_set_exact_match ───────────────────────────────────────────


def test_write_set_exact_match_git_diff() -> None:
    git_diff = _changed_files_against_origin_main()
    evidence_path = str(_EVIDENCE_PATH.relative_to(_REPO_ROOT))
    if evidence_path not in git_diff:
        pytest.skip("E-4-1 write_set exactness applies only when the E-4-1 evidence artifact is in the PR diff")
    evidence = json.loads(_EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence_write_set = sorted(set(evidence["write_set"]))
    assert evidence_write_set == git_diff, (
        "evidence.write_set diverges from git diff --name-only origin/main..HEAD\n"
        f"  evidence: {evidence_write_set}\n"
        f"  git diff: {git_diff}\n"
        f"  missing_from_evidence: {sorted(set(git_diff) - set(evidence_write_set))}\n"
        f"  extra_in_evidence: {sorted(set(evidence_write_set) - set(git_diff))}"
    )


# ── 9. no_pyproject_change ─────────────────────────────────────────────


def test_no_pyproject_change_in_slice() -> None:
    changed = _changed_files_against_origin_main()
    assert "pyproject.toml" not in changed, (
        "pyproject.toml MUST NOT change in E-4-1 (Epic 4 F8 absorb: [k8s-helm] out of scope)"
    )


# ── 10. chart_template_no_live_command ─────────────────────────────────


def test_chart_notes_and_readme_no_live_cluster_commands() -> None:
    targets = [_CHART_DIR / "templates" / "NOTES.txt", _CHART_DIR / "README.md"]
    hits: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        for live_cmd in _LIVE_CLUSTER_COMMANDS:
            if live_cmd in text:
                hits.append(f"{path}: contains forbidden live command {live_cmd!r}")
    assert hits == [], "chart NOTES.txt and README MUST NOT embed live cluster commands; found:\n" + "\n".join(hits)


# ── meta: plan doc + schema files reachable ────────────────────────────


def test_plan_doc_and_schema_files_exist() -> None:
    """Sanity: decision record + schema files exist (required by evidence cross-references)."""
    assert _PLAN_DOC_PATH.is_file(), f"plan doc missing: {_PLAN_DOC_PATH}"
    assert _SCHEMA_PATH.is_file(), f"evidence schema missing: {_SCHEMA_PATH}"
    assert _EVIDENCE_PATH.is_file(), f"evidence artifact missing: {_EVIDENCE_PATH}"
