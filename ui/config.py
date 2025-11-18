"""UI設定とフォント管理

このモジュールは、ゲームのUI設定を一元管理します。
- フォント設定
- 画面サイズ
- ギミック発動モード
- ダブルクリック設定
"""
import pygame

# ==================== 画面設定 ====================
# デフォルト画面サイズ
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800

# 現在の画面サイズ（リサイズ可能）
current_width = DEFAULT_WIDTH
current_height = DEFAULT_HEIGHT


def get_screen_size():
    """現在の画面サイズを取得"""
    return (current_width, current_height)


def set_screen_size(width, height):
    """画面サイズを設定"""
    global current_width, current_height
    current_width = width
    current_height = height


# ==================== フォント設定 ====================
FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)
# Help/operation text: slightly bolder and with more spacing for readability
HELP_FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)

# Simple cache for pygame fonts to avoid repeated SysFont calls each frame.
# Keyed by (family, size, bold).
FONT_CACHE = {}


# ==================== ギミック発動設定 ====================
# ギミック発動方式: 'number_key' | 'click_enlarged' | 'double_click'
gimmick_activation_mode = 'number_key'

# When top-level "カードをクリックして発動" is selected we keep a submode
# which is either 'click_enlarged' or 'double_click'. The effective
# `gimmick_activation_mode` mirrors this submode when click-top is active.
gimmick_click_submode = 'click_enlarged'


def get_gimmick_activation_mode():
    """ギミック発動モードを取得"""
    return gimmick_activation_mode


def set_gimmick_activation_mode(mode):
    """ギミック発動モードを設定"""
    global gimmick_activation_mode
    gimmick_activation_mode = mode


def get_gimmick_click_submode():
    """ギミッククリックサブモードを取得"""
    return gimmick_click_submode


def set_gimmick_click_submode(submode):
    """ギミッククリックサブモードを設定"""
    global gimmick_click_submode
    gimmick_click_submode = submode


# ==================== ダブルクリック設定 ====================
# Increase interval slightly to make double-click detection more forgiving for slower users
DOUBLE_CLICK_INTERVAL = 0.60  # seconds
# Maximum pixel distance between clicks to be considered a double-click
DOUBLE_CLICK_DIST = 36  # pixels
DOUBLE_CLICK_DIST_SQ = DOUBLE_CLICK_DIST * DOUBLE_CLICK_DIST

# ダブルクリック状態管理
last_click_time = 0.0
last_click_pos = (0, 0)
# Track the last logical card index that was clicked (None when click wasn't on a hand card)
last_clicked_card_index = None


def get_last_click_info():
    """最後のクリック情報を取得"""
    return (last_click_time, last_click_pos, last_clicked_card_index)


def set_last_click_info(time, pos, card_index):
    """最後のクリック情報を設定"""
    global last_click_time, last_click_pos, last_clicked_card_index
    last_click_time = time
    last_click_pos = pos
    last_clicked_card_index = card_index


def get_font(size: int, bold: bool = False, family: str = "Noto Sans JP, Meiryo, MS Gothic"):
    """
    フォントを取得（キャッシュ機能付き）
    
    Args:
        size: フォントサイズ
        bold: 太字かどうか
        family: フォントファミリー名
    
    Returns:
        pygame.font.Font: 要求されたフォントオブジェクト
    """
    key = (family, int(size), bool(bold))
    f = FONT_CACHE.get(key)
    if f is not None:
        return f
    try:
        f = pygame.font.SysFont(family, int(size), bold=bold)
    except Exception:
        # fallback to default font object
        try:
            f = pygame.font.Font(None, int(size))
        except Exception:
            f = FONT
    FONT_CACHE[key] = f
    return f
