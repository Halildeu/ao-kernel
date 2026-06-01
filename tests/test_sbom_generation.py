"""Unit + smoke tests for ``scripts/generate_sbom.py`` (V5 Epic 6 E-6-1a).

The pure-Python validation layer (``validate_sbom``) is exercised
exhaustively with synthetic SBOM payloads — these tests do not require
``cyclonedx-bom``.

The end-to-end smoke (build wheel → SBOM → validate) is gated on the
``cyclonedx-bom`` extra being installed. When the extra is absent the
smoke skips cleanly so CI without ``[sbom]`` extra does not flake.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module():
    module_path = _repo_root() / "scripts" / "generate_sbom.py"
    spec = importlib.util.spec_from_file_location("generate_sbom", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MODULE = _load_module()


def _valid_sbom() -> dict[str, Any]:
    """Return a synthetic CycloneDX 1.5 JSON SBOM that passes validation."""
    return {
        "bomFormat": _MODULE.SBOM_FORMAT,
        "specVersion": _MODULE.SBOM_SCHEMA_VERSION,
        "version": 1,
        "metadata": {
            "component": {
                "type": "library",
                "name": _MODULE.RELEASE_COMPONENT_NAME,
                "version": "5.0.0",
            },
        },
        "components": [
            {"type": "library", "name": _MODULE.RELEASE_COMPONENT_NAME, "version": "5.0.0"},
            {"type": "library", "name": "jsonschema", "version": "4.23.0"},
        ],
    }


# ── validate_sbom — happy + sad paths ───────────────────────────────


def test_validate_sbom_accepts_canonical_payload() -> None:
    sbom = _valid_sbom()
    _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_wrong_bomformat() -> None:
    sbom = _valid_sbom()
    sbom["bomFormat"] = "SPDX"
    with pytest.raises(_MODULE.SBOMGenerationError, match="bomFormat mismatch"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_wrong_specversion() -> None:
    sbom = _valid_sbom()
    sbom["specVersion"] = "1.4"
    with pytest.raises(_MODULE.SBOMGenerationError, match="specVersion mismatch"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_empty_components() -> None:
    sbom = _valid_sbom()
    sbom["components"] = []
    with pytest.raises(_MODULE.SBOMGenerationError, match="components list is empty"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_missing_components_key() -> None:
    sbom = _valid_sbom()
    del sbom["components"]
    with pytest.raises(_MODULE.SBOMGenerationError, match="components list is empty"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_missing_release_component() -> None:
    sbom = _valid_sbom()
    sbom["components"] = [{"type": "library", "name": "jsonschema", "version": "4.23.0"}]
    sbom["metadata"] = {"component": {"type": "library", "name": "some-other-pkg"}}
    with pytest.raises(_MODULE.SBOMGenerationError, match="release component"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_accepts_release_in_metadata_only() -> None:
    # If the wheel name shows up as metadata.component but NOT in
    # components list, that is still a valid release SBOM shape
    # (cyclonedx-py emits metadata.component for the analyzed wheel
    # in some versions).
    sbom = _valid_sbom()
    sbom["components"] = [{"type": "library", "name": "jsonschema", "version": "4.23.0"}]
    # metadata.component.name == ao-kernel from _valid_sbom() fixture
    _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_generator_tool_leak() -> None:
    """Codex 019e8337 absorb — generator tool must NEVER appear as a
    component (would mean SBOM describes the build env, not the
    release wheel).
    """
    for leaked in ("cyclonedx-bom", "cyclonedx-python-lib", "cyclonedx-py"):
        sbom = _valid_sbom()
        sbom["components"].append({"type": "library", "name": leaked, "version": "4.0.0"})
        with pytest.raises(_MODULE.SBOMGenerationError, match="generator tool leaked"):
            _MODULE.validate_sbom(sbom)


def test_validate_sbom_rejects_generator_tool_leak_case_insensitive() -> None:
    """Case-insensitive guard — uppercase or mixed case still rejected."""
    sbom = _valid_sbom()
    sbom["components"].append({"type": "library", "name": "CycloneDX-BOM", "version": "4.0.0"})
    with pytest.raises(_MODULE.SBOMGenerationError, match="generator tool leaked"):
        _MODULE.validate_sbom(sbom)


def test_validate_sbom_handles_non_list_components_gracefully() -> None:
    sbom = _valid_sbom()
    sbom["components"] = "not-a-list"
    with pytest.raises(_MODULE.SBOMGenerationError, match="components list is empty"):
        _MODULE.validate_sbom(sbom)


# ── pyproject extra wiring ──────────────────────────────────────────


def test_sbom_extra_present_in_pyproject() -> None:
    """Pin that ``[project.optional-dependencies]`` exposes ``sbom``
    with cyclonedx-bom dependency."""
    pyproject = (_repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    assert "\nsbom = [" in pyproject, "[sbom] extra must be declared in pyproject.toml"
    # Pin the generator package name + minimum version
    assert "cyclonedx-bom>=4.0.0" in pyproject, "[sbom] extra must pin cyclonedx-bom>=4.0.0 (V5 Epic 6 E-6-1 spec)"


def test_sbom_extra_is_not_in_default_runtime_deps() -> None:
    """cyclonedx-bom must NOT slip into the runtime dependency tree —
    it is a build/release-time tool only."""
    pyproject = (_repo_root() / "pyproject.toml").read_text(encoding="utf-8")
    # Find the dependencies block (between ``dependencies = [`` and the next ``]``)
    assert "cyclonedx-bom" in pyproject, "extra must exist somewhere in pyproject"
    # The substring must appear ONCE — under [sbom], not in core deps
    occurrences = pyproject.count("cyclonedx-bom")
    assert occurrences == 1, (
        f"cyclonedx-bom appears {occurrences} times in pyproject.toml; expected exactly 1 (under [sbom])"
    )


# ── CLI wiring (dist/ rejection) ────────────────────────────────────


def test_cli_rejects_dist_output_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Codex 019e8337 absorb — script must refuse to write into
    ``dist/`` (publish.yml twine whitelist would reject the JSON)."""
    fake_wheel = tmp_path / "ao_kernel-5.0.0-py3-none-any.whl"
    fake_wheel.write_bytes(b"PK\x05\x06" + b"\x00" * 18)  # minimal "ZIP" header

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    target = dist_dir / "ao_kernel-5.0.0-sbom.cdx.json"

    rc = _MODULE.main(["--wheel", str(fake_wheel), "--output", str(target)])
    assert rc == 2
    captured = capsys.readouterr()
    assert "MUST NOT be inside dist/" in captured.err or "must NOT be inside dist/" in captured.err


def test_cli_rejects_missing_wheel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake_wheel = tmp_path / "does-not-exist.whl"
    target = tmp_path / "build" / "sbom" / "ao-kernel-sbom.cdx.json"

    rc = _MODULE.main(["--wheel", str(fake_wheel), "--output", str(target)])
    assert rc == 1
    captured = capsys.readouterr()
    assert "wheel not found" in captured.err


# ── End-to-end smoke (gated on cyclonedx-bom presence) ──────────────


def _cyclonedx_available() -> bool:
    return importlib.util.find_spec("cyclonedx_py") is not None


@pytest.mark.skipif(not _cyclonedx_available(), reason="cyclonedx-bom extra not installed")
def test_generate_sbom_end_to_end_smoke(tmp_path: Path) -> None:
    """End-to-end smoke — build a wheel from this repo, generate SBOM,
    validate output. Skipped when ``cyclonedx-bom`` extra is absent
    (CI without ``[sbom]`` extra)."""
    import subprocess
    import sys

    build_dir = tmp_path / "build-output"
    build_dir.mkdir()

    # Build a wheel from the current repo into a temp directory.
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(build_dir), str(_repo_root())],
        check=True,
        capture_output=True,
    )
    wheels = list(build_dir.glob("ao_kernel-*.whl"))
    assert wheels, f"build did not produce a wheel in {build_dir}"
    wheel = wheels[0]

    out_path = tmp_path / "build" / "sbom" / wheel.stem.replace(".whl", "-sbom.cdx.json")
    sbom = _MODULE.generate_sbom(wheel, out_path)

    assert sbom["bomFormat"] == _MODULE.SBOM_FORMAT
    assert sbom["specVersion"] == _MODULE.SBOM_SCHEMA_VERSION
    assert out_path.exists()

    # Validate JSON shape on-disk too — script must persist what it returned.
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["bomFormat"] == _MODULE.SBOM_FORMAT
    assert on_disk["specVersion"] == _MODULE.SBOM_SCHEMA_VERSION
