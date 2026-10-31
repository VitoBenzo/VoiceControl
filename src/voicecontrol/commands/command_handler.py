#!/usr/bin/env python3
"""
Класс для обработки команд голосового агента.
"""

import logging
import platform
from typing import Dict, Any, Optional

class CommandHandler:
    """Класс для выполнения различных команд системы."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Определение операционной системы
        self.os_name = platform.system().lower()
        self.logger.info(f"Операционная система: {self.os_name}")

    def execute_command(self, command: str) -> Dict[str, Any]:
        """ОТКЛЮЧЕНО (этап 1, безопасность).

        Универсальное выполнение shell-команд (subprocess c shell=True,
        вызовы `bash -c`, команды, собранные строками) удалено: распознанный
        текст не должен превращаться в произвольную команду ОС.

        Выполнение действий ОС будет реализовано на этапе 3 через
        PlatformAdapter: subprocess со списком проверенных аргументов,
        shell=False и белый список приложений из конфигурации.
        """
        self.logger.error("Заблокировано: произвольный запуск shell-команд запрещён. '%s' не выполнен.", command)
        return {
            'success': False,
            'output': '',
            'error': 'Действия ОС недоступны: реализуются на этапе 3 через PlatformAdapter и белый список.',
            'returncode': -1,
        }

    def open_browser(self) -> Dict[str, Any]:
        """Открывает веб-браузер."""
        try:
            if self.os_name == 'windows':
                command = 'start "" "https://www.google.com"'
            elif self.os_name == 'darwin':  # macOS
                command = 'open "https://www.google.com"'
            else:  # Linux
                command = 'xdg-open "https://www.google.com"'
                
            return self.execute_command(command)
        except Exception as e:
            error_msg = f"Ошибка открытия браузера: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }

    def play_music(self) -> Dict[str, Any]:
        """Воспроизводит музыку."""
        try:
            if self.os_name == 'windows':
                # Попробуем запустить медиаплеер
                command = 'start "" "C:\\Program Files\\Windows Media Player\\wmplayer.exe"'
            elif self.os_name == 'darwin':  # macOS
                command = 'open -a "Music"'
            else:  # Linux
                command = 'mpg123 music.mp3'  # Простой пример
                
            return self.execute_command(command)
        except Exception as e:
            error_msg = f"Ошибка воспроизведения музыки: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }

    def check_weather(self) -> Dict[str, Any]:
        """Проверяет погоду с помощью стандартной команды."""
        try:
            if self.os_name == 'windows':
                # Windows - используем PowerShell
                command = 'powershell -command "Get-NetIpAddress"'
            elif self.os_name == 'darwin':  # macOS
                command = 'ping -c 1 google.com'
            else:  # Linux
                command = 'ping -c 1 google.com'
                
            return self.execute_command(command)
        except Exception as e:
            error_msg = f"Ошибка получения погоды: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }

    def turn_off_light(self) -> Dict[str, Any]:
        """Погасить свет (имитация)."""
        # Эта команда будет зависеть от подключенных устройств
        # Имитация: просто вывод в лог
        self.logger.info("Имитация погашения света")
        return {
            'success': True,
            'output': 'Свет погас',
            'error': '',
            'returncode': 0
        }

    def launch_windows(self) -> Dict[str, Any]:
        """Запускает Windows (имитация)."""
        # Простая имитация для демонстрации
        self.logger.info("Имитация запуска Windows")
        return {
            'success': True,
            'output': 'Windows запущен',
            'error': '',
            'returncode': 0
        }

    def get_system_info(self) -> Dict[str, Any]:
        """Получает информацию о системе."""
        try:
            info = {
                'os': platform.system(),
                'platform': platform.platform(),
                'processor': platform.processor(),
                'architecture': platform.architecture()[0],
                'machine': platform.machine()
            }
            
            return {
                'success': True,
                'output': str(info),
                'error': '',
                'returncode': 0
            }
        except Exception as e:
            error_msg = f"Ошибка получения информации о системе: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'output': '',
                'error': error_msg,
                'returncode': -1
            }

    def get_available_commands(self) -> list:
        """Возвращает список доступных команд."""
        return [
            'открой браузер',
            'включи музыку', 
            'какая погода',
            'погаси свет',
            'запусти виндовс',
            'получи информацию о системе'
        ]