#!/usr/bin/env python3
"""Прослушивание микрофона (этап 5): реальная запись команды через Microphone.

Гарантии:
- запись цикла «речь → тишина»: сегмент закрывается по VAD
  (max_silence_duration) либо по лимиту audio.max_record_seconds;
- случайных данных нет: успех возвращается только при фактической записи
  с речевой активностью;
- PyAudio отсутствует -> доступность False с WARNING (деградация, не краш);
- wake phrase (ключевая фраза) реализуется на этапе 7: метод явно
  заявляет NotImplementedError, никаких имитаций.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from voicecontrol.audio.audio_segment import AudioSegment
from voicecontrol.audio.microphone import Microphone, MicrophoneError
from voicecontrol.audio.vad import VoiceActivityDetector


class AudioListener:
    """Запись команд пользователя: Microphone (PyAudio) + VoiceActivityDetector."""

    def __init__(self, config, *, microphone: Optional[Microphone] = None):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_record_seconds = float(config.get('audio.max_record_seconds', 10.0))

        self.vad = VoiceActivityDetector(config)
        self.microphone: Optional[Microphone] = None

        if microphone is not None:  # инъекция (тесты/тестовый режим)
            self.microphone = microphone
        else:
            try:
                self.microphone = Microphone(config)
            except MicrophoneError as e:
                self.microphone = None
                self.logger.warning(
                    "Микрофон недоступен, аудиоввод деактивирован: %s", e)

    @property
    def available(self) -> bool:
        return self.microphone is not None and self.microphone.available

    # ------------------------------------------------------------- активация

    def wait_for_wake_phrase(self, wake_phrase: str) -> bool:
        """Ждёт ключевую фразу активации.

        Этап 7: потоковая запись + сопоставление фразы. До этого момента
        production-цикл заблокирован в main.py, а метод честно требует реализации.
        """
        raise NotImplementedError(
            "wait_for_wake_phrase: распознавание ключевой фразы реализуется "
            "на этапе 7 (сквозной цикл)."
        )

    # ---------------------------------------------------------------- запись

    def record_command(self) -> Optional[AudioSegment]:
        """Записывает одну голосовую команду; возвращает AudioSegment с речью.

        Логика: запись до паузы тишины (VAD) либо до max_record_seconds;
        тишина/шум/ошибка устройства -> None (не успех).

        Raises:
            MicrophoneError — только если доступность была заявлена, но запись
            не удалась (ошибка устройства на середине).
        """
        if not self.available:
            self.logger.info("Запись команды невозможна: микрофон недоступен")
            return None

        self.logger.info("Запись команды началась (лимит %.1f с)", self.max_record_seconds)
        started = time.monotonic()
        frames: list[bytes] = []   # накопленные «сырые» кадры
        chunk = self.microphone.chunk_size
        sr = self.microphone.sample_rate

        try:
            with _StreamingRecorder(self.microphone) as microphone:
                while True:
                    offset = time.monotonic() - started
                    if offset >= self.max_record_seconds:
                        self.logger.info("Достигнут лимит записи (%.1f с)", self.max_record_seconds)
                        break
                    frame = microphone.read_chunk()
                    frames.append(frame)
                    # Проверка тишины по уже накопленному хвосту
                    tail = AudioSegment.join_frames(frames[-8:], sr)
                    if not self.vad.is_speech(tail) and tail.duration() >= self.vad.max_silence_duration:
                        if _has_speech(self.vad, AudioSegment.join_frames(frames, sr)):
                            self.logger.info("Пауза тишины после речи — запись завершена")
                            break
        except MicrophoneError as e:
            self.logger.error("Запись команды не удалась: %s", e, exc_info=True)
            if frames:
                # Частичная запись — не выдаём её как команду; честный отказ
                return None
            return None

        segment = AudioSegment.join_frames(frames, sr)
        speech = self.vad.extract_speech(segment)
        if speech is None:
            self.logger.info("Речь не обнаружена (тишина или слишком короткий звук) — не команда")
            return None
        self.logger.info("Записана команда: %.2f с речи", speech.duration())
        return speech

    def close(self) -> None:
        if self.microphone is not None:
            self.microphone.close()


def _has_speech(vad: VoiceActivityDetector, segment: AudioSegment) -> bool:
    """Есть ли РЕЧЬ в накопленном материале (не только текущий хвост тишины)."""
    bounds = vad.detect_speech_bounds(segment)
    if bounds is None:
        return False
    start, end = bounds
    return (end - start) >= vad.min_speech_duration


class _StreamingRecorder:
    """Держит открытый поток микрофона между кадрами (закрытие в finally)."""

    def __init__(self, microphone: Microphone):
        self._microphone = microphone
        self._stream = microphone._open_stream()

    def read_chunk(self) -> bytes:
        try:
            return self._stream.read(self._microphone.chunk_size, exception_on_overflow=False)
        except OSError as e:
            raise MicrophoneError(f"Чтение потока не удалось: {e}") from e

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self._stream.stop_stream()
        except Exception:  # pragma: no cover
            pass
        self._stream.close()
        return False
