from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_policy_container_publish_workflow_builds_smokes_and_publishes_ghcr() -> None:
    workflow = _repo_root() / ".github" / "workflows" / "policy-container-publish.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "ghcr.io/halildeu/ao-kernel-live-adapter-gate-policy-service" in text
    assert "deploy/live-adapter-gate-policy-service/Dockerfile" in text
    assert "docker build -f \"$DOCKERFILE\"" in text
    assert "scripts/live_adapter_gate_policy_container_smoke.py" in text
    assert "--skip-build" in text
    assert "docker push \"$image_sha\"" in text
    assert "docker push \"$image_main\"" in text


def test_policy_container_publish_workflow_keeps_prs_and_live_credentials_closed() -> None:
    workflow = _repo_root() / ".github" / "workflows" / "policy-container-publish.yml"
    text = workflow.read_text(encoding="utf-8")

    assert "contents: read" in text
    assert "packages: write" in text
    assert "github.event_name != 'pull_request'" in text
    assert "GHCR_TOKEN: ${{ github.token }}" in text
    assert "secrets." not in text
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in text
    assert "AO_LIVE_ADAPTER_GATE_WEBHOOK_SECRET" not in text
    assert "AO_GITHUB_APP_PRIVATE_KEY" not in text
    assert "workflow_dispatch" in text
    assert "pull_request" in text
