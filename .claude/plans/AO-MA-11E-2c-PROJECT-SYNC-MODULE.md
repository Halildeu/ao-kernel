# AO-MA-11E-2c — Project sync module + CLI

> V5 Epic 1 (E-1-2 systematization slice)
> Implementer: Anthropic Claude (Opus 4.7 1M)
> Reviewer (planned): OpenAI Codex (cross-AI 2-way)

## 1. Why this slice

Operator rule (2026-06-02): all project-sync work must live inside the
``ao_kernel`` Python module, not behind a label or a shell script. Earlier
AO-MA-11E-2 work mixed module logic with workflow YAML in a single PR and
hit the API Overloaded ceiling at 45 tool uses. This slice splits the
module out cleanly so the follow-up workflow PR can land it atomically.

## 2. Scope

In:
- New package ``ao_kernel/project_sync/`` (errors, manifest, project_v2,
  issues, derivers, slice_adder, drift_healer, label_migrator, cli,
  __init__).
- CLI extension: ``ao-kernel project {sync,drift,add-slice,field-set,
  label-cleanup,from-pr}`` wired into ``ao_kernel/cli.py``.
- Four schemas under ``ao_kernel/defaults/schemas/project-sync-*.v1.json``
  (drift-report, sync-report, add-slice-request, label-migration-report).
- 46 tests under ``tests/test_project_sync_*.py`` (manifest, derivers,
  slice_adder, drift_healer, label_migrator, cli, schemas).

Out (next slice):
- ``.github/workflows/*.yml`` mutations (mirror sync workflow + drift
  guard workflow + label-cleanup dispatch). High-risk path; operator gate
  required; lands in a follow-up PR.
- Manifest amendment to record the new module wiring (lands with the
  workflow PR alongside the workflow evidence).

## 3. Module architecture

```
ao_kernel/project_sync/
  __init__.py            # Public facade — 24 re-exports
  errors.py              # ProjectSyncError tree
  manifest.py            # ProjectionManifest dataclass (load/save/digest)
  project_v2.py          # gh GraphQL wrapper (subprocess)
  issues.py              # gh issues wrapper (subprocess)
  derivers.py            # label/body -> field rules
  slice_adder.py         # atomic create issue + board + fields (with rollback)
  drift_healer.py        # check/heal manifest <-> board parity
  label_migrator.py      # migrate convention labels to fields then drop
  cli.py                 # argparse handlers
```

All clients are dependency-injected so tests run without touching the
network. The CLI is a thin parser/printer over the pure modules.

## 4. Field map

| Project field | Source rule |
|---|---|
| Epic | label ``epic-<id>`` (e.g. ``epic-1`` -> ``"1"``, ``epic-p0`` -> ``"P0"``) |
| Risk | label ``risk:<level>`` |
| Guard | label ``guard-flip:<name>`` (default ``"none"``) |
| Dependency | body regex ``(depends on|blocked by) #N`` |
| Estimate | risk default map (low=1, normal=2, high=5, critical=10) or explicit override |
| Consensus | request param |
| Evidence | request ``plan_ref`` |
| Mirror digest | ``ProjectionManifest.digest()`` at add time |
| Release impact | risk map (low/normal=patch, high=minor, critical=major) |

## 5. Atomicity model (slice_adder)

```
1. fetch_fields(project_node_id)
2. create_issue(title, body, labels, milestone)
3. add_issue_to_project(project_node_id, issue.node_id)
4. set_field_value() x N  (Epic, Risk, Guard, ...)
   on any failure -> rollback: gh issue close <new_issue> --comment "<reason>"
```

The rollback path leaves the failed issue closed so subsequent runs do not
try to re-create it. The audit trail stays in GitHub.

## 6. Validation

```
$ pytest tests/test_project_sync_*.py -v
46 passed in ~12s
$ ruff check ao_kernel/project_sync/ tests/test_project_sync_*.py
All checks passed!
$ mypy ao_kernel/project_sync/ --strict
Success: no issues found in 10 source files
```

File budget: largest is ``cli.py`` at 308 lines, well below 800.

## 7. Guard flag posture

All four schemas pin ``guard_flags.live_adapter_execution=false``,
``support_widening=false``, ``production_platform_claim=false`` as
``const false``. ``register_authority`` is ``const
"evidence_record_only"``. ``github_write_authorized`` is ``const true``
for this module — it IS the authorized writer surface (documented
exception in CLAUDE.md §5 and the AO-MA-SPM master plan).

## 8. Acceptance

- [x] Module imports cleanly
- [x] CLI subcommand registered + ``--help`` text emits
- [x] 46 tests pass
- [x] ruff clean, mypy strict clean
- [x] Four schemas Draft 2020-12 strict with const-pinned guard flags
- [ ] Cross-AI peer review AGREE (Codex)
- [ ] PR opened, CI green, auto-merge enabled
