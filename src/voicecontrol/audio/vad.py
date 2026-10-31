#!/usr/bin/env python3
"""Определение речевой активности (этап 5): оконный VAD на audioop.rms.

Без NumPy: уровни считаются по окнам int16 через stdlib-пакет audioop-lts.
Единицы порога — нормированный RMS 0.0..1.0, согласованные с
AudioSegment.rms() и config vad.silence_threshold.

Учитываются:
- vad.min_speech_duration — слишком короткие всплески отбрасываются (шум);
- vad.max_silence_duration — пауза такой длины закрывает речевой сегмент.
"""

from __future__ import annotations

import audioop
import logging
from typing import List, Optional, Tuple

from voicecontrol.audio.audio_segment import AudioSegment, SampleWidth

# Окно анализа: 1024 отсчёта int16 (32 мс при 16 кГц) — стандартный VAD-размер
WINDOW_SAMPLES = 1024


class VoiceActivityDetector:
    """Оконный VAD по нормированному RMS; параметры из [vad] конфигурации."""

    def __init__(self, config=None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.silence_threshold = float(
            (config.get('vad.silence_threshold', 0.01) if config else 0.01))
        self.min_speech_duration = float(
            (config.get('vad.min_speech_duration', 0.5) if config else 0.5))
        self.max_silence_duration = float(
            (config.get('vad.max_silence_duration', 1.0) if config else 1.0))

    # ------------------------------------------------------------------ уровни

    def _window_width(self, sample_rate: int) -> int:
        """Размер окна в байтах (WINDOW_SAMPLES int16-отсчётов)."""
        return WINDOW_SAMPLES * SampleWidth

    def _window_rms(self, segment: AudioSegment) -> List[float]:
        """Нормированный RMS каждого окна сегмента (последнее окно — хвост)."""
        levels = []
        width = self._window_width(segment.sample_rate)
        for offset in range(0, len(segment.data), width):
            chunk = segment.data[offset:offset + width]
            rms = audioop.rms(chunk, SampleWidth) / 32768.0
            levels.append(rms)
        return levels

    def _window_seconds(self, sample_rate: int) -> float:
        return WINDOW_SAMPLES / float(sample_rate)

    # ------------------------------------------------------------------- логика

    def detect_speech_bounds(self, segment: AudioSegment) -> Optional[Tuple[float, float]]:
        """Границы первой речной фразы в секундах (start, end) или None, если тишина.

        Фраза начинается, когда окно выше порога, и заканчивается после
        max_silence_duration непрерывной тишины (конец фразы — начало этой паузы).
        Хвост без закрывающей паузы считается до конца сегмента.
        """
        if segment.is_empty:
            return None
        levels = self._window_rms(segment)
        window_sec = self._window_seconds(segment.sample_rate)
        if window_sec <= 0:  # pragma: no cover — sample_rate валиден по построению
            return None

        first_voice = None
        for i, level in enumerate(levels):
            if level > self.silence_threshold:
                first_voice = i
                break
        if first_voice is None:
            return None

        # Ищем окно закрытия: первое окно после first_voice с тишиной длиной
        # >= max_silence_duration
        silent_run = 0
        end_index = len(levels)
        for i in range(first_voice, len(levels)):
            if levels[i] > self.silence_threshold:
                silent_run = 0
            else:
                silent_run += 1
                if silent_run * window_sec >= self.max_silence_duration:
                    end_index = i - silent_run + 1
                    break

        start = first_voice * window_sec
        end = end_index * window_sec
        return (start, end)

    def is_speech(self, segment: AudioSegment) -> bool:
        """Есть ли в сегменте речевая активность (любое окно выше порога)."""
        if segment.is_empty:
            return False
        return any(level > self.silence_threshold for level in self._window_rms(segment))

    def extract_speech(self, segment: AudioSegment) -> Optional[AudioSegment]:
        """Выделяет основную речевую часть сегмента.

        Отбрасывает тишину до/после; возвращает None если:
        - речи нет вовсе, или
        - речь короче min_speech_duration (считается шумом, а не командой).
        """
        bounds = self.detect_speech_bounds(segment)
        if bounds is None:
            return None
        start, end = bounds
        speech = segment.slice_by_seconds(start, end)
        if speech.duration() < self.min_speech_duration:
            self.logger.debug(
                "Речевой фрагмент %.2f с короче min_speech_duration=%.2f с — отброшен",
                speech.duration(), self.min_speech_duration,
            )
            return None
        return speech

    def split_audio_by_speech(self, segment: AudioSegment) -> List[AudioSegment]:
        """Разделяет сегмент на речевые куски (тишина >= max_silence_duration — граница)."""
        if segment.is_empty:
            return []
        levels = self._window_rms(segment)
        window_sec = self._window_seconds(segment.sample_rate)

        result: List[AudioSegment] = []
        speech_start: Optional[int] = None  # индекс окна
        silent_run = 0
        width = self._window_width(segment.sample_rate)

        def cut(end_index: int) -> None:
            nonlocal speech_start
            if speech_start is None:
                return
            piece = AudioSegment(
                segment.data[speech_start * width:end_index * width],
                segment.sample_rate,
            )
            if piece.duration() >= self.min_speech_duration:
                result.append(piece)
            else:
                self.logger.debug("Кусок %.2f с < min_speech_duration — отброшен",
                                  piece.duration())
            speech_start = None

        for i, level in enumerate(levels):
            if level > self.silence_threshold:
                if speech_start is None:
                    speech_start = i
                silent_run = 0
            elif speech_start is not None:
                silent_run += 1
                if silent_run * window_sec >= self.max_silence_duration:
                    cut(i - silent_run + 1)
                    silent_run = 0

        cut(len(levels))  # хвост
        return result
