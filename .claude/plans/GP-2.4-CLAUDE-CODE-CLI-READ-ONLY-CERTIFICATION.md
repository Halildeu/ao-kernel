# GP-2.4 — Claude Code CLI Read-Only Certification Contract

**Status:** Active
**Date:** 2026-04-24
**Tracker:** [#363](https://github.com/Halildeu/ao-kernel/issues/363)
**Parent:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`
**Handoff from:** `.claude/plans/GP-2.3-POST-STABLE-ADAPTER-CERTIFICATION-ENTRY.md`

## Amaç

`claude-code-cli` lane'ini stable support boundary'ye almadan önce read-only
real-adapter certification için gereken kanıt paketini tek contract altında
tanımlamak ve sonra küçük implementation/verification PR'larına bölmek.

Bu slice tek başına adapter'ı production-certified yapmaz. Certification
kararı ancak aşağıdaki evidence, failure-mode ve docs parity kapıları
kapatıldıktan sonra verilir.

## Başlangıç Gerçeği

1. `claude-code-cli` repo-native binary değildir; operator ortamındaki
   external `claude` PATH binary'sine dayanır.
2. Varsayılan auth yolu Claude Code session auth'tur. API key/env-token yolu
   fallback kabul edilir, primary recovery yolu değildir.
3. `claude auth status` tek başına yeterli değildir; gerçek `claude -p`
   prompt probe belirleyici sinyaldir.
4. Current local baseline probe `2026-04-24` tarihinde geçti:
   - `claude --version`: `2.1.87 (Claude Code)`
   - `claude auth status`: pass, auth method `claude.ai`
   - `claude -p "reply with the single token ok"`: pass
   - bundled manifest invocation smoke: pass
   - API key env route: not present
5. Bu baseline operator ortamının sağlıklı olduğunu gösterir; destek sınırını
   tek başına genişletmez.

## Certification Adayı

| Alan | Seçim |
|---|---|
| Adapter | `claude-code-cli` |
| Workflow | `governed_review_claude_code_cli` |
| Capability scope | `read_repo`, `review_findings` |
| Side-effect scope | read-only; live write yok |
| Required helper | `python3 scripts/claude_code_cli_smoke.py --output json` |
| Existing runbook | `docs/BENCHMARK-REAL-ADAPTER-RUNBOOK.md` |
| Current support tier | Beta (operator-managed) |

## Work Breakdown

### `GP-2.4a` — Preflight Evidence Contract

Hedef: helper smoke sonucunu machine-readable certification evidence olarak
pinlemek.

Kapsam:

1. `scripts/claude_code_cli_smoke.py --output json` çıktısında zorunlu alanları
   yaz:
   - `overall_status`
   - `adapter_id`
   - `binary_path`
   - `api_key_env_present`
   - `checks[].name`
   - `checks[].status`
   - `checks[].finding_code`
   - `checks[].returncode`
2. `overall_status=pass` için zorunlu check seti:
   - `version`
   - `auth_status`
   - `prompt_access`
   - `manifest_invocation`
3. `auth_status=pass` ama `prompt_access=fail` durumunu blocker say.
4. API key/env-token route'unu primary certification path yapma.

DoD:

1. Helper output contract test veya snapshot assertion ile pinli.
2. Known bugs `KB-001` ve `KB-002` support boundary kararına bağlandı.
3. Docs, helper smoke'u certification prerequisite olarak anlatıyor.

### `GP-2.4b` — Governed Workflow Smoke Evidence

Hedef: helper-level manifest smoke dışında governed workflow path'inin read-only
şekilde çalıştığını kanıtlamak.

Kapsam:

1. `governed_review_claude_code_cli` workflow'u controlled workspace üzerinde
   koşar.
2. `review_findings` artifact'i schema-valid olarak materialize olur.
3. Evidence JSONL en az şu eventleri içerir:
   - `step_started`
   - `policy_checked`
   - `adapter_invoked`
   - `step_completed`
   - terminal workflow state
4. Adapter invocation envelope redacted halde yazılır.
5. Output parse fail-closed davranışı korunur.

DoD:

1. Read-only workflow smoke tekrarlanabilir komutla belgelenir.
2. Evidence/artifact path'leri docs ve runbook ile aynı şeyi söyler.
3. Smoke başarısı repo root/PYTHONPATH kontaminasyonuna dayanmaz.

### `GP-2.4c` — Failure-Mode Matrix

Hedef: production claim'i için gerekli negatif yolları fake-green bırakmamak.

Minimum failure matrix:

| Failure | Beklenen sonuç |
|---|---|
| `claude` binary missing | `claude_binary_missing`, overall blocked/fail |
| `auth_status` fail | `claude_not_logged_in` veya eşdeğer finding |
| `prompt_access` fail | prompt access blocker; auth status yeşili yeterli sayılmaz |
| manifest invocation timeout | timeout finding, workflow başlamadan blocker |
| non-zero exit | adapter step failed, evidence'da return code görünür |
| malformed output | `output_parse_failed`, workflow fail-closed |
| policy deny | subprocess invocation gerçekleşmeden `policy_denied` |

DoD:

1. En az helper-level negative tests var.
2. En az workflow-level fail-closed path doğrulanır.
3. Hata sınıfları `docs/KNOWN-BUGS.md` ve runbook diliyle çelişmez.

### `GP-2.4d` — Support Boundary Verdict

Hedef: certification sonucunu tek karara indirmek.

Olası verdict'ler:

1. `production_certified_read_only`
2. `operator_managed_beta_keep`
3. `stay_deferred`

Karar kuralları:

1. Helper smoke pass tek başına production certification değildir.
2. Governed workflow smoke + evidence completeness + failure matrix kapanmadan
   stable support boundary genişlemez.
3. `KB-001` veya `KB-002` shipped baseline'ı etkilemez; ancak
   `claude-code-cli` promotion kararını sınırlayabilir.
4. Live-write kapsamı bu kararın dışında kalır; `gh-cli-pr` rollback
   rehearsal ayrı lane'dir.

## Out of Scope

- `gh-cli-pr` live-write veya remote PR creation.
- Claude API key-first integration.
- Extension support widening.
- Version bump, tag, publish veya release.
- Stable support boundary promotion before `GP-2.4d`.

## Zorunlu Kanıt Komutları

Contract PR için minimum:

```bash
python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 10
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
```

Implementation PR'larda ek olarak hedef testler ve governed workflow smoke
komutları yazılacaktır.

## Exit Criteria

1. `GP-2.4a..d` çıktıları tamamlanır.
2. Certification verdict tek değere iner.
3. Docs/runtime/tests/CI/support boundary aynı kararı anlatır.
4. Stable support boundary yalnız kanıt kapıları kapanırsa genişler.

