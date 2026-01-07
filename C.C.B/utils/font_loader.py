"""Font loading utilities with bundled font support.

This module provides consistent font loading that prioritizes the bundled
Noto Sans JP font for Japanese text support across all platforms.
"""

import os
import pygame
from .path_resolver import get_resource_path

# フォントキャッシュ
_font_cache = {}


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
    
    # 同梱フォントを優先して試す
    bundled_font_paths = [
        get_resource_path('Noto_Sans_JP/NotoSansJP-VariableFont_wght.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Regular.ttf'),
        get_resource_path('Noto_Sans_JP/static/NotoSansJP-Bold.ttf') if bold else None,
    ]
    
    for font_path in bundled_font_paths:
        if font_path and os.path.exists(font_path):
            try:
                font = pygame.font.Font(font_path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    
    # Windows システムフォント（存在確認付き）
    windows_font_paths = [
        "C:\\Windows\\Fonts\\msgothic.ttc",   # MSゴシック
        "C:\\Windows\\Fonts\\meiryo.ttc",     # メイリオ
        "C:\\Windows\\Fonts\\yugothic.ttf",   # 遊ゴシック
    ]
    
    for font_path in windows_font_paths:
        if os.path.exists(font_path):
            try:
                font = pygame.font.Font(font_path, size)
                _font_cache[key] = font
                return font
            except Exception:
                continue
    
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
