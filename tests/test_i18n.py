"""Tests for ao_kernel.i18n — CLI message localization."""

from __future__ import annotations

from ao_kernel.i18n import msg, reset_locale


class TestDefaultEnglish:
    def setup_method(self):
        reset_locale()

    def test_workspace_created_english(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        reset_locale()
        result = msg("workspace_created", path="/tmp/test")
        assert "Workspace created: /tmp/test" == result

    def test_error_no_workspace_english(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        reset_locale()
        result = msg("error_no_workspace")
        assert "No workspace found" in result
        assert "ao-kernel init" in result


class TestTurkishOverride:
    def setup_method(self):
        reset_locale()

    def test_workspace_created_turkish(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_LANG", "tr")
        reset_locale()
        result = msg("workspace_created", path="/tmp/test")
        assert "oluşturuldu" in result
        assert "/tmp/test" in result

    def test_error_no_workspace_turkish(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_LANG", "tr")
        reset_locale()
        result = msg("error_no_workspace")
        assert "bulunamadı" in result

    def test_lc_all_turkish(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        monkeypatch.setenv("LC_ALL", "tr_TR.UTF-8")
        reset_locale()
        result = msg("workspace_created", path="/x")
        assert "oluşturuldu" in result

    def test_lang_turkish(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.setenv("LANG", "tr_TR")
        reset_locale()
        result = msg("workspace_created", path="/x")
        assert "oluşturuldu" in result


class TestPriority:
    def setup_method(self):
        reset_locale()

    def test_ao_kernel_lang_overrides_lc(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_LANG", "en")
        monkeypatch.setenv("LC_ALL", "tr_TR.UTF-8")
        reset_locale()
        result = msg("workspace_created", path="/x")
        assert "Workspace created" in result

    def test_ao_kernel_lang_tr_overrides_en_lc(self, monkeypatch):
        monkeypatch.setenv("AO_KERNEL_LANG", "tr")
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        reset_locale()
        result = msg("workspace_created", path="/x")
        assert "oluşturuldu" in result


class TestFallback:
    def setup_method(self):
        reset_locale()

    def test_unknown_key_returns_key(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        reset_locale()
        result = msg("nonexistent_key_xyz")
        assert result == "nonexistent_key_xyz"

    def test_missing_format_arg_returns_template(self, monkeypatch):
        monkeypatch.delenv("AO_KERNEL_LANG", raising=False)
        reset_locale()
        result = msg("workspace_created")  # missing path=
        assert "Workspace created" in result
