"""Generate a CycloneDX 1.5 SBOM for an ao-kernel wheel.

V5 Epic 6 E-6-1a — release SBOM evidence generator (Codex thread
019e8337 absorb).

Authority model
---------------

The truth of "what is in the release" is the wheel itself, not the
development checkout or the workflow runner's Python environment. So
this script does not introspect the calling environment. Instead it:

1. Creates an isolated temporary virtual environment.
2. Installs the supplied wheel (and only the wheel + its required deps)
   into that venv.
3. Invokes ``cyclonedx-py environment <target-venv-python>`` against the
   target venv to produce CycloneDX JSON.
4. Validates the output against a minimal set of invariants:
   - ``bomFormat == "CycloneDX"``
   - ``specVersion == "1.5"``
   - ``components`` is non-empty
   - ``ao-kernel`` (the released wheel) appears as a component or in
     ``metadata.component``
   - The generator tool itself (``cyclonedx-bom`` / ``cyclonedx-py``)
     does NOT appear among the components (would pollute the release
     truth — the generator runs OUTSIDE the target venv).

The script writes the validated SBOM to the requested output path AND
returns the parsed dict for callers that want to do further
attestation (sigstore/cosign integration is out of scope for E-6-1a;
see Epic 9 final promotion follow-up).

CLI form (Codex iter-1 absorb — pinned schema version, explicit flags
that survive cyclonedx-bom 4.x → 5.x migration):

    python -m cyclonedx_py environment <TARGET_VENV_PYTHON> \\
        --output-format JSON \\
        --schema-version 1.5 \\
        --output-file <OUTPUT_PATH>

The generator is invoked from the *calling* (build) environment, where
``cyclonedx-bom`` is installed via ``pip install ao-kernel[sbom]``. The
target venv only contains the released wheel + its runtime deps;
that is what the SBOM describes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# CycloneDX JSON spec version pinned for V5 Epic 6 E-6-1. Bumping
# spec version is a separate decision (Codex iter-1 absorb).
SBOM_SCHEMA_VERSION = "1.5"
SBOM_FORMAT = "CycloneDX"
GENERATOR_PACKAGE_NAMES: frozenset[str] = frozenset(
    {
        "cyclonedx-bom",
        "cyclonedx-python-lib",
        "cyclonedx-py",
    }
)
RELEASE_COMPONENT_NAME = "ao-kernel"


class SBOMGenerationError(RuntimeError):
    """Raised when SBOM generation fails for any reason."""


def _ensure_wheel_path(wheel: Path) -> None:
    if not wheel.exists():
        raise SBOMGenerationError(f"wheel not found: {wheel}")
    if not wheel.is_file():
        raise SBOMGenerationError(f"wheel path is not a file: {wheel}")
    if wheel.suffix != ".whl":
        raise SBOMGenerationError(f"expected .whl extension: {wheel}")


def _build_target_venv(venv_dir: Path) -> Path:
    """Create a fresh venv and return its python executable path."""
    subprocess.run(
        [sys.executable, "-m", "venv", str(venv_dir)],
        check=True,
        capture_output=True,
    )
    py = venv_dir / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not py.exists():
        raise SBOMGenerationError(f"target venv python missing: {py}")
    return py


def _install_wheel(target_python: Path, wheel: Path) -> None:
    """Install the wheel + its required runtime deps into target venv."""
    subprocess.run(
        [
            str(target_python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--disable-pip-version-check",
            "--quiet",
            str(wheel),
        ],
        check=True,
        capture_output=True,
    )


def _run_cyclonedx(
    target_python: Path,
    output_path: Path,
    schema_version: str = SBOM_SCHEMA_VERSION,
) -> None:
    """Invoke cyclonedx-py from the calling env against target venv."""
    subprocess.run(
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "environment",
            str(target_python),
            "--output-format",
            "JSON",
            "--schema-version",
            schema_version,
            "--output-file",
            str(output_path),
        ],
        check=True,
        capture_output=True,
    )


def _component_names(sbom: dict[str, Any]) -> list[str]:
    """Return the list of component names recorded in the SBOM body."""
    components = sbom.get("components") or []
    if not isinstance(components, list):
        return []
    names: list[str] = []
    for component in components:
        if isinstance(component, dict):
            name = component.get("name")
            if isinstance(name, str):
                names.append(name)
    return names


def _metadata_component_name(sbom: dict[str, Any]) -> str | None:
    metadata = sbom.get("metadata")
    if not isinstance(metadata, dict):
        return None
    component = metadata.get("component")
    if not isinstance(component, dict):
        return None
    name = component.get("name")
    if isinstance(name, str):
        return name
    return None


def validate_sbom(sbom: dict[str, Any]) -> None:
    """Validate the SBOM against the V5 E-6-1 invariant set.

    Raises ``SBOMGenerationError`` on any violation. The invariants
    were pinned by Codex iter-1 absorb (thread ``019e8337``):

    - ``bomFormat == "CycloneDX"``
    - ``specVersion == SBOM_SCHEMA_VERSION``
    - non-empty ``components`` list
    - the released wheel (``ao-kernel``) appears either as a component
      or as ``metadata.component``
    - the generator tool itself does NOT appear among the components
      (would mean the SBOM is describing the build env, not the
      release wheel)
    """
    if sbom.get("bomFormat") != SBOM_FORMAT:
        raise SBOMGenerationError(
            f"bomFormat mismatch: expected {SBOM_FORMAT!r}, got {sbom.get('bomFormat')!r}"
        )
    if sbom.get("specVersion") != SBOM_SCHEMA_VERSION:
        raise SBOMGenerationError(
            f"specVersion mismatch: expected {SBOM_SCHEMA_VERSION!r}, got {sbom.get('specVersion')!r}"
        )
    names = _component_names(sbom)
    if not names:
        raise SBOMGenerationError("components list is empty; SBOM has no captured packages")

    metadata_name = _metadata_component_name(sbom)
    release_visible = RELEASE_COMPONENT_NAME in names or metadata_name == RELEASE_COMPONENT_NAME
    if not release_visible:
        raise SBOMGenerationError(
            f"release component {RELEASE_COMPONENT_NAME!r} not present in SBOM "
            f"(components={names!r}, metadata.component.name={metadata_name!r})"
        )

    leaked_generators = sorted(
        {name for name in names if name.lower() in {g.lower() for g in GENERATOR_PACKAGE_NAMES}}
    )
    if leaked_generators:
        raise SBOMGenerationError(
            f"generator tool leaked into SBOM components — release truth contaminated: {leaked_generators!r}"
        )


def generate_sbom(
    wheel_path: Path,
    output_path: Path,
    schema_version: str = SBOM_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Generate + validate an SBOM for ``wheel_path``.

    Writes JSON to ``output_path`` and returns the parsed dict.
    Raises ``SBOMGenerationError`` on any failure.

    The implementation creates an isolated target venv, installs the
    wheel, then runs cyclonedx-py against that venv. The generator
    tool itself stays in the *calling* (build) environment, so it
    never appears as a component of the release SBOM.
    """
    _ensure_wheel_path(wheel_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ao-sbom-") as tmpdir:
        venv_dir = Path(tmpdir) / "target-venv"
        try:
            target_python = _build_target_venv(venv_dir)
            _install_wheel(target_python, wheel_path)
            _run_cyclonedx(target_python, output_path, schema_version=schema_version)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise SBOMGenerationError(
                f"SBOM generation step failed: {exc.cmd} (exit {exc.returncode}): {stderr.strip()}"
            ) from exc

    try:
        parsed = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SBOMGenerationError(f"failed to read SBOM JSON output: {exc}") from exc

    if not isinstance(parsed, dict):
        raise SBOMGenerationError(
            f"SBOM JSON root must be an object; got {type(parsed).__name__}"
        )
    sbom: dict[str, Any] = parsed

    validate_sbom(sbom)

    # NOTE: caller chooses the final artifact path. We intentionally do
    # NOT default to ``dist/`` because publish.yml strips non-distribution
    # files from dist/ and the twine whitelist would reject SBOM JSON.
    # Recommended path: ``build/sbom/ao_kernel-<version>-sbom.cdx.json``
    # or ``release-artifacts/...``. See plan doc §3.
    if not output_path.exists():
        raise SBOMGenerationError(f"SBOM output path missing after generation: {output_path}")

    return sbom


def _shutil_check() -> None:
    if shutil.which(sys.executable) is None:
        raise SBOMGenerationError(f"Python executable not found: {sys.executable}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_sbom",
        description="Generate a CycloneDX 1.5 SBOM for an ao-kernel wheel (V5 Epic 6 E-6-1).",
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        required=True,
        help="Path to the wheel file to describe.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the CycloneDX JSON SBOM (NOT inside dist/).",
    )
    parser.add_argument(
        "--schema-version",
        default=SBOM_SCHEMA_VERSION,
        help=f"CycloneDX schema version (default: {SBOM_SCHEMA_VERSION}).",
    )
    args = parser.parse_args(argv)

    _shutil_check()
    if args.output.parent.resolve().name == "dist":
        # Codex iter-1 invariant — never write into dist/ (twine whitelist).
        print(
            f"::error::SBOM output path must NOT be inside dist/ (got {args.output}). "
            "publish.yml will reject non-distribution files.",
            file=sys.stderr,
        )
        return 2

    try:
        sbom = generate_sbom(args.wheel, args.output, schema_version=args.schema_version)
    except SBOMGenerationError as exc:
        print(f"::error::SBOM generation failed: {exc}", file=sys.stderr)
        return 1

    components = sbom.get("components") or []
    component_count = len(components) if isinstance(components, list) else 0
    print(
        f"SBOM generated: {args.output} (specVersion={sbom.get('specVersion')}, "
        f"components={component_count})"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover (entrypoint)
    sys.exit(main())
