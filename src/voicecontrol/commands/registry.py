#!/usr/bin/env python3
"""Централизованный реестр команд и результаты выполнения (этап 2).

Команды регистрируются явно через CommandRegistry, а не задаются
жёстко внутри диспетчера. Каждый обработчик обязан вернуть CommandResult
со фактическим успехом/неудачей — фиктивные «успехи» запрещены чеклистом.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Optional, Sequence

# Обработчик принимает словарь аргументов и обязан вернуть CommandResult
Handler = Callable[[Mapping[str, str]], 'CommandResult']

# Валидатор аргумента возвращает None при успехе или строку с описанием ошибки
ArgValidator = Callable[[Optional[str]], Optional[str]]


@dataclass(frozen=True)
class CommandResult:
    """Актуальный результат: успех/неудача, сообщение, язык ответа."""
    success: bool
    message: str
    language: str = 'ru'


@dataclass(frozen=True)
class Synonym:
    """Вариант фразы на конкретном языке.

    pattern может содержать плейсхолдеры аргументов: "открой {app}".
    """
    language: str
    pattern: str


@dataclass
class CommandSpec:
    """Спецификация команды."""
    name: str
    synonyms: Sequence[Synonym]
    # Этап 2: обработчик может отсутствовать (действия ОС подключаются на этапе 3)
    handler: Optional[Handler] = None
    validators: Mapping[str, ArgValidator] = field(default_factory=dict)
    required_args: Sequence[str] = ()
    dangerous: bool = False


class RegistryError(ValueError):
    """Ошибка регистрации команды."""


class CommandRegistry:
    """Централизованный реестр команд."""

    def __init__(self):
        self._specs: dict[str, CommandSpec] = {}

    def register(self, spec: CommandSpec) -> None:
        if not isinstance(spec, CommandSpec):
            raise RegistryError(f"Ожидался CommandSpec, получено {type(spec).__name__}")
        if not spec.name or not isinstance(spec.name, str):
            raise RegistryError(f"Некорректное имя команды: {spec.name!r}")
        if spec.name in self._specs:
            raise RegistryError(f"Команда '{spec.name}' уже зарегистрирована")
        if not spec.synonyms or not all(isinstance(s, Synonym) for s in spec.synonyms):
            raise RegistryError(f"Команда '{spec.name}': список синонимов пуст или некорректен")
        self._specs[spec.name] = spec

    def get(self, name: str) -> Optional[CommandSpec]:
        return self._specs.get(name)

    def commands(self) -> tuple[CommandSpec, ...]:
        return tuple(self._specs.values())

    def __iter__(self):
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)
