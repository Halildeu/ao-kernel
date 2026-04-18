# PR-C1b Implementation Plan v3 — Full Bundled bug_fix_flow E2E Benchmark

**v3 absorb (iter-2 PARTIAL — 1 blocker + 1 warning)**: Canned envelope `review_findings` + `commit_message` schema-valid shape (Codex citation: `review-findings.schema.v1.json:6-24` + `commit-message.schema.v1.json:5-19`); `bench_policy_override` simplified — `inherit_from_parent` reliance drop (driver `parent_env={}`), PATH prefix synth + command allowlist yeterli.

---

# (v2 retained for history)

## PR-C1b Implementation Plan v2 — Full Bundled bug_fix_flow E2E Benchmark

**Scope**: FAZ-C runtime closure 2. track. C1a altyapısı üzerine bug_fix_flow 7-step full bundled E2E benchmark. Patch plumbing top-level `diff` fallback. `gh-cli-pr` manifest input_envelope declarative fix (hem bundled hem fixture parity).

**Base**: `main cba3e2e` (PR #109 C1a merged). **Branch**: `feat/pr-c1b-bug-fix-flow-e2e`.

**Status**: iter-1 PARTIAL absorb → iter-2 submit. Codex thread `019d9ff8-fb83-7c41-bb35-872f730587f1`.

---

## v2 absorb summary (Codex iter-1 PARTIAL — 2 blocker + 4 warning)

Iter-1 kod-okumasıyla v1'de 2 tasarım yanlışı + 4 tutarlılık eksiği:

| # | iter-1 bulgu | v2 fix |
|---|---|---|
| **B1** | v1 happy-path "failing test → patch → green" workflow sırasıyla mümkün değil. `bug_fix_flow` sırası `preview_diff → ci_gate → await_approval → apply_patch` (`bug_fix_flow.v1.json:29-53`). `ci_gate` patch'ten ÖNCE çalışır; unpatched kodu test eder. | v2 happy-path semantiği: repo **baseline GREEN**; codex-stub kozmetik diff üretir (comment/docstring); `ci_gate` baseline'da green; approval; `apply_patch` diff'i uygular; `open_pr`. CI gate = pre-commit sanity check, post-patch verification DEĞİL. |
| **B2** | v1 `extracted_outputs.diff` yanlış — codex-stub top-level `diff` üretiyor (`fixtures/codex_stub.py:90-117`); manifest `output_parse` rule'u yalnız `review_findings` + `commit_message` için (`codex-stub.manifest.v1.json:22-35`); executor artifact top-level `diff` yazar (`executor.py:706-730`). Diskte `extracted_outputs.diff` YOK. | v2 fallback: `artifact.get("diff", "")` top-level. `extracted_outputs` path drop. Benchmark canned envelope top-level `diff` + `review_findings` + `commit_message` + `cost_actual` taşır. |

### v2 absorb warnings

- **W1** (iter-1): `install_bundled_workflow` helper gereksiz — `tests/benchmarks/conftest.py:38-57` zaten bundled workflow ve adapter'ları `.ao/` altına kopyalıyor. v2 §2.4 drop; benchmark test doğrudan bundled'ı bekler.
- **W2** (iter-1): `bench_policy_override` fixture hazır değil; wiring gerek. `gh` allowlist gereksiz (mock); kritik olan `PATH`/`PYTHONPATH`/`python3`. v2 §2.3 explicit fixture tanımı.
- **W3** (iter-1): Patch üretim path sorunu — benchmark repo `.ao/**` dosyalarıyla dirty. Naive `git add -N .` tabanlı diff `.ao/**` dahil eder. v2: **canonical diff hardcoded** benchmark envelope'da (küçük cosmetic patch string), git-based generation YOK.
- **W4** (iter-1): gh-cli-pr Option A runtime unblocker değil, declarative. Runtime substitution manifest shape'ine bakmıyor; envelope'da key varsa çalışıyor. Ama parity drift engellemek için hem bundled (`ao_kernel/defaults/adapters/gh-cli-pr.manifest.v1.json:15-18`) hem test fixture (`tests/fixtures/adapter_manifests/gh-cli-pr.manifest.v1.json:15-18`) birlikte güncellenmeli.

---

## 1. Problem

C1a (merged `cba3e2e`) adapter-path output_ref + context_compile materialisation + context_pack_ref envelope plumbing kurdu. C1b:

1. **bug_fix_flow bundled E2E benchmark YOK** — 7-step full-flow regression gate eksik.
2. **`_load_pending_patch_content`** (`multi_step_driver.py:1749-1763`) fixture-only MVP; adapter-path fallback yok → `apply_patch` step'i boş patch alır.
3. **`gh-cli-pr` manifest** (`gh-cli-pr.manifest.v1.json:9,15`) `args` `{context_pack_ref}` kullanıyor ama `input_envelope` shape deklare etmiyor. Declarative parity eksik (runtime çalışıyor ama tutarlılık kayıp).

---

## 2. Scope (atomic deliverable)

### 2.1 `_load_pending_patch_content` top-level diff fallback

**Before** (`multi_step_driver.py:1749-1763`):
```python
def _load_pending_patch_content(
    record: Mapping[str, Any], step_name: str,
) -> str:
    """MVP: test fixtures supply patch via record.intent.payload.patches[step_name]."""
    intent_payload = record.get("intent", {}).get("payload", {})
    if isinstance(intent_payload, Mapping):
        patches = intent_payload.get("patches", {}) or {}
        content = patches.get(step_name) if isinstance(patches, Mapping) else None
        if isinstance(content, str):
            return content
    return ""
```

**After** (v2 — top-level diff artifact fallback):
```python
def _load_pending_patch_content(
    record: Mapping[str, Any],
    step_name: str,
    *,
    workspace_root: Path | None = None,
) -> str:
    """Load pending patch content from (in order):
    1. record.intent.payload.patches[step_name] — fixture/override.
    2. Prior adapter step's artifact JSON → top-level `diff` field.
    
    PR-C1b: step 2 closes adapter-path for full bundled bug_fix_flow.
    Canonical diff location = top-level `artifact["diff"]` per
    codex-stub fixture + executor artifact writer contract.
    """
    intent_payload = record.get("intent", {}).get("payload", {})
    if isinstance(intent_payload, Mapping):
        patches = intent_payload.get("patches", {}) or {}
        content = patches.get(step_name) if isinstance(patches, Mapping) else None
        if isinstance(content, str):
            return content
    
    if workspace_root is None:
        return ""
    run_id = record.get("run_id")
    if not run_id:
        return ""
    for prior in reversed(record.get("steps", [])):
        if (
            prior.get("actor") == "adapter"
            and prior.get("state") == "completed"
            and prior.get("output_ref")
        ):
            run_dir = workspace_root / ".ao" / "evidence" / "workflows" / run_id
            artifact_path = run_dir / prior["output_ref"]
            if artifact_path.is_file():
                try:
                    artifact = json.loads(artifact_path.read_text())
                except (OSError, json.JSONDecodeError):
                    return ""
                diff = artifact.get("diff", "")
                if isinstance(diff, str):
                    return diff
            return ""
    return ""
```

**Caller update** (`multi_step_driver.py:738`):
```python
patch_content = _load_pending_patch_content(
    record, step_def.step_name, workspace_root=self._workspace_root,
)
```

Additive `workspace_root` kwarg default None → fixture-only path (backwards-compat).

### 2.2 `gh-cli-pr` manifest input_envelope widen (parity)

Hem bundled hem fixture manifest aynı anda güncellenir (W4 absorb):

**`ao_kernel/defaults/adapters/gh-cli-pr.manifest.v1.json`** + **`tests/fixtures/adapter_manifests/gh-cli-pr.manifest.v1.json`** (her ikisi):
```json
"input_envelope": {
    "task_prompt": "<PR title>",
    "run_id": "<uuid>",
    "context_pack_ref": "<path to PR body markdown>"
}
```

Runtime behavior DEĞİŞMEZ; bu declarative parity fix. Context.md body MVP (context profile + session/canonical/facts sections); "gerçek prod farklı PR body" gelecek PR'da kendi workflow step'iyle handle edilir.

### 2.3 Full bundled bug_fix_flow E2E benchmark

**Dosya**: `tests/benchmarks/test_governed_bugfix.py::TestFullBundledBugFixFlow`.

**Fixture setup** (mini_repo baseline green):
- `mini_repo/test_smoke.py` — tek assert `assert 1 + 1 == 2` (pass eder).
- `mini_repo/src/__init__.py` — boş.
- Git init + initial commit (baseline state).
- C1a `build_driver(tmp_path, policy_loader=bench_policy_override)` (forward policy).

**`bench_policy_override` fixture** (yeni, v3 simplified):

Driver `_build_sandbox()` her zaman `parent_env={}` geçiriyor (`multi_step_driver.py:1820-1829`), bu yüzden `inherit_from_parent=True` reliance gerçekten çalışmaz. PATH prefix synth + command allowlist yeterli:

```python
@pytest.fixture
def bench_policy_override():
    """Minimal policy for benchmark subprocess: PATH prefix synth
    + python3/pytest/git command allowlist. gh gereksiz (mock)."""
    return {
        "command_allowlist": {
            "exact": ["python3", "pytest", "git"],
            "prefixes": [
                "/usr/bin/",
                "/usr/local/bin/",
                "/opt/homebrew/bin/",
            ],
        },
        "secrets": {"allowlist_secret_ids": [], "exposure_modes": []},
        # Other keys mirror policy_worktree_profile.v1.json defaults.
    }
```

PATH değeri `allowed_prefixes` üzerinden synthesize edilir (`policy_enforcer.py:135-141`); driver parent_env={} olsa da subprocess PATH = `/usr/bin:/usr/local/bin:/opt/homebrew/bin` olur.

**Canned adapter envelopes**:

codex-stub (top-level diff, hardcoded — W3 absorb):
```python
# v3: review_findings + commit_message schema-valid shape per
# review-findings.schema.v1.json:6-24 + commit-message.schema.v1.json:5-19
# (output_parse rules on codex-stub manifest validate these).
CODEX_STUB_ENVELOPE = {
    "status": "ok",
    "diff": """--- a/src/__init__.py
+++ b/src/__init__.py
@@ -0,0 +1,1 @@
+# C1b benchmark: cosmetic docstring added by codex-stub
""",
    "review_findings": {
        "schema_version": "1",
        "findings": [],
        "summary": "C1b benchmark: no review issues.",
        "score": 1.0,
    },
    "commit_message": {
        "schema_version": "1",
        "subject": "docs: add module docstring",
        "body": "",
    },
    "cost_actual": {
        "tokens_input": 100,
        "tokens_output": 50,
        "cost_usd": 0.001,
        "time_seconds": 1.5,
    },
}
```

gh-cli-pr (mock PR open):
```python
GH_CLI_PR_ENVELOPE = {
    "status": "ok",
    "pr_url": "https://github.com/test/mock/pull/1",
    "cost_actual": {"time_seconds": 0.5, "cost_usd": 0.0},
}
```

**7-step drive**:
1. `compile_context` — C1a real materialisation (empty canonical/facts → MVP preamble).
2. `invoke_coding_agent` — mock_adapter_transport yields CODEX_STUB_ENVELOPE.
3. `preview_diff` — ao-kernel patch_preview reads via `_load_pending_patch_content` fallback → artifact top-level `diff`.
4. `ci_gate` — real pytest subprocess in worktree (baseline green).
5. `await_approval` — resume_token grant.
6. `apply_patch` — applies hardcoded diff to worktree.
7. `open_pr` — mock_adapter_transport yields GH_CLI_PR_ENVELOPE.

**Assertions**:
- `final_state == "completed"`.
- Artifact chain: `compile_context.output_ref` exists, context.md file exists.
- codex-stub `invocation_result.status == "ok"`, `output_ref` canonical JSON has `diff` field.
- apply_patch step_record.state == "completed" (patch applied successfully).
- open_pr adapter_returned event `status == "ok"`.
- B6 `capability_output_refs` plumbing preserved (review_findings + commit_message capability refs populated on codex-stub step).

### 2.4 ~~install_bundled_workflow helper~~ — DROP (W1 absorb)

`tests/benchmarks/conftest.py:38-57` zaten bundled workflow + adapter'ları kopyalıyor. Yeni helper gerekmez.

---

## 3. Test Plan

### 3.1 Yeni testler (`tests/benchmarks/test_governed_bugfix.py`)

Mevcut dosyada `TestHappyPath` varsa (B7 skeleton'dan), `TestFullBundledBugFixFlow` yeni class olarak eklenir:

- `test_happy_path_bug_fix_flow_completes` — 7 step green + patch applied + mock PR opened.
- `test_patch_artifact_fallback` — `record.intent.payload.patches={}` boş; fallback prior adapter artifact'tan diff okur.
- `test_ci_gate_failure_blocks_flow` — mini_repo'da failing `test_smoke.py` → ci_gate fail → workflow `failed`, apply_patch skip.

### 3.2 Regression gate

- `pytest tests/ -x` — 2151 + 3 = 2154 green.
- `tests/test_patch_errors.py` ve `tests/test_multi_step_driver.py` — `_load_pending_patch_content` additive kwarg backwards-compat.

---

## 4. Out of Scope

- **C2** (parent_env union) / **C3** (post_adapter_reconcile) / **C6** (dry_run_step) — paralel.
- Real `gh pr create` subprocess — mock (CI no-secrets).
- Real `claude-code-cli` subprocess — codex-stub mock.
- "Failing test → patch → green" narrative — **bug_fix_flow workflow sırası bunu desteklemiyor** (ci_gate patch-öncesi). Ayrı workflow (ör. `refactor_flow`) yaratmak istersek future PR.
- Real PR body generation (diff + summary markdown) — context.md MVP yeterli; prod body ayrı PR.
- Schema delta yok.

---

## 5. Risk Register

| Risk | L | I | Mitigation |
|---|---|---|---|
| R1 `_load_pending_patch_content` yeni kwarg caller'ları kırar | L | M | Additive default None; backward-compat kanıtı test |
| R2 Hardcoded diff git apply'de uyumsuz (line ending, path) | M | M | Minimal patch (tek yeni dosya satır); `git apply --check` ön-doğrulama |
| R3 pytest subprocess CI'da flaky | L | L | Single-file minimal smoke; timeout 60s |
| R4 Bench conftest bundled copy adapter manifest parity (bundled vs fixture) kayması | M | L | Aynı commit'te her iki manifest güncelleme |
| R5 gh-cli-pr mock envelope output canonical JSON'a yazılırken hangi field capture | L | L | Executor `_normalize_invocation_for_artifact` shape korunur; mock envelope shape yeterli |

---

## 6. Implementation Order

1. `gh-cli-pr` manifest input_envelope widen — **bundled + fixture parity** (1-key JSON update ×2).
2. `_load_pending_patch_content` artifact fallback + caller update.
3. `bench_policy_override` fixture + benchmark test class.
4. 3 test + regression.
5. Commit + post-impl Codex review + PR #110.

---

## 7. LOC Estimate

~550 satır (plumbing fallback +50, manifest +4, bench fixture +30, benchmark class +350, regression ~115).

---

## 8. Audit Trail

| Iter | Date | Verdict |
|---|---|---|
| v1 (Claude draft) | 2026-04-18 | Pre-Codex submit (`5f3b1b2`) |
| iter-1 (thread `019d9ff8`) | 2026-04-18 | **PARTIAL** — 2 blocker (workflow sırası yanlış, extracted_outputs.diff yanlış) + 4 warning |
| **v2 (iter-1 absorb)** | 2026-04-18 | Pre-iter-2 submit. Happy-path = baseline green + cosmetic diff; top-level `diff` fallback; bench_policy_override fixture; manifest parity; install_bundled_workflow drop. |
| iter-2 | 2026-04-18 | **PARTIAL** — 1 blocker (canned envelope review_findings/commit_message schema-invalid) + 1 warning (bench_policy_override inherit_from_parent driver parent_env={} ile çalışmaz) |
| **v3 (iter-2 absorb)** | 2026-04-18 | Pre-iter-3. Canned envelope schema-valid shape (schema_version + findings + summary + score; object commit_message) + bench_policy_override simplified. |
| iter-3 | TBD | AGREE expected (minimal text-level fix; Codex explicit AGREE yolu gösterdi) |

### Plan revision history

| Ver | Change |
|---|---|
| v1 | 3 scope + 5 Q; extracted_outputs.diff yanlış + "failing test → green" semantik hatası |
| **v2** | iter-1 absorb: happy-path baseline-green + cosmetic diff (ci_gate pre-commit sanity); artifact top-level `diff` kontratı; bench_policy_override explicit fixture; bundled + fixture manifest parity; install_bundled_workflow drop. |

**Status**: Plan v2 hazır. Codex thread `019d9ff8` iter-2 submit için hazır. Dar scope revisions; AGREE beklenir.
