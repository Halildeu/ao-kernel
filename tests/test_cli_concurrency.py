"""CLI concurrency + sub-directory invariants (PR-C8).

Covers three scenarios called out in the handoff:

1. `ao-kernel doctor` invoked from a sub-directory still resolves the
   workspace via `workspace.project_root()` (the C0 invariant).
2. `ao-kernel init` + `ao-kernel migrate --dry-run` happy path from a
   fresh directory.
3. Parallel canonical writes from multiple threads serialize through
   the CAS lock introduced in C5a — no interleaved writes corrupt
   the store.

These tests exercise the in-process `main(...)` entrypoint rather
than spawning subprocesses; subprocess-based CLI coverage is
provided by the existing `tests/test_cli.py` suite.
"""

from __future__ import annotations

import threading
from pathlib import Path

from ao_kernel.cli import main
from ao_kernel.context.canonical_store import promote_decision, query


# ── 1) `doctor` from a sub-directory ──────────────────────────────


class TestDoctorFromSubdirectory:
    def test_doctor_resolves_workspace_from_subdir(
        self, tmp_workspace, capsys, monkeypatch,
    ):
        # tmp_workspace fixture has already chdir'd into the workspace root.
        subdir = tmp_workspace.parent / "nested" / "deep"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)
        rc = main(["doctor"])
        assert rc == 0
        out = capsys.readouterr().out
        # doctor emits workspace-relative diagnostics; the workspace must
        # have been discovered via project_root() even though we are two
        # directories below it.
        assert "workspace" in out.lower() or "ok" in out.lower()


# ── 2) init + migrate --dry-run happy path ────────────────────────


class TestInitThenMigrateDryRun:
    def test_init_then_dry_run_migrate(self, empty_dir, capsys):
        rc_init = main(["init"])
        assert rc_init == 0
        assert (empty_dir / ".ao").is_dir()

        capsys.readouterr()  # drain init output

        rc_dry = main(["migrate", "--dry-run"])
        assert rc_dry == 0
        out = capsys.readouterr().out
        # --dry-run returns structured JSON per existing coverage; any
        # actionable payload is acceptable — we just need the command to
        # succeed from a freshly-initialized workspace.
        assert out.strip()


# ── 3) Parallel promote_decision through CAS lock ─────────────────


class TestParallelCanonicalWrites:
    def test_concurrent_promote_decisions_serialize(self, tmp_workspace: Path):
        """Threads issuing promote_decision concurrently must all land
        without corrupting the store. The C5a `_mutate_with_cas` FS
        lock serializes writers; every key must be retrievable after
        the threads finish."""
        workspace = tmp_workspace.parent  # project root (.ao parent)

        errors: list[BaseException] = []

        def _writer(idx: int) -> None:
            try:
                promote_decision(
                    workspace,
                    key=f"concurrent.key.{idx:02d}",
                    value=f"value-{idx}",
                    source="test",
                    confidence=0.9,
                )
            except BaseException as exc:  # pragma: no cover — surfaced via errors
                errors.append(exc)

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"unexpected writer failures: {errors!r}"
        items = query(workspace, key_pattern="concurrent.key.*")
        keys = {item["key"] for item in items}
        expected = {f"concurrent.key.{i:02d}" for i in range(8)}
        assert expected.issubset(keys), (
            f"missing keys after concurrent writes: expected={expected}, got={keys}"
        )
