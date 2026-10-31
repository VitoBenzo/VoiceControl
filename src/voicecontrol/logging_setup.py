#!/usr/bin/env python3
"""Настройка логирования VoiceControl (этап 1).

Использует RotatingFileHandler: лог не растёт бесконтрольно.
Уровень, файл и параметры ротации задаются секцией [logging] конфигурации.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from voicecontrol.config import Config, ConfigError

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging(config: Config, log_file: Optional[str] = None) -> logging.Logger:
    """Настраивает корневой логгер 'voicecontrol' и возвращает его.

    Обработчики пересоздаются, поэтому функция безопасна для повторных
    вызовов (например, из тестов с разными файлами).
    """
    level_name = str(config.get('logging.level', 'INFO')).upper()
    if level_name not in _LOG_LEVELS:
        raise ConfigError(f"logging.level: ожидалось одно из {_LOG_LEVELS}, получено {level_name!r}")

    file_path = Path(log_file or config.get('logging.file', 'voicecontrol.log'))
    max_bytes = int(config.get('logging.max_bytes', 1_000_000))
    backup_count = int(config.get('logging.backup_count', 3))

    root = logging.getLogger('voicecontrol')
    root.handlers.clear()
    root.setLevel(level_name)
    root.propagate = False

    file_handler = RotatingFileHandler(
        file_path, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(console)

    return root
