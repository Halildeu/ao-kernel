from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _workflow_text() -> str:
    workflow = _repo_root() / ".github" / "workflows" / "ao-release-gate-deploy-cloud-run.yml"
    return workflow.read_text(encoding="utf-8")


def test_release_gate_deploy_workflow_is_trusted_oidc_cloud_run_path() -> None:
    text = _workflow_text()

    assert "name: Deploy AO Release Gate to Cloud Run" in text
    assert "workflow_run:" in text
    assert 'workflows: ["Publish AO Release Gate Container"]' in text
    assert "workflow_dispatch:" in text
    assert "id-token: write" in text
    assert "packages: read" in text
    assert "google-github-actions/auth@v2" in text
    assert "workload_identity_provider: ${{ env.GCP_WORKLOAD_IDENTITY_PROVIDER }}" in text
    assert "google-github-actions/deploy-cloudrun@v2" in text
    assert "--allow-unauthenticated --ingress=all --port=8000" in text


def test_release_gate_deploy_workflow_uses_published_image_and_health_evidence() -> None:
    text = _workflow_text()

    assert "ghcr.io/halildeu/ao-kernel-ao-release-gate-service" in text
    assert "sha-${source_sha}" in text
    assert 'docker pull "${{ steps.images.outputs.ghcr_image }}"' in text
    assert 'docker push "${{ steps.images.outputs.gar_image }}"' in text
    assert "$service_url/healthz" in text
    assert "ao-release-gate-deploy-evidence/healthz.json" in text
    assert "ao-release-gate-deploy-evidence/ao-release-gate-deploy.v1.json" in text
    assert "ao_release_gate_deployed_health_checked" in text
    assert "$SERVICE_URL/github/ao-release-gate" in text
    assert "secret_value_readback: false" in text
    assert "check_run_post: false" in text
    assert "real_pr_evidence: false" in text
    assert "branch_protection_cutover: false" in text
    assert "merge_authority_enabled: false" in text
    assert "live_adapter_execution: false" in text


def test_release_gate_deploy_workflow_keeps_prs_and_live_credentials_closed() -> None:
    text = _workflow_text()

    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert "github.event.workflow_run.event != 'pull_request'" in text
    assert "pull_request:" not in text
    assert "pull_request_target" not in text
    assert "secrets." not in text
    assert "GHCR_TOKEN: ${{ github.token }}" in text
    assert "AO_CLAUDE_CODE_CLI_AUTH" not in text
    assert "gh pr merge" not in text
    assert "gh api repos/Halildeu/ao-kernel/branches/main/protection" not in text
    assert "gcloud secrets versions access" not in text
    assert "AO_RELEASE_GATE_WEBHOOK_SECRET=${{ env.AO_RELEASE_GATE_WEBHOOK_SECRET_NAME }}" in text
    assert "AO_GITHUB_APP_PRIVATE_KEY_PEM=${{ env.AO_RELEASE_GATE_GITHUB_APP_PRIVATE_KEY_SECRET_NAME }}" in text
