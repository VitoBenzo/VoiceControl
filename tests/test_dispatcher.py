#!/usr/bin/env python3
"""Тесты диспетчера: совпадения, аргументы, отказы, подтверждения (этап 2).

Проверяются гарантии чеклиста: неизвестная команда не вызывает обработчик,
валидация до выполнения, подтверждение опасных действий, честные отказы.
"""

from typing import List, Tuple

import pytest

from voicecontrol.commands.builtins import build_default_registry
from voicecontrol.commands.confirmation import ConfirmationTimeout
from voicecontrol.commands.dispatcher import CommandDispatcher
from voicecontrol.commands.registry import CommandRegistry, CommandResult, CommandSpec, Synonym


def make_config(language='ru', confirmation=True, timeout=10.0):
    class C:
        def get(self, key, default=None):
            return {
                'language': language,
                'security.confirmation_required': confirmation,
                'security.confirmation_timeout': timeout,
            }.get(key, default)
    return C()


def make_dispatcher(handler=None, dangerous=False, **cfg_kwargs):
    r = CommandRegistry()
    if handler is not None:
        r.register(CommandSpec(
            name='test_cmd',
            synonyms=[Synonym('ru', 'сделай вещь'), Synonym('de', 'mache die sache')],
            handler=handler,
            dangerous=dangerous,
        ))
    else:
        r.register(CommandSpec(
            name='test_cmd',
            synonyms=[Synonym('ru', 'сделай вещь'), Synonym('de', 'mache die sache')],
        ))
    return CommandDispatcher(r, make_config(**cfg_kwargs))


class TestMatchingAndArgs:
    def test_handler_called_with_args(self):
        calls = []

        def handler(args):
            calls.append(dict(args))
            return CommandResult(True, 'done')

        d = make_dispatcher(handler)
        result = d.dispatch('Сделай вещь')
        assert result.success is True
        assert calls == [{}]

        result = d.dispatch('Mache die sache')
        assert result.success is True
        assert len(calls) == 2

    def test_dispatcher_own_message_follows_phrase_language(self):
        """Собственные сообщения диспетчера — на языке распознанной фразы (de)."""
        d = make_dispatcher(handler=None)
        result = d.dispatch('Mache die sache')
        assert result.success is False
        assert result.language == 'de'

    def test_unknown_command_refused_no_handler(self):
        calls = []

        def handler(args):
            calls.append(args)
            return CommandResult(True, 'ok')

        d = make_dispatcher(handler)
        result = d.dispatch('купи хлеб')
        assert result.success is False
        assert 'Неизвестная' in result.message
        assert calls == []  # доказательство: действие не вызвано

    def test_empty_input_refused(self):
        d = make_dispatcher(lambda a: CommandResult(True, 'x'))
        for text in ('   ', None, ''):
            result = d.dispatch(text)
            assert result.success is False

    def test_handler_missing_is_honest_failure(self):
        d = make_dispatcher(handler=None)
        result = d.dispatch('сделай вещь')
        assert result.success is False
        assert 'этап 3' in result.message


class TestValidation:
    def make_arg_dispatcher(self, validator):
        r = CommandRegistry()
        r.register(CommandSpec(
            name='open_thing',
            synonyms=[Synonym('ru', 'открой {thing}')],
            validators={'thing': validator},
        ))
        return CommandDispatcher(r, make_config()), r

    def test_validator_rejects_before_handler(self):
        calls = []

        def handler(args):
            calls.append(args)
            return CommandResult(True, 'ok')

        def bad_validator(value):
            return 'плохое значение' if value == 'запрещено' else None

        r = CommandRegistry()
        r.register(CommandSpec(
            name='open_thing',
            synonyms=[Synonym('ru', 'открой {thing}')],
            handler=handler,
            validators={'thing': bad_validator},
        ))
        d = CommandDispatcher(r, make_config())

        result = d.dispatch('открой запрещено')
        assert result.success is False
        assert 'Недопустимый аргумент' in result.message
        assert calls == []  # валидация до обработчика

    def test_validator_defect_is_refusal_not_crash(self):
        def broken(v):
            raise RuntimeError('validator bug')

        r = CommandRegistry()
        r.register(CommandSpec(
            name='open_thing',
            synonyms=[Synonym('ru', 'открой {thing}')],
            validators={'thing': broken},
        ))
        d = CommandDispatcher(r, make_config())
        result = d.dispatch('открой что-то')
        assert result.success is False
        assert 'валидации' in result.message

    def test_builtins_volume_validator(self):
        d = CommandDispatcher(build_default_registry(), make_config())
        assert d.dispatch('громкость 300').success is False
        assert d.dispatch('громкость минус пять').success is False
        assert d.dispatch('громкость . избавиться').success is False


class TestDangerousConfirmation:
    def test_dangerous_requires_confirmation(self):
        # Выключение из каталога MVP: обработчика ещё нет (этап 3) — отказ честный
        dd = CommandDispatcher(build_default_registry(), make_config(confirmation=True))
        result = dd.dispatch('выключи компьютер')
        assert result.success is False
        assert 'этап 3' in result.message

    def test_dangerous_without_confirmation_provider_cancels(self):
        calls = []
        d = self._register_dangerous(calls)
        result = d.dispatch('сделай вещь')
        assert result.success is False
        assert 'отменено' in result.message
        assert calls == []

    def _register_dangerous(self, calls, **cfg_kwargs):
        def handler(args):
            calls.append(dict(args))
            return CommandResult(True, 'выполнено')

        r = CommandRegistry()
        r.register(CommandSpec(
            name='test_cmd',
            synonyms=[Synonym('ru', 'сделай вещь')],
            handler=handler,
            dangerous=True,
        ))
        return CommandDispatcher(r, make_config(**cfg_kwargs))

    def test_confirm_yes_executes(self):
        calls = []
        d = self._register_dangerous(calls)
        result = d.dispatch('сделай вещь', lambda prompt, timeout: 'да')
        assert result.success is True
        assert calls == [{}]

    def test_confirm_no_cancels(self):
        calls = []
        d = self._register_dangerous(calls)
        result = d.dispatch('сделай вещь', lambda prompt, timeout: 'нет')
        assert result.success is False
        assert 'отменено' in result.message
        assert calls == []

    def test_confirm_ambiguous_cancels(self):
        calls = []
        d = self._register_dangerous(calls)
        for answer in ('может быть', 'не знаю', '   '):
            result = d.dispatch('сделай вещь', lambda prompt, timeout: answer)
            assert result.success is False, answer
            assert calls == []

    def test_confirm_timeout_cancels(self):
        calls = []

        def timed_out(prompt, timeout):
            raise ConfirmationTimeout('ответ не получен')

        d = self._register_dangerous(calls)
        result = d.dispatch('сделай вещь', timed_out)
        assert result.success is False
        assert 'истекло' in result.message
        assert calls == []

    def test_confirmation_disabled_runs_directly(self):
        calls = []
        d = self._register_dangerous(calls, confirmation=False)
        result = d.dispatch('сделай вещь')
        assert result.success is True
        assert calls == [{}]

    def test_de_confirmation_prompt_language(self):
        seen_prompts = []

        def recorder(prompt, timeout):
            seen_prompts.append(prompt)
            return 'ja'

        r = CommandRegistry()
        r.register(CommandSpec(
            name='test_cmd',
            synonyms=[Synonym('ru', 'сделай вещь'), Synonym('de', 'mache die sache')],
            handler=lambda a: CommandResult(True, 'ok'),
            dangerous=True,
        ))
        d = CommandDispatcher(r, make_config())
        result = d.dispatch('Mache die sache', recorder)
        assert result.success is True
        assert seen_prompts and 'Bestätigen' in seen_prompts[0]
