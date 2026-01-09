"""UI レイアウト計算とテキスト描画ヘルパー"""
import pygame


# Base UI resolution used for consistent scaling between windowed and fullscreen
BASE_UI_W = 1200
BASE_UI_H = 800

# テキストレンダリングキャッシュ（同じテキストの繰り返しレンダリングを回避）
# { (text, font_size, bold, color): pygame.Surface }
_text_render_cache = {}
_TEXT_CACHE_MAX_SIZE = 500  # キャッシュの最大サイズ


def _get_cached_text_surface(font, text, color, cache_key):
    """キャッシュ付きテキストレンダリング。
    
    Args:
        font: pygame.font.Font オブジェクト
        text: レンダリングするテキスト
        color: 色タプル
        cache_key: キャッシュキー
        
    Returns:
        pygame.Surface
    """
    if cache_key in _text_render_cache:
        return _text_render_cache[cache_key]
    
    # キャッシュが大きくなりすぎたら古いエントリをクリア
    if len(_text_render_cache) > _TEXT_CACHE_MAX_SIZE:
        # 簡易的に半分をクリア
        keys_to_remove = list(_text_render_cache.keys())[:_TEXT_CACHE_MAX_SIZE // 2]
        for k in keys_to_remove:
            del _text_render_cache[k]
    
    surf = font.render(text, True, color)
    _text_render_cache[cache_key] = surf
    return surf


def clear_text_cache():
    """テキストレンダリングキャッシュをクリア。"""
    global _text_render_cache
    _text_render_cache = {}


def draw_text(surf, text, x, y, color=(20, 20, 20), bold=False, letter_spacing=0, scale=1.0):
    """Draw text with optional bold and letter spacing.

    Args:
        surf: pygame surface to draw on
        text: text string to render
        x, y: position to draw text
        color: RGB color tuple
        bold: render with a bold variant of the UI font
        letter_spacing: extra pixels to insert between characters (int)
        scale: scaling factor for font size

    Returns:
        pygame.Rect of the rendered text on the surface
    
    Backwards-compatible: default behavior is unchanged.
    """
    try:
        # Import font utilities dynamically to avoid circular imports
        import sys
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            # Fallback: try direct import
            try:
                from ui.config import get_font, FONT
            except ImportError:
                try:
                    from .config import get_font, FONT
                except ImportError:
                    # Last resort: use pygame default font
                    font = pygame.font.Font(None, 24)
                    img = font.render(text, True, color)
                    rect = surf.blit(img, (x, y))
                    return rect
            else:
                main_module = None
        
        if main_module:
            get_font = getattr(main_module, 'get_font', None)
            FONT = getattr(main_module, 'FONT', None)
            if not FONT or not get_font:
                # Fallback to default font
                font = pygame.font.Font(None, 24)
                img = font.render(text, True, color)
                rect = surf.blit(img, (x, y))
                return rect
        
        # fast path: no bold and no special spacing -> use global FONT directly with cache
        if not bold and (letter_spacing == 0) and float(scale) == 1.0:
            cache_key = (text, FONT.get_height(), False, color)
            img = _get_cached_text_surface(FONT, text, color, cache_key)
            rect = surf.blit(img, (x, y))
            return rect

        # choose a font for rendering; scale the base FONT height by 'scale'
        base_size = max(10, FONT.get_height())
        size = max(10, int(base_size * float(scale)))
        # Use cached font to avoid repeated SysFont invocations
        font = get_font(size, bold=bold)

        if letter_spacing <= 0:
            cache_key = (text, size, bold, color)
            img = _get_cached_text_surface(font, text, color, cache_key)
            rect = surf.blit(img, (x, y))
            return rect

        # Render per-character with spacing
        cur_x = x
        max_h = 0
        # scale letter spacing as well so spacing is proportional on large screens
        spacing_px = max(0, int(letter_spacing * float(scale)))
        for ch in text:
            ch_cache_key = (ch, size, bold, color)
            ch_surf = _get_cached_text_surface(font, ch, color, ch_cache_key)
            surf.blit(ch_surf, (cur_x, y))
            cur_x += ch_surf.get_width() + spacing_px
            max_h = max(max_h, ch_surf.get_height())

        total_w = cur_x - x
        return pygame.Rect(x, y, total_w, max_h)
    except Exception:
        # fallback to simple rendering to avoid crashing UI
        try:
            font = pygame.font.Font(None, 24)
            img = font.render(text, True, color)
            rect = surf.blit(img, (x, y))
            return rect
        except Exception:
            # absolute fallback: return empty rect
            return pygame.Rect(x, y, 0, 0)


def wrap_text(text: str, max_width: int):
    """Return list of lines wrapped to fit max_width using FONT metrics.
    
    Args:
        text: text string to wrap
        max_width: maximum pixel width for each line
    
    Returns:
        list of text lines that fit within max_width
    """
    try:
        # Import FONT dynamically to avoid circular imports
        import sys
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            # Fallback: try direct import
            try:
                from ui.config import FONT
            except ImportError:
                try:
                    from .config import FONT
                except ImportError:
                    # Last resort: return text as-is
                    return [text]
            else:
                main_module = None
        
        if main_module:
            FONT = getattr(main_module, 'FONT', None)
            if not FONT:
                return [text]
        
        lines = []
        cur = ""
        for ch in text:
            test = cur + ch
            w, _ = FONT.size(test)
            if w <= max_width or cur == "":
                cur = test
            else:
                lines.append(cur)
                cur = ch
        if cur:
            lines.append(cur)
        return lines
    except Exception:
        # Fallback: return text as single line
        return [text]


def compute_layout(win_w: int, win_h: int):
    """Compute common layout metrics used by draw_panel and input handling.
    
    Args:
        win_w: window width in pixels
        win_h: window height in pixels
    
    Returns:
        dict with keys:
            left_margin, left_panel_width, right_panel_width, right_panel_x,
            board_left, board_top, board_size, board_area_top, board_area_height,
            card_area_top, card_h, central_left, central_right, scale, right_outer_margin
    """
    # Compute a uniform scale relative to a base UI resolution so that
    # fullscreen and windowed modes scale UI elements consistently.
    try:
        scale_w = float(win_w) / float(BASE_UI_W)
        scale_h = float(win_h) / float(BASE_UI_H)
        scale = min(scale_w, scale_h)
    except Exception:
        scale = 1.0

    # Base measurements (from BASE_UI_W / BASE_UI_H) then scaled
    base_left_margin = max(8, int(BASE_UI_W * 0.018))
    base_left_panel_width = max(120, min(420, int(BASE_UI_W * 0.16)))
    base_right_panel_width = max(160, min(420, int(BASE_UI_W * 0.16)))
    base_board_area_top = max(12, int(BASE_UI_H * 0.02))
    inner_gap = int(20 * scale)

    left_margin = max(12, int(base_left_margin * scale))
    left_panel_width = max(12, int(base_left_panel_width * scale))
    right_panel_width = max(12, int(base_right_panel_width * scale))
    # 右側に一定割合の外側余白を確保して、表示サイズが変わっても見やすさを維持
    # 画面幅に対する割合で設定（例: 6%）。最小値は12pxを確保。
    try:
        right_outer_margin = max(12, int(win_w * 0.06))
    except Exception:
        right_outer_margin = 20

    board_area_top = max(8, int(base_board_area_top * scale))

    central_left = left_margin + left_panel_width + inner_gap
    # 右パネルの右側に right_outer_margin を設ける
    central_right = win_w - right_outer_margin - right_panel_width - inner_gap
    central_width = max(0, central_right - central_left)

    # reserve bottom area for hand display (card height scaled)
    # On large screens, prefer larger card thumbnails so cards can be "big" as requested.
    # Increase base card size slightly and make the upscaling more aggressive on large displays.
    base_card_h = max(140, int(BASE_UI_H * 0.22))
    if scale > 1.02:
        # more aggressive growth so cards become prominently larger on fullscreen
        extra = min(2.6, 1.0 + (scale - 1.0) * 1.4)
        base_card_h = int(base_card_h * extra)
    card_h = max(48, int(base_card_h * scale))
    reserved_bottom = card_h + int(80 * scale)
    avail_height = win_h - board_area_top - reserved_bottom

    board_size = max(64, min(central_width, avail_height))
    # If the UI is being upscaled (fullscreen), prefer to keep the board
    # slightly smaller so card art and UI elements have room and appear larger.
    try:
        if scale > 1.0:
            board_size = max(64, int(board_size * 0.9))
    except Exception:
        pass
    # center board within central region, but bias position for large screens
    # so the board moves toward the left/top to make room for larger cards and reduce top whitespace
    center_dx = max(0, (central_width - board_size) // 2)
    # horizontal bias: on larger scales, shift the board left by a larger fraction of available space
    try:
        # stronger left shift so board moves noticeably left on large displays
        horiz_bias = int(max(0, (scale - 1.0) * central_width * 0.28))
    except Exception:
        horiz_bias = 0
    board_left = central_left + max(0, center_dx - horiz_bias)

    # vertical bias: if there is extra vertical slack, push the board upward to minimize top whitespace
    slack = avail_height - board_size
    if slack > 0:
        # remove almost all of the top slack so the board moves up; keep a tiny safe margin
        move_up = int(slack * 0.98)
        # allow board to go very near the top (but not negative)
        board_top = max(4, board_area_top - move_up)
    else:
        board_top = board_area_top

    right_panel_x = win_w - right_outer_margin - right_panel_width

    card_area_top = board_top + board_size + int(20 * scale)

    # expose computed card height so draw_panel can size card thumbnails consistently
    # start from the scaled base size
    card_h = max(48, int(base_card_h * scale))

    # If there is extra vertical space below the board, use it to enlarge card artwork
    # while keeping sensible caps so cards don't become absurdly large.
    try:
        space_below = win_h - (board_top + board_size) - int(20 * scale)
        # leave a small padding; effective available for the card itself
        avail_for_card = max(0, space_below - int(24 * scale))
        if avail_for_card > card_h:
            # allow card to grow up to a fraction of board_size or a capped multiplier
            # allow cards to grow more aggressively into the freed vertical space
            # increase cap: allow up to 75% of board height or a larger multiple of base
            max_by_board = int(board_size * 0.75)
            max_by_base = int(base_card_h * scale * 3.5)
            target_h = min(avail_for_card, max_by_board, max_by_base)
            # smoothly increase (don't shrink if target smaller)
            if target_h > card_h:
                card_h = target_h
    except Exception:
        pass

    return {
        'left_margin': left_margin,
        'left_panel_width': left_panel_width,
        'right_panel_width': right_panel_width,
        'right_panel_x': right_panel_x,
        'right_outer_margin': right_outer_margin,
        'board_left': board_left,
        'board_top': board_top,
        'board_size': board_size,
        'board_area_top': board_area_top,
        'board_area_height': board_size,
        'card_area_top': card_area_top,
        'card_h': card_h,
        'central_left': central_left,
        'central_right': central_right,
        'scale': scale,
    }
