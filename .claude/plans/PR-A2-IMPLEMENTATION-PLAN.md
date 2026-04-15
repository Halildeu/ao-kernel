# PR-A2 Implementation Plan — Intent Router + Workflow Registry + Adapter Manifest Loader

**Status:** DRAFT **v2** · 2026-04-15
**Base branch:** `claude/tranche-a-pr-a2` (created from `origin/main` @ `2245a1d`)
**Plan authority:** Plan v2.1.1 §15 (Post-PR-A1 #3); PR-A0 `agent-adapter-contract.schema.v1.json`; PR-A1 `workflow/run_store.py`
**Scope position:** Tranche A PR 3/6 — wiring from intent → workflow → adapter (no invocation yet; PR-A3 executor)
**Adversarial:** CNS-20260415-021 iter-1 PARTIAL (7 blocking + 10 warning absorbed) → iter-2 pending

## Revision History

| Version | Date | Scope |
|---|---|---|
| v1 | 2026-04-15 | Initial draft. 3 modules + 2 schemas + 2 bundled defaults. |
| **v2** | 2026-04-15 | **CNS-021 iter-1 absorbed**: 7 blocker + 10 warning fixes. `additionalProperties:false` closed contracts; cross-ref enforcement acceptance gate; versionless resolution contract; IntentRouter no-match semantic; filename strict-dash match; structured `CrossRefIssue` type; adapter LoadReport reason taxonomy; test target 110-140. |

---

## 1. Amaç

PR-A0'da sözleşmesi kilitlenen ve PR-A1'de durable lifecycle'ı kodlanmış **workflow run** katmanının üstüne **intent → workflow resolution → adapter binding** katmanını getirmek. Gerçek adapter invocation (subprocess/HTTP) ve worktree executor **PR-A3**'te; bu PR **definition / manifest / registry contracts + rule-first routing** teslim eder.

### PR-A2'nin teslim ettiği (v2 final)

1. `workflow-definition.schema.v1.json` — kapalı sözleşme (`additionalProperties:false` top-level + step_def + nested policy/capability yapılarında). Workflow tanımı sözleşmesi (steps, policies, expected adapter ids, on_failure semantics). PR-A0 `workflow-run` ile cross-reference (run'ın `workflow_id + workflow_version` field'ları bu definition'ı pin'ler).
2. `intent-classifier-rules.schema.v1.json` — kapalı sözleşme. Kural-bazlı intent classifier konfigürasyon sözleşmesi. Conditional validation (`match_type → keywords/regex_any` non-empty). `workflow_version` opsiyonel; rule pinleyebilir.
3. `ao_kernel/workflow/registry.py` — workflow definition registry (bundled + workspace), cross-ref validation `list[CrossRefIssue]` structured dönüş (v2 B7).
4. `ao_kernel/workflow/intent_router.py` — rule-first intent classifier; no-match semantic net (v2 B4); ASCII word-boundary tokenization (v2 W7).
5. `ao_kernel/adapters/` — yeni public facade package; `LoadReport.skipped` genişletilmiş reason taxonomy (v2 W9); filename strict-dash match (v2 B6).
6. `ao_kernel/defaults/workflows/bug_fix_flow.v1.json` — bundled workflow, dash adapter_refs.
7. `ao_kernel/defaults/intent_rules/default_rules.v1.json` — bundled rules.
8. Tests: 4 test dosyası + fixture seti (dash-named, v2 W10 target ~120-140 test).
9. CHANGELOG `[Unreleased]` FAZ-A PR-A2 alt-bloğu.

---

## 2. Scope Fences

### Scope İçi

- 2 yeni JSON schema (`workflow-definition.v1` + `intent-classifier-rules.v1`), her ikisinde de `additionalProperties:false` top + nested (v2 B1).
- `ao_kernel/workflow/registry.py` + `ao_kernel/workflow/intent_router.py`
- `ao_kernel/adapters/` package (3 modül)
- 2 bundled default JSON
- 4 test dosyası + 7-10 fixture (dash-named, v2 B6)
- `__init__.py` narrow re-exports (workflow + adapters)
- CHANGELOG `[Unreleased]` extension
- Plan doc

### Scope Dışı

- Gerçek adapter invocation, worktree executor — PR-A3
- LLM-based intent classifier impl — PR-A6 (interface PR-A2'de yok, v2 W8: ABC/Protocol yok)
- Diff/patch engine — PR-A4
- Evidence CLI — PR-A5
- CLI komutları — PR-A3+
- Workflow migration (v1→v2) — FAZ-C breaking
- PR-A0 schemas + PR-A1 modules **frozen**, değişmez

### Bozulmaz İlkeler

- POSIX-only (değişmedi).
- CAS tek yazma yolu (PR-A1 invariant); registry/loader **read-only**.
- **Core dep değişmez** (`jsonschema>=4.23.0` only); highest-semver sıralama için yerel comparator (v2 W-Q3-add2: `packaging`/`semver` runtime dep eklenmez).
- `_internal` hariç coverage ≥85%; PR-A2 yeni modüller ≥90%.
- Fail-closed (invalid manifest/definition → `LoadReport.skipped`; cross-ref gap → structured `CrossRefIssue`).
- Narrow public facade.
- Schema validation at load boundary (@lru_cache, PR-A1 pattern).

---

## 3. Write Order (bağımlılık DAG)

```
1. schemas/workflow-definition.schema.v1.json        (closed contract, v2 B1)
2. schemas/intent-classifier-rules.schema.v1.json    (closed contract, v2 B1 + conditional)
       ↓
3. workflow/errors.py  (extend with WorkflowDefinitionError hierarchy + CrossRefIssue + IntentRulesCorruptedError)
       ↓
4. workflow/registry.py  (loads + validates + CrossRefIssue structured returns)
       ↓
5. adapters/errors.py  (typed adapter exceptions)
6. adapters/manifest_loader.py  (expanded LoadReport reason taxonomy, v2 W9)
7. adapters/__init__.py  (narrow re-exports)
       ↓
8. workflow/intent_router.py  (no-match semantic net + duplicate rule_id loader check, v2 B4 + B5)
9. workflow/__init__.py  (extend with registry + intent_router)
       ↓
10. defaults/workflows/bug_fix_flow.v1.json
11. defaults/intent_rules/default_rules.v1.json

Paralel tests:
12. test_workflow_registry.py
13. test_intent_router.py
14. test_adapter_manifest_loader.py
15. test_pr_a2_integration.py  (fail-closed cross-ref acceptance, v2 B2 & B7)

+ tests/fixtures/adapter_manifests/ (dash-named; cli happy, http happy, capability gap, duplicate, 4-5 negative; v2 W10)

Son:
16. CHANGELOG.md
17. git commit + push + gh pr create + CI monitor + M2 merge
```

---

## 4. Schema — `workflow-definition.schema.v1.json` (v2 closed contract)

**Path:** `ao_kernel/defaults/schemas/workflow-definition.schema.v1.json`
**LOC budget:** ~280-330 satır (v2: +30-50 for additionalProperties + item patterns + descriptions)

### Contract invariants (v2 B1 fix)

- `additionalProperties: false` at **top level** AND in every nested `$defs` object (step_def, policy_refs items, etc.) — matches PR-A0 `workflow-run.schema.v1.json:6-7, 132-156, 246-249` discipline.
- `expected_adapter_refs` items: `{"type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$"}` — matches PR-A0 `agent-adapter-contract.schema.v1.json:20-23` adapter_id pattern. Array has `uniqueItems: true`.
- `steps[*].adapter_id` (when actor=adapter): same pattern as above; **MUST be in `expected_adapter_refs`** (runtime cross-ref, not schema-level).
- `steps[*].required_capabilities` items: enum from PR-A0 `capability_enum` (6 values: `read_repo`, `write_diff`, `run_tests`, `open_pr`, `human_interrupt`, `stream_output`).

### Üst seviye alanlar

| Field | Tip | Gerekli | Açıklama |
|---|---|---|---|
| `$schema`, `$id`, `title`, `description` | standart | ✓ | `urn:ao:workflow-definition:v1` |
| `workflow_id` | string pattern `^[a-z][a-z0-9_]{1,63}$` | ✓ | Drift testi: iki schema arasında pattern eşitliği test-time doğrulanır (v2 W1) |
| `workflow_version` | SemVer | ✓ | Pattern `workflow-run.schema.v1.json:30-32` ile eşit |
| `display_name`, `description` | string, minLength:1 | ✓ | |
| `steps` | array<step_def> minItems:1 | ✓ | |
| `expected_adapter_refs` | array<pattern-adapter_id> uniqueItems:true | ✓ | |
| `default_policy_refs` | array<string> minItems:1 uniqueItems:true | ✓ | |
| `required_capabilities` | array<capability_enum> uniqueItems:true | opsiyonel | |
| `tags` | array<string> uniqueItems:true | opsiyonel | |
| `created_at`, `updated_at` | ISO-8601 date-time | `created_at` ✓ | |

### `$defs/step_def` (v2 closed + descriptive)

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["step_name", "actor", "on_failure"],
  "properties": {
    "step_name": {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,63}$"},
    "actor": {"type": "string", "enum": ["adapter", "ao-kernel", "human", "system"]},
    "adapter_id": {"type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$"},
    "required_capabilities": {"type": "array", "items": {"$ref": "#/$defs/capability_enum"}, "uniqueItems": true},
    "policy_refs": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": true},
    "on_failure": {
      "type": "string",
      "enum": ["transition_to_failed", "retry_once", "escalate_to_human"],
      "description": "Failure handling. transition_to_failed: terminal failed state with category. retry_once: exactly one immediate retry, no backoff, same input envelope (v2 W3). escalate_to_human: open HITL approval gate with diagnostic payload. Intentionally no `retry_with_backoff`, `branch_to_alternative`, `continue_on_error`, `custom` (v2 W4, FAZ-D #9 scope)."
    },
    "timeout_seconds": {
      "type": "integer",
      "minimum": 1,
      "description": "Step-level wall-clock. Effective deadline is min(step_timeout, remaining run-level budget.time_seconds); error.category=timeout on step-level miss, budget_exhausted on run-level (v2 W2)."
    },
    "human_interrupt_allowed": {"type": "boolean", "default": false},
    "gate": {"type": "string", "enum": ["pre_diff", "pre_apply", "pre_pr", "pre_merge", "post_ci", "custom"]}
  },
  "allOf": [
    {"if": {"properties": {"actor": {"const": "adapter"}}}, "then": {"required": ["adapter_id"]}}
  ]
}
```

### Invariants test matrix (v2 W1)

Test asserts: `workflow-definition.workflow_id.pattern == workflow-run.workflow_id.pattern`; same for `workflow_version`; same for `adapter_id` pattern across definition and contract schemas. Any PR-A0 schema revision that changes these patterns triggers a test failure requiring explicit plan update.

---

## 5. Schema — `intent-classifier-rules.schema.v1.json` (v2 net semantics)

**Path:** `ao_kernel/defaults/schemas/intent-classifier-rules.schema.v1.json`
**LOC budget:** ~180-220 satır

### Contract invariants (v2 B1 + B4 + B5 fix)

- `additionalProperties: false` top + every nested.
- Conditional validation (v2 Q4-add1): `match_type=keyword|combined → keywords minItems:1`; `match_type=regex|combined → regex_any minItems:1`.
- `default_workflow_id`: `{"type": ["string", "null"]}`; conditional `fallback_strategy=use_default → default_workflow_id non-null` (v2 Q4-add2).
- Optional per-rule `workflow_version` (SemVer pattern) — rules may pin specific workflow version; absent → highest-semver resolution (v2 B3).
- Duplicate `rule_id` **not** enforceable via JSON Schema alone; loader-level explicit check + `IntentRulesCorruptedError(reason="duplicate_rule_id")` (v2 B5).

### Üst seviye alanlar

| Field | Tip | Gerekli | Açıklama |
|---|---|---|---|
| `$schema`, `$id`, `title`, `description` | standart | ✓ | `urn:ao:intent-classifier-rules:v1` |
| `rules` | array<rule> minItems:1 | ✓ | Priority-ordered rule set |
| `default_workflow_id` | string \| null | opsiyonel | `fallback_strategy=use_default` ise non-null zorunlu (conditional) |
| `fallback_strategy` | enum | ✓ | `error_on_no_match` \| `use_default` \| `llm_fallback` |

### `$defs/rule`

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["rule_id", "workflow_id", "priority", "match_type", "confidence"],
  "properties": {
    "rule_id": {"type": "string", "minLength": 1},
    "workflow_id": {"type": "string", "pattern": "^[a-z][a-z0-9_]{1,63}$"},
    "workflow_version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+(?:-[\\w.-]+)?(?:\\+[\\w.-]+)?$"},
    "priority": {"type": "integer"},
    "match_type": {"type": "string", "enum": ["keyword", "regex", "combined"]},
    "keywords": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": true},
    "regex_any": {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": true},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "description": {"type": "string"}
  },
  "allOf": [
    {"if": {"properties": {"match_type": {"enum": ["keyword", "combined"]}}}, "then": {"required": ["keywords"], "properties": {"keywords": {"minItems": 1}}}},
    {"if": {"properties": {"match_type": {"enum": ["regex", "combined"]}}}, "then": {"required": ["regex_any"], "properties": {"regex_any": {"minItems": 1}}}}
  ]
}
```

### Matching semantics (v2 W7 net)

- **Keyword:** ASCII word-boundary regex `\b<keyword>\b` (case-insensitive). Unicode word boundary NOT explicitly supported in v1 — documented limitation; "bug-fix" matches "bug-fix" token as whole but does NOT match "bug" keyword (dash is boundary). "bug" DOES match "bug_fix" token if the keyword equals "bug" (underscore is word character in regex `\w`).
- **Regex:** any pattern in `regex_any` (case-insensitive, pre-compiled at load). Compile failure at load → `IntentRulesCorruptedError(reason="regex_compile")`.
- **Combined:** both keyword hit AND regex match required.
- Higher priority wins; tie-break **forbidden** (duplicate rule_id already rejected at load). If two rules at same priority both match, error: `IntentRulesCorruptedError(reason="duplicate_priority_match")`.

### No-match contract (v2 B4 fix)

- `fallback_strategy=error_on_no_match`: `classify()` returns `None`.
- `fallback_strategy=use_default`: schema guarantees `default_workflow_id non-null`; classify returns `ClassificationResult(workflow_id=default_workflow_id, confidence=0.0, matched_rule_id="__default__", match_type="default")`.
- `fallback_strategy=llm_fallback`: classify raises `NotImplementedError("[llm] fallback not implemented in PR-A2; ship in PR-A6")`.

---

## 6. Module — `ao_kernel/workflow/registry.py` (v2 structured cross-ref)

**Path:** `ao_kernel/workflow/registry.py`
**LOC budget:** ~320-380 satır

### Types (v2 B7 fix — structured)

```python
@dataclass(frozen=True)
class CrossRefIssue:
    kind: Literal["missing_adapter", "capability_gap"]
    workflow_id: str
    step_name: str | None          # None for top-level expected_adapter_refs gap
    adapter_id: str
    missing_capabilities: frozenset[str] = frozenset()
```

### Public API

```python
@dataclass(frozen=True)
class WorkflowDefinition:
    workflow_id: str
    workflow_version: str
    display_name: str
    description: str
    steps: tuple[StepDefinition, ...]
    expected_adapter_refs: tuple[str, ...]
    default_policy_refs: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    tags: tuple[str, ...]
    source: Literal["bundled", "workspace"]
    source_path: Path


@dataclass(frozen=True)
class StepDefinition:
    step_name: str
    actor: Literal["adapter", "ao-kernel", "human", "system"]
    adapter_id: str | None
    required_capabilities: tuple[str, ...]
    policy_refs: tuple[str, ...]
    on_failure: Literal["transition_to_failed", "retry_once", "escalate_to_human"]
    timeout_seconds: int | None
    human_interrupt_allowed: bool
    gate: str | None


class WorkflowRegistry:
    def __init__(self) -> None: ...
    def load_bundled(self) -> LoadReport: ...
    def load_workspace(self, workspace_root: Path) -> LoadReport: ...
    def list_workflows(self) -> list[WorkflowDefinition]: ...
    def get(self, workflow_id: str, *, version: str | None = None) -> WorkflowDefinition:
        """version=None returns highest SemVer across bundled+workspace;
        source precedence applies ONLY when keys are identical (same id+version).
        (v2 B3 / W5 explicit contract.)"""

    def validate_cross_refs(
        self,
        definition: WorkflowDefinition,
        adapter_registry: AdapterRegistry,
    ) -> list[CrossRefIssue]:
        """Returns empty list on success; structured issues otherwise."""


@dataclass(frozen=True)
class LoadReport:
    loaded: tuple[WorkflowDefinition, ...]
    skipped: tuple[SkippedDefinition, ...]


@dataclass(frozen=True)
class SkippedDefinition:
    source_path: Path
    reason: Literal[
        "schema_invalid",
        "json_decode",
        "duplicate_workflow_key",          # (id, version) collision (v2 W6 renamed)
        "workspace_overrides_bundled",     # audit, same key
        "read_error",
    ]
    details: str
```

### SemVer comparator (v2 Q3-add2 — no new dep)

Local `_parse_semver(ver: str) -> tuple[int, int, int, str]` + `_semver_key(ver)` for sort. Handles `MAJOR.MINOR.PATCH(-pre)(+build)`; pre-release ordering per SemVer 2.0 (alphanumeric comparison, ASCII, rc < r1 etc.). Pre-release loses to release when PATCH equal.

### Workspace > Bundled precedence (v2 W5 clarified)

- Same `(workflow_id, workflow_version)`: workspace wins; bundled record skipped with reason `workspace_overrides_bundled`.
- Different versions: both loaded; `get(id, version=None)` returns highest SemVer **across sources**. If bundled 1.0.0 and workspace 0.9.0 both load, `get("id")` returns bundled 1.0.0. This is intentional; workspace explicit pin is achieved by `get(id, version="0.9.0")`. Documented in API docstring.

### Error hierarchy (extends PR-A1 `workflow/errors.py`)

```python
class WorkflowDefinitionNotFoundError(WorkflowError): ...
class WorkflowDefinitionCorruptedError(WorkflowError): ...
class WorkflowDefinitionCrossRefError(WorkflowError):
    """Raised by caller when a CrossRefIssue list is non-empty and fail-closed is required."""
```

---

## 7. Module — `ao_kernel/adapters/` (v2 expanded LoadReport)

**Path:** `ao_kernel/adapters/`
**LOC budget:** ~420-520 satır (v2: +20-40 for reason taxonomy)

### 7.1 `errors.py`

```python
class AdapterError(Exception): ...
class AdapterManifestNotFoundError(AdapterError): ...
class AdapterManifestCorruptedError(AdapterError):
    reason: Literal[
        "json_decode",
        "schema_invalid",
        "adapter_id_mismatch",           # raw["adapter_id"] != filename-derived id
        "read_error",                    # file read fails (permissions, etc.)
        "not_an_object",                 # top-level is not a JSON object
        "duplicate_adapter_id",          # two manifests claim same adapter_id
    ]
```

(v2 W9: reason taxonomy extended. `ExtensionRegistry.loader.py:356-399` benzeri ayrım.)

### 7.2 `manifest_loader.py`

```python
@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    adapter_kind: Literal[...]                # 8 values PR-A0
    version: str
    capabilities: frozenset[str]
    invocation: Mapping[str, Any]
    input_envelope_shape: Mapping[str, Any]
    output_envelope_shape: Mapping[str, Any]
    interrupt_contract: Mapping[str, Any] | None
    policy_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_path: Path


class AdapterRegistry:
    def __init__(self) -> None: ...
    def load_workspace(self, workspace_root: Path) -> LoadReport:
        """Globs workspace_root/.ao/adapters/*.manifest.v1.json.
        Filename convention: <adapter_id>.manifest.v1.json (strict dash match,
        no underscore↔dash normalization; v2 Q5-add1)."""

    def get(self, adapter_id: str) -> AdapterManifest: ...
    def list_adapters(self) -> list[AdapterManifest]: ...
    def supports_capabilities(self, adapter_id: str, required: Iterable[str]) -> bool:
        """True iff adapter has all required capabilities."""
    def missing_capabilities(self, adapter_id: str, required: Iterable[str]) -> frozenset[str]:
        """Returns the gap set; supports_capabilities is a bool helper on top (v2 Q5-add3)."""


@dataclass(frozen=True)
class LoadReport:
    loaded: tuple[AdapterManifest, ...]
    skipped: tuple[SkippedManifest, ...]


@dataclass(frozen=True)
class SkippedManifest:
    source_path: Path
    reason: Literal[
        "json_decode",
        "schema_invalid",
        "adapter_id_mismatch",
        "read_error",
        "not_an_object",
        "duplicate_adapter_id",
    ]
    details: str
```

### Filename discovery (v2 B6 + Q5-add1)

1. Glob `workspace_root/.ao/adapters/*.manifest.v1.json`.
2. For each file: `expected_id = filename.stem.removesuffix(".manifest.v1")` (e.g. `codex-stub.manifest.v1.json` → `codex-stub`).
3. Load + validate; `raw["adapter_id"]` must exactly equal `expected_id` (no normalization).
4. On mismatch → `SkippedManifest(reason="adapter_id_mismatch")`.

**Fixture filenames** (v2 B6 corrected): `codex-stub.manifest.v1.json`, `gh-cli-pr.manifest.v1.json`, `claude-code-cli.manifest.v1.json`. Negative fixtures: `bad-id-mismatch.manifest.v1.json` (raw adapter_id differs from stem), `bad-schema.manifest.v1.json` (missing required field), `bad-not-object.manifest.v1.json` (top-level is a JSON array), `bad-duplicate-a.manifest.v1.json` + `bad-duplicate-b.manifest.v1.json` (same adapter_id in two files).

### 7.3 `__init__.py` (narrow)

Re-export: `AdapterManifest`, `AdapterRegistry`, `LoadReport` (rename `AdapterLoadReport` in public API to disambiguate from workflow's), `SkippedManifest`, errors. Private: `_expected_id_from_filename`, `_parse_manifest_fields`.

---

## 8. Module — `ao_kernel/workflow/intent_router.py` (v2 net no-match + deterministic)

**Path:** `ao_kernel/workflow/intent_router.py`
**LOC budget:** ~260-320 satır

### Public API (v2 B4 + B5 fix)

```python
@dataclass(frozen=True)
class ClassificationResult:
    workflow_id: str
    workflow_version: str | None          # optional per-rule pin (v2 B3)
    confidence: float
    matched_rule_id: str                   # "__default__" for fallback (v2 Q4-add3)
    match_type: Literal["keyword", "regex", "combined", "default"]


class IntentRouter:
    def __init__(
        self,
        rules: Sequence[IntentRule] | None = None,
        *,
        default_workflow_id: str | None = None,
        fallback_strategy: Literal["error_on_no_match", "use_default", "llm_fallback"] = "error_on_no_match",
    ):
        """rules=None loads bundled default_rules.v1.json via lru_cache.
        When rules+fallback_strategy both supplied directly, caller is
        responsible for the pair matching the contract."""

    def classify(self, input_text: str) -> ClassificationResult | None:
        """Returns:
        - matching rule result on first match (priority DESC);
        - ClassificationResult(default_workflow_id, 0.0, "__default__", "default") when use_default;
        - None when error_on_no_match and no match;
        - raises NotImplementedError for llm_fallback."""


@dataclass(frozen=True)
class IntentRule:
    rule_id: str
    workflow_id: str
    workflow_version: str | None
    priority: int
    match_type: Literal["keyword", "regex", "combined"]
    keywords: tuple[str, ...]
    regex_any: tuple[re.Pattern[str], ...]
    confidence: float
    description: str


def load_default_rules() -> list[IntentRule]:
    """@lru_cache; loads + validates + compiles bundled default_rules.v1.json.
    Raises IntentRulesCorruptedError on:
    - schema validation failure
    - duplicate rule_id (explicit loader check; schema alone cannot enforce)
    - regex_any pattern fails to compile
    (v2 B5 explicit taxonomy)"""
```

### Errors (extend `workflow/errors.py`)

```python
class IntentRulesCorruptedError(WorkflowError):
    reason: Literal[
        "schema_invalid",
        "duplicate_rule_id",
        "regex_compile",
        "duplicate_priority_match",     # runtime in classify
    ]
```

### Keyword matching semantics (v2 W7 documented)

- **Word boundary:** `r"\b" + re.escape(keyword) + r"\b"` compiled with `re.IGNORECASE`. Python `\b` is Unicode-aware by default in `re.UNICODE` mode (py3 default), but ASCII-specific tokenization preferred for v1 (Turkish ş/ç etc. may differ). Schema description documents: "ASCII-oriented matching; Unicode boundary behaviour follows Python `re.UNICODE`".
- **Examples:**
  - keyword `"bug"` matches `"fix the bug here"` ✓, matches `"bug_fix"` ✓ (underscore is `\w`), does NOT match `"debugger"` (b-o-r-d-e-r by `\b`).
  - keyword `"bug-fix"`: `\bbug-fix\b` matches `"bug-fix"` in isolation but not inside a longer token.
- Tests cover these cases explicitly.

---

## 9. Bundled — `defaults/workflows/bug_fix_flow.v1.json`

**Path:** `ao_kernel/defaults/workflows/bug_fix_flow.v1.json`
**LOC budget:** ~100-140 satır

Bug fix workflow definition with **dash** adapter_refs: `codex-stub`, `gh-cli-pr`. Fully schema-valid with `additionalProperties:false` compliance.

(Same structure as v1 §9; adapter_ids already dash, confirmed consistent with PR-A0 pattern.)

---

## 10. Bundled — `defaults/intent_rules/default_rules.v1.json`

**Path:** `ao_kernel/defaults/intent_rules/default_rules.v1.json`
**LOC budget:** ~40-80 satır

```json
{
  "rules": [
    {
      "rule_id": "bug_fix_keywords",
      "workflow_id": "bug_fix_flow",
      "priority": 100,
      "match_type": "keyword",
      "keywords": ["fix", "bug", "issue", "defect", "broken"],
      "confidence": 0.82,
      "description": "Common bug-fix vocabulary"
    }
  ],
  "default_workflow_id": null,
  "fallback_strategy": "error_on_no_match"
}
```

---

## 11. Test Strategy (v2 W10 expanded)

### Coverage targets (unchanged)

- `workflow/registry.py`: ≥90%
- `workflow/intent_router.py`: ≥95%
- `adapters/manifest_loader.py`: ≥90%
- `adapters/errors.py`: ≥95%

### Test file breakdown (v2 expanded: 110-140 target)

| File | Tests | Scope |
|---|---|---|
| `test_workflow_registry.py` | 35-42 | bundled + workspace load, same-key precedence, different-version ordering (workspace 0.9 vs bundled 1.0 explicit test, v2 W5), SemVer local comparator correctness, LoadReport, `duplicate_workflow_key` (v2 W6), `workspace_overrides_bundled`, corrupted JSON, schema invalid, read_error, `additionalProperties` rejection (top + step_def), unknown `on_failure` rejection (v2 Q2-add3), pattern drift regression |
| `test_intent_router.py` | 30-36 | keyword boundary edge cases (v2 W7), regex compile fail, combined both-required, priority DESC, duplicate rule_id load-time reject, duplicate priority match runtime error, `error_on_no_match`→None, `use_default`→default result (with `__default__` sentinel), `llm_fallback`→NotImplementedError, schema conditional validation (match_type ↔ keywords/regex) |
| `test_adapter_manifest_loader.py` | 30-38 | happy (cli + http fixtures), `adapter_id_mismatch`, `duplicate_adapter_id` across two files, `not_an_object`, `read_error`, `json_decode`, `schema_invalid`, filename exact-dash-match, `supports_capabilities` bool, `missing_capabilities` frozenset gap |
| `test_pr_a2_integration.py` | 15-22 | **acceptance**: intent classify → registry lookup → adapter cross-ref validation fail-closed (v2 B2): if `CrossRefIssue` list non-empty, integration test raises; happy + missing-adapter + capability-gap scenarios; bundled-only + workspace-only + mixed setups |

**Total target:** 110-138 new tests. Baseline 1184 → **target ≥1294**.

### Fixture expansion (v2 B6 + W10)

`tests/fixtures/adapter_manifests/`:
- `codex-stub.manifest.v1.json` — cli happy
- `gh-cli-pr.manifest.v1.json` — cli happy (open_pr capability)
- `claude-code-cli.manifest.v1.json` — cli happy (full capability set)
- `custom-http-example.manifest.v1.json` — http happy
- `bad-id-mismatch.manifest.v1.json` — adapter_id_mismatch negative
- `bad-schema.manifest.v1.json` — schema_invalid negative
- `bad-not-object.manifest.v1.json` — not_an_object negative
- `bad-duplicate-alpha.manifest.v1.json` + `bad-duplicate-beta.manifest.v1.json` — both claim adapter_id "duplicate-target" (duplicate_adapter_id negative)

**9 fixtures total.**

### Test quality gate

No `assert True`, no `except: pass`, no single `assert x is not None` as sole assertion. Cross-check asserts enforced.

---

## 12. CHANGELOG Update

(Unchanged from v1 shape; extend PR-A0+A1 `[Unreleased]` block with PR-A2 sub-section after the PR-A1 block. Full text populated at commit time to reflect final impl.)

---

## 13. Acceptance Criteria (v2)

### Module + test

- [ ] 2 new schemas created, `Draft202012Validator.check_schema` passes on each
- [ ] Top-level + nested `additionalProperties:false` enforced in both schemas (grep-verified)
- [ ] 3 workflow/adapter modules + 2 bundled JSON defaults created
- [ ] 4 test files + 9 fixtures (dash-named); **≥110 new tests passing**
- [ ] Coverage: `workflow/` ≥90%, `adapters/` ≥90%
- [ ] Total test count ≥ 1294 (1184 baseline + 110 minimum new)
- [ ] Integration test for cross-ref fail-closed acceptance passes
- [ ] SemVer comparator test matrix covers: same-key precedence, cross-source highest-wins, pre-release ordering

### Regression

- [ ] 1184 existing tests still pass
- [ ] Ruff + mypy strict clean (new modules)
- [ ] No PR-A0 schema modifications (grep-verified)
- [ ] No PR-A1 module modifications (grep-verified)
- [ ] No pyproject.toml deps added

### Process

- [ ] Plan TR, code/docs EN (CLAUDE.md §16)
- [ ] Conventional commits
- [ ] PR title < 70 chars, body with CNS-021 ref
- [ ] Plan merged with PR

---

## 14. Risk & Mitigation (v2)

| Risk | Olasılık | Mitigation |
|---|---|---|
| Schema drift between workflow-definition and workflow-run pattern | Düşük | Drift regression test (v2 W1) |
| Cross-ref enforcement bypass | Düşük | Integration test acceptance (v2 B2); PR-A3 executor contract note |
| Versionless intent resolution surprise | Düşük | Explicit "highest semver across sources" contract + optional per-rule `workflow_version` (v2 B3) |
| No-match behavior inconsistency | Eliminated | Net contract per strategy (v2 B4) |
| Duplicate rule_id collision | Eliminated | Loader-level explicit check (v2 B5) |
| Fixture filename pattern mismatch | Eliminated | Dash-named fixtures (v2 B6) |
| Cross-ref type erasure | Eliminated | `CrossRefIssue` structured type (v2 B7) |
| Adapter load-time edge-case coverage gaps | Düşük | Expanded reason taxonomy + negative fixtures (v2 W9) |
| Test count too low for real coverage | Düşük | Target 110-140 (v2 W10) |
| SemVer comparator bug without packaging dep | Düşük | Local comparator + explicit test matrix (v2 Q3-add2) |

---

## 15. Post-PR-A2 Outlook (unchanged)

PR-A2 unblocks:

- **PR-A3** — worktree executor. Consumes `WorkflowRegistry.get` + `AdapterRegistry.get` + `validate_cross_refs` (fail-closed), enforces `policy_worktree_profile`, spawns subprocess/HTTP.
- **PR-A4** — diff/patch engine.
- **PR-A5** — evidence timeline CLI.
- **PR-A6** — demo runnable + `[coding]` meta-extra + `[llm]` fallback intent classifier impl + README.

---

## 16. Audit Trail

| Field | Value |
|---|---|
| Base SHA | `2245a1d` (PR-A1 merge @ main) |
| Branch | `claude/tranche-a-pr-a2` (created) |
| Plan authority | v2.1.1 §15 + PR-A0 + PR-A1 |
| CNS (PR-A2 plan) | CNS-20260415-021 iter-1 PARTIAL → iter-2 pending |
| Adversarial stats iter-1 | 7 blocking + 10 warning absorbed in v2 |
| Sibling plans | `PR-A0-DRAFT-PLAN.md`, `PR-A1-IMPLEMENTATION-PLAN.md` |
| Extension pattern ref | `ao_kernel/extensions/loader.py::ExtensionRegistry` |
| Schema validator pattern ref | `ao_kernel/workflow/schema_validator.py` (@lru_cache + Draft 2020-12) |

---

**Status:** DRAFT v2, 7 blocker + 10 warning absorbed. Awaiting CNS-021 iter-2 AGREE before implementation.
