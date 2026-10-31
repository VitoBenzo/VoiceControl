#!/usr/bin/env python3
"""Подтверждение опасных действий (этап 2).

Правила из требования: отказ, неразборчивый ответ и таймаут отменяют действие.
Провайдер получает запрос и текст (потом — голос, этап 7) ответа пользователя;
лингвистика yes/no — по словарям и на русском, и на немецком.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from voicecontrol.commands.parser import normalize_text
from voicecontrol.commands.registry import CommandResult

YES_WORDS = frozenset({
    'да', 'ага', 'давай', 'подтверждаю', 'продолжай', 'ок', 'окей', 'хорошо',
    'yes', 'yeah', 'ok', 'ja', 'bitte',
})
NO_WORDS = frozenset({
    'нет', 'отмена', 'отмени', 'стоп', 'не надо', 'не стоит',
    'no', 'nein', 'stopp', 'abbrechen', 'cancel',
})

ConfirmFn = Callable[[str, float], Optional[str]]
"""Провайдер ответа: (prompt, timeout) -> текст ответа.

None или TimeoutError означают таймаут/отсутствие ответа.
"""


def is_affirmative(answer: Optional[str]) -> bool:
    return normalize_text(answer) in YES_WORDS


def is_negative(answer: Optional[str]) -> bool:
    return normalize_text(answer) in NO_WORDS


class ConfirmationTimeout(TimeoutError):
    """Таймаут ожидания ответа пользователя."""


def console_confirmation(prompt: str, timeout: float) -> Optional[str]:
    """Текстовый провайдер для console/dry-run режима: ожидает ввод до timeout.

    Используется явно (не включается незаметно); голосовой провайдер — этап 7.
    """
    import builtins
    deadline = time.monotonic() + max(timeout, 2.0)
    logger = logging.getLogger(__name__)
    logger.info("Ожидание подтверждения (%.0fs): %s", timeout, prompt)
    builtins.print(f"{prompt} (да/нет, {int(timeout)}с): ", end='', flush=True)
    try:
        answer = builtins.input()
    except (EOFError, KeyboardInterrupt) as e:
        raise ConfirmationTimeout(f"подтверждение не получено: {e}") from e
    if time.monotonic() >= deadline or not answer.strip():
        raise ConfirmationTimeout("пустой ответ или истёкшее время")
    return answer
