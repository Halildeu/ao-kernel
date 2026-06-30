"""Productization closeout invariants for release + install + quickstart."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fresh_install_product_smoke_script_covers_wheel_sdist_and_product_commands() -> None:
    text = (ROOT / "scripts" / "fresh_install_product_smoke.py").read_text(encoding="utf-8")

    assert "--mode" in text
    assert '"wheel", "sdist", "both"' in text
    assert "repo_onboarding_doctor" in text
    assert "pr_metadata_validate" in text
    assert "orchestration_run_wrapper_dry_run" in text
    assert "orchestration_run_wrapper_async_execute" in text
    assert "ai_review_help" in text
    assert "build/fresh-install-product-smoke" in text
    assert "support_widening" in text
    assert "production_platform_claim" in text
    assert "live_adapter_execution" in text


def test_packaging_smoke_now_gates_productized_local_workflows_without_dist_pollution() -> None:
    text = (ROOT / "scripts" / "packaging_smoke.py").read_text(encoding="utf-8")

    assert "_smoke_productized_local_workflows" in text
    assert "productized-local-workflows-smoke.v1.json" in text
    assert "build\" / \"packaging-smoke\"" in text
    assert "orchestration_run_wrapper_async_execute" in text
    assert "ai_review_help" in text
    assert "dist/`` remains" in text


def test_product_quickstart_is_end_to_end_and_keeps_guard_boundary() -> None:
    text = (ROOT / "docs" / "PRODUCT-QUICKSTART.md").read_text(encoding="utf-8")

    required_tokens = (
        "python -m pip install ao-kernel==4.3.1",
        "ao-kernel repo onboarding init-config",
        "ao-kernel repo onboarding doctor",
        "ao-kernel pr-metadata generate",
        "ao-kernel pr-metadata fix",
        "ao-kernel orchestration run-wrapper",
        "ao-kernel orchestration run-wrapper-async",
        "ao-kernel ai-review collect",
        "ao-kernel ai-review consensus",
        "ao-kernel ai-review high-risk-dry-run",
        "support widening",
        "production-platform readiness",
        "live adapter execution",
    )
    for token in required_tokens:
        assert token in text


def test_readme_links_product_quickstart_and_async_wrapper_v2() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/PRODUCT-QUICKSTART.md" in text
    assert "ao-kernel orchestration run-wrapper-async" in text
    assert "external evidence required" in text
    assert "live_adapter_execution" in text
