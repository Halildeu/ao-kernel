from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ao-ma10q-dedicated-actor-smoke.yml"
DOC = ROOT / ".claude" / "plans" / "AO-MA-10S-DEDICATED-ACTOR-SMOKE-WORKFLOW.md"
RECEIPT = ROOT / ".claude" / "plans" / "AO-MA-10S-DEDICATED-ACTOR-SMOKE-WORKFLOW.v1.json"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _strip_yaml_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _run_step_blocks(text: str) -> list[str]:
    blocks = re.split(r"\n      - name: ", text)
    return blocks[1:]


def test_ao_ma10s_workflow_is_dispatch_only_and_main_bound() -> None:
    text = _workflow_text()
    stripped = _strip_yaml_comments(text)
    assert "workflow_dispatch:" in text
    assert "\n  push:" not in stripped
    assert "\n  pull_request:" not in stripped
    assert "\n  pull_request_target:" not in stripped
    assert "\n  schedule:" not in stripped
    assert 'if [ "$GITHUB_REF" != "refs/heads/main" ]; then' in text
    assert "AO-MA-10q smoke must be dispatched from refs/heads/main" in text


def test_ao_ma10s_workflow_permissions_are_minimal() -> None:
    text = _workflow_text()
    assert "\npermissions:\n  contents: read\n" in text
    forbidden = [
        "contents: write",
        "checks: write",
        "pull-requests: write",
        "issues: write",
        "actions: write",
        "deployments: write",
    ]
    for item in forbidden:
        assert item not in text


def test_ao_ma10s_secret_is_only_bound_as_env_and_not_echoed() -> None:
    text = _workflow_text()
    assert 'GLADYATORE_LAB_GH_TOKEN: ${{ secrets.GLADYATORE_LAB_GH_TOKEN }}' in text
    assert 'AO_GOVERNANCE_GH_TOKEN: ${{ secrets.AO_GOVERNANCE_GH_TOKEN }}' in text
    assert text.count("${{ secrets.GLADYATORE_LAB_GH_TOKEN }}") == 1
    assert text.count("${{ secrets.AO_GOVERNANCE_GH_TOKEN }}") == 1
    shell_blocks = "\n".join(_run_step_blocks(text))
    assert "$GLADYATORE_LAB_GH_TOKEN" not in shell_blocks
    assert "${GLADYATORE_LAB_GH_TOKEN" not in shell_blocks
    assert "$AO_GOVERNANCE_GH_TOKEN" not in shell_blocks
    assert "${AO_GOVERNANCE_GH_TOKEN" not in shell_blocks
    assert "set -x" not in shell_blocks
    assert "env |" not in shell_blocks
    assert "printenv" not in shell_blocks


def test_ao_ma10s_workflow_runs_doctor_before_runner_and_uploads_artifacts() -> None:
    text = _workflow_text()
    doctor = "scripts/ao_ma10r_dedicated_actor_credential_doctor.py"
    runner = "scripts/ao_ma10q_dedicated_actor_runner.py"
    assert doctor in text
    assert runner in text
    assert text.index(doctor) < text.index(runner)
    assert "ao-ma10r-credential-doctor-result.json" in text
    assert "ao-ma10q-dedicated-actor-runner-result.json" in text
    assert "actions/upload-artifact@v7" in text
    assert "if: always()" in text
    assert "if-no-files-found: error" in text


def test_ao_ma10s_execute_mode_requires_confirmation() -> None:
    text = _workflow_text()
    assert "AO-MA-10L-EXECUTE" in text
    assert 'if [ "$CONFIRMATION" != "AO-MA-10L-EXECUTE" ]; then' in text
    assert 'q_args+=(--execute --confirmation "$CONFIRMATION")' in text


def test_ao_ma10s_doc_and_receipt_preserve_authority_boundary() -> None:
    doc = DOC.read_text(encoding="utf-8")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["status"] == "implemented_fail_closed"
    assert receipt["trigger"] == "workflow_dispatch_only"
    assert receipt["allowed_ref"] == "refs/heads/main"
    assert receipt["secret_env"] == "GLADYATORE_LAB_GH_TOKEN"
    assert receipt["governance_secret_env"] == "AO_GOVERNANCE_GH_TOKEN"
    assert receipt["producer_secret_env"] == "AO_GOVERNANCE_GH_TOKEN"
    assert receipt["producer_release_authority"] is False
    assert receipt["token_value_recorded"] is False
    assert receipt["release_authority"] == "ao-release-gate+github-ruleset"
    assert receipt["ai_output_release_authority"] is False
    assert receipt["support_widening"] is False
    assert receipt["production_platform_claim"] is False
    assert receipt["live_adapter_execution"] is False
    assert "merge actor is `gladyatore-lab`, not" in doc
