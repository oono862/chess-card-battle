"""Path resolution utilities for PyInstaller compatibility.

This module provides functions to resolve file paths correctly whether
running in development mode or as a PyInstaller-packaged executable.
"""

import os
import sys


def get_base_path():
    """Get the base path for resource files.
    
    Returns:
        str: When running as PyInstaller exe, returns sys._MEIPASS (temp directory).
             Otherwise, returns the project root directory.
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller でパッケージ化された場合
        # sys._MEIPASS はリソースが展開される一時ディレクトリ
        return sys._MEIPASS
    else:
        # 開発環境の場合
        # utils/path_resolver.py -> utils -> c.c.b -> project root
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_resource_path(relative_path):
    """Get the absolute path to a resource file.
    
    Args:
        relative_path: Path relative to the project root (e.g., 'images/card.png')
        
    Returns:
        str: Absolute path to the resource file.
    """
    return os.path.join(get_base_path(), relative_path)


def get_writable_path(relative_path):
    """Get a writable path for saving user data.
    
    In PyInstaller exe mode, the resource directory (sys._MEIPASS) is read-only.
    This function returns a path in the same directory as the exe for writing.
    
    Args:
        relative_path: Filename or relative path for the writable file
                      (e.g., 'saved_decks.json')
        
    Returns:
        str: Absolute path where the file can be written.
    """
    if getattr(sys, 'frozen', False):
        # exe と同じディレクトリに保存（書き込み可能）
        return os.path.join(os.path.dirname(sys.executable), relative_path)
    else:
        # 開発環境ではプロジェクトルートに保存
        return os.path.join(get_base_path(), relative_path)


def get_user_data_dir():
    """Get the directory for storing user data.
    
    Returns:
        str: Directory path where user data (settings, saved decks) should be stored.
    """
    if getattr(sys, 'frozen', False):
        # exe と同じディレクトリ
        return os.path.dirname(sys.executable)
    else:
        # 開発環境ではプロジェクトルート
        return get_base_path()


def is_frozen():
    """Check if running as a PyInstaller executable.
    
    Returns:
        bool: True if running as exe, False in development mode.
    """
    return getattr(sys, 'frozen', False)


# 便利な定数（初期化時に計算）
BASE_PATH = get_base_path()
IMAGES_DIR = get_resource_path('images')
MUSIC_DIR = get_resource_path('mugic')
FONT_DIR = get_resource_path('Noto_Sans_JP')
