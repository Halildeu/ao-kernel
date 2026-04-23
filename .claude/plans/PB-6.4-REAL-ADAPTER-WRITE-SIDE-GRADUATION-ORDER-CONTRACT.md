# PB-6.4 — Real-adapter / Write-side Graduation Order Contract

**Status:** In progress (decision/ordering slice)  
**Date:** 2026-04-23  
**Parent tracker:** [#243](https://github.com/Halildeu/ao-kernel/issues/243)  
**Active issue:** [#263](https://github.com/Halildeu/ao-kernel/issues/263)

## 1) Problem

`PB-6.3b` sonrası sıradaki risk, widening adaylarını yanlış sırada açmaktır:

- real-adapter lane'leri helper smoke ile fazla güvenli varsaymak,
- write-side lane'leri rollback/evidence sınırı netleşmeden açmak,
- docs/runtime/support mapping tutarlılığını bozmaktır.

Bu nedenle `PB-6.4`'ün işi yeni runtime promotion yazmak değil, **promotion
sırasını ve kapılarını sertleştirmektir**.

## 2) Scope ve Scope Dışı

### Scope

1. real-adapter lane promotion sırasını risk/kanıt ekseninde yeniden dizmek
2. write-side widening adaylarını açık hold koşullarına bağlamak
3. support mapping (docs + doctor truth + issue/status dili) tutarlılığını
   tek kararda sabitlemek

### Scope dışı

1. Bu slice içinde yeni runtime action/handler promotion'ı yapmak
2. `gh-cli-pr` live remote PR opening lane'ini doğrudan açmak
3. `PRJ-KERNEL-API` write-side action'ları (`project_status`,
   `roadmap_follow`, `roadmap_finish`) widening'e almak

## 3) Mevcut Baseline (Karar Girdisi)

1. Public support boundary dar tutuluyor: shipped baseline +
   operator-managed beta lane ayrımı net.
2. `PRJ-KERNEL-API` bugün yalnız read-only iki action ile runtime-backed.
3. `PRJ-CONTEXT-ORCHESTRATION` `contract_only`; runtime handler yok.
4. `claude-code-cli` ve `gh-cli-pr` lane'leri beta/operator-managed.
5. Write-side lane'lerde rollback/evidence ve side-effect boundary riskleri,
   read-only lane'lere göre daha yüksek.

## 4) Risk-Ordered Lane Sıralaması

| Sıra | Aday | Risk | Karar |
|---|---|---|---|
| 1 | Support mapping hardening (`docs` + truth inventory sınıfları) | Düşük | **First** |
| 2 | `claude-code-cli` lane promotion readiness kararı | Orta | **Second** |
| 3 | `gh-cli-pr` live remote PR opening write lane | Yüksek | **Hold** |
| 4 | `PRJ-KERNEL-API` write-side action widening | Yüksek | **Hold** |

## 5) Tranche Planı

### `PB-6.4a` (First): Support mapping hardening

Amaç:

1. inventory-to-support mapping tablosunu SSOT yüzeylerde tek anlamlı yapmak
2. `doctor` truth sınıfları ile docs sınıfları arasındaki eşleşme kuralını
   yazılı hale getirmek

DoD:

1. support mapping tablosu tekil ve çelişkisiz
2. `runtime_backed / contract_only / quarantined` sınıfları docs diline
   birebir bağlanmış
3. status/issue yüzeyi "next active slice" bilgisini net taşıyor

### `PB-6.4b` (Second): `claude-code-cli` lane promotion readiness kararı

Amaç:

1. helper smoke geçen lane'i widening adayı saymak için minimum proof seti
   yazmak
2. known-bug durumu ve operator prerequisite'leri promotion kararına bağlamak

DoD:

1. lane-specific promotion checklist
2. failure-mode matrisi + prerequisite doğrulama adımları
3. karar sonucu: `stay beta` veya `promotion candidate`, gerekçesiyle yazılı

### `PB-6.4c` (Hold): `gh-cli-pr` live write lane

Hold koşulları:

1. disposable sandbox ve side-effect boundary sözleşmesi
2. rollback + evidence completeness koşulları
3. güvenli preflight ile live write lane ayrımının testle pinlenmesi

### `PB-6.4d` (Hold): `PRJ-KERNEL-API` write-side actions

Hold koşulları:

1. write-side governance/policy contract netleşmesi
2. action-level behavior tests + negative path coverage
3. support boundary dokümanlarında explicit widening kararı

## 6) Widening İçin Zorunlu Ortak Kanıt Seti

Herhangi bir widening kararı için aşağıdaki 5 kapı birlikte aranır:

1. gerçek code path (bootstrap/handler/runtime bağlantısı)
2. behavior-first test (pozitif + negatif path)
3. smoke kanıtı (operator lane ise prerequisite dahil)
4. docs/support boundary parity
5. rollback + known-bug durumu

Bu beş kapıdan biri eksikse lane widening yapılmaz.

## 7) Bu Slice'ın Çıkış Kriteri

`PB-6.4` karar slice'ı, aşağıdakiler yazılı olduğunda kapanır:

1. first/second/hold lane sırası
2. her lane için açık DoD/hold koşulu
3. bir sonraki implementasyon hattının tekil seçimi (`PB-6.4a`)

## 8) Sıradaki Adım

Bu karar contract'ı merge olduktan sonra ilk implementasyon hattı:

1. `PB-6.4a` support mapping hardening (docs/truth parity slice)
