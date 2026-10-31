#!/usr/bin/env python3
"""Загрузка и валидация конфигурации VoiceControl.

Этап 1:
- конфигурация читается из внешнего файла, путь передаётся явно при запуске;
- основной формат — TOML (stdlib tomllib), JSON принимается для совместимости;
- проверяются обязательные поля, типы и диапазоны значений;
- ошибочная конфигурация даёт понятное сообщение (ConfigError), а не молчаливые
  значения по умолчанию.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

class ConfigError(ValueError):
    """Ошибка конфигурации: отсутствует поле, неверный тип или значение вне диапазона."""

_RUN_MODES = ("production", "test")
_LANGUAGES = ("ru", "de")
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
_SAMPLE_RATES = (8000, 16000, 22050, 44100, 48000)
_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large")

class Config:
    """Валидированная конфигурация.

    Доступ к значениям по «точечному» пути секций:
    config.get('audio.sample_rate'), config.get('language').
    """

    def __init__(self, data: Mapping[str, Any]):
        self._data: Dict[str, Any] = dict(data)

    def get(self, key: str, default: Any = None) -> Any:
        node: Any = self._data
        for part in key.split('.'):
            if not isinstance(node, Mapping) or part not in node:
                return default
            node = node[part]
        return node

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)

def load_config(config_path: str | Path) -> Config:
    """Загружает и валидирует конфигурацию из файла TOML или JSON.

    Raises:
        ConfigError: файл не найден, неверный формат, ошибка синтаксиса,
            отсутствующее/неверное поле или значение вне диапазона.
    """
    path = Path(config_path)
    if not path.is_file():
        raise ConfigError(f"Файл конфигурации не найден: {path}")

    try:
        if path.suffix.lower() == '.toml':
            with path.open('rb') as f:
                data = tomllib.load(f)
        elif path.suffix.lower() == '.json':
            with path.open('r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            raise ConfigError(
                f"Неподдерживаемый формат конфигурации '{path.suffix}'. "
                "Поддерживаются TOML (.toml) и JSON (.json)."
            )
    except ConfigError:
        raise
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"Ошибка разбора TOML в {path}: {e}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"Ошибка разбора JSON в {path}: {e}")

    validate_config(data)
    return Config(data)

# ------------------------------------------------------------------ валидация

def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)

def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)

def _check_int(name: str, value: Any, low: int, high: int) -> None:
    _require(_is_int(value), f"{name}: ожидалось целое число, получено {type(value).__name__} ({value!r})")
    _require(low <= value <= high, f"{name}: значение {value} вне диапазона {low}..{high}")

def _check_float(name: str, value: Any, low: float, high: float) -> None:
    _require(
        isinstance(value, (int, float)) and not isinstance(value, bool),
        f"{name}: ожидалось число, получено {type(value).__name__} ({value!r})",
    )
    _require(low <= value <= high, f"{name}: значение {value} вне диапазона {low}..{high}")

def _check_str(name: str, value: Any, *, non_empty: bool = True) -> None:
    _require(isinstance(value, str), f"{name}: ожидалась строка, получено {type(value).__name__} ({value!r})")
    if non_empty:
        _require(value.strip() != '', f"{name}: строка не должна быть пустой")

def _check_enum(name: str, value: Any, choices: Tuple[str, ...]) -> None:
    _require(
        isinstance(value, str) and value in choices,
        f"{name}: ожидалось одно из {choices}, получено {value!r}",
    )

def _check_bool(name: str, value: Any) -> None:
    _require(isinstance(value, bool), f"{name}: ожидался булев тип, получено {type(value).__name__} ({value!r})")

def validate_config(data: Mapping[str, Any]) -> None:
    """Проверяет структуру, типы и диапазоны всей конфигурации."""
    _require(isinstance(data, dict), "Конфигурация должна быть таблицей/словарём")

    # --- общие поля (обязательные) ---
    _check_str('language', data.get('language'))
    _check_enum('language', data['language'], _LANGUAGES)

    _check_str('wake_phrase', data.get('wake_phrase'))

    if 'run_mode' in data:
        _check_enum('run_mode', data['run_mode'], _RUN_MODES)

    if 'additional_languages' in data:
        langs = data['additional_languages']
        _require(
            isinstance(langs, list) and all(isinstance(x, str) for x in langs),
            "additional_languages: ожидался массив строк",
        )
        bad = [x for x in langs if x not in _LANGUAGES]
        _require(not bad, f"additional_languages: неподдерживаемые языки {bad}; поддерживаются {_LANGUAGES}")
        _require(
            data['language'] not in langs,
            "additional_languages: основной язык language не должен дублироваться",
        )

    # --- аудио ---
    audio = data.get('audio', {})
    _require(isinstance(audio, dict), "секция [audio]: должна быть таблицей")
    _check_int('audio.sample_rate', audio.get('sample_rate'), 8000, 48000)
    _require(
        audio['sample_rate'] in _SAMPLE_RATES,
        f"audio.sample_rate: значение {audio['sample_rate']}; поддерживаются {_SAMPLE_RATES}",
    )
    _check_int('audio.chunk_size', audio.get('chunk_size'), 128, 8192)
    if 'channels' in audio:
        _check_int('audio.channels', audio['channels'], 1, 2)
    if 'device' in audio:
        _check_int('audio.device', audio['device'], -1, 512)
    if 'max_record_seconds' in audio:
        _check_float('audio.max_record_seconds', audio['max_record_seconds'], 1.0, 30.0)

    # --- VAD ---
    vad = data.get('vad', {})
    _require(isinstance(vad, dict), "секция [vad]: должна быть таблицей")
    if 'silence_threshold' in vad:
        _check_float('vad.silence_threshold', vad['silence_threshold'], 0.0, 1.0)
    if 'min_speech_duration' in vad:
        _check_float('vad.min_speech_duration', vad['min_speech_duration'], 0.0, 5.0)
    if 'max_silence_duration' in vad:
        _check_float('vad.max_silence_duration', vad['max_silence_duration'], 0.1, 10.0)

    # --- Whisper (этап 6) ---
    whisper = data.get('whisper', {})
    _require(isinstance(whisper, dict), "секция [whisper]: должна быть таблицей")
    if 'model' in whisper:
        _check_enum('whisper.model', whisper['model'], _WHISPER_MODELS)
    if 'device' in whisper:
        _check_enum('whisper.device', whisper['device'], ("cpu", "cuda"))

    # --- безопасность ---
    security = data.get('security', {})
    _require(isinstance(security, dict), "секция [security]: должна быть таблицей")
    if 'target_os' in security:
        _check_enum('security.target_os', security['target_os'], ("windows", "linux", "macos"))
    if 'dry_run' in security:
        _check_bool('security.dry_run', security['dry_run'])
    if 'app_whitelist' in security:
        wl = security['app_whitelist']
        _require(isinstance(wl, dict), "security.app_whitelist: ожидалась таблица имя -> путь")
        for key, val in wl.items():
            _check_str(f"security.app_whitelist['{key}']", val)
    if 'allowed_dirs' in security:
        dirs = security['allowed_dirs']
        _require(
            isinstance(dirs, list) and all(isinstance(x, str) for x in dirs),
            "security.allowed_dirs: ожидался массив строк",
        )
    if 'confirmation_required' in security:
        _check_bool('security.confirmation_required', security['confirmation_required'])
    if 'confirmation_timeout' in security:
        _check_float('security.confirmation_timeout', security['confirmation_timeout'], 2.0, 60.0)

    # --- TTS ---
    tts = data.get('tts', {})
    _require(isinstance(tts, dict), "секция [tts]: должна быть таблицей")
    if 'engine' in tts:
        _check_enum('tts.engine', tts['engine'], ("pyttsx3",))
    if 'rate' in tts:
        _check_int('tts.rate', tts['rate'], 50, 350)
    if 'volume' in tts:
        _check_float('tts.volume', tts['volume'], 0.0, 1.0)
    if 'voice_id' in tts:
        _require(tts['voice_id'] is None or isinstance(tts['voice_id'], str),
                 "tts.voice_id: ожидалась строка или отсутствие значения")
    if 'voice_ids' in tts:
        vids = tts['voice_ids']
        _require(
            isinstance(vids, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in vids.items()),
            "tts.voice_ids: ожидалась таблица язык -> идентификатор голоса (строки)",
        )
        bad = [k for k in vids if k not in ('ru', 'de')]
        _require(not bad, f"tts.voice_ids: ожидались языки из {('ru', 'de')}, получены {bad}")

    # --- логирование ---
    log = data.get('logging', {})
    _require(isinstance(log, dict), "секция [logging]: должна быть таблицей")
    if 'level' in log:
        _check_enum('logging.level', log['level'], _LOG_LEVELS)
    if 'file' in log:
        _check_str('logging.file', log['file'], non_empty=True)
    if 'max_bytes' in log:
        _check_int('logging.max_bytes', log['max_bytes'], 1024, 1_000_000_000)
    if 'backup_count' in log:
        _check_int('logging.backup_count', log['backup_count'], 0, 20)
