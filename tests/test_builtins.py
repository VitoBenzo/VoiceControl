#!/usr/bin/env python3
"""Тесты каталога MVP-команд (этап 2): области ТЗ, валидаторы, ru/de.

Пути и громкость тестируются без обращений к файловой системе пользователя:
используются пути во временных директориях pytest.
"""

import pytest

from voicecontrol.commands.builtins import (
    make_path_validator, make_volume_validator,
)
from voicecontrol.commands.registry import CommandSpec, CommandRegistry, Synonym


class TestVolumeValidator:
    check = staticmethod(make_volume_validator())

    @pytest.mark.parametrize("value", ["0", "50", "100", "30%"])
    def test_ok(self, value):
        assert self.check(value) is None

    @pytest.mark.parametrize("value", ["", "  ", None, "abc", "-5", "101", "50.5", "50,5", "пять"])
    def test_rejected(self, value):
        assert self.check(value) is not None


class TestPathValidator:
    def test_empty_allowed_dirs_forbids_all(self, tmp_path):
        check = make_path_validator(())
        assert check(str(tmp_path)) is not None  # даже корректный путь запрещён

    def test_inside_allowed(self, tmp_path):
        allowed = [str(tmp_path)]
        check = make_path_validator(allowed)
        p = tmp_path / 'sub'
        p.mkdir()
        assert check(str(p)) is None

    def test_outside_allowed(self, tmp_path):
        allowed_dir = tmp_path / 'allowed'
        allowed_dir.mkdir()
        check = make_path_validator([str(allowed_dir)])
        outside = tmp_path / 'outside'
        outside.mkdir()
        problem = check(str(outside))
        assert problem is not None
        assert 'вне разрешённых' in problem

    @pytest.mark.parametrize("value", [
        r"D:\Data\..\Secret",
        r"D:\Data\..\..\Secret\file.txt",
        "C:/Secrets/../file.txt",
    ])
    def test_dotdot_rejected_explicitly(self, value, tmp_path):
        check = make_path_validator([str(tmp_path)])
        assert check(value) is not None

    def test_relative_rejected(self):
        check = make_path_validator([r"C:\Data"])
        assert check('relative/path.txt') is not None

    def test_empty_rejected(self):
        check = make_path_validator([r"C:\Data"])
        assert check('') is not None
        assert check(None) is not None


class TestCatalog:
    def build(self):
        from voicecontrol.commands.builtins import build_default_registry
        return build_default_registry()

    # Раздел 4.4 ТЗ: только эти категории
    CATALOG_NAMES = (
        'open_app', 'close_app', 'minimize_windows',
        'open_folder', 'open_file', 'set_volume', 'shutdown', 'restart',
    )

    OUT_OF_SCOPE = ('weather', 'light', 'launch_windows', 'system_info')

    def test_exact_catalog(self):
        names = {spec.name for spec in self.build()}
        assert names == set(self.CATALOG_NAMES)
        for legacy in self.OUT_OF_SCOPE:
            assert legacy not in names

    def test_handlers_none_in_stage2(self):
        for spec in self.build():
            assert spec.handler is None, spec.name

    def test_power_commands_dangerous(self):
        r = self.build()
        for name in ('shutdown', 'restart', 'close_app'):
            assert r.get(name).dangerous is True

    def test_every_command_has_ru_and_de(self):
        for spec in self.build():
            langs = {s.language for s in spec.synonyms}
            assert {'ru', 'de'} <= langs, spec.name

    def test_no_legacy_unsupported_phrases(self):
        # Искусственные фразы прежней реализации не совпадают ни с одной командой
        from voicecontrol.commands.parser import match_command, normalize_text
        r = self.build()
        for phrase in ('погаси свет', 'какая погода', 'получи информацию о системе'):
            assert match_command(normalize_text(phrase), r) is None

    def test_legacy_windows_phrase_maps_to_open_app_grammar_only(self):
        # «запусти виндовс» совпадает только с общей грамматикой запуска приложения;
        # фальшивого системного действия нет — белый список этапа 3 отсекёт имя.
        from voicecontrol.commands.parser import match_command, normalize_text
        r = self.build()
        m = match_command(normalize_text('запусти виндовс'), r)
        assert m is not None
        assert m.spec.name == 'open_app'
