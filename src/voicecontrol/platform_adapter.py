#!/usr/bin/env python3
"""Платформенный адаптер (этап 3): все вызовы ОС за единым интерфейсом.

Гарантии из требования:
- целевая ОС задаётся конфигурацией (security.target_os), а НЕ угадывается кодом;
- запуск процессов — только subprocess со СПИСКОМ аргументов и shell=False;
- dry_run=True не выполняет системных вызовов, только описывает действие;
- любая ошибка действия — это отказ (success=False), а не ложный успех;
- белый список приложений и валидация путей выполняются до адаптера (os_handlers).
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Sequence

_TARGET_OS = ("windows", "linux", "macos")


class AdapterError(ValueError):
    """Неизвестная/неуказанная целевая ОС."""


@dataclass(frozen=True)
class ActionOutcome:
    """Результат действия ОС: успех/неудача и понятное описание."""
    success: bool
    detail: str


def run_command(argv: Sequence[str], *, dry_run: bool, timeout: float = 20.0) -> ActionOutcome:
    """Единственная точка вызова внешних процессов.

    argv — список аргументов (не строка для shell). shell=False всегда.
    """
    argv = list(argv)
    logger = logging.getLogger('voicecontrol.platform_adapter')
    if dry_run:
        logger.info("[dry-run] было бы выполнено: %s", argv)
        return ActionOutcome(True, f"[dry-run] было бы выполнено: {argv}")

    logger.info("Выполнение: %s", argv)
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,          # запрещено требованием: shell-строки не используются
            check=False,
        )
    except FileNotFoundError as e:
        logger.error("Команда недоступна: %s (argv=%s)", e, argv)
        return ActionOutcome(False, f"Команда недоступна: {e}")
    except PermissionError as e:
        logger.error("Отказано в доступе: %s (argv=%s)", e, argv)
        return ActionOutcome(False, f"Отказано в доступе: {e}")
    except subprocess.TimeoutExpired:
        logger.error("Превышено время (%ss): %s", timeout, argv)
        return ActionOutcome(False, f"Превышено время выполнения ({timeout:.0f} с): {argv[0]}")
    except OSError as e:
        logger.error("Ошибка ОС: %s (argv=%s)", e, argv)
        return ActionOutcome(False, f"Ошибка ОС: {e}")

    stdout = (result.stdout or '').strip()
    stderr = (result.stderr or '').strip()
    if result.returncode != 0:
        detail = stderr or stdout or f"код возврата {result.returncode}"
        logger.error("Неуспешный код возврата %s: %s (argv=%s)", result.returncode, detail, argv)
        return ActionOutcome(False, detail)
    return ActionOutcome(True, stdout or "выполнено без вывода")


class WindowsAdapter:
    """Windows: explorer/taskkill/shutdown; COM для окон; pycaw для громкости."""

    target_os = 'windows'

    def __init__(self, dry_run: bool = True):
        self.dry_run = bool(dry_run)
        self.logger = logging.getLogger(self.__class__.__name__)

    def launch_app(self, exe_path: str) -> ActionOutcome:
        return run_command([exe_path], dry_run=self.dry_run, timeout=10.0)

    def close_app(self, exe_path: str) -> ActionOutcome:
        image = os.path.basename(exe_path)
        return run_command(['taskkill', '/IM', image, '/F'], dry_run=self.dry_run)

    def minimize_all_windows(self) -> ActionOutcome:
        if self.dry_run:
            self.logger.info("[dry-run] минимизация всех окон (Shell.Application)")
            return ActionOutcome(True, "[dry-run] было бы выполнено: MinimizeAll()")
        try:
            import win32com.client  # noqa
        except ImportError as e:
            return ActionOutcome(False, f"pywin32 недоступен (установите extras 'windows'): {e}")
        try:
            shell = win32com.client.Dispatch('Shell.Application')
            shell.MinimizeAll()
            return ActionOutcome(True, "Все окна свернуты")
        except Exception as e:
            self.logger.error("MinimizeAll не выполнен: %s", e)
            return ActionOutcome(False, f"Свернуть окна не удалось: {e}")

    def open_folder(self, path: str) -> ActionOutcome:
        return run_command(['explorer', path], dry_run=self.dry_run)

    def open_file(self, path: str) -> ActionOutcome:
        return run_command(['explorer', path], dry_run=self.dry_run)

    def set_volume(self, level: int) -> ActionOutcome:
        if self.dry_run:
            self.logger.info("[dry-run] громкость -> %s%%", level)
            return ActionOutcome(True, f"[dry-run] громкость была бы установлена: {level}%")
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import POINTER, cast
        except ImportError as e:
            return ActionOutcome(False, f"pycaw/comtypes недоступны (установите extras 'windows'): {e}")
        try:
            speakers = AudioUtilities.GetSpeakers()
            interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            return ActionOutcome(True, f"Громкость: {level}%")
        except Exception as e:
            self.logger.error("Не удалось установить громкость: %s", e)
            return ActionOutcome(False, f"Громкость не установлена: {e}")

    def shutdown(self) -> ActionOutcome:
        return run_command(['shutdown', '/s', '/f', '/t', '0'], dry_run=self.dry_run)

    def restart(self) -> ActionOutcome:
        return run_command(['shutdown', '/r', '/f', '/t', '0'], dry_run=self.dry_run)


class LinuxAdapter:
    """Linux: xdg-open, amixer, shutdown; wmctrl для окон (опционально)."""

    target_os = 'linux'

    def __init__(self, dry_run: bool = True):
        self.dry_run = bool(dry_run)
        self.logger = logging.getLogger(self.__class__.__name__)

    def launch_app(self, exe_path: str) -> ActionOutcome:
        return run_command([exe_path], dry_run=self.dry_run, timeout=10.0)

    def close_app(self, exe_path: str) -> ActionOutcome:
        image = os.path.basename(exe_path)
        return run_command(['pkill', '-f', image], dry_run=self.dry_run)

    def minimize_all_windows(self) -> ActionOutcome:
        return run_command(['wmctrl', '-k', 'on'], dry_run=self.dry_run)

    def open_folder(self, path: str) -> ActionOutcome:
        return run_command(['xdg-open', path], dry_run=self.dry_run)

    def open_file(self, path: str) -> ActionOutcome:
        return run_command(['xdg-open', path], dry_run=self.dry_run)

    def set_volume(self, level: int) -> ActionOutcome:
        return run_command(
            ['amixer', '-D', 'pulse', 'sset', 'Master', f'{level}%'],
            dry_run=self.dry_run,
        )

    def shutdown(self) -> ActionOutcome:
        return run_command(['shutdown', '-h', 'now'], dry_run=self.dry_run)

    def restart(self) -> ActionOutcome:
        return run_command(['shutdown', '-r', 'now'], dry_run=self.dry_run)


class MacOSAdapter:
    """macOS: open, amixer-замена — osascript; питание через 'shutdown' (sudo может потребоваться)."""

    target_os = 'macos'

    def __init__(self, dry_run: bool = True):
        self.dry_run = bool(dry_run)
        self.logger = logging.getLogger(self.__class__.__name__)

    def launch_app(self, exe_path: str) -> ActionOutcome:
        return run_command(['open', '-a', exe_path], dry_run=self.dry_run, timeout=10.0)

    def close_app(self, exe_path: str) -> ActionOutcome:
        name = os.path.splitext(os.path.basename(exe_path))[0].replace('"', '')
        return run_command(['osascript', '-e', f'quit app "{name}"'], dry_run=self.dry_run)

    def minimize_all_windows(self) -> ActionOutcome:
        return run_command(
            ['osascript', '-e', 'tell application "System Events" to set visible to false'],
            dry_run=self.dry_run,
        )

    def open_folder(self, path: str) -> ActionOutcome:
        return run_command(['open', path], dry_run=self.dry_run)

    def open_file(self, path: str) -> ActionOutcome:
        return run_command(['open', path], dry_run=self.dry_run)

    def set_volume(self, level: int) -> ActionOutcome:
        return run_command(
            ['osascript', '-e', f'set volume output volume {int(level)}'],
            dry_run=self.dry_run,
        )

    def shutdown(self) -> ActionOutcome:
        return run_command(['osascript', '-e', 'tell app "System Events" to shut down'], dry_run=self.dry_run)

    def restart(self) -> ActionOutcome:
        return run_command(['osascript', '-e', 'tell app "System Events" to restart'], dry_run=self.dry_run)


_ADAPTERS = {
    'windows': WindowsAdapter,
    'linux': LinuxAdapter,
    'macos': MacOSAdapter,
}


def create_adapter(target_os: str, dry_run: bool = True):
    """Фабрика адаптера по ЯВНО указанной целевой ОС (без угадывания)."""
    if target_os not in _ADAPTERS:
        raise AdapterError(
            f"security.target_os: ожидалось одно из {_TARGET_OS}, получено {target_os!r}. "
            "Целевая ОС задаётся пользователем в конфигурации."
        )
    adapter_cls = _ADAPTERS[target_os]
    logging.getLogger('voicecontrol.platform_adapter').info(
        "Создан адаптер целевой ОС '%s' (dry_run=%s)", target_os, dry_run,
    )
    return adapter_cls(dry_run=dry_run)
