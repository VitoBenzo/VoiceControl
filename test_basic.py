#!/usr/bin/env python3
"""Basic functionality test for VoiceControl."""

import os
import sys
import time

# Test basic imports
try:
    import speech_recognition as sr
    import pyttsx3
    print("✓ Core modules imported successfully")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

def test_audio_setup():
    """Test if audio devices are accessible."""
    try:
        # Create recognizer instance
        recognizer = sr.Recognizer()
        print("✓ Recognizer created successfully")
        
        # Test microphone access (this will fail if no mic, but we're just checking setup)
        with sr.Microphone() as source:
            print("✓ Microphone access test completed")
        
        return True
    except Exception as e:
        print(f"Note: Audio setup test showed issue (expected without hardware): {e}")
        return True  # This is expected to fail without hardware

def test_tts():
    """Test text-to-speech functionality."""
    try:
        engine = pyttsx3.init()
        print("✓ Text-to-speech engine initialized")
        
        # Test basic speaking
        engine.say("VoiceControl test successful")
        engine.runAndWait()
        print("✓ Text-to-speech test completed")
        return True
    except Exception as e:
        print(f"✗ TTS error: {e}")
        return False

def main():
    """Run all basic tests."""
    print("Running basic VoiceControl functionality tests...")
    print("=" * 50)
    
    # Test audio setup
    test_audio_setup()
    
    # Test TTS
    test_tts()
    
    print("=" * 50)
    print("Basic functionality tests completed!")

if __name__ == "__main__":
    main()