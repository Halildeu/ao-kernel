# WP-8.4 — Public Capability / Support Matrix Alignment

**Durum tarihi:** 2026-04-22
**İlişkili issue:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)
**Üst WP:** [#199](https://github.com/Halildeu/ao-kernel/issues/199)

## Amaç

`WP-8.2` ve `WP-8.3` ile gerçek adapter smoke yüzeyleri somutlaştıktan sonra,
bu yüzeylerin public dokümanlarda tek anlamlı tier diline oturmasını
sağlamak. Bu slice yeni runtime semantics eklemez; support boundary ve
capability matrisi ifadelerini hizalar.

## Bu Slice'ın Sınırı

- odak `docs/PUBLIC-BETA.md` + `docs/ADAPTERS.md` + status SSOT
- `claude-code-cli` ve `gh-cli-pr` için tek anlamlı tier dili üretmek
- `WP-9` runbook / incident readiness kapsamına girmemek
- yeni operator smoke ya da runtime code eklememek

## Hedef Tier Dili

| Yüzey | Hedef ifade |
|---|---|
| Bundled `review_ai_flow` + `codex-stub` | Shipped |
| `claude-code-cli` helper-backed real-adapter lane | Beta (operator-managed) |
| `gh-cli-pr` helper-backed dry-run lane | Beta (operator-managed preflight only) |
| `gh-cli-pr` ile gerçek remote PR açılışı | Deferred |

## Kabul Kriterleri

1. `docs/PUBLIC-BETA.md` ve `docs/ADAPTERS.md` aynı tier kelimelerini kullanır
2. `claude-code-cli` için helper-backed smoke varlığı beta/operator-managed
   olarak ifade edilir; shipped baseline sanılmaz
3. `gh-cli-pr` için dry-run helper ile live PR opening açıkça ayrılır
4. `PRODUCTION-HARDENING-PROGRAM-STATUS.md` `WP-8.3`'ü kapanmış, `WP-8.4`'ü
   aktif slice olarak gösterir

## Beklenen Sonraki Adım

`WP-8.4` merge sonrası aktif hat `WP-9` olur:

- incident runbook
- rollback yolu
- upgrade notes
- support boundary
- known bugs registry
