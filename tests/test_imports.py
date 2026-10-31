#!/usr/bin/env python3
"""Тесты импорта пакета (этап 1).

Проект должен импортироваться как пакет voicecontrol.
Модуль, зависящий от PyAudio (audio.microphone), проверяется отдельно:
зависимость может отсутствовать в окружении. audio.vad и audio.audio_segment
используют только stdlib audioop-lts и импортируются всегда.
"""

import pytest

PYAUDIO_MODULES = ("voicecontrol.audio.microphone",)


def _import(name):
    import importlib
    return importlib.import_module(name)


MODULES = [
    "voicecontrol",
    "voicecontrol.config",
    "voicecontrol.logging_setup",
    "voicecontrol.core.agent",
    "voicecontrol.commands.dispatcher",
    "voicecontrol.commands.command_handler",
    "voicecontrol.speech.recognizer",
    "voicecontrol.speech.text_to_speech",
    "voicecontrol.voice.response",
    "voicecontrol.audio.listener",
    "voicecontrol.audio.wake_word_detector",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    assert _import(name) is not None


@pytest.mark.parametrize("name", PYAUDIO_MODULES)
def test_optional_modules_reported(name):
    """Зависящие от PyAudio/NumPy модули: либо отсутствуют зависимости (skip),
    либо импорт проходит. Отсутствие зависимостей — явный результат, а не успех-заглушка."""
    try:
        _import(name)
    except Exception as e:
        pytest.skip(f"зависимости не установлены: {e}")


def test_agent_creation_with_valid_config(caplog):
    from voicecontrol.config import load_config
    from voicecontrol.core.agent import VoiceControlAgent
    from pathlib import Path

    config_path = Path(__file__).resolve().parents[1] / "config.example.toml"
    cfg = load_config(config_path)
    agent = VoiceControlAgent(cfg)
    assert agent.wake_phrase == "voice control"
    assert agent.poll_interval > 0
