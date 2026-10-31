#!/usr/bin/env python3
"""Тест безопасности (этап 1): произвольный ввод НЕ вызывает subprocess.

Доказывает, что путь произвольного shell-выполнения удалён из
CommandHandler.execute_command: любой вход (в т.ч. распознанный текст)
возвращает отказ и не порождает системных процессов.
"""

from unittest.mock import patch

from voicecontrol.commands.command_handler import CommandHandler

UNSAFE_INPUTS = [
    "rm -rf /",
    "del C:\\Windows\\System32",
    "format c:",
    "start chrome",            # даже «непослушная» корректная команда не выполняется
    "",
]


def make_handler():
    # Конфигурация не используется обработчиком напрямую
    return CommandHandler({})


def test_execute_command_never_calls_subprocess():
    for text in UNSAFE_INPUTS:
        handler = make_handler()
        with patch("subprocess.run") as run_mock, patch("subprocess.Popen") as popen_mock:
            result = handler.execute_command(text)
            run_mock.assert_not_called()
            popen_mock.assert_not_called()
            assert result["success"] is False
            assert result["returncode"] != 0


def test_response_carries_stage3_message():
    result = make_handler().execute_command("любой текст")
    assert "PlatformAdapter" in result["error"]


def test_environment_config_documented():
    """Конфиг должен содержать секцию безопасности (задаётся явно пользователем)."""
    from pathlib import Path
    example = Path(__file__).resolve().parents[1] / "config.example.toml"
    text = example.read_text(encoding="utf-8")
    assert "app_whitelist" in text
    assert "allowed_dirs" in text


def test_get_system_info_does_not_spawn_processes():
    from unittest.mock import patch as _patch
    handler = make_handler()
    with _patch("subprocess.run") as run_mock:
        result = handler.get_system_info()
        run_mock.assert_not_called()
        assert result["success"] is True
        assert "os" in result["output"]


def test_no_shell_apis_in_code():
    """AST-анализ: нет вызовов с shell=True и нет ссылок на модуль subprocess."""
    import ast
    import inspect
    from voicecontrol.commands import command_handler

    source = inspect.getsource(command_handler)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                assert kw.arg != "shell", "найден вызов с shell=True"

    assert "import subprocess" not in source
    assert "subprocess." not in source
