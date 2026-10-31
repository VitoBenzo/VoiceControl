#!/usr/bin/env python3
"""Локальный синтез речи (pyttsx3) — рабочий путь агента (этап 4).

Гарантии:
- интерфейс speak(text, language) — русский и немецкий;
- голос выбирается по языку (или задаётся явно в tts.voice_ids);
- Ошибка инициализации/синтеза/воспроизведения логируется явно;
  успеха return False. Финальный успех только после фактического
  engine.runAndWait() без исключений (фиктивных успехов нет);
- unit-тесты полностью мокают pyttsx3 и не требуют аудиоустройства.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Optional

# Подстрочные признаки языковых кодов в свойствах голосов (SAPI/pyttsx3)
_LANG_HINTS = {
    'ru': ('ru', 'russian'),
    'de': ('de', 'german', 'deutsch'),
}


def _voice_signature(voice: Any) -> str:
    """Конкатенирует ключевые поля голоса в одну нижнюю строку для поиска."""
    parts = []
    for attr in ('id', 'name', 'languages', 'gender'):
        value = getattr(voice, attr, None)
        if isinstance(value, (list, tuple)):
            parts.extend(str(x) for x in value)
        elif value is not None:
            parts.append(str(value))
    return ' '.join(parts).casefold()


class TextToSpeech:
    """Оболочка над pyttsx3 с выбором голоса по языку и честными ошибками."""

    def __init__(self, config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rate = int((config.get('tts.rate', 190) if config else 190))
        self.volume = float((config.get('tts.volume', 1.0) if config else 1.0))
        self.default_language = str((config.get('language', 'ru') if config else 'ru')).casefold()
        voice_ids = dict((config.get('tts.voice_ids', {}) if config else {}) or {})
        self.voice_ids = {k.casefold(): v for k, v in voice_ids.items()}

        self.engine = None
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
        except Exception as e:
            self.logger.error("Ошибка инициализации TTS: %s", e, exc_info=True)
            return

        try:
            self.apply_defaults()
        except Exception as e:
            self.logger.error("Ошибка применения настроек TTS: %s", e, exc_info=True)
            self.engine = None
            return

        self.logger.info("TTS готов (rate=%s, volume=%.2f, дефолтный язык=%s)",
                         self.rate, self.volume, self.default_language)

    # ------------------------------------------------------------- состояние

    @property
    def available(self) -> bool:
        return self.engine is not None

    def apply_defaults(self) -> None:
        self.engine.setProperty('rate', self.rate)
        self.engine.setProperty('volume', self.volume)

    def _voices(self) -> list:
        try:
            return list(self.engine.getProperty('voices') or [])
        except Exception as e:
            self.logger.error("Не удалось прочитать список голосов: %s", e)
            return []

    def available_voices(self) -> list:
        """Список голосов {id,name,languages}; основа для проверки доступности ru/de."""
        result = []
        for voice in self._voices():
            langs = getattr(voice, 'languages', None)
            result.append({
                'id': getattr(voice, 'id', ''),
                'name': getattr(voice, 'name', ''),
                'languages': list(langs) if isinstance(langs, (list, tuple)) else langs,
            })
        return result

    def _pick_voice_id(self, language: Optional[str]) -> Optional[str]:
        lang = str(language or self.default_language).casefold()[:2]
        explicit = self.voice_ids.get(lang) or self.voice_ids.get(str(language or self.default_language).casefold())
        if explicit:
            return explicit
        hints = _LANG_HINTS.get(lang)
        if not hints:
            return None
        available = self._voices()
        for voice in available:
            sig = _voice_signature(voice)
            for hint in hints:
                if hint in sig:
                    return getattr(voice, 'id', None)
        return None

    def has_voice_for(self, language: str) -> bool:
        """Есть ли установленный голос для указанного языка (для диагностики ru/de)."""
        return self._pick_voice_id(language) is not None

    # ------------------------------------------------------------------ речь

    def speak(self, text, language: Optional[str] = None) -> bool:
        """Произносит текст. True только после успешного runAndWait."""
        if not isinstance(text, str) or not text.strip():
            self.logger.warning("Пустой текст ответа — синтез не выполнен")
            return False
        if self.engine is None:
            self.logger.error("TTS недоступен (инициализация не удалась) — речь не синтезирована")
            return False

        try:
            voice_id = self._pick_voice_id(language)
            if voice_id:
                self.engine.setProperty('voice', voice_id)
            else:
                self.logger.warning(
                    "Голос для языка '%s' не найден — используется базовый голос", language,
                )
            self.apply_defaults()
            self.engine.say(text)
            self.engine.runAndWait()
            self.logger.info("Ответ произнесён (%s): %s", language, text)
            return True
        except Exception as e:
            self.logger.error("Ошибка синтеза/воспроизведения: %s", e, exc_info=True)
            return False

    def save_to_file(self, text: str, filename: str) -> bool:
        """Синтез в WAV-файл (для тестов/записи). True только при успехе."""
        if self.engine is None or not isinstance(text, str) or not text.strip():
            self.logger.error("Синтез в файл невозможен (TTS недоступен или текст пуст)")
            return False
        try:
            self.engine.save_to_file(text, filename)
            self.engine.runAndWait()
            self.logger.info("Аудио сохранено: %s", filename)
            return True
        except Exception as e:
            self.logger.error("Ошибка сохранения аудио: %s", e, exc_info=True)
            return False

    def close(self) -> None:
        """Остановка движка (корректное освобождение — этап 7)."""
        if self.engine is not None:
            try:
                self.engine.stop()
            except Exception as e:  # pragma: no cover — зависит от драйвера SAPI
                self.logger.error("Ошибка остановки TTS: %s", e)
