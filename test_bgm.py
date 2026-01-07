#!/usr/bin/env python3
"""BGM manager test script"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'c.c.b'))

try:
    from audio.bgm_manager import *
    
    print("=== BGM Manager Test ===")
    print(f"BGM enabled: {get_bgm_enabled()}")
    print(f"BGM volume: {get_bgm_volume()}")
    print(f"Current BGM mode: {get_current_bgm_mode()}")
    print(f"Is BGM playing: {is_bgm_playing()}")
    
    # Test volume setting
    print("\n--- Testing volume setting ---")
    set_bgm_volume(0.5)
    print(f"After set_bgm_volume(0.5): {get_bgm_volume()}")
    
    # Test BGM enable/disable
    print("\n--- Testing enable/disable ---")
    set_bgm_enabled(False)
    print(f"After set_bgm_enabled(False): {get_bgm_enabled()}")
    set_bgm_enabled(True) 
    print(f"After set_bgm_enabled(True): {get_bgm_enabled()}")
    
    # Test BGM mode setting (if audio files exist)
    print("\n--- Testing BGM mode setting ---")
    set_bgm_mode('title')
    print(f"After set_bgm_mode('title'): {get_current_bgm_mode()}")
    print(f"Is BGM playing: {is_bgm_playing()}")
    
    print("\nBGM manager test completed successfully!")
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error during test: {e}")