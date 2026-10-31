#!/usr/bin/env python3
"""Нормализация командного текста и извлечение аргументов (этап 2).

Нормализация: регистр (casefold), пунктуация, типографские пробелы.
Извлечение аргументов: плейсхолдеры {name} в шаблонах синонимов.
Совпадений нет — явный None; случайных результатов нет.

Важно: ':', '\\', '/', '%', '.', '-' сохраняются в тексте — они значимы
для путей и громкости. «Заголовочное» двоеточие перед пробелом удаляется.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from voicecontrol.commands.registry import CommandRegistry, CommandSpec

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# Пунктуация → пробел. Дефис и точка НЕ удаляются (легальны в путях/расширениях).
# '[' и ']' внутри класса экранируются, иначе класс закрывается раньше времени.
_PUNCT_RE = re.compile(r"[,;!?«»„“”\"'()\[\]]+")

# Типографские и переводные пробелы
_EX_SPACE_RE = re.compile(r"[\u00a0\u2000-\u200b\t\r\n]+")


def normalize_text(text) -> str:
    r"""Нормальный вид команды: casefold, пунктуация → пробел, одинарные пробелы.

    Двоеточие перед пробелом считается разделителем («громкость: 50» →
    «громкость 50»); путь с обратным слэшем сохраняется.
    None → ''.
    """
    if text is None:
        return ''
    text = _EX_SPACE_RE.sub(' ', str(text))
    text = _PUNCT_RE.sub(' ', text)
    # «Предложенческое» двоеточие перед пробелом — разделитель
    text = re.sub(r":\s+", ' ', text)
    text = re.sub(r"\s+", ' ', text)
    text = text.strip(" .,;:!?«»„“”\"'()[]")
    return text.casefold()


def placeholder_names(pattern: str) -> tuple[str, ...]:
    """Имена аргументов шаблона: "открой {app}" → ('app',)."""
    return tuple(m.group(1) for m in _PLACEHOLDER_RE.finditer(pattern))


def compile_synonym(pattern: str) -> re.Pattern:
    """Компилирует шаблон синонима в regex с именованными группами аргументов."""
    placeholders = list(_PLACEHOLDER_RE.finditer(pattern))
    parts = []
    last = 0
    for i, m in enumerate(placeholders):
        literal = re.escape(pattern[last:m.start()])
        parts.append(literal)
        # Последний плейсхолдер жадно захватывает хвост фразы, остальные — минимально
        name = m.group(1)
        parts.append(f"(?P<{name}>.+)" if i == len(placeholders) - 1 else f"(?P<{name}>.+?)")
        last = m.end()
    parts.append(re.escape(pattern[last:]))
    regex = ''.join(parts).replace('\\ ', r'\s+')
    return re.compile('^' + regex + '$')


@dataclass(frozen=True)
class TextMatch:
    """Найденное совпадение: команда, аргументы, язык фразы."""
    spec: CommandSpec
    args: dict[str, str]
    language: str
    pattern: str


class _CompiledRegistry:
    """Кэш скомпилированных шаблонов реестра."""

    def __init__(self, registry: CommandRegistry):
        self._compiled: dict[str, dict[str, re.Pattern]] = {}
        for spec in registry:
            self._compiled[spec.name] = {
                syn.pattern: compile_synonym(syn.pattern) for syn in spec.synonyms
            }

    def get(self, spec_name: str, pattern: str) -> Optional[re.Pattern]:
        return self._compiled.get(spec_name, {}).get(pattern)


def match_command(normalized: str, registry: CommandRegistry) -> Optional[TextMatch]:
    """Ищет команду по нормализованному тексту.

    Приоритет по «литеральности»: шаблон, у которого больше букв самого шаблона
    (фиксированные фразы, «открой файл X»), побеждает общий («открой X»).
    При равенстве — порядок регистрации. Совпадений нет — None.
    """
    if not normalized:
        return None
    compiled = _CompiledRegistry(registry)  # компиляция быстрая, реестр мал
    best: Optional[TextMatch] = None
    best_score = (-1, -1, 0)
    for order, spec in enumerate(registry):
        for syn in spec.synonyms:
            rx = compiled.get(spec.name, syn.pattern)
            m = rx.match(normalized)  # шаблоны заякорены ^...$
            if not m:
                continue
            matched_len = m.end()
            args_len = sum(len(v) for v in m.groupdict().values())
            score = (matched_len - args_len, matched_len, -order)
            if score > best_score:
                best_score = score
                args = {k: m.group(k).strip() for k in m.groupdict()}
                best = TextMatch(
                    spec=spec, args=args,
                    language=syn.language, pattern=syn.pattern,
                )
    return best
