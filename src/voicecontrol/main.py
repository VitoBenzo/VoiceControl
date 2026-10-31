#!/usr/bin/env python3
"""Точка входа VoiceControl.

Запуск:
    python -m voicecontrol.main --config config.toml

Этап 1:
- путь к конфигурации передаётся явно (по умолчанию config.toml);
- логи ротируются (см. logging_setup);
- в режиме production запуск рабочего цикла заблокирован: реальный аудиоввод,
  распознавание и диспетчер действий ещё не реализованы (этапы 2-7), а текущие
  адаптеры содержат случайные имитации. Запуск возможен только в режиме
  run_mode = "test", и даже он не запускает рабочий цикл до этапа 7.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in (None, ''):
    # Прямой запуск файла: добавляем каталог src, чтобы работал пакет voicecontrol.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voicecontrol.config import ConfigError, load_config
from voicecontrol.logging_setup import setup_logging

DEFAULT_CONFIG_PATH = 'config.toml'


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='voicecontrol',
        description='Голосовой агент управления компьютером (локальные компоненты).',
    )
    parser.add_argument(
        '--config', '-c',
        default=DEFAULT_CONFIG_PATH,
        help=f'путь к файлу конфигурации TOML/JSON (по умолчанию: {DEFAULT_CONFIG_PATH})',
    )
    return parser


def main(argv: list | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config)

    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f'Ошибка конфигурации: {e}', file=sys.stderr)
        return 2

    setup_logging(config)
    logger = logging.getLogger('voicecontrol.main')

    run_mode = config.get('run_mode', 'production')
    logger.info(
        'Старт: конфигурация=%s, run_mode=%s, language=%s, wake_phrase=%r',
        config_path, run_mode, config.get('language'), config.get('wake_phrase'),
    )

    if run_mode != 'test':
        logger.error(
            'Запуск в режиме production заблокирован: компоненты аудиоввода (этапы 5-7), '
            'распознавания (этап 6) и безопасных действий ОС (этап 3) ещё не реализованы.'
        )
        logger.error(
            'Для отладки текстовых компонентов задайте в конфигурации '
            'run_mode = "test" (тестовые адаптеры при этом включаются явно, а не незаметно).'
        )
        return 1

    logger.warning('Режим test: включены тестовые адаптеры. Это НЕ рабочий режим.')
    logger.info(
        'Этап 1 завершён: каркас пакета, конфигурация с валидацией и ротация логов. '
        'Рабочий цикл будет подключён на этапе 7.'
    )
    return 0


if __name__ == '__main__':
    sys.exit(main())
