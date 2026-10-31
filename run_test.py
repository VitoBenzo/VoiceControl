#!/usr/bin/env python3
"""Test script to run the VoiceControl agent with basic functionality."""

import sys
import os
from pathlib import Path

# Добавляем путь к проекту для импортов
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    from voicecontrol.main import main
    
    print("✓ Все модули успешно импортированы")
    print("✓ Запуск теста VoiceControl агента...")
    
    # В этом тесте просто проверим, что агент может быть создан
    from voicecontrol.config import load_config
    from voicecontrol.core.agent import VoiceControlAgent
    
    config = load_config()
    print("✓ Конфигурация загружена успешно")
    
    agent = VoiceControlAgent(config)
    print("✓ Голосовой агент создан успешно")
    
    print("\nТест завершен успешно!")
    print("VoiceControl агент готов к работе.")
    
except ImportError as e:
    print(f"✗ Ошибка импорта: {e}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Ошибка при тестировании: {e}")
    import traceback
    traceback.print_exc()