#!/usr/bin/env python3
"""Тесты загрузки и валидации конфигурации (этап 1)."""

import json
import textwrap

import pytest

from voicecontrol.config import Config, ConfigError, load_config

VALID_TOML = textwrap.dedent("""
    language = "ru"
    wake_phrase = "activate"

    [audio]
    sample_rate = 16000
    chunk_size = 1024

    [tts]
    rate = 190
""")

VALID = {
    "language": "ru",
    "wake_phrase": "activate",
    "audio": {"sample_rate": 16000, "chunk_size": 1024},
}


def write_toml(tmp_path, content=VALID_TOML):
    p = tmp_path / "config.toml"
    p.write_text(content, encoding="utf-8")
    return p


class TestLoad:
    def test_toml_loads(self, tmp_path):
        cfg = load_config(write_toml(tmp_path))
        assert isinstance(cfg, Config)
        assert cfg.get("language") == "ru"
        assert cfg.get("wake_phrase") == "activate"
        assert cfg.get("audio.sample_rate") == 16000
        assert cfg.get("audio.chunk_size") == 1024

    def test_json_fallback(self, tmp_path):
        p = tmp_path / "config.json"
        p.write_text(json.dumps(VALID), encoding="utf-8")
        cfg = load_config(p)
        assert cfg.get("audio.sample_rate") == 16000

    def test_missing_file(self, tmp_path):
        with pytest.raises(ConfigError, match="не найден"):
            load_config(tmp_path / "nope.toml")

    def test_unsupported_format(self, tmp_path):
        p = tmp_path / "config.ini"
        p.write_text("x = 1", encoding="utf-8")
        with pytest.raises(ConfigError, match="формат"):
            load_config(p)

    def test_broken_toml(self, tmp_path):
        p = tmp_path / "bad.toml"
        p.write_text("language = [", encoding="utf-8")
        with pytest.raises(ConfigError, match="TOML"):
            load_config(p)

    def test_missing_required_field(self, tmp_path):
        p = tmp_path / "config.toml"
        p.write_text('wake_phrase = "x"\n', encoding="utf-8")
        with pytest.raises(ConfigError, match="language"):
            load_config(p)


class TestValidation:
    def _load_with(self, tmp_path, overrides=None, base=None):
        """Готовит конфиг из словаря (base/overrides) с глубоким слиянием и загружает как JSON."""
        import copy

        def deep_merge(dst, src):
            for key, value in src.items():
                if isinstance(value, dict) and isinstance(dst.get(key), dict):
                    deep_merge(dst[key], value)
                else:
                    dst[key] = value

        data = copy.deepcopy(base if base is not None else VALID)
        deep_merge(data, overrides or {})
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return load_config(p)

    def test_empty_wake_phrase(self, tmp_path):
        with pytest.raises(ConfigError, match="wake_phrase.*пустой"):
            self._load_with(tmp_path, {"wake_phrase": ""})

    def test_bad_enum(self, tmp_path):
        with pytest.raises(ConfigError, match="run_mode"):
            self._load_with(tmp_path, {"run_mode": "turbo"})

    def test_unsupported_language(self, tmp_path):
        with pytest.raises(ConfigError, match="language"):
            self._load_with(tmp_path, {"language": "fr"})

    def test_bad_type(self, tmp_path):
        with pytest.raises(ConfigError, match="audio.sample_rate"):
            self._load_with(tmp_path, {"audio": {"sample_rate": "16k"}})

    @pytest.mark.parametrize("rate", [4000, 12000, 96000])
    def test_sample_rate_choices(self, tmp_path, rate):
        with pytest.raises(ConfigError, match="sample_rate"):
            self._load_with(tmp_path, {"audio": {"sample_rate": rate}})

    @pytest.mark.parametrize("rate", [8000, 16000, 44100])
    def test_sample_rate_ok(self, tmp_path, rate):
        cfg = self._load_with(tmp_path, {"audio": {"sample_rate": rate}})
        assert cfg.get("audio.sample_rate") == rate

    def test_chunk_size_range(self, tmp_path):
        with pytest.raises(ConfigError, match="chunk_size"):
            self._load_with(tmp_path, {"audio": {"chunk_size": 64}})

    def test_vad_threshold_range(self, tmp_path):
        with pytest.raises(ConfigError, match="silence_threshold"):
            self._load_with(tmp_path, {"vad": {"silence_threshold": 1.5}})

    def test_confirmation_timeout_range(self, tmp_path):
        with pytest.raises(ConfigError, match="confirmation_timeout"):
            self._load_with(tmp_path, {"security": {"confirmation_timeout": 0.5}})

    def test_whitelist_must_be_table(self, tmp_path):
        with pytest.raises(ConfigError, match="app_whitelist"):
            self._load_with(tmp_path, {"security": {"app_whitelist": "notepad"}})

    def test_whitelist_values_must_be_strings(self, tmp_path):
        with pytest.raises(ConfigError, match="app_whitelist"):
            self._load_with(tmp_path, {"security": {"app_whitelist": {"notepad": 1}}})

    def test_tts_volume_range(self, tmp_path):
        with pytest.raises(ConfigError, match="tts.volume"):
            self._load_with(tmp_path, {"tts": {"volume": 2.0}})

    def test_logging_rotation_settings(self, tmp_path):
        with pytest.raises(ConfigError, match="max_bytes"):
            self._load_with(tmp_path, {"logging": {"max_bytes": 10}})

    def test_defaults_optional_sections(self, tmp_path):
        cfg = self._load_with(tmp_path)
        # Отсутствующие секции не запрещают запуск; значения берутся по умолчанию
        assert cfg.get("run_mode", "production") == "production"
        assert cfg.get("logging.max_bytes", 1_000_000) == 1_000_000
