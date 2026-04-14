# ao-kernel — Faz 5 Master Proje Planı

**Plan versiyonu:** v1.0
**Oluşturma tarihi:** 2026-04-14
**Hazırlayan:** Claude (assistant) + Halil (karar verici)
**İstişareler (girdi):** CNS-20260414-005 (plan review, Verdict D), CNS-20260414-006 (A0 safety net, Verdict C)
**Başlangıç baseline:** `main @ dc25cd2` — v2.1.1 PyPI'da yayında, 754 test, %77 branch coverage
**Hedef:** v2.2.0 → v2.3.0 → v3.0.0 sırasıyla üç release

> **Not:** Bu plan canlı bir doküman. Her tamamlanan adım işaretlenecek, her istişare sonucu `Change Log` bölümüne eklenecek. Değişiklik öneren herhangi bir karar için CNS açılmalı (CLAUDE.md §15).

---

## 1. Executive Summary

ao-kernel v2.1.1 teknik olarak **sağlam** (policy engine, memory loop, checkpoint/resume çalışıyor) ancak **üç borç kategorisi** var:

1. **Operasyonel güvenlik açığı:** `main` branch protection yok, global git config kayıp önleyici ayar yok, repo-local hook yok, bir worktree yanlış upstream track ediyor (`wizardly-euclid → origin/main`) — aktif kayıp riski.
2. **Faz 4 entegrasyon borcu:** PR #55'te scaffold edilen vector store, secrets factory, extension loader alt sistemleri production code path'inde **çağrılmıyor** (yetim abstraction'lar). Faz 4.4 checkpoint tek bağlı tranş.
3. **Ürünleşme açığı:** `examples/` yok, `SECURITY.md` yok, PyPI classifier "Alpha" (v2.1.1 ile uyumsuz), registry "vision/audio/code_agentic" flag'leri için provider implementasyonu sıfır → silent false-advertise riski.

**Bu plan** üç tranşla bu üç borcu sırayla kapatır, **her tranş bağımsız release üretir**:

| Release | Tranş | Hedef |
|---------|-------|-------|
| v2.2.0 | **Preflight (P1-P6)** + **Tranş A (A1-A8)** | Operasyonel güvenlik + hijyen + ürünleşme min seti |
| v2.3.0 | **Tranş B (B1-B5)** | Faz 4 wiring tamamlanır, abstraction'lar gerçekten tüketilir |
| v3.0.0 | **Tranş C (C1-C5)** | Test derinleşmesi + yeni capability'ler için hazırlık |

**Çekirdek ilke:** Fail-closed felsefesi (CLAUDE.md §2 madde 1) operasyonel güvenliğe de uygulanır. Preflight `git push` disiplini olmadan kod işi başlamaz.

---

## 2. Context & Drivers

### 2.1 Neden şimdi?

- Önceki oturum "master plan kapandı, yarım iş yok" raporladı → bu oturumun derin analizi **bunun doğru olmadığını** gösterdi (4 paralel Explore agent + grep doğrulaması).
- CNS-009 dersi tekrarlanmasın: "PR merge edildi ≠ özellik entegre oldu".
- Kullanıcı "kod ezilmesi/kaybolma" endişesini dile getirdi — operasyonel güvenlik artık bilinçli risk.

### 2.2 Karar girdileri

- **CNS-20260414-005** (Verdict D): Faz 5 planı yön olarak doğru, ama önce D0 pre-tranche (endpoint base_url, provider continuation state, secrets migration safety) gerekli. İki Claude iddiasını çürüttü.
- **CNS-20260414-006** (Verdict C): A0 safety net ayrı tranche değil, Tranş A'nın preflight gate'i olsun. Üç Claude önerisini çürüttü (linear history, pull.rebase global, push.default global). Aktif upstream hatası tespit etti.

### 2.3 Çözülmeyen teknik borçlar (Faz 5 **sonrasına** bilinçli erteleme)

Faz 5 bu 5 işi **kapsam dışı** bırakır, v3.0.0+ için uzun vadeli:
- Vision/audio altyapısı (CNS-005 C1 → A7'de sadece "unsupported" işaretleme yapılacak)
- Async/await refactor (D9 sync SDK kararı revizyonu gerekir)
- Geniş `_internal` coverage (~60 modül, ayrı kampanya)
- Otomatik tool-use loop (D0.2 mini-CNS'den sonra)
- Prompt experiments (A/B/canary/shadow — ürün kararı)

---

## 3. Kapsam (Scope)

### 3.1 In-Scope

| Alan | Detay |
|---|---|
| **Operasyonel güvenlik** | GitHub branch/tag protection, dar global git config, versioned `.githooks/`, upstream fix, workflow ayrıştırma |
| **Hijyen** | `.patch` arşivleme, PyPI classifier, exception swallowing fix, README SDK/MCP matrix, SECURITY.md, registry overclaim fix |
| **Ürünleşme min set** | `examples/hello-llm/`, memory güncellemesi, CHANGELOG kayıtları |
| **Faz 4 wiring** | Vector store → semantic_retrieval, secrets factory → LLM transport, extension loader → startup path, evidence robustness, agent coordination write path |
| **Test derinleşmesi** | evidence/writer, workspace.py, context_store.py coverage artışı; CLI subprocess + session concurrency testleri |

### 3.2 Out-of-Scope (bilinçli)

- Yeni LLM provider ekleme
- UI/dashboard geliştirme
- Yeni policy tipi tanımlama
- Mevcut governance API'nin breaking değişikliği (CNS olmadan)
- Rakip benchmark suite (v3.0.0+ için)
- Vision/audio provider implementasyonu (sadece registry'den çekme)
- Async/await refactor

### 3.3 Out-of-Plan (konu dışı)

- İşletme kararları (pricing, licensing)
- Repo'nun fork/transfer edilmesi
- Anthropic Codex API değişikliği

---

## 4. Hedefler & Başarı Kriterleri

### 4.1 SMART Hedefler

| # | Hedef | Ölçüm | Hedef değer | Deadline |
|---|---|---|---|---|
| G1 | Operasyonel kayıp riskini kapat | Main'e direct push ve force push imkansız | 0 ihlal | Preflight sonu |
| G2 | Yetim Faz 4 abstraction'larını bağla | Production code path'inde çağrılan abstraction sayısı | 5/5 (vector, secrets, extensions, evidence, agent_coord) | Tranş B sonu |
| G3 | Kritik modül coverage artır | evidence_writer %70+, workspace.py %80+, context_store.py %70+ | 3/3 hedef tutar | Tranş C sonu |
| G4 | Ürünleşme min sete ulaş | SECURITY.md + examples + classifier + README matrix | 4/4 | Tranş A sonu |
| G5 | Release cadence tutar | v2.2.0, v2.3.0, v3.0.0 tag'leri PyPI'da | 3/3 | 2026-06-30'a kadar |

### 4.2 Ürün Seviyesi Başarı Kriterleri

- ✅ Yeni kullanıcı 5 dakikada `examples/hello-llm/` çalıştırabilir (README komutları kopyala-yapıştır).
- ✅ `pip install ao-kernel[pgvector]` kurulumdan sonra `AoKernelClient` gerçekten pgvector'ı kullanır (vector store değilse log ile açıklar).
- ✅ MCP `ao_llm_call` kullanıcısı thin executor olduğunu README capability matrix'inde görür.
- ✅ Registry'deki bir capability flag'i `supported` ise kullanıcı o özelliği gerçekten kullanabilir. `unsupported` ise deny alır, silent fail yok.
- ✅ Main branch'ine kabul edilmiş PR dışında hiçbir commit girmez.

---

## 5. Paydaşlar & Roller (RACI)

| Rol | Sorumluluk | Kim |
|---|---|---|
| **Karar verici (Approver)** | Plan onayı, CNS kararları, release tag | Halil |
| **Uygulayıcı (Responsible)** | Kod yazımı, test, PR, dokümantasyon | Claude (assistant) |
| **Danışman (Consulted)** | Mimari karar review, itiraz | Codex (GPT-5.4) |
| **Bilgilendirilen (Informed)** | Release notes, CHANGELOG okuru | Son kullanıcılar (PyPI) |

**RACI matrisi özeti:** Halil onaylar, Claude yapar, Codex review eder, CHANGELOG son kullanıcıya bildirir.

---

## 6. Work Breakdown Structure (WBS)

### 6.1 Preflight — Faz 5 Gate (Tranş A'nın zorunlu ön-şartı)

Kod işine başlanmadan **tamamı** bitmiş olmalı.

#### P1 — Upstream Hijyeni ✅ TAMAMLANDI (2026-04-14, commit 8df56d0)
- **Süre:** 2 dk
- **Sorumlu:** Claude
- **Açıklama:** `claude/wizardly-euclid` branch'i şu an `origin/main` track ediyor (CNS-006 Q8 doğrulaması). Ya kendi remote branch'ine push edilir + upstream güncellenir, ya da upstream tamamen kaldırılır.
- **Uygulanan:** Branch `origin/claude/wizardly-euclid`'e push edildi, upstream kendi branch'ine çevrildi.
- **Kabul kriteri:** `git config branch.claude/wizardly-euclid.merge` → `refs/heads/claude/wizardly-euclid` ✅
- **Risk:** Bu adım yapılmadan `git pull` / `git push` main'i etkiler.
- **Rollback:** `git config branch.claude/wizardly-euclid.merge refs/heads/main` (upstream geri)

#### P2 — GitHub Branch Protection ✅ TAMAMLANDI (2026-04-14)
- **Süre:** 10 dk
- **Sorumlu:** Claude (gh CLI)
- **Açıklama:** `main` için protection rules aktifleştirilir.
- **Uygulanan:** `gh api PUT repos/Halildeu/ao-kernel/branches/main/protection` ile tüm kurallar aktif. `required_status_checks` null (P5 sonrası eklenecek). Doğrulama: `allow_force_pushes.enabled=false`, `enforce_admins.enabled=true`, `required_linear_history.enabled=false`.
- **Kurallar:**
  - ✅ Require PR before merging (1 approval)
  - ✅ Require status checks (test.yml — required list P5'te netleşir)
  - ✅ Require conversation resolution
  - ✅ Block force pushes
  - ✅ Block deletions
  - ✅ Include administrators
  - ❌ **Linear history AÇMA** (Codex Q2 itirazı — mevcut merge-PR workflow ile çelişir)
  - ⚠️ **Signed commits OPSİYONEL** (Codex Q3 — CI robot risk, ikinci fazda)
- **Kabul kriteri:** `gh api repos/Halildeu/ao-kernel/branches/main/protection` → 200 OK, JSON'da `required_pull_request_reviews.required_approving_review_count=1`, `allow_force_pushes.enabled=false`, `allow_deletions.enabled=false`, `enforce_admins.enabled=true`.
- **Risk:** Acil hotfix gerekirse disiplin sürtünmesi. → `hotfix/*` PR akışı (RCA: CNS-006 Q2).
- **Rollback:** `gh api --method DELETE repos/Halildeu/ao-kernel/branches/main/protection`

#### P3 — Dar Global Git Config ✅ TAMAMLANDI (2026-04-14)
- **Süre:** 3 dk
- **Sorumlu:** Claude
- **Açıklama:** SADECE güvenli-global ayarlar set edilir.
- **Uygulanan:** `rerere.enabled=true`, `gc.reflogExpire=365.days.ago`, `gc.reflogExpireUnreachable=365.days.ago`, `fetch.prune=true`, `push.followTags=true`. `pull.rebase` ve `push.default` global'e SET EDİLMEDİ.
- **Komutlar:**
  ```bash
  git config --global rerere.enabled true
  git config --global gc.reflogExpire "365.days.ago"
  git config --global gc.reflogExpireUnreachable "365.days.ago"
  git config --global fetch.prune true
  git config --global push.followTags true
  ```
- **Global'e GİRMEYECEK** (Codex Q5 itirazı):
  - ❌ `pull.rebase=true` — diğer repo'larda sürpriz rebase
  - ❌ `push.default=current` — sürpriz remote branch oluşturma
- **Kabul kriteri:** `git config --global --list | grep -E "rerere|reflogExpire|fetch\.prune|push\.followTags"` → 5 satır.
- **Risk:** Yok (geriye dönük uyumlu, sadece ekleme).

#### P4 — Versioned `.githooks/` ✅ TAMAMLANDI (2026-04-14, commit 91fbc84)
- **Süre:** 15 dk
- **Sorumlu:** Claude
- **Açıklama:** Repo içinde `.githooks/` dizini oluştur, `core.hooksPath=.githooks` ayarla. Hook'lar versioned, review edilebilir, worktree'ler arasında tutarlı (Codex Q6).
- **Uygulanan:** `.githooks/pre-commit` (secret/patch/100MB), `.githooks/pre-push` (main block, WIP warn), `.githooks/README.md`. `core.hooksPath=.githooks`. Smoke test: dummy secret → commit blocked as expected. Commit sırasında hook kendini çalıştırdı: `✓ pre-commit: OK`.
- **Hook'lar:**
  - `pre-commit`: (a) secret pattern blokla (`sk-[A-Za-z0-9]{20,}`, `api_key\s*=\s*["'].*["']`), (b) `.patch` ekleme uyarısı, (c) 100MB+ dosya blokla
  - `pre-push`: (a) direct-main push blokla (branch protection ikinci güvenlik), (b) `WIP`/`fixup!` commit varsa uyar
- **Kabul kriteri:**
  - `.githooks/pre-commit` ve `.githooks/pre-push` executable
  - `git config core.hooksPath` → `.githooks`
  - Test: dummy secret içeren commit bloke edilir, WIP push uyarısı gelir.
- **Risk:** `core.hooksPath` repo-local set edilirse worktree'lerde çalışmayabilir. → Çözüm: doc'da clone sonrası manuel set talimatı (`CONTRIBUTING.md`'de). `pre-commit` framework overkill (Codex Q6c).

#### P5 — Workflow Ayrıştırma ✅ TAMAMLANDI (2026-04-14, commit 7a3c129)
- **Süre:** 20 dk
- **Sorumlu:** Claude
- **Açıklama:** `test.yml`'i `lint`, `test-3.11`, `test-3.12`, `test-3.13`, `typecheck`, `coverage` ayrı job'lara ayır — required check seçilebilsin (Codex Q4).
- **Uygulanan:** 5 ayrı job (lint, test matrix, coverage, typecheck, extras-install). typecheck + extras-install `continue-on-error: true` (görünür ama required değil). Coverage gate %70 korundu. YAML syntax doğrulandı (`python3 -c "import yaml"`).
- **Branch protection required list:**
  - ✅ `lint`, `test-3.11`, `test-3.12`, `test-3.13`, `coverage`
  - ⚠️ `typecheck` (mypy) — **required DEĞİL** (hâlâ `|| true` varsayımı, görünür olsun ama blocker olmasın — CNS-006 Q4)
- **Kabul kriteri:** CI'da bir PR açılınca yukarıdaki job isimleri ayrı ayrı görünür. Required list'e eklenince bir başarısızlık merge'ü blokluyor.
- **Risk:** Job ayrımı test süresini uzatır (paralel çalışır ama setup overhead). → Ölçümle kabul et, gerekirse geri döndür.
- **Rollback:** `git revert` ile eski `test.yml`'e dön.

#### P6 — Tag Protection ✅ TAMAMLANDI (2026-04-14)
- **Süre:** 3 dk
- **Sorumlu:** Claude
- **Açıklama:** `v*` pattern için tag silme/force-update yasağı (Codex Q7 orta-yüksek öncelik).
- **Uygulanan:** Ruleset 15043973 (`gh api POST rulesets`) — `refs/tags/v*` için `deletion`, `non_fast_forward`, `update` rules, `bypass_actors: []`, `current_user_can_bypass: never`. Supply chain güvenliği aktif.
- **Kabul kriteri:** `gh api repos/Halildeu/ao-kernel/tags/protection` → `v*` rule görünür.
- **Risk:** Yanlış tag atılırsa silmek zor. → Çözüm: tag atmadan önce `git tag --verify` disiplini.

#### P7 — `.archive/patches/` Taşı (Codex Q9 önerisi) ✅ TAMAMLANDI (2026-04-14)
- **Süre:** 2 dk
- **Sorumlu:** Claude
- **Açıklama:** Kökteki 20 `.patch` dosyası silinmez, `.archive/patches/` altına taşınır (psikolojik safety net).
- **Ek:** `.gitignore`'a `/*.patch` ekle (yeni backup'lar köke düşmesin).
- **Uygulanan:** 20 dosya `git mv` ile taşındı (rename olarak tracked), `.gitignore`'a `/*.patch` eklendi (yalnızca root), `.archive/patches/README.md` yazıldı.

### 6.2 Tranş A — Hijyen & Honesty (v2.2.0 hedef)

Preflight bittikten sonra başlar. Her adım ayrı commit, bir PR içinde toplanır.

#### A1 — `.patch` Arşivleme
- P7 ile birleştirildi (yukarıda). İşaretleme: ✅ (Preflight'a taşındı).

#### A2 — PyPI Classifier `Alpha → Beta`
- **Süre:** 5 dk
- **Dosya:** `pyproject.toml`
- **Kabul kriteri:** `Development Status :: 4 - Beta`
- **DoD:** Classifier değişti, commit atıldı, CI yeşil.
- **Risk:** PyPI'daki mevcut v2.1.1 paketi güncellenemez (published) → v2.2.0 ile yayınlanacak.

#### A3 — Exception Swallowing Fix
- **Süre:** 30 dk
- **Dosyalar:**
  - `client.py:388-389` (non-stream evidence)
  - `client.py:413-414` (eval scorecard)
  - `client.py:503-513` (stream evidence — CNS-005 R1 genişletilmiş kapsam)
  - `context/context_compiler.py:147-148` (telemetry — debug seviyesi kalsın, silent OK)
- **Pattern:** `except Exception: pass` → `except Exception as e: logger.warning("evidence skipped", exc_info=e)` (telemetry için `logger.debug`).
- **Kabul kriteri:** Yeni unit test (`test_client_swallow_fix.py`): yapay exception fırlat, log'da warning görünmesini assert et.
- **DoD:** Test eklendi, yeşil. Coverage etkisi pozitif.
- **Risk:** Log noise artışı. → `logger.warning` sadece evidence/eval için, telemetry `debug`.

#### A4 — README SDK↔MCP Capability Matrix
- **Süre:** 20 dk
- **Dosya:** `README.md`
- **Açıklama:** Kod docstring'ine dokunma (zaten var — Codex itirazı). README'ye yeni bölüm:
  ```
  ## SDK vs MCP — Which one?
  
  | Feature | AoKernelClient (SDK) | MCP ao_llm_call |
  |---|---|---|
  | Route resolution | ✅ | ✅ |
  | Capability check | ✅ | ✅ (via build) |
  | Context injection | ✅ | ❌ |
  | Decision extraction | ✅ | ❌ |
  | Eval scorecard | ✅ | ❌ |
  | Evidence trail | ✅ (via post-processor) | ❌ |
  | Telemetry | ✅ | ❌ |
  ```
- **Kabul kriteri:** README'de matrix + "Use MCP when..." 2-3 satırlık guide.
- **DoD:** Markdown preview'da tablo düzgün render olur, README `wc -l` artmış.

#### A5 — SECURITY.md
- **Süre:** 45 dk
- **Dosya:** `SECURITY.md` (yeni)
- **İçerik:**
  - Responsible disclosure (iletişim kanalı, beklenen yanıt süresi)
  - Secrets best practices (env-var kullanımı, log'lara sızdırmama)
  - Policy engine güvenlik modeli özet (fail-closed, D8)
  - Bilinen kısıtlar (MCP thin executor, evidence opt-in, vb.)
  - Supported versions (v2.x aktif, v1.x EOL)
- **Kabul kriteri:** GitHub otomatik "Security policy" sekmesinde görünür.

#### A6 — `examples/hello-llm/`
- **Süre:** 1-1.5 saat
- **Dosyalar:**
  - `examples/hello-llm/README.md` — 5-dakikada çalıştırma talimatı
  - `examples/hello-llm/main.py` — workspace init + OpenAI provider + basit llm_call
  - `examples/hello-llm/requirements.txt` — `ao-kernel[llm]`
  - `examples/hello-llm/.env.example` — `OPENAI_API_KEY=` placeholder
- **Kabul kriteri:** Claude clean ortamda `pip install -r requirements.txt && python main.py` çalıştırdığında success mesajı. `.env` set olmamışsa anlaşılır hata.
- **DoD:** README'de `examples/` linki var.

#### A7 — Registry Overclaim Fix (CNS-005 R2)
- **Süre:** 30 dk
- **Dosya:** `ao_kernel/defaults/registry/provider_capability_registry.v1.json`
- **Açıklama:** Tüm provider'larda `vision`, `audio`, `code_agentic`, `structured_output` flag'lerini `supported` → `unsupported` yap (gerçekten implement edilmemişler için).
- **Kabul kriteri:** `grep -c '"vision": *"supported"' defaults/registry/*.json` → 0. Kullanıcı "vision provider" isteyip hata alırsa silent fail değil explicit deny döner.
- **DoD:** Yeni test: registry'deki flag kullanıcı isteğinde `unsupported` → `PolicyViolation` raise.

#### A8 — Memory Güncelleme
- **Süre:** 15 dk
- **Dosyalar:** `project_origin.md`, `project_p3_candidates.md`, `feedback_codex_consultations.md`
- **Değişiklikler:**
  - `project_origin.md`: "Faz 4 PR merge, wiring kaldı" notu ekle
  - `project_p3_candidates.md`: "4.1-4.3 wiring borcu, Tranş B'de bağlanacak"
  - `feedback_codex_consultations.md`: CNS-005 + CNS-006 verdict + kabul itirazları ekle
- **Kabul kriteri:** Memory dosyaları güncel, `MEMORY.md` index değişmedi (sadece hook'lar).

### 6.3 Tranş B — Faz 4 Wiring (v2.3.0 hedef)

Tranş A tamamlanıp v2.2.0 tag'lendikten sonra başlar. Her adım potansiyel mini-CNS gerektirir.

#### B1 — Vector Store Integration
- **Süre:** 3-4 saat
- **Ön-şart:** Mini-CNS (CNS-005 Soru 3 tasarım kararı) — backend seçim mekanizması.
- **Kapsam:** `semantic_retrieval.py` içinde `VectorStoreBackend` parametre olarak inject edilir, default `InMemoryVectorStore`. `pgvector` opt-in (env flag veya provider config).
- **DoD:**
  - `semantic_retrieval.py` `VectorStoreBackend` kullanır
  - `pgvector` backend ile integration test (Docker compose ile pgvector container)
  - `InMemoryVectorStore` default davranış değişmez (backward compatible)
  - Coverage: `vector_store.py` %80+, `vector_store_pgvector.py` %60+

#### B2 — Secrets Factory → LLM Transport
- **Süre:** 4-5 saat
- **Ön-şart:** CNS-005 D0.3 (secrets migration safety). Dual-read pattern: factory varsa factory, yoksa `os.getenv` fallback.
- **Kapsam:** `_internal/prj_kernel_api/llm_executor.py` (veya transport) içinde API key çözümleme `create_provider()` üzerinden. Geriye dönük uyumlu.
- **DoD:**
  - Mevcut `OPENAI_API_KEY` env-var workflow bozulmaz
  - `AO_KERNEL_SECRETS_PROVIDER=vault_stub` ile Vault stub backend'e geçiş çalışır
  - Integration test: factory tüm provider tipleri için API key çözebiliyor

#### B3 — Extension Loader Startup Integration
- **Süre:** 3 saat
- **Ön-şart:** Mini-CNS — lazy vs eager loading, activation dispatch tasarımı.
- **Kapsam:** `AoKernelClient.__init__` veya workspace init'te `ExtensionRegistry.load_from_defaults()` çağrılır. Activation dispatch için yeni bir entry point tanımı.
- **DoD:**
  - Client init'ten sonra `client.extensions` erişilebilir
  - En az 1 örnek extension (hello-extension) gerçekten aktive olur
  - Coverage: `extensions/loader.py` %85+

#### B4 — Evidence Writer Robustness
- **Süre:** 2 saat
- **Kapsam:**
  - `llm_post_processors` içinde evidence yazımı sessiz swallow yerine structured warning
  - MCP tool'ları `ao_llm_call`, `ao_policy_check`, `ao_quality_gate` için evidence yazımı eklenir (şu an yok)
- **DoD:**
  - MCP tool call sonrası `.ao/evidence/*.jsonl` dosyasında kayıt görünür
  - Test: corruption/write-fail durumunda warning log, execution devam eder

#### B5 — Agent Coordination Write Path Expose
- **Süre:** 2 saat
- **Ön-şart:** Mini-CNS — public API mı internal mı?
- **Kapsam:** `AoKernelClient.record_decision()`, `AoKernelClient.finalize_session()` public metodları.
- **DoD:**
  - Public API olarak expose edilmiş
  - Multi-agent E2E test: iki AoKernelClient instance'ı aynı canonical store'a yazar, stale detection çalışır

### 6.4 Tranş C — Coverage & Test (v3.0.0 hazırlık)

Tranş B tamamlanıp v2.3.0 tag'lendikten sonra başlar.

#### C2 — `_internal/evidence/writer.py` Coverage %28 → %70
- **Süre:** 2 saat
- **DoD:** Coverage raporunda modül `>= 70%` branch, edge case testleri (corrupt file, disk full, concurrent write) eklenmiş.

#### C3 — `workspace.py` Coverage %46 → %80
- **Süre:** 1.5 saat
- **DoD:** Workspace resolution edge case testleri (CWD değişimi, `.ao` hiyerarşisi, symlink, izin yok).

#### C4 — `_internal/session/context_store.py` Coverage %51 → %70
- **Süre:** 2 saat
- **DoD:** 160 satır miss'in %50'sini kapatan testler.

#### C5 — CLI Subprocess + Session Concurrency
- **Süre:** 3 saat
- **Dosyalar:** `tests/test_cli_subprocess.py`, `tests/test_session_concurrency.py` (yeni)
- **DoD:**
  - CLI: `subprocess.run("ao-kernel init")` çalışıp `.ao/` oluşturulur, çıkış kodu 0
  - Concurrency: 5 thread eşzamanlı `AoKernelClient.llm_call` → atomik write, bozulma yok

> **C1** (vision/audio karar) A7'ye taşındı — burada yok.

---

## 7. Bağımlılıklar & Sıralama

### 7.1 Görev Bağımlılık Grafiği (lite)

```
Preflight (P1-P7) — tümü sırasız ama "bağımsız sıra"
  P1 (upstream fix)  ────┐
  P2 (branch protect) ──┤
  P3 (git config)    ──┼──→ Tranş A başlar
  P4 (hooks)         ──┤
  P5 (workflow split)── ┤
  P6 (tag protect)   ──┘
  P7 (.patch archive)─┘

Tranş A (v2.2.0)
  A2 → A8 paralel olabilir (dosyalar bağımsız)
  A6 (examples) → A5 (SECURITY'de link) kısmen bağlı
  Tüm A* → PR → v2.2.0 tag

Tranş B (v2.3.0)  [v2.2.0 tag'den sonra]
  B1 ← Mini-CNS-007 (vector design)
  B2 ← CNS-005 D0.3
  B3 ← Mini-CNS-008 (extension activation)
  B4 paralel (bağımsız)
  B5 ← Mini-CNS-009 (public API)
  Tüm B* → PR → v2.3.0 tag

Tranş C (v3.0.0)
  C2, C3, C4, C5 paralel
  Tüm C* + uzun vadeli kalan işler → v3.0.0 tag
```

### 7.2 Kritik Yol

**Kritik yol:** P1 → P2 → P5 → A3 → A6 → A7 → A8 → v2.2.0 tag
Çünkü:
- P1 olmadan herhangi bir push riskli
- P2 olmadan preflight tamamlanmaz
- P5 required checks'i netleştirir
- A3 evidence integrity (core değer)
- A6 examples credibility
- A7 silent false-advertise riskini kapatır
- A8 memory güncel olmadan sonraki oturum yanlış bilgi alır

---

## 8. Risk Register

| # | Risk | Etki | Olasılık | Kategori | Mitigation | Owner |
|---|------|------|----------|----------|------------|-------|
| R1 | Branch protection acil hotfix'i engeller | Orta | Düşük | Operasyonel | `hotfix/*` PR fast-track, temporary admin bypass ile audit trail | Halil |
| R2 | `pre-commit` hook secret pattern false positive | Düşük | Orta | DX | Regex test suite, `--no-verify` emergency (dokümante) | Claude |
| R3 | B1/B2 breaking change (secrets/vector) | Yüksek | Orta | Teknik | Dual-read pattern, feature flag, deprecation warning | Claude |
| R4 | Codex istişaresi yanıt veremez (capacity) | Düşük | Orta | Süreç | Retry + fallback: kullanıcıyla direkt karar | Claude |
| R5 | Tranş B uzun sürer, release trenisi kayar | Orta | Orta | Süreç | Her B* bağımsız merge, v2.3.0 kısmi release opsiyonu | Halil |
| R6 | Registry overclaim fix mevcut kullanıcıyı etkiler | Düşük | Düşük | Teknik | CHANGELOG'da breaking not, fallback mode | Claude |
| R7 | workflow ayrıştırma CI süresini artırır | Düşük | Yüksek | CI | Paralel job konfigürasyonu, metric izleme | Claude |
| R8 | `.githooks/` clone sonrası manuel set gerekir | Düşük | Yüksek | DX | `CONTRIBUTING.md`'de talimat, `make setup` script | Claude |
| R9 | Memory güncellemesi yanlış commit edilir (push'a gider) | Düşük | Düşük | Güvenlik | Memory `~/.claude/projects/` içinde, repo'dan bağımsız | — |
| R10 | v2.2.0 tag sonrası kritik bug bulunur | Orta | Düşük | Release | Patch release (v2.2.1) planı, yedek rollback | Halil |

### 8.1 Risk Heat Map

```
Olasılık ↑
Yüksek     |          R7, R8     |                    |
Orta       |          R2         | R3, R4, R5         |
Düşük      | R6, R9              | R1, R10            |
           |   Düşük             | Orta    | Yüksek →  Etki
```

---

## 9. Definition of Done (DoD)

### 9.1 Adım Seviye DoD

Bir adım "done" sayılır ancak **tüm** şu koşullar sağlanırsa:
- [ ] Kod değişikliği yapıldı VEYA "no-code change" (config, doc) doğrulandı
- [ ] Unit test eklendi/güncellendi (test edilebilir değişiklik için)
- [ ] Test suite yeşil (`pytest -x`)
- [ ] Lint yeşil (`ruff check`)
- [ ] Type check geçer (`mypy --ignore-missing-imports`, hata `|| true` ile maskelendiği için kritik hatalar görünür)
- [ ] Coverage etkisi kontrol edildi (düşmez, hedef modül için artar)
- [ ] İlgili CHANGELOG girdisi yazıldı (`Unreleased` altında)
- [ ] Commit mesajı Conventional Commits formatında (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`)

### 9.2 Tranş Seviye DoD

Bir tranş (Preflight / A / B / C) "done" sayılır ancak **tüm** adımları done **ve**:
- [ ] PR açılmış, review yapılmış (Codex veya self-review)
- [ ] PR'da Tranş özeti + başarı kriterleri listesi
- [ ] main'e merge edilmiş (branch protection PR required zorunlu tutar)
- [ ] Memory güncellemesi commit edilmiş
- [ ] CHANGELOG `Unreleased` → yeni versiyon başlığı taşındı
- [ ] Versiyon bump (`pyproject.toml`) yapıldı

### 9.3 Release Seviye DoD

Bir release (v2.2.0 / v2.3.0 / v3.0.0) "tag'lenmeye hazır" sayılır ancak:
- [ ] İlgili tranş(lar) done
- [ ] `pyproject.toml` versiyon doğru (`2.2.0` vb.)
- [ ] CHANGELOG başlığı `## [2.2.0] - 2026-MM-DD`
- [ ] README'de breaking değişiklik notu (varsa)
- [ ] Tüm testler yeşil (754 → hedeflenen test sayısı)
- [ ] Coverage gate geçer (%70 min)
- [ ] Local `pip install -e .` ve `ao-kernel doctor` temiz
- [ ] `examples/hello-llm/` çalışır durumda (A6'dan sonra)
- [ ] `git tag v2.2.0 && git push origin v2.2.0` → publish.yml PyPI'ya yollar
- [ ] PyPI'da versiyon görünür (https://pypi.org/project/ao-kernel/)
- [ ] GitHub release notes yazıldı

---

## 10. Test Stratejisi

### 10.1 Test Piramidi Hedefi (Faz 5 sonu)

```
           /\
          /E2E\          Tranş C'de +5 test (examples/, CLI subprocess)
         /------\
        /Integ.\         Tranş B'de +15 test (vector, secrets, extension)
       /--------\
      /   Unit   \       Tranş A'da +10, Tranş C'de +40 test
     /------------\
    /  Static/AST  \     Preflight'ta hook-level check'ler
   /----------------\
```

### 10.2 Test Kategorileri

| Kategori | Hedef | Araç | Min coverage |
|---|---|---|---|
| Unit | Her public fonksiyon | pytest | %85 |
| Integration | Pipeline'ların uçtan uca akışı | pytest + pytest-asyncio (gerekirse) | %70 |
| Regression | Bilinen bug'lar için guard test | pytest `@pytest.mark.regression` | N/A (her bug için 1 test) |
| Smoke | `examples/` gerçekten çalışır | `subprocess.run` ile | 1 pass |
| Concurrency | Thread-safe garantileri | `threading.Thread` fixture | C5'te eklenir |
| Mutation | AST gate + değişken test kalitesi | `mutmut` (opsiyonel, v3.0.0+) | — |
| Chaos | Corrupt state, disk full, partial write | `test_chaos.py` genişletme | C2'de artar |

### 10.3 Test Ekleme Kuralı

Her değişiklik için **en az 1 test** şartı. İstisnalar:
- Pure doc değişikliği (README, CHANGELOG)
- Pure config değişikliği (classifier, gitignore)
- Pure rename/dead code removal (mevcut test değişikliğe kapsam yeter)

---

## 11. Release Plan

### 11.1 v2.2.0 — "Safety & Hygiene" (Preflight + Tranş A)

- **Hedef tarih:** Preflight + Tranş A onay sonrası + ~1-2 oturum
- **İçerik:** Operasyonel güvenlik + ürünleşme min set + hijyen
- **Breaking değişiklik:** Registry `vision/audio/code_agentic` → `unsupported` (A7) — **not as breaking** çünkü silent fail → explicit deny. CHANGELOG'da "Behavior change" bölümü.
- **Rollback:** `v2.1.1` üzerinde `git tag -d v2.2.0` + PyPI yank (gerçekten kritik bug varsa)

### 11.2 v2.3.0 — "Integration" (Tranş B)

- **Hedef tarih:** v2.2.0 + 2-3 oturum (mini-CNS'ler dahil)
- **İçerik:** Faz 4 abstraction'ları gerçekten tüketilir
- **Breaking değişiklik:** B2 secrets factory default değişimi olabilir — **dual-read** ile geriye dönük uyumlu tutulacak
- **Migration notu:** CHANGELOG'da "How to opt-in pgvector", "How to enable Vault provider" bölümleri

### 11.3 v3.0.0 — "Test Depth" (Tranş C + uzun vadeli kalan)

- **Hedef tarih:** v2.3.0 + 2-4 oturum
- **İçerik:** Coverage artışı + uzun vadeli işlerin bir kısmı (vision impl, auto tool-use loop — bunlar ayrı CNS'ler gerektirir)
- **Breaking değişiklik:** Async API eklenirse (D9 revizyonu) — major version gerçekçi nedeni

---

## 12. KPIs & Metrics

### 12.1 İzlenecek Göstergeler

| Metrik | Baseline (dc25cd2) | v2.2.0 hedef | v2.3.0 hedef | v3.0.0 hedef |
|---|---|---|---|---|
| Toplam test | 754 | 770+ | 800+ | 850+ |
| Branch coverage | 77% | 78% | 80% | 82% |
| `_internal/evidence/writer.py` cov | 28% | 28% | 45% | 70% |
| `workspace.py` cov | 46% | 46% | 55% | 80% |
| `context_store.py` cov | 51% | 51% | 60% | 70% |
| Ürüne bağlı yetim abstraction | 4 | 4 | 0 | 0 |
| GitHub branch protection | ❌ | ✅ | ✅ | ✅ |
| CI job sayısı | 1 (monolitik) | 5 (ayrık) | 5 | 6 (typecheck blocking) |
| `examples/` projesi | 0 | 1 | 1-2 | 3+ |
| PyPI classifier | Alpha | Beta | Beta | Production |
| Registry flag tutarlılığı | 4/10 overclaim | 0/10 | 0/10 | 0/10 |
| Ortalama PR review süresi | N/A | — | — | — |

### 12.2 Ölçüm Mekanizması

- **Her tranş sonunda:** `pytest --cov` çıktısı `docs/metrics/vX.Y.Z-coverage.txt`'e kaydedilir
- **Her release öncesi:** `docs/metrics/release-checklist.md` otomasyonu (manuel için)
- **Haftalık (opsiyonel):** Codex ile progress review CNS

---

## 13. Rollback / Contingency Plan

### 13.1 Adım Seviye Rollback

Her adımın bireysel rollback'i var (tabloda `Rollback` alanında).

### 13.2 Tranş Seviye Rollback

- **Tranş A rollback:** `git revert <merge-commit>` → v2.1.1 davranışına dön. PyPI'dan yank yap.
- **Tranş B rollback:** Daha karmaşık (B1/B2 API yüzeyi değiştirir). Dual-read pattern'i sayesinde feature flag ile opt-out: `AO_KERNEL_LEGACY_SECRETS=1`.
- **Tranş C rollback:** Pure test ekleme, rollback'e gerek yok (tests coverage düşürmez).

### 13.3 Acil Durum Prosedürü

Eğer preflight sonrası kritik bug bulunursa:
1. `hotfix/<bug-name>` branch aç
2. PR hızlı onay (Halil direkt approve + Codex short review)
3. Merge sonrası `v2.2.1` patch release
4. Audit trail: hotfix sebebi CHANGELOG'da

---

## 14. Communication & Approval Gates

### 14.1 Onay Noktaları (Gates)

| Gate | Onay veren | Ne onaylanır | Sonraki adım |
|---|---|---|---|
| G0 | Halil | Bu plan dosyası | Preflight P1'e başla |
| G1 | Halil | Preflight sonu (P7 bitti) ✅ 2026-04-14 merge d9e86be | Tranş A başla |
| G2 | Halil + Codex (CNS-opsiyonel) | Tranş A PR hazır | Merge + v2.2.0 tag |
| G3 | Halil | v2.2.0 release sonrası | Tranş B başla |
| G4 | Codex (CNS-007) | B1 tasarımı | B1 implementasyonu |
| G5 | Codex (CNS-008) | B3 tasarımı | B3 implementasyonu |
| G6 | Codex (CNS-009) | B5 API kararı | B5 implementasyonu |
| G7 | Halil + Codex | Tranş B PR hazır | Merge + v2.3.0 tag |
| G8 | Halil | Tranş C başla onayı | Tranş C |
| G9 | Halil | v3.0.0 release | Tag + PyPI |

### 14.2 Codex İstişareleri (planlı)

| ID | Konu | Tranş | Durum |
|---|---|---|---|
| CNS-20260414-005 | Plan review | Faz 5 | ✅ Answered (Verdict D) |
| CNS-20260414-006 | A0 safety net | Preflight | ✅ Answered (Verdict C) |
| CNS-2026MMDD-007 | Vector store design | B1 | Planlı |
| CNS-2026MMDD-008 | Extension activation | B3 | Planlı |
| CNS-2026MMDD-009 | Agent coord public API | B5 | Planlı |
| CNS-2026MMDD-010 | v3.0.0 scope (vision/async) | C ötesi | Planlı (uzun vadeli) |

### 14.3 Memory Kaydı

Her CNS sonrası `feedback_codex_consultations.md` güncellenir (CLAUDE.md §15 kural 3).

---

## 15. Assumptions & Constraints

### 15.1 Varsayımlar

- Halil tam otorite sahibi, onay süreci tek katmanlı
- GitHub hesabı yetkisi yeterli (branch protection, rulesets, actions)
- Codex erişimi (`codex exec`) çalışıyor — capacity hatası olursa retry
- PyPI trusted publishing yapılandırması v2.1.1'den beri çalışıyor
- Mevcut 754 test pytest ile yeşil başlıyor (re-run ile doğrula)
- Worktree disiplini sürer (wizardly-euclid upstream düzeltildikten sonra)

### 15.2 Kısıtlar

- **Python >= 3.11** (pyproject.toml — değiştirilmez)
- **Core dep `jsonschema` dışında zorunlu bağımlılık eklenmez** (CLAUDE.md §12)
- **Dosya bütçesi < 800 satır** (D4)
- **Coverage gate %70 min** — düşürülmez, ancak artırılabilir
- **Breaking değişiklik yalnızca major version** — v2.x içinde olmaz (B2 dual-read mecburi nedeni)
- **Türkçe kullanıcı iletişimi** (CLAUDE.md §16) — dokümantasyon Türkçe, kod/commit İngilizce
- **Codex istişaresi zorunlu** mimari kararlarda (CLAUDE.md §15 kural 1)

---

## 16. Change Management

### 16.1 Plan Değişikliği Süreci

Bu plan değişirse:
1. Değişikliğin sebebi (yeni bulgu, CNS sonucu, kullanıcı kararı) yazılır
2. `Change Log` bölümüne eklenir (aşağıda)
3. Plan versiyonu bump edilir (v1.0 → v1.1)
4. Etkilenen gate/DoD/risk güncellenir

### 16.2 Change Log

| Tarih | Plan v | Değişiklik | Kaynak |
|---|---|---|---|
| 2026-04-14 | v1.0 | İlk taslak oluşturuldu | CNS-005 + CNS-006 sonuçları |
| 2026-04-14 | v1.1 | Preflight tamamlandı ve v2.2.0-track açıldı. Yol üstünde kazanıldı: mypy 131→0, typecheck gerçek gate, client.save_checkpoint/resume_checkpoint real-bug fix, 18 dead __init__.py sildi. G1 merged @ d9e86be. | PR #56 merge |

---

## 17. Appendix

### 17.1 Referanslar

- **CLAUDE.md** — mimari kararlar (D1-D14), governance ilkeleri
- **Memory** — `~/.claude/projects/.../memory/` dizini
- **CNS geçmişi** — `.ao/consultations/requests/` + `responses/`
- **Önceki plan** — `.claude/plans/master-plan.md` (Faz 0-4, tamamlandı)
- **GitHub repo** — https://github.com/Halildeu/ao-kernel
- **PyPI paket** — https://pypi.org/project/ao-kernel/

### 17.2 CNS Özeti

- **CNS-20260414-005** (Verdict D): Faz 5 planı yön doğru, D0 gerekli. Claude'un 2 iddiası çürütüldü (`EvidenceWriter` doğrudan çağrı + thin executor uyarısı).
- **CNS-20260414-006** (Verdict C): A0 ayrı tranche değil, Tranş A preflight. 3 Claude önerisi çürütüldü (linear history, `pull.rebase` global, `push.default` global). 1 kritik bulgu (wizardly-euclid upstream hatası).

### 17.3 Terminoloji

- **Tranş** (İng. *tranche*) — Bağımsız merge edilebilir iş paketi, bir release'e karşılık gelir
- **Preflight** — Kod işi başlamadan önce zorunlu operasyonel/güvenlik hazırlığı
- **Yetim abstraction** — Kod seviyesinde kuruldu ama production code path'inde tüketilmiyor
- **DoD** — Definition of Done — iş tamamlandı sayılmasının koşulları
- **CNS** — Consultation (Codex istişare dosyası)

### 17.4 Sembol Açıklamaları

- ✅ Tamamlandı
- ⏳ Devam ediyor
- ⚠️ Dikkat / karar bekliyor
- ❌ Yapılmayacak / reddedildi
- 🔴 Blocker
- 🟡 Önemli ama blocker değil
- 🟢 Nice-to-have

---

## 18. Approval

- [x] **G0 onayı:** Halil planı onayladı
- Tarih: 2026-04-14
- Notlar: Plan v1.0 bu haliyle kabul. Preflight P1'den başlanacak.

> Onaylandı — **Preflight P1'den** başlanıyor. Her tamamlanan adım bu dosyada checkbox olarak işaretlenir.

**Plan sonu.**
