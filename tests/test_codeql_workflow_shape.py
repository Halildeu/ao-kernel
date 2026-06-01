"""Shape invariants for the CodeQL Security Analysis workflow.

V5 Epic 6 E-6-5 (Codex 019e8350 absorb) — pins:

- workflow file exists at canonical path
- trigger set: push main + PR main + weekly schedule + manual dispatch
- ``pull_request_target`` MUST NOT appear (Codex 019e8350 absorb —
  fork PR token risk)
- permissions: minimum + ``security-events: write`` + ``pull-requests:
  read``; ``contents: write`` MUST NOT appear (write-side bypass)
- ``actions/checkout@v6`` + ``persist-credentials: false``
- ``github/codeql-action/init@v3`` + ``analyze@v3``
- language ``python`` declared in the matrix
- ``timeout-minutes`` <= 30 (Codex 019e8350 absorb — was 360 default)
- ``config-file: ./.github/codeql/codeql-config.yml`` referenced
- workflow does NOT inline ``queries:`` (single source-of-truth lives
  in the config file)
- config file exists at canonical path
- ``security-extended`` query pack pinned in config
- ``security-and-quality`` query pack NOT present yet (deferred to a
  follow-up slice once baseline is triaged)
- ``paths-ignore`` covers tests + defaults + pycache + .pyc
"""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow_path() -> Path:
    return _repo_root() / ".github" / "workflows" / "codeql.yml"


def _config_path() -> Path:
    return _repo_root() / ".github" / "codeql" / "codeql-config.yml"


def _workflow_text() -> str:
    return _workflow_path().read_text(encoding="utf-8")


def _config_text() -> str:
    return _config_path().read_text(encoding="utf-8")


# ── Workflow file existence + identity ──────────────────────────────


def test_codeql_workflow_exists_at_canonical_path() -> None:
    assert _workflow_path().exists(), ".github/workflows/codeql.yml must exist (V5 Epic 6 E-6-5)"


def test_codeql_workflow_name_pinned() -> None:
    assert "name: CodeQL Security Analysis" in _workflow_text()


# ── Trigger set ──────────────────────────────────────────────────────


def test_codeql_workflow_triggers_include_push_pr_schedule_dispatch() -> None:
    text = _workflow_text()
    # Each trigger appears as a YAML key (regex-free; substring is
    # sufficient because the file is hand-authored).
    assert "  push:\n    branches: [main]" in text, "push main trigger missing"
    assert "  pull_request:\n    branches: [main]" in text, "PR main trigger missing"
    assert "  schedule:" in text, "schedule trigger missing"
    assert "  workflow_dispatch:" in text, "workflow_dispatch trigger missing"


def test_codeql_workflow_schedule_uses_weekly_low_traffic_cron() -> None:
    text = _workflow_text()
    # Codex 019e8350 absorb — Monday 03:17 UTC weekly. Pin exactly
    # so accidental cron drift (e.g. hourly) is rejected.
    assert '"17 3 * * 1"' in text, "schedule cron must be weekly Mon 03:17 UTC"


def test_codeql_workflow_rejects_pull_request_target() -> None:
    """Codex 019e8350 absorb — pull_request_target is a known fork
    PR token risk surface and must NEVER appear in the CodeQL
    workflow.
    """
    assert "pull_request_target" not in _workflow_text(), "pull_request_target MUST NOT appear (fork-PR token risk)"


# ── Permissions ──────────────────────────────────────────────────────


def test_codeql_workflow_permissions_minimum_set() -> None:
    text = _workflow_text()
    assert "actions: read" in text
    assert "contents: read" in text
    assert "pull-requests: read" in text
    assert "security-events: write" in text


def test_codeql_workflow_rejects_contents_write() -> None:
    """contents: write would allow code mutation — write-side bypass
    surface. Must NOT appear (Codex 019e8350 absorb)."""
    assert "contents: write" not in _workflow_text()


def test_codeql_workflow_rejects_id_token_write() -> None:
    """id-token: write is unnecessary for CodeQL SARIF upload and
    would expand the OIDC surface (Codex 019e8350 absorb)."""
    assert "id-token: write" not in _workflow_text()


# ── Action versions + checkout hardening ─────────────────────────────


def test_codeql_workflow_uses_checkout_v6_no_persist_credentials() -> None:
    text = _workflow_text()
    assert "uses: actions/checkout@v6" in text
    assert "persist-credentials: false" in text


def test_codeql_workflow_uses_codeql_action_v3() -> None:
    text = _workflow_text()
    assert "uses: github/codeql-action/init@v3" in text
    assert "uses: github/codeql-action/analyze@v3" in text


def test_codeql_workflow_does_not_install_python_setup() -> None:
    """Codex 019e8350 absorb — CodeQL Python is build-less; setup-python
    is unnecessary and grows the runtime/network failure surface.
    """
    assert "uses: actions/setup-python" not in _workflow_text()


# ── Matrix + timeout ─────────────────────────────────────────────────


def test_codeql_workflow_matrix_pins_python() -> None:
    text = _workflow_text()
    assert "language: [python]" in text


def test_codeql_workflow_timeout_capped_at_30_minutes() -> None:
    """Codex 019e8350 absorb — was GitHub default 360 min; we cap
    at 30 (Python CodeQL expected 5-15 min)."""
    text = _workflow_text()
    assert "timeout-minutes: 30" in text, "timeout-minutes must be 30 (not 360 default)"
    assert "timeout-minutes: 360" not in text, "stale 360-min default must NOT appear"


# ── Single-source-of-truth config file ───────────────────────────────


def test_codeql_workflow_references_config_file() -> None:
    text = _workflow_text()
    assert "config-file: ./.github/codeql/codeql-config.yml" in text


def test_codeql_workflow_does_not_inline_queries_key() -> None:
    """Codex 019e8350 absorb — queries: must live only in the config
    file (single source-of-truth). Workflow inlining creates drift.
    """
    text = _workflow_text()
    # ``queries:`` as a top-level workflow key must NOT appear under
    # the init step (config-file is the only declaration).
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("queries:"):
            # Only legitimate ``queries:`` location is inside the
            # config file, not this workflow file.
            raise AssertionError(
                f"workflow inlines queries on line {i + 1}: {line!r}; queries belong in config file only"
            )


# ── Config file shape ────────────────────────────────────────────────


def test_codeql_config_file_exists() -> None:
    assert _config_path().exists(), ".github/codeql/codeql-config.yml must exist"


def test_codeql_config_pins_security_extended_query_pack() -> None:
    assert "uses: security-extended" in _config_text(), "security-extended query pack must be declared"


def test_codeql_config_defers_security_and_quality_pack() -> None:
    """V5 Epic 6 E-6-5 baseline (Codex 019e8350 absorb) — the broader
    security-and-quality pack is OUT of this slice and ships only
    after the initial alert baseline is triaged. Match only the
    ``uses:`` declaration form (comments referencing the pack name
    are allowed for documentation context).
    """
    assert "uses: security-and-quality" not in _config_text(), (
        "security-and-quality query pack is deferred; must NOT be declared via 'uses:' yet"
    )


def test_codeql_config_paths_scope_covers_runtime_code() -> None:
    text = _config_text()
    assert "  - ao_kernel" in text, "ao_kernel must be in scanned paths"
    assert "  - scripts" in text, "scripts must be in scanned paths"


def test_codeql_config_paths_ignore_glob_covers_noise() -> None:
    text = _config_text()
    for ignore in (
        '"tests/**"',
        '"ao_kernel/defaults/**"',
        '"**/__pycache__/**"',
        '"**/*.pyc"',
    ):
        assert ignore in text, f"paths-ignore must include {ignore}"


def test_codeql_config_default_queries_remain_enabled() -> None:
    """Default queries provide essential security checks; we layer
    security-extended ON TOP (not as replacement)."""
    assert "disable-default-queries: false" in _config_text()
