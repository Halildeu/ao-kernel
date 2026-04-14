# .archive/patches/

Historical `.patch` files moved here during Preflight P7 (CNS-20260414-006 Q9 recommendation).

## Context

These 20 patch files were generated while developing Faz 2–Faz 4 features. All their commits are merged into `main` (verified 2026-04-14 against history `dc25cd2` and prior). They are kept here as a psychological safety net rather than deleted outright — git history already retains the content.

## Can I delete these?

Yes, at any time. They contain no data that is not already reachable through `git log`. Keeping them for one release cycle (through v2.2.0) is a soft guarantee; after that, feel free to remove the directory entirely.

## Why not just delete them now?

CNS-20260414-006 Q9: "güvenli önerim doğrudan silmek yerine önce `.archive/patches/` altına taşıyın veya tek bir inventory notuyla bir release çevrimi bekleyin; teknik açıdan silmek recoverability'yi yok etmez, ama psikolojik safety net için arşiv geçişi daha sakin."

## Inventory

See `ls .archive/patches/*.patch` for the full list. Files are tracked by git and recoverable via `git log --follow` if ever needed.
