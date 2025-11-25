"""
ウィンドウ管理モジュール

Pygameのウィンドウ初期化、リサイズ、クロック管理を行います。
"""
import pygame
import logging

logger = logging.getLogger(__name__)

# デフォルトのウィンドウサイズ
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800

# グローバル変数
_screen = None
_clock = None
_window_size = (DEFAULT_WIDTH, DEFAULT_HEIGHT)


def initialize_pygame():
    """Pygameを初期化する
    
    Returns:
        bool: 初期化に成功した場合はTrue、失敗した場合はFalse
    """
    try:
        pygame.init()
        logger.info("Pygame initialized successfully")
        
        # フォントも初期化
        try:
            from . import config
            config._initialize_fonts()
            logger.info("Fonts initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize fonts: {e}")
        
        return True
    except Exception as e:
        logger.exception(f"Failed to initialize pygame: {e}")
        return False


def create_window(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, caption="Chess-Card-Battle β", resizable=True):
    """ゲームウィンドウを作成する
    
    既存のディスプレイサーフェスがある場合は再利用します。
    これにより、モジュールがインポートされた際に複数のウィンドウが
    作成されることを防ぎます。
    
    Args:
        width (int): ウィンドウの幅（デフォルト: 1200）
        height (int): ウィンドウの高さ（デフォルト: 800）
        caption (str): ウィンドウのキャプション（デフォルト: "Chess-Card-Battle β"）
        resizable (bool): ウィンドウをリサイズ可能にするか（デフォルト: True）
    
    Returns:
        pygame.Surface: 作成されたディスプレイサーフェス、または既存のサーフェス
    """
    global _screen, _window_size
    
    try:
        # 既存のディスプレイサーフェスを取得試行
        existing_surf = pygame.display.get_surface()
    except Exception:
        existing_surf = None
    
    if existing_surf:
        # 既存のウィンドウを再利用
        _screen = existing_surf
        _window_size = _screen.get_size()
        logger.info(f"Reusing existing window: {_window_size}")
    else:
        # 新しいウィンドウを作成
        flags = pygame.RESIZABLE if resizable else 0
        _screen = pygame.display.set_mode((width, height), flags)
        pygame.display.set_caption(caption)
        _window_size = (width, height)
        logger.info(f"Created new window: {width}x{height}, resizable={resizable}")
    
    return _screen


def get_screen():
    """現在のディスプレイサーフェスを取得する
    
    Returns:
        pygame.Surface: ディスプレイサーフェス、または作成されていない場合はNone
    """
    return _screen


def get_window_size():
    """現在のウィンドウサイズを取得する
    
    Returns:
        tuple: (幅, 高さ) のタプル
    """
    global _window_size
    if _screen:
        _window_size = _screen.get_size()
    return _window_size


def update_window_size():
    """ウィンドウサイズを更新する（リサイズイベント後に呼び出す）
    
    Returns:
        tuple: 更新後の (幅, 高さ) のタプル
    """
    global _window_size
    if _screen:
        _window_size = _screen.get_size()
        logger.debug(f"Window size updated: {_window_size}")
    return _window_size


def create_clock():
    """ゲームクロックを作成する
    
    Returns:
        pygame.time.Clock: 作成されたクロックオブジェクト
    """
    global _clock
    _clock = pygame.time.Clock()
    logger.info("Game clock created")
    return _clock


def get_clock():
    """現在のクロックオブジェクトを取得する
    
    Returns:
        pygame.time.Clock: クロックオブジェクト、または作成されていない場合はNone
    """
    return _clock


def tick(fps=60):
    """クロックをティックして指定のFPSを維持する
    
    Args:
        fps (int): 目標フレームレート（デフォルト: 60）
    
    Returns:
        int: 前フレームからの経過ミリ秒
    """
    if _clock:
        return _clock.tick(fps)
    return 0


def initialize_window(width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT, caption="Chess-Card-Battle β", resizable=True):
    """Pygameとウィンドウを完全に初期化する
    
    この関数は initialize_pygame(), create_window(), create_clock() を
    まとめて実行します。
    
    Args:
        width (int): ウィンドウの幅（デフォルト: 1200）
        height (int): ウィンドウの高さ（デフォルト: 800）
        caption (str): ウィンドウのキャプション
        resizable (bool): ウィンドウをリサイズ可能にするか
    
    Returns:
        tuple: (screen, clock) のタプル。失敗した場合は (None, None)
    """
    if not initialize_pygame():
        logger.error("Failed to initialize Pygame")
        return None, None
    
    screen = create_window(width, height, caption, resizable)
    clock = create_clock()
    
    return screen, clock
