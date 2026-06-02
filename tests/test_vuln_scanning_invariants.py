"""Shape invariants for V5 Epic 6 E-6-2 vulnerability scanning baseline.

Pins:

- ``.github/dependabot.yml`` exists at canonical path
- version: 2 + pip + github-actions ecosystems
- weekly schedule, low-traffic Mon 04:00 UTC slot
- runtime vs dev groups (reviewer noise control)
- conservative open-PR limits (5/3)
- ``.github/workflows/trivy.yml`` exists at canonical path
- 4 triggers (push main + PR main + weekly schedule + manual dispatch)
- ``pull_request_target`` rejected (fork-PR token risk)
- minimum permissions (contents:read + security-events:write only)
- ``contents: write`` rejected; ``id-token: write`` rejected
- ``actions/checkout@v6`` + ``persist-credentials: false``
- ``aquasecurity/trivy-action`` pinned to EXACT semver (not @v0 major)
- ``scan-type: fs`` + ``severity: CRITICAL,HIGH`` (baseline)
- ``scanners: vuln`` (no config/secret scanning in this slice)
- ``exit-code: "0"`` (advisory; do not block CI yet)
- ``format: sarif`` + SARIF upload via ``codeql-action/upload-sarif@v3``
- ``category: trivy-fs`` (distinct from CodeQL category)
- ``timeout-minutes: 20``
- Snyk: NO workflow file (deferred per Codex 019e8385 absorb);
  plan doc carries explicit deferred note + secret/tier decision pointer
"""

from __future__ import annotations

import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _dependabot_path() -> Path:
    return _repo_root() / ".github" / "dependabot.yml"


def _trivy_path() -> Path:
    return _repo_root() / ".github" / "workflows" / "trivy.yml"


def _plan_doc_path() -> Path:
    return _repo_root() / ".claude" / "plans" / "EPIC-6-E6-2-VULN-SCANNING.md"


def _dependabot_text() -> str:
    return _dependabot_path().read_text(encoding="utf-8")


def _trivy_text() -> str:
    return _trivy_path().read_text(encoding="utf-8")


def _plan_text() -> str:
    return _plan_doc_path().read_text(encoding="utf-8")


# ── Dependabot config file ───────────────────────────────────────────


def test_dependabot_file_exists_at_canonical_path() -> None:
    assert _dependabot_path().exists(), ".github/dependabot.yml must exist"


def test_dependabot_version_2_pinned() -> None:
    text = _dependabot_text()
    assert text.lstrip().startswith("version: 2"), "Dependabot config version must be 2"


def test_dependabot_has_pip_ecosystem() -> None:
    assert "package-ecosystem: pip" in _dependabot_text()


def test_dependabot_has_github_actions_ecosystem() -> None:
    assert "package-ecosystem: github-actions" in _dependabot_text()


def test_dependabot_uses_weekly_schedule() -> None:
    text = _dependabot_text()
    # interval: weekly appears for both ecosystems
    assert text.count("interval: weekly") >= 2


def test_dependabot_uses_low_traffic_slot() -> None:
    """Mon 04:00 UTC chosen for low-traffic CI runner contention."""
    text = _dependabot_text()
    assert "day: monday" in text
    assert 'time: "04:00"' in text
    assert "timezone: UTC" in text


def test_dependabot_pip_uses_runtime_dev_groups() -> None:
    """Codex 019e8385 absorb — runtime/dev split reduces reviewer noise."""
    text = _dependabot_text()
    assert "python-runtime:" in text
    assert "python-dev:" in text


def test_dependabot_conservative_open_pr_limits() -> None:
    """5 max open PRs for pip + 3 max for github-actions."""
    text = _dependabot_text()
    assert "open-pull-requests-limit: 5" in text
    assert "open-pull-requests-limit: 3" in text


def test_dependabot_commit_message_prefixes() -> None:
    """Commit message prefixes enforce repo's conventional commit style."""
    text = _dependabot_text()
    assert '"chore(deps)"' in text
    assert '"chore(actions)"' in text


# ── Trivy workflow file ──────────────────────────────────────────────


def test_trivy_workflow_exists() -> None:
    assert _trivy_path().exists(), ".github/workflows/trivy.yml must exist"


def test_trivy_workflow_name_pinned() -> None:
    assert "name: Trivy Vulnerability Scan" in _trivy_text()


def test_trivy_workflow_has_four_triggers() -> None:
    text = _trivy_text()
    assert "  push:\n    branches: [main]" in text
    assert "  pull_request:\n    branches: [main]" in text
    assert "  schedule:" in text
    assert "  workflow_dispatch:" in text


def test_trivy_workflow_weekly_cron_off_peak() -> None:
    """Mon 04:23 UTC — off-peak, after Dependabot 04:00 slot."""
    assert '"23 4 * * 1"' in _trivy_text()


def test_trivy_workflow_rejects_pull_request_target() -> None:
    """Fork-PR token risk surface (Codex 019e8385 absorb)."""
    assert "pull_request_target" not in _trivy_text()


def test_trivy_workflow_permissions_minimum() -> None:
    """Codex 019e8385 absorb — only contents:read + security-events:write."""
    text = _trivy_text()
    assert "contents: read" in text
    assert "security-events: write" in text


def test_trivy_workflow_rejects_contents_write() -> None:
    assert "contents: write" not in _trivy_text()


def test_trivy_workflow_rejects_id_token_write() -> None:
    assert "id-token: write" not in _trivy_text()


def test_trivy_workflow_rejects_all_extra_write_permissions() -> None:
    """Codex 019e8385 iter-2 absorb (non-blocking hardening) — single
    regression pin against future drift adding ``packages: write``,
    ``checks: write``, ``deployments: write``, ``actions: write``,
    ``pull-requests: write``, ``pages: write``, ``issues: write``,
    ``discussions: write``, ``statuses: write``,
    ``repository-projects: write``. Only ``security-events: write``
    is allowed in this workflow.
    """
    text = _trivy_text()
    forbidden_writes = [
        "packages: write",
        "checks: write",
        "deployments: write",
        "actions: write",
        "pull-requests: write",
        "pages: write",
        "issues: write",
        "discussions: write",
        "statuses: write",
        "repository-projects: write",
    ]
    leaked = [w for w in forbidden_writes if w in text]
    assert not leaked, f"workflow declares forbidden *: write permissions: {leaked}"


def test_trivy_workflow_uses_checkout_v6_no_persist_credentials() -> None:
    text = _trivy_text()
    assert "uses: actions/checkout@v6" in text
    assert "persist-credentials: false" in text


def test_trivy_action_pinned_to_exact_semver_not_major() -> None:
    """Codex 019e8385 P1 absorb — ``@v0`` floating major rejected;
    exact semver tag pinned with ``v`` prefix matching upstream
    release tags (aquasecurity/trivy-action publishes ``vX.Y.Z`` only;
    unprefixed ``X.Y.Z`` does not resolve at workflow runtime).
    Anthropic reviewer B1 absorb."""
    text = _trivy_text()
    # Floating major (`@v0`) rejected — must be exact semver
    assert re.search(r"aquasecurity/trivy-action@v\d+(?!\.)", text) is None, (
        "floating @vMAJOR (e.g. @v0) must NOT be used; pin to exact semver"
    )
    # Exact semver MUST carry the upstream `v` prefix to resolve at runtime
    vprefixed = re.search(r"aquasecurity/trivy-action@v(\d+\.\d+\.\d+)", text)
    assert vprefixed is not None, (
        "trivy-action must be pinned to vX.Y.Z (upstream publishes "
        "vX.Y.Z only; bare X.Y.Z fails at runtime with "
        "'Unable to resolve action')"
    )
    # Negative invariant: bare X.Y.Z (no v prefix) must NOT appear
    bare = re.search(r"aquasecurity/trivy-action@(?<!v)(\d+\.\d+\.\d+)", text)
    assert bare is None, (
        f"trivy-action@{bare.group(1) if bare else 'X.Y.Z'} pinned WITHOUT v prefix "
        "does not resolve on GitHub Actions; use @vX.Y.Z"
    )


def test_trivy_scan_type_fs() -> None:
    """Baseline is filesystem scan; container image scan is a follow-up slice."""
    assert "scan-type: fs" in _trivy_text()


def test_trivy_severity_critical_high_baseline() -> None:
    """Codex 019e8385 absorb — MEDIUM noise deferred."""
    assert "severity: CRITICAL,HIGH" in _trivy_text()


def test_trivy_scanners_vuln_only() -> None:
    """Codex 019e8385 absorb — config/secret scanning out of scope."""
    assert "scanners: vuln" in _trivy_text()


def test_trivy_advisory_exit_code_zero() -> None:
    """Codex 019e8385 absorb — ``exit-code: "0"`` baseline (advisory)."""
    text = _trivy_text()
    assert 'exit-code: "0"' in text, "Trivy must be advisory (exit-code: '0')"


def test_trivy_ignore_unfixed_true() -> None:
    """Skip unfixable CVEs in baseline to reduce noise."""
    assert "ignore-unfixed: true" in _trivy_text()


def test_trivy_sarif_format_and_upload() -> None:
    text = _trivy_text()
    assert "format: sarif" in text
    assert "uses: github/codeql-action/upload-sarif@v3" in text


def test_trivy_sarif_category_distinct_from_codeql() -> None:
    """Codex 019e8385 absorb — use ``trivy-fs`` category so the two
    analyses do not collide on GHAS Security tab."""
    text = _trivy_text()
    assert "category: trivy-fs" in text


def test_trivy_timeout_capped_at_20_minutes() -> None:
    assert "timeout-minutes: 20" in _trivy_text()


# ── Snyk deferred (Codex 019e8385 absorb) ───────────────────────────


def test_snyk_workflow_does_not_exist() -> None:
    """Snyk requires SNYK_TOKEN secret + tier decision + operator
    authorization (Codex 019e8385 absorb — empty placeholder
    workflow rejected)."""
    snyk_path = _repo_root() / ".github" / "workflows" / "snyk.yml"
    assert not snyk_path.exists(), "Snyk workflow must NOT exist in this slice (operator-bound follow-up)"


def test_plan_doc_notes_snyk_deferred_and_container_followup() -> None:
    """Plan doc must explicitly carry Snyk deferred + container image
    scan follow-up so closeout does not overclaim coverage."""
    text = _plan_text()
    assert "Snyk" in text, "Plan doc must mention Snyk explicitly"
    assert "deferred" in text.lower() or "follow-up" in text.lower() or "out-of-scope" in text.lower()
    assert "SNYK_TOKEN" in text, "Plan doc must call out SNYK_TOKEN secret + operator-bound decision"
    assert "container image" in text.lower() or "image scan" in text.lower(), (
        "Plan doc must record container image scan follow-up"
    )


def test_plan_doc_pins_advisory_not_required_gate() -> None:
    """Plan doc must clarify Trivy is advisory, NOT a required gate."""
    text = _plan_text()
    assert "advisory" in text.lower()
    # Plan doc must say required-gate promotion is deferred
    assert "required" in text.lower() and (
        "follow-up" in text.lower() or "future" in text.lower() or "deferred" in text.lower()
    )


def test_plan_doc_records_guard_flag_invariants() -> None:
    """Public claim discipline — three guard flags pinned const false."""
    text = _plan_text()
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in text, f"Plan doc must record {flag} invariant"
