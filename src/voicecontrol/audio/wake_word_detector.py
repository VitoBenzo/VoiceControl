#!/usr/bin/env python3
"""
Детектор ключевой фразы для голосового агента.
"""

import logging
import time
from typing import List, Optional

class WakeWordDetector:
    """Класс для обнаружения ключевой фразы."""
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.wake_phrases = self._load_wake_phrases()
        
    def _load_wake_phrases(self) -> List[str]:
        """Загружает список ключевых фраз из конфига."""
        phrases = self.config.get('wake_phrases', [])
        if not isinstance(phrases, list):
            phrases = [phrases]
        
        # Добавляем ключевую фразу по умолчанию
        default_phrase = self.config.get('wake_phrase', 'voice control')
        if default_phrase and default_phrase not in phrases:
            phrases.append(default_phrase)
            
        return [phrase.lower() for phrase in phrases]
        
    def detect_wake_word(self, text: str) -> Optional[str]:
        """
        Проверяет, содержится ли ключевая фраза в тексте.
        
        Args:
            text (str): Текст для проверки
            
        Returns:
            str or None: Найденная ключевая фраза или None
        """
        if not text:
            return None
            
        text_lower = text.lower().strip()
        
        for phrase in self.wake_phrases:
            # Проверяем, начинается ли текст с ключевой фразы
            if text_lower.startswith(phrase):
                return phrase
                
        return None
        
    def is_wake_phrase(self, text: str) -> bool:
        """
        Проверяет, является ли текст ключевой фразой.
        
        Args:
            text (str): Текст для проверки
            
        Returns:
            bool: True если текст является ключевой фразой
        """
        return self.detect_wake_word(text) is not None
    
    def get_wake_phrases(self) -> List[str]:
        """Возвращает список ключевых фраз."""
        return self.wake_phrases