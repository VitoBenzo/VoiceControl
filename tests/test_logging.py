#!/usr/bin/env python3
"""Тесты логирования с ротацией (этап 1)."""

import logging
from pathlib import Path

from voicecontrol.config import Config
from voicecontrol.logging_setup import setup_logging


def make_config(log_file, max_bytes, backup_count=2, level="INFO"):
    return Config({
        "logging": {
            "file": str(log_file),
            "max_bytes": max_bytes,
            "backup_count": backup_count,
            "level": level,
        }
    })


def test_setup_returns_logger(tmp_path):
    log_file = tmp_path / "vc.log"
    logger = setup_logging(make_config(log_file, max_bytes=100_000))
    assert isinstance(logger, logging.Logger)
    assert logger.name == "voicecontrol"


def test_log_written(tmp_path):
    log_file = tmp_path / "vc.log"
    logger = setup_logging(make_config(log_file, max_bytes=100_000))
    logger.info("тестовое сообщение")
    for h in logger.handlers:
        h.flush()
    assert log_file.exists()
    assert "тестовое сообщение" in log_file.read_text(encoding="utf-8")


def test_rotation_creates_backup(tmp_path):
    log_file = tmp_path / "rotate.log"
    # Маленький лимит, чтобы ротация гарантированно сработала
    logger = setup_logging(make_config(log_file, max_bytes=1024, backup_count=2))
    filler = "x" * 256
    for i in range(12):
        logger.info("строка %d %s", i, filler)
    for h in logger.handlers:
        h.flush()

    backups = [p for p in tmp_path.glob("rotate.log.*")]
    # Число копий не превышает backup_count
    assert 1 <= len(backups) <= 2
    # Основной файл не превышает лимит заметно больше одного сообщения
    assert log_file.stat().st_size <= 1024 + 512


def test_bad_level_raises(tmp_path):
    import pytest
    from voicecontrol.config import ConfigError
    with pytest.raises(ConfigError, match="logging.level"):
        setup_logging(make_config(tmp_path / "vc.log", max_bytes=1024, level="LOUD"))


def test_resetup_replaces_handlers(tmp_path):
    """Повторный вызов setup_logging не дублирует обработчики (важно для тестов)."""
    logger = setup_logging(make_config(tmp_path / "a.log", max_bytes=10_000))
    setup_logging(make_config(tmp_path / "b.log", max_bytes=10_000))
    n = len(logger.handlers)
    assert n == 2  # файл + консоль, без накопления
