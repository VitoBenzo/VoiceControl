#!/usr/bin/env python3
"""
Основной класс голосового агента.
Отвечает за координацию всех компонентов и выполнение основного цикла работы.

Этап 1 (ограничение): AudioListener/SpeechRecognizer всё ещё содержат случайные
тестовые адаптеры — они будут заменены на реальные компоненты на этапах 5-7.
Добавлено ограниченное ожидание между попытками (poll_interval), чтобы цикл
не создавал активную нагрузку и не генерировал бесконечный поток логов.
"""

import logging
import time
from typing import Optional

from voicecontrol.config import Config
from voicecontrol.audio.listener import AudioListener
from voicecontrol.speech.recognizer import SpeechRecognizer
from voicecontrol.commands.dispatcher import CommandDispatcher
from voicecontrol.voice.response import VoiceResponse


class VoiceControlAgent:
    """Голосовой агент для управления компьютером по голосовым командам."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        # Инициализация компонентов
        self.listener = AudioListener(config)
        self.recognizer = SpeechRecognizer(config)
        from voicecontrol.commands.os_handlers import build_os_registry
        self.dispatcher = CommandDispatcher(build_os_registry(config), config)
        self.response = VoiceResponse(config)

        # Загрузка ключевой фразы из конфига
        self.wake_phrase = config.get('wake_phrase', 'voice control')
        # Ограниченное ожидание между попытками сек/запуск без события
        self.poll_interval = float(config.get('loop.poll_interval', 0.5))
        self._running = False
        self.logger.info(
            "Инициализация агента с ключевой фразой: %s (poll_interval=%.2fs)",
            self.wake_phrase, self.poll_interval,
        )

    def stop(self) -> None:
        """Плавная остановка основного цикла."""
        self._running = False

    def run(self):
        """Основной цикл работы агента."""
        self.logger.info("Запуск основного цикла агента")
        self._running = True
        try:
            while self._running:
                try:
                    # Ожидание ключевой фразы
                    self.logger.info("Ожидание ключевой фразы...")
                    if self.listener.wait_for_wake_phrase(self.wake_phrase):
                        self.logger.info("Ключевая фраза '%s' обнаружена", self.wake_phrase)

                        # Запись команды
                        audio_data = self.listener.record_command()
                        if audio_data:
                            # Распознавание речи
                            text = self.recognizer.recognize(audio_data)
                            if text:
                                self.logger.info("Распознан текст: %s", text)

                                # Диспетчеризация команды
                                result = self.dispatcher.dispatch(text)
                                self.logger.info("Результат выполнения команды: %s", result)

                                # Голосовой ответ
                                self.response.speak(result.message, result.language)
                            else:
                                error_msg = "Не удалось распознать речь"
                                self.logger.warning(error_msg)
                                self.response.speak(error_msg, self.config.get('language', 'ru'))
                        else:
                            error_msg = "Ошибка при записи команды"
                            self.logger.error(error_msg)
                            self.response.speak(error_msg, self.config.get('language', 'ru'))
                    else:
                        # Ожидание без активной нагрузки между попытками
                        time.sleep(self.poll_interval)

                except KeyboardInterrupt:
                    self.logger.info("Принудительная остановка агента")
                    break
                except Exception as e:
                    self.logger.error("Ошибка в основном цикле: %s", e, exc_info=True)
                    # Ограниченная пауза после ошибки вместо активного цикла
                    time.sleep(self.poll_interval)
        finally:
            self._running = False
            self.logger.info("Основной цикл агента остановлен")
