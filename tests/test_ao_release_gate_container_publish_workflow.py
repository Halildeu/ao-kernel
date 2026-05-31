from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow_text() -> str:
    workflow = _repo_root() / ".github" / "workflows" / "ao-release-gate-container-publish.yml"
    return workflow.read_text(encoding="utf-8")


def test_release_gate_container_publish_workflow_builds_smokes_and_publishes_ghcr() -> None:
    text = _workflow_text()

    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service" in text
    assert "deploy/ao-release-gate-service/Dockerfile" in text
    assert 'docker build -f "$DOCKERFILE"' in text
    assert "scripts/ao_release_gate_container_smoke.py" in text
    assert "--skip-build" in text
    assert 'docker push "$image_sha"' in text
    assert 'docker push "$image_main"' in text
    assert "sha-${GITHUB_SHA}" in text


def test_release_gate_container_publish_workflow_keeps_prs_and_live_credentials_closed() -> None:
    text = _workflow_text()

    assert "contents: read" in text
    assert "packages: write" in text
    assert "github.event_name == 'workflow_dispatch' || github.ref == 'refs/heads/main'" in text
    assert "GHCR_TOKEN: ${{ github.token }}" in text
    assert "pull_request" in text
    assert "codex/**" in text
    assert "secrets." not in text
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in text
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET" not in text
    assert "AO_GITHUB_APP_PRIVATE_KEY" not in text
    assert "/github/ao-release-gate" not in text
    assert "branch_protection" not in text


def test_release_gate_container_readme_records_publish_boundary() -> None:
    readme = (_repo_root() / "deploy" / "ao-release-gate-service" / "README.md").read_text(encoding="utf-8")

    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service:sha-<commit>" in readme
    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service:main" in readme
    assert "POST /github/ao-release-gate" in readme
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET" in readme
    assert "AO_CLAUDE_CODE_CLI_AUTH" in readme
    assert "does not change branch protection" in readme
