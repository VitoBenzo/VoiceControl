#!/usr/bin/env python3
"""Тесты локального TTS (этап 4). pyttsx3 полностью мокается:

аудиоустройство и реальные голоса НЕ требуются.
"""

import logging
from unittest.mock import patch

from voicecontrol.speech.text_to_speech import TextToSpeech
from voicecontrol.voice.response import VoiceResponse


class FakeVoice:
    def __init__(self, vid, languages):
        self.id = vid
        self.name = vid
        self.languages = languages


RU_VOICE = FakeVoice('SAPI_RU', ['HKEY_LOCAL_MACHINE\\SOFTWARE\\...ru-RU'])
DE_VOICE = FakeVoice('SAPI_DE', ['HKEY_LOCAL_MACHINE\\SOFTWARE\\...de-DE'])


class FakeEngine:
    def __init__(self, voices=(RU_VOICE, DE_VOICE), fail_on_wait=False):
        self.properties = {}
        self.spoken = []
        self._voices = voices
        self._fail = fail_on_wait
        self.wait_calls = 0

    def setProperty(self, name, value):
        self.properties[name] = value

    def getProperty(self, name):
        if name == 'voices':
            return list(self._voices)
        return self.properties.get(name)

    def say(self, text):
        self.spoken.append(text)

    def runAndWait(self):
        self.wait_calls += 1
        if self._fail:
            raise RuntimeError('audio output failure')

    def stop(self):
        pass


class DictConfig:
    """Простейшая оболочка над dict — как Config.get()."""

    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        return self.data.get(key, default)


def patch_init(engine, raising=False):
    """Подменяет pyttsx3.init на фабрику fake-движка."""
    def factory(driver=None):
        if raising:
            raise RuntimeError('no SAPI voices')
        return engine
    return patch('pyttsx3.init', side_effect=factory)


class TestSpeakByLanguage:
    def test_ru_voice_selected(self):
        engine = FakeEngine()
        with patch_init(engine):
            tts = TextToSpeech(None)
        assert tts.available is True
        assert tts.speak('Привет', 'ru') is True
        assert engine.spoken[-1] == 'Привет'
        assert engine.properties.get('voice') == 'SAPI_RU'
        assert engine.wait_calls == 1  # успех только после фактического воспроизведения

    def test_de_voice_selected(self):
        engine = FakeEngine()
        with patch_init(engine):
            tts = TextToSpeech(None)
        assert tts.speak('Hallo', 'de') is True
        assert engine.properties.get('voice') == 'SAPI_DE'

    def test_unknown_language_uses_default_voice_with_warning(self, caplog):
        engine = FakeEngine()
        with patch_init(engine):
            tts = TextToSpeech(None)
        with caplog.at_level(logging.WARNING, logger='TextToSpeech'):
            ok = tts.speak('blabla', 'fr')
        assert ok is True
        assert any('не найден' in r.message for r in caplog.records)

    def test_explicit_voice_ids_override(self):
        engine = FakeEngine()
        config = DictConfig({
            'language': 'ru',
            'tts.rate': 200,
            'tts.volume': 0.8,
            'tts.voice_ids': {'ru': 'RU_EXPLICIT', 'de': 'DE_EXPLICIT'},
        })
        with patch_init(engine):
            tts = TextToSpeech(config)
        assert tts.speak('Привет', 'ru') is True
        assert engine.properties.get('voice') == 'RU_EXPLICIT'

    def test_missing_voice_fallback_ok(self):
        engine = FakeEngine(voices=())
        with patch_init(engine):
            tts = TextToSpeech(None)
        assert tts.has_voice_for('ru') is False
        assert tts.speak('текст', 'ru') is True  # базовый голос, но синтез выполнен


class TestFailureHonesty:
    def test_init_failure_is_caught_and_available_false(self, caplog):
        with patch_init(None, raising=True):
            tts = TextToSpeech(None)
        assert tts.available is False
        with caplog.at_level(logging.ERROR, logger='TextToSpeech'):
            ok = tts.speak('привет')
        assert ok is False
        assert any('TTS недоступен' in r.message for r in caplog.records)

    def test_run_and_wait_failure_returns_false(self, caplog):
        engine = FakeEngine(fail_on_wait=True)
        with patch_init(engine):
            tts = TextToSpeech(None)
        with caplog.at_level(logging.ERROR, logger='TextToSpeech'):
            ok = tts.speak('Привет', 'ru')
        assert ok is False
        assert any('Ошибка синтеза' in r.message for r in caplog.records)

    def test_empty_text_is_not_success(self):
        engine = FakeEngine()
        with patch_init(engine):
            tts = TextToSpeech(None)
        assert tts.speak('   ') is False
        assert tts.speak(None) is False
        assert engine.spoken == []


class TestVoiceResponseIntegration:
    def test_success_only_after_real_speak(self, monkeypatch):
        engine = FakeEngine()
        with patch_init(engine):
            resp = VoiceResponse(None)
        assert resp.speak('Готово', 'ru') is True
        assert resp.speak('Fertig', 'de') is True

    def test_broken_tts_returns_false_not_fake_success(self, caplog):
        with patch_init(None, raising=True):
            resp = VoiceResponse(None)
        with caplog.at_level(logging.ERROR, logger='VoiceResponse'):
            ok = resp.speak('Готово', 'ru')
        assert ok is False   # печать в консоль не считается успехом
        assert any('недоступен' in r.message for r in caplog.records)
