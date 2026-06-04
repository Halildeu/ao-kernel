# Support Surface Inventory (V5 Epic 3 E-3-4)

> Slice #856. A **narrative companion** to [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md).
> It **restates** today's narrow-stable boundary (it does not re-declare or widen
> it) and inventories the surface dimensions a *future* support-widening decision
> would consider — naming, per dimension, the **prerequisites** that widening would
> require. **This document announces no widening.** Infrastructure-only: no guard
> flag is flipped (`support_widening` / `production_platform_claim` /
> `live_adapter_execution` remain `const false`); a widening is opened only by the
> Epic 9 operator-bound supersession PR.

## 1. Current narrow stable boundary (restated, not re-claimed)

Per `SUPPORT-BOUNDARY.md` §1.1 ("ST-2 stable boundary freeze"), the stable
support set is the **`Shipped baseline` layer only**. The freeze deliberately
excludes operator-managed beta lanes, live-write / remote side-effect flows,
contract inventory without behavior evidence, roadmap/spec-only walkthroughs, and
deferred support claims. `ST-3` real-adapter certification and `ST-4` live-write
rollback rehearsal are **not** blockers for the narrow stable runtime *as long as
stable docs do not claim those surfaces* — they become blockers only if a future
PR tries to promote real adapters or live-write behavior into stable shipped
support.

The authoritative statement lives in `SUPPORT-BOUNDARY.md`; this section is a
pointer, not a second source of truth.

## 2. Surface dimensions inventoried for future widening

The support-widening evidence schema (E-3-1,
`support_widening_evidence.schema.v1.json`) recognises five `surface_class`
values. Each is a dimension a *future* widening could open — none is open today:

| `surface_class` | Examples of what a future widening could add |
|---|---|
| `provider` | additional LLM providers (e.g. Mistral, Cohere, Llama via HuggingFace) beyond the shipped baseline |
| `python_version` | a backward-compat decision (e.g. 3.10) or a new release (e.g. 3.14) beyond the shipped 3.11–3.13 matrix |
| `os_platform` | Windows desktop, macOS Apple Silicon (arm64), Linux ARM64 |
| `db_backend` | the `pgvector` semantic backend (the extra is pinned today but **no backend ships**); a future alternative backend |
| `deployment_topology` | single-tenant container, k8s Helm, multi-tenant SaaS isolation |

## 3. What each widening dimension requires (prerequisites, NOT promises)

Read directly from the v1 evidence schema's per-class evidence list. These are
the **prerequisites** a dimension's widening evidence pack would have to satisfy
(v1 records the *simulated* shape; the live thresholds below are what Epic 9's v2
supersession evidence would require):

| Dimension | Widening prerequisite |
|---|---|
| `provider` | N live integration tests passing for the provider (v2 requires ≥ 3) — not the v1 stub count |
| `python_version` | the full pytest matrix green on every supported version (incl. any added version) |
| `os_platform` | a passing smoke per added platform |
| `db_backend` | a real round-trip on the test corpus for the backend (e.g. pgvector) |
| `deployment_topology` | a passing isolation test per topology |

Each prerequisite is recorded as live evidence (`evidence_class: live`, not
`simulated`) only under the Epic 9 operator-bound supersession PR — never by an
Epic 3 slice.

## 4. Boundary disclaimer

This inventory does not announce any widening; it names what would be required if widening were authorized.
The `ST-2` stable boundary freeze stays in effect until the operator-bound
supersession PR (Epic 9) explicitly opens a dimension. Nothing here promotes a
real adapter, a live-write surface, or any new platform into the shipped
baseline.

## 5. Cross-references

- Authoritative boundary: [`SUPPORT-BOUNDARY.md`](SUPPORT-BOUNDARY.md) §1.1
- Evidence schema (E-3-1): `ao_kernel/defaults/schemas/support-widening-evidence.schema.v1.json`
- Smoke harness (E-3-2): `scripts/run_support_smoke.py`
- Final promotion authority: Epic 9 operator-bound supersession PR (`#895`)
