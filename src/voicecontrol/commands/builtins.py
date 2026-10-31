#!/usr/bin/env python3
"""Каталог команд MVP — только категории из раздела 4.4 ТЗ: приложения,
окна, папки, файлы/директории, громкость, выключение и перезагрузка.

Этап 2: команды зарегистрированы с вариантами ru/de и валидаторами аргументов,
но обработчики (None) подключаются на этапе 3 через PlatformAdapter и белый
список. Случайных/фиктивных действий здесь нет.

Варианты «погаси свет», «запусти виндовс», «какая погода», «информация о
системе» из прежней реализации отсутствуют: они не входят в ТЗ.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Sequence

from voicecontrol.commands.registry import CommandRegistry, CommandSpec, Synonym

_logger = logging.getLogger(__name__)


def _path_inside(path: Path, base: Path) -> bool:
    """Регистронезависимая проверка «path находится внутри base» без ложных
    префиксов (C:\\Data не считается директорией для C:\\Database)."""
    p_cf = str(path).casefold()
    base_cf = str(base).casefold()
    if p_cf == base_cf:
        return True
    separator = '\\' if '\\' in base_cf else '/'
    return p_cf.startswith(base_cf.rstrip('\\/') + separator)


# ------------------------------------------------------------------ валидаторы

def not_empty(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return "аргумент пуст"
    return None


def make_app_validator():
    """Имя приложения: без разделителей путей; сопоставление с белым списком — этап 3."""

    def check(value: Optional[str]) -> Optional[str]:
        empty = not_empty(value)
        if empty:
            return empty
        v = value.strip()
        if any(ch in v for ch in ('\\', '/', ':', ';', '&', '|', '\x00')):
            return f"имя приложения не может содержать разделители путей/команд: {v!r}"
        return None

    return check


def make_volume_validator():
    """Громкость 0..100; '%' допускается."""

    def check(value: Optional[str]) -> Optional[str]:
        empty = not_empty(value)
        if empty:
            return empty
        v = value.strip().rstrip('%')
        # десятичный разделитель и запятая не поддерживаются: только int
        if not v.isdigit():
            return f"ожидалось число 0..100, получено: {value!r}"
        level = int(v)
        if not (0 <= level <= 100):
            return f"громкость {level} вне диапазона 0..100"
        return None

    return check


def make_path_validator(allowed_dirs: Sequence[str]):
    """Путь: абсолютный, без '..' перехода, внутри разрешённых директорий.

    Возврат ошибки-строки или None. Обход разрешённой директории невозможен:
    "..", символьные ссылки и относительные пути отбрасываются resolve().
    """
    if allowed_dirs:
        allowed = []
        for d in allowed_dirs:
            base = Path(d).resolve()
            allowed.append(base)
    else:
        allowed = None  # файловые операции запрещены вовсе

    def check(value: Optional[str]) -> Optional[str]:
        empty = not_empty(value)
        if empty:
            return empty
        v = value.strip().strip('"')
        if not Path(v).is_absolute():
            return f"ожидался абсолютный путь, получено: {v!r}"
        if any(part == '..' for part in v.replace('/', '\\').split('\\')):
            return f"путь содержит переход '..': {v!r}"
        if allowed is None:
            return (
                "файловые операции запрещены: в конфигурации пуста "
                "security.allowed_dirs"
            )
        try:
            resolved = Path(v).resolve()
        except (OSError, ValueError) as e:
            return f"некорректный путь {v!r}: {e}"
        for base in allowed:
            if _path_inside(resolved, base):
                return None
        return (
            f"путь {v!r} вне разрешённых директорий "
            f"({', '.join(str(b) for b in allowed)})"
        )

    return check


# ------------------------------------------------------------------ каталог

S = Synonym


def build_default_registry(allowed_dirs: Optional[Sequence[str]] = None) -> CommandRegistry:
    """Реестр MVP-команд по разделу 4.4 ТЗ с вариантами ru/de.

    Этап 2: handler=None — действия ОС подключаются на этапе 3.
    """
    app_check = make_app_validator()
    volume_check = make_volume_validator()
    path_check = make_path_validator(allowed_dirs or ())

    specs = [
        CommandSpec(
            name='open_app',
            synonyms=[S('ru', 'открой {app}'), S('ru', 'запусти {app}'),
                      S('de', 'öffne {app}'), S('de', 'starte {app}')],
            validators={'app': app_check},
            required_args=('app',),
        ),
        CommandSpec(
            name='close_app',
            synonyms=[S('ru', 'закрой {app}'), S('ru', 'закрыть {app}'),
                      S('de', 'schließe {app}')],
            validators={'app': app_check},
            required_args=('app',),
            dangerous=True,  # закрытие приложения — опасное действие
        ),
        CommandSpec(
            name='minimize_windows',
            synonyms=[S('ru', 'сверни все окна'), S('ru', 'сверни окна'),
                      S('de', 'minimiere alle fenster'), S('de', 'minimiere fenster')],
        ),
        CommandSpec(
            name='open_folder',
            synonyms=[S('ru', 'открой папку {path}'), S('de', 'öffne ordner {path}')],
            validators={'path': path_check},
            required_args=('path',),
        ),
        CommandSpec(
            name='open_file',
            synonyms=[S('ru', 'открой файл {path}'), S('de', 'öffne datei {path}')],
            validators={'path': path_check},
            required_args=('path',),
        ),
        CommandSpec(
            name='set_volume',
            synonyms=[S('ru', 'громкость {level}'), S('ru', 'установи громкость {level}'),
                      S('de', 'lautstärke {level}')],
            validators={'level': volume_check},
            required_args=('level',),
        ),
        CommandSpec(
            name='shutdown',
            synonyms=[S('ru', 'выключи компьютер'), S('ru', 'выключение системы'),
                      S('de', 'fahr herunter'), S('de', 'herunterfahren')],
            dangerous=True,
        ),
        CommandSpec(
            name='restart',
            synonyms=[S('ru', 'перезагрузи компьютер'), S('ru', 'перезагрузка'),
                      S('de', 'starte neu'), S('de', 'neustart')],
            dangerous=True,
        ),
    ]

    registry = CommandRegistry()
    for spec in specs:
        registry.register(spec)
    _logger.debug("Реестр команд построен: %d команд", len(registry))
    return registry
