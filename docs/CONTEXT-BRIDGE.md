# Context Doc-Bridge

`.md`-tabanlı bağlam yöneten bir repo'nun (AGENTS.md, ADR'lar, `current-state`,
karar kayıtları) içeriğini **governed canonical store**'a alır ve oradan kısa,
provenance'lı bir **markdown context packet** üretir. Packet herhangi bir AI'a
(Claude / Codex / Mavis) enjekte edilebilir.

> Tasarım = cross-AI plan-time mutabakatı (Codex AGREE): **governed JSON store**
> (query / freshness / provenance / tier) + ondan türetilen **kısa markdown
> packet** (yalnız fresh + high-confidence; tam dump DEĞİL). Store tek doğruluk
> kaynağıdır; packet türetilmiştir ve fail-closed'dur.

## Neden

Multi-AI bir ekipte her AI kendi bağlam dosyasını okur (Claude → CLAUDE.md,
Codex/OpenCode → AGENTS.md). Aynı "truth" birden çok dosyaya dağılınca **drift**
oluşur. Doc-bridge structured truth'u (ADR / current-state / kararlar) tek
governed store'da toplar; her AI **aynı** packet'i okur → drift biter, freshness
+ provenance + tier governed olur.

## Kullanım

### SDK

```python
from ao_kernel.context.doc_bridge import ingest_docs, render_context_packet

report = ingest_docs("/path/to/repo")          # root = repo = workspace
print(report.ingested, report.by_type)

packet = render_context_packet("/path/to/repo")  # kısa markdown packet
```

İki fonksiyon da ilk argüman olarak **workspace root**'u (`.ao` konumu) alır.
Farklı bir ağacı taramak için (örn. bir repo'yu read-only ayrı workspace'e almak)
`repo_root=` geçin:

```python
ingest_docs("/tmp/ws", repo_root="/path/to/repo")          # repo read-only kalır
render_context_packet("/tmp/ws", repo_root="/path/to/repo")
```

### CLI

```bash
ao-kernel context ingest                       # cwd'yi tara, .ao store'a yaz
ao-kernel context ingest --repo /path --output json
ao-kernel context packet                       # default packet (conf>=0.7)
ao-kernel context packet --include-doc-claims --min-conf 0.5
ao-kernel context packet --mapping custom-mapping.json
```

## Mapping

Çıkarım declarative, schema-validated bir mapping ile sürülür. Bundled default
(`ao_kernel/defaults/context_bridge/doc_mapping.default.v1.json`) yaygın
conventions'ı kapsar ve tamamen override edilebilir. Şema:
`ao_kernel/defaults/schemas/context-doc-bridge-mapping.schema.v1.json`.

Her kural:

| Alan | Açıklama |
|---|---|
| `mapping_id` | Kuralın stabil kimliği (provenance + re-verify için) |
| `glob` | Repo-root'a göre desen (mutlak / `..` / symlink reddedilir) |
| `type` | `rule` \| `decision` \| `fact` (packet bölümlemesi) |
| `tier` | `repo_canonical` \| `canonical_doc` \| `doc_claim` |
| `key_template` | `{stem}` / `{num}` / `{index}` ile deterministic key |
| `value_strategy` | `first_heading` \| `status_line` \| `section_headings` |
| `confidence` / `status_map` | Sabit confidence veya status→confidence eşlemesi |
| `collision_policy` | `strict` \| `supersede` \| `update_same_source` |

## Fail-closed garantiler

- **Stale / drift / silinmiş kaynak**: packet render anında kaynak dosya
  re-hash edilir ve mapping kuralı tekrar uygulanır. Dosya silinmişse veya aynı
  key + `value_hash` üretilemiyorsa item packet'e **GİRMEZ**.
- **Secret koruması**: secret-benzeri token içeren değer ingest **edilmez**
  (redakte edilip saklanmaz); diagnostic'te raporlanır.
- **`doc_claim` opt-in**: doküman-iddiası (`current-state` "done/green" gibi)
  release truth değildir; default packet'e girmez. `--include-doc-claims` ile
  `UNVERIFIED` etiketiyle görünür.
- **Authority sınırı**: packet header'ı net belirtir — bu **source-derived
  context'tir, release authority DEĞİLDİR**; `support_widening`,
  `production_platform_claim`, `live_adapter_execution` guard flag'lerini
  **override edemez**.
- **Atomic**: tüm batch tek CAS revision altında yazılır (partial-write yok).

## Multi-AI wiring

`.md` giriş dosyaları (AGENTS.md / CLAUDE.md) **kalır** — onlar session-bootstrap
sözleşmeleridir. Doc-bridge altta paylaşılan governed truth katmanını besler:

```
AGENTS.md + context-priority + current-state + ADR + decisions
        │  ao-kernel context ingest (read-only)
        ▼
   governed store (.ao/)  ── tek SSOT (provenance + freshness + tier)
        │  ao-kernel context packet
   Claude · Codex · Mavis   (üçü de AYNI fresh+high-confidence packet'i okur)
```

## Sınırlar (v1)

- Kaynak repo **read-only** okunur; bridge repoya yazmaz (`.ao` workspace hariç).
- `compile_context` (LLM-call pipeline), MCP yüzeyi ve 3 guard flag **değişmez**.
- MCP `ao_memory_read`'in packet döndürmesi v1 kapsamı dışındadır (gelecek).
