#!/usr/bin/env python3
"""Аудиосегмент — общий формат данных аудиоввода (этап 5).

int16 моно rappresentaция в bytes; длительность/RMS вычисляются без NumPy
(stdlib: struct + audioop-lts). Единые единицы: RMS нормирован 0..1,
что согласовано с конфигурацией vad.silence_threshold.
"""

from __future__ import annotations

import audioop
import struct
from typing import Iterable

SampleWidth = 2  # int16


class AudioSegmentFormatError(ValueError):
    """Некорректный сегмент (нецелый размер int16, пустой samples_rate)."""


class AudioSegment:
    """Фрагмент моно-аудио int16 LE."""

    __slots__ = ('data', 'sample_rate')

    def __init__(self, data: bytes, sample_rate: int):
        if not isinstance(data, (bytes, bytearray)):
            raise AudioSegmentFormatError(f"data: ожидались bytes, получено {type(data).__name__}")
        if len(data) % SampleWidth != 0:
            raise AudioSegmentFormatError("bytes данных не кратно размеру int16")
        if not isinstance(sample_rate, int) or sample_rate <= 0:
            raise AudioSegmentFormatError(f"sample_rate некорректен: {sample_rate!r}")
        self.data = bytes(data)
        self.sample_rate = int(sample_rate)

    # ------------------------------------------------------------------ метрика

    def duration(self) -> float:
        """Длительность в секундах."""
        return len(self.data) / (SampleWidth * self.sample_rate)

    def rms(self) -> float:
        """Среднеквадратичный уровень, нормированный 0.0..1.0.

        Единицы согласованы с vad.silence_threshold из конфигурации.
        """
        if not self.data:
            return 0.0
        return audioop.rms(self.data, SampleWidth) / 32768.0

    def samples(self) -> list[int]:
        """int16 отсчёты в списке."""
        return list(struct.unpack(f'<{len(self.data) // SampleWidth}h', self.data))

    @property
    def is_empty(self) -> bool:
        return len(self.data) == 0

    # ------------------------------------------------------------------ нарезка

    def slice_by_seconds(self, start_sec: float, end_sec: float) -> 'AudioSegment':
        """Подсегмент по границам в секундах (за пределами — обрезается)."""
        total = self.duration()
        start = max(0.0, min(start_sec, total))
        end = max(start, min(end_sec, total))
        byte_start = int(start * self.sample_rate) * SampleWidth
        byte_end = int(end * self.sample_rate) * SampleWidth
        return AudioSegment(self.data[byte_start:byte_end], self.sample_rate)

    @classmethod
    def join_frames(cls, frames: Iterable[bytes], sample_rate: int) -> 'AudioSegment':
        """Склейка кадров (bytes) микрофона в сегмент."""
        joined = b''.join(bytes(f) for f in frames)
        return cls(joined, sample_rate)

    def __len__(self) -> int:
        return len(self.data)

    def __repr__(self) -> str:  # pragma: no cover — отладочная
        return f"AudioSegment(seconds={self.duration():.2f}, rate={self.sample_rate}, bytes={len(self.data)})"
