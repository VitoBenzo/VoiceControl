#!/usr/bin/env python3
"""Голосовые ответы агента (этап 4): основной путь — локальный TTS.

Правила:
- speak() возвращает True только после фактического синтеза/воспроизведения
  (TextToSpeech без исключений);
- если tts недоступен/неуспешен — ошибка логируется, текст показывается в
  консоли как запасной канал, но статус — False (никаких ложных успехов);
- поддерживаются ответы на русском и немецком (выбор голоса по языку).
"""

from __future__ import annotations

import logging
from typing import Optional

from voicecontrol.speech.text_to_speech import TextToSpeech


class VoiceResponse:
    """Отвечает пользователю голосом через локальный синтезатор."""

    def __init__(self, config=None):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.default_language = str(config.get('language', 'ru') if config else 'ru').casefold()
        self.tts: Optional[TextToSpeech] = None
        try:
            self.tts = TextToSpeech(config)
        except Exception as e:  # двойная защита: TextToSpeech сам ловит, но не пропускаем
            self.logger.error("Инициализация TTS в ответчике не удалась: %s", e, exc_info=True)
            self.tts = None

    def speak(self, message: str, language: Optional[str] = None) -> bool:
        """Произносит ответ на указанном языке.

        Возвращает True только при успешном синтезе/воспроизведении.
        """
        lang = language or self.default_language
        self.logger.info("Ответ (язык=%s): %s", lang, message)

        if self.tts is not None and self.tts.available:
            if self.tts.speak(message, lang):
                return True
            self.logger.error("Синтез не удался — сообщение только в консоль")
        else:
            self.logger.error("TTS недоступен — сообщение только в консоль")

        # Запасной канал: показать текст в консоли; успехом это НЕ считается
        try:
            print(f"[Голосовой ответ] {message}")
        except Exception as e:
            self.logger.error("Вывод в консоль тоже не удался: %s", e)
        return False

    def close(self) -> None:
        if self.tts is not None:
            self.tts.close()
