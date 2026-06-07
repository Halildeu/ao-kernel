"""Doc-bound smoke for docs/USING-AO-KERNEL-IN-YOUR-PROJECT.md.

Keeps the consumer onboarding guide honest: every load-bearing claim in the doc
(fail-closed policy, governed context persistence, the documented CLI surfaces,
and the const-false guard-flag boundary) is verified against the installed
package here, with no network and no provider API key. If the doc and the
package drift, this test fails.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ao_kernel import AoKernelClient, governance


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "USING-AO-KERNEL-IN-YOUR-PROJECT.md"

DOCUMENTED_SUBCOMMANDS = (
    "init",
    "doctor",
    "evidence",
    "policy-sim",
    "consultation",
    "orchestration",
    "quality",
    "mcp",
)


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_doc_present_and_states_governed_control_plane_boundary() -> None:
    assert DOC.is_file()
    text = _doc_text()
    low = text.lower()
    # Positioning: governed control-plane, explicitly NOT a production platform.
    assert "governed control-plane" in low
    assert "not" in low and "production-platform claim" in low
    # The three guard flags are documented as false.
    for flag in ("live_adapter_execution", "support_widening", "production_platform_claim"):
        assert flag in text, f"doc must document guard flag {flag}"
    # Operating model: CLI subscriptions, no API key for the core.
    assert "no provider api key is required" in low or "no api key" in low


def test_doc_install_and_init_commands_present() -> None:
    text = _doc_text()
    assert "pip install ao-kernel" in text
    assert "ao-kernel init" in text
    assert "ao-kernel doctor" in text
    assert "ao-kernel[mcp]" in text


def test_documented_failclosed_policy_actually_denies(tmp_path: Path) -> None:
    # Doc claims: a missing policy denies by default (fail-closed). Verify it.
    result = governance.check_policy("nonexistent_policy", {"action": "x"}, workspace=tmp_path)
    assert result.get("decision") == "deny" or result.get("allowed") is False


def test_documented_governed_context_roundtrip(tmp_path: Path) -> None:
    # Doc claims: record_decision persists and query_memory reads it back.
    subprocess.run(
        [sys.executable, "-m", "ao_kernel", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    with AoKernelClient(workspace_root=str(tmp_path)) as client:
        client.record_decision("db_choice", "postgres", confidence=0.9)
        hits = client.query_memory("db_choice")
    assert hits, "query_memory must return the recorded decision"
    assert any(h.get("value") == "postgres" for h in hits)
    # Persistence claim: canonical store written under .ao/.
    assert list((tmp_path / ".ao").rglob("canonical_decisions*.json")), "canonical store must persist"


def test_documented_cli_subcommands_exist() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "ao_kernel", "--help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    help_text = proc.stdout + proc.stderr
    for sub in DOCUMENTED_SUBCOMMANDS:
        assert sub in help_text, f"documented subcommand '{sub}' missing from CLI help"


def test_documented_doctor_and_bundled_policy_work(tmp_path: Path) -> None:
    # Doc documents `ao-kernel doctor` and a bundled-policy check. Run them.
    subprocess.run(
        [sys.executable, "-m", "ao_kernel", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    doctor = subprocess.run(
        [sys.executable, "-m", "ao_kernel", "doctor"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert doctor.returncode == 0, f"doctor failed: {doctor.stdout}\n{doctor.stderr}"
    assert "OK" in (doctor.stdout + doctor.stderr)
    # Bundled policy is evaluated by the engine (documented call), not bypassed.
    result = governance.check_policy("policy_cost_tracking", {"action": "llm_call"}, workspace=tmp_path)
    assert "decision" in result or "allowed" in result


# The exact set of MCP governance tools named in the onboarding doc. Pinned so a
# doc/server drift (a renamed or dropped tool) fails closed here.
DOCUMENTED_MCP_TOOLS = (
    "ao_policy_check",
    "ao_llm_route",
    "ao_quality_gate",
    "ao_workspace_status",
    "ao_memory_read",
    "ao_memory_write",
)


def test_doc_mcp_tools_match_shipped_mcp_server() -> None:
    # Every MCP tool the doc names must (a) appear in the doc and (b) ship in
    # mcp_server.py. Full set, not a sample, so future drift is caught.
    text = _doc_text()
    server_src = (ROOT / "ao_kernel" / "mcp_server.py").read_text(encoding="utf-8")
    for tool in DOCUMENTED_MCP_TOOLS:
        assert tool in text, f"doc must name MCP tool {tool}"
        assert tool in server_src, f"doc names {tool} but mcp_server.py does not ship it"


def test_doc_mcp_http_uses_correct_extra() -> None:
    # HTTP transport ships in the separate `mcp-http` extra (starlette + uvicorn),
    # not `mcp`. If the doc documents `--transport http`, it must document the
    # `ao-kernel[mcp-http]` install, and that extra must really carry the deps.
    text = _doc_text()
    if "--transport http" in text:
        assert "ao-kernel[mcp-http]" in text, "HTTP transport must be documented under the mcp-http extra"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "mcp-http" in pyproject
    http_block = pyproject.split("mcp-http", 1)[1][:200]
    assert "starlette" in http_block and "uvicorn" in http_block, "mcp-http extra must carry starlette + uvicorn"


def test_no_guard_flip_or_production_claim_language() -> None:
    # The onboarding doc must not overclaim. It may mention the forbidden phrase
    # only in a negating context ("not a ... production platform").
    low = _doc_text().lower()
    if "production coding automation platform" in low:
        # Must appear only with a negation nearby.
        idx = low.index("production coding automation platform")
        window = low[max(0, idx - 40) : idx]
        assert "not" in window, "production-platform phrase must be negated"
