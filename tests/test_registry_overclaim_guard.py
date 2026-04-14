"""Guard test: prevent re-introducing capability overclaims.

Tranş A / A7 + CNS-005 R2. The capabilities `vision`, `audio`,
`code_agentic`, and `structured_output` are explicitly `unsupported` in
v2.2.0 across all providers because no provider-side integration exists.

If someone bumps one to `supported` / `experimental` without also wiring
the provider code + contract test, this test fails. Reviewer gets a clear
signal that registry truth and provider truth must move together.
"""

from __future__ import annotations

import pytest

from ao_kernel.config import load_default


GUARDED_CAPS = ("vision", "audio", "code_agentic", "structured_output")


@pytest.fixture(scope="module")
def registry() -> dict:
    return load_default("registry", "provider_capability_registry.v1.json")


def test_every_provider_declares_guarded_caps(registry: dict) -> None:
    """Sanity: each provider's capabilities block lists the guarded keys."""
    for pid, pdata in registry["providers"].items():
        caps = pdata["capabilities"]
        for cap in GUARDED_CAPS:
            assert cap in caps, f"{pid} is missing capability key {cap!r}"


def test_guarded_caps_all_unsupported(registry: dict) -> None:
    """If any guarded cap is not `unsupported`, the provider integration
    and a contract test must exist first — block the registry change here.
    """
    overclaims: list[str] = []
    for pid, pdata in registry["providers"].items():
        caps = pdata["capabilities"]
        for cap in GUARDED_CAPS:
            status = caps.get(cap)
            if status != "unsupported":
                overclaims.append(f"{pid}.{cap}={status!r}")
    assert not overclaims, (
        "Capability overclaim(s) detected. Each of vision / audio / code_agentic / "
        "structured_output MUST remain 'unsupported' until a provider-side "
        "implementation AND a contract test land together. See CNS-005 R2.\n\n"
        "Overclaims: " + ", ".join(overclaims)
    )
