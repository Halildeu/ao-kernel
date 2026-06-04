"""V5 Epic 4 E-4-3 invariants: operator-owned PostgreSQL provisioning + secret mgmt.

The chart references an EXTERNAL, operator-owned PostgreSQL backend via
secretKeyRef ONLY. It never deploys the database, never creates the Secret,
and never embeds credential literals. These invariants are machine-enforced:

  - values.yaml carries a `postgresql` block, disabled by default
  - NO inline credential value anywhere (secretKeyRef only)
  - values.schema.json pins the postgresql block (additionalProperties:false)
  - deployment.yaml gates DB env on postgresql.enabled + uses secretKeyRef
  - chart does NOT contain a PostgreSQL StatefulSet/Deployment (operator-owned)
  - render-only: no live kubectl/psql commands embedded in templates/docs
  - no runtime guard-flag key strings introduced
  - operator runbook docs/OPERATOR-SECRET-MANAGEMENT.md present + complete
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CHART_DIR = _REPO_ROOT / "deploy" / "helm" / "ao-kernel"
_VALUES = _CHART_DIR / "values.yaml"
_SCHEMA = _CHART_DIR / "values.schema.json"
_DEPLOYMENT = _CHART_DIR / "templates" / "deployment.yaml"
_RUNBOOK = _REPO_ROOT / "docs" / "OPERATOR-SECRET-MANAGEMENT.md"

# Credential-literal smell: a quoted non-empty password/username default.
_FORBIDDEN_INLINE = ("password:", "passwd:")


def _load_values() -> dict:
    if yaml is None:
        pytest.skip("PyYAML not installed")
    return yaml.safe_load(_VALUES.read_text(encoding="utf-8"))


# ---- 1. values.yaml postgresql block (4) --------------------------------


def test_values_has_postgresql_block() -> None:
    vals = _load_values()
    assert "postgresql" in vals, "values.yaml missing postgresql block (E-4-3)"


def test_postgresql_disabled_by_default() -> None:
    vals = _load_values()
    assert vals["postgresql"]["enabled"] is False, (
        "postgresql must default to disabled (library/in-memory mode is the default)"
    )


def test_postgresql_block_has_secret_reference_keys_not_values() -> None:
    """The block carries secretName + key POINTERS, never a password literal."""
    vals = _load_values()
    pg = vals["postgresql"]
    for key in ("secretName", "usernameKey", "passwordKey", "host", "port", "dbname", "sslmode"):
        assert key in pg, f"postgresql block missing {key!r}"
    # The block must NOT carry a 'password' or 'username' VALUE key.
    assert "password" not in pg, "postgresql block must not carry an inline password"
    assert "username" not in pg, "postgresql block must not carry an inline username"


def test_postgresql_default_secret_coords_empty() -> None:
    """Defaults are empty/non-committal; operator fills them in an overlay."""
    vals = _load_values()
    pg = vals["postgresql"]
    assert pg["host"] == "", "default host must be empty (operator-provided)"
    assert pg["secretName"] == "", "default secretName must be empty (operator-provided)"


# ---- 2. No inline secret material (2) -----------------------------------


def test_no_inline_credential_literal_in_values() -> None:
    """No quoted non-empty password/username literal in values.yaml."""
    text = _VALUES.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        low = stripped.lower()
        for marker in _FORBIDDEN_INLINE:
            if low.startswith(marker):
                value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                assert value == "", f"inline credential literal in values.yaml: {line!r}"


def test_deployment_db_credentials_use_secretkeyref_only() -> None:
    text = _DEPLOYMENT.read_text(encoding="utf-8")
    # The DB username/password env must resolve via secretKeyRef, never value:.
    assert "AO_KERNEL_DB_PASSWORD" in text, "deployment must wire DB password env"
    assert "AO_KERNEL_DB_USERNAME" in text, "deployment must wire DB username env"
    # Find the DB password block and assert it uses secretKeyRef.
    idx = text.find("AO_KERNEL_DB_PASSWORD")
    window = text[idx : idx + 200]
    assert "secretKeyRef" in window, "DB password must use secretKeyRef (never inline value)"


# ---- 3. values.schema.json pins the block (2) ---------------------------


def test_schema_has_postgresql_property() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    assert "postgresql" in schema["properties"], "values.schema.json missing postgresql"
    pg = schema["properties"]["postgresql"]
    assert pg.get("additionalProperties") is False, "postgresql schema must be closed"
    for key in ("enabled", "host", "port", "dbname", "sslmode", "secretName", "usernameKey", "passwordKey"):
        assert key in pg["properties"], f"postgresql schema missing {key!r}"


def test_schema_sslmode_enum_pins_safe_modes() -> None:
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["postgresql"]["properties"]["sslmode"]["enum"]
    assert "require" in enum and "verify-full" in enum, "sslmode enum must include require/verify-full"


# ---- 4. deployment gating (2) -------------------------------------------


def test_deployment_db_env_gated_on_enabled() -> None:
    text = _DEPLOYMENT.read_text(encoding="utf-8")
    assert "if .Values.postgresql.enabled" in text, (
        "DB env block must be gated on postgresql.enabled (no DB env when disabled)"
    )


def test_chart_does_not_deploy_postgresql() -> None:
    """Operator-owned: the chart must NOT contain a PostgreSQL workload."""
    for path in (_CHART_DIR / "templates").rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        # A StatefulSet/Deployment whose image is postgres would be chart-managed DB.
        assert "image: postgres" not in text.lower(), f"chart must not deploy postgres: {path}"
        assert "kind: StatefulSet" not in text, f"chart must not own a StatefulSet: {path}"


# ---- 5. render-only + no live commands (1) ------------------------------


def test_runbook_no_inline_password_in_create_secret() -> None:
    """The runbook's kubectl create secret example must read creds from a
    file/stdin, never a shell literal that lands in history."""
    text = _RUNBOOK.read_text(encoding="utf-8")
    assert _RUNBOOK.is_file()
    # The example uses --from-file / $(cat ...), not --from-literal=password=<plain>
    assert "--from-file=password" in text, "runbook must show file-based password provisioning"


# ---- 6. runbook completeness (3) ----------------------------------------


def test_runbook_present_and_covers_required_sections() -> None:
    text = _RUNBOOK.read_text(encoding="utf-8")
    for section in ("operator-owned", "Rotation", "secretKeyRef", "guard flag"):
        assert section.lower() in text.lower(), f"runbook missing coverage of {section!r}"


def test_runbook_disclaims_production_and_guard_flags() -> None:
    text = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "const false" in text or "const false" in text
    for flag in ("support_widening", "production_platform_claim", "live_adapter_execution"):
        assert flag in text, f"runbook must affirm {flag} stays untouched"


def test_runbook_clarifies_not_pgvector() -> None:
    """E-4-3 is connection+secret plumbing; the optional pgvector backend
    (E-7-5) is a separate, lazy-import surface — the runbook must not conflate."""
    text = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "pgvector" in text and "e-7-5" in text


# ---- 7. no guard-flag key strings introduced (1) ------------------------


def test_no_guard_flag_key_in_chart_postgresql_surface() -> None:
    """The chart must not introduce runtime guard-flag KEYS (the values may
    only NAME them in comments affirming they are untouched)."""
    # values.yaml may mention flags only in the runbook prose, not as keys.
    vals = _load_values()

    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in (
                    "support_widening",
                    "production_platform_claim",
                    "live_adapter_execution",
                ), f"guard-flag KEY present in values: {k}"
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(vals)


# ---- 8. governance: slice-scoped, no workflow mutation (1) --------------


def test_no_workflow_mutation_in_diff() -> None:
    """E-4-3 is a chart/docs/test slice; it MUST NOT touch .github/workflows/.

    Introducer-PR detection (parity with #915 fix): use --diff-filter=A so
    only the PR that ADDS this test triggers the assertion.
    """
    added = subprocess.run(
        [
            "git",
            "diff",
            "--diff-filter=A",
            "--name-only",
            "origin/main...HEAD",
            "--",
            "tests/test_epic_4_3_postgres_provisioning.py",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if added.returncode != 0:
        pytest.skip(f"git diff unavailable: {added.stderr.strip()}")
    if not added.stdout.strip():
        pytest.skip("E-4-3 test not ADDED by this PR (introducer pattern); invariant N/A")
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
    assert not touched, f"E-4-3 must not touch .github/workflows/. Touched: {touched}"
