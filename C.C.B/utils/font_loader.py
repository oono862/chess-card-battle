"""Font loading utilities with bundled font support.

This module provides consistent font loading that prioritizes the bundled
Noto Sans JP font for Japanese text support across all platforms.
"""

import os
import pygame
from .path_resolver import get_resource_path, path_exists_cached

# フォントキャッシュ
_font_cache = {}

# フォントパス探索結果のキャッシュ（起動時に一度だけ計算）
_bundled_font_path = None
_bundled_font_path_searched = False


def _find_bundled_font_path():
    """同梱フォントのパスを探索してキャッシュする。
    
    起動時に一度だけ実行され、結果をキャッシュする。
    """
    global _bundled_font_path, _bundled_font_path_searched
    
    if _bundled_font_path_searched:
        return _bundled_font_path
    
    _bundled_font_path_searched = True
    
    # 同梱フォントのパス候補（優先順）
    font_candidates = [
        get_resource_path('Noto_Sans_JP/NotoSansJP-VariableFont_wght.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Regular.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Bold.ttf'),
    ]
    
    for font_path in font_candidates:
        if path_exists_cached(font_path):
            _bundled_font_path = font_path
            return _bundled_font_path
    
    # Windowsシステムフォントのフォールバック
    windows_font_paths = [
        "C:\\Windows\\Fonts\\msgothic.ttc",
        "C:\\Windows\\Fonts\\meiryo.ttc",
        "C:\\Windows\\Fonts\\yugothic.ttf",
    ]
    
    for font_path in windows_font_paths:
        if path_exists_cached(font_path):
            _bundled_font_path = font_path
            return _bundled_font_path
    
    return None


def get_font(size, bold=False):
    """Get a font object with Japanese support.
    
    Prioritizes the bundled Noto Sans JP font, then falls back to system fonts.
    Results are cached for performance.
    
    Args:
        size: Font size in points.
        bold: Whether to use bold weight (best effort).
        
    Returns:
        pygame.font.Font: A font object that supports Japanese text.
    """
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    
    # キャッシュ済みのフォントパスを使用（毎回パス検索を避ける）
    font_path = _find_bundled_font_path()
    
    if font_path:
        try:
            font = pygame.font.Font(font_path, size)
            _font_cache[key] = font
            return font
        except Exception:
            pass
    
    # フォールバック: pygame のシステムフォント機能
    try:
        font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic, msgothic", size, bold=bold)
        _font_cache[key] = font
        return font
    except Exception:
        pass
    
    # 最終フォールバック: デフォルトフォント
    font = pygame.font.Font(None, size)
    _font_cache[key] = font
    return font


def get_japanese_font(size, bold=False):
    """Alias for get_font() - explicitly named for Japanese text.
    
    Args:
        size: Font size in points.
        bold: Whether to use bold weight.
        
    Returns:
        pygame.font.Font: A font object that supports Japanese text.
    """
    return get_font(size, bold)


def clear_font_cache():
    """Clear the font cache.
    
    Call this if you need to reload fonts (e.g., after changing display settings).
    """
    global _font_cache
    _font_cache = {}


def get_bundled_font_path():
    """Get the path to the primary bundled font file.
    
    Returns:
        str or None: Path to the bundled font file, or None if not found.
    """
    paths = [
        get_resource_path('Noto_Sans_JP/NotoSansJP-VariableFont_wght.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Regular.ttf'),
    ]
    
    for path in paths:
        if os.path.exists(path):
            return path
    
    return None
