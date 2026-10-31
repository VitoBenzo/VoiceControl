#!/usr/bin/env python3
"""Тесты нормализации и разбора команд (этап 2)."""

import pytest

from voicecontrol.commands.builtins import build_default_registry
from voicecontrol.commands.parser import (
    compile_synonym, match_command, normalize_text, placeholder_names,
)

REGISTRY = build_default_registry()


class TestNormalize:
    def test_case_and_spaces(self):
        assert normalize_text('  ОТКРОЙ   БРАУЗЕР  ') == 'открой браузер'

    def test_punctuation_removed(self):
        assert normalize_text('Выключи, компьютер!') == 'выключи компьютер'
        assert normalize_text('«Перезагрузка».') == 'перезагрузка'

    def test_typographic_spaces(self):
        assert normalize_text('\u00a0выключи\u00a0компьютер') == 'выключи компьютер'

    def test_casefold_umlauts(self):
        assert normalize_text('ÖFFNE NOTIZBLOCK') == 'öffne notizblock'

    def test_none_and_empty(self):
        assert normalize_text(None) == ''
        assert normalize_text('   ') == ''


class TestCompileSynonym:
    def test_placeholder_names(self):
        assert placeholder_names('открой {app}') == ('app',)
        assert placeholder_names('нет аргументов') == ()

    @pytest.mark.parametrize(
        "pattern,text,args",
        [
            ('открой {app}', 'открой блокнот', {'app': 'блокнот'}),
            ('громкость {level}', 'громкость 50', {'level': '50'}),
        ],
    )
    def test_matches(self, pattern, text, args):
        m = compile_synonym(pattern).match(text)
        assert m is not None
        assert {k: m.group(k) for k in args} == args

    def test_placeholder_requires_value(self):
        assert compile_synonym('открой {app}').match('открой ') is None

    def test_fixed_phrase_anchors(self):
        # «выключи компьютер через час» НЕ совпадает с фиксированной фразой
        assert compile_synonym('выключи компьютер').match('выключи компьютер через час') is None


class TestMatchCommand:
    def test_ru_synonym(self):
        m = match_command(normalize_text('Открой, блокнот'), REGISTRY)
        assert m is not None
        assert m.spec.name == 'open_app'
        assert m.language == 'ru'
        assert m.args == {'app': 'блокнот'}

    def test_de_synonym(self):
        m = match_command(normalize_text('Öffne Notizblock'), REGISTRY)
        assert m is not None
        assert m.spec.name == 'open_app'
        assert m.language == 'de'
        assert m.args == {'app': 'notizblock'}

    def test_fixed_command(self):
        m = match_command(normalize_text('Перезагрузка'), REGISTRY)
        assert m is not None
        assert m.spec.name == 'restart'
        assert m.args == {}

    def test_synonym_variants(self):
        for phrase, name in [
            ('запусти калькулятор', 'open_app'),
            ('закрой блокнот', 'close_app'),
            ('сверни все окна', 'minimize_windows'),
            ('установи громкость 30', 'set_volume'),
            ('выключи компьютер', 'shutdown'),
            ('fahr herunter', 'shutdown'),
            ('starte neu', 'restart'),
            ('lautstärke 40', 'set_volume'),
            ('minimiere alle fenster', 'minimize_windows'),
        ]:
            m = match_command(normalize_text(phrase), REGISTRY)
            assert m is not None, phrase
            assert m.spec.name == name, phrase

    def test_no_match(self):
        assert match_command(normalize_text('сделай мне кофе'), REGISTRY) is None
        assert match_command(normalize_text('погаси свет'), REGISTRY) is None  # вне ТЗ
        assert match_command(normalize_text('какая погода'), REGISTRY) is None  # вне ТЗ

    def test_empty(self):
        assert match_command('', REGISTRY) is None

    def test_arg_value_path_syntax_preserved(self):
        """Аргумент пути: разделители и расширение сохраняются (символы :\\.  и /).

        Регистр — нижний (casefold нормализации); пути Windows нечувствительны к регистру.
        """
        m = match_command(normalize_text('открой файл C:\\Data\\Report.TXT'), REGISTRY)
        assert m is not None
        assert m.spec.name == 'open_file'
        assert m.args['path'] == r'c:\data\report.txt'

    def test_folder_beats_generic_open(self):
        """Специфичный шаблон «открой папку X» полон общего «открой X»."""
        m = match_command(normalize_text('открой папку доп материалы'), REGISTRY)
        assert m is not None
        assert m.spec.name == 'open_folder'
        assert m.args == {'path': 'доп материалы'}
