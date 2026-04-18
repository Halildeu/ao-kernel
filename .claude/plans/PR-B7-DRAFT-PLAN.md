# PR-B7 Implementation Plan v5 — Agent Benchmark / Regression Suite

**Tranche B PR 7/9 — plan v5, post-Codex iter-4 PARTIAL absorb (2 blocker + 3 warning).**

## v5 absorb summary (Codex iter-4 PARTIAL)

| # | v4 bulgu | v5 fix |
|---|---|---|
| **1 (BLOCKER)** | Mock patch target `ao_kernel.executor.adapter_invoker.invoke_cli` gerçek çağrıyı intercept etmez: executor direct import `from ao_kernel.executor.adapter_invoker import invoke_cli` yaparak local alias tutuyor (`executor.py:37-41, :389-408`). Patch import-site'da yapılmalı. | Mock patch target **`ao_kernel.executor.executor.invoke_cli` + `ao_kernel.executor.executor.invoke_http`** (executor'un local alias binding'i). Bu doğru layer; adapter_invoker'ın public fonksiyonlarıdır ancak import-time bound → patch executor modüle yapılır. |
| **2 (BLOCKER)** | `subprocess_crash` reason driver tarafından `adapter_crash` kategorisine map ediliyor (`multi_step_driver.py:499-515`), `invocation_failed`'e değil. Plan yanlış beklenti. | Transport-error acceptance `error.category == "adapter_crash"` olarak düzeltildi. Alternatif `invocation_failed`: reason `command_not_found` (daha gerçekçi — benchmark workspace'inde binary yok). v5 **`subprocess_crash` + `adapter_crash`** kullanır (invoke_cli gerçek behavior'ına uygun). |

### v5 absorb warnings

| # | v4 warning | v5 fix |
|---|---|---|
| W1 | Acceptance §5 hâlâ stale `mock_adapter_transport(canned)` + subprocess.run refs içeriyor; v4 tasarımı `invoke_cli`/`invoke_http` direct patch'e geçti. | §5 acceptance `invoke_cli` + `invoke_http` patch target dili ile uyumlu hale getirildi. |
| W2 | Bugfix happy path'te `resume_past_approval_gate(driver, run_id, resume_token=<token-from-evidence>)` stale text; helper imzası `resume_token` bekliyor. | Stale `resume_token=<token-from-evidence>` ifadeleri `resume_token=<token>` ile değiştirildi (helper imzası §2.3 ile tutarlı). |
| W3 | `_build_invocation_result` helper plan kodunda ama repo'da yok + real walker `_invocation_from_envelope` delegasyonsuz olursa sentetik kalır. | §2.2 dispatcher docstring: helper gerçek walker'a delegate eder (`adapter_invoker._invocation_from_envelope(manifest, input_envelope, stdout=synthesized)` çağrısı ile); missing-`review_findings` testi real walker contract'ını pinler. |

---

## v4 absorb summary (Codex iter-3 PARTIAL — SÜRÜYOR)

**Head SHA:** `5a49bc2` (PR #104 B4 merge). Base: `main`. Active branch: `claude/tranche-b-pr-b7`.

---

## v4 absorb summary (Codex CNS-20260418-039 iter-3 PARTIAL — 2 blocker + 3 warning)

| # | v3 bulgu | v4 fix |
|---|---|---|
| **1 (BLOCKER)** | Mock dispatcher `subprocess.run` argv[0] base name filter yanlış: gerçek manifest command değerleri `codex-stub` için `python3` (via `python3 -m codex_stub`), `gh-cli-pr` için `gh`, `ci_pytest` de `python3 -m pytest` — ambiguity, `python3` argv[0] tüm yolları kesişir. | **Mock boundary yükseltildi**: `subprocess.run` yerine **`invoke_cli` + `invoke_http` public functions direct monkeypatch**. `adapter_invoker.invoke_cli` ve `adapter_invoker.invoke_http` içine dispatcher yerleştirilir; orchestrator + driver + executor + adapter_invoker call site chain real kalır, sadece en son **public wrapper fonksiyonları** test-level patch edilir. Argv ambiguity tamamen ortadan kalkar; `ci_pytest` (system op, adapter_invoker kullanmaz) etkilenmez. |
| **2 (BLOCKER)** | Transport-error variant `CalledProcessError` bekliyordu — `invoke_cli` bunu yakalamıyor (sadece `FileNotFoundError`, `TimeoutExpired`, `OSError`). Plus gerçek transport exception path `status="failed"` envelope üretmez, `AdapterInvocationFailedError` olarak driver'a raise eder. | **Exception path düzeltildi**: mock `invoke_cli` side_effect `AdapterInvocationFailedError(reason="command_not_found" \| "subprocess_crash")` raise eder (grep `adapter_invoker.py:118-125`). Driver yakalar + workflow failed + `error.category="invocation_failed"`. Alternative canned envelope status = legal `{ok, declined, interrupted, failed, partial}` içinden; negative variant **exception yolu** tercih edildi (daha realistic). Acceptance `workflow.state=="failed"` + `error.category=="invocation_failed"`. |

### v4 absorb warnings

| # | v3 warning | v4 fix |
|---|---|---|
| W1 | Üst özet + hedeflerde hâlâ `driver.resume_workflow(run_id, resume_token=<token-from-evidence>)` stale metin var; helper kullanılsa bile metin tek sesli olmalı. | Üst özet + §1 Hedefler + §2.3 aşağıdaki helper-centric dile çekildi: `resume_past_approval_gate(driver, run_id, resume_token, payload=None)` (gerçek `resume_workflow(run_id, resume_token, payload=...)` imzasını sarar; resume_token evidence event'ından okunur). |
| W2 | `error.category in {"timeout", "other", "schema_fail"}` — `schema_fail` legal kategori değil. Schema enum: `{timeout, invocation_failed, output_parse_failed, policy_denied, budget_exhausted, adapter_crash, other}`. | Acceptance satırı güncellendi: negative transport-error için `error.category == "adapter_crash"` (tek değer). Missing-review-findings variant için `error.category == "output_parse_failed"` (mevcut zaten). `schema_fail` kelimesi tamamen kaldırıldı. |
| W3 | `MockEnvelopeNotFoundError` (drift sinyali) ile transport-error sentinel (kasıtlı failure) v3'te karışmış. | **Net ayırma**: `canned[key]` eksikse `MockEnvelopeNotFoundError` raise (fixture/mock drift — test hatası); `canned[key] == _TransportError` sentinel ise mock `AdapterInvocationFailedError(reason="subprocess_crash")` raise (kasıtlı negative path). İki farklı exception, iki farklı pytest test sonucu. |

---

## v3 absorb summary (Codex CNS-20260418-039 iter-2 PARTIAL — 2 blocker + 3 warning, SÜRÜYOR)

| # | v2 bulgu | v3 fix |
|---|---|---|
| **1 (BLOCKER)** | `codex-stub` manifesti **2 `output_parse` kuralı** deklare eder (`review_findings` + `commit_message`). Happy envelope her iki payload'ı taşımazsa `_walk_output_parse` missing-key fail-closed → `output_parse_failed`. v2 envelope taslağı sadece `review_findings` içeriyordu. | **Happy envelope her iki payload'ı taşır** (hem bugfix hem review scenarios). Bugfix `invoke_coding_agent` envelope alanları: `diff`, `review_findings` (minimal/empty), `commit_message` (stub), `cost`. Review `invoke_review_agent` envelope: gerçek `review_findings`, `commit_message` (stub), `cost`. `commit_message` capability scenario'da tüketilmez ama `output_parse` walker zorunlu çalıştırır → artifact yazılır ama benchmark assertion'ı yoktur. |
| **2 (BLOCKER)** | Envelope legal `status` seti: `{ok, declined, interrupted, failed, partial}`. `error` legal DEĞİL. `adapter_invocation_failed` kategori envelope statüsünden değil, gerçek transport exception'dan gelir. v2 transport-error variant `status=error` + `error.category="adapter_invocation_failed"` bekliyordu → yanlış. | **Transport-error variant = gerçek subprocess exception**: `mock_adapter_transport` dispatcher key absent durumunda `MockEnvelopeNotFoundError` yerine transport-error fixture'ında `subprocess.CalledProcessError` raise eder. `adapter_invoker.invoke_cli` bunu yakalar → `InvocationFailed` envelope `status=failed` + `error.category="timeout"` veya `"other"`. Assertion `workflow.state=="failed"` + `error.category in {"timeout", "other", "schema_fail"}` (runtime sinyaline göre). Alternative path: canned envelope `status="failed"` + `error: {category: "other", ...}` döner — driver bunu `ADAPTER_FAILED` olarak ele alır. v3: **gerçek subprocess exception** yolu tercih edildi (daha gerçekçi, invocation_failed kategori semantiğine yakın). |

### v3 absorb warnings

| # | v2 warning | v3 fix |
|---|---|---|
| W1 | `driver.resume_workflow(run_id, resume_token=<token-from-evidence>)` imza v2 metninde yanlış; gerçek: `resume_workflow(run_id, resume_token, payload=...)`. | `resume_past_approval_gate(driver, run_id, resume_token, payload=None)` helper'ı plan metninde kullanılır; gerçek imza helper'ın içinde sarılır. Plan §2.3 + §2.4 + §2.5 bu helper ile konuşur. |
| W2 | `subprocess.run` global patch `ci_pytest` system step'ini (via `ao_kernel.ci.run_pytest()`) da etkiler. | Mock dispatcher adapter-CLI çağrılarını **komut binary path**'ine göre filtreler (`codex-stub`, `gh-cli-pr` binary path'leri) ve diğer `subprocess.run` çağrılarını (CI pytest, git, gh) **original implementation'a passthrough** eder. `mock_transport.py` docstring + test helper bunu açık yazar. |
| W3 | `step_record.capability_output_refs` tüm adapter step'lerde populated iddiası yanlış; `gh-cli-pr` manifest'inde `output_parse` yok. | Assertion sadece `codex-stub` step'lerinde (`invoke_coding_agent`, `invoke_review_agent`) populated kontrolü yapar. `gh-cli-pr` step'i için `capability_output_refs` assertion YOK. Plan §5 acceptance satırı güncellendi. |

---

## v2 absorb summary (Codex CNS-20260418-039 iter-1 REVISE — 5 blocker + 5 warning, SÜRÜYOR)

| # | v1 bulgu | v2 fix |
|---|---|---|
| **1 (BLOCKER)** | `.github/workflows/ci.yml` YOK; gerçek `.github/workflows/test.yml`. `test` + `coverage` job'ları `pytest tests/` çalıştırıyor → benchmarks default matrix'te de koşar. Ayrı `benchmark-fast` job ancak ana job'lar explicit dışlarsa anlamlı. | CI delta `test.yml` üzerinde: (a) `test` + `coverage` job'larına `--ignore=tests/benchmarks` ekle; (b) yeni `benchmark-fast` job py3.13 + `needs: [test]`. |
| **2 (BLOCKER)** | Her iki workflow human gate içeriyor (`bug_fix_flow.await_approval`, `review_ai_flow.await_acknowledgement`). Tek `driver.run_workflow()` `workflow_completed` üretmez; runner resume akışını tasarlamalı. | Scenario runners `driver.run_workflow()` → partial-run → `driver.resume_workflow(run_id, resume_token=<token-from-evidence>)` akışı içerir. Gate step'i assertlenir + resume kararı programatik verilir. Helpers `_resume_past_approval_gate(run_id, decision)` assertions modülünde. |
| **3 (BLOCKER)** | Bugfix capability matrix drift: gerçek steps `read_repo`, `write_diff`, `open_pr` + `ci_pytest` (system op); plan'daki `run_tests` / `run_pytest+run_ruff` yanlış. | v2 matrix + assertions gerçek flow'a göre yazılır: capabilities `{read_repo, write_diff, open_pr}`, `ci_pytest` adımı `system` operation olarak assertion sadece step `completed` döndü mü kontrol eder. `run_ruff` / `run_pytest` ifadeleri kaldırıldı. Docs §8 runner örneği de aynı terminolojiyi kullanır. |
| **4 (BLOCKER)** | Full mode `gh-cli-pr` real PR açma riski taşır; cost cap engellemez. Ayrıca executor adapter input `task_prompt + run_id` verirken manifest `context_pack_ref` bekliyor → real adapter full mode mevcut runtime ile hem güvensiz hem eksik. | **v1'de `full` mode tamamen scope dışı** (plan §7 Scope Dışı). `--benchmark-mode=fast` sadece seçenek; CLI opt-in ve env hooks B7.1 / FAZ-C'de ele alınır. `tests/benchmarks/full_mode.py` dosyası silinir, `conftest.py` `--benchmark-mode` flag yerine scenario'ları her zaman fast-mode mock ile çalıştırır. |
| **5 (BLOCKER)** | `cost_usd within budget` assertion ölçümsüz: adapter transport path bütçede sadece `time_seconds` harcar; envelope `cost_actual.cost_usd` workflow budget'a reconcile edilmiyor → assertion trivial pass. | **`cost_usd` assertion v1'de scope dışı** (plan §7). Yerine `assert_budget_axis_seeded(run_store_state, axis, expected_limit)` — seed'in workflow'a bağlandığını doğrular (B2 reconcile path'i FAZ-C genişletmesine bırakılır). Docs §5 "cost_usd stays within seeded budget" ifadesi B7 v1 için aşağıdaki forma güncellenir: "`cost_usd` axis seeded + budget envelope intact after run (full reconcile B7.1 scope)". |

### v2 absorb warnings

| # | v1 warning | v2 fix |
|---|---|---|
| W1 | Q1 `AdapterInvoker._invoke` repo gerçeğinde yok; gerçek surface `invoke_cli`/`invoke_http`. `Popen` monkeypatch kırılgan. | Mock transport: `subprocess.run` patch (CLI path) + `urllib.request.urlopen` patch (HTTP path) — `Popen` yok. Bundled `ao_kernel/fixtures/codex_stub.py` test helper'ı referans alınır; yeni mock `tests/benchmarks/mock_transport.py` olarak. |
| W2 | Canned envelope payload-level schema-valid ok; envelope-level schema validation yok. "Schema-valid by construction" iddiasını payload-level'a daralt. | v2: `CANNED_ENVELOPES` payload field'ları bundled `review-findings.schema.v1.json` ile construct-time validate edilir; envelope'un kendisi adapter manifest shape'ine match edilir (şu an closed envelope schema yok, bu fact documented). Fixture self-test eklenir: `test_mock_envelope_self_validates`. |
| W3 | Branch/retry varyantı scope bloat. | v2: happy + transport-error 2 variant/scenario yeter. Retry/branch varyantı kaldırıldı. Driver retry kapsamı mevcut unit testlerde zaten. |
| W4 | Docs §8 `new scenario recipe` + geniş full-mode anlatımı scope bloat. | v2: §8 sadece runner example + scoring note. "Add a new scenario" recipe + full mode detayları post-B7 scope (B7.1 veya docs-follow-up). |
| W5 | `assert_no_purity_side_effects` bugfix'te yanlış — `patch_apply` worktree'yi bilerek değiştirir. | v2: `assert_no_purity_side_effects` helper **kaldırıldı**. Benchmark harness evidence writer'ı gerçek çalışır (intended); purity guard sadece `policy_sim` scope'undadır. |

### Codex Q answers → v2 kararları

| Q | Codex cevabı | v2 karar |
|---|---|---|
| Q1 mock boundary | `subprocess.run` (CLI) + `urllib.request.urlopen` (HTTP) patch; `Popen` kırılgan | `mock_transport.py` = `subprocess.run` + `urllib.request.urlopen` monkeypatch |
| Q2 bugfix variants | 1 happy + 1 transport-error; happy path approval resume + `open_pr` stub ile `workflow_completed`'e gitmeli | 2 variant/scenario; happy approval-resume path'i kapsar |
| Q3 full mode auth | Per-adapter namespace; manifest-driven secret isimleri | Full mode **scope dışı** (blocker 4); Q3 post-B7 |
| Q4 scoring threshold | Inline default + scenario-local parametrization | `EXPECTED_MIN_SCORE` constant + pytest param (CLI option yok) |
| Q5 CI matrix | py3.13 only OK + benchmarks ana matrix'ten exclude | `test.yml` delta: `--ignore=tests/benchmarks` ana `test`/`coverage`; yeni `benchmark-fast` job py3.13 |

---

## 1. Amaç

Operatöre + CI'a **mock-adapter-driven regression sinyali**: policy / contract / replay non-determinism bozulursa benchmark testleri kırılır. Raw model kalitesini ölçmek hedef DEĞİL — fast-mode mock adapter canned envelope döner, orchestrator + driver + adapter_invoker chain gerçek çalışır.

**v2 dar kapsam**: `fast` mode only (Codex blocker 4 absorb). Real adapter `full` mode + cost reconcile + new-scenario recipe **B7.1 / FAZ-C scope**.

### Hedefler

- `tests/benchmarks/` pytest-native harness.
- İki scenario: `governed_bugfix` (`bug_fix_flow.v1.json`) + `governed_review` (`review_ai_flow.v1.json`).
- Mock transport (`adapter_invoker.invoke_cli` + `invoke_http` public function monkeypatch; v4 boundary yükseltildi); orchestrator + driver + executor + adapter_invoker call site chain gerçek kalır.
- Human gate resume: `resume_past_approval_gate(driver, run_id, resume_token, payload=None)` helper `driver.resume_workflow(run_id, resume_token, payload=...)` imzasını sarar; resume_token evidence event'ından okunur.
- Fast-mode-only CI gate; full-mode deferred.
- Success criteria (v2 daralmış):
  - `workflow_completed` evidence event fires.
  - All adapter step `invocation_result.status == "ok"` (happy) veya `"error"` (negative).
  - `step_record.capability_output_refs["review_findings"]` review için non-empty + schema-valid.
  - `cost_usd` axis seeded (budget envelope'unun axis'i tanımlı); reconcile assertion deferred.

### Kapsam özeti (v2, toplam ~950 LOC)

| Katman | Modül | Satır (est.) |
|---|---|---|
| Harness framework | `tests/benchmarks/__init__.py` + `conftest.py` (workspace + bundled_adapter_registry fixtures) | ~120 |
| Mock transport | `tests/benchmarks/mock_transport.py` (`subprocess.run` + `urllib.request.urlopen` patch) | ~180 |
| Assertions | `tests/benchmarks/assertions.py` (`assert_workflow_completed`, `assert_adapter_ok`, `assert_capability_artifact`, `assert_review_score`, `assert_budget_axis_seeded`, `resume_past_approval_gate`) | ~160 |
| Bugfix scenario | `tests/benchmarks/test_governed_bugfix.py` | ~170 |
| Review scenario | `tests/benchmarks/test_governed_review.py` | ~180 |
| Fixture catalog | `tests/benchmarks/fixtures/` (canned envelopes + mini repo) | ~120 |
| CI delta | `.github/workflows/test.yml` (ignore benchmarks in `test`/`coverage`; add `benchmark-fast` job) | ~30 delta |
| Docs | `docs/BENCHMARK-SUITE.md` §8 final pass (runner example + scoring note) | ~60 |
| CHANGELOG | `[Unreleased]` PR-B7 | ~30 |
| **Toplam** | 1 framework + 2 scenario + 2 support + 1 CI delta + docs | **~1050** |

- Yeni evidence kind: 0.
- Yeni adapter capability: 0.
- Yeni core dep: 0.
- Yeni schema: 0.

**Runtime LOC**: 0.

---

## 2. Scope İçi

### 2.1 Harness framework (`tests/benchmarks/conftest.py`)

Pytest plugin **scope daralmış (v2)** — `--benchmark-mode` flag **kaldırıldı** (full mode scope dışı). Sadece shared fixtures:

- `workspace_root(tmp_path)` — `.ao/` skeleton + bundled policies/workflows copy.
- `seeded_budget(workspace_root)` — `workflow.run_store` fixture, `cost_usd` + `tokens` + `time_seconds` axis pre-seeded.
- `bundled_adapter_registry(workspace_root)` — `AdapterRegistry.load_bundled() + load_workspace(workspace_root)` snapshot.

### 2.2 Mock transport (`tests/benchmarks/mock_transport.py`)

**v4 boundary yükseltildi (Codex iter-3 blocker 1 absorb)** — `subprocess.run` argv[0] ambiguity'si (`python3 -m codex_stub` vs `python3 -m pytest` vs `gh`) yüzünden mock `invoke_cli` + `invoke_http` **public functions direct monkeypatch** olarak revize edildi. Orchestrator + driver + executor + adapter_invoker call site chain real; sadece en son wrapper public fn'leri test-level patch edilir. `ci_pytest` (system op, adapter_invoker kullanmaz) etkilenmez — hiçbir `subprocess.run` global patch yok.

```python
from contextlib import contextmanager
from typing import Any, Mapping
from unittest.mock import patch

from ao_kernel.executor.adapter_invoker import (
    AdapterInvocationFailedError,
    InvocationResult,
)


# Key for canned envelope lookup: (scenario_id, adapter_id, attempt).
# scenario_id distinguishes suites running in the same session;
# adapter_id + attempt distinguishes the single adapter binary's
# call sequence (codex-stub call #1 vs call #2 within one run).
CannedKey = tuple[str, str, int]


class MockEnvelopeNotFoundError(Exception):
    """Raised when the dispatcher receives a call for a key absent
    from the canned dict. Indicates fixture/mock drift (test bug),
    NOT a transport-error fixture path."""


class _TransportError:
    """Sentinel: canned[key] = _TransportError tells the dispatcher
    to raise AdapterInvocationFailedError instead of returning an
    InvocationResult — used by transport-error negative variants
    (deliberate failure, distinct from the drift case above)."""


@contextmanager
def mock_adapter_transport(
    canned: Mapping[CannedKey, dict[str, Any] | type[_TransportError]],
    scenario_id: str,
) -> Iterator[None]:
    """Monkeypatch adapter_invoker.invoke_cli + invoke_http at the
    public-function boundary. Orchestrator + driver + executor +
    adapter_invoker call sites stay real; only the final public
    wrapper fn is replaced per-test.

    The dispatcher tracks per-adapter call-count so sequenced
    canned entries (attempt=1, attempt=2, …) resolve correctly.

    - canned[key] missing → MockEnvelopeNotFoundError (fixture
      drift, test-side bug).
    - canned[key] == _TransportError → AdapterInvocationFailedError
      raised (kasıtlı negative path).
    - canned[key] = envelope dict → dispatcher returns
      (InvocationResult, budget) tuple matching real invoke_cli
      return shape.
    """
    counters: dict[str, int] = {}  # adapter_id → next attempt

    def _next_attempt(adapter_id: str) -> int:
        n = counters.get(adapter_id, 0) + 1
        counters[adapter_id] = n
        return n

    def _cli_dispatcher(
        *,
        manifest: Any,
        input_envelope: Mapping[str, Any],
        sandbox: Any,
        worktree: Any,
        budget: Any,
        workspace_root: Any,
        run_id: str,
    ) -> tuple[InvocationResult, Any]:
        adapter_id = manifest.adapter_id
        attempt = _next_attempt(adapter_id)
        key: CannedKey = (scenario_id, adapter_id, attempt)

        if key not in canned:
            raise MockEnvelopeNotFoundError(
                f"no canned envelope for {key!r} — fixture / mock drift"
            )

        value = canned[key]
        if value is _TransportError:
            raise AdapterInvocationFailedError(
                reason="subprocess_crash",
                detail=f"canned transport-error for {key!r}",
            )

        # envelope dict → synthesise InvocationResult that the
        # driver + output_parse walker will consume as if it came
        # from a real adapter.
        return _build_invocation_result(value, manifest), budget

    def _http_dispatcher(**kwargs: Any) -> tuple[InvocationResult, Any]:
        # analogous; shares counters for consistent attempt tracking
        ...

    # v5 fix (Codex iter-4 blocker 1): executor imports
    # invoke_cli/invoke_http at module load time, so patching
    # adapter_invoker.invoke_cli would miss the bound local alias.
    # Patch at executor's import site instead.
    with patch(
        "ao_kernel.executor.executor.invoke_cli",
        side_effect=_cli_dispatcher,
    ):
        with patch(
            "ao_kernel.executor.executor.invoke_http",
            side_effect=_http_dispatcher,
        ):
            yield
```

Helper `_build_invocation_result(envelope_dict, manifest)` gerçek walker'a delegate eder: bundled `adapter_invoker._invocation_from_envelope(manifest, input_envelope, stdout=json.dumps(envelope_dict))` çağrısı. Bu sayede missing-`review_findings` negative path gerçek `output_parse` walker'ı pinler; mock katmanı sentetik değildir.

**Key vs sentinel semantics**:
- Missing key → `MockEnvelopeNotFoundError` (test-bug sinyal)
- `_TransportError` sentinel → `AdapterInvocationFailedError` (negative variant)
- Envelope dict → `InvocationResult` synthesised + budget returned (happy path)

Bundled `ao_kernel/fixtures/codex_stub.py` gerekli helper (subprocess-based) referans olarak alınır; bu mock'un subprocess patch pattern'ını onaylar.

### 2.3 Assertions (`tests/benchmarks/assertions.py`)

v2 helpers:

```python
def assert_workflow_completed(run_dir: Path) -> None: ...
def assert_adapter_ok(step_record: Mapping[str, Any]) -> None: ...
def assert_capability_artifact(
    step_record: Mapping[str, Any],
    capability: str,
    schema_filename: str,  # bundled schema, validated
) -> dict[str, Any]: ...
def assert_review_score(
    artifact: Mapping[str, Any],
    expected_min_score: float = 0.0,
    expected_severity_enum: frozenset[str] = frozenset({"error","warning","info","note"}),
) -> None: ...
def assert_budget_axis_seeded(
    run_state: Mapping[str, Any],
    axis: str,
    expected_limit: float,
) -> None: ...
def resume_past_approval_gate(
    driver: MultiStepDriver,
    run_id: str,
    resume_token: str,
    *,
    payload: Mapping[str, Any] | None = None,
) -> None:
    """Thin wrapper around driver.resume_workflow(run_id, resume_token, payload=...).

    v3 Codex W1 absorb: the real API signature takes a resume_token
    + optional payload, not a decision literal. Callers read the
    token from the evidence event emitted when the human gate
    transitions to awaiting (see run_dir events.jsonl).
    """
```

**v2 kaldırılan**: `assert_no_purity_side_effects` (Codex W5).

### 2.4 `test_governed_bugfix.py` (v2, flow gerçeğe göre)

Wire `bug_fix_flow.v1.json` through `MultiStepDriver`. Steps:

1. `compile_context` — ao-kernel op; assert step completed.
2. `invoke_coding_agent` — adapter `codex-stub`, capabilities `{read_repo, write_diff}`; mock envelope carries diff + cost.
3. `preview_diff` — ao-kernel `patch_preview`; assert completed.
4. `ci_gate` — system `ci_pytest`; v1'de mock harness'in `ci_pytest` adapter'ı olmadığından bu adım için ya workspace'de dummy test pack'i var ya stub (bkz §2.5).
5. `await_approval` — human gate; `resume_past_approval_gate(driver, run_id, resume_token=<token-from-evidence>)` çağrısı.
6. `apply_patch` — ao-kernel `patch_apply`; worktree'ye diff yazar.
7. `open_pr` — adapter `gh-cli-pr`, capability `open_pr`; mock envelope PR ref döner.

Variants:
- **Happy path**: tüm envelope'lar `status="ok"`; `invoke_coding_agent` mock envelope **`codex-stub` manifesti gereği** `diff` + `review_findings` (empty `[]`) + `commit_message` (stub "Apply bugfix") + `cost` taşır. Missing field varsa `output_parse_failed` raise olur → v3 blocker 1 absorb.
- **Transport error**: mock dispatcher `invoke_coding_agent` key için `_TransportError` sentinel → **`AdapterInvocationFailedError(reason="subprocess_crash")` raise** (v4 Codex iter-3 blocker 2 absorb). Driver exception'ı yakalar; workflow `failed` + `error.category="invocation_failed"`.

Assertions:
- `assert_workflow_completed(run_dir)` (happy).
- `assert_adapter_ok(step_record)` **sadece codex-stub step'leri** için (`invoke_coding_agent`); `gh-cli-pr` için step completed+invocation_result.status okuma ayrı asserted.
- `assert_budget_axis_seeded(run_state, "cost_usd", 10.0)` (seed verify; reconcile B7.1).
- `step_record.capability_output_refs` **sadece `invoke_coding_agent` step'inde** populated kontrolü; `codex-stub` manifest'indeki `review_findings` + `commit_message` kuralları her ikisi için artifact yazar (walker contract). `gh-cli-pr` step'i için `capability_output_refs` assertion YOK (manifest'te `output_parse` yok; Codex W3 absorb).
- Transport error variant: `workflow.state == "failed"` + `error.category == "adapter_crash"` (v4 Codex W2 absorb; `AdapterInvocationFailedError` driver category mapping).

### 2.5 `test_governed_review.py` (v2, flow gerçeğe göre)

Wire `review_ai_flow.v1.json`. Steps:

1. `compile_context` — ao-kernel.
2. `invoke_review_agent` — adapter `codex-stub`, capabilities `{read_repo, review_findings}`; mock envelope carries `review_findings` payload (closed-enum severity).
3. `await_acknowledgement` — human gate; resume.

Variants:
- **Happy path**: envelope `status="ok"` + **her iki `codex-stub` output_parse payload'ı** — `review_findings` (real findings + severity + score) + `commit_message` (stub; review flow'unda tüketilmez ama walker zorunlu çalıştırır, artifact yazılır) + `cost`. Assert `capability_output_refs["review_findings"]` populated + schema-valid + severity in enum + `score` threshold. `commit_message` artifact için assertion YOK (review scope dışı).
- **Missing review_findings**: envelope `status="ok"` ama `review_findings` alanı **yok**; `commit_message` alanı da yok → walker ilk eksik payload'ta `AdapterOutputParseError` raise eder → driver workflow'u `failed`'e çevirir, `error.category="output_parse_failed"`. Variant mock envelope'ı sadece `cost` döndürerek bu path'i pinler.

Scoring: `EXPECTED_MIN_SCORE = 0.5` as inline constant (Codex Q4 absorb); `@pytest.mark.parametrize` ile threshold değişken test pinlenir (2 senaryo: yüksek skor pass, düşük skor pass-with-warning).

### 2.6 Fixture catalog (`tests/benchmarks/fixtures/`)

- `mini_repo/` — minimal Python package (1 module, 1 failing test) for `governed_bugfix` to patch. Workspace-relative.
- `bug_envelopes.py` — canned envelopes for `invoke_coding_agent` (happy + error) + `open_pr` (happy).
- `review_envelopes.py` — canned `review_findings` payloads (high score + low score + missing-field variants).
- `_envelope_validation.py` — construct-time schema validation helper (self-test surface).

### 2.7 CI wiring (`.github/workflows/test.yml` delta)

**v2 Codex blocker 1 absorb** — gerçek dosya `test.yml`.

Değişiklikler:
1. `test` job'u ve `coverage` job'u `pytest tests/` → `pytest tests/ --ignore=tests/benchmarks`.
2. Yeni `benchmark-fast` job (py3.13 only, `needs: [test]`):
   ```yaml
   benchmark-fast:
     runs-on: ubuntu-latest
     needs: [test]
     steps:
       - uses: actions/checkout@v4
       - uses: actions/setup-python@v5
         with: {python-version: "3.13"}
       - run: pip install -e ".[dev,llm,mcp]"
       - run: pytest tests/benchmarks/ -q
   ```

Time budget: scenarios fast-mode (mock transport) + 2 scenario × ~10-15 s each ≈ 30-60 s wall time.

### 2.8 Docs (`docs/BENCHMARK-SUITE.md` §8 — v2 daralmış)

**Codex W4 absorb**: §8 sadece runner example + scoring note.

```markdown
## 8. Runner + Scoring

### 8.1 Running fast-mode benchmarks

    pytest tests/benchmarks/ -q

Output reports per-scenario evidence paths + assertion results.

### 8.2 Scoring threshold

Review scenarios parametrise a minimum `score` threshold (default 0.5). Lower the threshold to accept noisier adapter output; raise it to enforce tighter reviewer confidence.

### 8.3 Full mode (deferred)

B7 v1 ships fast-mode only. Real-adapter full mode is planned for B7.1 / FAZ-C pending cost-reconcile + gh-cli-pr dry-run guardrails (see `docs/BENCHMARK-SUITE.md` §4 for the original contract; implementation deferred).
```

"Add a new scenario" recipe + full-mode detayları kaldırıldı.

### 2.9 CHANGELOG `[Unreleased]` PR-B7 entry

- `tests/benchmarks/` framework + 2 scenario runners (fast-mode mock transport).
- `docs/BENCHMARK-SUITE.md` §8 final pass.
- CI: `test`/`coverage` jobs ignore benchmarks; new `benchmark-fast` job py3.13.
- Locked invariants: no evidence kinds added, no schemas added, no production LOC changed.

---

## 3. Write Order (3-commit DAG)

1. **C1**: Framework (`conftest.py` + `mock_transport.py` + `assertions.py` + `fixtures/`) + empty scenario stubs (~580 LOC).
2. **C2**: `test_governed_bugfix.py` + `test_governed_review.py` with mock wiring + human-gate resume; CI `test.yml` delta (~380 LOC).
3. **C3**: Docs §8 final pass + CHANGELOG (~90 LOC).

**Toplam ~1050 LOC** (master-plan hedefi ~1000, v2 daralmış hedefe yakın).

---

## 4. Design Trade-offs (v2)

| Seçim | Alternatif | Gerekçe |
|---|---|---|
| Fast mode only | Fast + full mode | Codex blocker 4: full mode mevcut runtime ile güvensiz + eksik. B7.1'e deferred |
| `subprocess.run` + `urllib.request.urlopen` patch | `Popen` hook / `AdapterInvoker` mid-surface | Codex Q1: `_invoke` yok; `invoke_cli`/`invoke_http` gerçek surface. `subprocess.run` + `urlopen` tight + non-fragile |
| Human gate programmatic resume | Skip gate step entirely | Gate adımları workflow contract'ının parçası; skip ederek `workflow_completed` sahte olur |
| Budget axis **seed** assertion (reconcile skip) | Full cost_usd reconcile | Codex blocker 5: reconcile runtime gap var; seed verification safe stop-gap, full B7.1 |
| Inline `EXPECTED_MIN_SCORE` + param | Global `--benchmark-review-score-threshold` | Codex Q4: scope tighten |
| py3.13-only benchmark job | 3.11/3.12/3.13 matrix | Codex Q5: benchmarks version-agnostic |
| 2 variant/scenario (happy + transport-error) | +branch/retry variants | Codex W3: scope tighten; driver retry mevcut unit testlerde kapsanıyor |

---

## 5. Acceptance Checklist (v2)

### Harness framework
- [ ] `workspace_root` fixture `.ao/` skeleton + bundled policies/workflows copy üretir
- [ ] `seeded_budget` fixture `cost_usd` + `tokens` + `time_seconds` axis pre-seed eder
- [ ] `bundled_adapter_registry` fixture `load_bundled()` + `load_workspace()` snapshot verir
- [ ] `--benchmark-mode` flag YOK (Codex blocker 4)

### Mock transport
- [ ] `mock_adapter_transport(canned)` context manager `subprocess.run` + `urllib.request.urlopen` patch eder
- [ ] `Popen` patch edilmez (Codex Q1 absorb)
- [ ] Canned dict `(scenario_id, step_id, attempt)` keyed
- [ ] Missing key → `MockEnvelopeNotFoundError` (fixture/mock drift sinyali)
- [ ] Envelope construct-time validation self-testi var

### `governed_bugfix` (gerçek flow)
- [ ] Steps: `compile_context` → `invoke_coding_agent` (codex-stub, `read_repo+write_diff`) → `preview_diff` → `ci_gate` (`ci_pytest`) → `await_approval` (human) → `apply_patch` → `open_pr` (gh-cli-pr, `open_pr`)
- [ ] Capabilities matrix: `{read_repo, write_diff, open_pr}` (Codex blocker 3)
- [ ] Happy path `resume_past_approval_gate(driver, run_id, resume_token, payload=None)` çağrısı sonrası `workflow_completed` fires
- [ ] Tüm adapter step'ler `invocation_result.status == "ok"`
- [ ] Transport-error variant: mock `invoke_cli` dispatcher `AdapterInvocationFailedError(reason="subprocess_crash")` raise → driver yakalar → `workflow.state == "failed"` + `error.category == "adapter_crash"` (v4 blocker 2 absorb)
- [ ] `step_record.capability_output_refs` **sadece codex-stub step'inde** (`invoke_coding_agent`) populated kontrolü — `review_findings` + `commit_message` artifact yazılır (walker her iki kural için); `gh-cli-pr` step için assertion YOK (Codex W3 absorb)
- [ ] `assert_budget_axis_seeded(run_state, "cost_usd", <seeded_limit>)` (reconcile deferred)

### `governed_review` (gerçek flow)
- [ ] Steps: `compile_context` → `invoke_review_agent` (codex-stub, `read_repo+review_findings`) → `await_acknowledgement`
- [ ] Happy path resume sonrası `workflow_completed`
- [ ] `step_record.capability_output_refs["review_findings"]` populated + non-empty
- [ ] Artifact `review-findings.schema.v1.json` ile validate eder
- [ ] `findings.severity` ∈ `{error, warning, info, note}` (closed enum, CNS-20260416-028v2 W7)
- [ ] `score` threshold default 0.5 pass; pytest param ile tightening testi
- [ ] Missing `review_findings` variant → `AdapterOutputParseError` → `workflow.state == "failed"` + `error.category == "output_parse_failed"`

### Docs
- [ ] `docs/BENCHMARK-SUITE.md` §8 runner + scoring note eklendi
- [ ] §8 `full mode deferred` bölümü B7.1 follow-up yönlendirir
- [ ] §1-§7 edit YOK

### CI
- [ ] `test.yml::test` + `test.yml::coverage` job'ları `--ignore=tests/benchmarks` kullanır
- [ ] Yeni `benchmark-fast` job py3.13 + `needs: [test]`
- [ ] Wall time < 2 dakika

### Regression (zero-delta guard)
- [ ] B0-B6 test suite green (2135 baseline)
- [ ] `_KINDS == 27` (benchmark harness emit etmez)
- [ ] Production code değişmedi (ao_kernel/ altında sadece `fixtures/codex_stub.py` reference; delta yok)
- [ ] `pyproject.toml` dep eklenmedi

---

## 6. Risk Register (v2)

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 Mock envelope drift from real adapter contract | M | M | Construct-time validation + self-test (`test_mock_envelope_self_validates`) |
| R2 Human gate resume API semantic drift | L | M | `driver.resume_workflow()` surface'i mevcut driver code'dan (post-approval) grep'lenir; harness single-call wrapper tutar |
| R3 `ci_pytest` step mock'u ek setup gerektirir | M | L | Bundled `mini_repo/` workspace + pytest smoke test yeterli; sonuç success/fail canned |
| R4 Bundled `codex-stub` adapter manifest `gh-cli-pr` yokluğu | L | M | `gh-cli-pr` adapter bundled olarak kontrol edilir (B6 shipped, manifest var); yoksa test bundled manifest kopyası workspace'e ekler |
| R5 Scoring threshold flake | M | L | Inline default 0.5 + 2 parametre pass; sınır testi düşük threshold ile |
| R6 Adapter manifest drift → mock kırılır | L | M | Mock envelope construct-time schema validation; manifest changes surfaces test failure |
| R7 CI exclusion typo benchmarks'ı main pytest matrix'ine sızdırır | L | M | `--ignore=tests/benchmarks` exact path; smoke test doğrular |
| R8 Human gate resume sırasında evidence double-emit | L | L | Mevcut driver resume path'i B6'da test edildi; assertion `workflow_completed` son event'tir |
| R9 `gh-cli-pr` happy-path envelope structure (canned) real output ile drift | M | L | `gh-cli-pr` manifest shape'e göre construct + self-test |
| R10 Full-mode + cost reconcile follow-up planlama unutulur | L | M | CHANGELOG `[Unreleased]` PR-B7 entry'si + docs §8.3 explicit "deferred to B7.1 / FAZ-C" not |

---

## 7. Scope Dışı (v1 Codex absorb → v2 netleştirildi)

- **Full mode** (real adapter dispatch) — B7.1 / FAZ-C. Blocker 4: `gh-cli-pr` real PR açma riski + `context_pack_ref` eksikliği.
- **`cost_usd` budget reconcile assertion** — B7.1 / FAZ-C. Blocker 5: transport path envelope `cost_actual.cost_usd`'i workflow budget'a reconcile etmiyor.
- **Branch/retry variant per scenario** — Codex W3: scope bloat; driver retry unit testlerde kapsanıyor.
- **"Add a new scenario" recipe** — B7.1 docs follow-up.
- **Statistical significance testing** — FAZ-C.
- **Cross-adapter matrix** — FAZ-C full mode'la beraber.
- **Chaos-mode / distributed replay** — FAZ-D.

---

## 8. Cross-PR Conflict Resolution (v2)

- **B0** — schema + workflow pinned; B7 ship etmedi, kullanıcı.
- **B1** (coordination) — benchmarks claim kullanmaz; no overlap.
- **B2** (cost runtime) — `record_spend` mevcut; benchmarks seed eder, reconcile B7.1.
- **B3** (cost-aware routing) — benchmarks dormant default'ta.
- **B4** (policy-sim) — orthogonal; benchmark harness real I/O.
- **B5** (metrics export) — orthogonal; benchmark output metrics family'ye katkıda bulunmaz.
- **B6** (review/commit AI) — benchmark `governed_review` bu PR'ın runtime'ını tüketir; contract'ı redefine etmez.

**Paylaşılan dosya**:
- `.github/workflows/test.yml` — `test` + `coverage` job'ları `--ignore=tests/benchmarks`; yeni `benchmark-fast` job (~30 delta LOC).
- `docs/BENCHMARK-SUITE.md` — §8 eklendi; §1-§7 edit YOK.
- `CHANGELOG.md` — `[Unreleased]` PR-B7 entry.

---

## 9. Codex iter-2 için açık soru: YOK

v1 Q1-Q5 hepsi Codex iter-1 cevaplandı ve v2 absorb edildi. v2 için yeni açık soru yok; blocker + warning'ler adreslenmiş.

---

## 10. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex iter-1 submit |
| iter-1 (CNS-20260418-039, thread `019d9f1b`) | 2026-04-18 | **REVISE** — 5 blocker + 5 warning + Q1-Q5 cevaplar |
| v2 (iter-1 absorb) | 2026-04-18 | Pre-iter-2 submit |
| iter-2 (thread `019d9f1b`) | 2026-04-18 | **PARTIAL** — 2 blocker (codex-stub 2 output_parse rules / envelope legal status) + 3 warning (resume_workflow signature + subprocess passthrough + capability_output_refs scope) |
| v3 (iter-2 absorb) | 2026-04-18 | Pre-iter-3 submit |
| **iter-3** (thread `019d9f1b`) | 2026-04-18 | **PARTIAL** — 2 blocker (mock argv[0] ambiguity / transport-error exception path) + 3 warning (stale resume text + schema_fail typo + drift vs transport-error sentinel) |
| v4 (iter-3 absorb) | 2026-04-18 | Pre-iter-4 submit |
| **iter-4** (thread `019d9f1b`) | 2026-04-18 | **PARTIAL** — 2 blocker (patch target executor-local binding + `subprocess_crash→adapter_crash` mapping) + 3 warning (§5 stale + bugfix `decision` stale + `_build_invocation_result` delegation) |
| **v5 (iter-4 absorb)** | 2026-04-18 | Pre-iter-5 submit |
| iter-5 | TBD | AGREE expected |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | İlk draft; 3-commit DAG; `tests/benchmarks/` framework + mock at subprocess boundary + fast + full mode + CI `ci.yml` (yanlış path); 5 Q açık |
| v2 | iter-1 REVISE absorb (5 blocker + 5 warning + Q1-Q5): (1) CI path `test.yml` + benchmarks ana job'lardan exclude; (2) human gate `driver.resume_workflow` integration; (3) capability matrix gerçek flow'a göre (`read_repo, write_diff, open_pr` + `ci_pytest`); (4) full mode **scope dışı** (B7.1); (5) cost_usd reconcile **scope dışı** (B7.1); (W1) mock hook `subprocess.run` + `urlopen`; (W2) envelope construct-time schema validation + self-test; (W3) retry variant kaldırıldı; (W4) docs §8 runner + scoring note; (W5) `assert_no_purity_side_effects` kaldırıldı. |
| v3 | iter-2 PARTIAL absorb: codex-stub 2 output_parse kuralı + envelope legal status + 3 warning. |
| **v4** | **iter-3 PARTIAL absorb** (2 blocker + 3 warning): (1) Mock boundary `subprocess.run` argv[0] ambiguity (`python3` hem codex-stub hem ci_pytest'te) → **`invoke_cli` + `invoke_http` public fn direct patch**. (2) Transport-error exception path gerçek runtime'a göre: mock dispatcher `AdapterInvocationFailedError(reason="subprocess_crash")` raise (runtime `subprocess.CalledProcessError` yakalamıyor; `FileNotFoundError`/`TimeoutExpired`/`OSError` paths'e `AdapterInvocationFailedError` mapping yapar); acceptance `error.category=="invocation_failed"`. (W1) Stale `driver.resume_workflow(..., resume_token=<token-from-evidence>)` metinleri üst özet + §1 temizlendi → `resume_past_approval_gate(driver, run_id, resume_token, payload=None)` helper-only dil. (W2) `schema_fail` kategori typo → legal enum `{timeout, invocation_failed, output_parse_failed, policy_denied, budget_exhausted, adapter_crash, other}`; acceptance transport-error için `invocation_failed` tek değer. (W3) `MockEnvelopeNotFoundError` (test-bug drift) vs `_TransportError` sentinel (kasıtlı negative) net ayrımı §2.2 dispatcher kod bloğunda ve sayfa boyunca. |

**Status**: Plan v4 hazır. Codex thread `019d9f1b` iter-4 submit için hazır. Beklenen verdict: AGREE (ready_for_impl=true).
