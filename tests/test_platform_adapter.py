#!/usr/bin/env python3
"""Тесты PlatformAdapter (этап 3). Все системные вызовы — моки subprocess."""

from unittest.mock import patch

import pytest

from voicecontrol.platform_adapter import (
    ActionOutcome, AdapterError, LinuxAdapter, MacOSAdapter, WindowsAdapter,
    create_adapter, run_command,
)


class InvalidArgs:
    """Объект, который не может стать argv-списком без падения."""


class TestFactory:
    @pytest.mark.parametrize("target_os,cls", [
        ("windows", WindowsAdapter),
        ("linux", LinuxAdapter),
        ("macos", MacOSAdapter),
    ])
    def test_creates_adapter(self, target_os, cls):
        adapter = create_adapter(target_os, dry_run=True)
        assert isinstance(adapter, cls)
        assert adapter.dry_run is True

    @pytest.mark.parametrize("target_os", [None, "", "dos", " Windows "])
    def test_unknown_os_rejected(self, target_os):
        # Целевая ОС не угадывается: только явная и валидная
        with pytest.raises(AdapterError):
            create_adapter(target_os, dry_run=True)


class TestRunCommand:
    def test_dry_run_never_calls_subprocess(self):
        # Даже если subprocess сломан — dry-run его не трогает
        with patch('subprocess.run', side_effect=RuntimeError('subprocess must not be called')):
            outcome = run_command(['shutdown', '/s'], dry_run=True)
        assert outcome.success is True
        assert '[dry-run]' in outcome.detail
        assert outcome.detail != 'выполнено'

    def test_success_with_zero_returncode(self):
        fake = FakeResult(returncode=0, stdout='готово', stderr='')
        with patch('subprocess.run', return_value=fake) as run_mock:
            outcome = run_command(['explorer', r'D:\Data'], dry_run=False)
        assert outcome.success is True
        assert 'готово' in outcome.detail

        args, kwargs = run_mock.call_args
        assert isinstance(args[0], list)            # СПИСОК аргументов, не строка
        assert kwargs.get('shell') is False          # shell=False всегда
        assert 'check' in kwargs

    def test_nonzero_returncode_is_failure(self):
        fake = FakeResult(returncode=3, stdout='', stderr='ошибка доступа')
        with patch('subprocess.run', return_value=fake):
            outcome = run_command(['taskkill', '/IM', 'x.exe'], dry_run=False)
        assert outcome.success is False
        assert outcome.detail != ''

    def test_missing_binary_is_failure_not_crash(self):
        with patch('subprocess.run', side_effect=FileNotFoundError('нет файла')):
            outcome = run_command(['definitely-missing-tool'], dry_run=False)
        assert outcome.success is False
        assert 'недоступна' in outcome.detail

    def test_timeout_is_failure(self):
        import subprocess
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='x', timeout=5)):
            outcome = run_command(['slow-tool'], dry_run=False, timeout=5)
        assert outcome.success is False
        assert 'время' in outcome.detail

    def test_no_shell_strings_in_module(self):
        """AST-анализ: нет shell=True, нет вызова с bash -c в адаптере."""
        import ast, inspect
        src = inspect.getsource(__import__(
            'voicecontrol.platform_adapter', fromlist=['x'])
        )
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    assert not (kw.arg == 'shell' and getattr(kw.value, 'value', None) is True), \
                        'найден shell=True'
        assert "'-c'" not in src
        assert '"-c", command' not in src


class FakeResult:
    def __init__(self, returncode, stdout='', stderr='', args=None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.args = args


class TestAdaptersLinMac:
    def test_linux_volume_argv(self):
        adapter = LinuxAdapter(dry_run=False)
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeResult(0, 'ok')) as run_mock:
            outcome = adapter.set_volume(40)
        assert outcome.success is True
        args = run_mock.call_args[0][0]
        assert args == ['amixer', '-D', 'pulse', 'sset', 'Master', '40%']

    def test_mac_volume_argv(self):
        adapter = MacOSAdapter(dry_run=False)
        with patch('voicecontrol.platform_adapter.subprocess.run', return_value=FakeResult(0, 'ok')) as run_mock:
            outcome = adapter.set_volume(25)
        args = run_mock.call_args[0][0]
        assert args == ['osascript', '-e', 'set volume output volume 25']
