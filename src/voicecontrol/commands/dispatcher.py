#!/usr/bin/env python3
"""Диспетчер команд (этап 2): разбор → валидация → подтверждение → выполнение.

Гарантии:
- неизвестная/пустая команда даёт понятный отказ и НЕ вызывает ни один обработчик;
- аргументы валидируются до вызова обработчика;
- опасные команды требуют подтверждения: отказ, неразборчивый ответ и таймаут
  отменяют действие;
- обработчик обязан вернуть CommandResult; исключение или посторонний тип —
  это отказ, а не фиктивный успех;
- распознанный текст используется только как аргументы зарегистрированных
  команд, но не как произвольная команда ОС (этап 3 — PlatformAdapter).
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from voicecontrol.commands.confirmation import (
    ConfirmFn, is_affirmative, ConfirmationTimeout,
)
from voicecontrol.commands.parser import match_command, normalize_text
from voicecontrol.commands.registry import CommandRegistry, CommandResult


class CommandDispatcher:
    """Разбирает пользовательский текст и выполняет зарегистрированные команды."""

    def __init__(self, registry: CommandRegistry, config: Any = None):
        if not isinstance(registry, CommandRegistry):
            raise TypeError("CommandDispatcher: требуется CommandRegistry")
        self.registry = registry
        self.logger = logging.getLogger(self.__class__.__name__)
        self.language = (config.get('language', 'ru') if config else 'ru')
        self.confirmation_required = bool(config.get('security.confirmation_required', True)) if config else True
        self.confirmation_timeout = float(config.get('security.confirmation_timeout', 10.0)) if config else 10.0

    def dispatch(self, text: str, get_confirmation: Optional[ConfirmFn] = None) -> CommandResult:
        normalized = normalize_text(text)
        if not normalized:
            self.logger.info("Пустая или нераспознаваемая фраза")
            return CommandResult(False, "Команда не распознана: пустой ввод.", self.language)

        match = match_command(normalized, self.registry)
        if match is None:
            self.logger.warning("Неизвестная команда: %r", text)
            return CommandResult(
                False,
                f"Неизвестная команда: «{text}». Скажите команду из списка поддерживаемых.",
                self.language,
            )

        spec = match.spec
        args = match.args
        self.logger.info("Команда: %s (%s), аргументы: %s", spec.name, match.language, args)

        # --- валидация аргументов до выполнения ---
        error = self._validate_args(spec, args)
        if error is not None:
            self.logger.warning("Отклонено: %s: %s", spec.name, error)
            return CommandResult(False, error, self.language)

        # --- обработчик (этап 3) ---
        if spec.handler is None:
            message = (
                f"Действие «{spec.name}» распознано, но обработчик ещё не подключён (этап 3)."
                if match.language == 'ru' else
                f"Aktion «{spec.name}» erkannt, aber der Handler ist noch nicht verbunden (Etappe 3)."
            )
            self.logger.info(message)
            return CommandResult(False, message, match.language)

        # --- подтверждение опасных действий ---
        if spec.dangerous and self.confirmation_required:
            cancel = self._obtain_confirmation(spec, match, get_confirmation)
            if cancel is not None:
                return cancel

        try:
            result = spec.handler(args)
        except Exception as e:  # отказ, а не ложный успех
            self.logger.error("Ошибка обработчика команды '%s': %s", spec.name, e, exc_info=True)
            return CommandResult(False, f"Действие «{spec.name}» вызвало ошибку: {e}", self.language)

        if not isinstance(result, CommandResult):
            self.logger.error(
                "Обработчик команды '%s' вернул %s вместо CommandResult — трактуется как отказ.",
                spec.name, type(result).__name__,
            )
            return CommandResult(False, f"Внутренняя ошибка результата действия «{spec.name}».", self.language)

        self.logger.info("Результат команды '%s': success=%s", spec.name, result.success)
        return result

    # ------------------------------------------------------------------ части

    def _validate_args(self, spec, args: Mapping[str, str]) -> Optional[str]:
        missing = [a for a in spec.required_args if a not in args]
        if missing:
            return f"Команда «{spec.name}» требует аргументы {missing}, получено: {args or '—'}."
        for arg, validator in spec.validators.items():
            try:
                value = args.get(arg)
                problem = validator(value)
            except Exception as e:  # дефект валидатора — отказ, не падение диспетчера
                return f"Внутренняя ошибка валидации аргумента «{arg}» команды «{spec.name}»: {e}"
            if problem is not None:
                return f"Недопустимый аргумент «{arg}» команды «{spec.name}»: {problem}."
        return None

    def _obtain_confirmation(
        self, spec, match, get_confirmation: Optional[ConfirmFn],
    ) -> Optional[CommandResult]:
        """Возвращает CommandResult отмены или None, если подтверждено."""
        if match.language == 'de':
            prompt = f"Bestätigen Sie die Aktion «{spec.name}»?"
            cancelled = f"Aktion «{spec.name}» abgebrochen."
        else:
            prompt = f"Подтверждаете действие «{spec.name}»?"
            cancelled = f"Действие «{spec.name}» отменено."

        if get_confirmation is None:
            self.logger.warning("Команда '%s': подтверждение недоступно — действие отменено", spec.name)
            return CommandResult(False, f"{cancelled} Подтверждение недоступно.", self.language)

        try:
            answer = get_confirmation(prompt, self.confirmation_timeout)
        except ConfirmationTimeout:
            self.logger.info("Команда '%s': таймаут подтверждения — отменено", spec.name)
            return CommandResult(
                False,
                f"{cancelled} Время на подтверждение истекло."
                if match.language == 'ru' else
                f"{cancelled} Zeit für die Bestätigung ist abgelaufen.",
                self.language,
            )
        except Exception as e:
            self.logger.error("Команда '%s': сбой получения подтверждения: %s", spec.name, e)
            return CommandResult(False, f"{cancelled} Ошибка получения подтверждения: {e}", self.language)

        normalized = normalize_text(answer)
        if is_affirmative(normalized):
            self.logger.info("Команда '%s': подтверждено", spec.name)
            return None
        if match.language == 'de':
            detail = f"Wiederholte Antwort: «{answer}»."
        else:
            detail = f"Ответ: «{answer}»."
        self.logger.info("Команда '%s': отказ/неразборчивый ответ — отменено", spec.name)
        return CommandResult(False, f"{cancelled} {detail}", self.language)
