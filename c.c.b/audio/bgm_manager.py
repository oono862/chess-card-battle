"""BGM管理モジュール

このモジュールはゲーム内のBGM再生を管理します。
設定の保持、BGMの切り替え、ボリューム調整などの機能を提供します。
"""
import os
import sys
import pygame

# Import path resolver for PyInstaller compatibility
try:
    from ..utils.path_resolver import get_resource_path, MUSIC_DIR
except Exception:
    try:
        from c.c.b.utils.path_resolver import get_resource_path, MUSIC_DIR
    except Exception:
        # Fallback: define locally if path_resolver is not available
        def get_resource_path(rel_path):
            if getattr(sys, 'frozen', False):
                return os.path.join(sys._MEIPASS, rel_path)
            else:
                return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), rel_path)
        MUSIC_DIR = get_resource_path('mugic')

# ---- BGM 設定 (UI から変更可能) ----
# BGM を再生するかどうか (設定画面で切替)
bgm_enabled = True
# BGM ボリューム (0.0 - 1.0)
bgm_volume = 0.8

# track current logical bgm mode so callers can reapply when toggling
current_bgm_mode = None


def get_bgm_enabled():
    """BGM有効状態を取得"""
    return bgm_enabled


def set_bgm_enabled(enabled):
    """BGM有効状態を設定"""
    global bgm_enabled
    bgm_enabled = enabled
    if not enabled:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass


def get_bgm_volume():
    """BGMボリュームを取得"""
    return bgm_volume


def set_bgm_volume(volume):
    """BGMボリュームを設定 (0.0 - 1.0)"""
    global bgm_volume
    bgm_volume = max(0.0, min(1.0, volume))
    try:
        if pygame.mixer.get_init() and bgm_enabled:
            pygame.mixer.music.set_volume(bgm_volume)
    except Exception:
        pass


def get_current_bgm_mode():
    """現在のBGMモードを取得"""
    return current_bgm_mode


def _ensure_mixer_initialized() -> bool:
    """Ensure pygame mixer is initialized. Returns True if ready."""
    try:
        if pygame.mixer.get_init():
            return True
        try:
            pygame.mixer.init()
            return True
        except Exception:
            return False
    except Exception:
        return False


def set_bgm_mode(mode: str | None) -> None:
    """Atomically switch background music according to mode.

    - 'title' -> MusMus-BGM-162.mp3
    - 'game'  -> MusMus-BGM-173.mp3
    - None    -> stop music

    This function is defensive: it initializes the mixer if needed and
    catches exceptions so UI flow is not interrupted.
    """
    global current_bgm_mode
    
    # ensure mixer is available
    if not _ensure_mixer_initialized():
        return

    current_bgm_mode = mode

    if not bgm_enabled:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        return

    # Determine the music file based on mode
    music_file = None
    if mode == 'title':
        music_file = "MusMus-BGM-162.mp3"
    elif mode == 'game':
        music_file = "MusMus-BGM-173.mp3"

    if music_file is None:
        # mode is None or unrecognized; stop music
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        return

    # Build the absolute path to the music file using path_resolver (PyInstaller compatible)
    try:
        music_path = os.path.join(MUSIC_DIR, music_file)
    except Exception:
        # If path resolution fails, skip BGM
        return

    if not os.path.exists(music_path):
        # Music file not found; skip BGM silently
        return

    try:
        pygame.mixer.music.load(music_path)
        pygame.mixer.music.set_volume(bgm_volume)
        pygame.mixer.music.play(-1)  # loop indefinitely
    except Exception:
        # If loading or playing fails, skip BGM silently
        pass
