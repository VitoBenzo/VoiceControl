#!/usr/bin/env python3
"""Обработчики действий ОС (этап 3): каталог команд этапа 2 + PlatformAdapter.

Разделение ответственности:
- валидаторы аргументов и нормализация — этап 2 (parser/builtins);
- белый список приложений и валидация путей — здесь, до вызова адаптера;
- фактические системные вызовы — только в PlatformAdapter;
- dry_run включается конфигурацией (security.dry_run) и никогда не «незаметно».

Распознанный текст не превращается в произвольную команду ОС: имя приложения
резолвится ТОЛЬКО через белый список, путь — только внутри allowed_dirs.
"""

from __future__ import annotations

import logging
from typing import Mapping, Optional

from voicecontrol.commands.builtins import build_default_registry
from voicecontrol.config import ConfigError
from voicecontrol.platform_adapter import ActionOutcome, create_adapter
from voicecontrol.commands.registry import CommandRegistry, CommandResult

_logger = logging.getLogger(__name__)


def _ru_outcome(outcome: ActionOutcome, ok_msg: str, fail_prefix: str) -> str:
    """Сообщение: при успехе — описание действия, при ошибке — её причина."""
    if outcome.success:
        return f"{ok_msg} {outcome.detail}".strip()
    return f"{fail_prefix} {outcome.detail}".strip()


def _whitelist_reject(app: str) -> CommandResult:
    return CommandResult(
        False,
        f"Приложение «{app}» отсутствует в белом списке (security.app_whitelist). Действие не выполнено.",
    )


def _resolve_app_arg(app: str, whitelist: Mapping[str, str]) -> Optional[str]:
    """Имя приложения -> путь из белого списка (без учёта регистра).

    Если не найден — None: имя не подставляется в системные вызовы.
    """
    if not app or not app.strip():
        return None
    key = app.strip().casefold()
    for name, exe in whitelist.items():
        if str(name).strip().casefold() == key:
            exe = str(exe).strip()
            if exe:
                return exe
    return None


def build_os_registry(config):
    """Реестр команд с реальными обработчиками действий ОС.

    Требует явно заданной целевой ОС: security.target_os (не угадывается кодом).
    dry_run берётся из security.dry_run (по умолчанию True — безопасный режим).
    """
    allowed_dirs = tuple(config.get('security.allowed_dirs', []) or ())
    whitelist = dict(config.get('security.app_whitelist', {}) or {})

    registry = build_default_registry(allowed_dirs=allowed_dirs)

    target_os = config.get('security.target_os', None)
    if not target_os:
        raise ConfigError(
            "security.target_os не задан: целевая ОС должна быть указана "
            "пользователем в конфигурации (windows|linux|macos), а не угадана."
        )
    adapter = create_adapter(str(target_os), dry_run=bool(config.get('security.dry_run', True)))

    for spec in registry:
        name = spec.name

        if name == 'open_app':
            def handler(args, _n=name):
                app = str(args.get('app', '')).strip()
                exe = _resolve_app_arg(app, whitelist)
                if exe is None:
                    return _whitelist_reject(app)
                outcome = adapter.launch_app(exe)
                message = _ru_outcome(
                    outcome,
                    ok_msg=f"Запуск «{app}»:",
                    fail_prefix=f"Запуск «{app}» не выполнен:",
                )
                return CommandResult(outcome.success, message)

        elif name == 'close_app':
            def handler(args, _n=name):
                app = str(args.get('app', '')).strip()
                exe = _resolve_app_arg(app, whitelist)
                if exe is None:
                    return _whitelist_reject(app)
                outcome = adapter.close_app(exe)
                message = _ru_outcome(
                    outcome,
                    ok_msg=f"Закрытие «{app}»:",
                    fail_prefix=f"Закрытие «{app}» не выполнено:",
                )
                return CommandResult(outcome.success, message)

        elif name == 'minimize_windows':
            def handler(args, _n=name):
                outcome = adapter.minimize_all_windows()
                message = _ru_outcome(
                    outcome,
                    ok_msg="Свертывание окон:",
                    fail_prefix="Свернуть окна не удалось:",
                )
                return CommandResult(outcome.success, message)

        elif name in ('open_folder', 'open_file'):
            def handler(args, _n=name):
                path = str(args.get('path', '')).strip()
                # Защита в глубину: валидатор пути вызывается повторно здесь
                validator = registry.get(_n).validators['path']
                problem = validator(path)
                if problem is not None:
                    return CommandResult(False, f"Путь не разрешён: {problem}")
                if _n == 'open_folder':
                    outcome = adapter.open_folder(path)
                    ok_msg = f"Открываю папку «{path}»:"
                    fail_prefix = f"Папка «{path}» не открыта:"
                else:
                    outcome = adapter.open_file(path)
                    ok_msg = f"Открываю файл «{path}»:"
                    fail_prefix = f"Файл «{path}» не открыт:"
                return CommandResult(outcome.success, _ru_outcome(outcome, ok_msg, fail_prefix))

        elif name == 'set_volume':
            def handler(args, _n=name):
                level_raw = str(args.get('level', '')).strip().rstrip('%')
                try:
                    level = int(level_raw)
                except ValueError:
                    return CommandResult(False, f"Недопустимый уровень громкости: {level_raw!r}")
                outcome = adapter.set_volume(level)
                message = _ru_outcome(
                    outcome,
                    ok_msg="Установка громкости:",
                    fail_prefix="Громкость не установлена:",
                )
                return CommandResult(outcome.success, message)

        elif name == 'shutdown':
            def handler(args, _n=name):
                outcome = adapter.shutdown()
                message = _ru_outcome(
                    outcome,
                    ok_msg="Выключение:",
                    fail_prefix="Выключение не выполнено:",
                )
                return CommandResult(outcome.success, message)

        elif name == 'restart':
            def handler(args, _n=name):
                outcome = adapter.restart()
                message = _ru_outcome(
                    outcome,
                    ok_msg="Перезагрузка:",
                    fail_prefix="Перезагрузка не выполнена:",
                )
                return CommandResult(outcome.success, message)

        else:  # pragma: no cover — новые команды каталога должны добавляться явно
            _logger.error("Команда '%s' без обработчика этапа 3 — останется неактивной", name)
            spec.handler = None
            continue

        spec.handler = handler

    _logger.info(
        "ОС-реестр готов: %d команд, target_os=%s, dry_run=%s",
        len(registry), target_os, bool(config.get('security.dry_run', True)),
    )
    return registry
