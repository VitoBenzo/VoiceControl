#!/usr/bin/env python3
"""Simple test to verify basic functionality without complex audio dependencies."""

import sys
import os

# Проверка, что все необходимые модули могут быть импортированы
required_modules = [
    'speech_recognition',
    'pyttsx3',
    'json', 
    'os',
    'sys',
    'time'
]

print("Проверка наличия модулей...")
for module in required_modules:
    try:
        __import__(module)
        print(f"✓ {module} - доступен")
    except ImportError as e:
        print(f"✗ {module} - НЕДОСТУПЕН: {e}")

print("\nПроверка структуры проекта...")

# Проверяем наличие файлов
required_files = [
    'src/voicecontrol/main.py',
    'src/voicecontrol/config.py',
    'src/voicecontrol/core/agent.py',
    'src/voicecontrol/audio/listener.py',
    'src/voicecontrol/speech/recognizer.py',
    'src/voicecontrol/commands/dispatcher.py',
    'src/voicecontrol/voice/response.py'
]

for file in required_files:
    if os.path.exists(file):
        print(f"✓ {file} - существует")
    else:
        print(f"✗ {file} - отсутствует")

print("\nГотовность к установке зависимостей...")
print("Для полной функциональности необходимы:")
print("- speech_recognition (для распознавания речи)")
print("- pyttsx3 (для синтеза речи)")
print("- pyaudio (для работы с микрофоном - может быть сложен в установке)")
