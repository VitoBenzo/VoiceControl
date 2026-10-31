#!/usr/bin/env python3
"""Тесты обработчиков ОС (этап 3): белый список, allowed_dirs, подтверждения.

Реальные системные операции НЕ выполняются: dry_run=True или subprocess в моках.
"""

from unittest.mock import patch

import pytest

from voicecontrol.commands.dispatcher import CommandDispatcher
from voicecontrol.commands.os_handlers import build_os_registry
from voicecontrol.config import ConfigError

NOTEPAD = r'C:\Windows\System32\notepad.exe'


def make_config(**overrides):
    data = {
        'security.target_os': 'windows',
        'security.dry_run': True,
        'security.app_whitelist': {'notepad': NOTEPAD},
        'security.allowed_dirs': [],
        'language': 'ru',
        'security.confirmation_required': True,
        'security.confirmation_timeout': 10.0,
    }
    data.update(overrides)

    class C:
        def get(self, key, default=None):
            return data.get(key, default)

    return C()


class FakeOK:
    returncode = 0
    stdout = ''
    stderr = ''


class FakeFail:
    returncode = 1
    stdout = ''
    stderr = 'Отказано в доступе'


def build_dispatcher(config):
    """Диспетчер на ОС-реестре, построенном из ЭТОГО ЖЕ конфига (важно для allowed_dirs)."""
    return CommandDispatcher(build_os_registry(config), config)


class TestBuildContext:
    def test_target_os_required_not_guessed(self):
        # Без явного target_os построение реестра невозможно (ОС не угадывается кодом)
        with pytest.raises(ConfigError, match='target_os'):
            build_os_registry(make_config(**{'security.target_os': None}))

    def test_registry_has_real_handlers(self):
        registry = build_os_registry(make_config())
        for spec in registry:
            assert callable(spec.handler), spec.name
        # только каталог MVP
        assert {s.name for s in registry} == {
            'open_app', 'close_app', 'minimize_windows', 'open_folder',
            'open_file', 'set_volume', 'shutdown', 'restart',
        }

    def test_dangerous_flags_kept(self):
        registry = build_os_registry(make_config())
        for name in ('close_app', 'shutdown', 'restart'):
            assert registry.get(name).dangerous is True


class TestWhitelist:
    def test_unknown_app_never_executes(self):
        config = make_config(**{'security.dry_run': False})
        with patch('subprocess.run') as run_mock:
            result = build_dispatcher(config).dispatch('открой страшный вирус')
        assert result.success is False
        assert 'белом списке' in result.message
        run_mock.assert_not_called()  # главный тест безопасности

    def test_case_insensitive_whitelist_resolution(self):
        config = make_config(**{'security.dry_run': False})
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeOK()) as run_mock:
            result = build_dispatcher(config).dispatch('ОТКРОЙ NOTEPAD')
        assert result.success is True
        argv = run_mock.call_args[0][0]
        assert argv == [NOTEPAD]                      # путь из белого списка, не из текста
        assert run_mock.call_args[1]['shell'] is False

    def test_real_mode_launch_success(self):
        config = make_config(**{'security.dry_run': False})
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeOK()) as run_mock:
            result = build_dispatcher(config).dispatch('открой notepad')
        assert result.success is True
        assert run_mock.call_args[0][0] == [NOTEPAD]

    def test_real_mode_launch_failure_reported(self):
        # Ошибка действия возвращается как отказ, а не ложный успех
        config = make_config(**{'security.dry_run': False})
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeFail()):
            result = build_dispatcher(config).dispatch('открой notepad')
        assert result.success is False
        assert 'не выполнен' in result.message


class TestFilesystem:
    def make_fs_config(self, allowed_dir, **extra):
        return make_config(**{'security.allowed_dirs': [str(allowed_dir)], **extra})

    def test_folder_inside_allowed(self, tmp_path):
        target = tmp_path / 'sub'
        target.mkdir()
        config = self.make_fs_config(tmp_path, **{'security.dry_run': False})
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeOK()) as run_mock:
            result = build_dispatcher(config).dispatch(f'открой папку {target}')
        assert result.success is True
        argv = run_mock.call_args[0][0]
        assert argv[0] == 'explorer'
        assert str(target).lower() == str(argv[1]).lower()

    def test_folder_outside_allowed_refused(self, tmp_path):
        allowed = tmp_path / 'allowed'
        allowed.mkdir()
        outsider = tmp_path / 'outsider'
        outsider.mkdir()
        config = self.make_fs_config(allowed)
        with patch('subprocess.run') as run_mock:
            result = build_dispatcher(config).dispatch(f'открой папку {outsider}')
        assert result.success is False
        assert 'вне разрешённых' in result.message
        run_mock.assert_not_called()

    def test_traversal_refused(self, tmp_path):
        config = self.make_fs_config(tmp_path)
        with patch('subprocess.run') as run_mock:
            result = build_dispatcher(config).dispatch(r'открой файл D:\Data\..\Секретное\file.txt')
        assert result.success is False
        run_mock.assert_not_called()

    def test_empty_allowed_dirs_forbids_fs(self, tmp_path):
        config = make_config()
        with patch('subprocess.run') as run_mock:
            result = build_dispatcher(config).dispatch(f'открой папку {tmp_path}')
        assert result.success is False
        assert 'разреш' in result.message or 'запрещены' in result.message
        run_mock.assert_not_called()


class TestDangerousWithRealHandlers:
    def test_shutdown_confirmed_dry_run(self):
        config = make_config()
        d = build_dispatcher(config)
        result = d.dispatch('выключи компьютер', lambda prompt, timeout: 'да')
        # dry_run=True: подпроцессы не вызываются, сообщение честно описывает действие
        assert result.success is True
        assert '[dry-run]' in result.message

    def test_shutdown_refused_cancels(self):
        config = make_config()
        d = build_dispatcher(config)
        result = d.dispatch('выключи компьютер', lambda prompt, timeout: 'нет')
        assert result.success is False
        assert 'отменено' in result.message

    def test_close_app_requires_confirmation(self):
        config = make_config()
        d = build_dispatcher(config)
        result = d.dispatch('закрой notepad')  # без провайдера — отмена
        assert result.success is False
        assert 'отменено' in result.message

    def test_set_volume_no_confirm_needed(self):
        config = make_config()
        d = build_dispatcher(config)
        with patch('subprocess.run') as run_mock:
            result = d.dispatch('громкость 45')
        assert result.success is True
        # Windows pycaw путь в dry-run не трогает subprocess — он не вызывается
        run_mock.assert_not_called()
        assert '45' in result.message
