# PB-6.4a — Support Mapping Hardening

**Status:** Active  
**Date:** 2026-04-23  
**Parent:** `PB-6.4`  
**Issue:** [#265](https://github.com/Halildeu/ao-kernel/issues/265)

## Amaç

`doctor` truth sınıfları (`runtime_backed`, `contract_only`, `quarantined`)
ile support boundary doküman dilini tek anlamlı hale getirmek.

## Kapsam

1. `docs/SUPPORT-BOUNDARY.md` mapping tablosu
2. `docs/PUBLIC-BETA.md` truth-tier yorum kuralı
3. `tests/test_doctor_cmd.py` structured report truth payload parity assert'leri
4. status SSOT'ta aktif slice/issue hizası

## Kapsam Dışı

1. runtime handler/policy davranışı değiştirmek
2. support widening implementation açmak
3. write-side lane promotion yapmak

## DoD

1. truth tier -> support yorumu iki dokümanda da aynı
2. `doctor` structured report testi `contract_only` ve id-count parity'yi pinler
3. aktif issue + status dosyası aynı slice'ı gösterir

## Kanıt

1. `pytest tests/test_doctor_cmd.py tests/test_extension_loader.py -q`
2. `python3 -m ao_kernel doctor`
