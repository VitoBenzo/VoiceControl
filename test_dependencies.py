#!/usr/bin/env python3
"""Test script to verify all dependencies are working correctly."""

import sys

def test_dependencies():
    """Test if all required modules can be imported."""
    
    required_modules = [
        'speech_recognition',
        'pyttsx3',
        'os',
        'time',
        'json',
        'subprocess'
    ]
    
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module} - OK")
        except ImportError as e:
            print(f"✗ {module} - FAILED: {e}")
            missing_modules.append(module)
    
    if not missing_modules:
        print("\nAll dependencies are installed correctly!")
        return True
    else:
        print(f"\nMissing modules: {', '.join(missing_modules)}")
        return False

if __name__ == "__main__":
    test_dependencies()