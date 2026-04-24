# GP-2.5 — gh-cli-pr Live-Write Rollback Rehearsal Contract

**Status:** Completed — `rehearsal_pass_keep_beta`
**Date:** 2026-04-24  
**Tracker:** [#373](https://github.com/Halildeu/ao-kernel/issues/373)  
**Live rehearsal tracker:** [#375](https://github.com/Halildeu/ao-kernel/issues/375)
**Parent:** [#329](https://github.com/Halildeu/ao-kernel/issues/329)  
**Parent roadmap:** `.claude/plans/GP-2-DEFERRED-SUPPORT-LANES-REPRIORITIZATION.md`

## Amaç

`gh-cli-pr` lane'ini preflight/readiness seviyesinden gerçek remote PR opening
support claim'ine taşımadan önce disposable sandbox ve rollback rehearsal
sözleşmesini tek karar kaynağına indirmek.

Bu slice tek başına live remote PR opening'i promote etmez. Amaç, yan etkili
bir sonraki denemenin hangi repo, branch, komut, artifact, cleanup ve verdict
kurallarıyla kabul edileceğini yazılı hale getirmektir.

## Başlangıç Gerçeği

1. `gh-cli-pr` repo-native binary değildir; operator ortamındaki external `gh`
   PATH binary'sine ve GitHub auth durumuna dayanır.
2. Public support boundary bugün iki ayrı çizgi taşır:
   - `gh-cli-pr` helper-backed preflight + live-write readiness probe:
     Beta/operator-managed
   - full remote PR opening: Deferred
3. `GP-1.2` canlı create -> verify -> rollback zinciri denemiştir; ancak
   `--require-disposable-keyword ao-kernel` override ile ana repo üzerinde
   doğrulandığı için verdict `stay_preflight` kalmıştır.
4. `PB-8.1` ile helper tarafında explicit opt-in, disposable keyword guard,
   create -> verify -> rollback ve keep-open risk guard'ları kod/test
   seviyesinde mevcuttur.
5. `GP-2.5` bu mevcut guard'ları support-boundary kararına çevirecek yeni
   disposable rehearsal sözleşmesini tanımlar.

## Current No-Side-Effect Evidence

2026-04-24 tarihli yan etkisiz doğrulama:

```bash
python3 scripts/gh_cli_pr_smoke.py \
  --mode preflight \
  --output json \
  --timeout-seconds 20 \
  --report-path /tmp/gp25-gh-preflight.report.json
```

Sonuç:

1. `overall_status=pass`
2. `binary_path=/opt/homebrew/bin/gh`
3. `repo_name=Halildeu/ao-kernel`
4. `version`, `auth_status`, `manifest_contract`, `repo_view`,
   `pr_dry_run` checks pass

Fail-closed guard doğrulaması:

```bash
python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --head main \
  --base main \
  --output json \
  --timeout-seconds 20 \
  --report-path /tmp/gp25-gh-livewrite-guard.report.json
```

Sonuç:

1. `overall_status=blocked`
2. `findings=["gh_pr_live_write_same_head_base"]`
3. `pr_live_write_verify` ve `pr_live_write_rollback` checks `skip`
4. Remote PR side effect oluşmadı.

## Disposable Live-Write Rehearsal Evidence

2026-04-24 tarihinde `GP-2.5a` kapsamında disposable sandbox rehearsal
çalıştırıldı.

Hedef:

1. repo: `Halildeu/ao-kernel-sandbox`
2. repo visibility: private
3. default branch: `main`
4. head branch: `smoke/gp25-livewrite-20260424T024918Z`
5. artifact root: `/tmp/ao-kernel-gp25a-gh-cli-pr-live-write`

Komut:

```bash
python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --repo Halildeu/ao-kernel-sandbox \
  --head smoke/gp25-livewrite-20260424T024918Z \
  --base main \
  --output json \
  --timeout-seconds 30 \
  --report-path /tmp/ao-kernel-gp25a-gh-cli-pr-live-write/gh-cli-pr-live-write.report.json
```

Sonuç:

1. `overall_status=pass`
2. `adapter_id=gh-cli-pr`
3. `repo_name=Halildeu/ao-kernel-sandbox`
4. `findings=[]`
5. `version`, `auth_status`, `manifest_contract`, `repo_view`,
   `pr_live_write`, `pr_live_write_verify`, `pr_live_write_rollback` checks
   pass
6. created PR: `https://github.com/Halildeu/ao-kernel-sandbox/pull/1`
7. independent final PR state: `CLOSED`
8. remote head ref cleanup: `404 Not Found` for
   `heads/smoke/gp25-livewrite-20260424T024918Z`

İlk denemede helper, current GitHub CLI için geçersiz olan
`gh repo view --repo <repo>` çağrısında fail-closed durdu. Bu regression
`gh repo view <repo> --json ...` şeklinde dar scope'la düzeltildi ve
`tests/test_gh_cli_pr_smoke.py::test_repo_override_uses_positional_repo_view_arg`
ile pinlendi. İlk denemede PR oluşturulmadı; yalnız push edilen ephemeral head
branch temizlendi.

Final verdict:

`rehearsal_pass_keep_beta`. Disposable sandbox create -> verify -> rollback
zinciri çalışmıştır, ancak bu tek başına `gh-cli-pr` full remote PR opening'i
stable shipped support'a yükseltmez. Lane Beta/operator-managed kalır; support
widening için ayrı promotion PR'ı, tekrar edilebilir kanıt ve docs parity
gerekir.

## Rehearsal Target Contract

Live-write rehearsal yalnız aşağıdaki koşulların tamamı sağlanırsa çalıştırılır:

1. **Disposable repo:** `--repo <owner>/<repo>` explicit verilir ve repo adı
   default guard keyword `sandbox` içerir.
2. **No production target:** `Halildeu/ao-kernel` veya korunan production repo
   hedef alınmaz. Eğer guard keyword override gerekiyorsa karar notunda nedeni
   yazılır; bu override support widening kanıtı sayılmaz.
3. **Explicit refs:** `--head` ve `--base` explicit verilir; default branch
   fallback kabul edilmez.
4. **Different refs:** `--head != --base`.
5. **Ephemeral head branch:** head branch `smoke/gp25-livewrite-<timestamp>`
   formatındadır ve rehearsal sonunda remote/local cleanup yapılır.
6. **Rollback mandatory:** `--keep-live-write-pr-open` kullanılmaz. Rollback
   check pass olmadan rehearsal success sayılmaz.
7. **Artifact mandatory:** `--report-path` ile JSON raporu kalıcı artifact
   olarak yazılır.

Canonical command shape:

```bash
ARTIFACT_ROOT=/tmp/ao-kernel-gp25-gh-cli-pr-live-write
mkdir -p "$ARTIFACT_ROOT"

python3 scripts/gh_cli_pr_smoke.py \
  --mode live-write \
  --allow-live-write \
  --repo <owner>/<sandbox-repo> \
  --head smoke/gp25-livewrite-<timestamp> \
  --base main \
  --output json \
  --report-path "$ARTIFACT_ROOT/gh-cli-pr-live-write.report.json"
```

## Required Evidence

Bir rehearsal ancak aşağıdaki JSON koşullarıyla `pass` kabul edilir:

| Alan | Beklenen |
|---|---|
| `overall_status` | `pass` |
| `adapter_id` | `gh-cli-pr` |
| `repo_name` | disposable/sandbox repo |
| `findings` | `[]` |
| `checks.version.status` | `pass` |
| `checks.auth_status.status` | `pass` |
| `checks.manifest_contract.status` | `pass` |
| `checks.repo_view.status` | `pass` |
| `checks.pr_live_write.status` | `pass` |
| `checks.pr_live_write_verify.status` | `pass` |
| `checks.pr_live_write_rollback.status` | `pass` |

Ek artifact beklentileri:

1. report path commit edilmez; issue/PR comment'inde summary + artifact path
   yazılır.
2. created PR URL raporda görünür.
3. rollback sonrası PR `CLOSED` doğrulanır.
4. ephemeral head branch local ve remote temizlenir.
5. cleanup yapılamazsa rehearsal `pass` olsa bile support promotion açılmaz;
   ayrı cleanup incident kaydı gerekir.

## Failure Matrix

| Failure | Stable finding code | Verdict etkisi |
|---|---|---|
| `gh` binary missing | `gh_binary_missing` | block |
| auth fail | `gh_auth_failed` / auth status finding | block |
| live-write opt-in yok | `gh_pr_live_write_opt_in_required` | block |
| repo context yok | `gh_pr_live_write_repo_context_required` | block |
| explicit base yok | `gh_pr_live_write_base_ref_required` | block |
| explicit head yok | `gh_pr_live_write_head_ref_required` | block |
| head/base aynı | `gh_pr_live_write_same_head_base` | block |
| repo disposable değil | `gh_pr_live_write_repo_not_disposable` | block |
| create fail | `gh_pr_live_write_failed` | block |
| verify fail | `gh_pr_live_write_verify_failed` | block; rollback yine denenmeli |
| keep-open istendi | `gh_pr_live_write_keep_open_requested` | block |
| rollback timeout | `gh_pr_live_write_rollback_timeout` | block |
| rollback fail | `gh_pr_live_write_rollback_failed` | block |

## Verdict Options

`GP-2.5` sonunda yalnız şu kararlardan biri verilir:

1. `rehearsal_pass_keep_beta`: create -> verify -> rollback canlı geçti; lane
   Beta/operator-managed kalır, production support için ek tekrar ve ops gate
   gerekir.
2. `rehearsal_fail_keep_deferred`: rehearsal guard veya rollback koşulları
   kapanmadı; full remote PR opening Deferred kalır.
3. `promotion_candidate_live_write`: disposable rehearsal tekrar edilebilir
   evidence üretti; support widening için ayrı promotion PR'ı açılabilir.

Bu slice'ın varsayılanı `rehearsal_pass_keep_beta` veya
`rehearsal_fail_keep_deferred` olmalıdır. `promotion_candidate_live_write`
ancak en az bir disposable sandbox pass + cleanup kanıtı ve docs parity ile
değerlendirilir.

## Out of Scope

- Stable support boundary widening.
- Production repo üzerinde gerçek remote PR create çalıştırmak.
- `bug_fix_flow` release closure support promotion.
- Version bump, tag veya publish.
- `claude-code-cli` support verdict'ini değiştirmek.

## Validation Commands

Contract PR için minimum:

```bash
python3 -m pytest -q tests/test_gh_cli_pr_smoke.py
python3 scripts/gh_cli_pr_smoke.py --mode preflight --output json --timeout-seconds 20
python3 scripts/gh_cli_pr_smoke.py --mode live-write --allow-live-write --repo Halildeu/ao-kernel-sandbox --head main --base main --output json --timeout-seconds 20
python3 scripts/truth_inventory_ratchet.py --output json
python3 -m pytest -q tests/test_cli_entrypoints.py tests/test_doctor_cmd.py
```

Not: Üçüncü komutun `overall_status=blocked` ve
`gh_pr_live_write_same_head_base` finding'i üretmesi beklenen güvenlik
davranışıdır.

## Exit Criteria

1. Contract repo içinde merge edilir.
2. GP-2 roadmap/status bu contract'ı aktif hat olarak gösterir.
3. No-side-effect preflight ve guard smoke kanıtı yazılır.
4. Disposable live-write rehearsal için exact command/artifact/cleanup/verdict
   kuralları netleşir.
5. Stable support boundary unchanged kalır.

## Closeout

`GP-2.5` ve `GP-2.5a` birlikte şu kararı üretmiştir:

1. no-side-effect preflight ve guard smoke geçmiştir;
2. sandbox live-write create -> verify -> rollback zinciri geçmiştir;
3. cleanup bağımsız olarak doğrulanmıştır;
4. repo override helper bug'ı testle kapatılmıştır;
5. stable support boundary unchanged kalmıştır;
6. next action support widening değil, gerekirse ayrı `gh-cli-pr` promotion
   decision PR'ıdır.
