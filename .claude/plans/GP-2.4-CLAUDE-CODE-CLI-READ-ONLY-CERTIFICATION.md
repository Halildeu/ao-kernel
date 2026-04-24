# GP-2.4 — Claude Code CLI Read-Only Certification Contract

**Status:** Completed
**Date:** 2026-04-24
**Tracker:** [#363](https://github.com/Halildeu/ao-kernel/issues/363)
**Verdict issue:** [#371](https://github.com/Halildeu/ao-kernel/issues/371)
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
4. Current local baseline probe `2026-04-24` tarihinde 30 saniyelik helper
   timeout ile geçti:
   - `claude --version`: `2.1.87 (Claude Code)`
   - `claude auth status`: pass, auth method `claude.ai`
   - `claude -p "reply with the single token ok"`: pass
   - bundled manifest invocation smoke: pass
   - API key env route: not present
5. Aynı oturumda 10 saniyelik probe `prompt_smoke_timeout` üretebildiği için
   certification prerequisite komutu 30 saniye timeout ile koşulacaktır.
6. Bu baseline operator ortamının sağlıklı olduğunu gösterir; destek sınırını
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
| Final support tier | Beta (operator-managed) |
| Final verdict | `operator_managed_beta_keep` |

## Work Breakdown

### `GP-2.4a` — Preflight Evidence Contract

Status: Completed by issue [#365](https://github.com/Halildeu/ao-kernel/issues/365).

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

Closeout:

1. `tests/test_claude_code_cli_smoke.py` passing preflight JSON output shape'ini
   top-level ve per-check zorunlu alanlarla pinler.
2. Canonical passing check seti pinlidir:
   `version`, `auth_status`, `prompt_access`, `manifest_invocation`.
3. `auth_status=pass` + `prompt_access=fail` overall `blocked` kalır;
   `KB-001` sınıfı fake green üretemez.
4. `ANTHROPIC_API_KEY` varlığı gözlemlenir fakat prompt access fail durumunu
   başarıya çeviremez; `KB-002` fallback/token route'u primary certification
   path değildir.
5. Support boundary unchanged kalır; helper pass tek başına production
   certification değildir.

### `GP-2.4b` — Governed Workflow Smoke Evidence

Status: completed by issue [#367](https://github.com/Halildeu/ao-kernel/issues/367).

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
4. Adapter stdout/stderr evidence log redacted halde yazılır.
5. Output parse fail-closed davranışı korunur.

DoD:

1. Read-only workflow smoke tekrarlanabilir komutla belgelenir.
2. Evidence/artifact path'leri docs ve runbook ile aynı şeyi söyler.
3. Smoke başarısı repo root/PYTHONPATH kontaminasyonuna dayanmaz.

Closeout:

1. `ao_kernel.real_adapter_workflow_smoke` governed workflow smoke helper'ını
   sağlar.
2. `scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60`
   canlı koşuda `overall_status=pass`, `final_state=completed` döndürdü.
3. Kanıt run'ı:
   - `run_id=c17e1456-2e4c-40fd-8942-c4880bd6fcc8`
   - workspace:
     `/private/var/folders/ly/mwks8pvj07q2s1njtcnjjk2c0000gn/T/ao-kernel-claude-workflow-smoke-7q53d5w2`
4. Doğrulanan evidence seti:
   - `step_started`
   - `policy_checked`
   - `adapter_invoked`
   - `step_completed`
   - `workflow_completed`
5. `review_findings` artifact'i schema-valid materialize oldu:
   `artifacts/invoke_review_agent-review_findings-attempt1.json`.
6. `adapter-claude-code-cli.jsonl` redaction kontrolünden geçti.
7. Support boundary unchanged kalır; `GP-2.4d` verdict sonucunda lane
   production-certified yapılmadı.

### `GP-2.4c` — Failure-Mode Matrix

Status: completed by issue [#369](https://github.com/Halildeu/ao-kernel/issues/369).

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

Closeout:

| Failure | Finding code / kanıt | Test |
|---|---|---|
| `claude` binary missing | `claude_binary_missing`, remaining checks `skip` | `test_binary_missing_blocks_and_skips_remaining_checks` |
| `auth_status` not logged in | `claude_not_logged_in` | `test_auth_status_not_logged_in_blocks_preflight_contract` |
| `prompt_access` fail | `prompt_access_denied`; `auth_status=pass` başarıya çeviremez | `test_auth_status_pass_prompt_access_fail_blocks_preflight_contract` |
| manifest invocation timeout | `manifest_smoke_timeout` | `test_manifest_timeout_is_reported_without_success_promotion` |
| manifest non-JSON output | `manifest_output_not_json` | `test_manifest_non_json_output_is_contract_failure` |
| adapter non-zero exit | `adapter_non_zero_exit` | `test_workflow_smoke_classifies_adapter_non_zero_exit` |
| malformed workflow output | `output_parse_failed` | `test_workflow_smoke_classifies_output_parse_fail_closed` |
| policy deny | `policy_denied` | `test_workflow_smoke_classifies_policy_denial_before_promotion` |

`WorkflowSmokeCheck` artık `finding_code` taşır; `findings[]` stable code'ları
önceler, prose-only failure üretmez. Support boundary unchanged kalır; `GP-2.4d`
verdict sonucunda lane production-certified yapılmadı.

### `GP-2.4d` — Support Boundary Verdict

Status: completed by issue [#371](https://github.com/Halildeu/ao-kernel/issues/371).

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

Closeout:

| Karar alanı | Sonuç |
|---|---|
| Final verdict | `operator_managed_beta_keep` |
| Stable support boundary impact | Unchanged |
| Public tier | `Beta (operator-managed)` |
| Production-certified read-only? | Hayır |
| Shipped demo impact | Yok; default shipped demo `review_ai_flow + codex-stub` kalır |
| Next GP lane | `gh-cli-pr` live-write rollback rehearsal |

Gerekçe:

1. `GP-2.4a`, `GP-2.4b` ve `GP-2.4c` evidence kapıları kapanmıştır; lane
   helper preflight, governed workflow smoke ve negative failure-mode matrix
   üretir.
2. Bu kanıtlar lane'i "fake green olmayan operator-managed beta" seviyesine
   yükseltir; ancak `claude-code-cli` hâlâ repo-native değildir ve operator
   ortamındaki external `claude` PATH binary, session auth ve prompt access
   prerequisite'lerine bağlıdır.
3. `KB-001` ve `KB-002` shipped baseline'ı etkilemez; fakat production-certified
   read-only support claim için ortam-bağımsızlık ve CI-managed live adapter
   garantisi hâlâ eksiktir.
4. Bu nedenle support tier genişlemez. Lane kullanılabilir, kanıtlı ve
   işletilebilir bir Beta/operator-managed yüzey olarak kalır.

## Out of Scope

- `gh-cli-pr` live-write veya remote PR creation.
- Claude API key-first integration.
- Extension support widening.
- Version bump, tag, publish veya release.
- Stable support boundary promotion before `GP-2.4d`.

## Zorunlu Kanıt Komutları

Contract PR için minimum:

```bash
python3 -m pytest -q tests/test_claude_code_cli_smoke.py
python3 -m pytest -q tests/test_claude_code_cli_workflow_smoke.py
python3 scripts/claude_code_cli_smoke.py --output json --timeout-seconds 30
python3 scripts/claude_code_cli_workflow_smoke.py --output json --timeout-seconds 60
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
```

Implementation PR'larda ek olarak hedef testler ve governed workflow smoke
komutları yazılacaktır.

## Exit Criteria

1. `GP-2.4a..d` çıktıları tamamlandı.
2. Certification verdict tek değere indi: `operator_managed_beta_keep`.
3. Docs/runtime/tests/CI/support boundary aynı kararı anlatır.
4. Stable support boundary genişlemedi.
