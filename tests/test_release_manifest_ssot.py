"""Product release manifest SSOT tests.

The bundled manifest is the consumer/operator-facing version alignment surface:
it pins the published product version and the install/deploy surfaces that must
move with it. Contract versions such as schema/policy v1 and roadmap lines such
as V5 remain independent lifecycle markers by design.
"""

from __future__ import annotations

import importlib.resources
import json
import tomllib
from pathlib import Path

import yaml


_REPO_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST = _REPO_ROOT / "ao_kernel" / "defaults" / "release" / "product-release-manifest.v1.json"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"


def _load_manifest() -> dict:
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def _load_pyproject() -> dict:
    with _PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def _load_chart() -> dict:
    return yaml.safe_load((_REPO_ROOT / "deploy" / "helm" / "ao-kernel" / "Chart.yaml").read_text(encoding="utf-8"))


def _load_values() -> dict:
    return yaml.safe_load((_REPO_ROOT / "deploy" / "helm" / "ao-kernel" / "values.yaml").read_text(encoding="utf-8"))


def _load_operator_checklist() -> dict:
    return json.loads(
        (_REPO_ROOT / "docs" / "operator-runbooks" / "operator-action-checklist.v1.json").read_text(
            encoding="utf-8"
        )
    )


def test_release_manifest_shape_and_authority_boundary() -> None:
    manifest = _load_manifest()

    assert manifest["schema_version"] == "product-release-manifest.v1"
    assert manifest["artifact_kind"] == "product_release_manifest"
    assert manifest["product"] == "ao-kernel"
    assert manifest["release_line"] == "v4"
    assert manifest["published_package"]["publish_status"] == "operator_publish_pending"
    assert manifest["release_authority"] == {
        "source_ready_authority": "ao-release-gate+github-ruleset",
        "publish_authority": "operator-runbook",
        "ai_output_release_authority": False,
    }


def test_release_manifest_is_packaged_as_importlib_resource() -> None:
    data = (
        importlib.resources.files("ao_kernel.defaults.release")
        .joinpath("product-release-manifest.v1.json")
        .read_text(encoding="utf-8")
    )

    assert json.loads(data) == _load_manifest()


def test_product_version_matches_python_package_and_cli_surfaces() -> None:
    import ao_kernel

    manifest = _load_manifest()
    pyproject = _load_pyproject()
    product_version = manifest["product_version"]

    assert product_version == "4.3.1"
    assert pyproject["project"]["name"] == manifest["published_package"]["name"]
    assert pyproject["project"]["version"] == product_version
    assert ao_kernel.__version__ == product_version
    assert manifest["published_package"]["version"] == product_version
    assert manifest["components"]["python_package"] == product_version
    assert manifest["components"]["cli"] == product_version


def test_product_version_matches_install_docs_helm_app_and_operator_publish_ref() -> None:
    manifest = _load_manifest()
    version = manifest["product_version"]
    tag_ref = f"refs/tags/v{version}"

    onboarding = (_REPO_ROOT / "docs" / "USING-AO-KERNEL-IN-YOUR-PROJECT.md").read_text(encoding="utf-8")
    assert f"ao-kernel=={version}" in onboarding
    assert manifest["components"]["docs_install_pin"] == version

    chart = _load_chart()
    values = _load_values()
    assert chart["appVersion"] == version
    assert values["image"]["tag"] == version
    assert manifest["components"]["helm_app_version"] == version

    checklist = _load_operator_checklist()
    publish_action = next(action for action in checklist["actions"] if action["id"] == "p0-1-pypi-publish")
    assert publish_action["dispatch_inputs"]["ref"] == tag_ref
    assert any(f"/{version}/" in artifact for artifact in publish_action["expected_artifacts"])
    assert manifest["published_package"]["operator_publish_ref"] == tag_ref
    assert manifest["components"]["operator_publish_ref"] == tag_ref
    assert manifest["published_package"]["pypi_project_url"].endswith(f"/{version}/")


def test_non_product_versions_are_declared_not_equalized_by_design() -> None:
    manifest = _load_manifest()
    chart = _load_chart()
    not_equalized = manifest["not_equalized_by_design"]

    assert chart["version"] != manifest["product_version"]
    assert "helm_chart_version" in not_equalized
    assert "json_schema_versions" in not_equalized
    assert "policy_versions" in not_equalized
    assert "v5" in not_equalized


def test_manifest_keeps_release_guard_flags_false() -> None:
    assert _load_manifest()["guard_flags"] == {
        "support_widening": False,
        "production_platform_claim": False,
        "live_adapter_execution": False,
    }
