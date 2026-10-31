#!/usr/bin/env python3
"""Тесты реестра команд (этап 2)."""

import pytest

from voicecontrol.commands.registry import (
    CommandRegistry, CommandSpec, RegistryError, Synonym,
)


def make_spec(name='cmd', pattern='сделай вещь', handler=None, dangerous=False):
    return CommandSpec(
        name=name,
        synonyms=[Synonym('ru', pattern)],
        handler=handler,
        dangerous=dangerous,
    )


def test_register_and_get():
    r = CommandRegistry()
    spec = make_spec()
    r.register(spec)
    assert r.get('cmd') is spec
    assert len(r) == 1
    assert list(r)[0].name == 'cmd'


def test_duplicate_rejected():
    r = CommandRegistry()
    r.register(make_spec())
    with pytest.raises(RegistryError, match='уже'):
        r.register(make_spec())


def test_bad_name_rejected():
    r = CommandRegistry()
    with pytest.raises(RegistryError):
        r.register(make_spec(name=''))


def test_empty_synonyms_rejected():
    r = CommandRegistry()
    with pytest.raises(RegistryError, match='синонимов'):
        r.register(CommandSpec(name='cmd', synonyms=[]))


def test_iterable_order_preserved():
    r = CommandRegistry()
    r.register(make_spec('a', 'фраза а'))
    r.register(make_spec('b', 'фраза б'))
    assert [s.name for s in r] == ['a', 'b']
