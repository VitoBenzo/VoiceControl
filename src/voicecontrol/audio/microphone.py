#!/usr/bin/env python3
"""Микрофон (этап 5): реальная запись через PyAudio.

Гарантии:
- параметры (sample_rate, chunk_size, channels, device) берутся ТОЛЬКО из
  конфигурации (audio.*), а не угадываются;
- поток открывается/закрывается явно: закрытие — в finally, в том числе при
  ошибке чтения;
- любая ошибка — MicrophoneError (явная), а не тихий None-успех;
- PyAudio может отсутствовать в окружении: ImportError -> MicrophoneError
  с понятной инструкцией (listener деградирует с WARNING, краша нет);
- формат данных — int16 mono, единый с AudioSegment (audio.audio_segment).
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from voicecontrol.audio.audio_segment import AudioSegment

try:  # PyAudio — обязательная зависимость этапа 5, но может не быть собранной
    import pyaudio
except ImportError:  # pragma: no cover — зависит от окружения
    pyaudio = None

_SAMPLE_WIDTH = 2  # int16


class MicrophoneError(RuntimeError):
    """Ошибка аудиоввода: нет PyAudio, нет устройства, запись не удалась."""


class Microphone:
    """Запись аудио с устройства ввода через PyAudio (int16, mono по умолчанию)."""

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

        self.sample_rate = int(config.get('audio.sample_rate', 16000))
        self.chunk_size = int(config.get('audio.chunk_size', 1024))
        self.channels = int(config.get('audio.channels', 1))
        self.device = config.get('audio.device', None)  # None = системный по умолчанию
        if self.device is not None and int(self.device) < 0:
            self.device = None

        if pyaudio is None:
            raise MicrophoneError(
                "PyAudio не установлен: установите пакет (pip install PyAudio) "
                "или extras 'voicecontrol[audio]'. Аудиоввод недоступен."
            )

        try:
            self.audio = pyaudio.PyAudio()
        except Exception as e:
            self.logger.error("Ошибка инициализации PyAudio: %s", e, exc_info=True)
            raise MicrophoneError(f"Инициализация PyAudio не удалась: {e}") from e

        self._closed = False

    # ---------------------------------------------------------------- состояние

    @property
    def available(self) -> bool:
        return pyaudio is not None and not self._closed and getattr(self, 'audio', None) is not None

    def device_count(self) -> int:
        """Число доступных аудиоустройств (для диагностики)."""
        try:
            return int(self.audio.get_device_count())
        except Exception as e:  # pragma: no cover — зависит от драйвера
            self.logger.error("Не удалось получить список устройств: %s", e)
            return 0

    # -------------------------------------------------------------------- запись

    def _open_stream(self):
        kwargs = dict(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )
        if self.device is not None:
            kwargs['input_device_index'] = int(self.device)
        return self.audio.open(**kwargs)

    def record_audio(self, duration: float) -> AudioSegment:
        """Записывает `duration` секунд и возвращает AudioSegment (int16).

        Ошибки — MicrophoneError; поток закрывается в finally.
        """
        duration = float(duration)
        if duration <= 0:
            raise MicrophoneError(f"Длительность записи должна быть > 0, получено {duration!r}")
        if not self.available:
            raise MicrophoneError("Микрофон недоступен (PyAudio не инициализирован или закрыт)")

        frames: List[bytes] = []
        total_frames = max(1, int(self.sample_rate * duration / self.chunk_size))

        stream = None
        try:
            stream = self._open_stream()
            self.logger.debug(
                "Запись: %.2fs, rate=%s, chunk=%s, channels=%s, device=%s",
                duration, self.sample_rate, self.chunk_size, self.channels, self.device,
            )
            for _ in range(total_frames):
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
        except OSError as e:
            self.logger.error("Ошибка записи с микрофона: %s", e, exc_info=True)
            raise MicrophoneError(f"Запись с микрофона не удалась: {e}") from e
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                except Exception as e:  # pragma: no cover
                    self.logger.error("Ошибка остановки потока: %s", e)
                try:
                    stream.close()
                except Exception as e:  # pragma: no cover
                    self.logger.error("Ошибка закрытия потока: %s", e)

        segment = AudioSegment.join_frames(frames, self.sample_rate)
        self.logger.info("Записано %.2f с аудио (%d байт)", segment.duration(), len(segment))
        return segment

    def close(self) -> None:
        """Освобождает PyAudio (вызывается при завершении, этап 7)."""
        if getattr(self, 'audio', None) is not None and not self._closed:
            try:
                self.audio.terminate()
                self.logger.info("Микрофон освобождён")
            except Exception as e:  # pragma: no cover — зависит от драйвера
                self.logger.error("Ошибка освобождения PyAudio: %s", e)
            finally:
                self._closed = True
