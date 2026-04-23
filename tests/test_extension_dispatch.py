"""Tests for extension activation dispatch (B3f, CNS-008).

Covers:
  - ActionRegistry explicit registration, duplicate protection, resolve/invoke
  - Bootstrap wires PRJ-HELLO when its manifest is enabled+healthy
  - Bootstrap skips when manifest absent/disabled/blocked
  - AoKernelClient exposes extensions + action_registry + call_action
  - Hello extension round-trip via the client
"""

from __future__ import annotations

import json

import pytest

from ao_kernel.client import AoKernelClient
from ao_kernel.extensions.dispatch import ActionRegistry
from ao_kernel.extensions.loader import ExtensionRegistry


class TestActionRegistry:
    def test_register_and_resolve(self):
        reg = ActionRegistry()
        reg.register("foo", lambda p: {"ok": True, **p}, extension_id="EXT-X")
        record = reg.resolve("foo")
        assert record is not None
        assert record.extension_id == "EXT-X"

    def test_unknown_action_resolve_returns_none(self):
        reg = ActionRegistry()
        assert reg.resolve("missing") is None

    def test_duplicate_registration_rejected(self):
        reg = ActionRegistry()
        reg.register("a", lambda p: {}, extension_id="EXT-1")
        with pytest.raises(ValueError, match="already registered"):
            reg.register("a", lambda p: {}, extension_id="EXT-2")

    def test_replace_flag_overrides(self):
        reg = ActionRegistry()
        reg.register("a", lambda p: {"v": 1}, extension_id="EXT-1")
        reg.register("a", lambda p: {"v": 2}, extension_id="EXT-2", replace=True)
        assert reg.resolve("a").extension_id == "EXT-2"

    def test_invoke_calls_handler(self):
        reg = ActionRegistry()
        reg.register("echo", lambda p: {"echoed": p.get("msg")}, extension_id="EXT-E")
        result = reg.invoke("echo", {"msg": "hi"})
        assert result == {"echoed": "hi"}

    def test_invoke_unknown_raises(self):
        reg = ActionRegistry()
        with pytest.raises(LookupError, match="no handler registered"):
            reg.invoke("nope", {})

    def test_list_actions_is_sorted(self):
        reg = ActionRegistry()
        reg.register("b", lambda p: {}, extension_id="X")
        reg.register("a", lambda p: {}, extension_id="X")
        names = [r.action for r in reg.list_actions()]
        assert names == ["a", "b"]


class TestBootstrapHelloExtension:
    def test_hello_world_registered_by_default(self):
        """B3f DoD: PRJ-HELLO activates end-to-end via default bootstrap."""
        client = AoKernelClient()
        record = client.action_registry.resolve("hello_world")
        assert record is not None
        assert record.extension_id == "PRJ-HELLO"

    def test_call_action_round_trip(self):
        """The whole point of B3f: client.call_action() actually runs."""
        client = AoKernelClient()
        out = client.call_action("hello_world", {"name": "tester"})
        assert out["ok"] is True
        assert out["extension_id"] == "PRJ-HELLO"
        assert "tester" in out["greeting"]

    def test_call_action_default_name(self):
        client = AoKernelClient()
        out = client.call_action("hello_world")
        assert "ao-kernel" in out["greeting"]

    def test_extensions_property_exposes_registry(self):
        client = AoKernelClient()
        ext = client.extensions.get("PRJ-HELLO")
        assert ext is not None
        assert ext.enabled is True
        assert ext.truth_tier == "runtime_backed"
        assert ext.runtime_handler_registered is True
        assert "hello_world" in ext.entrypoints.get("kernel_api_actions", [])


class TestBootstrapKernelApiExtension:
    def test_kernel_api_default_handler_id_is_explicit(self):
        from ao_kernel.extensions.bootstrap import default_handler_extension_ids

        assert "PRJ-KERNEL-API" in default_handler_extension_ids()

    def test_kernel_api_actions_registered_by_default(self):
        client = AoKernelClient()

        for action in (
            "system_status",
            "doc_nav_check",
            "project_status",
            "roadmap_follow",
            "roadmap_finish",
        ):
            record = client.action_registry.resolve(action)
            assert record is not None
            assert record.extension_id == "PRJ-KERNEL-API"

    def test_kernel_api_system_status_payload_is_bounded(self):
        client = AoKernelClient()

        out = client.call_action("system_status", {"detail": True, "ignored": "x"})

        assert out["ok"] is True
        assert out["action"] == "system_status"
        assert out["extension_id"] == "PRJ-KERNEL-API"
        result = out["result"]
        assert result["supported_actions"] == [
            "system_status",
            "doc_nav_check",
            "project_status",
            "roadmap_follow",
            "roadmap_finish",
        ]
        assert result["read_only_actions"] == ["system_status", "doc_nav_check"]
        assert result["write_actions"] == [
            "project_status",
            "roadmap_follow",
            "roadmap_finish",
        ]
        contract = result["write_side_contract"]
        assert contract["dry_run_default"] is True
        assert contract["require_confirm_for_write"] is True
        assert result["params_echo"] == {"detail": True}
        truth = result["extension_truth"]
        assert truth["runtime_backed"] == 2
        assert "PRJ-KERNEL-API" in truth["runtime_backed_ids"]

    def test_kernel_api_doc_nav_check_reports_clean_runtime_refs(self):
        client = AoKernelClient()

        out = client.call_action("doc_nav_check")

        assert out["ok"] is True
        assert out["action"] == "doc_nav_check"
        result = out["result"]
        assert result["network_required"] is False
        assert result["workspace_write"] is False
        ext = result["extension"]
        assert ext["extension_id"] == "PRJ-KERNEL-API"
        assert ext["truth_tier"] == "runtime_backed"
        assert ext["runtime_handler_registered"] is True
        assert ext["kernel_api_actions"] == [
            "system_status",
            "doc_nav_check",
            "project_status",
            "roadmap_follow",
            "roadmap_finish",
        ]
        assert ext["missing_runtime_refs"] == []
        assert ext["remap_candidate_refs"] == []
        assert result["write_side_contract"]["dry_run_default"] is True

    def test_project_status_requires_workspace_root(self):
        client = AoKernelClient()
        out = client.call_action("project_status", {})

        assert out["ok"] is False
        assert out["status"] == "BLOCKED"
        assert out["error"]["code"] == "WORKSPACE_ROOT_REQUIRED"

    def test_project_status_dry_run_default_no_side_effect(self, tmp_path):
        client = AoKernelClient()

        out = client.call_action(
            "project_status",
            {"workspace_root": str(tmp_path)},
        )

        assert out["ok"] is True
        result = out["result"]
        assert result["dry_run"] is True
        assert result["write_applied"] is False
        report_path = tmp_path / result["report_path"]
        assert not report_path.exists()

    def test_project_status_write_requires_confirm_token(self, tmp_path):
        client = AoKernelClient()
        out = client.call_action(
            "project_status",
            {
                "workspace_root": str(tmp_path),
                "dry_run": False,
            },
        )

        assert out["ok"] is False
        assert out["status"] == "BLOCKED"
        assert out["error"]["code"] == "WRITE_CONFIRM_REQUIRED"

    def test_project_status_idempotent_write_contract(self, tmp_path):
        client = AoKernelClient()
        params = {
            "workspace_root": str(tmp_path),
            "dry_run": False,
            "confirm_write": "I_UNDERSTAND_SIDE_EFFECTS",
            "request_id": "req-1",
        }

        first = client.call_action("project_status", params)
        second = client.call_action("project_status", params)

        assert first["ok"] is True
        assert first["result"]["write_applied"] is True
        assert first["result"]["idempotent"] is False
        assert second["ok"] is True
        assert second["result"]["write_applied"] is False
        assert second["result"]["idempotent"] is True

    def test_roadmap_follow_conflict_and_takeover(self, tmp_path):
        client = AoKernelClient()
        base_params = {
            "workspace_root": str(tmp_path),
            "dry_run": False,
            "confirm_write": "I_UNDERSTAND_SIDE_EFFECTS",
        }

        first = client.call_action(
            "roadmap_follow",
            {**base_params, "roadmap_id": "A", "step_id": "s1"},
        )
        conflict = client.call_action(
            "roadmap_follow",
            {**base_params, "roadmap_id": "B", "step_id": "s1"},
        )
        takeover = client.call_action(
            "roadmap_follow",
            {
                **base_params,
                "roadmap_id": "B",
                "step_id": "s1",
                "allow_takeover": True,
            },
        )

        assert first["ok"] is True
        assert conflict["ok"] is False
        assert conflict["status"] == "BLOCKED"
        assert conflict["error"]["code"] == "ROADMAP_CONFLICT"
        assert takeover["ok"] is True
        assert takeover["result"]["status"] == "following"

    def test_roadmap_finish_requires_follow_then_becomes_idempotent(self, tmp_path):
        client = AoKernelClient()
        base_params = {
            "workspace_root": str(tmp_path),
            "dry_run": False,
            "confirm_write": "I_UNDERSTAND_SIDE_EFFECTS",
            "roadmap_id": "R1",
            "step_id": "s2",
        }

        not_following = client.call_action("roadmap_finish", base_params)
        follow = client.call_action("roadmap_follow", base_params)
        finish = client.call_action("roadmap_finish", base_params)
        finish_again = client.call_action("roadmap_finish", base_params)

        assert not_following["ok"] is False
        assert not_following["status"] == "BLOCKED"
        assert not_following["error"]["code"] == "ROADMAP_NOT_FOLLOWING"
        assert follow["ok"] is True
        assert finish["ok"] is True
        assert finish["result"]["idempotent"] is False
        assert finish["result"]["status"] == "finished"
        assert finish_again["ok"] is True
        assert finish_again["result"]["idempotent"] is True

    def test_write_partial_failure_restores_previous_state(self, tmp_path, monkeypatch):
        from ao_kernel.extensions.handlers import prj_kernel_api

        client = AoKernelClient()
        base_params = {
            "workspace_root": str(tmp_path),
            "dry_run": False,
            "confirm_write": "I_UNDERSTAND_SIDE_EFFECTS",
            "roadmap_id": "ROLLBACK-1",
            "step_id": "s1",
        }
        first = client.call_action("roadmap_follow", base_params)
        assert first["ok"] is True

        state_path = tmp_path / ".ao" / "state" / "kernel_api_roadmap_state.v1.json"
        before = state_path.read_text(encoding="utf-8")

        def _boom(path, entry):  # noqa: ARG001
            raise RuntimeError("forced-audit-failure")

        monkeypatch.setattr(prj_kernel_api, "_append_jsonl", _boom)
        failed = client.call_action(
            "roadmap_follow",
            {**base_params, "step_id": "s2"},
        )

        assert failed["ok"] is False
        assert failed["error"]["code"] == "WRITE_PARTIAL_FAILURE_ROLLBACK"
        after = state_path.read_text(encoding="utf-8")
        assert after == before
        restored = json.loads(after)
        assert restored["last_step_id"] == "s1"


class TestBootstrapSkipsBlocked:
    def test_bootstrap_skips_disabled_manifest(self, tmp_path, monkeypatch):
        """Disabled manifests are not wired into the action registry."""
        # Build an ExtensionRegistry that claims PRJ-HELLO is disabled.
        reg = ExtensionRegistry()
        from ao_kernel.extensions.loader import ExtensionManifest

        fake = ExtensionManifest(
            version="v1",
            extension_id="PRJ-HELLO",
            semver="1.0.0",
            origin="CORE",
            owner="CORE",
            layer_contract={"write_roots_allowlist": []},
            entrypoints={"kernel_api_actions": ["hello_world"]},
            policies=[],
            ui_surfaces=[],
            compat={"core_min": "0.0.0", "core_max": "", "notes": []},
            enabled=False,  # <-- key
        )
        reg._extensions["PRJ-HELLO"] = fake

        from ao_kernel.extensions.bootstrap import register_default_handlers
        actions = ActionRegistry()
        registered = register_default_handlers(actions, extensions=reg)
        assert registered == 0
        assert actions.resolve("hello_world") is None

    def test_bootstrap_skips_activation_blocked(self):
        """Compat-blocked manifests are skipped even when enabled=True."""
        from ao_kernel.extensions.loader import ExtensionManifest
        reg = ExtensionRegistry()
        reg._extensions["PRJ-HELLO"] = ExtensionManifest(
            version="v1",
            extension_id="PRJ-HELLO",
            semver="1.0.0",
            origin="CORE",
            owner="CORE",
            layer_contract={"write_roots_allowlist": []},
            entrypoints={"kernel_api_actions": ["hello_world"]},
            policies=[],
            ui_surfaces=[],
            compat={"core_min": "99.0.0", "core_max": "", "notes": []},
            enabled=True,
            activation_blockers=("compat:core_min=99.0.0 > current=2.2.0",),
        )
        from ao_kernel.extensions.bootstrap import register_default_handlers
        actions = ActionRegistry()
        registered = register_default_handlers(actions, extensions=reg)
        assert registered == 0

    def test_bootstrap_without_extensions_registers_unconditionally(self):
        """Library-mode callers can bypass the gate by passing extensions=None."""
        from ao_kernel.extensions.bootstrap import register_default_handlers
        actions = ActionRegistry()
        registered = register_default_handlers(actions, extensions=None)
        assert registered == 2
        assert actions.resolve("hello_world") is not None
        assert actions.resolve("system_status") is not None
        assert actions.resolve("doc_nav_check") is not None


class TestFailureIsolation:
    def test_handler_registration_failure_does_not_break_client(self, monkeypatch):
        """If one handler blows up, others still register and client init succeeds."""

        def exploding_register(actions):
            raise RuntimeError("handler coded bug")

        # Replace the real module registration with one that raises.
        class FakeModule:
            register = staticmethod(exploding_register)

        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "ao_kernel.extensions.handlers.prj_hello":
                return FakeModule
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        # Client init must not raise even when every handler fails.
        client = AoKernelClient()
        assert client.action_registry is not None
        assert client.action_registry.resolve("hello_world") is None
