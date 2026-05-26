# RG-1 Bootstrap — Operator-Bound Supersession Record

**Status:** operator bilinçli onay bekleyen tek seferlik bootstrap istisnası
**PR:** [#643](https://github.com/Halildeu/ao-kernel/pull/643)
**Branch:** `codex/rg-conclusion-semantics`
**Decision artifact:** `rg_1_bootstrap_operator_supersession_one_shot`

## Context

`RG-CONCLUSION-SEMANTICS` C-prime migration kendi paradox'unu kıramaz: PR
`#643`'ün `ao-release-gate` job'u `base/scripts/` üzerinde çalışır, ama base
= `origin/main = 1f70ce7` migration'ın yeni script (`ao_release_gate_publish_check_runs.py`)
ve flag'lerini (`--wrapper-exit-code`, `--emit-multi-check-runs`)
henüz içermez.

Codex iter-3 BLOCK + iter-4 önerisi: workflow **bootstrap-safe**. Decision
step `--help` probe ile yeni flag desteğini test eder; yoksa legacy
`--fail-on-deny`'e düşer. Publish step script'in var olup olmadığını
kontrol eder; yoksa warning + exit 0.

Bootstrap-safe pattern PR #643'ün **gelecekteki** API değişikliklerine
karşı defansiftir, ama PR #643'ün **kendi** gate run'u hâlâ legacy
mantıkla çalışır: `--fail-on-deny` + path-sensitive
`.github/workflows/`, `scripts/ao_release_gate*.py`, `.claude/plans/`,
`ao_kernel/ao_release_gate.py` değişiklikleri →
`path_sensitive_human_review_missing` blocker → exit 1.

## Operator Paradox

Bu single-shot bootstrap'in **kendi paradoxu**:

| Operator HARD RULE | Bu PR'ın durumu |
|---|---|
| "CI tamamen yeşil olmadan approve YOK" (`feedback_operator_approve_requires_green_ci.md`) | ao-release-gate fail (legacy mantık + path-sensitive review missing) |
| "Gate yapısal false-red veriyorsa workflow fix önce gelir" (CLAUDE.md) | Bu PR **workflow fix**'in kendisi |

Bu PR olmadan workflow fix uygulanamaz; bu PR'ı merge etmek için ise
operator approve şart, ama yeni semantik henüz aktif değil → kilit.

## Çözüm: Tek seferlik operator-bound supersession

CLAUDE.md HARD RULE — Governance / Sistemik Bug (2026-05-05):

> "Admin Merge YOK. Ad hoc 'workflow bug fix, bir kere admin merge
> yapalım' çizgisi mevcut kontratla çakışır. (...) Eğer operator
> prensibi 'failing check varken review bile yok' diye mutlak kalacaksa
> in-band çözüm yok. O zaman tek doğru yol: explicit operator-bound
> supersession kaydı ile ruleset migration yapmak."

Codex iter-2 (thread `019e65c3`) buna paralel: paradox kırmanın in-band
yolu yok; tek doğru yol explicit operator-bound supersession kaydı +
açık beyan.

## Operator açık beyan (sen tamamlayacaksın)

Bu kayıt PR #643 merge edilirken operator (`Halildeu` veya
`gladyatore-lab`) tarafından açıkça onaylanmalı. Onay yöntemleri:

**Yöntem 1: PR approve + commit reference**

PR #643 sayfasında "Review changes → Approve" tuşu, body olarak:

```
RG-1 bootstrap operator-bound supersession.

Kabul ediyorum: bu PR'ın ao-release-gate fail göstergesi yapısal
false-red (path_sensitive_human_review_missing). Bu PR workflow fix'in
kendisi; migration sonrası gate doğru sinyal verecek. Tek seferlik
istisna, governance debt biriktirmez.

Audit ref: .claude/plans/RG-1-BOOTSTRAP-OPERATOR-SUPERSESSION.md
```

**Yöntem 2: gh CLI**

```bash
gh pr review 643 --approve --body "RG-1 bootstrap operator-bound supersession; audit ref .claude/plans/RG-1-BOOTSTRAP-OPERATOR-SUPERSESSION.md"
```

## Post-merge contract

PR #643 merge sonrası:

1. main'de yeni script + flag'ler artık mevcut
2. Sonraki PR'ların base'i RG-1 merged main → bootstrap fallback path'i
   alınmaz, yeni `--wrapper-exit-code` yolu çalışır
3. Operator paradox **artık yaşanmaz**: lone CODEOWNER-review-pending
   blocker → legacy `ao-release-gate` job exit 0 (success), CI yeşil,
   operator prensibi korunur, approve verir
4. Dual check-run (`ao-release-gate-technical` + `ao-release-gate-review`)
   yayını başlar (shadow, henüz required değil)

## Phase 2 (RG-2 follow-up — operator action)

Bu kayıttan ayrı bir audit doc'u ile operator ruleset `16803733`'te
required check setini değiştirir:

- **Kaldır:** `ao-release-gate` (eski; compatibility wrapper olarak
  çalışmaya devam eder ama required değil)
- **Ekle:** `ao-release-gate-technical` (source-pinned integration_id 15368)
- **Ekle:** `ao-release-gate-review` (source-pinned integration_id 15368)

## Phase 3 (RG-3 follow-up PR)

Eski compatibility wrapper code path silinir; sadece dual check-run
yayını kalır.

## Bu kayıt forbidden actions hala korur

- Branch protection / ruleset mutation: **operator action**, agent değil
- `gpp_status.v1.json`, `gp5_platform_claim_decision.py`, policies,
  public SDK signatures: dokunulmamış
- `support_widening`, `production_platform_claim`,
  `live_adapter_execution`: hepsi `false`
- Admin Merge YASAK: `--admin` flag kullanılmadı; bu **normal merge** +
  operator approve, sadece "approve = CI yeşil" prensibinin tek seferlik
  bilinçli askıya alınması

## Audit trail

| Alan | Değer |
|---|---|
| Decision | `rg_1_bootstrap_operator_supersession_one_shot` |
| PR | https://github.com/Halildeu/ao-kernel/pull/643 |
| Branch | `codex/rg-conclusion-semantics` |
| HEAD (will fill) | (PR merge sonrası commit SHA) |
| Operator | `Halildeu` veya `gladyatore-lab` |
| Codex thread | `019e65c3-7841-7211-b627-e79e9af48643` |
| Plan doc | `.claude/plans/RG-1-CONCLUSION-SEMANTICS-MIGRATION.md` |
| Evidence | `local-ai-review-evidence.v1.json` |
| Operator prensibi reference | `feedback_operator_approve_requires_green_ci.md` |
| Bootstrap fallback impl | `.github/workflows/test.yml` ao-release-gate job |
| Effective on | merge (RG-1 main'e indikten sonra paradox çözülür) |
