"""Tests for extension activation dispatch (B3f, CNS-008).

Covers:
  - ActionRegistry explicit registration, duplicate protection, resolve/invoke
  - Bootstrap wires PRJ-HELLO when its manifest is enabled+healthy
  - Bootstrap skips when manifest absent/disabled/blocked
  - AoKernelClient exposes extensions + action_registry + call_action
  - Hello extension round-trip via the client
"""

from __future__ import annotations

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
        assert registered == 1
        assert actions.resolve("hello_world") is not None


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
