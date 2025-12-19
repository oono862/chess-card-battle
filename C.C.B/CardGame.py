#カードゲーム部分実装
import os
import pygame
from ui.config import get_ui_effects_enabled
from pygame import Rect
import sys, traceback, os, json, logging, math, re
from datetime import datetime
import time as _ct_time
from typing import List, TYPE_CHECKING
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# 駒の名前マッピング（ツールチップ表示用）
PIECE_NAMES = {
    'K': 'キング',
    'Q': 'クイーン',
    'R': 'ルーク',
    'B': 'ビショップ',
    'N': 'ナイト',
    'P': 'ポーン'
}

# Ensure we can obtain the actual display/window size in one place.
def _refresh_display_size_from_pygame():
    """Return (W,H) using the most authoritative pygame API available.

    This helper uses `pygame.display.get_window_size()` when available (SDL2),
    falling back to the display surface size. It also updates module globals
    `W`, `H` when possible.
    """
    # reference globals but don't require they be defined at import time
    global W, H, screen
    # remember previous reported size so we can detect changes and invalidate
    # any cached, size-dependent resources (eg. scaled background surfaces)
    prev_w = globals().get('W', None)
    prev_h = globals().get('H', None)
    try:
        # Prefer the display surface size (logical drawing surface) for
        # layout calculations. When Pygame is run with SCALED, the window
        # physical size (get_window_size) can differ from the logical
        # surface size used for blitting; using the surface size prevents
        # layout/mouse-coordinate mismatches.
        surf = None
        try:
            surf = pygame.display.get_surface()
        except Exception:
            surf = None
        if surf:
            try:
                sz = surf.get_size()
                W, H = int(sz[0]), int(sz[1])
                globals()['W'] = W
                globals()['H'] = H
                # If size changed, invalidate any cached, size-specific surfaces
                if (prev_w, prev_h) != (W, H):
                    if 'play_bg_surf' in globals():
                        globals()['play_bg_surf'] = None
                return (W, H)
            except Exception:
                pass
        # Fallback: if surface not available or failed, use window size
        try:
            win_sz = pygame.display.get_window_size()
            if win_sz and isinstance(win_sz, tuple) and len(win_sz) == 2:
                W, H = int(win_sz[0]), int(win_sz[1])
                globals()['W'] = W
                globals()['H'] = H
                if (prev_w, prev_h) != (W, H):
                    if 'play_bg_surf' in globals():
                        globals()['play_bg_surf'] = None
                return (W, H)
        except Exception:
            pass
    except Exception:
        pass
    # fallback: return previously-set globals if available
    try:
        return (W, H)
    except Exception:
        return (1200, 800)
# card_coreの解決順を「このファイルと同じディレクトリ」を最優先にする
local_dir = os.path.dirname(os.path.abspath(__file__))
if local_dir not in sys.path:
    sys.path.insert(0, local_dir)
# 互換目的で親ディレクトリもパスに加えるが、優先度は下げる
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
# Try to import local chess engine and rules modules (support package-relative and absolute imports)
try:
    # If this file is imported as part of the package, prefer relative imports
    from . import chess_engine as chess
    from .chess import rules as chess_rules
except Exception:
    try:
        import chess_engine as chess
    except Exception:
        chess = None
    try:
        import chess_rules_simple as chess_rules
    except Exception:
        try:
            from chess import rules as chess_rules
        except Exception:
            chess_rules = None
    # Help static type checkers / language servers resolve package-relative imports
    if TYPE_CHECKING:
        # These imports are only for editors/type-checkers (no runtime effect).
        try:
            from c.c.b.assets import animation as animation  # type: ignore
            from c.c.b.assets import image_loader as image_loader  # type: ignore
        except Exception:
            try:
                from assets import animation as animation  # type: ignore
                from assets import image_loader as image_loader  # type: ignore
            except Exception:
                pass
try:
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck, PlayerState, make_rule_cards_deck, PendingAction, Card, Game, Deck
    from card_core import eff_heat_block_tile, eff_freeze_piece, eff_storm_jump_once, eff_lightning_two_actions, eff_draw2, eff_alchemy, eff_graveyard_roulette, eff_leech_pp2
except Exception:
    logger.exception("Failed to import card_core module")
    raise

# スクリプトを直接実行する場合、同ディレクトリ下の `assets/` を import できるように
# カレントファイルのディレクトリを sys.path に追加しておく（ローカル実行時の互換性補助）。
_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.insert(0, _this_dir)

# User settings persistence (simple JSON in module directory)
def _get_settings_path():
    try:
        return os.path.join(_this_dir, 'user_settings.json')
    except Exception:
        return 'user_settings.json'

def load_user_anim_scale():
    try:
        p = _get_settings_path()
        if not os.path.exists(p):
            return None
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
        v = d.get('user_anim_scale', None)
        if v is None:
            return None
        try:
            return float(v)
        except Exception:
            return None
    except Exception:
        return None

def save_user_anim_scale(val: float):
    try:
        p = _get_settings_path()
        d = {}
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f) or {}
            except Exception:
                d = {}
        d['user_anim_scale'] = float(val)
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    except Exception:
        pass

def load_user_anim_choice():
    try:
        p = _get_settings_path()
        if not os.path.exists(p):
            return None
        with open(p, 'r', encoding='utf-8') as f:
            d = json.load(f)
        return d.get('user_anim_choice', None)
    except Exception:
        return None

def save_user_anim_choice(choice: str):
    try:
        p = _get_settings_path()
        d = {}
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    d = json.load(f) or {}
            except Exception:
                d = {}
        d['user_anim_choice'] = str(choice)
        try:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    except Exception:
        pass

# Pygameウィンドウ管理をインポート
try:
    from ui.window import initialize_window, get_screen, get_clock, get_window_size, update_window_size
except Exception:
    logger.exception("Failed to import ui.window module")
    pygame.init()
    def initialize_window(w=1200, h=800, caption="Chess-Card-Battle β", resizable=True):
        screen = pygame.display.set_mode((w, h), pygame.RESIZABLE if resizable else 0)
        pygame.display.set_caption(caption)
        return screen, pygame.time.Clock()
    def get_screen(): return pygame.display.get_surface()
    def get_clock(): return pygame.time.Clock()
    def get_window_size():
        s = pygame.display.get_surface()
        return s.get_size() if s else (1200, 800)
    def update_window_size(): pass

    # Helper: update module globals W,H to the actual display/window pixel size.
    # Note: a top-level version of this function exists to ensure it's available
    # regardless of whether this except-block is taken; keep this as a thin wrapper
    # for backward compatibility.
    def _refresh_display_size_from_pygame():
        try:
            return globals()['_refresh_display_size_from_pygame']()
        except Exception:
            try:
                return (W, H)
            except Exception:
                return (1200, 800)

# UIフォント設定をインポート
try:
    from ui.config import (get_font, FONT, SMALL, TINY, HELP_FONT, get_gimmick_activation_mode, set_gimmick_activation_mode, get_gimmick_click_submode, set_gimmick_click_submode, DOUBLE_CLICK_INTERVAL, DOUBLE_CLICK_DIST, DOUBLE_CLICK_DIST_SQ, get_last_click_info, set_last_click_info)
    from ui.layout import draw_text, wrap_text, compute_layout, BASE_UI_W, BASE_UI_H
    from ui import card_renderer
    from ui import overlay
    from ui.panel_renderer import draw_background
except Exception:
    logger.exception("Failed to import ui modules")
    BASE_UI_W, BASE_UI_H = 1200, 800
    pygame.init()
    FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
    SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
    TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)
    HELP_FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
    DOUBLE_CLICK_INTERVAL, DOUBLE_CLICK_DIST, DOUBLE_CLICK_DIST_SQ = 0.60, 36, 1296
    def get_gimmick_activation_mode(): return 'number_key'
    def set_gimmick_activation_mode(mode): pass
    def get_gimmick_click_submode(): return 'click_enlarged'
    def set_gimmick_click_submode(submode): pass
    def get_last_click_info(): return (0.0, (0, 0), None)
    def set_last_click_info(time, pos, card_index): pass
    # フォント関連の関数はui.configとui.layoutから使用
    # FONT_CACHE = {}  # ui.configに存在
    # get_font, draw_text, wrap_text はui.config/ui.layoutから使用

    def compute_layout(win_w: int, win_h: int):
        return {}

    def draw_background(screen, W, H, IMG_DIR, PLAY_BG_FILENAME, play_bg_img, play_bg_surf):
        screen.fill((240, 240, 245))
        return play_bg_img, play_bg_surf

    # フォールバックのoverlay関数を定義
    class _FallbackOverlay:
        def handle_scrollbar_drag_start(self, pos, show_log, scrollbar_rect, log_scroll_offset):
            return False

        def handle_scrollbar_drag_end(self):
            pass

        def handle_scrollbar_motion(self, pos, show_log, scrollbar_rect, log_scroll_offset, max_scroll):
            return log_scroll_offset

        def get_scrollbar_state(self):
            return (None, False, 0, 0)

    overlay = _FallbackOverlay()

    # Ensure we can access animation controls if the assets module exists
    try:
        # package-relative (preferred when imported as c.c.b.CardGame)
        from .assets import animation as animation_mod
    except Exception:
        try:
            # explicit package import
            from c.c.b.assets import animation as animation_mod  # type: ignore[reportMissingImports]
        except Exception:
            try:
                # fallback absolute import
                import c.c.b.assets.animation as animation_mod  # type: ignore[reportMissingImports]
            except Exception:
                try:
                    # top-level assets module
                    from assets import animation as animation_mod
                except Exception:
                    animation_mod = None

# BGM管理をインポート
try:
    from audio.bgm_manager import (set_bgm_mode, get_bgm_enabled, set_bgm_enabled, get_bgm_volume, set_bgm_volume, get_current_bgm_mode)
except Exception:
    logger.exception("Failed to import audio.bgm_manager module")
    def set_bgm_mode(mode: str | None) -> None: pass
    def get_bgm_enabled(): return True
    def set_bgm_enabled(enabled): pass
    def get_bgm_volume(): return 0.8
    def set_bgm_volume(volume): pass
    def get_current_bgm_mode(): return None
# デバッグツールをインポート
try:
    from debug.debug_tools import (DEBUG_COUNTER_CHECK_CARD_MODE, _debug_mark_card_played, debug_setup_castling, debug_setup_en_passant, debug_setup_promotion, debug_reset_initial, debug_setup_checkmate, debug_setup_counter_check_white, debug_setup_simul_check_start, set_debug_counter_check_mode, get_debug_counter_check_mode)
except Exception:
    logger.exception("Failed to import debug.debug_tools module")
    DEBUG_COUNTER_CHECK_CARD_MODE = False
    def _debug_mark_card_played(): pass
    def debug_setup_castling(): pass
    def debug_setup_en_passant(): pass
    def debug_setup_promotion(): pass
    def debug_reset_initial(): pass
    def debug_setup_checkmate(): pass
    def debug_setup_counter_check_white(): pass
    def debug_setup_simul_check_start(): pass
    def set_debug_counter_check_mode(enabled: bool): pass
    def get_debug_counter_check_mode() -> bool: return False

# 画像・アニメーション管理をインポート
# Try relative import first (package context), then explicit package, then top-level import.
try:
    # when used as package (c.c.b.CardGame), prefer relative import
    from .assets import image_loader, animation
    IMG_DIR = image_loader.IMG_DIR
    get_card_image = image_loader.get_card_image
    get_piece_image_surface = image_loader.get_piece_image_surface
    play_heat_gif_at = animation.play_heat_gif_at
    play_ic_gif_at = animation.play_ic_gif_at
    heat_gif_anim = animation.heat_gif_anim
    ic_gif_anim = animation.ic_gif_anim
    _ensure_mg_gif_loaded = animation._ensure_mg_gif_loaded
    _ensure_mg_gif_2p_loaded = animation._ensure_mg_gif_2p_loaded
    IC_GIF_SCALE = animation.IC_GIF_SCALE
    _animation_module = animation
except Exception:
    try:
        # explicit package import (works when workspace root is project root)
        from c.c.b.assets import image_loader, animation  # type: ignore[reportMissingImports]
        IMG_DIR = image_loader.IMG_DIR
        get_card_image = image_loader.get_card_image
        get_piece_image_surface = image_loader.get_piece_image_surface
        play_heat_gif_at = animation.play_heat_gif_at
        play_ic_gif_at = animation.play_ic_gif_at
        heat_gif_anim = animation.heat_gif_anim
        ic_gif_anim = animation.ic_gif_anim
        _ensure_mg_gif_loaded = animation._ensure_mg_gif_loaded
        _ensure_mg_gif_2p_loaded = animation._ensure_mg_gif_2p_loaded
        IC_GIF_SCALE = animation.IC_GIF_SCALE
        _animation_module = animation
    except Exception:
        try:
            # fallback: top-level assets package (when running via repo root)
            from assets import image_loader, animation
            IMG_DIR = image_loader.IMG_DIR
            get_card_image = image_loader.get_card_image
            get_piece_image_surface = image_loader.get_piece_image_surface
            play_heat_gif_at = animation.play_heat_gif_at
            play_ic_gif_at = animation.play_ic_gif_at
            heat_gif_anim = animation.heat_gif_anim
            ic_gif_anim = animation.ic_gif_anim
            _ensure_mg_gif_loaded = animation._ensure_mg_gif_loaded
            _ensure_mg_gif_2p_loaded = animation._ensure_mg_gif_2p_loaded
            IC_GIF_SCALE = animation.IC_GIF_SCALE
            _animation_module = animation
        except Exception:
            logger.exception("Failed to import assets modules")
            IMG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "images")
            def get_card_image(name: str, size=(72, 96)): return None
            def get_piece_image_surface(name: str, color: str, size: tuple): return None
            def play_heat_gif_at(row: int, col: int): pass
            def play_ic_gif_at(row: int, col: int): pass
            def _ensure_mg_gif_loaded(): pass
            def _ensure_mg_gif_2p_loaded(): pass
            heat_gif_anim = {'playing': False, 'frames': None, 'durations': None, 'pos': None}
            ic_gif_anim = {'playing': False, 'frames': None, 'durations': None, 'pos': None}
            IC_GIF_SCALE = 1.4
            _animation_module = None

# Synchronize animation module references so UI code uses the same module
try:
    if (not globals().get('animation_mod')) and _animation_module:
        animation_mod = _animation_module
    elif globals().get('animation_mod') is None and _animation_module:
        animation_mod = _animation_module
except Exception:
    try:
        animation_mod = globals().get('animation_mod', None)
    except Exception:
        animation_mod = None

# デッキ管理をインポート
try:
    # Relative import when used as package (primary method)
    from .game.deck_manager import (DECK_SAVE_FILE, load_saved_decks, save_decks_to_file, list_custom_decks, load_custom_deck_by_name, build_deck_for_mode, build_ai_player, build_game_from_card_names)
    from .game.turn_manager import start_player_turn, attempt_start_turn, end_player_chess_move, switch_turn
except ImportError:
    # Try top-level import (script execution)
    try:
        from game.deck_manager import (DECK_SAVE_FILE, load_saved_decks, save_decks_to_file, list_custom_decks, load_custom_deck_by_name, build_deck_for_mode, build_ai_player, build_game_from_card_names)
        from game.turn_manager import start_player_turn, attempt_start_turn, end_player_chess_move, switch_turn
    except ImportError:
        logger.exception("Failed to import game modules")
        import os as _os, json as _json

        # Candidate locations for saved_decks.json (project layout varies depending on run mode)
        _candidates = [
            _os.path.join(_os.path.dirname(__file__), 'saved_decks.json'),
            _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), 'saved_decks.json'),
            _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), 'saved_decks.json'),
        ]

        # Choose existing file or default to first candidate
        DECK_SAVE_FILE = next((p for p in _candidates if _os.path.exists(p)), _candidates[0])

        def _read_decks_from(path):
            try:
                with open(path, 'r', encoding='utf-8') as fh:
                    data = _json.load(fh)
                    if isinstance(data, list):
                        # normalize length to 9
                        out = list(data[:9]) + [None] * max(0, 9 - len(data))
                        return out
            except Exception:
                return [None] * 9
            return [None] * 9

        def _write_decks_to(path, decks):
            try:
                with open(path, 'w', encoding='utf-8') as fh:
                    _json.dump(decks, fh, ensure_ascii=False, indent=2)
                return True
            except Exception:
                return False

        def load_saved_decks():
            return _read_decks_from(DECK_SAVE_FILE)

        def save_decks_to_file(decks):
            # Attempt to write to the chosen DECK_SAVE_FILE; if it fails, try candidates
            if _write_decks_to(DECK_SAVE_FILE, decks):
                return True
            for p in _candidates:
                try:
                    if _write_decks_to(p, decks):
                        return True
                except Exception:
                    continue
            return False

        def list_custom_decks():
            d = _os.path.join(_os.path.dirname(__file__), 'decks')
            out = []
            try:
                if _os.path.isdir(d):
                    for fn in sorted(_os.listdir(d)):
                        if fn.lower().endswith('.json'):
                            out.append(_os.path.splitext(fn)[0])
            except Exception:
                pass
            return out

        def load_custom_deck_by_name(name: str):
            d = _os.path.join(_os.path.dirname(__file__), 'decks')
            p = _os.path.join(d, f"{name}.json")
            try:
                if _os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as fh:
                        return _json.load(fh)
            except Exception:
                return None
            return None

        def build_deck_for_mode(mode: str):
            """モードに応じてデッキを構築する"""
            try:
                if mode == 'custom':
                    # 作成デッキを読み込む
                    try:
                        saved_decks = load_saved_decks()
                        if saved_decks and saved_decks[0]:
                            return build_game_from_card_names(
                                [card.get('name', '') for card in saved_decks[0].get('cards', [])]
                            ).player.deck
                    except Exception:
                        pass
                # 固定デッキまたはカスタムデッキ読み込み失敗時
                return new_game_with_rule_deck().player.deck
            except Exception:
                return None

        def build_ai_player(mode: str):
            try:
                deck = build_deck_for_mode(mode)
                return PlayerState(deck=deck, pp_max=10)
            except Exception:
                return None

        def build_game_from_card_names(names): return None
        def start_player_turn(ai_end_msg: str = None): pass
        def attempt_start_turn(): pass
        def end_player_chess_move(): pass
        def switch_turn(): pass

# ゲームループ管理をインポート
try:
    from game import loop_manager
except Exception:
    logger.exception("Failed to import game.loop_manager module")
    loop_manager = None
# キーボード入力処理をインポート
try:
    from input.keyboard_handler import handle_keydown as _handle_keydown_impl
except Exception:
    logger.exception("Failed to import input.keyboard_handler module")
    _handle_keydown_impl = None
# モーダルダイアログをインポート
try:
    from ui.modals import (
        show_deck_choice_modal as _show_deck_choice_modal_impl,
        show_deck_modal as _show_deck_modal_impl,
        show_deck_editor as _show_deck_editor_impl,
        show_deck_options as _show_deck_options_impl,
        show_deck_battle_confirm as _show_deck_battle_confirm_impl,
        show_deck_action_modal as _show_deck_action_modal_impl,
        show_deck_contents_overlay as _show_deck_contents_overlay_impl,
        show_start_screen as _show_start_screen_impl,
        show_settings_screen as _show_settings_screen_impl
    )
    # custom_deck_selectionはdeck_modalsに含まれていないため個別処理
    _modals_available = True
except Exception:
    logger.exception("Failed to import ui.modals module")
    _show_deck_choice_modal_impl = None
    _show_deck_modal_impl = None
    _show_deck_editor_impl = None
    _show_deck_options_impl = None
    _show_deck_battle_confirm_impl = None
    _show_deck_action_modal_impl = None
    _show_deck_contents_overlay_impl = None
    _show_start_screen_impl = None
    _show_settings_screen_impl = None
    _modals_available = False
# チェス盤描画をインポート
try:
    # import module object as `draw_board` so callers can access module-level caches
    import ui.board_renderer as draw_board
    from ui.board_renderer import (draw_chessboard, draw_pieces, draw_card_effects, draw_gif_animations, draw_turn_telop, draw_notice_message, draw_highlights, draw_check_indicator)
except Exception:
    logger.exception("Failed to import ui.board_renderer module")
    draw_board = None
    def draw_chessboard(screen, layout, chess): pass
    def draw_pieces(screen, layout, chess, SMALL): pass
    def draw_card_effects(screen, layout, game, chess, TINY): pass
    def draw_gif_animations(screen, layout): pass
    def draw_turn_telop(screen, layout, turn_telop_msg, turn_telop_until): pass
    def draw_notice_message(screen, layout, notice_msg, notice_until): pass
    def draw_highlights(screen, layout, selected_piece, highlight_squares, chess, game, is_in_check, simulate_move): pass
    def draw_check_indicator(screen, layout, game_over, chess, is_in_check_for_display, can_attack_king_with_cards, W, H): pass

# Draw dashed rect helper (moved to utils/drawing.py). Import it if available,
# otherwise provide a safe fallback so existing calls don't crash.
try:
    from utils.drawing import draw_dashed_rect
except Exception:
    try:
        # try package-style import
        from c.c.b.utils.drawing import draw_dashed_rect  # type: ignore[reportMissingImports]
    except Exception:
        def draw_dashed_rect(surf, color, rect, dash=6, gap=4, width=2):
            try:
                pygame.draw.rect(surf, color, rect, width)
            except Exception:
                pass

pygame.init()

# 画面設定
W, H = 1200, 800
is_fullscreen = False
# store previous windowed size so we can restore when leaving fullscreen
_prev_window_size = (W, H)
# 既存のdisplay surfaceを再利用（複数ウィンドウ防止）
try:
    existing_surf = pygame.display.get_surface()
except Exception:
    existing_surf = None
if existing_surf:
    screen = existing_surf
else:
    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
    pygame.display.set_caption("Chess-Card-Battle β")
clock = pygame.time.Clock()

# 基準UI解像度（スケーリング用）
BASE_UI_W = 1200
BASE_UI_H = 800

# Debugging: visualize layout rectangles when investigating resize issues
LAYOUT_DEBUG = False

def draw_debug_layout(screen, layout):
    """Draw helpful rectangles and mouse coordinates to diagnose layout mismatches.

    Only active when `LAYOUT_DEBUG` is True.
    """
    try:
        if not LAYOUT_DEBUG:
            return
        # board box
        bx = layout.get('board_left', layout.get('left_margin', 0))
        by = layout.get('board_top', layout.get('top_margin', 0))
        bsize = layout.get('board_size', layout.get('board_area_width', 400))
        pygame.draw.rect(screen, (255, 0, 0), (bx, by, bsize, bsize), 2)
        # board area
        bal = layout.get('board_area_left', bx)
        baw = layout.get('board_area_width', bsize)
        bat = layout.get('board_area_top', by)
        bah = layout.get('board_area_height', bsize)
        pygame.draw.rect(screen, (0, 255, 0), (bal, bat, baw, bah), 2)
        # card area / hand
        cat = layout.get('card_area_top')
        if cat is not None:
            pygame.draw.line(screen, (0, 0, 255), (layout.get('left_margin', 0), cat), (layout.get('left_margin', 0) + 200, cat), 2)
        # mouse pos and window size
        try:
            mx, my = pygame.mouse.get_pos()
            s = f"mx={mx},my={my}, W={W},H={H}"
            f = FONT if 'FONT' in globals() else pygame.font.SysFont(None, 18)
            surf = f.render(s, True, (255, 255, 255))
            screen.blit(surf, (8, 8))
        except Exception:
            pass
    except Exception:
        pass

# Wrap compute_layout so it always refreshes the authoritative display size
# before calling the real layout function. Then update imported module
# references so other code using `compute_layout` at runtime uses this wrapper.
def compute_layout_with_refresh(win_w: int | None = None, win_h: int | None = None):
    try:
        # refresh authoritative sizes
        try:
            w, h = _refresh_display_size_from_pygame()
        except Exception:
            try:
                w, h = (W, H)
            except Exception:
                w, h = (BASE_UI_W, BASE_UI_H)
        # allow callers to override with explicit values if provided
        if win_w is not None and win_h is not None:
            return globals().get('compute_layout_orig', globals().get('compute_layout'))(int(win_w), int(win_h))
        # call the originally-imported compute_layout (preserve fallback)
        func = globals().get('compute_layout_orig') or globals().get('compute_layout')
        if not func:
            # fallback: import from ui.layout dynamically
            try:
                import ui.layout as _layout_mod
                func = getattr(_layout_mod, 'compute_layout')
            except Exception:
                def _f(w, h): return {}
                func = _f
        return func(int(w), int(h))
    except Exception:
        try:
            return globals().get('compute_layout_orig', lambda a, b: {})(win_w or BASE_UI_W, win_h or BASE_UI_H)
        except Exception:
            return {}

# If `compute_layout` was imported earlier, keep original and replace name.
try:
    if 'compute_layout' in globals() and globals().get('compute_layout'):
        globals()['compute_layout_orig'] = globals()['compute_layout']
        globals()['compute_layout'] = compute_layout_with_refresh
    # also patch the ui.layout module if loaded so other modules get our wrapper
    try:
        import sys
        if 'ui.layout' in sys.modules:
            import ui.layout as _layout_mod
            _layout_mod.compute_layout = compute_layout_with_refresh
    except Exception:
        pass
except Exception:
    pass
FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)
# Help/operation text: slightly bolder and with more spacing for readability
HELP_FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)

# ギミック発動方式: 'number_key' | 'click_enlarged' | 'double_click'
gimmick_activation_mode = 'number_key'
gimmick_click_submode = 'click_enlarged'  # クリックモード時のサブモード
# ダブルクリック検出用
last_click_time = 0.0
last_click_pos = (0, 0)
last_clicked_card_index = None
DOUBLE_CLICK_INTERVAL = 0.60
DOUBLE_CLICK_DIST = 36
DOUBLE_CLICK_DIST_SQ = DOUBLE_CLICK_DIST * DOUBLE_CLICK_DIST

# ゲーム状態（難易度・デッキモード選択後に初期化）
game = None
ai_player = None

# Convenience fallback for test imports: when this module is imported by
# lightweight test scripts (not run as the full UI), some tests expect a
# `game` object to exist so they can call methods like `start_turn()`.
# Create a minimal sample game here if one hasn't been created already.
try:
    if game is None:
        try:
            game = new_game_with_sample_deck()
            # Register GIF animation hook
            if game and _animation_module and hasattr(_animation_module, 'play_ic_gif_at'):
                game.play_ic_gif = _animation_module.play_ic_gif_at
        except Exception:
            # best-effort fallback: leave game as None if creation fails
            game = None
except Exception:
    # swallow any import-time errors to avoid breaking consumers
    pass
    pass
# ヘルパー: 相手（AI）の手札枚数を取得する（UI はこれを参照する）
def get_opponent_hand_count():
    try:
        return len(getattr(ai_player, 'hand').cards)
    except Exception:
        # フォールバック: 初期値や何らかの理由で参照できない場合は 0 を返す
        return 0


def _debug_report_anim_scales(context_label: str = ''):
    try:
        import sys
        vals = {}
        try:
            vals['animation_mod'] = animation_mod.get_anim_time_scale() if 'animation_mod' in globals() and animation_mod and hasattr(animation_mod, 'get_anim_time_scale') else None
        except Exception:
            vals['animation_mod'] = None
        try:
            vals['_animation_module'] = globals().get('_animation_module').get_anim_time_scale() if globals().get('_animation_module') and hasattr(globals().get('_animation_module'), 'get_anim_time_scale') else None
        except Exception:
            vals['_animation_module'] = None
        try:
            m = None
            try:
                import importlib
                m = importlib.import_module('c.c.b.assets.animation')
            except Exception:
                try:
                    m = importlib.import_module('assets.animation')
                except Exception:
                    m = sys.modules.get('c.c.b.assets.animation') or sys.modules.get('assets.animation')
            vals['imported_animation'] = m.get_anim_time_scale() if m and hasattr(m, 'get_anim_time_scale') else None
        except Exception:
            vals['imported_animation'] = None
        try:
            logger.debug("DEBUG_ANIM_SCALES %s: %s", context_label, vals)
        except Exception:
            pass
    except Exception:
        pass
# AI 用のギミックフラグ
ai_next_move_can_jump = False
ai_extra_moves_this_turn = 0
ai_consecutive_turns = 0
# When True, the next ai_make_move() call is a continuation of an existing AI
# '迅雷' extra-turn and should NOT perform start-of-turn effects (draw/PP reset).
ai_continuation = False

# 簡易アニメーション: AIが駒をどこに移動させたかを視覚化するための状態
# フォールバックでも安全に参照できるように辞書で管理する
base_ai_move_duration = 2.4
try:
    _scale = animation_mod.get_anim_time_scale() if animation_mod and hasattr(animation_mod, 'get_anim_time_scale') else 1.0
except Exception:
    _scale = 1.0
ai_move_anim = {'active': False, 'from_row': None, 'from_col': None, 'row': None, 'col': None, 'start': 0.0, 'duration': base_ai_move_duration * _scale}
# アニメーション設定フラグ（設定画面でトグル可能）
ai_move_pulse_enabled = True
ai_move_ghost_enabled = True
ai_move_arrow_enabled = True

show_grave = False
show_log = False  # ログ表示切替（デフォルト非表示）
log_scroll_offset = 0  # ログスクロール用オフセット（0=最新）
enlarged_card_index = None  # 拡大表示中のカードインデックス（None=非表示）
enlarged_card_name = None  # 墓地など手札以外の拡大表示用カード名（未定義での参照を防止）
enlarged_card_scale = 1.0  # 拡大表示のスケール倍率（1.0=デフォルトサイズ）
enlarged_card_mouse_y = None  # 拡大表示開始時のマウスY座標
show_opponent_hand = False  # 相手の手札表示切替（デフォルト非表示）
# モジュールローカルのログビュー（overlayモジュールの複数ロード問題対策）
current_log_view = 'detail'
# BGM設定（設定画面で変更可）
bgm_enabled = True
bgm_volume = 0.8
current_bgm_mode = None

# デッキモード: 'fixed'=ルールデッキ(24枚), 'custom'=作成デッキ(20枚)
DECK_MODE = 'fixed'

# 最後に選択されたカスタムデッキの情報（デッキ詳細を見た後にバトル開始する場合に使用）
_selected_deck_slot_idx = None
_selected_deck_card_names = None

# デッキ管理関数(_custom_decks_dir, list_custom_decks, load_custom_deck_by_name, 
# build_game_from_card_names, build_deck_for_mode, build_ai_player)は
# game/deck_manager.pyに移行済みのため削除しました

# set_bgm_modeはaudio/bgm_manager.pyに移行済みのため削除しました

def _generate_random_gimmick_cards(count: int = 4) -> List[Card]:
    """ゲーム開始時にプレイヤーとAIに配布するギミックカードをランダムに生成する。
    
    Args:
        count: 生成するギミックカードの枚数（デフォルト4枚）
    
    Returns:
        Card オブジェクトのリスト
    """
    try:
        # card_core.py の make_rule_cards_deck に定義されているギミックカード8種類
        gimmick_pool = [
            Card("灼熱", 2, eff_heat_block_tile),
            Card("氷結", 2, eff_freeze_piece),
            Card("暴風", 3, eff_storm_jump_once),
            Card("迅雷", 3, eff_lightning_two_actions),
            Card("2ドロー", 1, eff_draw2),
            Card("錬成", 0, eff_alchemy),
            Card("墓地ルーレット", 1, eff_graveyard_roulette),
            Card("摂取", 1, eff_leech_pp2),
        ]
        # ランダムに count 枚選択するが、同一ギミックは最大3枚までとする
        import random
        max_per_card = 3
        selected: List[Card] = []
        counts = {c.name: 0 for c in gimmick_pool}
        # シャッフルしてから選ぶことで偏りを抑える
        pool_indices = list(range(len(gimmick_pool)))
        # スタート時のギミックは同一カードが4枚になるべきではないため、
        # 重複が上限に達するまでリトライして選ぶ実装にする
        while len(selected) < count:
            if not pool_indices:
                pool_indices = list(range(len(gimmick_pool)))
            idx = random.choice(pool_indices)
            card = gimmick_pool[idx]
            if counts[card.name] < max_per_card:
                selected.append(card)
                counts[card.name] += 1
            else:
                # そのカードは上限に達したため候補から一時的に除外
                try:
                    pool_indices.remove(idx)
                except Exception:
                    pass
            # Safety: 無限ループ回避（理論上起きないが保険）
            if not pool_indices and len(selected) < count:
                # すべてのカードが上限に達した場合は残りをランダムで埋める
                remaining = count - len(selected)
                for _ in range(remaining):
                    selected.append(random.choice(gimmick_pool))
                break
        return selected
    except Exception:
        # エラー時は空リストを返す（ゲーム進行を止めない）
        return []

def new_game_with_mode(mode: str):
    """Create a new Game with player's deck and return the Game object.

    This mirrors new_game_with_rule_deck but allows trimming the deck
    based on the selected mode.
    
    NOTE: 'custom' mode should NOT be used directly; use build_game_from_card_names instead
    to ensure the saved deck is properly loaded.
    """
    try:
        # Allow both 'fixed' and 'custom'; default to 'fixed' if unknown
        if mode not in ('fixed', 'custom'):
            logger.warning("new_game_with_mode called with mode=%s, falling back to fixed", mode)
            mode = 'fixed'

        deck = build_deck_for_mode(mode)
        if deck is None:
            # fallback to rule deck
            deck = make_rule_cards_deck()
        # Noneや空データを除外
        deck.cards = [c for c in getattr(deck, 'cards', []) if c is not None]
        deck.shuffle()
        player = PlayerState(deck=deck)
        game = Game(player=player)
        # Wrap game.log so appended messages are recorded into master_log too
        try:
            # preserve any existing entries
            existing = list(getattr(game, 'log', []) or [])
            game.log = LogList('game', existing)
        except Exception:
            try:
                game.log = LogList('game')
            except Exception:
                pass
        # PPを最大に回復（setup_battleの代わりに手動で行う）
        try:
            player.reset_pp()
            game.log.append("バトル開始: PPを最大まで回復しました。")
        except Exception:
            pass
        
        # 固定デッキ(24枚)の場合について:
        # 以前は先頭から無差別に4枚を取り除いていましたが、
        # ギミック配布時に同名カードを追加すると種類ごとの上限(3枚)を
        # 超えてしまう可能性がありました。
        # ここでは先にデッキをそのままにしておき、後で配布するギミックと
        # 同名のカードがデッキに存在すれば1枚ずつ取り除く実装に変更します。

        # ゲーム開始時にプレイヤーにギミックカード4枚のみを配布（固定デッキのみ）
        try:
            if mode == 'fixed':
                gimmick_cards = _generate_random_gimmick_cards(4)
                for gc in gimmick_cards:
                    if gc is not None:
                        player.hand.add(gc)
                # 配布したギミックと同名のカードがデッキに残っていれば
                # 同数だけデッキから取り除くことで、種類ごとの最大枚数が
                # 守られるようにする。
                try:
                    if hasattr(player, 'deck') and hasattr(player.deck, 'cards'):
                        for gc in gimmick_cards:
                            if gc is None:
                                continue
                            for i, dcard in enumerate(list(player.deck.cards)):
                                if getattr(dcard, 'name', None) == getattr(gc, 'name', None):
                                    try:
                                        player.deck.cards.pop(i)
                                    except Exception:
                                        pass
                                    break
                except Exception:
                    pass
                if gimmick_cards and hasattr(game, 'log'):
                    game.log.append("バトル開始: ギミックカード4枚を受け取りました。")
        except Exception:
            pass
        
        # Register GIF animation hook
        try:
            if _animation_module and hasattr(_animation_module, 'play_ic_gif_at'):
                game.play_ic_gif = _animation_module.play_ic_gif_at
        except Exception:
            pass
        return game
    except Exception:
        # Last resort, call existing helper
        try:
            return new_game_with_rule_deck()
        except Exception:
            return None


def show_deck_choice_modal(screen):
    """Show a modal letting the user pick between fixed deck and created deck.
    
    NOTE: このファイル内の実装は、ui.modals.deck_modals に完全版が存在します。
    TODO: 将来的には ui.modals.show_deck_choice_modal を直接使用するように
          シグネチャを統一し、このファイルの実装を削除する。
    
    Sets global `DECK_MODE` to 'fixed' or 'custom'. If user selects the
    created deck option, opens the deck list modal for inspection.
    """
    global DECK_MODE
    clk = pygame.time.Clock()
    # デバウンス: 連続呼び出し防止
    try:
        global _last_deck_choice_open_time
    except Exception:
        _last_deck_choice_open_time = None
    try:
        now = _ct_time.time()
        if _last_deck_choice_open_time and (now - _last_deck_choice_open_time) < 0.5:
            return False
        _last_deck_choice_open_time = now
    except Exception:
        pass
    # モーダルを開いたクリックイベントをフラッシュ（二重アクション防止）
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass
    w, h = 560, 240
    x = (W - w)//2
    y = (H - h)//2

    # snapshot background to keep previous screen visible under overlay
    try:
        _bg_frame = screen.copy()
    except Exception:
        _bg_frame = None

    # Button geometry
    btn_w = 220
    btn_h = 80
    left_x = x + 50
    right_x = x + w - btn_w - 32
    by = y + 80

    while True:
        # get current window size each frame so UI components position correctly
        win_w, win_h = screen.get_size()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                # ユーザーがEscを押したら、前の画面に戻る（何も選択しない）
                return False
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                # close icon (top-right of modal) — screen coordinates
                close_rect = pygame.Rect(x + w - 34, y + 8, 26, 26)
                if close_rect.collidepoint(mx, my):
                    return False
                # fixed deck
                if left_x <= mx <= left_x + btn_w and by <= my <= by + btn_h:
                    # If user explicitly chooses fixed deck, clear any previously
                    # saved custom-deck selection so it doesn't accidentally
                    # override later deck rebuilds.
                    global _selected_deck_card_names, _selected_deck_slot_idx
                    DECK_MODE = 'fixed'
                    _selected_deck_card_names = None
                    _selected_deck_slot_idx = None
                    return True
                # created deck
                if right_x <= mx <= right_x + btn_w and by <= my <= by + btn_h:
                    # User chose created decks. Do not open the extra modal overlay;
                    # instead mark DECK_MODE as 'custom' and return so the main
                    # deck-list screen remains interactive and in front.
                    DECK_MODE = 'custom'
                    return True

        # draw overlay/modal
        if _bg_frame is not None:
            try:
                screen.blit(_bg_frame, (0,0))
            except Exception:
                pass
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((210,215,220))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)

        title = FONT.render("デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        # fixed deck button
        fixed_rect = pygame.Rect(left_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), fixed_rect)
        pygame.draw.rect(surf, (70,70,70), fixed_rect, 2)
        t1 = SMALL.render("固定デッキ （デフォルト）", True, (30,30,30))
        # 固定デッキ枚数表示（中央揃え）
        t2 = SMALL.render(f"カード数: 24 / 24", True, (80,80,80))
        surf.blit(t1, (fixed_rect.x + 6, fixed_rect.y + 12))
        surf.blit(t2, (fixed_rect.x + (btn_w - t2.get_width())//2, fixed_rect.y + 40))

        # custom deck button
        custom_rect = pygame.Rect(right_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), custom_rect)
        pygame.draw.rect(surf, (70,70,70), custom_rect, 2)
        c1 = SMALL.render("作成したデッキ（暫定）", True, (30,30,30))
        # 作成デッキ枚数表示（実際の枚数を取得）
        try:
            from game.deck_manager import load_saved_decks
            custom_decks = load_saved_decks()
            # 先頭の作成デッキを取得（Noneでなければ）
            first_deck = custom_decks[0] if custom_decks and custom_decks[0] else None
            if first_deck and isinstance(first_deck, dict):
                cards_field = first_deck.get('cards', [])
                deck_len = len(cards_field) if isinstance(cards_field, list) else 0
            else:
                deck_len = 0
        except Exception:
            deck_len = 0
        c2 = SMALL.render(f"カード数: {deck_len} / 20", True, (80,80,80))
        surf.blit(c1, (custom_rect.x + (btn_w - c1.get_width())//2, custom_rect.y + 12))
        surf.blit(c2, (custom_rect.x + (btn_w - c2.get_width())//2, custom_rect.y + 40))

        # close icon at top-right of modal
        pygame.draw.rect(surf, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(surf, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            surf.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass

        screen.blit(surf, (x,y))
        pygame.display.flip()
        clk.tick(30)

# CPU 難易度 (1=Easy,2=Medium,3=Hard,4=Expert)
CPU_DIFFICULTY = 2

# 画像の読み込み（カード名と同じファイル名.png を images 配下から探す）
# IMG_DIR is already imported from image_loader module above
_image_cache = {}
card_rects = []  # カードのクリック判定用矩形リスト
_piece_image_cache = {}
# master_log: 全ログの時系列マスター（各ログ追加を一意の連番で記録）
master_log = []  # list of tuples (seq:int, source:str, msg:str)
_log_seq = 0


class LogList(list):
    """List wrapper that records appended messages into master_log with sequence IDs.

    Behaves like a normal list for existing code, but intercepts append/extend to
    also add entries to `master_log` for cross-list chronological ordering.
    """
    def __init__(self, name, initial=None):
        super().__init__(initial or [])
        self._name = name

    def append(self, item):
        global _log_seq, master_log
        try:
            _log_seq += 1
            master_log.append((_log_seq, self._name, str(item)))
            logger.debug("[DEBUG LogList] %s.append: seq=%s, msg=%s, master_log size=%d", self._name, _log_seq, str(item)[:50], len(master_log))
        except Exception as e:
            logger.debug("[DEBUG LogList] %s.append FAILED: %s", self._name, e)
        return super().append(item)

    def extend(self, items):
        for it in items:
            self.append(it)


chess_log = LogList('chess')  # チェス専用ログ（カード用の game.log と分離）

# プレイ画面用背景画像の候補とキャッシュ
PLAY_BG_FILENAME = "ChatGPT Image 2025年11月4日 11_12_06.png"
play_bg_img = None      # 元画像を保持（リサイズ用）
play_bg_surf = None     # 現在のウィンドウサイズに合わせたスケール済みサーフ

# クリックターゲットなどのグローバル初期値（未定義参照による例外を防止）
confirm_yes_rect = None
confirm_no_rect = None
start_turn_rect = None
grave_label_rect = None
opponent_hand_rect = None
grave_card_rects = []
scrollbar_rect = None
dragging_scrollbar = False
drag_start_y = 0
drag_start_offset = 0
# スクロールバードラッグ用（draw_panelで計算される値）
_max_scroll = 0  # ログスクロールの最大値
# Heat choice button rects (灼熱の二択ボタン)
heat_choice_unfreeze_rect = None
heat_choice_block_rect = None

# GIFアニメーション関連の変数はassets.animation.pyから参照
# (heat_gif_anim, ic_gif_anim, mg_gif_*など)

# DEBUG: 反撃チェック検証モード (F6でON/OFF)
# デバッグ関数(_debug_mark_card_played, debug_setup_*)はdebug/debug_tools.pyに移行済みのため削除しました
# draw_dashed_rect関数はutils/drawing.pyに移行済みのため削除しました

"""
------------------ Chess integration (via external module) ------------------
UI側で持つ状態のみここに保持し、ルールや盤面状態（pieces等）は chess_rules_simple モジュールに委譲します。
"""
selected_piece = None  # 選択中の駒（dict）
highlight_squares = []  # ハイライトする移動先座標のリスト
chess_current_turn = 'white'
import time as _ct_time
# 初期ターン表示
try:
    turn_telop_msg = "YOUR TURN"
    turn_telop_until = _ct_time.time() + 1.0
except Exception:
    turn_telop_msg = None
    turn_telop_until = 0.0
game_over = False      # ゲームが終わったかどうか
game_over_winner = None # 勝者（まだ決まっていない）

# 同時チェック管理（両者同時チェック時の特殊勝敗判定）
simul_check_active = False
simul_white_result = 'none'  # 'none'|'pending'|'cleared'|'failed'
simul_black_result = 'none'
white_turn_index = 0
black_turn_index = 0
last_turn_color = None
simul_white_deadline = None
simul_black_deadline = None

# AI thinking/display settings
# AI thinking/display settings
THINKING_ENABLED = True
# ユーザー要望によりデフォルトを2.0秒に延長
AI_THINK_DELAY = 1.7
THINK_DOT_FREQ = 4.0

# CPU waiting state
cpu_wait = False
cpu_wait_start = 0.0
# ターン切替用テロップ（中央表示）
turn_telop_msg = None
turn_telop_until = 0.0
# 短時間表示用の警告テキスト（ログ以外に画面表示するため）
notice_msg = None
notice_until = 0.0

# Debug関数は debug/debug_tools.py に移行済み（フォールバックは140-161行で定義済み）

def restart_game():
    """ゲームを初期状態にリセットして再戦する"""
    global game_over, game_over_winner, chess_current_turn, selected_piece, highlight_squares, cpu_wait, game, ai_player
    global log_scroll_offset

    # Clear previous logs so rematch/difficulty-change starts with fresh logs
    try:
        global master_log, _log_seq, chess_log
        # clear master and per-list logs
        try:
            master_log.clear()
        except Exception:
            master_log = []
        try:
            _log_seq = 0
        except Exception:
            _log_seq = 0
        try:
            if 'chess_log' in globals() and getattr(chess_log, 'clear', None):
                chess_log.clear()
        except Exception:
            pass
        try:
            if 'game' in globals() and game is not None and getattr(game, 'log', None):
                try:
                    game.log.clear()
                except Exception:
                    # replace with fresh LogList
                    try:
                        game.log = LogList('game')
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass
    
    # チェス盤を初期配置に（盤リセットは共通処理に任せる）
    try:
        chess.pieces[:] = chess.create_pieces()
    except Exception:
        pass
    try:
        chess.en_passant_target = None
    except Exception:
        pass
    # プロモーション状態をクリア
    try:
        chess_rules.clear_promotion_state(chess)
    except Exception:
        try:
            chess.promotion_pending = None
        except Exception:
            pass

    # ゲーム状態をリセット
    game_over = False
    game_over_winner = None
    chess_current_turn = 'white'
    selected_piece = None
    highlight_squares = []
    cpu_wait = False

    # カードゲーム部分もリセット

    # ユーザー要望: 再戦時は確認モーダルを表示せず、直前に使っていたデッキをそのまま使う
    try:
        # 直前の game が存在し、そのプレイヤーにデッキが保存されていればそれを再利用
        if game is not None and getattr(game, 'player', None) is not None and getattr(getattr(game, 'player', None), 'deck', None) is not None:
            # game / ai_player をそのまま再利用して UI/盤面だけ初期化する
            try:
                _prepare_new_battle_after_deck_already_selected()
                # reset log scroll
                log_scroll_offset = 0
                return
            except Exception:
                # 何らかの理由で既存 game の再利用に失敗した場合はフォールバックして新規作成へ
                logger.exception("Failed to reuse previous game for rematch; falling back to recreate")

        # 既存 game がなければ、現在の DECK_MODE に従って新しいゲームを作成する（モーダルは表示しない）
        try:
            if DECK_MODE == 'custom':
                # 作成デッキを読み込んでゲームを作成
                try:
                    saved_decks = load_saved_decks()
                    if saved_decks and saved_decks[0] and isinstance(saved_decks[0], dict):
                        deck_card_names = [card.get('name', '') for card in saved_decks[0].get('cards', [])]
                        if deck_card_names and 'build_game_from_card_names' in globals():
                            game = build_game_from_card_names(deck_card_names)
                        else:
                            # フォールバック: 作成デッキが無い場合は固定デッキ
                            game = new_game_with_mode('fixed')
                    else:
                        # 保存されたデッキが無い場合は固定デッキ
                        game = new_game_with_mode('fixed')
                except Exception:
                    logger.exception("Failed to load custom deck, falling back to fixed")
                    game = new_game_with_mode('fixed')
            else:
                # 固定デッキ
                game = new_game_with_mode('fixed')
            
            try:
                ai_player = build_ai_player(DECK_MODE)
                try:
                    _init_ai_start_hand(ai_player, 4, game)
                except Exception:
                    pass
                # フォールバック: AIの手札が0枚の場合は直接デッキから4枚引かせる
                try:
                    got = 0
                    if ai_player is not None and hasattr(ai_player, 'hand') and hasattr(ai_player, 'deck'):
                        try:
                            got = len(getattr(ai_player, 'hand').cards or [])
                        except Exception:
                            got = 0
                        if got == 0:
                            # Attempt to draw up to 4 cards safely
                            for _ in range(4):
                                try:
                                    c = ai_player.deck.draw()
                                    if c is not None:
                                        ai_player.hand.add(c)
                                except Exception:
                                    pass
                            try:
                                if game and hasattr(game, 'log'):
                                    game.log.append("[注意] AIの初期手札が0枚だったため、デッキから4枚を強制的に配布しました。")
                            except Exception:
                                pass
                except Exception:
                    pass
            except Exception:
                ai_player = None
        except Exception:
            # 失敗したら固定デッキで強制作成
            try:
                game = new_game_with_mode('fixed')
                ai_player = build_ai_player('fixed')
                try:
                    _init_ai_start_hand(ai_player, 4, game)
                except Exception:
                    pass
            except Exception:
                game = None
                ai_player = None
    except Exception:
        logger.exception("Unexpected error in restart_game")
    log_scroll_offset = 0
    
    # ターン開始フラグを初期化（1ターン目はボタン押下が必要）
    try:
        game.turn_active = False
        game.player_moved_this_turn = False
    except Exception:
        pass
    # 再戦時/再開時のフォールバック: AIの手札が0枚の場合はデッキから4枚を配布
    try:
        if globals().get('ai_player', None) is not None:
            try:
                ai = globals().get('ai_player')
                got = 0
                try:
                    got = len(getattr(ai, 'hand').cards or [])
                except Exception:
                    got = 0
                if got == 0 and hasattr(ai, 'deck') and getattr(ai, 'deck') is not None:
                    for _ in range(4):
                        try:
                            c = ai.deck.draw()
                            if c is not None:
                                ai.hand.add(c)
                        except Exception:
                            pass
                    try:
                        if game and hasattr(game, 'log'):
                            game.log.append("[注意] 再戦時: AIの手札が0枚だったため、デッキから4枚を強制的に配布しました。")
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception:
        pass

    game.log.append("=== ゲームを再開しました ===")
    game.log.append("白のターンです。[T]キーまたはゲーム開始ボタンを押してターンを開始してください。")


def _rebuild_deck_from_card_names(deck_card_names: list) -> bool:
    """保存されたカード名リストからプレイヤー/AIのデッキを再構築する。

    build_game_from_card_names は初期手札を引いてデッキを減らすため、
    一度仮ゲームを生成して手札+山札の合計カードを集め直し、改めて Deck を作り直す。
    """
    global game, ai_player

    if not deck_card_names:
        logger.debug("No deck_card_names provided for rebuild")
        return False

    try:
        # 仮ゲームを作成してカードインスタンスを取得（手札4枚 + 山札残り）
        temp_game = build_game_from_card_names(deck_card_names)
        if not temp_game or not hasattr(temp_game, 'player'):
            logger.debug("Temp game build failed for deck rebuild")
            return False

        try:
            cards_all = []
            cards_all.extend(getattr(temp_game.player.hand, 'cards', []) or [])
            cards_all.extend(getattr(temp_game.player.deck, 'cards', []) or [])
            # 念のため枚数チェック
            if len(cards_all) == 0:
                logger.debug("No cards collected from temp game for rebuild")
                return False
        except Exception as e:
            logger.debug("Failed to collect cards from temp game: %s", e)
            return False

        # 新しい Deck を構築し、シャッフルしてランダム性を確保
        try:
            new_player_deck = Deck(list(cards_all))
            new_player_deck.shuffle()
            game.player.deck = new_player_deck
            logger.debug("Player deck rebuilt and shuffled (%d cards)", len(cards_all))
        except Exception as e:
            logger.debug("Failed to rebuild/shuffle player deck: %s", e)
            return False

        # AI デッキも同じ構成で再構築（独立にシャッフル）
        try:
            new_ai_cards = list(cards_all)
            new_ai_deck = Deck(new_ai_cards)
            new_ai_deck.shuffle()
            if ai_player is not None:
                ai_player.deck = new_ai_deck
            logger.debug("AI deck rebuilt and shuffled (%d cards)", len(new_ai_cards))
        except Exception as e:
            logger.debug("Failed to rebuild AI deck: %s", e)
            # AI失敗は致命ではないため続行

        return True
    except Exception as e:
        logger.debug("Unexpected error in _rebuild_deck_from_card_names: %s", e)
        return False

def _prepare_new_battle_after_deck_already_selected():
    """Reset board/UI state when a new Game object has already been
    created (for example, show_start_screen() created globals()['game']).

    This mirrors the non-deck parts of restart_game() but does NOT prompt
    the user for deck selection; it assumes `game` and `ai_player` are
    already set to the desired values.
    """
    global game_over, game_over_winner, chess_current_turn, selected_piece, highlight_squares, cpu_wait
    global log_scroll_offset, game, ai_player
    global _selected_deck_card_names

    # Reset chess board state
    try:
        chess.pieces[:] = chess.create_pieces()
    except Exception:
        pass
    try:
        chess.en_passant_target = None
    except Exception:
        pass
    # プロモーション状態をクリア
    try:
        if chess_rules:
            chess_rules.clear_promotion_state(chess)
        else:
            chess.promotion_pending = None
    except Exception:
        pass

    # Reset UI/flow flags
    game_over = False
    game_over_winner = None
    chess_current_turn = 'white'
    selected_piece = None
    highlight_squares = []
    cpu_wait = False

    # Also ensure logs are reset for the new battle
    try:
        global master_log, _log_seq, chess_log
        try:
            master_log.clear()
        except Exception:
            master_log = []
        try:
            _log_seq = 0
        except Exception:
            _log_seq = 0
        try:
            if getattr(chess_log, 'clear', None):
                chess_log.clear()
        except Exception:
            pass
        try:
            if game is not None and getattr(game, 'log', None):
                try:
                    game.log.clear()
                except Exception:
                    try:
                        game.log = LogList('game')
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass

    # Reset card/chess-effect state on the Game object so lingering tiles/auras are cleared
    try:
        if game is not None:
            game.pending = None
            game.turn = 0
            game.blocked_tiles = {}
            game.frozen_pieces = {}
            game.blocked_tiles_owner = {}
            game.player_moved_this_turn = False
            game.turn_active = False
            game.player_consecutive_turns = 0
            game.ai_consecutive_turns = 0
            game.ai_next_move_can_jump = False
            game.player_ironwall_protection_turns = 0
            game.ai_ironwall_protection_turns = 0
            try:
                # also reset any per-turn movement flags
                if hasattr(game.player, 'extra_moves_this_turn'):
                    game.player.extra_moves_this_turn = 0
                if hasattr(game.player, 'next_move_can_jump'):
                    game.player.next_move_can_jump = False
            except Exception:
                pass
    except Exception:
        pass

    # Reset card game state: hand, deck, graveyard
    try:
        if game is not None and hasattr(game, 'player'):
            player = game.player
            # 手札をリセット
            if hasattr(player, 'hand') and hasattr(player.hand, 'cards'):
                player.hand.cards.clear()
            # 墓地をリセット
            if hasattr(player, 'graveyard'):
                try:
                    if hasattr(player.graveyard, 'cards'):
                        player.graveyard.cards.clear()
                    elif isinstance(player.graveyard, list):
                        player.graveyard.clear()
                except Exception:
                    pass
            # PPを最大に回復
            if hasattr(player, 'reset_pp'):
                player.reset_pp()
    except Exception as e:
        logger.debug("Failed to reset player card state: %s", e)

    # Reset AI card game state
    try:
        if ai_player is not None and hasattr(ai_player, 'hand'):
            # 手札をリセット
            if hasattr(ai_player, 'hand') and hasattr(ai_player.hand, 'cards'):
                ai_player.hand.cards.clear()
            # 墓地をリセット
            if hasattr(ai_player, 'graveyard'):
                try:
                    if hasattr(ai_player.graveyard, 'cards'):
                        ai_player.graveyard.cards.clear()
                    elif isinstance(ai_player.graveyard, list):
                        ai_player.graveyard.clear()
                except Exception:
                    pass
            # PPを最大に回復
            if hasattr(ai_player, 'reset_pp'):
                ai_player.reset_pp()
    except Exception as e:
        logger.debug("Failed to reset AI card state: %s", e)

    # Rebuild decks from saved card names (only when DECK_MODE == 'custom')
    rebuilt = False
    if DECK_MODE == 'custom' and _selected_deck_card_names:
        try:
            rebuilt = _rebuild_deck_from_card_names(_selected_deck_card_names)
        except Exception as e:
            logger.debug("Failed to rebuild decks from card names: %s", e)

    # fixedデッキなどでカード名が保持されていない場合は、モードに応じて新デッキを生成
    if not rebuilt:
        try:
            new_deck = build_deck_for_mode(DECK_MODE)
            if new_deck:
                game.player.deck = new_deck
                game.player.deck.shuffle()
                if ai_player is not None:
                    ai_deck = build_deck_for_mode(DECK_MODE)
                    if ai_deck:
                        ai_deck.shuffle()
                        ai_player.deck = ai_deck
                rebuilt = True
                logger.debug("Decks rebuilt from mode=%s", DECK_MODE)
        except Exception as e:
            logger.debug("Failed to rebuild decks from mode %s: %s", DECK_MODE, e)

    # プレイヤーの初期手札をデッキからドローする（再戦時の初期化）
    try:
        if game is not None and hasattr(game, 'player'):
            draw_count = 4
            player = game.player
            # 手札を確実にクリアしてからドロー
            if hasattr(player, 'hand') and hasattr(player.hand, 'cards'):
                player.hand.cards.clear()
            for _ in range(draw_count):
                try:
                    c = player.deck.draw() if hasattr(player, 'deck') else None
                    if c is not None:
                        player.hand.add(c)
                except Exception:
                    pass
            if hasattr(game, 'log'):
                game.log.append(f"バトル開始時にデッキから{draw_count}枚ドローしました。")
    except Exception as e:
        logger.debug("Failed to draw initial player hand during rematch init: %s", e)

    # AIの初期手札をデッキからドローする（再戦時の初期化）
    try:
        if ai_player is not None:
            draw_count = 4
            # 手札を確実にクリアしてからドロー（既にクリア済みだが念のため）
            if hasattr(ai_player, 'hand') and hasattr(ai_player.hand, 'cards'):
                ai_player.hand.cards.clear()
            drawn_count = 0
            for _ in range(draw_count):
                try:
                    c = ai_player.deck.draw() if hasattr(ai_player, 'deck') else None
                    if c is not None:
                        ai_player.hand.add(c)
                        drawn_count += 1
                except Exception:
                    pass
            if drawn_count > 0 and hasattr(game, 'log'):
                game.log.append(f"AI: バトル開始時にデッキから{drawn_count}枚ドローしました。")
            logger.debug("_prepare_new_battle: AI drew %d cards, hand size=%d", drawn_count, len(ai_player.hand.cards) if hasattr(ai_player, 'hand') and hasattr(ai_player.hand, 'cards') else 0)
    except Exception as e:
        logger.debug("Failed to draw initial AI hand during rematch init: %s", e)

    # Ensure game/ai_player exist; do not recreate them here
    try:
        if game is not None:
            try:
                game.turn_active = False
                game.player_moved_this_turn = False
            except Exception:
                pass
    except Exception:
        pass

    log_scroll_offset = 0
    try:
        if game is not None:
            game.log.append("=== ゲームを再開しました ===")
            game.log.append("白のターンです。[T]キーまたはゲーム開始ボタンを押してターンを開始してください。")
    except Exception:
        pass

def _init_ai_start_hand(ai: object, n: int = 4, game_obj: object | None = None) -> None:
    """AIに開始時の初期手札としてデッキから4枚ドローさせる。

    PlayerState互換オブジェクト（deck.draw, hand.add, hand_limit, graveyard, reset_pp）を想定。
    ゲームログがあれば記録する。
    注: nパラメータは互換性のために残していますが、現在は使用されません。
    """
    try:
        if ai is None:
            logger.debug("_init_ai_start_hand: ai is None")
            return
        
        # デバッグ: AIのデッキ情報を確認
        try:
            deck_count = len(ai.deck.cards) if hasattr(ai, 'deck') and hasattr(ai.deck, 'cards') else 0
            logger.debug("_init_ai_start_hand: AI deck has %d cards", deck_count)
        except Exception as e:
            logger.debug("_init_ai_start_hand: Failed to get deck count: %s", e)
        
        # PPを最大へ
        try:
            if hasattr(ai, 'reset_pp'):
                ai.reset_pp()
        except Exception as e:
            logger.debug("_init_ai_start_hand: Failed to reset PP: %s", e)
        
        # デッキから初期手札を4枚引く
        try:
            draw_count = 4
            drawn_count = 0
            for i in range(draw_count):
                card = None
                try:
                    card = ai.deck.draw() if hasattr(ai, 'deck') else None
                except Exception as e:
                    logger.debug("_init_ai_start_hand: Failed to draw card %d: %s", i, e)
                
                if card:
                    try:
                        if hasattr(ai, 'hand'):
                            ai.hand.add(card)
                            drawn_count += 1
                            logger.debug("_init_ai_start_hand: Drew card %d: %s", i+1, card.name if hasattr(card, 'name') else str(card))
                        else:
                            logger.debug("_init_ai_start_hand: AI has no hand attribute")
                    except Exception as e:
                        logger.debug("_init_ai_start_hand: Failed to add card to hand: %s", e)
                else:
                    logger.debug("_init_ai_start_hand: Card %d is None (deck empty?)", i+1)
            
            # 最終的な手札枚数を確認
            try:
                final_hand_count = len(ai.hand.cards) if hasattr(ai, 'hand') and hasattr(ai.hand, 'cards') else 0
                logger.debug("_init_ai_start_hand: AI final hand count: %d (drew %d)", final_hand_count, drawn_count)
            except Exception:
                pass
            
            if drawn_count > 0 and game_obj and hasattr(game_obj, 'log'):
                game_obj.log.append(f"AI: バトル開始時にデッキから{drawn_count}枚ドローしました。")
        except Exception as e:
            logger.exception("_init_ai_start_hand: Error during card draw: %s", e)
    except Exception as e:
        logger.exception("_init_ai_start_hand: Unexpected error: %s", e)

def create_pieces():
    # 互換のためのエイリアス（将来的に削除予定）
    return chess.create_pieces()


def show_start_screen():
    """起動時に難易度を選択する簡易メニュー。
    1-4 のキーか、画面上のボタンで選択可能。選択はグローバル CPU_DIFFICULTY に保存される。
    """
    # 選択結果をグローバルに反映
    global CPU_DIFFICULTY, W, H, screen
    global _selected_deck_card_names, _selected_deck_slot_idx

    # NOTE:
    # Avoid unintentionally reusing a previously persisted custom-deck
    # selection when the user returns to the difficulty/start screen.
    # Persisted selections are useful for "rematch" flows, but when the
    # user explicitly returns to the difficulty menu we should show the
    # deck-selection UI again. Clear the persisted selection here so the
    # deck list/modal is presented normally.
    try:
        _selected_deck_card_names = None
        _selected_deck_slot_idx = None
    except Exception:
        pass
    # Prefer a repo-local background image (if present), otherwise fall back to user's Downloads
    repo_bg_path = os.path.join(IMG_DIR, "ChatGPT Image 2025年10月21日 14_06_32.png")
    user_bg_path = r"c:\Users\Student\Downloads\ChatGPT Image 2025年10月21日 14_06_32.png"
    bg_surf = None
    repo_bg_used = False
    try:
        if os.path.exists(repo_bg_path):
            img = pygame.image.load(repo_bg_path)
            bg_surf = pygame.transform.smoothscale(img, (W, H)).convert()
            repo_bg_used = True
        elif os.path.exists(user_bg_path):
            img = pygame.image.load(user_bg_path)
            bg_surf = pygame.transform.smoothscale(img, (W, H)).convert()
    except Exception:
        bg_surf = None

    # normalize names and prepare UI metrics/fonts used below
    bg = bg_surf
    # keep the original loaded image (if any) for rescaling on resize
    bg_img = locals().get('img', None)

    # Try to play title BGM (non-fatal if audio subsystem or file missing)
    try:
        set_bgm_mode('title')
    except Exception:
        pass

    while True:
        # Use the actual current surface size from the passed-in screen so the
        # UI aligns correctly when this module is used as an imported UI.
        win_w, win_h = screen.get_size()
        # DEBUG: 保存されたデッキ情報を確認
        try:
            logger.debug("show_start_screen: _selected_deck_card_names=%s, _selected_deck_slot_idx=%s", _selected_deck_card_names[:3] if _selected_deck_card_names else None, _selected_deck_slot_idx)
        except Exception:
            pass
        # recompute fonts/layout each frame so start screen responds to VIDEORESIZE
        title_font = get_font(max(32, int(H * 0.05)), bold=True)
        btn_font = get_font(max(20, int(H * 0.03)), bold=True)
        options = [("1 - 簡単", 1), ("2 - ノーマル", 2), ("3 - ハード", 3), ("4 - ベリーハード", 4)]
        # ボタン幅を広げてテキストが見切れないようにする
        btn_w = 260
        btn_h = 80
        # use larger horizontal spacing between buttons to match screenshot
        spacing = 20
        total_h = len(options) * btn_h + (len(options) - 1) * spacing
        # place title near top and move buttons further down to create generous whitespace like reference
        title_y = int(H * 0.08)
        # create a larger vertical gap between title and buttons per user request
        start_y = title_y + title_font.get_height() + 240

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.VIDEORESIZE:
                # update global window size and recreate screen surface
                try:
                    W, H = max(200, event.w), max(200, event.h)
                    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                    # rescale background image if we have the original loaded image
                    if bg_img is not None:
                        try:
                            bg = pygame.transform.smoothscale(bg_img, (W, H)).convert()
                        except Exception:
                            bg = bg_surf
                except Exception:
                    pass
            # keyboard selection (1-4)
            if event.type == pygame.KEYDOWN:
                if pygame.K_1 <= event.key <= pygame.K_4:
                    CPU_DIFFICULTY = event.key - pygame.K_0
                    # After difficulty selection, let user pick deck mode
                    try:
                        selected = show_deck_choice_modal(screen)
                    except Exception:
                        selected = False
                    # if the user canceled (Esc/×), don't start the game; keep showing menu
                    if not selected:
                        continue
                    # if custom decks were selected, always show deck list to pick a deck
                    try:
                        if DECK_MODE == 'custom':
                            started = show_deck_modal(screen, battle_select_mode=True)
                            if started:
                                return
                            else:
                                continue
                        else:
                            globals()['game'] = new_game_with_mode(DECK_MODE)
                            globals()['ai_player'] = build_ai_player(DECK_MODE)
                            try:
                                _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit(0)

            # mouse click or touch (FINGERDOWN)
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1) or event.type == pygame.FINGERDOWN:
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                else:
                    # map normalized touch coords to screen coords
                    mx = int(event.x * W)
                    my = int(event.y * H)

                # check difficulty buttons (horizontal layout)
                btn_x = (W - (btn_w*len(options) + spacing*(len(options)-1)))//2
                for i, (_lab, val) in enumerate(options):
                    bx = btn_x + i * (btn_w + spacing)
                    by = start_y
                    if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
                        CPU_DIFFICULTY = val
                        # deck choice modal
                        try:
                            selected = show_deck_choice_modal(screen)
                        except Exception:
                            selected = False
                        if not selected:
                            continue
                        try:
                            if DECK_MODE == 'custom':
                                # Always show deck list for user to pick manually
                                started = show_deck_modal(screen, battle_select_mode=True)
                                if started:
                                    return
                                else:
                                    continue
                            else:
                                globals()['game'] = new_game_with_mode(DECK_MODE)
                                globals()['ai_player'] = build_ai_player(DECK_MODE)
                                try:
                                    # AIも開始時に4枚ドロー（プレイヤーと同様の初期手札）
                                    _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                                except Exception:
                                    pass
                                try:
                                    gtmp = globals().get('game')
                                    logger.debug("global game set (start_screen) id=%s deck_count=%s", id(gtmp), len(getattr(gtmp.player.deck,'cards',[])) if gtmp and hasattr(gtmp,'player') else 'NA')
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        return

                # deck button (centered below) - match the drawing coordinates used later
                deck_w = 220  # matches deck_btn_w when drawing
                deck_h = 64   # matches deck_btn_h when drawing
                deck_x = (W - deck_w)//2
                # compute deck_y to match drawing: hint_y = start_y + btn_h + 140; deck_y = hint_y + 100
                deck_y = start_y + btn_h + 240
                # settings button on the left (same vertical position as deck button)
                settings_w = 180
                settings_h = deck_h
                settings_x = 20
                settings_y = deck_y
                if settings_x <= mx <= settings_x + settings_w and settings_y <= my <= settings_y + settings_h:
                    # open settings modal/screen
                    show_settings_screen(screen)
                    # consume click and continue the main loop (settings handles its own loop)
                    continue
                if deck_x <= mx <= deck_x + deck_w and deck_y <= my <= deck_y + deck_h:
                    # open deck selection modal (deck editor requires slot context)
                    show_deck_modal(screen)

        # draw background (image if available) - always scale to current window size
        try:
            win_w, win_h = screen.get_size()
        except Exception:
            win_w, win_h = W, H

        bg_frame = None
        # If we have an original loaded image, always scale it to the current size
        if bg_img is not None:
            try:
                bg_frame = pygame.transform.smoothscale(bg_img, (win_w, win_h)).convert()
            except Exception:
                bg_frame = bg
        else:
            # If we only have a previously-scaled surface, use it when sizes match,
            # otherwise rescale it to the current window size for consistent filling.
            if bg is not None:
                try:
                    if getattr(bg, 'get_size', None) and bg.get_size() == (win_w, win_h):
                        bg_frame = bg
                    else:
                        bg_frame = pygame.transform.smoothscale(bg, (win_w, win_h)).convert()
                except Exception:
                    bg_frame = None

        if bg_frame is not None:
            try:
                screen.blit(bg_frame, (0, 0))
                # apply brighten overlay depending on source
                bright = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
                if repo_bg_used:
                    bright.fill((255, 255, 255, 10))
                else:
                    bright.fill((255, 255, 255, 40))
                screen.blit(bright, (0, 0))
            except Exception:
                try:
                    screen.fill((150, 100, 50))
                except Exception:
                    pass
        else:
            # lighter sepia fallback
            try:
                screen.fill((150, 100, 50))
            except Exception:
                pass

        # gentle dark overlay to maintain contrast but keep background visible
        overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
        overlay.fill((0,0,0,30))  # 減少: 80 -> 30 (背景をもっと見えるように)
        screen.blit(overlay, (0,0))

        # Title with outline (dark fill with light outline to match screenshot)
        title_text = "CPUの難易度を設定してください"
        title_surf = title_font.render(title_text, True, (30,30,30))
        tx = (W - title_surf.get_width())//2
        ty = title_y
        # subtle outline (light) behind the darker text
        outline_surf = title_font.render(title_text, True, (240,240,240))
        for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            screen.blit(outline_surf, (tx+ox, ty+oy))
        screen.blit(title_surf, (tx, ty))

        # horizontal buttons (4 across) to match provided image
        btn_x = (W - (btn_w*4 + spacing*3))//2
        for i, (lab, val) in enumerate(options):
            bx = btn_x + i * (btn_w + spacing)
            by = start_y
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            # button fill and darker border
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (80,80,80), rect, 4)
            txt = btn_font.render(lab, True, (30,30,30))
            screen.blit(txt, (bx + (btn_w-txt.get_width())//2, by + (btn_h-txt.get_height())//2))

        # hint text and deck button (centered below buttons) - push further down per request
        hint = title_font.render("キー1-4でも選択できます。Escで終了", True, (240,240,240))
        hint_y = start_y + btn_h + 140
        screen.blit(hint, ((W-hint.get_width())//2, hint_y))

        deck_btn_w = 220
        deck_btn_h = 64
        deck_x = (W - deck_btn_w)//2
        deck_y = hint_y + 100
        deck_rect = pygame.Rect(deck_x, deck_y, deck_btn_w, deck_btn_h)
        pygame.draw.rect(screen, (230,230,230), deck_rect)
        pygame.draw.rect(screen, (70,70,70), deck_rect, 3)
        dtxt = btn_font.render("デッキ作成", True, (30,30,30))
        screen.blit(dtxt, (deck_x + (deck_btn_w - dtxt.get_width())//2, deck_y + (deck_btn_h - dtxt.get_height())//2))
        # Settings button (left bottom, same vertical as deck button)
        try:
            settings_w = 180
            settings_h = deck_btn_h
            settings_x = 20
            settings_y = deck_y
            settings_rect = pygame.Rect(settings_x, settings_y, settings_w, settings_h)
            pygame.draw.rect(screen, (230,230,230), settings_rect)
            pygame.draw.rect(screen, (70,70,70), settings_rect, 3)
            stxt = btn_font.render("設定", True, (30,30,30))
            screen.blit(stxt, (settings_x + (settings_w - stxt.get_width())//2, settings_y + (settings_h - stxt.get_height())//2))
        except Exception:
            pass
        # BGM クレジット表示（右下） 
        try:
            credit_text = "BGM:MusMus様"
            # create a bold variant for slightly thicker text
            try:
                credit_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", SMALL.get_height(), bold=True)
            except Exception:
                credit_font = SMALL
            # darker fill color for "濃く"
            fill_color = (200, 200, 200)
            outline_color = (10, 10, 10)
            credit_surf = credit_font.render(credit_text, True, fill_color)
            # draw a slightly darker outline for readability
            try:
                outline = credit_font.render(credit_text, True, outline_color)
                x = W - credit_surf.get_width() - 14
                y = H - credit_surf.get_height() - 40
                # outline offset (one pixel) then draw the main text twice to emphasize weight
                screen.blit(outline, (x + 1, y + 1))
            except Exception:
                x = W - credit_surf.get_width() - 14
                y = H - credit_surf.get_height() - 40
            # draw main text twice with tiny offset to make it visually bolder
            try:
                screen.blit(credit_surf, (x, y))
                screen.blit(credit_surf, (x + 1, y))
            except Exception:
                try:
                    screen.blit(credit_surf, (x, y))
                except Exception:
                    pass
        except Exception:
            pass

        pygame.display.flip()
        clock.tick(30)


# デッキ管理システムは game/deck_manager.py に移行済み（フォールバックは180-200行で定義済み）

def show_deck_modal(screen, battle_select_mode=False):
    """デッキリスト画面（3x3グリッド表示）。
    既存の saved_decks.json を読み込み、9スロットを表示します。
    空スロットは「作成」ボタンでデッキ作成へ移動。既存デッキをクリックすると
    小さなアクションモーダルを開きます。
    """
    # Present the deck-selection screen as a fullscreen view (non-blocking overlay)
    global W, H
    clk = pygame.time.Clock()
    
    # Debounce: prevent immediate re-entry when called twice by the same click
    try:
        global _last_deck_modal_open_time
    except Exception:
        _last_deck_modal_open_time = None
    try:
        now = _ct_time.time()
        if _last_deck_modal_open_time and (now - _last_deck_modal_open_time) < 0.5:
            return False
        _last_deck_modal_open_time = now
    except Exception:
        pass
    # Flush the click/touch that opened the modal to avoid immediate
    # double-activation of the selected slot (same rationale as above).
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass
    while True:
        # refresh authoritative window/surface size each frame so modals
        # recompute layout correctly after resize/fullscreen changes
        try:
            W, H = _refresh_display_size_from_pygame()
        except Exception:
            try:
                W, H = screen.get_size()
            except Exception:
                pass
        # keep current window size in local variables for positioning dialogs/buttons
        win_w, win_h = W, H
        # load saved decks each frame so external edits are reflected immediately
        decks = load_saved_decks()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # visible debug output so user can see clicks in PowerShell
                try:
                    logger.info(f"anim modal MOUSEBUTTONDOWN at {mx},{my}")
                except Exception:
                    logger.debug("anim modal MOUSEBUTTONDOWN at %d,%d", mx, my)
                # Back button click (画面下部の「戻る」)
                back_chk = pygame.Rect(20, H - 70, 120, 50)
                if back_chk.collidepoint(mx, my):
                    return
                # compute grid geometry (centered)
                w = 720; h = 480
                x = (W - w)//2; y = (H - h)//2
                slot_w = (w - 40) // 3
                slot_h = (h - 80) // 3
                rel_x = mx - x - 10
                rel_y = my - y - 40
                if rel_x < 0 or rel_y < 0:
                    continue
                col = rel_x // (slot_w + 10)
                row = rel_y // (slot_h + 10)
                if col < 0 or col > 2 or row < 0 or row > 2:
                    continue
                slot_idx = int(row * 3 + col)
                if slot_idx < 0 or slot_idx >= len(decks):
                    continue
                if decks[slot_idx]:
                    # existing deck -> either action modal or battle-select flow
                    if battle_select_mode:
                        # ask user to confirm starting battle with this deck
                        start = show_deck_battle_confirm(screen, decks[slot_idx], slot_idx)
                        # reload decks in case of edits
                        decks = load_saved_decks()
                        if start:
                            # user chose to start battle with this deck
                            names = []
                            if decks[slot_idx]:
                                cards_field = decks[slot_idx].get('cards', [])
                            # Validate custom deck size: disallow decks larger than 20 cards
                            try:
                                if cards_field is not None and len(cards_field) > 20:
                                    # Show a blocking warning modal to the user
                                    try:
                                        msg = f"選択したデッキは{len(cards_field)}枚です。\n最大20枚までです。\n\n20枚を超えているためゲームで使用できません！"
                                        # modal loop
                                        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                                        overlay.fill((0, 0, 0, 150))
                                        font = get_font(max(18, int(H * 0.025)))
                                        ok_font = get_font(max(16, int(H * 0.02)), bold=True)
                                        # prepare message lines
                                        lines = msg.split('\n')
                                        modal_w = min(800, int(W * 0.6))
                                        modal_h = max(160, 40 * len(lines) + 80)
                                        modal_x = (W - modal_w) // 2
                                        modal_y = (H - modal_h) // 2
                                        ok_rect = pygame.Rect(modal_x + modal_w//2 - 60, modal_y + modal_h - 60, 120, 40)
                                        showing = True
                                        while showing:
                                            for mev in pygame.event.get():
                                                if mev.type == pygame.QUIT:
                                                    pygame.quit(); sys.exit(0)
                                                if (mev.type == pygame.KEYDOWN and mev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE)):
                                                    showing = False
                                                if mev.type == pygame.MOUSEBUTTONDOWN and mev.button == 1:
                                                    mx, my = mev.pos
                                                    if ok_rect.collidepoint(mx, my):
                                                        showing = False
                                            # draw overlay + modal
                                            try:
                                                screen.blit(overlay, (0,0))
                                                pygame.draw.rect(screen, (240,240,240), (modal_x, modal_y, modal_w, modal_h))
                                                pygame.draw.rect(screen, (100,100,100), (modal_x, modal_y, modal_w, modal_h), 2)
                                                # draw text
                                                ty = modal_y + 20
                                                for ln in lines:
                                                    surf = font.render(ln, True, (20,20,20))
                                                    screen.blit(surf, (modal_x + 20, ty))
                                                    ty += surf.get_height() + 6
                                                # OK button
                                                pygame.draw.rect(screen, (50,120,200), ok_rect)
                                                ok_s = ok_font.render("OK", True, (255,255,255))
                                                screen.blit(ok_s, (ok_rect.x + (ok_rect.w - ok_s.get_width())//2, ok_rect.y + (ok_rect.h - ok_s.get_height())//2))
                                                pygame.display.flip()
                                                clk.tick(30)
                                            except Exception:
                                                # if drawing fails, just sleep briefly and continue the modal loop
                                                try:
                                                    pygame.time.wait(100)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        logger.warning("Selected custom deck invalid size (%d) - user notified", len(cards_field))
                                    # keep modal open (do not start battle)
                                    continue
                            except Exception:
                                pass
                            # saved format may be list of card-name strings or list of dicts
                            if isinstance(cards_field, list):
                                if cards_field and isinstance(cards_field[0], dict):
                                    names = [str(c.get('name')) for c in cards_field if c and 'name' in c]
                                else:
                                    names = [str(x) for x in cards_field]
                            try:
                                logger.debug("show_deck_modal starting battle, names=%s", names)
                                # Remember that user explicitly chose a custom deck so future
                                # rematches or returning to menus should preserve this choice.
                                global DECK_MODE, _selected_deck_card_names, _selected_deck_slot_idx
                                DECK_MODE = 'custom'
                                _selected_deck_card_names = names
                                _selected_deck_slot_idx = slot_idx
                                if names and 'build_game_from_card_names' in globals():
                                    logger.debug("Calling build_game_from_card_names with names=%s", names)
                                    g = build_game_from_card_names(names)
                                    if g is not None:
                                        globals()['game'] = g
                                        # DEBUG: 作成されたゲームのデッキをログ出力
                                        try:
                                            player_hand = [c.name for c in g.player.hand.cards]
                                            player_deck_first_5 = [c.name for c in g.player.deck.cards[:5]]
                                            logger.debug("Created game from names - hand=%s, deck_first_5=%s", player_hand, player_deck_first_5)
                                        except Exception:
                                            pass
                                    else:
                                        # If build_game_from_card_names failed, fall back to custom deck build
                                        logger.warning("build_game_from_card_names returned None, using custom deck as fallback")
                                        globals()['game'] = new_game_with_mode('custom')
                                else:
                                    logger.warning("names empty or build_game_from_card_names not available, using fixed deck as fallback")
                                    globals()['game'] = new_game_with_mode('custom')
                                globals()['ai_player'] = build_ai_player('custom')
                                try:
                                    _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                                except Exception:
                                    pass
                                # debug: print resulting deck composition if possible
                                try:
                                    g = globals().get('game')
                                    if g and hasattr(g, 'player') and hasattr(g.player, 'deck'):
                                        cards = getattr(g.player.deck, 'cards', None)
                                        if cards is not None:
                                            logger.debug("created game deck count=%d; first_cards=%s", len(cards), [c.name for c in cards[:8]])
                                except Exception as _e:
                                    logger.debug("error inspecting created game: %s", _e)
                            except Exception as e:
                                logger.debug("exception when creating game from names: %s", e)
                                # fallback to a safe default but keep DECK_MODE='custom'
                                globals()['game'] = new_game_with_mode('custom')
                                globals()['ai_player'] = build_ai_player('custom')
                                try:
                                    _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                                except Exception:
                                    pass
                            # cleanly exit; outer finally will clear in-progress flag
                            return True
                        continue
                    else:
                        # normal browsing: show small action modal
                        res = show_deck_action_modal(screen, decks[slot_idx], slot_idx)
                        # if deck was confirmed for later use (e.g., after viewing details),
                        # _selected_deck_* globals will be set, but we don't start battle yet
                        decks = load_saved_decks()
                        continue
                else:
                    # empty slot -> open editor to create new deck
                    new_deck = show_deck_editor(screen, None, slot_idx)
                    if new_deck:
                        decks[slot_idx] = new_deck
                        save_decks_to_file(decks)
                    continue

        # draw full-screen deck grid
        screen.fill((240, 235, 230))
        title_font = get_font(36, bold=True)
        title = title_font.render("作成デッキを選択してください", True, (30,30,30))
        screen.blit(title, ((W - title.get_width()) // 2, 24))

        w = 720; h = 480
        x = (W - w)//2; y = (H - h)//2
        slot_w = (w - 40) // 3
        slot_h = (h - 80) // 3
        sx = x + 10
        sy = y + 40
        idx = 0
        slot_font = get_font(20, bold=True)
        for r in range(3):
            for c in range(3):
                rx = sx + c * (slot_w + 10)
                ry = sy + r * (slot_h + 10)
                rect = pygame.Rect(rx, ry, slot_w, slot_h)
                # 既存デッキは青系で、未作成スロットはグレーで表示
                deck = decks[idx] if idx < len(decks) else None
                if deck:
                    # 背景は薄い青、枠は濃い青
                    pygame.draw.rect(screen, (220, 240, 255), rect)
                    pygame.draw.rect(screen, (60, 100, 160), rect, 4)
                    nm = deck.get('name', f'デッキ{idx+1}')
                    txt = SMALL.render(nm, True, (30,30,30))
                    screen.blit(txt, (rect.x + 12, rect.y + 12))
                    cnt = ''
                    if 'cards' in deck:
                        cnt = f"{len(deck['cards'])} 枚"
                    if cnt:
                        ctxt = SMALL.render(cnt, True, (60,60,60))
                        screen.blit(ctxt, (rect.right - ctxt.get_width() - 8, rect.y + 12))
                else:
                    pygame.draw.rect(screen, (245,245,250), rect)
                    pygame.draw.rect(screen, (80,80,80), rect, 3)
                    screen.blit(SMALL.render("デッキ作成", True, (100,100,100)), (rect.x + (rect.w - 100)//2, rect.y + (rect.h - 24)//2))
                idx += 1

        # back button
        back_rect = pygame.Rect(20, H - 70, 120, 50)
        pygame.draw.rect(screen, (200, 200, 200), back_rect)
        pygame.draw.rect(screen, (80, 80, 80), back_rect, 3)
        back_text = FONT.render("戻る", True, (30, 30, 30))
        screen.blit(back_text, (back_rect.x + (back_rect.width - back_text.get_width()) // 2,
                               back_rect.y + (back_rect.height - back_text.get_height()) // 2))

        pygame.display.flip()
        clk.tick(30)
    # end of modal


def show_deck_options(screen, deck):
    """デッキの編集/削除選択ダイアログ"""
    global W, H
    clock = pygame.time.Clock()
    
    while True:
        # keep authoritative display size up-to-date
        # global W, H
        try:
            W, H = _refresh_display_size_from_pygame()
        except Exception:
            try:
                W, H = screen.get_size()
            except Exception:
                pass
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                
                dialog_w, dialog_h = 400, 250
                dialog_x = (W - dialog_w) // 2
                dialog_y = (H - dialog_h) // 2
                
                # 編集ボタン
                edit_rect = pygame.Rect(dialog_x + 50, dialog_y + 80, 300, 50)
                if edit_rect.collidepoint(mx, my):
                    return 'edit'
                
                # 削除ボタン
                delete_rect = pygame.Rect(dialog_x + 50, dialog_y + 140, 300, 50)
                if delete_rect.collidepoint(mx, my):
                    return 'delete'
        
        # 暗転オーバーレイ
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0, 0))
        
        # ダイアログ
        dialog_w, dialog_h = 400, 250
        dialog_x = (W - dialog_w) // 2
        dialog_y = (H - dialog_h) // 2
        dialog_surf = pygame.Surface((dialog_w, dialog_h))
        dialog_surf.fill((210, 215, 220))
        pygame.draw.rect(dialog_surf, (80, 80, 80), (0, 0, dialog_w, dialog_h), 3)
        
        # タイトル
        title = FONT.render("デッキを選択", True, (30, 30, 30))
        dialog_surf.blit(title, ((dialog_w - title.get_width()) // 2, 20))
        
        # 編集ボタン
        edit_rect = pygame.Rect(50, 80, 300, 50)
        pygame.draw.rect(dialog_surf, (200, 220, 255), edit_rect)
        pygame.draw.rect(dialog_surf, (60, 100, 160), edit_rect, 3)
        edit_text = FONT.render("デッキ編集", True, (30, 30, 30))
        dialog_surf.blit(edit_text, ((dialog_w - edit_text.get_width()) // 2, 90))
        
        # 削除ボタン
        delete_rect = pygame.Rect(50, 140, 300, 50)
        pygame.draw.rect(dialog_surf, (255, 200, 200), delete_rect)
        pygame.draw.rect(dialog_surf, (160, 60, 60), delete_rect, 3)
        delete_text = FONT.render("デッキ削除", True, (30, 30, 30))
        dialog_surf.blit(delete_text, ((dialog_w - delete_text.get_width()) // 2, 150))
        
        screen.blit(dialog_surf, (dialog_x, dialog_y))
        pygame.display.flip()
        clock.tick(30)


def show_deck_battle_confirm(screen, deck, slot_idx):
    """Confirm dialog: ask the user whether to start battle with this deck.

    Returns True if user chose to start battle, False otherwise.
    """
    global W, H
    clk = pygame.time.Clock()
    w, h = 560, 240
    x = (W - w)//2
    y = (H - h)//2
    title_font = get_font(28)

    # snapshot background to keep previous screen visible under overlay
    try:
        _bg_frame = screen.copy()
    except Exception:
        _bg_frame = None

    while True:
        # refresh display size so modal positioning is correct after resize
        try:
            W, H = _refresh_display_size_from_pygame()
        except Exception:
            try:
                W, H = screen.get_size()
            except Exception:
                pass
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                if ev.key == pygame.K_y:
                    return True
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # compute local coords
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return False
                lx = mx - x
                ly = my - y
                # buttons
                btn_w = 160
                btn_h = 48
                gap = 24
                bx = (w - (btn_w*2 + gap)) // 2
                by = h - 80
                confirm_rect = pygame.Rect(bx, by, btn_w, btn_h)
                start_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
                # close icon (inside modal, top-right)
                close_rect = pygame.Rect(w-34, 8, 26, 26)
                if confirm_rect.collidepoint(lx, ly):
                    # show deck contents
                    show_deck_contents_overlay(screen, deck)
                    continue
                if close_rect.collidepoint(lx, ly):
                    return False
                if start_rect.collidepoint(lx, ly):
                    return True

        # draw
        if _bg_frame is not None:
            try:
                screen.blit(_bg_frame, (0,0))
            except Exception:
                pass
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))
        box = pygame.Surface((w, h))
        box.fill((210,215,220))
        try:
            logger.debug("show_deck_contents_overlay: C.C.B/CardGame.py bg=(240,235,230), size=(%d,%d)", w, h)
        except Exception:
            pass
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render("このデッキでバトルしますか？", True, (30,30,30))
        box.blit(title, (20, 24))

        # buttons: デッキ確認, バトルスタート
        btn_w = 160
        btn_h = 48
        gap = 24
        bx = (w - (btn_w*2 + gap)) // 2
        by = h - 80
        confirm_rect = pygame.Rect(bx, by, btn_w, btn_h)
        start_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
        pygame.draw.rect(box, (200,220,255), confirm_rect)
        pygame.draw.rect(box, (200,255,200), start_rect)
        # close icon at top-right of modal
        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            box.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass
        pygame.draw.rect(box, (80,80,80), confirm_rect, 2)
        pygame.draw.rect(box, (80,80,80), start_rect, 2)
        t_confirm = SMALL.render("デッキ確認", True, (30,30,30))
        t_start = SMALL.render("バトルスタート", True, (30,30,30))
        box.blit(t_confirm, (confirm_rect.x + (btn_w - t_confirm.get_width())//2, confirm_rect.y + (btn_h - t_confirm.get_height())//2))
        box.blit(t_start, (start_rect.x + (btn_w - t_start.get_width())//2, start_rect.y + (btn_h - t_start.get_height())//2))

        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


def show_deck_editor(screen, existing_deck, slot_idx):
    """デッキ作成/編集画面
    
    Args:
        screen: pygame surface
        existing_deck: 既存のデッキ（編集時）またはNone（新規作成時）
        slot_idx: デッキスロット番号（0-8）
    
    Returns:
        作成/編集されたデッキ辞書、またはNone（キャンセル時）
    """
    # 利用可能な全カード（ゲーム内で使用されるカードリスト）
    available_cards = [
        {'name': '灼熱', 'cost': 2},
        {'name': '氷結', 'cost': 2},
        {'name': '暴風', 'cost': 3},
        {'name': '迅雷', 'cost': 3},
        {'name': '2ドロー', 'cost': 1},
        {'name': '錬成', 'cost': 0},
        {'name': '墓地ルーレット', 'cost': 1},
        {'name': '摂取', 'cost': 1},
        {'name': '命がけのギャンブル', 'cost': 3},
        {'name': '負けるわけないだろwww', 'cost': 4},
        {'name': '鉄壁', 'cost': 2},
        {'name': 'ハンです☆', 'cost': 2},
    ]
    
    # 現在のデッキカード
    if existing_deck:
        deck_cards = existing_deck.get('cards', []).copy()
        deck_name = existing_deck.get('name', f'デッキ{slot_idx + 1}')
    else:
        deck_cards = []
        deck_name = f'デッキ{slot_idx + 1}'
    
    clock = pygame.time.Clock()
    scroll_offset = 0
    input_active = False
    input_text = deck_name
    textinput_buffer = ""  # TEXTINPUTイベント用バッファ（重複入力防止）
    
    global W, H
    # テキスト入力モード：一度有効にしたら無効にしない（日本語IME互換性のため）
    pygame.key.start_text_input()
    # initialize local window size variables (static analyzer friendly)
    win_w, win_h = screen.get_size()
    
    while True:
        # refresh authoritative display size each frame so layout matches
        try:
            W, H = _refresh_display_size_from_pygame()
        except Exception:
            try:
                W, H = screen.get_size()
            except Exception:
                pass
        # local copy
        win_w, win_h = W, H
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)

            # KEYDOWN イベント処理：制御キー（バックスペース、エンター、ESC）のみ
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    # ESCキー：入力終了して画面から抜ける
                    pygame.key.stop_text_input()
                    return None
                
                # テキストボックスが活性状態の場合のみ制御キーを処理
                if input_active:
                    if event.key == pygame.K_RETURN:
                        # エンターで入力終了
                        input_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        # バックスペースで文字削除
                        input_text = input_text[:-1]
            
            # TEXTINPUT イベント：全ての文字入力（アルファベット、日本語IME確定など）
            # このイベントが発火していることが前提
            if event.type == pygame.TEXTINPUT:
                if input_active and len(input_text) < 20:
                    # TEXTINPUTで入力された文字を直接追加
                    input_text += event.text

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # 右クリック
                mx, my = event.pos
                # カード画像ローダーをインポート
                try:
                    from assets.image_loader import get_card_image
                except Exception:
                    get_card_image = None
                
                if get_card_image:
                    # 全カードリストで右クリック
                    list_start_y = 110
                    card_h = 50
                    for i, card in enumerate(available_cards):
                        card_y = list_start_y + i * card_h - scroll_offset
                        if 110 <= card_y < H - 100:
                            card_rect = pygame.Rect(20, card_y, 500, card_h - 5)
                            if card_rect.collidepoint(mx, my):
                                show_card_detail(screen, card['name'], get_card_image)
                                break
                    
                    # デッキ内カードで右クリック
                    deck_start_x = win_w - 420
                    card_counts = {}
                    for card in deck_cards:
                        key = card['name']
                        if key not in card_counts:
                            card_counts[key] = {'name': card['name'], 'cost': card['cost'], 'count': 0}
                        card_counts[key]['count'] += 1
                    
                    display_idx = 0
                    for card_info in card_counts.values():
                        card_y = list_start_y + display_idx * card_h
                        if 110 <= card_y < win_h - 100:
                            card_rect = pygame.Rect(deck_start_x, card_y, 400, card_h - 5)
                            if card_rect.collidepoint(mx, my):
                                show_card_detail(screen, card_info['name'], get_card_image)
                                break
                        display_idx += 1
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                
                # 保存ボタン
                save_rect = pygame.Rect(win_w - 250, win_h - 70, 120, 50)
                if save_rect.collidepoint(mx, my):
                    # デッキ枚数チェック
                    if len(deck_cards) < 20:
                        logger.debug("save clicked with %d cards (<20) - entering confirmation dialog", len(deck_cards))
                        # 20枚未満でも保存を許可するか確認するダイアログに変更
                        # 「破棄する」-> 変更を破棄して戻る
                        # 「保存する」-> 20枚未満だが保存してデッキリストに戻る
                        show_warning = True
                        while show_warning:
                            for warn_ev in pygame.event.get():
                                if warn_ev.type == pygame.QUIT:
                                    pygame.quit(); sys.exit(0)
                                if warn_ev.type == pygame.MOUSEBUTTONDOWN and warn_ev.button == 1:
                                    wmx, wmy = warn_ev.pos
                                    dialog_w, dialog_h = 500, 220
                                    dialog_x = (win_w - dialog_w) // 2
                                    dialog_y = (win_h - dialog_h) // 2

                                    # 破棄ボタン
                                    discard_rect = pygame.Rect(dialog_x + 60, dialog_y + 140, 160, 50)
                                    if discard_rect.collidepoint(wmx, wmy):
                                        logger.debug("user selected DISCARD in low-deck dialog")
                                        pygame.key.stop_text_input()
                                        return None  # 変更破棄してデッキリストへ

                                    # 保存するボタン
                                    save_anyway_rect = pygame.Rect(dialog_x + 280, dialog_y + 140, 160, 50)
                                    if save_anyway_rect.collidepoint(wmx, wmy):
                                        logger.debug("user selected SAVE ANYWAY in low-deck dialog")
                                        # 20枚未満だが保存して戻る
                                        pygame.key.stop_text_input()
                                        return {
                                            'name': input_text if input_text.strip() else f'デッキ{slot_idx + 1}',
                                            'cards': deck_cards,
                                            'created_at': existing_deck.get('created_at', datetime.now().isoformat()) if existing_deck else datetime.now().isoformat()
                                        }

                            # 警告ダイアログ描画
                            overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
                            overlay.fill((0, 0, 0, 190))
                            screen.blit(overlay, (0, 0))

                            dialog_surf = pygame.Surface((dialog_w, dialog_h))
                            dialog_surf.fill((210,215,220))
                            pygame.draw.rect(dialog_surf, (200, 100, 100), (0, 0, dialog_w, dialog_h), 4)

                            # メッセージ
                            warn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18, bold=True)
                            msg1 = warn_font.render("20枚未満なのでバトルで使用できません。", True, (30, 30, 30))
                            msg2 = warn_font.render("このまま保存しますか？ (バトルでは使用不可)", True, (30, 30, 30))
                            dialog_surf.blit(msg1, ((dialog_w - msg1.get_width()) // 2, 40))
                            dialog_surf.blit(msg2, ((dialog_w - msg2.get_width()) // 2, 70))

                            # 破棄ボタン
                            discard_rect = pygame.Rect(60, 140, 160, 50)
                            pygame.draw.rect(dialog_surf, (255, 200, 200), discard_rect)
                            pygame.draw.rect(dialog_surf, (160, 60, 60), discard_rect, 3)
                            discard_text = FONT.render("破棄する", True, (30, 30, 30))
                            dialog_surf.blit(discard_text, (discard_rect.x + (discard_rect.width - discard_text.get_width()) // 2,
                                                            discard_rect.y + (discard_rect.height - discard_text.get_height()) // 2))

                            # 保存するボタン
                            save_anyway_rect = pygame.Rect(280, 140, 160, 50)
                            pygame.draw.rect(dialog_surf, (200, 255, 200), save_anyway_rect)
                            pygame.draw.rect(dialog_surf, (60, 160, 60), save_anyway_rect, 3)
                            save_anyway_text = FONT.render("保存する", True, (30, 30, 30))
                            dialog_surf.blit(save_anyway_text, (save_anyway_rect.x + (save_anyway_rect.width - save_anyway_text.get_width()) // 2,
                                                                save_anyway_rect.y + (save_anyway_rect.height - save_anyway_text.get_height()) // 2))

                            screen.blit(dialog_surf, (dialog_x, dialog_y))
                            pygame.display.flip()
                            clock.tick(30)

                    # 20枚以上なら保存
                    pygame.key.stop_text_input()
                    return {
                        'name': input_text if input_text.strip() else f'デッキ{slot_idx + 1}',
                        'cards': deck_cards,
                        'created_at': existing_deck.get('created_at', datetime.now().isoformat()) if existing_deck else datetime.now().isoformat()
                    }
                
                # キャンセルボタン
                cancel_rect = pygame.Rect(win_w - 140, win_h - 70, 120, 50)
                if cancel_rect.collidepoint(mx, my):
                    pygame.key.stop_text_input()
                    return None
                
                # テキストボックスをクリックした場合（名前入力を活性化）
                name_rect = pygame.Rect(300, 20, 400, 40)
                if name_rect.collidepoint(mx, my):
                    # テキストボックスをクリック → 入力モードON
                    input_active = True
                    # IME状態をリセット（IME使用中に別の入力に切り替わった場合の対策）
                    pygame.key.stop_text_input()
                    pygame.key.start_text_input()
                    # これ以上のイベント処理をスキップ
                else:
                    # テキストボックス以外をクリック → 入力モード終了
                    input_active = False
                    
                    # カードリストクリック（追加）
                    list_start_y = 110  # 描画と同じ位置に修正
                    card_h = 50
                    for i, card in enumerate(available_cards):
                        card_y = list_start_y + i * card_h - scroll_offset
                        if 110 <= card_y < H - 100:  # 範囲も修正
                            card_rect = pygame.Rect(20, card_y, 500, card_h - 5)
                            if card_rect.collidepoint(mx, my):
                                # 同じカードが最大3枚まで
                                count = sum(1 for c in deck_cards if c['name'] == card['name'])
                                if count < 3:
                                    deck_cards.append(card.copy())
                                break
                    
                    # デッキカードクリック（削除）- 集計表示に対応
                    deck_start_x = win_w - 420
                    # カードを集計
                    card_counts = {}
                    for card in deck_cards:
                        key = card['name']
                        if key not in card_counts:
                            card_counts[key] = {'name': card['name'], 'cost': card['cost'], 'count': 0}
                        card_counts[key]['count'] += 1
                    
                    display_idx = 0
                    for card_info in card_counts.values():
                        card_y = list_start_y + display_idx * card_h
                        if 110 <= card_y < win_h - 100:
                            card_rect = pygame.Rect(deck_start_x, card_y, 400, card_h - 5)
                            if card_rect.collidepoint(mx, my):
                                # このカードを1枚削除
                                for i, c in enumerate(deck_cards):
                                    if c['name'] == card_info['name']:
                                        deck_cards.pop(i)
                                        break
                                break
                        display_idx += 1
            
            if event.type == pygame.MOUSEWHEEL:
                scroll_offset -= event.y * 30
                scroll_offset = max(0, min(scroll_offset, len(available_cards) * 50 - 400))
        
        # 背景
        screen.fill((240, 235, 230))
        
        # タイトル
        title_font = get_font(28, bold=True)
        title = title_font.render("デッキ作成/編集", True, (30, 30, 30))
        screen.blit(title, (20, 25))
        
        # 名前入力欄
        name_rect = pygame.Rect(300, 20, 400, 40)
        pygame.draw.rect(screen, (255, 255, 255) if input_active else (240, 240, 240), name_rect)
        pygame.draw.rect(screen, (100, 150, 255) if input_active else (100, 100, 100), name_rect, 2)
        # 日本語対応フォントを直接ファイル指定で取得
        try:
            # Windowsの標準日本語フォントを直接読み込み
            import os
            font_paths = [
                "C:\\Windows\\Fonts\\msgothic.ttc",  # MSゴシック
                "C:\\Windows\\Fonts\\meiryo.ttc",    # メイリオ
                "C:\\Windows\\Fonts\\yugothic.ttf",  # 遊ゴシック
            ]
            name_font = None
            for font_path in font_paths:
                if os.path.exists(font_path):
                    name_font = pygame.font.Font(font_path, 24)
                    break
            if name_font is None:
                # フォールバック: システムフォント
                name_font = pygame.font.SysFont("msgothic,meiryo", 24)
        except:
            # 最終フォールバック
            name_font = pygame.font.Font(None, 24)
        
        name_text = name_font.render(input_text if input_text else "", True, (30, 30, 30))
        screen.blit(name_text, (name_rect.x + 10, name_rect.y + 8))
        
        # カーソル表示（点滅）
        if input_active:
            import time
            if int(time.time() * 2) % 2 == 0:  # 0.5秒ごとに点滅
                cursor_x = name_rect.x + 10 + name_text.get_width()
                cursor_y = name_rect.y + 8
                pygame.draw.line(screen, (30, 30, 30), 
                               (cursor_x, cursor_y), 
                               (cursor_x, cursor_y + name_text.get_height()), 2)
        
        # 全カードリスト
        list_title = FONT.render("全カード（クリックで追加）", True, (30, 30, 30))
        screen.blit(list_title, (20, 70))
        
        card_h = 50
        list_start_y = 110
        for i, card in enumerate(available_cards):
            card_y = list_start_y + i * card_h - scroll_offset
            if 80 <= card_y < H - 100:
                card_rect = pygame.Rect(20, card_y, 500, card_h - 5)
                pygame.draw.rect(screen, (220, 240, 255), card_rect)
                pygame.draw.rect(screen, (100, 120, 180), card_rect, 2)
                
                card_text = SMALL.render(f"{card['name']} (コスト: {card['cost']})", True, (30, 30, 30))
                screen.blit(card_text, (card_rect.x + 10, card_rect.y + 15))
                
                # デッキ内の枚数表示
                count = sum(1 for c in deck_cards if c['name'] == card['name'])
                if count > 0:
                    count_text = SMALL.render(f"{count}/3", True, (160, 60, 60) if count >= 3 else (60, 160, 60))
                    screen.blit(count_text, (card_rect.x + 450, card_rect.y + 15))
        
        # デッキ内カードリスト（重複をまとめて表示）
        deck_start_x = W - 420
        deck_title = FONT.render(f"デッキ内カード（{len(deck_cards)}枚）", True, (30, 30, 30))
        screen.blit(deck_title, (deck_start_x, 70))
        
        # カードを集計（重複をまとめる）
        card_counts = {}
        for card in deck_cards:
            key = card['name']
            if key not in card_counts:
                card_counts[key] = {'name': card['name'], 'cost': card['cost'], 'count': 0}
            card_counts[key]['count'] += 1
        
        # 集計結果を表示
        display_idx = 0
        for card_info in card_counts.values():
            card_y = list_start_y + display_idx * card_h
            if 110 <= card_y < H - 100:
                card_rect = pygame.Rect(deck_start_x, card_y, 400, card_h - 5)
                
                pygame.draw.rect(screen, (255, 240, 220), card_rect)
                pygame.draw.rect(screen, (180, 120, 100), card_rect, 2)
                
                card_text = SMALL.render(f"{card_info['name']} (コスト: {card_info['cost']}) ×{card_info['count']}枚", 
                                        True, (30, 30, 30))
                screen.blit(card_text, (card_rect.x + 10, card_rect.y + 15))
            display_idx += 1
        
        # ボタン類
        save_rect = pygame.Rect(W - 250, H - 70, 120, 50)
        pygame.draw.rect(screen, (200, 255, 200), save_rect)
        pygame.draw.rect(screen, (60, 160, 60), save_rect, 3)
        save_text = FONT.render("保存", True, (30, 30, 30))
        screen.blit(save_text, (save_rect.x + (save_rect.width - save_text.get_width()) // 2,
                               save_rect.y + (save_rect.height - save_text.get_height()) // 2))
        
        cancel_rect = pygame.Rect(W - 140, H - 70, 120, 50)
        pygame.draw.rect(screen, (255, 200, 200), cancel_rect)
        pygame.draw.rect(screen, (160, 60, 60), cancel_rect, 3)
        cancel_text = FONT.render("戻る", True, (30, 30, 30))
        screen.blit(cancel_text, (cancel_rect.x + (cancel_rect.width - cancel_text.get_width()) // 2,
                                 cancel_rect.y + (cancel_rect.height - cancel_text.get_height()) // 2))
        
        pygame.display.flip()
        clock.tick(30)
    
    # ループ終了時必ずテキスト入力モードを無効化
    pygame.key.stop_text_input()


def show_deck_modal_old(screen):
    """Simple deck modal - click/touch to close."""
    clock = pygame.time.Clock()
    w, h = 640, 420
    x = (W - w)//2
    y = (H - h)//2
    modal_surf = pygame.Surface((w, h))
    modal_surf.fill((210,215,220))
    pygame.draw.rect(modal_surf, (80,80,80), (0,0,w,h), 3)

    # build a textual list of player's deck
    try:
        limit = 20 if globals().get('DECK_MODE') == 'custom' else 24
    except Exception:
        limit = 24
    lines = [f"{i+1}. {c.name} (cost {c.cost})" for i,c in enumerate(game.player.deck.cards[:limit])]

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                return

        # dim background
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))
        screen.blit(modal_surf, (x,y))
        # draw list
        ty = y + 18
        for ln in lines:
            txt = SMALL.render(ln, True, (30,30,30))
            screen.blit(txt, (x+16, ty))
            ty += 24
            if ty > y + h - 40:
                break

        hint = TINY.render("クリック/タッチで閉じる", True, (80,80,80))
        screen.blit(hint, (x + (w - hint.get_width())//2, y + h - 28))


def show_custom_deck_selection(screen):
    """保存された作成デッキを一覧表示して選択する画面。
    saved_decks.json に保存されたデッキ（存在するもの）を表示し、
    選択されるとそのデッキでゲームを開始します。
    作成済みデッキがない場合は「作る」ボタンでデッキ作成画面へ移動できます。
    """
    global DECK_MODE
    clk = pygame.time.Clock()

    # saved_decks に格納されたデッキ群（9スロット）を読み込む
    saved = load_saved_decks()
    # 表示用の (slot_idx, name) リストを作る（None のスロットは除外）
    choices = []
    for i, d in enumerate(saved):
        if d:
            choices.append((i, d.get('name', f'デッキ{i+1}')))

    # Flush the click/touch that opened the modal so it doesn't immediately
    # register here and cause an accidental selection.
    try:
        pygame.event.get([pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN])
    except Exception:
        try:
            pygame.event.clear()
        except Exception:
            pass

    w = 640
    h = 360
    x = (W - w)//2
    y = (H - h)//2
    entry_h = 56
    pad = 20
    start_y = y + 64

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                if not (x <= mx <= x + w and y <= my <= y + h):
                    continue
                rel_y = my - start_y
                idx = rel_y // (entry_h + pad)
                if 0 <= idx < max(1, len(choices)):
                    # choices が空ならメッセージ領域のボタン（作る/戻る）を処理
                    if not choices:
                        # ボタン領域を計算
                        btn_w = 120
                        make_rect = pygame.Rect(x + 80, y + h - 90, btn_w, 50)
                        back_rect = pygame.Rect(x + w - 200, y + h - 90, btn_w, 50)
                        if make_rect.collidepoint(mx, my):
                            # デッキ作成画面（グリッド）へ移動
                            show_deck_modal(screen)
                            # 再読み込み
                            saved = load_saved_decks()
                            choices = [(i, d.get('name', f'デッキ{i+1}')) for i, d in enumerate(saved) if d]
                            continue
                        if back_rect.collidepoint(mx, my):
                            return
                        continue

                    # choices から選択されたスロットを特定
                    if idx < len(choices):
                        slot_idx = choices[idx][0]
                        deck = saved[slot_idx]
                        # deck のカード名リストを取得。保存形式がオブジェクト一覧の場合は名前列に変換する
                        names = None
                        if deck:
                            cards_field = deck.get('cards')
                            if isinstance(cards_field, list):
                                if cards_field and isinstance(cards_field[0], dict):
                                    names = [str(c.get('name')) for c in cards_field if c and 'name' in c]
                                else:
                                    names = [str(x) for x in cards_field]
                        DECK_MODE = 'custom'
                        # ゲーム作成ロジックは既存の関数を再利用（存在確認）
                        try:
                            logger.debug("selection modal starting battle, names=%s", names)
                            if names and 'build_game_from_card_names' in globals():
                                globals()['game'] = build_game_from_card_names(names)
                            else:
                                globals()['game'] = new_game_with_mode(DECK_MODE)
                                globals()['ai_player'] = build_ai_player(DECK_MODE)
                                try:
                                    _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                                except Exception:
                                    pass
                                try:
                                    gtmp = globals().get('game')
                                    logger.debug("global game set (mouse_start) id=%s deck_count=%s", id(gtmp), len(getattr(gtmp.player.deck,'cards',[])) if gtmp and hasattr(gtmp,'player') else 'NA')
                                except Exception:
                                    pass
                            try:
                                g = globals().get('game')
                                if g and hasattr(g, 'player') and hasattr(g.player, 'deck'):
                                    cards = getattr(g.player.deck, 'cards', None)
                                    if cards is not None:
                                        logger.debug("created game deck count=%d; first_cards=%s", len(cards), [c.name for c in cards[:8]])
                            except Exception as _e:
                                logger.debug("error inspecting created game: %s", _e)
                        except Exception as e:
                            logger.debug("exception when creating game from names: %s", e)
                            globals()['game'] = new_game_with_mode(DECK_MODE)
                            globals()['ai_player'] = build_ai_player(DECK_MODE)
                            try:
                                _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
                            except Exception:
                                pass
                        return

        # draw overlay and modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((210,215,220))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)
        title = FONT.render("作成デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        ty = 0
        if not choices:
            # 作成済みデッキがない場合の案内表示
            info = SMALL.render("作成済みのデッキがありません。デッキ作成で新しいデッキを作成してください。", True, (60,60,60))
            surf.blit(info, (20, 80))
            # 作る / 戻る ボタン
            make_rect = pygame.Rect(80, h - 90, 120, 50)
            back_rect = pygame.Rect(w - 200, h - 90, 120, 50)
            pygame.draw.rect(surf, (200, 240, 200), make_rect)
            pygame.draw.rect(surf, (80, 120, 80), make_rect, 3)
            pygame.draw.rect(surf, (240, 200, 200), back_rect)
            pygame.draw.rect(surf, (120, 80, 80), back_rect, 3)
            surf.blit(SMALL.render("作る", True, (30,30,30)), (make_rect.x + 36, make_rect.y + 14))
            surf.blit(SMALL.render("戻る", True, (30,30,30)), (back_rect.x + 36, back_rect.y + 14))
        else:
            for i, (slot_idx, name) in enumerate(choices):
                ex = pygame.Rect(pad, start_y - y + ty, w - pad*2, entry_h)
                pygame.draw.rect(surf, (220,220,220), ex)
                pygame.draw.rect(surf, (70,70,70), ex, 2)
                ntxt = SMALL.render(name, True, (30,30,30))
                surf.blit(ntxt, (ex.x + 12, ex.y + (entry_h - ntxt.get_height())//2))
                # 枚数表示
                deck = saved[slot_idx]
                cnt_txt = ""
                if deck and 'cards' in deck:
                    cnt_txt = f"{len(deck['cards'])} 枚"
                if cnt_txt:
                    ctxt = SMALL.render(cnt_txt, True, (80,80,80))
                    surf.blit(ctxt, (ex.right - ctxt.get_width() - 12, ex.y + (entry_h - ctxt.get_height())//2))
                ty += entry_h + pad

        screen.blit(surf, (x,y))
        pygame.display.flip()
        clk.tick(30)


def show_deck_action_modal(screen, deck, slot_idx):
    """小さな選択モーダルを表示して 'confirm'|'view'|'edit'|None を返す。"""
    # DEBUG: 受け取ったデッキ情報をログ出力
    try:
        if deck:
            cards = deck.get('cards', [])
            card_names = [c.get('name') if isinstance(c, dict) else str(c) for c in cards]
            logger.debug("show_deck_action_modal - slot=%d, deck_name=%s, card_count=%d, cards=%s", slot_idx, deck.get('name', 'Unknown'), len(cards), card_names[:5])
        else:
            logger.debug("show_deck_action_modal - slot=%d, deck=None", slot_idx)
    except Exception as e:
        logger.debug("Error logging deck info in action modal: %s", e)
    
    clk = pygame.time.Clock()
    w, h = 420, 200
    x = (W - w) // 2
    y = (H - h) // 2
    # Use Japanese-capable fonts to avoid tofu (□) when rendering deck names
    title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28)
    btn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 22)
    deck_name = deck.get('name', f'デッキ{slot_idx+1}')

    # snapshot background to keep previous screen visible under overlay
    try:
        _bg_frame = screen.copy()
    except Exception:
        _bg_frame = None

    # build short preview lines for the deck (first few card names)
    preview_lines = []
    for c in deck.get('cards', [])[:8]:
        if isinstance(c, dict):
            preview_lines.append(str(c.get('name', '不明')))
        else:
            preview_lines.append(str(c))

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return None
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # outside click closes
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return None

                # close (×) button
                close_rect = pygame.Rect(x + w - 34, y + 8, 26, 26)
                if close_rect.collidepoint(mx, my):
                    return None

                # buttons: left=edit, mid=view, right=delete
                btn_w = 110
                gap = 20
                bx = x + (w - (btn_w*3 + gap*2)) // 2
                by = y + h - 70
                edit_rect = pygame.Rect(bx, by, btn_w, 40)
                view_rect = pygame.Rect(bx + btn_w + gap, by, btn_w, 40)
                delete_rect = pygame.Rect(bx + (btn_w + gap)*2, by, btn_w, 40)

                if edit_rect.collidepoint(mx, my):
                    # open deck editor and save if edited
                    try:
                        decks = load_saved_decks()
                    except Exception:
                        decks = None
                    if decks is not None:
                        edited = show_deck_editor(screen, decks[slot_idx], slot_idx)
                        if edited:
                            decks[slot_idx] = edited
                            save_decks_to_file(decks)
                    return None

                if view_rect.collidepoint(mx, my):
                    # 単にデッキ詳細を表示するだけとし、バトル用の事前選択は保存しない
                    try:
                        show_deck_contents_overlay(screen, deck)
                    finally:
                        pass
                    return None

                if delete_rect.collidepoint(mx, my):
                    # confirmation loop
                    while True:
                        # draw confirm dialog
                        confirm_w, confirm_h = 420, 160
                        cx = x + (w - confirm_w)//2
                        cy = y + (h - confirm_h)//2
                        if _bg_frame is not None:
                            try:
                                screen.blit(_bg_frame, (0,0))
                            except Exception:
                                pass
                        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
                        # darken fully so the background deck list is not visible
                        overlay.fill((0,0,0,190))
                        screen.blit(overlay, (0,0))

                        # redraw modal box under confirm
                        box = pygame.Surface((w, h))
                        box.fill((210,215,220))
                        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
                        title = title_font.render(deck_name, True, (30,30,30))
                        box.blit(title, (20, 18))
                        info = SMALL.render("このデッキをどうしますか？", True, (60,60,60))
                        box.blit(info, (20,56))

                        # プレビューはこの画面では表示しない（要望により削除）

                        # buttons under modal — ensure they fit inside the box and center text
                        btn_h = 40
                        padding = 20
                        gap2 = 20
                        max_btn_w = (w - padding*2 - gap2*2) // 3
                        btn_w2 = min(140, max_btn_w)
                        bx2 = (w - (btn_w2*3 + gap2*2)) // 2
                        by2 = h - padding - btn_h
                        edit_rect_local = pygame.Rect(bx2, by2, btn_w2, btn_h)
                        view_rect_local = pygame.Rect(bx2 + btn_w2 + gap2, by2, btn_w2, btn_h)
                        delete_rect_local = pygame.Rect(bx2 + (btn_w2 + gap2)*2, by2, btn_w2, btn_h)
                        pygame.draw.rect(box, (220,220,255), edit_rect_local)
                        pygame.draw.rect(box, (200,240,200), view_rect_local)
                        pygame.draw.rect(box, (255,200,200), delete_rect_local)
                        pygame.draw.rect(box, (80,80,80), edit_rect_local, 2)
                        pygame.draw.rect(box, (80,80,80), view_rect_local, 2)
                        pygame.draw.rect(box, (80,80,80), delete_rect_local, 2)
                        # center button labels
                        et = btn_font.render("デッキ編集", True, (30,30,30))
                        vt = btn_font.render("デッキ詳細", True, (30,30,30))
                        dt = btn_font.render("デッキ削除", True, (30,30,30))
                        box.blit(et, (edit_rect_local.x + (btn_w2 - et.get_width())//2, edit_rect_local.y + (btn_h - et.get_height())//2))
                        box.blit(vt, (view_rect_local.x + (btn_w2 - vt.get_width())//2, view_rect_local.y + (btn_h - vt.get_height())//2))
                        box.blit(dt, (delete_rect_local.x + (btn_w2 - dt.get_width())//2, delete_rect_local.y + (btn_h - dt.get_height())//2))

                        # draw confirm box
                        confirm_surf = pygame.Surface((confirm_w, confirm_h))
                        confirm_surf.fill((210,215,220))
                        pygame.draw.rect(confirm_surf, (80,80,80), (0,0,confirm_w,confirm_h), 3)
                        q_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
                        qtxt = q_font.render("本当にこのデッキを削除しますか？", True, (30,30,30))
                        confirm_surf.blit(qtxt, ((confirm_w - qtxt.get_width())//2, 20))
                        yes_rect = pygame.Rect(60, confirm_h - 64, 120, 44)
                        no_rect = pygame.Rect(confirm_w - 180, confirm_h - 64, 120, 44)
                        pygame.draw.rect(confirm_surf, (200,255,200), yes_rect)
                        pygame.draw.rect(confirm_surf, (255,200,200), no_rect)
                        pygame.draw.rect(confirm_surf, (80,80,80), yes_rect, 2)
                        pygame.draw.rect(confirm_surf, (80,80,80), no_rect, 2)
                        confirm_surf.blit(q_font.render("はい (Y)", True, (30,30,30)), (yes_rect.x + 16, yes_rect.y + 10))
                        confirm_surf.blit(q_font.render("いいえ (N)", True, (30,30,30)), (no_rect.x + 16, no_rect.y + 10))

                        screen.blit(box, (x,y))
                        screen.blit(confirm_surf, (cx, cy))
                        pygame.display.flip()

                        # wait for confirm events
                        done = False
                        for cev in pygame.event.get():
                            if cev.type == pygame.QUIT:
                                pygame.quit(); sys.exit(0)
                            if cev.type == pygame.KEYDOWN:
                                if cev.key == pygame.K_y:
                                    try:
                                        decks = load_saved_decks()
                                        decks[slot_idx] = None
                                        save_decks_to_file(decks)
                                    except Exception:
                                        pass
                                    return None
                                if cev.key == pygame.K_n or cev.key == pygame.K_ESCAPE:
                                    done = True
                                    break
                            if cev.type == pygame.MOUSEBUTTONDOWN and cev.button == 1:
                                mx2, my2 = cev.pos
                                if cx <= mx2 <= cx + confirm_w and cy <= my2 <= cy + confirm_h:
                                    rx = mx2 - cx
                                    ry = my2 - cy
                                    if yes_rect.collidepoint(rx, ry):
                                        try:
                                            decks = load_saved_decks()
                                            decks[slot_idx] = None
                                            save_decks_to_file(decks)
                                        except Exception:
                                            pass
                                        return None
                                    if no_rect.collidepoint(rx, ry):
                                        done = True
                                        break
                        if done:
                            break
                    # end confirmation loop

        # 描画
        if _bg_frame is not None:
            try:
                screen.blit(_bg_frame, (0,0))
            except Exception:
                pass
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0, 0))
        box = pygame.Surface((w, h))
        box.fill((210, 215, 220))
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render(deck_name, True, (30,30,30))
        box.blit(title, (20, 18))
        info = SMALL.render("このデッキをどうしますか？", True, (60,60,60))
        box.blit(info, (20, 56))

        # close icon
        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        box.blit(btn_font.render("×", True, (60,60,60)), (w-30, 6))

        # プレビューはこの画面では表示しない（要望により削除）

        # ボタン: 左=デッキ編集, 中=デッキ詳細, 右=デッキ削除（ボタンが箱からはみ出さないように調整）
        btn_h = 40
        padding = 20
        gap = 20
        max_btn_w = (w - padding*2 - gap*2) // 3
        btn_w = min(140, max_btn_w)
        bx = (w - (btn_w*3 + gap*2)) // 2
        by = h - padding - btn_h
        edit_rect_local = pygame.Rect(bx, by, btn_w, btn_h)
        view_rect_local = pygame.Rect(bx + btn_w + gap, by, btn_w, btn_h)
        delete_rect_local = pygame.Rect(bx + (btn_w + gap)*2, by, btn_w, btn_h)
        pygame.draw.rect(box, (220, 220, 255), edit_rect_local)
        pygame.draw.rect(box, (200, 240, 200), view_rect_local)
        pygame.draw.rect(box, (255, 200, 200), delete_rect_local)
        pygame.draw.rect(box, (80,80,80), edit_rect_local, 2)
        pygame.draw.rect(box, (80,80,80), view_rect_local, 2)
        pygame.draw.rect(box, (80,80,80), delete_rect_local, 2)
        # center labels
        et = btn_font.render("デッキ編集", True, (30,30,30))
        vt = btn_font.render("デッキ詳細", True, (30,30,30))
        dt = btn_font.render("デッキ削除", True, (30,30,30))
        box.blit(et, (edit_rect_local.x + (btn_w - et.get_width())//2, edit_rect_local.y + (btn_h - et.get_height())//2))
        box.blit(vt, (view_rect_local.x + (btn_w - vt.get_width())//2, view_rect_local.y + (btn_h - vt.get_height())//2))
        box.blit(dt, (delete_rect_local.x + (btn_w - dt.get_width())//2, delete_rect_local.y + (btn_h - dt.get_height())//2))

        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


def show_card_detail(screen, card_name, get_card_image):
    """カード詳細表示（拡大表示）"""
    clk = pygame.time.Clock()
    
    # 拡大カードの基準サイズ（スケールを掛けて表示）
    base_detail_w = 360
    base_detail_h = 480
    # グローバルの拡大率を使ってモーダル中もスクロールで拡大縮小できるようにする
    global enlarged_card_scale, enlarged_card_mouse_y
    try:
        enlarged_card_scale = 1.0
    except Exception:
        enlarged_card_scale = 1.0
    
    # 元の画面を保存（背景が徐々に濃くなるのを防ぐ）
    base_screen = screen.copy()
    
    # 半透明オーバーレイを一度だけ作成
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((20, 20, 20, 180))
    
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                return
            if ev.type == pygame.MOUSEWHEEL:
                # モーダル表示中のホイールで拡大縮小
                try:
                    enlarged_card_scale = max(0.5, min(2.5, enlarged_card_scale + (ev.y * 0.1)))
                    enlarged_card_mouse_y = None
                except Exception:
                    pass
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
        
        # 元の画面から描画開始
        screen.blit(base_screen, (0, 0))
        screen.blit(overlay, (0, 0))
        
        # カード画像を中央に表示（グローバル拡大率を反映）
        detail_w = int(base_detail_w * enlarged_card_scale)
        detail_h = int(base_detail_h * enlarged_card_scale)
        cx = (W - detail_w) // 2
        cy = (H - detail_h) // 2

        if get_card_image:
            try:
                card_img = get_card_image(card_name, size=(detail_w, detail_h))
                if card_img:
                    screen.blit(card_img, (cx, cy))
                else:
                    raise Exception("card_img is None")
            except Exception:
                # フォールバック表示
                fallback = pygame.Surface((detail_w, detail_h))
                fallback.fill((255, 255, 255))
                pygame.draw.rect(fallback, (100, 100, 100), (0, 0, detail_w, detail_h), 3)
                try:
                    name_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 24, bold=True)
                    name_surf = name_font.render(card_name, True, (30, 30, 30))
                except Exception:
                    name_font = pygame.font.SysFont(None, 24)
                    name_surf = name_font.render(card_name, True, (30, 30, 30))
                name_rect = name_surf.get_rect(center=(detail_w // 2, detail_h // 2))
                fallback.blit(name_surf, name_rect)
                screen.blit(fallback, (cx, cy))
        
        # ヒント表示
        try:
            hint_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
            hint = hint_font.render("クリックで閉じる", True, (255, 255, 255))
        except Exception:
            hint_font = pygame.font.SysFont(None, 18)
            hint = hint_font.render("Click to close", True, (255, 255, 255))
        hint_rect = hint.get_rect(center=(W // 2, cy + detail_h + 30))
        screen.blit(hint, hint_rect)
        
        pygame.display.flip()
        clk.tick(30)


def show_deck_contents_overlay(screen, deck):
    """デッキ内容オーバーレイ表示（画像ベース、重複カードは×n表示）"""
    # カード画像ローダーをインポート
    global W, H
    get_card_image = None
    try:
        from assets.image_loader import get_card_image
    except Exception:
        get_card_image = None
    
    # DEBUG: 受け取ったデッキ情報をログ出力
    try:
        deck_name = deck.get('name', 'Unknown')
        cards = deck.get('cards', [])
        card_names = [c.get('name') if isinstance(c, dict) else str(c) for c in cards]
        logger.debug("show_deck_contents_overlay - deck_name=%s, card_count=%d, cards=%s", deck_name, len(cards), card_names[:5])
    except Exception as e:
        logger.debug("Error logging deck info: %s", e)
    
    clk = pygame.time.Clock()
    w = min(1100, W - 60)  # 1000 → 1100に拡大
    h = min(850, H - 60)   # 720 → 850に拡大
    x = (W - w)//2
    y = (H - h)//2
    
    try:
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 32, bold=True)  # 28 → 32に拡大
        count_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)  # 18 → 20に拡大
    except Exception:
        title_font = pygame.font.SysFont(None, 32)
        count_font = pygame.font.SysFont(None, 20)

    # カードを集計（重複をカウント）
    card_counts = {}
    for c in deck.get('cards', []):
        if isinstance(c, dict):
            name = str(c.get('name', '不明'))
        else:
            name = str(c)
        card_counts[name] = card_counts.get(name, 0) + 1
    
    unique_cards = list(card_counts.keys())
    
    # カードの位置情報を保存（クリック判定用）
    card_rects = {}
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if not (x <= mx <= x + w and y <= my <= y + h):
                    return
                lx = mx - x
                ly = my - y
                if (w - 34) <= lx <= (w - 8) and 8 <= ly <= 34:
                    return
                
                # カードクリック判定
                clicked_card = False
                for card_name, rect in card_rects.items():
                    if rect.collidepoint(lx, ly):
                        # カード詳細表示を呼び出し
                        show_card_detail(screen, card_name, get_card_image)
                        clicked_card = True
                        break
                if clicked_card:
                    # 詳細表示から戻ったら、次のフレームでデッキ表示を再描画
                    continue
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return

        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((15, 15, 15, 50) if not get_ui_effects_enabled() else (0, 0, 0, 180))
        screen.blit(overlay, (0,0))

        box = pygame.Surface((w, h))
        box.fill((240,235,230))
        pygame.draw.rect(box, (80,80,80), (0,0,w,h), 3)
        title = title_font.render(deck.get('name', 'デッキ'), True, (30,30,30))
        box.blit(title, (20, 12))

        pygame.draw.rect(box, (200,200,200), (w-34, 8, 26, 26))
        pygame.draw.rect(box, (80,80,80), (w-34, 8, 26, 26), 1)
        try:
            box.blit(SMALL.render("×", True, (60,60,60)), (w-30, 6))
        except Exception:
            pass

        # カード画像を表示（グリッド形式）
        card_w = 140  # 120 → 140に拡大
        card_h = 190  # 160 → 190に拡大
        margin = 20   # 15 → 20に拡大
        
        # カード枚数に応じて行数を決定
        num_cards = len(unique_cards)
        if num_cards <= 8:
            # 少ない場合は2行
            target_rows = 2
        else:
            # 多い場合は3行
            target_rows = 3
        
        # 目標行数に基づいて列数を計算
        cols = (num_cards + target_rows - 1) // target_rows
        
        # 実際の行数を計算
        actual_rows = (num_cards + cols - 1) // cols
        
        # グリッド全体のサイズを計算
        grid_width = cols * card_w + (cols - 1) * margin
        grid_height = actual_rows * card_h + (actual_rows - 1) * (margin + 10)
        
        # センタリング（水平・垂直）
        start_x = (w - grid_width) // 2
        start_y = (h - grid_height) // 2 + 20  # タイトル分少し下げる
        
        # カード位置情報をクリア
        card_rects.clear()
        
        for idx, card_name in enumerate(unique_cards):
            col = idx % cols
            row = idx // cols
            cx = start_x + col * (card_w + margin)
            cy = start_y + row * (card_h + margin + 10)
            
            # カード位置を記録
            card_rects[card_name] = pygame.Rect(cx, cy, card_w, card_h)
            
            # カード画像を描画
            if get_card_image:
                try:
                    card_img = get_card_image(card_name, size=(card_w, card_h))
                    if card_img is None:
                        raise Exception("card_img is None")
                    box.blit(card_img, (cx, cy))
                except Exception:
                    # フォールバック: テキスト表示
                    pygame.draw.rect(box, (255, 255, 255), (cx, cy, card_w, card_h))
                    pygame.draw.rect(box, (100, 100, 100), (cx, cy, card_w, card_h), 2)
                    name_lines = []
                    if len(card_name) > 8:
                        name_lines.append(card_name[:8])
                        name_lines.append(card_name[8:])
                    else:
                        name_lines.append(card_name)
                    name_y = cy + 10
                    for line in name_lines:
                        name_surf = TINY.render(line, True, (30, 30, 30))
                        name_rect = name_surf.get_rect(center=(cx + card_w // 2, name_y))
                        box.blit(name_surf, name_rect)
                        name_y += 16
            else:
                # get_card_imageが使えない場合
                pygame.draw.rect(box, (255, 255, 255), (cx, cy, card_w, card_h))
                pygame.draw.rect(box, (100, 100, 100), (cx, cy, card_w, card_h), 2)
                name_surf = TINY.render(card_name, True, (30, 30, 30))
                name_rect = name_surf.get_rect(center=(cx + card_w // 2, cy + card_h // 2))
                box.blit(name_surf, name_rect)
            
            # 重複数を右下に表示（2枚以上の場合）
            count = card_counts[card_name]
            if count > 1:
                count_bg = pygame.Surface((40, 28), pygame.SRCALPHA)
                count_bg.fill((0, 0, 0, 200))
                box.blit(count_bg, (cx + card_w - 43, cy + card_h - 30))
                
                # より大きく見やすいフォントで表示
                try:
                    large_count_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 22, bold=True)
                    count_text = large_count_font.render(f"×{count}", True, (255, 255, 255))
                except Exception:
                    count_text = count_font.render(f"×{count}", True, (255, 255, 255))
                box.blit(count_text, (cx + card_w - 40, cy + card_h - 28))

        hint = TINY.render("外側をクリックすると閉じる", True, (80,80,80))
        box.blit(hint, (w - hint.get_width() - 12, h - 28))
        screen.blit(box, (x, y))
        pygame.display.flip()
        clk.tick(30)


# Note: the detailed deck editor implementation lives earlier in this file
# (the function that accepts (screen, existing_deck, slot_idx)).
# This placeholder definition was removed to avoid shadowing the real editor.


def show_settings_screen(screen):
    """Simple settings screen to toggle BGM ON/OFF and adjust volume.

    This is a modal-like loop that returns when the user presses "戻る".
    It updates module-level `bgm_enabled` and `bgm_volume` globals and
    applies them to pygame.mixer.music where appropriate.
    """
    global bgm_enabled, bgm_volume
    clk = pygame.time.Clock()
    dragging = False
    drag_offset = 0

    # layout (enlarged to give more space for options)
    w = 760
    h = 420
    x = (W - w) // 2
    y = (H - h) // 2

    # Capture the current animation time scale when opening the modal.
    try:
        prev_scale = animation_mod.get_anim_time_scale() if animation_mod and hasattr(animation_mod, 'get_anim_time_scale') else 1.0
    except Exception:
        prev_scale = 1.0
    # Fast = half of the previously current scale, Slow = previous current scale
    fast_scale = max(0.01, float(prev_scale) / 2.0)
    slow_scale = float(prev_scale)

    # slider geometry
    slider_x = x + 40
    slider_y = y + 140
    slider_w = w - 80
    slider_h = 6

    # snapshot current screen to keep the background visible behind the modal
    try:
        settings_bg_frame = screen.copy()
    except Exception:
        settings_bg_frame = None

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    # finger: normalized coords -> screen coords
                    try:
                        sx, sy = screen.get_size()
                        mx = int(ev.x * sx)
                        my = int(ev.y * sy)
                    except Exception:
                        mx, my = 0, 0
                # back button
                back_rect = pygame.Rect(x + w - 120, y + h - 56, 100, 40)
                if back_rect.collidepoint(mx, my):
                    return
                # toggle BGM checkbox
                chk_rect = pygame.Rect(x + 40, y + 60, 24, 24)
                if chk_rect.collidepoint(mx, my):
                    bgm_enabled = not bgm_enabled
                    try:
                        # Reapply or stop BGM according to the current logical mode
                        if bgm_enabled:
                            try:
                                # reapply the currently selected mode (title/game) so proper file is loaded
                                set_bgm_mode(current_bgm_mode)
                            except Exception:
                                # fallback: just set volume
                                try:
                                    pygame.mixer.music.set_volume(max(0.0, min(1.0, bgm_volume)))
                                except Exception:
                                    pass
                        else:
                            try:
                                set_bgm_mode(None)
                            except Exception:
                                try:
                                    pygame.mixer.music.set_volume(0.0)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                # slider hit check
                slid_rect = pygame.Rect(slider_x, slider_y - 8, slider_w, 24)
                if slid_rect.collidepoint(mx, my):
                    dragging = True
                    # compute proportion
                    rel = (mx - slider_x) / float(max(1, slider_w))
                    bgm_volume = max(0.0, min(1.0, rel))
                    try:
                        if pygame.mixer.get_init() and bgm_enabled:
                            pygame.mixer.music.set_volume(bgm_volume)
                    except Exception:
                        pass
                # Animation settings button click (placed next to Back button)
                try:
                    anim_btn_rect = pygame.Rect(x + w - 352, y + h - 56, 220, 40)
                    if anim_btn_rect.collidepoint(mx, my):
                        try:
                            show_animation_settings_screen(screen)
                        except Exception:
                            pass
                        continue
                except Exception:
                    pass

                # Gimmick activation option click areas (relative to modal)
                gimm_x = x + 40
                gimm_y = y + 220
                opt_w = w - 80
                opt_h = 28
                # top-level options
                top_num_rect = pygame.Rect(gimm_x, gimm_y, opt_w, opt_h)
                top_click_rect = pygame.Rect(gimm_x, gimm_y + opt_h + 8, opt_w, opt_h)
                # nested options (shown only when top-click is selected)
                nested_x = gimm_x + 20
                nested_y = top_click_rect.y + opt_h + 8
                nested_rect_1 = pygame.Rect(nested_x, nested_y, opt_w - 20, opt_h)
                nested_rect_2 = pygame.Rect(nested_x, nested_y + (opt_h + 8), opt_w - 20, opt_h)

                if top_num_rect.collidepoint(mx, my):
                    globals()['gimmick_activation_mode'] = 'number_key'
                    try:
                        globals()['notice_msg'] = "発動方法: 数字キー"
                        globals()['notice_until'] = _ct_time.time() + 1.5
                    except Exception:
                        pass
                elif top_click_rect.collidepoint(mx, my):
                    # Select the click-top mode but keep the chosen submode
                    # If a submode hasn't been chosen yet, default to click_enlarged
                    sub = globals().get('gimmick_click_submode', 'click_enlarged')
                    globals()['gimmick_click_submode'] = sub
                    globals()['gimmick_activation_mode'] = sub
                    try:
                        globals()['notice_msg'] = "発動方法: カードをクリックして発動"
                        globals()['notice_until'] = _ct_time.time() + 1.5
                    except Exception:
                        pass
                else:
                    # handle nested option clicks when the click-top area is shown
                    if nested_rect_1.collidepoint(mx, my):
                        globals()['gimmick_click_submode'] = 'click_enlarged'
                        globals()['gimmick_activation_mode'] = 'click_enlarged'
                        try:
                            globals()['notice_msg'] = "発動方法: 拡大クリック"
                            globals()['notice_until'] = _ct_time.time() + 1.5
                        except Exception:
                            pass
                    elif nested_rect_2.collidepoint(mx, my):
                        globals()['gimmick_click_submode'] = 'double_click'
                        globals()['gimmick_activation_mode'] = 'double_click'
                        try:
                            globals()['notice_msg'] = "発動方法: ダブルクリック"
                            globals()['notice_until'] = _ct_time.time() + 1.5
                        except Exception:
                            pass
                        # animation settings button
                    # redundant old anim btn handler removed; button handled above
                    pass
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                dragging = False
            elif ev.type == pygame.MOUSEMOTION and dragging:
                mx, my = ev.pos
                rel = (mx - slider_x) / float(max(1, slider_w))
                bgm_volume = max(0.0, min(1.0, rel))
                try:
                    if pygame.mixer.get_init() and bgm_enabled:
                        pygame.mixer.music.set_volume(bgm_volume)
                except Exception:
                    pass
                

        # draw modal
        if settings_bg_frame is not None:
            try:
                screen.blit(settings_bg_frame, (0, 0))
            except Exception:
                pass
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((210,215,220))
        pygame.draw.rect(surf, (70,70,70), (0,0,w,h), 3)

        title = FONT.render("設定", True, (30,30,30))
        surf.blit(title, (20, 12))

        # BGM enabled checkbox
        try:
            chk_rect = pygame.Rect(40, 60, 24, 24)
            pygame.draw.rect(surf, (230,230,230), chk_rect)
            pygame.draw.rect(surf, (80,80,80), chk_rect, 2)
            txt = SMALL.render("BGM を再生する", True, (30,30,30))
            surf.blit(txt, (80, 60))
            if bgm_enabled:
                # draw a tidy check mark that fits inside the checkbox
                try:
                    cx = chk_rect.x
                    cy = chk_rect.y
                    pts = [
                        (cx + 4, cy + 12),
                        (cx + 10, cy + 18),
                        (cx + 20, cy + 6),
                    ]
                    pygame.draw.lines(surf, (20,20,20), False, pts, 3)
                except Exception:
                    # fallback: small filled rect
                    pygame.draw.rect(surf, (20,20,20), (chk_rect.x+6, chk_rect.y+6, 12, 12))
        except Exception:
            pass

        # Volume slider
        try:
            # slider background
            sx = slider_x - x
            sy = slider_y - y
            pygame.draw.rect(surf, (200,200,200), (sx, sy - slider_h//2, slider_w, slider_h))
            # knob position
            kx = int(sx + bgm_volume * slider_w)
            ky = sy
            pygame.draw.circle(surf, (80,80,80), (kx, ky), 10)
            vol_txt = SMALL.render(f"音量: {int(bgm_volume*100)}%", True, (30,30,30))
            # move the volume text slightly upward for better spacing
            surf.blit(vol_txt, (40, sy + 8))
        except Exception:
            pass

        # Back button
        back_rect = pygame.Rect(w - 120, h - 56, 100, 40)
        pygame.draw.rect(surf, (220,220,220), back_rect)
        pygame.draw.rect(surf, (70,70,70), back_rect, 2)
        back_txt = SMALL.render("戻る", True, (30,30,30))
        surf.blit(back_txt, (back_rect.x + (back_rect.w - back_txt.get_width())//2, back_rect.y + (back_rect.h - back_txt.get_height())//2))

        # Animation settings button (placed next to Back button)
        try:
            anim_btn = pygame.Rect(w - 352, h - 56, 220, 40)
            pygame.draw.rect(surf, (220,240,255), anim_btn)
            pygame.draw.rect(surf, (70,90,140), anim_btn, 2)
            atxt = SMALL.render("アニメーション設定", True, (30,30,30))
            surf.blit(atxt, (anim_btn.x + (anim_btn.w - atxt.get_width())//2, anim_btn.y + (anim_btn.h - atxt.get_height())//2))
        except Exception:
            pass

        # Gimmick activation method description and options
        try:
            opt_title = SMALL.render("ギミック発動操作変更", True, (30,30,30))
            # place title a bit lower to avoid overlapping the volume label
            surf.blit(opt_title, (40, 180))
            gimm_x = 40
            gimm_y = 220
            opt_h = 28
            opt_w = w - 80

            # Top-level options: 1) 数字キーで発動  2) カードをクリックして発動
            # Draw top-level radios
            # Top 1: 数字キーで発動
            chk_x = gimm_x
            chk_y = gimm_y
            pygame.draw.circle(surf, (200,200,200), (chk_x+10, chk_y+opt_h//2), 10)
            if gimmick_activation_mode == 'number_key':
                pygame.draw.circle(surf, (80,80,80), (chk_x+10, chk_y+opt_h//2), 6)
            txt1 = SMALL.render("数字キーで発動", True, (30,30,30))
            surf.blit(txt1, (chk_x + 28, chk_y + (opt_h - txt1.get_height())//2))

            # Top 2: カードをクリックして発動
            chk_y2 = gimm_y + opt_h + 8
            pygame.draw.circle(surf, (200,200,200), (chk_x+10, chk_y2+opt_h//2), 10)
            # top-click is considered selected when effective mode is not number_key
            if gimmick_activation_mode != 'number_key':
                pygame.draw.circle(surf, (80,80,80), (chk_x+10, chk_y2+opt_h//2), 6)
            txt2 = SMALL.render("カードをクリックして発動", True, (30,30,30))
            surf.blit(txt2, (chk_x + 28, chk_y2 + (opt_h - txt2.get_height())//2))

            # If click-top is selected, draw nested options indented
            if gimmick_activation_mode != 'number_key':
                nested_x = gimm_x + 20
                nested_y = chk_y2 + opt_h + 8
                # nested 1: 拡大カードをクリックで発動
                pygame.draw.circle(surf, (200,200,200), (nested_x+10, nested_y+opt_h//2), 10)
                if globals().get('gimmick_click_submode', 'click_enlarged') == 'click_enlarged':
                    pygame.draw.circle(surf, (80,80,80), (nested_x+10, nested_y+opt_h//2), 6)
                ntxt1 = SMALL.render("拡大カードをクリックして発動", True, (30,30,30))
                surf.blit(ntxt1, (nested_x + 28, nested_y + (opt_h - ntxt1.get_height())//2))

                # nested 2: ダブルクリックで発動
                nested_y2 = nested_y + (opt_h + 8)
                pygame.draw.circle(surf, (200,200,200), (nested_x+10, nested_y2+opt_h//2), 10)
                if globals().get('gimmick_click_submode', 'click_enlarged') == 'double_click':
                    pygame.draw.circle(surf, (80,80,80), (nested_x+10, nested_y2+opt_h//2), 6)
                ntxt2 = SMALL.render("ダブルクリックで発動", True, (30,30,30))
                surf.blit(ntxt2, (nested_x + 28, nested_y2 + (opt_h - ntxt2.get_height())//2))
        except Exception:
            pass
        # クレジット表示（モーダル左下）
        try:
            credit_text = "フリーBGM・音楽素材:MusMus様"
            try:
                credit_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", max(14, SMALL.get_height()-2), bold=True)
            except Exception:
                credit_font = SMALL
            fill_color = (120, 120, 120)
            outline_color = (30, 30, 30)
            credit_surf = credit_font.render(credit_text, True, fill_color)
            outline = credit_font.render(credit_text, True, outline_color)
            # Place credit at the modal's top-right with a small inset
            cx = w - credit_surf.get_width() - 12
            cy = 12
            # draw outline slightly offset then main text
            surf.blit(outline, (cx + 1, cy + 1))
            surf.blit(credit_surf, (cx, cy))
        except Exception:
            pass

        screen.blit(surf, (x, y))
        pygame.display.flip()
        clk.tick(30)

def show_animation_settings_screen(screen):
    """Modal to toggle AI animation options:
    - 駒移動パルスON/OFF
    - 駒ゴーストON/OFF
    - 矢印ON/OFF
    """
    global ai_move_pulse_enabled, ai_move_ghost_enabled, ai_move_arrow_enabled
    global user_anim_scale
    global animation_mod, _animation_module
    clk = pygame.time.Clock()
    w = 600
    h = 400
    # determine current window size to avoid relying on globals
    try:
        W, H = screen.get_size()
    except Exception:
        try:
            W, H = get_window_size()
        except Exception:
            W, H = 1200, 800
    x = (W - w) // 2
    y = (H - h) // 2

    # Capture the current animation time scale when opening the modal.
    # Semantics: '遅い' = current scale, '早い' = half of current scale.
    try:
        # Prefer explicit user choice stored in this module if present
        # Load saved discrete choice if present (persisted between runs)
        if globals().get('user_anim_choice') is None:
            try:
                v = load_user_anim_choice()
                if v is not None:
                    globals()['user_anim_choice'] = v
            except Exception:
                pass

        if globals().get('user_anim_scale') is not None:
            prev_scale = float(globals().get('user_anim_scale'))
        else:
            # Try to read from canonical animation module (package or top-level)
            import importlib, sys
            mod = None
            try:
                mod = importlib.import_module('c.c.b.assets.animation')
            except Exception:
                try:
                    mod = importlib.import_module('assets.animation')
                except Exception:
                    mod = sys.modules.get('c.c.b.assets.animation') or sys.modules.get('assets.animation')
            if mod and hasattr(mod, 'get_anim_time_scale'):
                prev_scale = float(mod.get_anim_time_scale())
            elif animation_mod and hasattr(animation_mod, 'get_anim_time_scale'):
                prev_scale = float(animation_mod.get_anim_time_scale())
            else:
                prev_scale = 1.0
    except Exception:
        prev_scale = 1.0
    # debug: report the value used to compute fast/slow scales
    try:
        logger.debug(f"show_animation_settings_screen prev_scale={prev_scale} user_anim_scale={globals().get('user_anim_scale')}")
    except Exception:
        pass
    # Use deterministic canonical scales to avoid relative/accumulating
    # semantics that cause intermittent confusion when multiple modules
    # are imported under different names. 'fast' is 0.5x, 'slow' is 1.0x.
    try:
        fast_scale = 0.5
    except Exception:
        fast_scale = 0.5
    try:
        slow_scale = 1.0
    except Exception:
        slow_scale = 1.0

    # layout defaults used by both options and radios
    opt_x = 40
    opt_y = 48
    gap = 36

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                # back button
                back_rect = pygame.Rect(x + w - 120, y + h - 56, 100, 40)
                if back_rect.collidepoint(mx, my):
                    return
                # checkboxes
                cb_x = x + 40
                cb_y = y + 48
                cb_h = 36
                # pulse
                cb1 = pygame.Rect(cb_x, cb_y, 24, 24)
                if cb1.collidepoint(mx, my):
                    ai_move_pulse_enabled = not ai_move_pulse_enabled
                # ghost
                cb2 = pygame.Rect(cb_x, cb_y + cb_h, 24, 24)
                if cb2.collidepoint(mx, my):
                    ai_move_ghost_enabled = not ai_move_ghost_enabled
                # arrow
                cb3 = pygame.Rect(cb_x, cb_y + cb_h*2, 24, 24)
                if cb3.collidepoint(mx, my):
                    ai_move_arrow_enabled = not ai_move_arrow_enabled
                # animation speed radios (hit areas aligned to drawing coordinates)
                radio_x = x + 40  # matches draw radio_x
                # move radios one extra gap downward to create space for a label
                radio_y = y + 48 + cb_h*4 + 12
                fast_w = 110
                slow_w = 110
                r_h = 36
                # define two radio hit areas (早い, 遅い)
                fast_rect = pygame.Rect(radio_x, radio_y, fast_w, r_h)
                slow_rect = pygame.Rect(radio_x + 120, radio_y, slow_w, r_h)
                # debug: print mouse and rects so we can diagnose hit-test failures
                try:
                    logger.info(f"anim modal MOUSEBUTTONDOWN at {mx},{my} ; fast_rect={fast_rect} slow_rect={slow_rect}")
                except Exception:
                    logger.debug("anim modal MOUSEBUTTONDOWN at %d,%d ; fast_rect=%s slow_rect=%s", mx, my, fast_rect, slow_rect)

                if fast_rect.collidepoint(mx, my):
                    try:
                        logger.info("animation: fast radio clicked")
                        # Try multiple ways to set the global animation scale so
                        # we don't miss the actual module object used elsewhere.
                        success = False
                        try:
                            if animation_mod and hasattr(animation_mod, 'set_anim_time_scale'):
                                animation_mod.set_anim_time_scale(fast_scale)
                                # persist canonical choice and scale
                                globals()['user_anim_scale'] = float(fast_scale)
                                globals()['user_anim_choice'] = 'fast'
                                try:
                                    save_user_anim_scale(float(fast_scale))
                                    save_user_anim_choice('fast')
                                except Exception:
                                    pass
                                logger.debug(f"set_anim_time_scale -> {fast_scale} (via animation_mod)")
                                success = True
                        except Exception:
                            success = False
                        try:
                            if not success and globals().get('_animation_module') and hasattr(globals().get('_animation_module'), 'set_anim_time_scale'):
                                globals().get('_animation_module').set_anim_time_scale(fast_scale)
                                globals()['user_anim_scale'] = float(fast_scale)
                                globals()['user_anim_choice'] = 'fast'
                                try:
                                    save_user_anim_scale(float(fast_scale))
                                    save_user_anim_choice('fast')
                                except Exception:
                                    pass
                                logger.debug(f"set_anim_time_scale -> {fast_scale} (via _animation_module)")
                                # point local refs to that module
                                try:
                                    animation_mod = globals().get('_animation_module')
                                    _animation_module = globals().get('_animation_module')
                                except Exception:
                                    pass
                                success = True
                        except Exception:
                            pass
                        if not success:
                            try:
                                import importlib, sys
                                mod = None
                                try:
                                    mod = importlib.import_module('c.c.b.assets.animation')
                                except Exception:
                                    try:
                                        mod = importlib.import_module('assets.animation')
                                    except Exception:
                                        mod = sys.modules.get('c.c.b.assets.animation') or sys.modules.get('assets.animation')
                                if mod:
                                    try:
                                        if hasattr(mod, 'set_anim_time_scale'):
                                            mod.set_anim_time_scale(fast_scale)
                                        else:
                                            setattr(mod, 'ANIM_TIME_SCALE', float(fast_scale))
                                        globals()['user_anim_scale'] = float(fast_scale)
                                        globals()['user_anim_choice'] = 'fast'
                                        try:
                                            save_user_anim_scale(float(fast_scale))
                                            save_user_anim_choice('fast')
                                        except Exception:
                                            pass
                                        logger.debug(f"set_anim_time_scale -> {fast_scale} (via import module)")
                                    except Exception:
                                        pass
                                    try:
                                        animation_mod = mod
                                        _animation_module = mod
                                    except Exception:
                                        pass
                                    success = True
                            except Exception:
                                pass
                        # Clear image_loader GIF cache so new durations are used
                        try:
                            import importlib, sys
                            il = None
                            try:
                                il = importlib.import_module('c.c.b.assets.image_loader')
                            except Exception:
                                try:
                                    il = importlib.import_module('assets.image_loader')
                                except Exception:
                                    il = sys.modules.get('c.c.b.assets.image_loader') or sys.modules.get('assets.image_loader')
                                if il and hasattr(il, '_gif_animation_cache'):
                                    try:
                                        il._gif_animation_cache.clear()
                                        logger.debug('image_loader: gif cache cleared')
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        # Also attempt to find any loaded modules that correspond to
                        # the animation implementation file and set their scale/attr,
                        # plus clear any image_loader modules' gif caches. This handles
                        # environments where the same file was imported under multiple
                        # module names (script vs package imports).
                        try:
                            import sys
                            for name, mod in list(sys.modules.items()):
                                try:
                                    mf = getattr(mod, '__file__', '') or ''
                                    if mf and mf.replace('/', os.sep).endswith(os.path.join('assets', 'animation.py')):
                                        try:
                                            if hasattr(mod, 'set_anim_time_scale'):
                                                mod.set_anim_time_scale(fast_scale)
                                                logger.debug(f"set_anim_time_scale -> {fast_scale} (via sys.modules {name})")
                                            else:
                                                setattr(mod, 'ANIM_TIME_SCALE', float(fast_scale))
                                                logger.debug(f"ANIM_TIME_SCALE set -> {fast_scale} (via sys.modules {name})")
                                        except Exception:
                                            pass
                                    if mf and mf.replace('/', os.sep).endswith(os.path.join('assets', 'image_loader.py')):
                                        if hasattr(mod, '_gif_animation_cache'):
                                            try:
                                                mod._gif_animation_cache.clear()
                                                logger.debug(f"image_loader: gif cache cleared (via sys.modules {name})")
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception:
                        pass
                elif slow_rect.collidepoint(mx, my):
                    try:
                        logger.info("animation: slow radio clicked")
                        # Same robust path for slow_scale
                        success = False
                        try:
                            if animation_mod and hasattr(animation_mod, 'set_anim_time_scale'):
                                animation_mod.set_anim_time_scale(slow_scale)
                                globals()['user_anim_scale'] = float(slow_scale)
                                globals()['user_anim_choice'] = 'slow'
                                try:
                                    save_user_anim_scale(float(slow_scale))
                                    save_user_anim_choice('slow')
                                except Exception:
                                    pass
                                logger.debug(f"set_anim_time_scale -> {slow_scale} (via animation_mod)")
                                success = True
                        except Exception:
                            success = False
                        try:
                            if not success and globals().get('_animation_module') and hasattr(globals().get('_animation_module'), 'set_anim_time_scale'):
                                globals().get('_animation_module').set_anim_time_scale(slow_scale)
                                globals()['user_anim_scale'] = float(slow_scale)
                                globals()['user_anim_choice'] = 'slow'
                                try:
                                    save_user_anim_scale(float(slow_scale))
                                    save_user_anim_choice('slow')
                                except Exception:
                                    pass
                                logger.debug(f"set_anim_time_scale -> {slow_scale} (via _animation_module)")
                                try:
                                    animation_mod = globals().get('_animation_module')
                                    _animation_module = globals().get('_animation_module')
                                except Exception:
                                    pass
                                success = True
                        except Exception:
                            pass
                        if not success:
                            try:
                                import importlib, sys
                                mod = None
                                try:
                                    mod = importlib.import_module('c.c.b.assets.animation')
                                except Exception:
                                    try:
                                        mod = importlib.import_module('assets.animation')
                                    except Exception:
                                        mod = sys.modules.get('c.c.b.assets.animation') or sys.modules.get('assets.animation')
                                if mod:
                                    if hasattr(mod, 'set_anim_time_scale'):
                                        mod.set_anim_time_scale(slow_scale)
                                        globals()['user_anim_scale'] = float(slow_scale)
                                        try:
                                            globals()['user_anim_choice'] = 'slow'
                                            save_user_anim_choice('slow')
                                        except Exception:
                                            pass
                                        try:
                                            save_user_anim_scale(float(slow_scale))
                                        except Exception:
                                            pass
                                        logger.debug("set_anim_time_scale -> %s (via import)", slow_scale)
                                    else:
                                        try:
                                            setattr(mod, 'ANIM_TIME_SCALE', float(slow_scale))
                                            globals()['user_anim_scale'] = float(slow_scale)
                                            try:
                                                globals()['user_anim_choice'] = 'slow'
                                                save_user_anim_choice('slow')
                                            except Exception:
                                                pass
                                            try:
                                                save_user_anim_scale(float(slow_scale))
                                            except Exception:
                                                pass
                                            logger.debug("ANIM_TIME_SCALE set -> %s (via import setattr)", slow_scale)
                                        except Exception:
                                            pass
                                    try:
                                        animation_mod = mod
                                        _animation_module = mod
                                    except Exception:
                                        pass
                                    success = True
                            except Exception:
                                pass
                        try:
                            import importlib, sys
                            il = None
                            try:
                                il = importlib.import_module('c.c.b.assets.image_loader')
                            except Exception:
                                try:
                                    il = importlib.import_module('assets.image_loader')
                                except Exception:
                                    il = sys.modules.get('c.c.b.assets.image_loader') or sys.modules.get('assets.image_loader')
                            if il and hasattr(il, '_gif_animation_cache'):
                                try:
                                    il._gif_animation_cache.clear()
                                    logger.debug('image_loader: gif cache cleared')
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # Also sweep sys.modules as a fallback (see fast branch)
                        try:
                            import sys
                            for name, mod in list(sys.modules.items()):
                                try:
                                    mf = getattr(mod, '__file__', '') or ''
                                    if mf and mf.replace('/', os.sep).endswith(os.path.join('assets', 'animation.py')):
                                        if hasattr(mod, 'set_anim_time_scale'):
                                            try:
                                                mod.set_anim_time_scale(slow_scale)
                                                logger.debug("set_anim_time_scale -> %s (via sys.modules %s)", slow_scale, name)
                                            except Exception:
                                                pass
                                        else:
                                            try:
                                                setattr(mod, 'ANIM_TIME_SCALE', float(slow_scale))
                                                logger.debug("ANIM_TIME_SCALE set -> %s (via sys.modules %s)", slow_scale, name)
                                            except Exception:
                                                pass
                                    if mf and mf.replace('/', os.sep).endswith(os.path.join('assets', 'image_loader.py')):
                                        if hasattr(mod, '_gif_animation_cache'):
                                            try:
                                                mod._gif_animation_cache.clear()
                                                logger.debug("image_loader: gif cache cleared (via sys.modules %s)", name)
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    except Exception:
                        pass

        # draw modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,190))
        screen.blit(overlay, (0,0))
        surf = pygame.Surface((w, h))
        surf.fill((210,215,220))
        pygame.draw.rect(surf, (70,70,70), (0,0,w,h), 3)
        title = FONT.render("駒移動アニメーション設定", True, (30,30,30))
        surf.blit(title, (20, 12))

        # options
        try:
            opt_x = 40
            opt_y = 48
            gap = 36
            # pulse
            pygame.draw.rect(surf, (230,230,230), (opt_x, opt_y, 24, 24))
            pygame.draw.rect(surf, (80,80,80), (opt_x, opt_y, 24, 24), 2)
            if ai_move_pulse_enabled:
                pygame.draw.circle(surf, (40,120,220), (opt_x+12, opt_y+12), 6)
            surf.blit(SMALL.render("駒移動パルスを表示する", True, (30,30,30)), (opt_x+36, opt_y))

            # ghost
            oy = opt_y + gap
            pygame.draw.rect(surf, (230,230,230), (opt_x, oy, 24, 24))
            pygame.draw.rect(surf, (80,80,80), (opt_x, oy, 24, 24), 2)
            if ai_move_ghost_enabled:
                pygame.draw.circle(surf, (120,120,120), (opt_x+12, oy+12), 6)
            surf.blit(SMALL.render("駒のゴーストを表示する", True, (30,30,30)), (opt_x+36, oy))

            # arrow
            oy2 = opt_y + gap*2
            pygame.draw.rect(surf, (230,230,230), (opt_x, oy2, 24, 24))
            pygame.draw.rect(surf, (80,80,80), (opt_x, oy2, 24, 24), 2)
            if ai_move_arrow_enabled:
                pygame.draw.circle(surf, (220,40,40), (opt_x+12, oy2+12), 6)
            surf.blit(SMALL.render("移動方向の矢印を表示する", True, (30,30,30)), (opt_x+36, oy2))
        except Exception:
            pass

        # animation speed radios (draw before back button)
        try:
            # determine current selection: prefer explicit user choice stored in this
            # module (user_anim_scale). Fallback to the animation module's getter.
            try:
                if globals().get('user_anim_scale') is not None:
                    cur_scale = float(globals().get('user_anim_scale'))
                else:
                    cur_scale = animation_mod.get_anim_time_scale() if animation_mod and hasattr(animation_mod, 'get_anim_time_scale') else 1.0
            except Exception:
                cur_scale = float(globals().get('user_anim_scale')) if globals().get('user_anim_scale') is not None else 1.0
            # normalize: pick explicit selected option to avoid overlapping draw conditions
            try:
                d_fast = abs(cur_scale - fast_scale)
                d_slow = abs(cur_scale - slow_scale)
                if d_fast <= d_slow:
                    selected_speed = 'fast'
                else:
                    selected_speed = 'slow'
            except Exception:
                selected_speed = 'slow'
            try:
                logger.debug(f"radio draw cur_scale={cur_scale} fast={fast_scale} slow={slow_scale} user_anim_scale={globals().get('user_anim_scale')} selected={selected_speed}")
            except Exception:
                pass
            radio_x = opt_x
            # move radios one extra gap downward to create a gap for the new label
            radio_y = opt_y + gap*4 + 12

            # draw the label above the radios in the new gap
            try:
                label_txt = SMALL.render("アニメーション表示時間", True, (30,30,30))
                label_x = opt_x
                label_y = opt_y + gap*3 + 6
                surf.blit(label_txt, (label_x, label_y))
            except Exception:
                pass

            # draw a subtle background for the radio area to make it visible
            try:
                pygame.draw.rect(surf, (245,245,250), (radio_x-8, radio_y-8, 360, 44))
                pygame.draw.rect(surf, (200,200,200), (radio_x-8, radio_y-8, 360, 44), 1)
            except Exception:
                pass

            # fast radio (left)
            fx = radio_x
            fy = radio_y
            pygame.draw.circle(surf, (200,200,200), (fx+10, fy+12), 10)
            # selected indicator
            try:
                if selected_speed == 'fast':
                    pygame.draw.circle(surf, (40,120,220), (fx+10, fy+12), 6)
            except Exception:
                if cur_scale <= (fast_scale + slow_scale) / 2.0:
                    pygame.draw.circle(surf, (40,120,220), (fx+10, fy+12), 6)
            surf.blit(SMALL.render("早い", True, (30,30,30)), (fx+28, fy))

            # slow radio (right)
            sx = radio_x + 120
            sy = radio_y
            pygame.draw.circle(surf, (200,200,200), (sx+10, sy+12), 10)
            try:
                if selected_speed == 'slow':
                    pygame.draw.circle(surf, (220,40,40), (sx+10, sy+12), 6)
            except Exception:
                if cur_scale > (fast_scale + slow_scale) / 2.0:
                    pygame.draw.circle(surf, (220,40,40), (sx+10, sy+12), 6)
            surf.blit(SMALL.render("遅い", True, (30,30,30)), (sx+28, sy))

            # debug log to console so user can see radio drawing state
            try:
                logger.debug(f"animation radios drawn: cur_scale={cur_scale:.3f} fast={fast_scale:.3f} slow={slow_scale:.3f}")
            except Exception:
                logger.debug("animation radios drawn: cur_scale=%s fast=%s slow=%s", cur_scale, fast_scale, slow_scale)
        except Exception:
            pass

        # back
        back_rect = pygame.Rect(w - 120, h - 56, 100, 40)
        pygame.draw.rect(surf, (220,220,220), back_rect)
        pygame.draw.rect(surf, (70,70,70), back_rect, 2)
        back_txt = SMALL.render("戻る", True, (30,30,30))
        surf.blit(back_txt, (back_rect.x + (back_rect.w - back_txt.get_width())//2, back_rect.y + (back_rect.h - back_txt.get_height())//2))

        screen.blit(surf, (x, y))
        pygame.display.flip()
        clk.tick(30)

def get_piece_at(row, col):
    # 後方互換のための薄いラッパー
    return chess.get_piece_at(row, col)

def on_board(r,c):
    return 0 <= r < 8 and 0 <= c < 8

def simulate_move(src_piece, to_r, to_c):
    return chess.simulate_move(src_piece, to_r, to_c)

def is_in_check_for_display(pcs, color):
    """
    表示用のチェック判定。
    - 凍結は無視（表示は出す）
    - ルールの合法手生成に依存せず、幾何学的な“攻撃”で判定する
      （駒の種類ごとの攻撃方向・到達可能マスでキングが射程内かを見る）
    """
    # キング位置
    king = None
    for p in pcs:
        try:
            if p.name == 'K' and p.color == color:
                king = p
                break
        except Exception:
            if isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color:
                king = p
                break
    if not king:
        return False

    # 安全な属性/辞書アクセス
    def _pget(obj, key):
        try:
            return getattr(obj, key)
        except Exception:
            try:
                return obj.get(key)
            except Exception:
                return None

    kr = _pget(king, 'row')
    kc = _pget(king, 'col')

    opponent = 'black' if color == 'white' else 'white'

    # 盤上の駒を取得する関数
    def piece_at(r, c):
        try:
            return chess.get_piece_at(r, c)
        except Exception:
            # フォールバック（pcsを走査）
            for q in pcs:
                rr = _pget(q, 'row')
                cc = _pget(q, 'col')
                if rr == r and cc == c:
                    return q
            return None

    # 1) ナイトの攻撃
    for dr, dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
        pr, pc = kr + dr, kc + dc
        p = piece_at(pr, pc)
        if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'N':
            return True

    # 2) ポーンの攻撃
    pawn_dirs = [(-1, -1), (-1, 1)] if opponent == 'white' else [(1, -1), (1, 1)]
    for dr, dc in pawn_dirs:
        pr, pc = kr + dr, kc + dc
        p = piece_at(pr, pc)
        if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'P':
            return True

    # 3) キングの隣接攻撃
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr == 0 and dc == 0:
                continue
            pr, pc = kr + dr, kc + dc
            p = piece_at(pr, pc)
            if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'K':
                return True

    # 4) 直線・斜めのレイ（R/B/Q）
    ray_dirs = [
        (-1,0),(1,0),(0,-1),(0,1),   # R, Q
        (-1,-1),(-1,1),(1,-1),(1,1)  # B, Q
    ]
    for dr, dc in ray_dirs:
        pr, pc = kr + dr, kc + dc
        while 0 <= pr < 8 and 0 <= pc < 8:
            p = piece_at(pr, pc)
            if p is None:
                pr += dr
                pc += dc
                continue
            pcol = _pget(p, 'color')
            pname = _pget(p, 'name')
            if pcol != opponent:
                break
            # この方向に応じて当たり判定
            if dr == 0 or dc == 0:  # 縦横
                if pname in ('R', 'Q'):
                    return True
            if dr != 0 and dc != 0:  # 斜め
                if pname in ('B', 'Q'):
                    return True
            break

    return False

def is_in_check(pcs, color):
    """
    ゲームルール用のチェック判定。
    凍結されている駒は動けないため、その駒からの攻撃は無視する。
    """
    # find king of color
    king = None
    for p in pcs:
        if (hasattr(p, 'name') and p.name == 'K' and p.color == color) or \
           (isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color):
            king = p
            break
    if not king:
        return False
    
    king_row = king.row if hasattr(king, 'row') else king.get('row')
    king_col = king.col if hasattr(king, 'col') else king.get('col')
    king_pos = (king_row, king_col)
    opponent = 'black' if color == 'white' else 'white'
    
    frozen = getattr(game, 'frozen_pieces', {})

    for p in pcs:
        p_color = p.color if hasattr(p, 'color') else p.get('color')
        if p_color == opponent:
            # 凍結されている駒は攻撃できないため、チェック判定から除外
            is_frozen = False
            try:
                is_frozen = (id(p) in frozen and frozen.get(id(p), 0) > 0) or (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0)
            except Exception:
                is_frozen = (id(p) in frozen and frozen.get(id(p), 0) > 0)
            if is_frozen:
                continue
            
            # この駒の有効手を取得(ignore_castling=Trueで高速化)
            if hasattr(p, 'get_valid_moves'):
                m = p.get_valid_moves(pcs, ignore_castling=True)
            else:
                # dict形式の場合はスキップ(通常はPieceオブジェクト)
                continue
                
            if king_pos in m:
                return True
    return False


def can_attack_king_with_cards(pcs, color):
    """
    カード効果（迅雷や暴風のジャンプ等）を考慮して、相手が現在の手でキングを攻撃できるかを判定する（表示用）。
    get_valid_moves(..., ignore_check=True) を用いて、カード付与の特殊手を含めて射程を検査する。
    """
    # find king pos
    king = None
    for p in pcs:
        try:
            if p.name == 'K' and p.color == color:
                king = p
                break
        except Exception:
            if isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color:
                king = p
                break
    if not king:
        return False
    kr = getattr(king, 'row', None) if hasattr(king, 'row') else king.get('row')
    kc = getattr(king, 'col', None) if hasattr(king, 'col') else king.get('col')
    if kr is None or kc is None:
        return False

    opponent = 'black' if color == 'white' else 'white'
    try:
        for p in pcs:
            pcol = getattr(p, 'color', None) if hasattr(p, 'color') else (p.get('color') if isinstance(p, dict) else None)
            if pcol != opponent:
                continue
            try:
                moves = get_valid_moves(p, ignore_check=True)
            except Exception:
                moves = []
            for mv in moves:
                if mv == (kr, kc):
                    return True
    except Exception:
        return False
    return False

def get_valid_moves(piece, pcs=None, ignore_check=False):
    # pcs: list of piece dicts; if None, use global pieces
    if pcs is None:
        # prefer local 'pieces' (dict-style) if present, otherwise fall back to chess.pieces
        pcs = globals().get('pieces', chess.pieces)
    moves = []
    # If this piece is frozen by a card effect, it cannot move.
    # The UI sometimes passes dict-style piece representations while the
    # engine maintains canonical Piece instances in chess.pieces. Try to
    # resolve the canonical engine piece at the piece's location and consult
    # the freeze map and transient attribute on that instance.
    frozen_map = getattr(game, 'frozen_pieces', {}) or {}
    try:
        # get row/col from either object attributes or dict keys
        prow = getattr(piece, 'row', None)
        pcol = getattr(piece, 'col', None)
    except Exception:
        prow = None
        pcol = None
    try:
        if (prow is None or pcol is None) and isinstance(piece, dict):
            prow = prow if prow is not None else piece.get('row')
            pcol = pcol if pcol is not None else piece.get('col')
    except Exception:
        pass

    engine_piece = None
    try:
        if prow is not None and pcol is not None:
            engine_piece = chess.get_piece_at(int(prow), int(pcol))
    except Exception:
        engine_piece = None

    # Check freeze on canonical engine piece first
    try:
        if engine_piece is not None:
            if (id(engine_piece) in frozen_map and frozen_map.get(id(engine_piece), 0) > 0) or (hasattr(engine_piece, 'frozen_turns') and getattr(engine_piece, 'frozen_turns', 0) > 0):
                return []
    except Exception:
        pass

    # Fallback: check freeze on the passed-in piece object itself
    try:
        if (id(piece) in frozen_map and frozen_map.get(id(piece), 0) > 0) or (hasattr(piece, 'frozen_turns') and getattr(piece, 'frozen_turns', 0) > 0):
            return []
    except Exception:
        pass

    # small accessor to support both object-style Piece and dict-style pieces
    def _pget(p, key, default=None):
        if hasattr(p, key):
            return getattr(p, key)
        try:
            return p[key]
        except Exception:
            return default

    name = _pget(piece, 'name')
    r, c = _pget(piece, 'row'), _pget(piece, 'col')
    color = _pget(piece, 'color')

    def occupied(rr,cc):
        return get_piece_at(rr,cc) is not None
    def occupied_by_color(rr,cc,color):
        p = get_piece_at(rr,cc)
        return p is not None and _pget(p, 'color')==color
    def is_blocked_tile(rr, cc, color):
        # If a blocked tile applies to this color, disallow moving there
        try:
            # Prefer model helper if available (handles multi-entry representation)
            if getattr(game, 'is_tile_blocked_for', None) is not None:
                try:
                    # game.is_tile_blocked_for(tile, color) -> True if blocked for that color
                    if game.is_tile_blocked_for((rr, cc), color):
                        return True
                except Exception:
                    pass
            # Fallback to legacy single-owner mapping
            if getattr(game, 'blocked_tiles_owner', None) is not None:
                owner = game.blocked_tiles_owner.get((rr, cc))
                if owner == color:
                    return True
        except Exception:
            pass
        return False

    if name == 'P':
        dir = -1 if color == 'white' else 1
        # storm jump for pawn: if next_move_can_jump and front square is blocked, jump over it
        try:
            # support jump flag for both players: white uses game.player.next_move_can_jump,
            # black (AI) uses module-level ai_next_move_can_jump
            if color == 'white':
                can_jump = getattr(game, 'player', None) is not None and getattr(game.player, 'next_move_can_jump', False)
            else:
                # prefer game-level AI flag if present (set by card effects), otherwise fall back to module-level global
                can_jump = getattr(game, 'ai_next_move_can_jump', globals().get('ai_next_move_can_jump', False))
        except Exception:
            can_jump = False
        
        # Check if storm jump applies (front square occupied)
        front_occupied = on_board(r+dir, c) and occupied(r+dir, c)
        
        if can_jump and front_occupied:
            # Jump over the front piece to 2 squares ahead (can capture enemy there)
            nr2 = r + 2*dir
            if on_board(nr2, c) and not occupied_by_color(nr2, c, color) and not is_blocked_tile(nr2, c, color):
                moves.append((nr2, c))
        else:
            # Normal forward movement (only if front is NOT occupied or storm not active)
            if on_board(r+dir, c) and not occupied(r+dir,c) and not is_blocked_tile(r+dir, c, color):
                moves.append((r+dir,c))
                # double from starting rank
                start_row = 6 if color == 'white' else 1
                if r==start_row and on_board(r+2*dir,c) and not occupied(r+2*dir,c) and not is_blocked_tile(r+2*dir, c, color):
                    moves.append((r+2*dir,c))
        # captures
        for dc in (-1,1):
            nr,nc = r+dir, c+dc
            if on_board(nr,nc) and occupied(nr,nc) and not occupied_by_color(nr,nc,color) and not is_blocked_tile(nr, nc, color):
                moves.append((nr,nc))
        # en passant — use chess.en_passant_target if present
        if getattr(chess, 'en_passant_target', None) is not None:
            target_r, target_c = chess.en_passant_target
            if color == 'white' and r == 3:
                if abs(c - target_c) == 1 and target_r == 2 and not is_blocked_tile(target_r, target_c, color):
                    moves.append((target_r, target_c))
            elif color == 'black' and r == 4:
                if abs(c - target_c) == 1 and target_r == 5 and not is_blocked_tile(target_r, target_c, color):
                    moves.append((target_r, target_c))
    elif name == 'N':
        for dr,dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
            nr,nc = r+dr, c+dc
            if on_board(nr,nc) and not occupied_by_color(nr,nc,color) and not is_blocked_tile(nr, nc, color):
                moves.append((nr,nc))
    elif name in ('B','R','Q'):
        directions = []
        if name in ('B','Q'):
            directions += [(-1,-1),(-1,1),(1,-1),(1,1)]
        if name in ('R','Q'):
            directions += [(-1,0),(1,0),(0,-1),(0,1)]
        for dr,dc in directions:
            step = 1
            jumped = False
            while True:
                nr,nc = r+dr*step, c+dc*step
                if not on_board(nr,nc):
                    break
                # If this tile is blocked for this piece's color, movement cannot pass or land here
                if is_blocked_tile(nr, nc, color):
                    break

                if occupied(nr,nc):
                    if not occupied_by_color(nr,nc,color):
                        # Only allow capture if the tile itself is not blocked for this color
                        if not is_blocked_tile(nr, nc, color):
                            moves.append((nr,nc))
                    # If a card granted a single jump ability, allow jumping over one piece
                    try:
                        if color == 'white':
                            can_jump = getattr(game, 'player', None) is not None and getattr(game.player, 'next_move_can_jump', False)
                        else:
                            can_jump = getattr(game, 'ai_next_move_can_jump', globals().get('ai_next_move_can_jump', False))
                    except Exception:
                        can_jump = False
                    if can_jump and not jumped:
                        # attempt to land on the next square beyond this occupied square
                        step2 = step + 1
                        nr2, nc2 = r+dr*step2, c+dc*step2
                        if on_board(nr2, nc2) and not occupied_by_color(nr2, nc2, color) and not is_blocked_tile(nr2, nc2, color):
                            moves.append((nr2, nc2))
                        # only allow a single jump; stop after
                    break

                # empty and not blocked -> can move here
                moves.append((nr,nc))
                step += 1
    elif name == 'K':
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                nr,nc = r+dr, c+dc
                if on_board(nr,nc) and not occupied_by_color(nr,nc,color) and not is_blocked_tile(nr, nc, color):
                    moves.append((nr,nc))

        # キャスリング
        if not _pget(piece, 'has_moved', False) and not ignore_check:
            if color == 'white':
                king_row = 7
            else:
                king_row = 0

            rook_kingside = get_piece_at(king_row, 7)
            if (rook_kingside and _pget(rook_kingside, 'name') == 'R' and
                _pget(rook_kingside, 'color') == color and
                not _pget(rook_kingside, 'has_moved', False)):
                # ensure path squares are free and not blocked for this color
                if (not occupied(king_row, 5) and not occupied(king_row, 6)
                        and not is_blocked_tile(king_row, 5, color) and not is_blocked_tile(king_row, 6, color)):
                    moves.append((king_row, 6))  # キャスリング後のキングの位置

            rook_queenside = get_piece_at(king_row, 0)
            if (rook_queenside and _pget(rook_queenside, 'name') == 'R' and
                _pget(rook_queenside, 'color') == color and
                not _pget(rook_queenside, 'has_moved', False)):
                # ensure path squares are free and not blocked for this color
                if (not occupied(king_row, 1) and not occupied(king_row, 2) and not occupied(king_row, 3)
                        and not is_blocked_tile(king_row, 1, color) and not is_blocked_tile(king_row, 2, color) and not is_blocked_tile(king_row, 3, color)):
                    moves.append((king_row, 2))  # キャスリング後のキングの位置

    # filter moves that leave king in check
    # 例外1: 同時チェック中はフィルタを無効化（ルールで許可）
    # 例外2: 自分がチェック中かつ『迅雷』が有効、
    #        または[DEBUG] カード直後のみ許可モードで直前にカード使用扱いの場合は
    #        「チェック回避の手」か「相手にチェックを与える手（反撃チェック）」を許可する
    if not ignore_check and not globals().get('simul_check_active', False):
        legal = []
        try:
            self_in_check = is_in_check(chess.pieces, color)
        except Exception:
            self_in_check = False
        # 迅雷の有効判定（白=player、黒=AI）
        try:
            if color == 'white':
                lightning_active = getattr(game, 'player_consecutive_turns', 0) > 0
            else:
                lightning_active = globals().get('ai_consecutive_turns', 0) > 0
        except Exception:
            lightning_active = False
        # [DEBUG] カード直後のみ許可モードのゲート
        try:
            debug_card_gate = globals().get('DEBUG_COUNTER_CHECK_CARD_MODE', False) and getattr(game, '_debug_last_action_was_card', False)
        except Exception:
            debug_card_gate = False
        opp = 'black' if color == 'white' else 'white'
        for mv in moves:
            newp = simulate_move(piece, mv[0], mv[1])
            # 通常: 自駒がチェックでない局面にできる手のみ
            if not is_in_check(newp, color):
                legal.append(mv)
                continue
            # 反撃チェックの特例1: 自分がチェック中で、迅雷またはデバッグモード時
            if self_in_check and (lightning_active or debug_card_gate):
                try:
                    if is_in_check(newp, opp):
                        legal.append(mv)
                        continue
                except Exception:
                    pass
            # 反撃チェックの特例2: 自分がチェック中でない時、迅雷またはデバッグモード時
            # 「自分がチェックされる位置でも、相手にもチェックを与えるなら許可」
            if not self_in_check and (lightning_active or debug_card_gate):
                try:
                    if is_in_check(newp, opp):
                        legal.append(mv)
                        continue
                except Exception:
                    pass
        return legal
    return moves

def has_legal_moves_for(color):
    return chess.has_legal_moves_for(color)

def has_legal_moves_with_cards(color):
    """カード効果（暴風のジャンプ、封鎖、凍結）込みで合法手が存在するかを判定。
    盤面は chess_engine の pieces を参照しつつ、移動生成は本ファイルの get_valid_moves を使う。
    """
    try:
        for p in chess.pieces:
            # カラー取得（オブジェクト/辞書対応）
            try:
                pcolor = getattr(p, 'color', None)
            except Exception:
                pcolor = p.get('color') if isinstance(p, dict) else None
            if pcolor != color:
                continue
            moves = get_valid_moves(p, ignore_check=True)
            for mv in moves:
                newp = simulate_move(p, mv[0], mv[1])
                if not is_in_check(newp, color):
                    return True
        return False
    except Exception:
        # フォールバック: 既存のチェスエンジン関数
        return chess.has_legal_moves_for(color)

def apply_move(piece, to_r, to_c):
    return chess.apply_move(piece, to_r, to_c)

def ai_make_move():
    # AI difficulty-aware move selection (black)
    import random
    global CPU_DIFFICULTY
    global ai_player, ai_next_move_can_jump, ai_extra_moves_this_turn, ai_consecutive_turns

    # Begin AI turn: restore PP and draw 1 card (simple turn-start behavior for AI).
    # If this ai_make_move() call is a continuation of a '迅雷' extra-turn
    # (ai_continuation True), skip start-of-turn effects (PP reset / draw).
    global ai_continuation
    try:
        if ai_continuation:
            # This is an extra consecutive AI move; do not reset PP or draw.
            ai_continuation = False
            logger.debug("AI連続ターン: フラグリセットスキップ")
        else:
            # AI ターン開始フラグをリセット（ドロー前に実行）
            game._ai_turn_sep_added = False
            logger.debug("AIターン開始: _ai_turn_sep_added=%s", getattr(game, '_ai_turn_sep_added', None))
            ai_player.reset_pp()
            # draw 1 card if available and hand limit not exceeded
            if len(ai_player.hand.cards) < getattr(ai_player, 'hand_limit', 7):
                c = ai_player.deck.draw()
                if c:
                    ai_player.hand.add(c)
                    game.log.append("─── AIのターン ───")
                    game.log.append("AI: ターン開始で1枚ドローしました。")
                    logger.debug("AIドロー成功")
            else:
                # ドローしない場合でもAIターン開始を記録
                game.log.append("─── AIのターン ───")
                logger.debug("AIドロースキップ: 手札満杯")
    except Exception:
        # defensive: ignore if ai_player not properly initialized
        pass

    # AI: チェス手前にカード使用を考慮
    def ai_consider_play_card():
        # Ensure assignments to module-level AI flags affect globals (nested function)
        global ai_next_move_can_jump, ai_extra_moves_this_turn, ai_consecutive_turns
        # aggressiveness / per-attempt probability by difficulty
        # significantly increased to make AI use cards more frequently
        probs = {1: 0.55, 2: 0.75, 3: 0.90, 4: 0.99}
        p_play = probs.get(CPU_DIFFICULTY, 0.65)
        if not ai_player.hand.cards:
            try:
                game.log.append(f"AI: 手札が空です（カード使用をスキップ）")
            except Exception:
                pass
            return False

        # Gather simple board metrics to influence card choice (mobility, high-value targets)
        try:
            my_move_count = 0
            opp_move_count = 0
            for p in chess.pieces:
                try:
                    moves = get_valid_moves(p, ignore_check=True)
                except Exception:
                    moves = []
                if getattr(p, 'color', None) == 'black':
                    my_move_count += len(moves)
                else:
                    opp_move_count += len(moves)
        except Exception:
            my_move_count = opp_move_count = 0

        # highest opponent piece value (for targeting priorities)
        vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        highest_opp_val = 0
        try:
            for p in chess.pieces:
                if getattr(p, 'color', None) == 'white':
                    highest_opp_val = max(highest_opp_val, vals.get(getattr(p, 'name', ''), 0))
        except Exception:
            highest_opp_val = 0

        # decide how many attempts to try this turn (higher difficulty => more plays)
        # increased to make AI play more cards per turn
        max_attempts = {1: 2, 2: 3, 3: 4, 4: 5}.get(CPU_DIFFICULTY, 3)
        attempts = 0
        made_any = False
        played_names = set()  # avoid repeating the same card multiple times in one AI think session
        while attempts < max_attempts:
            # if random roll fails, stop trying further plays
            if random.random() > p_play:
                break

            # recompute playable indices according to current PP
            playable = [i for i, c in enumerate(ai_player.hand.cards) if c.can_play(ai_player) and c.name not in played_names]
            if not playable:
                break

            # prefer list (disruptive first), but adjust order by simple board heuristics
            names = [ai_player.hand.cards[i].name for i in playable]
            prefer = ['氷結', '灼熱', '暴風', '迅雷', '2ドロー', '錬成']
            # If opponent has much higher mobility, prefer blocking (灼熱)
            if opp_move_count > my_move_count + 4:
                prefer.remove('灼熱') if '灼熱' in prefer else None
                prefer.insert(0, '灼熱')
            # If AI has low mobility, prefer buffs that grant movement (暴風/迅雷)
            if '暴風' in prefer:
                # Estimate whether 暴風 (jump) would actually increase AI mobility.
                try:
                    # compute moves with jump enabled by temporarily toggling flag
                    before_moves = my_move_count
                    added = 0
                    try:
                        # set a temporary flag so get_valid_moves considers jump
                        prev_flag_game = getattr(game, 'ai_next_move_can_jump', None)
                        prev_flag_global = globals().get('ai_next_move_can_jump', None)
                        try:
                            setattr(game, 'ai_next_move_can_jump', True)
                        except Exception:
                            globals()['ai_next_move_can_jump'] = True
                        # recompute AI move count with jump
                        with_jump = 0
                        for p in chess.pieces:
                            try:
                                if getattr(p, 'color', None) == 'black':
                                    with_jump += len(get_valid_moves(p, ignore_check=True))
                            except Exception:
                                pass
                        added = with_jump - before_moves
                    finally:
                        # restore flags
                        try:
                            if prev_flag_game is None:
                                try:
                                    delattr(game, 'ai_next_move_can_jump')
                                except Exception:
                                    globals().pop('ai_next_move_can_jump', None)
                            else:
                                setattr(game, 'ai_next_move_can_jump', prev_flag_game)
                        except Exception:
                            try:
                                if prev_flag_global is None:
                                    globals().pop('ai_next_move_can_jump', None)
                                else:
                                    globals()['ai_next_move_can_jump'] = prev_flag_global
                            except Exception:
                                pass
                    # prefer 暴風 only if it yields at least one extra legal move
                    if my_move_count < opp_move_count and added > 0:
                        prefer.remove('暴風')
                        prefer.insert(0, '暴風')
                    elif my_move_count < opp_move_count and added <= 0:
                        # don't aggressively pick 暴風 if it doesn't increase mobility
                        if '暴風' in prefer:
                            prefer.remove('暴風')
                            # reinsert lower in preference
                            pref_tail = ['迅雷', '2ドロー', '錬成']
                            for t in pref_tail:
                                if t in prefer:
                                    prefer.insert(prefer.index(t), '暴風')
                                    break
                except Exception:
                    # fallback to original behavior if any error
                    if my_move_count < opp_move_count and '暴風' in prefer:
                        prefer.remove('暴風')
                        prefer.insert(0, '暴風')
            # If there are no good non-king targets, deprioritize 氷結 (avoid always freezing the king)
            try:
                opp_non_king_exists = any(getattr(p, 'color', None) == 'white' and getattr(p, 'name', None) != 'K' for p in chess.pieces)
            except Exception:
                opp_non_king_exists = False
            if not opp_non_king_exists and '氷結' in prefer:
                # move 氷結 to the end so AI won't pick it unless nothing better
                prefer = [x for x in prefer if x != '氷結'] + ['氷結']
            # If opponent has a high-value piece, prioritize 氷結
            if highest_opp_val >= 5:
                if '氷結' in prefer:
                    prefer.remove('氷結')
                    prefer.insert(0, '氷結')
            chosen_idx = None
            # Difficulty-aware selection: for Normal+ use a scoring function to pick the best card
            if CPU_DIFFICULTY >= 2:
                scores = {}
                # helper: estimate added mobility from 暴風 for current board
                def estimate_jump_added():
                    try:
                        before = 0
                        for p in chess.pieces:
                            try:
                                if getattr(p, 'color', None) == 'black':
                                    before += len(get_valid_moves(p, ignore_check=True))
                            except Exception:
                                pass
                        # toggle jump flag
                        prev_game_flag = getattr(game, 'ai_next_move_can_jump', None)
                        prev_global_flag = globals().get('ai_next_move_can_jump', None)
                        try:
                            try:
                                setattr(game, 'ai_next_move_can_jump', True)
                            except Exception:
                                globals()['ai_next_move_can_jump'] = True
                            with_jump = 0
                            for p in chess.pieces:
                                try:
                                    if getattr(p, 'color', None) == 'black':
                                        with_jump += len(get_valid_moves(p, ignore_check=True))
                                except Exception:
                                    pass
                        finally:
                            # restore
                            try:
                                if prev_game_flag is None:
                                    try:
                                        delattr(game, 'ai_next_move_can_jump')
                                    except Exception:
                                        globals().pop('ai_next_move_can_jump', None)
                                else:
                                    setattr(game, 'ai_next_move_can_jump', prev_game_flag)
                            except Exception:
                                try:
                                    if prev_global_flag is None:
                                        globals().pop('ai_next_move_can_jump', None)
                                    else:
                                        globals()['ai_next_move_can_jump'] = prev_global_flag
                                except Exception:
                                    pass
                        return with_jump - before
                    except Exception:
                        return 0

                # precompute some context used in heuristics
                try:
                    capture_ops = 0
                    for p, mv in candidates:
                        tgt = chess.get_piece_at(mv[0], mv[1])
                        if tgt is not None and getattr(tgt, 'color', None) == 'white':
                            capture_ops += 1
                except Exception:
                    capture_ops = 0

                for idx in playable:
                    try:
                        card = ai_player.hand.cards[idx]
                        name = card.name
                        # base score from preference order (higher better)
                        base = 0
                        if name in prefer:
                            base = (len(prefer) - prefer.index(name)) * 12
                        else:
                            base = 6
                        score = base
                        # Enhanced heuristics per card
                        if name == '暴風':
                            
                            benefit = 0
                            try:
                                # collect before-move sets per AI piece
                                before_map = {}
                                for p in chess.pieces:
                                    try:
                                        if getattr(p, 'color', None) == 'black':
                                            before_map[p] = set(tuple(m) for m in get_valid_moves(p, ignore_check=True))
                                    except Exception:
                                        before_map[p] = set()

                                prev_game_flag = getattr(game, 'ai_next_move_can_jump', None)
                                prev_global_flag = globals().get('ai_next_move_can_jump', None)
                                try:
                                    try:
                                        setattr(game, 'ai_next_move_can_jump', True)
                                    except Exception:
                                        globals()['ai_next_move_can_jump'] = True

                                    # find opponent king for distance heuristics
                                    opp_king = next((pp for pp in chess.pieces if getattr(pp, 'color', None) == 'white' and getattr(pp, 'name', '') == 'K'), None)

                                    for p, prev_moves in list(before_map.items()):
                                        try:
                                            with_moves = set(tuple(m) for m in get_valid_moves(p, ignore_check=True))
                                            new_moves = with_moves - prev_moves
                                            for mv in new_moves:
                                                # capture opportunity
                                                try:
                                                    tgt = chess.get_piece_at(mv[0], mv[1])
                                                except Exception:
                                                    tgt = None
                                                if tgt is not None and getattr(tgt, 'color', None) == 'white':
                                                    benefit += 30
                                                else:
                                                    # small bonus for any additional reachable square
                                                    benefit += 4
                                                    # bonus if the new move gets closer to opponent king
                                                    try:
                                                        if opp_king is not None:
                                                            pr, pc = getattr(p, 'row', 0), getattr(p, 'col', 0)
                                                            kr, kc = getattr(opp_king, 'row', 0), getattr(opp_king, 'col', 0)
                                                            before_dist = abs(pr - kr) + abs(pc - kc)
                                                            new_dist = abs(mv[0] - kr) + abs(mv[1] - kc)
                                                            if new_dist < before_dist:
                                                                benefit += 8
                                                    except Exception:
                                                        pass
                                        except Exception:
                                            pass
                                finally:
                                    # restore flags
                                    try:
                                        if prev_game_flag is None:
                                            try:
                                                delattr(game, 'ai_next_move_can_jump')
                                            except Exception:
                                                globals().pop('ai_next_move_can_jump', None)
                                        else:
                                            setattr(game, 'ai_next_move_can_jump', prev_game_flag)
                                    except Exception:
                                        try:
                                            if prev_global_flag is None:
                                                globals().pop('ai_next_move_can_jump', None)
                                            else:
                                                globals()['ai_next_move_can_jump'] = prev_global_flag
                                        except Exception:
                                            pass
                            except Exception:
                                benefit = 0

                            # reward based on computed benefit
                            score += benefit
                            # small fallback bonus if AI is under pressure
                            if my_move_count < opp_move_count:
                                score += 10
                        elif name == '氷結':
                            # prefer freezing non-king high-value pieces
                            try:
                                best_v = 0
                                piece_count = 0
                                for p in chess.pieces:
                                    if getattr(p, 'color', None) == 'white' and getattr(p, 'name', '') != 'K':
                                        v = {'P':1,'N':3,'B':3,'R':5,'Q':9}.get(getattr(p, 'name', ''), 0)
                                        best_v = max(best_v, v)
                                        piece_count += 1
                                score += best_v * 10
                                # bonus for having multiple good targets
                                if piece_count >= 3:
                                    score += 12
                            except Exception:
                                pass
                        elif name == '灼熱':
                            # useful when opponent mobility >> ours
                            mob_diff = opp_move_count - my_move_count
                            score += max(0, mob_diff) * 8
                            # bonus for blocking opponent's key squares
                            if mob_diff > 5:
                                score += 20
                        elif name == '迅雷':
                            # prefer if capture opportunities exist or we have mobility to exploit
                            score += capture_ops * 12
                            # also prefer when AI mobility is lower than opponent
                            if my_move_count < opp_move_count:
                                score += 10
                            # bonus if AI has pieces near opponent king
                            try:
                                opp_king = next((p for p in chess.pieces if getattr(p, 'color', None) == 'white' and getattr(p, 'name', '') == 'K'), None)
                                if opp_king:
                                    kr, kc = getattr(opp_king, 'row', 0), getattr(opp_king, 'col', 0)
                                    nearby = sum(1 for p in chess.pieces if getattr(p, 'color', None) == 'black' and abs(getattr(p, 'row', 0) - kr) <= 2 and abs(getattr(p, 'col', 0) - kc) <= 2)
                                    score += nearby * 8
                            except Exception:
                                pass
                        elif name == '2ドロー':
                            # prefer when hand is low
                            hand_size = len(ai_player.hand.cards)
                            if hand_size <= 2:
                                score += 25
                            elif hand_size <= 4:
                                score += 15
                        elif name == '錬成':
                            # prefer to generate card advantage
                            score += 8
                            # bonus if deck has more cards
                            if len(getattr(ai_player.deck, 'cards', [])) > 5:
                                score += 10
                        scores[idx] = score
                    except Exception:
                        scores[idx] = 0

                # pick best according to difficulty randomness
                if scores:
                    best_idx = max(scores, key=scores.get)
                    if CPU_DIFFICULTY == 2:
                        # Normal: 80% pick best, 20% choose random among playable
                        if random.random() < 0.8:
                            chosen_idx = best_idx
                        else:
                            chosen_idx = random.choice(playable)
                    elif CPU_DIFFICULTY == 3:
                        # Hard: 95% pick best
                        if random.random() < 0.95:
                            chosen_idx = best_idx
                        else:
                            chosen_idx = random.choice(playable)
                    else:
                        # Very-hard: always pick best
                        chosen_idx = best_idx
                else:
                    chosen_idx = random.choice(playable)
            else:
                # Easy: keep original simple preference/random behavior
                for pref in prefer:
                    if pref in names:
                        chosen_idx = playable[names.index(pref)]
                        break
                if chosen_idx is None:
                    chosen_idx = random.choice(playable)

            # attempt play via unified resolver so AI follows same rules as player
            try:
                ok, msg = game.play_card_for(ai_player, chosen_idx)
                card_name = ai_player.hand.cards[chosen_idx].name if 0 <= chosen_idx < len(ai_player.hand.cards) else None
                if ok:
                    made_any = True
                    # record that we've just used this card to avoid repeating it
                    if card_name:
                        played_names.add(card_name)
                else:
                    try:
                        game.log.append(f"AI: カードの使用に失敗しました: {msg}")
                    except Exception:
                        pass
                    # if failed due to unusable context, avoid retrying same card
                    if card_name:
                        played_names.add(card_name)
            except Exception as e:
                try:
                    game.log.append(f"AI: カード使用中に例外が発生しました: {e}")
                except Exception:
                    pass

            attempts += 1

        return made_any

    # (animation rendering moved to draw_panel where board metrics are available)
    # Compute candidates BEFORE ai_consider_play_card() so it can reference them
    candidates = []  # list of (piece, move)
    for p in chess.pieces:
        if p.color != 'black':
            continue
        # Use wrapper to respect freeze/blocked tiles; ignore self-check here and handle per difficulty
        v = get_valid_moves(p, ignore_check=True)
        for mv in v:
            candidates.append((p, mv))

    # attempt to play a card (may mutate ai state)
    try:
        prev_turn_active = getattr(game, 'turn_active', False)
        # allow AI to play via game.play_card_for which requires turn_active
        game.turn_active = True
        ai_consider_play_card()
        game.turn_active = prev_turn_active
    except Exception as e:
        try:
            game.turn_active = prev_turn_active
        except Exception:
            pass
        # Log the exception for debugging
        try:
            game.log.append(f"AI: カード使用検討中にエラーが発生しました: {e}")
        except Exception:
            pass

    if not candidates:
        game.log.append('AI: 動ける手がありません')
        return

    # Difficulty 1: fully random
    if CPU_DIFFICULTY == 1:
        sel = random.choice(candidates)

    # Difficulty 2: avoid moves that leave black in check; otherwise random
    elif CPU_DIFFICULTY == 2:
        safe = []
        for p, mv in candidates:
            newp = simulate_move(p, mv[0], mv[1])
            if not is_in_check(newp, 'black'):
                safe.append((p, mv))
        sel = random.choice(safe) if safe else random.choice(candidates)

    # Difficulty 3: prefer captures (highest piece value captured)
    elif CPU_DIFFICULTY == 3:
        best = []
        best_score = -999
        values = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        for p, mv in candidates:
            tgt = chess.get_piece_at(mv[0], mv[1])
            score = values.get(tgt.name,0) if tgt else 0
            if score > best_score:
                best_score = score
                best = [(p,mv)]
            elif score == best_score:
                best.append((p,mv))
        sel = random.choice(best)

    # Difficulty 4: prefer captures, avoid self-check, and favor higher-value captures
    else:
        best = []
        best_score = -999
        values = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':100}
        for p, mv in candidates:
            newp = simulate_move(p, mv[0], mv[1])
            if is_in_check(newp, 'black'):
                continue
            tgt = chess.get_piece_at(mv[0], mv[1])
            score = values.get(tgt.name,0) if tgt else 0
            if score > best_score:
                best_score = score
                best = [(p,mv)]
            elif score == best_score:
                best.append((p,mv))
        sel = random.choice(best) if best else random.choice(candidates)

    p, mv = sel
    # 移動元を記録してから適用（パルスと矢印描画のため）
    try:
        src_r = getattr(p, 'row', None)
        src_c = getattr(p, 'col', None)
    except Exception:
        src_r = src_c = None
    apply_move(p, mv[0], mv[1])
    # AIの最初の駒移動に区切り線を追加
    if not getattr(game, '_ai_turn_sep_added', False):
        game.log.append("─── AIのターン ───")
        game._ai_turn_sep_added = True
        logger.debug("AIターン開始ログ追加: _ai_turn_sep_added=%s", getattr(game, '_ai_turn_sep_added', None))
    log_msg = f"AI({CPU_DIFFICULTY}): {p.name} を {mv} に移動"
    game.log.append(log_msg)
    logger.debug("AI駒移動ログ追加: %s, master_log size=%d", log_msg, len(master_log))
    # 移動アニメーションを開始する（移動元: 赤パルス、移動先: 青パルス、両者を矢印で結ぶ）
    try:
        ai_move_anim['active'] = True
        ai_move_anim['from_row'] = src_r
        ai_move_anim['from_col'] = src_c
        ai_move_anim['row'] = mv[0]
        ai_move_anim['col'] = mv[1]
        ai_move_anim['start'] = _ct_time.time()
        # アニメ時間を延長（元の2.4秒を2倍して4.8秒に設定）
        try:
            scale = animation_mod.get_anim_time_scale() if animation_mod and hasattr(animation_mod, 'get_anim_time_scale') else 1.0
        except Exception:
            scale = 1.0
        ai_move_anim['duration'] = base_ai_move_duration * scale
        try:
            logger.debug("ai_move_anim set duration -> base=%s scale=%s duration=%s", base_ai_move_duration, scale, ai_move_anim.get('duration'))
        except Exception:
            pass
        try:
            _debug_report_anim_scales('after_ai_move_anim_set')
        except Exception:
            pass
        # ゴースト駒情報: 移動前の駒を一ターン分表示するために保存
        try:
            ai_move_anim['ghost_name'] = getattr(p, 'name', None)
            ai_move_anim['ghost_color'] = getattr(p, 'color', None)
            ai_move_anim['ghost_turn'] = getattr(game, 'turn', None)
        except Exception:
            ai_move_anim['ghost_name'] = None
            ai_move_anim['ghost_color'] = None
            ai_move_anim['ghost_turn'] = None
    except Exception:
        pass
    
    # AI自動昇格処理: 昇格が保留中の場合、自動的にクイーンに昇格させる
    if chess.promotion_pending is not None:
        try:
            promoted_piece = chess.promotion_pending.get('piece')
            piece_color = chess.promotion_pending.get('color')
            if promoted_piece is not None and piece_color == 'black':
                # AIは基本的にクイーンに昇格（難易度によって選択を変えることも可能）
                promotion_choice = 'Q'
                if CPU_DIFFICULTY >= 3:
                    # 高難易度では状況に応じて最適な駒を選択
                    # 簡易判定: ナイトが有効な場合もあるが、通常はクイーンが最善
                    promotion_choice = 'Q'
                
                promoted_piece.name = promotion_choice
                game.log.append(f"AI: ポーンを{promotion_choice}に昇格させました。")
                chess.promotion_pending = None
        except Exception as e:
            # エラーが発生した場合でもpendingをクリア
            chess.promotion_pending = None
            game.log.append(f"AI昇格処理エラー: {e}")
    
    # consume AI jump flag or extra moves
    try:
        # Prefer game-level flag if present (set by card_core), fallback to module-level
        if getattr(game, 'ai_next_move_can_jump', globals().get('ai_next_move_can_jump', False)):
            # consumed for one move
            try:
                game.ai_next_move_can_jump = False
            except Exception:
                pass
            try:
                ai_next_move_can_jump = False
            except Exception:
                pass
    except Exception:
        pass

# initialize pieces (module already initializes on import)


HELP_LINES = [
    "[T] 次のターン開始",
    "[1-7] カード使用",
    "[D] 保留中: 捨て札確定",
    "[L] ログ表示切替",
    "[G] 墓地表示切替",
    "[H] 相手の手札表示",
    # "[F8] 反撃チェック直前局面にジャンプ (DEBUG)",
    # "[F9] 同時チェック開始局面にジャンプ (DEBUG)",
    "[クリック] カード拡大",
    "[Esc] 終了",
]


def draw_panel():
    global game_over, game_over_winner
    # 背景画像があればそれを描画し、なければ従来の塗りつぶしを行う
    global log_toggle_rect, play_bg_img, play_bg_surf
    play_bg_img, play_bg_surf = draw_background(screen, W, H, IMG_DIR, PLAY_BG_FILENAME, play_bg_img, play_bg_surf)

    # Refresh display size (handles SCALED/SDL window differences) and then compute layout
    _refresh_display_size_from_pygame()
    # レイアウト設定: 左側基本情報、右側チェス盤
    layout = compute_layout(W, H)
    left_panel_width = layout['left_panel_width']
    left_margin = layout['left_margin']
    top_margin = layout['board_area_top']

    # 基本情報の配置（左側）
    info_x = left_margin
    info_y = top_margin
    line_height = 35
    # 左パネルの太字表示に合わせて縦間隔を少し広げる
    left_line_step = 44
    
    # ターン数
    draw_text(screen, f"ターン: {game.turn}", info_x, info_y, bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # PP
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", info_x, info_y, bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    # 簡易エフェクト表示: 次に発動する特別アクションを左パネルに表示
    # 表記ルール: 「次：飛越可」「次：追加行動×n」
    if getattr(game.player, 'next_move_can_jump', False):
        draw_text(screen, "次：飛越可", info_x, info_y, (10, 40, 180), scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    # 迅雷効果の表示（player_consecutive_turnsを使用）
    consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    if consecutive_turns > 0:
        info_y += 6
        label = "次：追加行動" if consecutive_turns == 1 else f"次：追加行動×{consecutive_turns}"
        draw_text(screen, label, info_x, info_y, (10, 120, 10), scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    
    # 鉄壁効果の表示（1回限りの防御）
    player_ironwall_show = False
    try:
        player_ironwall_show = getattr(game, 'ironwall_showing', {}).get('white', False) or getattr(game.player, 'iron_wall_active', False)
    except Exception:
        player_ironwall_show = getattr(game.player, 'iron_wall_active', False)
    if player_ironwall_show:
        info_y += 6
        draw_text(screen, "🛡 鉄壁：敵の妨害を防御", info_x, info_y, (200, 80, 0), bold=True, scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    
    # 鉄壁保護（UI表示を削除）
    info_y += left_line_step
    
    # 山札
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", info_x, info_y, (40,40,90), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 墓地表示（クリック可能領域として矩形を保存）
    grave_text = f"墓地: {len(game.player.graveyard)}枚"
    global grave_label_rect
    grave_label_rect = draw_text(screen, grave_text, info_x, info_y, (90,40,40), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 相手の手札表示（クリック可能領域として矩形を保存）
    opponent_hand_text = f"相手の手札: {get_opponent_hand_count()}枚"
    global opponent_hand_rect
    opponent_hand_rect = draw_text(screen, opponent_hand_text, info_x, info_y, (100,50,100), bold=True, letter_spacing=1, scale=layout.get('scale', 1.0))
    info_y += left_line_step
    
    # 相手（AI）の鉄壁効果の表示
    ai_has_ironwall_active = False
    ai_has_ironwall_protection = False
    try:
        # AI player の iron_wall_active を確認
        if hasattr(game, 'ai_player'):
            ai_has_ironwall_active = getattr(game.ai_player, 'iron_wall_active', False)
        # game レベルのフラグも確認
        if not ai_has_ironwall_active:
            ai_has_ironwall_active = getattr(game, 'ai_iron_wall_active', False)
        # AI の保護ターン数を確認
        ai_has_ironwall_protection = getattr(game, 'ai_ironwall_protection_turns', 0) > 0
    except Exception:
        pass
    
    try:
        ai_ironwall_show = getattr(game, 'ironwall_showing', {}).get('black', False) or ai_has_ironwall_active
    except Exception:
        ai_ironwall_show = ai_has_ironwall_active
    if ai_ironwall_show:
        draw_text(screen, "敵🛡 鉄壁：次の効果を防御", info_x, info_y, (200, 80, 0), bold=True, scale=layout.get('scale', 1.0))
        info_y += left_line_step - 6
    
    # ※AIの「1ターン保護」表示は不要のため省略
    
    if ai_has_ironwall_active or ai_has_ironwall_protection:
        info_y += 10  # 区切り用の余白

    # マウスでも押せる『ターン開始(T)』ボタンを左パネルに配置
    global start_turn_rect
    btn_w, btn_h = 160, 36
    start_turn_rect = pygame.Rect(info_x, info_y, btn_w, btn_h)
    # 押下可否に応じて色分け
    can_start = (getattr(game, 'pending', None) is None) and (not getattr(game, 'turn_active', False)) and (chess_current_turn == 'white') and (not cpu_wait) and (not game_over)
    bg_col = (60, 140, 220) if can_start else (140, 140, 140)
    pygame.draw.rect(screen, bg_col, start_turn_rect)
    pygame.draw.rect(screen, (255,255,255), start_turn_rect, 2)
    # Scale the button label so it follows the UI scale used on the right-side rendering
    ui_scale = layout.get('scale', 1.0)
    try:
        lab_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", max(12, int(FONT.get_height() * ui_scale)), bold=True)
        lab = lab_font.render("バトル開始 (T)", True, (255,255,255))
        screen.blit(lab, (start_turn_rect.x + (btn_w - lab.get_width())//2, start_turn_rect.y + (btn_h - lab.get_height())//2))
    except Exception:
        lab = FONT.render("バトル開始 (T)", True, (255,255,255))
        screen.blit(lab, (start_turn_rect.x + (btn_w - lab.get_width())//2, start_turn_rect.y + (btn_h - lab.get_height())//2))
    info_y += left_line_step
    
    # 保留中表示（基本情報の下）
    if getattr(game, 'pending', None) is not None:
        info_y += line_height + 10
        label = game.pending.kind
        src = game.pending.info.get('source_card_name')
        if src:
            label = f"{src} ({label})"
        draw_text(screen, f"⚠ 保留中:", info_x, info_y, (180, 60, 0))
        info_y += 20
        draw_text(screen, label, info_x, info_y, (180, 60, 0))

    # 右パネル: ヘルプ（簡潔に） - use right panel x so help stays grouped
    help_x = layout['right_panel_x'] + 12
    help_y = layout['board_top']
    # Operation/help header (use bolder font)
    try:
        header_s = HELP_FONT.render("操作:", True, (60, 60, 100))
        screen.blit(header_s, (help_x, help_y))
    except Exception:
        draw_text(screen, "操作:", help_x, help_y, (60, 60, 100))
    # increase spacing to improve readability
    # Use slightly larger line spacing so each help item is easier to read.
    help_y += 44
    for hl in HELP_LINES:  # 全ての操作を表示
        try:
            line_s = HELP_FONT.render(hl, True, (30, 30, 90))
            screen.blit(line_s, (help_x, help_y))
        except Exception:
            draw_text(screen, hl, help_x, help_y, (30, 30, 90))
        # add more vertical gap between items for improved readability
        help_y += 40

    # チェス盤エリア: 左側パネルの右、画面上部から配置
    board_area_left = layout['central_left']
    board_area_top = layout['board_top']
    # board_size and position computed by compute_layout
    board_size = layout['board_size']
    board_area_width = board_size
    board_area_height = board_size
    square_w = board_size // 8
    square_h = square_w
    board_left = layout['board_left']
    board_top = layout['board_top']
    # use pale greenish theme similar to original design
    light = (235, 248, 240)
    dark = (200, 220, 200)
    # draw board background
    try:
        pygame.draw.rect(screen, (200, 220, 200), (board_left, board_top, board_size, board_size))
        pygame.draw.rect(screen, (120, 140, 120), (board_left, board_top, board_size, board_size), 2)
    except Exception:
        # fallback: nothing
        pass
    for rr in range(8):
        for cc in range(8):
            rrect = pygame.Rect(board_left + cc*square_w, board_top + rr*square_h, square_w, square_h)
            pygame.draw.rect(screen, light if (rr+cc)%2==0 else dark, rrect)

    # 簡易アニメーション: AIが移動させた先と移動元をパルスで表示し、矢印で結ぶ
    try:
        if ai_move_anim.get('active'):
            to_r = ai_move_anim.get('row')
            to_c = ai_move_anim.get('col')
            from_r = ai_move_anim.get('from_row')
            from_c = ai_move_anim.get('from_col')
            elapsed = _ct_time.time() - ai_move_anim.get('start', 0.0)
            dur = max(0.001, float(ai_move_anim.get('duration', 1.0)))
            if elapsed >= dur:
                ai_move_anim['active'] = False
            else:
                prog = max(0.0, min(1.0, elapsed / dur))
                # pulse 0->1->0 shape
                pulse = math.sin(prog * math.pi)
                # radius relative to square
                r0 = square_w // 2
                radius = max(2, int(r0 * (0.6 + 0.6 * pulse)))
                alpha = max(0, min(255, int(220 * (1.0 - prog))))

                # precompute source/destination top-left positions so ghost drawing
                # can reference them even if the pulse effect is disabled.
                fx = fy = sx = sy = None
                if to_r is not None and to_c is not None:
                    fx = board_left + to_c * square_w
                    fy = board_top + to_r * square_h

                # destination: blue pulse
                if to_r is not None and to_c is not None and globals().get('ai_move_pulse_enabled', True):
                    surf = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                    col_to = (40, 120, 220)  # blue
                    pygame.draw.circle(surf, (*col_to, max(24, alpha//6)), (square_w//2, square_h//2), radius)
                    pygame.draw.circle(surf, (*col_to, alpha), (square_w//2, square_h//2), radius, 3)
                    screen.blit(surf, (fx, fy))

                # source: red pulse
                if from_r is not None and from_c is not None:
                    sx = board_left + from_c * square_w
                    sy = board_top + from_r * square_h
                if from_r is not None and from_c is not None and globals().get('ai_move_pulse_enabled', True):
                    surf2 = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                    col_from = (220, 40, 40)  # red
                    pygame.draw.circle(surf2, (*col_from, max(24, alpha//6)), (square_w//2, square_h//2), radius)
                    pygame.draw.circle(surf2, (*col_from, alpha), (square_w//2, square_h//2), radius, 3)
                    screen.blit(surf2, (sx, sy))

                # ghost piece: show a translucent piece image (same shape as moved piece) at source for one turn
                if globals().get('ai_move_ghost_enabled', True):
                    try:
                        ghost_name = ai_move_anim.get('ghost_name')
                        ghost_color = ai_move_anim.get('ghost_color')
                        ghost_turn = ai_move_anim.get('ghost_turn')
                        # Show ghost while the AI animation is active OR for one full turn
                        # (i.e., while game.turn equals the saved ghost_turn). This ensures
                        # the ghost remains visible even after the quick ai animation finishes.
                        show_ghost = False
                        if ghost_name and ghost_color:
                            if ai_move_anim.get('active'):
                                show_ghost = True
                            else:
                                try:
                                    if getattr(game, 'turn', None) == ghost_turn:
                                        show_ghost = True
                                except Exception:
                                    show_ghost = False
                        if show_ghost:
                            # compute padding and image size consistent with normal piece drawing
                            padding = max(6, int(square_w * 0.08))
                            img_w = square_w - padding*2
                            img_h = square_h - padding*2
                            gp = get_piece_image_surface(ghost_name, ghost_color, (img_w, img_h))
                            if gp is not None:
                                # draw translucent copy to avoid modifying the shared
                                # piece surface (which would affect all pieces of
                                # the same type/color).
                                try:
                                    tmp = gp.copy()
                                    tmp.set_alpha(100)
                                    screen.blit(tmp, (sx + padding, sy + padding))
                                except Exception:
                                    # fallback: attempt to blit the original image
                                    # without changing its alpha to avoid global
                                    # side-effects. If that fails, silently ignore.
                                    try:
                                        screen.blit(gp, (sx + padding, sy + padding))
                                    except Exception:
                                        pass
                            else:
                                # fallback: translucent circle with piece initial
                                cx = sx + square_w//2
                                cy = sy + square_h//2
                                gsurf = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                                col = (240,240,240) if ghost_color == 'white' else (40,40,40)
                                pygame.draw.circle(gsurf, (*col, 80), (square_w//2, square_h//2), max(4, radius-2))
                                try:
                                    label = SMALL.render(ghost_name, True, (0,0,0) if ghost_color == 'white' else (255,255,255))
                                    gsurf.blit(label, (square_w//2 - label.get_width()//2, square_h//2 - label.get_height()//2))
                                except Exception:
                                    pass
                                screen.blit(gsurf, (sx, sy))
                    except Exception:
                        pass
                else:
                    # ghost disabled: nothing to draw
                    pass

                # arrow from source to destination (draw on board-relative surface)
                if from_r is not None and from_c is not None and to_r is not None and to_c is not None and globals().get('ai_move_arrow_enabled', True):
                    surf_arrow = pygame.Surface((board_size, board_size), pygame.SRCALPHA)
                    # centers relative to board surface
                    fx_c = from_c * square_w + square_w // 2
                    fy_c = from_r * square_h + square_h // 2
                    tx_c = to_c * square_w + square_w // 2
                    ty_c = to_r * square_h + square_h // 2
                    # Offset start/end so arrow does not overlap piece image.
                    padding_local = max(6, int(square_w * 0.08))
                    img_w = max(0, square_w - padding_local * 2)
                    # distance from center to piece image edge (approx)
                    center_to_edge = img_w / 2.0 + 4.0
                    dx = tx_c - fx_c
                    dy = ty_c - fy_c
                    dist = math.hypot(dx, dy)
                    if dist > 1e-6:
                        ux = dx / dist
                        uy = dy / dist
                        # ensure offsets do not cross (if very short, reduce offset)
                        max_offset = max(0.0, (dist / 2.0) - 2.0)
                        use_offset = min(center_to_edge, max_offset)
                        start_x = fx_c + ux * use_offset
                        start_y = fy_c + uy * use_offset
                        end_x = tx_c - ux * use_offset
                        end_y = ty_c - uy * use_offset
                    else:
                        start_x, start_y = fx_c, fy_c
                        end_x, end_y = tx_c, ty_c
                    # arrow: draw a shadowed/thick shaft then a clear colored shaft so arrow is obvious
                    shadow_w = max(6, square_w//10)
                    main_w = max(4, square_w//12)
                    shadow_col = (0, 0, 0, max(120, int(alpha)))
                    main_col = (220, 40, 40, 255)
                    # draw from adjusted start to end so it doesn't overlap pieces
                    pygame.draw.line(surf_arrow, shadow_col, (start_x, start_y), (end_x, end_y), shadow_w)
                    pygame.draw.line(surf_arrow, main_col, (start_x, start_y), (end_x, end_y), main_w)
                    # arrowhead (draw black outline then red fill)
                    dx = tx_c - fx_c
                    dy = ty_c - fy_c
                    dist = math.hypot(dx, dy)
                    if dist > 0:
                        ux = dx / dist
                        uy = dy / dist
                        # perpendicular
                        px = -uy
                        py = ux
                        size = min(max(8, square_w//4), int(square_w * 0.6))
                        # arrowhead base point should be at end_x/end_y (offset from tile center)
                        left = (end_x - int(ux * size) + int(px * (size//2)), end_y - int(uy * size) + int(py * (size//2)))
                        right = (end_x - int(ux * size) - int(px * (size//2)), end_y - int(uy * size) - int(py * (size//2)))
                        # outline
                        try:
                            pygame.draw.polygon(surf_arrow, (0,0,0, max(160, int(alpha))), [(end_x, end_y), left, right])
                        except Exception:
                            pass
                        pygame.draw.polygon(surf_arrow, (220,40,40,255), [(end_x, end_y), left, right])
                    # blit arrow surface at board origin
                    screen.blit(surf_arrow, (board_left, board_top))
    except Exception:
        pass

    # 駒の描画（画像があれば画像で、なければフォールバックで丸と文字）
    for p in chess.pieces:
        cell_x = board_left + p.col*square_w
        cell_y = board_top + p.row*square_h
        # leave small padding so piece images don't touch square edges
        padding = max(6, int(square_w * 0.08))
        img_w = square_w - padding*2
        img_h = square_h - padding*2
        img = get_piece_image_surface(p.name, p.color, (img_w, img_h))
        if img is not None:
            screen.blit(img, (cell_x + padding, cell_y + padding))
        else:
            cx = cell_x + square_w//2
            cy = cell_y + square_h//2
            radius = min(square_w, square_h)//2 - padding
            if p.color == 'white':
                pygame.draw.circle(screen, (250,250,250), (cx,cy), radius)
                label = SMALL.render(p.name, True, (0,0,0))
            else:
                pygame.draw.circle(screen, (40,40,40), (cx,cy), radius)
                label = SMALL.render(p.name, True, (255,255,255))
            screen.blit(label, (cx - label.get_width()//2, cy - label.get_height()//2))
    
    # 鉄壁エフェクトの視覚化（キングの周りにバリアを表示）
    try:
        # プレイヤーの鉄壁チェック（UIフラグを優先して即時表示/非表示する）
        try:
            player_has_ironwall = getattr(game, 'ironwall_showing', {}).get('white', False) or getattr(game.player, 'iron_wall_active', False) or getattr(game, 'player_ironwall_protection_turns', 0) > 0
        except Exception:
            player_has_ironwall = getattr(game.player, 'iron_wall_active', False) or getattr(game, 'player_ironwall_protection_turns', 0) > 0
        try:
            ai_has_ironwall = getattr(game, 'ironwall_showing', {}).get('black', False) or getattr(game, 'ai_iron_wall_active', False) or getattr(game, 'ai_ironwall_protection_turns', 0) > 0
        except Exception:
            ai_has_ironwall = getattr(game, 'ai_iron_wall_active', False) or getattr(game, 'ai_ironwall_protection_turns', 0) > 0
        
        if player_has_ironwall or ai_has_ironwall:
            for p in chess.pieces:
                if p.name == 'K':  # キングのみ
                    draw_barrier = False
                    barrier_color = (220, 180, 20)  # 金色
                    
                    if p.color == 'white' and player_has_ironwall:
                        draw_barrier = True
                    elif p.color == 'black' and ai_has_ironwall:
                        draw_barrier = True
                    
                    if draw_barrier:
                        cell_x = board_left + p.col * square_w
                        cell_y = board_top + p.row * square_h
                        
                        # 光るバリアエフェクト（複数の円で表現）
                        import time
                        pulse = abs(math.sin(time.time() * 3))  # パルス効果
                        
                        # 外側の大きな円
                        outer_radius = int((square_w // 2) * (0.9 + pulse * 0.1))
                        pygame.draw.circle(screen, barrier_color, 
                                         (cell_x + square_w // 2, cell_y + square_h // 2), 
                                         outer_radius, 3)
                        
                        # 内側の小さな円
                        inner_radius = int((square_w // 2) * (0.7 + pulse * 0.1))
                        alpha_surface = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                        pygame.draw.circle(alpha_surface, (*barrier_color, int(80 + pulse * 60)), 
                                         (square_w // 2, square_h // 2), inner_radius)
                        screen.blit(alpha_surface, (cell_x, cell_y))
                        
                        # 四隅に小さなシールドアイコン
                        shield_size = max(8, square_w // 8)
                        corner_offsets = [(2, 2), (square_w - shield_size - 2, 2), 
                                        (2, square_h - shield_size - 2), 
                                        (square_w - shield_size - 2, square_h - shield_size - 2)]
                        for ox, oy in corner_offsets:
                            shield_rect = pygame.Rect(cell_x + ox, cell_y + oy, shield_size, shield_size)
                            pygame.draw.rect(screen, barrier_color, shield_rect, 2)
    except Exception:
        pass

    # カード効果視覚化（封鎖マス・凍結駒のオーバーレイ）
    try:
        for (br, bc), raw in getattr(game, 'blocked_tiles', {}).items():
            # raw may be legacy int or new list of entries
            try:
                if isinstance(raw, list):
                    entries = raw
                elif isinstance(raw, dict):
                    entries = [raw]
                else:
                    entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]
            except Exception:
                entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]

            # only show overlay if any entry has turns > 0
            any_active = False
            for e in entries:
                try:
                    if int(e.get('turns', 0)) > 0:
                        any_active = True
                        break
                except Exception:
                    continue
            if not any_active:
                continue

            bx = board_left + bc * square_w
            by = board_top + br * square_h
            s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
            s.fill((200, 30, 30, 120))
            screen.blit(s, (bx, by))
            # ターン数を小さく表示 (join multiple turns if present)
            try:
                turns_text = ','.join(str(int(e.get('turns', 0))) for e in entries if int(e.get('turns', 0)) > 0)
            except Exception:
                turns_text = str(getattr(game, 'blocked_tiles_owner', {}).get((br, bc)) or '')
            ttxt = TINY.render(turns_text, True, (255,255,255))
            screen.blit(ttxt, (bx + 4, by + 4))
            # 所有者表示（白/黒の頭文字） - use legacy owner mapping for display
            owner = getattr(game, 'blocked_tiles_owner', {}).get((br, bc))
            if owner:
                ot = TINY.render(owner[0].upper(), True, (255,255,255))
                screen.blit(ot, (bx + 4, by + 18))
    except Exception:
        pass

    # 仮決定中の選択表示 (点線): target_tiles_multi の selected を赤い点線で描画
    try:
        if getattr(game, 'pending', None) is not None and game.pending.kind == 'target_tiles_multi':
            sel = game.pending.info.get('selected', [])
            tmax = game.pending.info.get('max_tiles', 3)
            for idx, (br, bc) in enumerate(sel):
                bx = board_left + bc * square_w
                by = board_top + br * square_h
                rrect = pygame.Rect(bx, by, square_w, square_h)
                draw_dashed_rect(screen, (200, 30, 30), rrect, dash=6, gap=4, width=3)
                # small tentative label at bottom-right
                try:
                    ttxt = TINY.render(f"仮{idx+1}/{tmax}", True, (200,30,30))
                    screen.blit(ttxt, (bx + square_w - ttxt.get_width() - 4, by + square_h - ttxt.get_height() - 4))
                except Exception:
                    pass
    except Exception:
        pass

    # Play heat GIF animation if active (centered on selected board square)
    try:
        # animation.pyのheat_gif_animを参照
        _heat_gif_anim = _animation_module.heat_gif_anim if _animation_module else {}
        if _heat_gif_anim.get('playing') and _heat_gif_anim.get('frames'):
            elapsed = _ct_time.time() - _heat_gif_anim.get('start_time', 0.0)
            total = _heat_gif_anim.get('total_duration', 0.0)
            frames = _heat_gif_anim.get('frames')
            durations = _heat_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                # stop animation
                _heat_gif_anim['playing'] = False
            else:
                # determine current frame by elapsed ms
                acc = 0.0
                elapsed_ms = elapsed * 1000.0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if elapsed_ms < acc:
                        idx = i
                        break
                frame = frames[idx]
                # compute position centered on target square
                pos = _heat_gif_anim.get('pos')
                if pos is not None:
                    r, c = pos
                    fx = board_left + c * square_w
                    fy = board_top + r * square_h
                    # scale animation to exactly the square size so it fits the tile
                    try:
                        fw = int(square_w)
                        fh = int(square_h)
                        f_surf = pygame.transform.smoothscale(frame, (fw, fh))
                    except Exception:
                        f_surf = frame
                    # draw aligned to the tile's top-left so it occupies the tile area
                    screen.blit(f_surf, (fx, fy))
    except Exception:
        # Don't let animation errors break UI
        pass

    # Play ice GIF animation if active (centered on target/frozen piece square)
    try:
        # animation.pyのic_gif_animを参照
        _ic_gif_anim = _animation_module.ic_gif_anim if _animation_module else {}
        if _ic_gif_anim.get('playing') and _ic_gif_anim.get('frames'):
            elapsed = _ct_time.time() - _ic_gif_anim.get('start_time', 0.0)
            total = _ic_gif_anim.get('total_duration', 0.0)
            frames = _ic_gif_anim.get('frames')
            durations = _ic_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                _ic_gif_anim['playing'] = False
            else:
                # determine current frame
                acc = 0.0
                elapsed_ms = elapsed * 1000.0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if elapsed_ms < acc:
                        idx = i
                        break
                frame = frames[idx]
                pos = _ic_gif_anim.get('pos')
                if pos is not None:
                    r, c = pos
                    # scale animation so it FITS INSIDE the tile while preserving aspect ratio
                    try:
                        fw0, fh0 = frame.get_width(), frame.get_height()
                        # compute max allowed scale to fit inside tile
                        max_w = max(1, square_w)
                        max_h = max(1, square_h)
                        # respect IC_GIF_SCALE as an upper bound but ensure not exceeding tile
                        scale_bound = IC_GIF_SCALE
                        # scale factors to fit width/height
                        sf_w = max_w / fw0
                        sf_h = max_h / fh0
                        # choose smallest to ensure fit, and do not exceed scale_bound
                        sf = min(sf_w, sf_h, scale_bound)
                        if sf <= 0:
                            sf = 1.0
                        fw = max(1, int(fw0 * sf))
                        fh = max(1, int(fh0 * sf))
                        f_surf = pygame.transform.smoothscale(frame, (fw, fh))
                    except Exception:
                        f_surf = frame
                        fw = f_surf.get_width()
                        fh = f_surf.get_height()
                    # center the scaled animation INSIDE the tile
                    fx = board_left + c * square_w + (square_w - fw) // 2
                    fy = board_top + r * square_h + (square_h - fh) // 2
                    screen.blit(f_surf, (fx, fy))
    except Exception:
        pass

    # 封鎖タイルGIFループ再生 (Image_MG.gif/Image_MG_2P.gif)
    try:
        # ensure both variants are loaded (2P may fallback to standard MG)
        _ensure_mg_gif_loaded()
        _ensure_mg_gif_2p_loaded()

        # animation.pyからmg_gif関連の変数を取得
        mg_gif_frames_cache = _animation_module.mg_gif_frames_cache if _animation_module else None
        mg_gif_2p_frames_cache = _animation_module.mg_gif_2p_frames_cache if _animation_module else None
        mg_gif_durations = _animation_module.mg_gif_durations if _animation_module else None
        mg_gif_2p_durations = _animation_module.mg_gif_2p_durations if _animation_module else None
        mg_gif_total_duration = _animation_module.mg_gif_total_duration if _animation_module else 0.0
        mg_gif_2p_total_duration = _animation_module.mg_gif_2p_total_duration if _animation_module else 0.0

        # if neither is available, skip
        if not (mg_gif_frames_cache or mg_gif_2p_frames_cache):
            raise Exception("no mg gif available")

        # We'll compute per-variant total_ms as needed
        now_ms = int(_ct_time.time() * 1000)

        for (br, bc), raw in getattr(game, 'blocked_tiles', {}).items():
            # raw may be legacy int or new list of entries
            try:
                if isinstance(raw, list):
                    entries = raw
                elif isinstance(raw, dict):
                    entries = [raw]
                else:
                    entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]
            except Exception:
                entries = [{'owner': getattr(game, 'blocked_tiles_owner', {}).get((br, bc)), 'turns': raw}]

            # only show while any turns > 0
            any_active = False
            for e in entries:
                try:
                    if int(e.get('turns', 0)) > 0:
                        any_active = True
                        break
                except Exception:
                    continue
            if not any_active:
                continue

            bx = board_left + bc * square_w
            by = board_top + br * square_h

            # select which gif variant to use based on blocked_tiles_owner (legacy first-owner)
            owner = getattr(game, 'blocked_tiles_owner', {}).get((br, bc))
            use_2p = False
            try:
                # Heuristic: if the blocked tile owner is 'white' (i.e. the tile
                # blocks white player) it's likely AI applied it; show 2P variant.
                if owner == 'white' and mg_gif_2p_frames_cache:
                    use_2p = True
            except Exception:
                use_2p = False

            frames_cache = mg_gif_2p_frames_cache if use_2p and mg_gif_2p_frames_cache else mg_gif_frames_cache
            durations = mg_gif_2p_durations if use_2p and mg_gif_2p_durations else mg_gif_durations

            if not frames_cache or not durations:
                continue

            try:
                total_ms = int(sum(durations))
            except Exception:
                total_ms = max(1, int((mg_gif_2p_total_duration if use_2p else mg_gif_total_duration) * 1000))

            # frame index by modulo looping
            if total_ms > 0:
                tmod = now_ms % total_ms
                acc = 0
                idx = 0
                for i, d in enumerate(durations):
                    acc += d
                    if tmod < acc:
                        idx = i
                        break
            else:
                idx = 0

            frame = frames_cache[idx]
            try:
                f_surf = pygame.transform.smoothscale(frame, (square_w, square_h))
            except Exception:
                f_surf = frame
            # draw on tile top-left so it covers the tile area
            screen.blit(f_surf, (bx, by))
    except Exception:
        pass

    # ターン表示テロップ（中央・1秒表示）
    try:
        if turn_telop_msg and _ct_time.time() < turn_telop_until:
            # 中央に大きめのテキストを表示（ボード内に表示）
            bs = board_size
            bx = board_left
            by = board_top
            telop_font_size = max(28, bs // 8)
            telop_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", telop_font_size, bold=True)
            telop_surf = telop_font.render(turn_telop_msg, True, (255, 255, 255))
            # drop shadow
            shadow = telop_font.render(turn_telop_msg, True, (0, 0, 0))
            tx = bx + (bs - telop_surf.get_width()) // 2
            ty = by + (bs - telop_surf.get_height()) // 2

            # 'YOUR TURN' の場合は背景を描かずテキストのみ表示する
            draw_bg = True
            try:
                if isinstance(turn_telop_msg, str) and turn_telop_msg.strip().upper() == 'YOUR TURN':
                    draw_bg = False
            except Exception:
                draw_bg = True

            if draw_bg:
                try:
                    pad_x = max(10, telop_font_size // 5)
                    pad_y = max(6, telop_font_size // 8)
                    bxx = tx - pad_x
                    byy = ty - pad_y
                    bbw = telop_surf.get_width() + pad_x * 2
                    bbh = telop_surf.get_height() + pad_y * 2
                    bg = pygame.Surface((bbw, bbh))
                    bg.fill((28, 28, 28))
                    screen.blit(bg, (bxx, byy))
                    pygame.draw.rect(screen, (220, 180, 60), (bxx, byy, bbw, bbh), 2)
                except Exception:
                    pass

            # 影と文字
            try:
                screen.blit(shadow, (tx + 3, ty + 3))
            except Exception:
                pass
            try:
                screen.blit(telop_surf, (tx, ty))
            except Exception:
                pass
    except Exception:
        pass

    # 短時間表示用の警告（ログに加えて画面にも0.5秒表示）
    try:
        if notice_msg and _ct_time.time() < notice_until:
            # small semi-transparent box near top-center of board
            box_w = min(500, board_size - 40)
            notice_font_size = max(16, board_size // 24)
            notice_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", notice_font_size, bold=True)
            notice_surf = notice_font.render(notice_msg, True, (255, 230, 180))
            shadow = notice_font.render(notice_msg, True, (0,0,0))
            bx = board_left + (board_size - notice_surf.get_width()) // 2
            by = board_top + 8
            # 背景ボックスは常に不透明にして視認性を確保
            try:
                bw = notice_surf.get_width() + 20
                bh = notice_surf.get_height() + 12
                tmp = pygame.Surface((bw, bh))
                tmp.fill((28, 28, 28))
                screen.blit(tmp, (bx-10, by-6))
                pygame.draw.rect(screen, (220, 180, 60), (bx-10, by-6, bw, bh), 2)
                screen.blit(shadow, (bx+2, by+2))
            except Exception:
                try:
                    pygame.draw.rect(screen, (28,28,28), (bx-10, by-6, notice_surf.get_width()+20, notice_surf.get_height()+12))
                    pygame.draw.rect(screen, (220,180,60), (bx-10, by-6, notice_surf.get_width()+20, notice_surf.get_height()+12), 2)
                    screen.blit(shadow, (bx+2, by+2))
                except Exception:
                    pass
            screen.blit(notice_surf, (bx, by))
    except Exception:
        pass

    try:
        for p in chess.pieces:
            # consider both the game.frozen_pieces mapping and a transient
            # per-piece attribute that may be set when AI applies 凍結
            try:
                frozen_map = getattr(game, 'frozen_pieces', {})
                is_frozen = (id(p) in frozen_map and frozen_map.get(id(p), 0) > 0) or (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0)
            except Exception:
                is_frozen = id(p) in getattr(game, 'frozen_pieces', {})
            if is_frozen:
                fx = board_left + p.col * square_w
                fy = board_top + p.row * square_h
                s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
                s.fill((30, 120, 200, 90))
                screen.blit(s, (fx, fy))
                # 凍結マーク
                mark = SMALL.render('凍', True, (255,255,255))
                screen.blit(mark, (fx + square_w - mark.get_width() - 4, fy + 4))
    except Exception:
        pass

    # ハイライト（選択可能な移動先）- Chess Main準拠の色分け
    if selected_piece:
        # 反撃チェック（迅雷時のみ許可）を色分けするための事前判定
        try:
            sp_color = getattr(selected_piece, 'color', selected_piece.get('color'))
        except Exception:
            sp_color = 'white'
        try:
            pre_self_in_check = is_in_check(chess.pieces, sp_color)
        except Exception:
            pre_self_in_check = False
        try:
            if sp_color == 'white':
                lightning_active_for_highlight = getattr(game, 'player_consecutive_turns', 0) > 0
            else:
                lightning_active_for_highlight = globals().get('ai_consecutive_turns', 0) > 0
        except Exception:
            lightning_active_for_highlight = False
        # [DEBUG] カード直後のみ許可モードのゲート（ハイライト用）
        try:
            debug_card_gate_hl = globals().get('DEBUG_COUNTER_CHECK_CARD_MODE', False) and getattr(game, '_debug_last_action_was_card', False)
        except Exception:
            debug_card_gate_hl = False
        for hr, hc in highlight_squares:
            hrect = pygame.Rect(board_left + hc*square_w, board_top + hr*square_h, square_w, square_h)
            
            # 移動先の色分け判定
            is_en_passant = False
            is_castling = False
            is_checkmate = False
            is_counter_check = False
            
            # アンパサン判定
            if selected_piece.name == 'P' and chess.en_passant_target is not None:
                if (hr, hc) == chess.en_passant_target:
                    if ((selected_piece.color == 'white' and selected_piece.row == 3) or
                        (selected_piece.color == 'black' and selected_piece.row == 4)):
                        is_en_passant = True
            
            # キャスリング判定
            if selected_piece.name == 'K' and abs(hc - selected_piece.col) == 2:
                is_castling = True
            
            # チェックメイト/キング捕獲判定
            target_piece = chess.get_piece_at(hr, hc)
            if target_piece and target_piece.name == 'K' and target_piece.color != selected_piece.color:
                is_checkmate = True
            else:
                # 相手を詰ませる手かどうかを判定
                temp_pieces = chess.simulate_move(selected_piece, hr, hc)
                next_turn = 'black' if selected_piece.color == 'white' else 'white'
                # 詰み判定: 相手がチェックで、合法手なし
                if any(p.name == 'K' and p.color == next_turn for p in temp_pieces):
                    # has_legal_moves_forはグローバルpiecesを使うので、一時的に使えない
                    # 代わりに手動で判定
                    is_mate = is_in_check(temp_pieces, next_turn)
                    if is_mate:
                        # 相手に合法手があるか簡易チェック
                        has_moves = False
                        for tp in temp_pieces:
                            if tp.color == next_turn:
                                moves = tp.get_valid_moves(temp_pieces)
                                for mv in moves:
                                    test = simulate_move(tp, mv[0], mv[1])
                                    if not is_in_check(test, next_turn):
                                        has_moves = True
                                        break
                            if has_moves:
                                break
                        if not has_moves:
                            is_checkmate = True
            
            # 反撃チェック判定（自駒は依然チェックだが、相手にもチェックを与える）
            # または、自分がチェック中でなくても、迅雷時に相手にチェックを与える手
            try:
                if (lightning_active_for_highlight or debug_card_gate_hl):
                    post_sim = simulate_move(selected_piece, hr, hc)
                    opp_color = 'black' if sp_color == 'white' else 'white'
                    # ケース1: 自分がチェック中で、移動後も自分チェック＋相手もチェック
                    if pre_self_in_check and is_in_check(post_sim, sp_color) and is_in_check(post_sim, opp_color):
                        is_counter_check = True
                    # ケース2: 自分がチェック中でなく、移動後に自分チェック＋相手もチェック
                    elif not pre_self_in_check and is_in_check(post_sim, sp_color) and is_in_check(post_sim, opp_color):
                        is_counter_check = True
            except Exception:
                pass

            # 色決定（Chess Main準拠＋反撃チェック=オレンジ）
            if is_checkmate:
                highlight_color = (255, 0, 0, 100)  # 赤: チェックメイト/キング捕獲
            elif is_en_passant:
                highlight_color = (0, 0, 255, 100)  # 青: アンパサン
            elif is_castling:
                highlight_color = (255, 215, 0, 100)  # 金: キャスリング
            elif is_counter_check:
                highlight_color = (255, 165, 0, 110)  # オレンジ: 反撃チェック（迅雷時）
            else:
                highlight_color = (0, 255, 0, 80)  # 緑: 通常移動
            
            s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
            s.fill(highlight_color)
            screen.blit(s, hrect.topleft)
    # 盤面の左右に太めの黒線を描画して境界を明確に（元実装に近づける）
    left_x = board_left
    right_x = board_left + 8 * square_w
    pygame.draw.rect(screen, (20,20,20), (left_x-3, board_top, 6, 8 * square_h))
    pygame.draw.rect(screen, (20,20,20), (right_x-3, board_top, 6, 8 * square_h))
    # 盤面の上下にも太めの黒線を描画（上端・下端）
    pygame.draw.rect(screen, (20,20,20), (board_left, board_top-3, 8 * square_w, 6))
    pygame.draw.rect(screen, (20,20,20), (board_left, board_top + 8 * square_h - 3, 8 * square_w, 6))
    
    # チェック中の表示（凍結・カード効果を含む）
    if not game_over:
        check_colors = []
        # 表示用には凍結駒も含めた全ての脅威を表示
        # またカード効果（迅雷の追加行動・暴風のジャンプ等）でキングを攻撃可能なら表示する
        if is_in_check_for_display(chess.pieces, 'white') or can_attack_king_with_cards(chess.pieces, 'white'):
            check_colors.append('white')
        if is_in_check_for_display(chess.pieces, 'black') or can_attack_king_with_cards(chess.pieces, 'black'):
            check_colors.append('black')

        # チェック中かつ合法手なし（詰み）なら敗北処理（『負けるわけないだろwww』自動発動を優先）
        for color in check_colors:
            if not has_legal_moves_with_cards(color):
                # 自動発動の条件を満たす場合は先に試行
                can_auto_no_lose_exists = hasattr(game, 'can_auto_no_lose')
                if not can_auto_no_lose_exists:
                    logger.debug("can_auto_no_lose is not defined")
                can_auto = can_auto_no_lose_exists and game.can_auto_no_lose(color)
                if not can_auto:
                    # 失敗理由の詳細を記録（手札・PPの状況を抜粋） - debug only
                    try:
                        pp = getattr(game.player, 'pp_current', None)
                        hand_names = [c.name for c in getattr(game.player.hand, 'cards', [])]
                        logger.debug("自動発動不可: color=%s, PP=%s, 手札=%s", color, pp, hand_names)
                    except Exception:
                        logger.debug("自動発動不可: color=%s 詳細取得に失敗", color)
                
                auto_triggered = False
                if can_auto and hasattr(game, 'auto_trigger_no_lose'):
                    if game.auto_trigger_no_lose(color):
                        who = '白' if color == 'white' else '黒'
                        game.log.append(f"{who}は『負けるわけないだろwww』を自動発動。PP3と『摂取』を消費し、盤面のみ初期化します。")
                        # 自動発動成功時はゲームオーバーにせず、次の描画サイクルでpending処理に委ねる
                        auto_triggered = True
                    else:
                        logger.debug("auto_trigger_no_lose returned False for color=%s", color)
                
                # 自動発動に成功しなかった場合のみゲームオーバー
                if not auto_triggered:
                    game_over = True
                    game_over_winner = 'black' if color == 'white' else 'white'
                    who = '白' if color == 'white' else '黒'
                    result_msg = "YOU LOSE！黒の勝利！" if color == 'white' else "YOU WIN！白の勝利！"
                    game.log.append(f"{who}はチェックメイト！{result_msg}")
                    # ゲームオーバー時は昇格処理をクリア
                    chess.promotion_pending = None
                    # チェックメイト判定は一度だけ行う
                    break

        if check_colors:
            # チェック状態の変化を追跡
            if not hasattr(draw_panel, "last_check_colors"):
                draw_panel.last_check_colors = []
            if check_colors != draw_panel.last_check_colors:
                draw_panel.last_check_colors = check_colors.copy()

            # 左パネルの中央付近に表示（手札と被らない位置）
            check_x = left_margin + 10
            check_y = H // 2 - 50

            for idx, color in enumerate(draw_panel.last_check_colors):
                msg = f"{'白' if color == 'white' else '黒'}チェック中"
                check_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
                check_text = check_font.render(msg, True, (255, 165, 0))

                text_w = check_text.get_width()
                text_h = check_text.get_height()

                # 背景を半透明の黒で塗りつぶして視認性を向上
                bg_rect = pygame.Rect(check_x - 5, check_y - 3 + idx * (text_h + 10), text_w + 10, text_h + 6)
                try:
                    tmp = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                    tmp.fill((0, 0, 0, 40 if not get_ui_effects_enabled() else 160))
                    screen.blit(tmp, (bg_rect.x, bg_rect.y))
                except Exception:
                    pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(screen, (255, 165, 0), bg_rect, 2)
                screen.blit(check_text, (check_x, check_y + idx * (text_h + 10)))

    # 右側エリア: ログ（切替式、スクロール対応）
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    if show_log:
        # Preferred log panel sits to the right of the board when enough room exists.
        # Make the preferred width a bit larger so normal windows get a readable panel.
        preferred_w = max(360, min(520, layout.get('right_panel_width', 360)))
        # If this is a scaled / fullscreen (拡大画面) UI, allow a wider preferred width
        ui_scale = layout.get('scale', 1.0)
        if ui_scale > 1.15:
            # only increase preferred_w for expanded screens; keep standard screens unchanged
            # grow the log to use at least ~75% of the right-side available area (without overlapping the board)
            gap_exp = int(28 * ui_scale)
            right_margin_exp = 12
            max_right_space = max(0, W - (board_right + gap_exp) - right_margin_exp)
            # safety subtract to avoid 1px overlaps
            safety = 8
            if max_right_space > 200:
                # target to occupy ~75% of the available right-side space, clamped so it never exceeds the space
                target75 = int(max_right_space * 0.75)
                use_w = max(target75, 420)
                use_w = min(use_w, max(0, max_right_space - safety))
                preferred_w = max(preferred_w, use_w)
            else:
                # if not much room, fall back to the scaled target but don't change standard behavior
                preferred_w = max(preferred_w, min(912, int(520 * ui_scale * 1.2)))
        board_right = board_area_left + board_area_width
        scale = layout.get('scale', 1.0)
        gap = int(28 * scale)
        right_margin = 12
        available_right_space = W - (board_right + gap) - right_margin

        # Default: try to place on the right with preferred width
        if available_right_space >= preferred_w:
            log_panel_left = board_right + gap
            log_panel_top = board_area_top
            log_panel_width = preferred_w
            log_panel_height = min(board_area_height, max(220, H - log_panel_top - 24))
        else:
            # Not enough horizontal room: attempt to place below the board between board and hand
            space_below_board = max(0, layout.get('card_area_top', H) - (board_top + board_size))
            if space_below_board >= 160:
                log_panel_left = layout['left_margin']
                log_panel_top = board_top + board_size + int(12 * scale)
                log_panel_width = min(preferred_w, W - 2 * layout['left_margin'] - 24)
                log_panel_height = min(space_below_board - 12, 420)
            else:
                # fallback: try to sit to the right but shrink width to the available space
                use_w = max(220, min(preferred_w, available_right_space)) if available_right_space > 0 else 0
                if use_w > 0 and (board_right + gap + use_w + right_margin) <= W:
                    log_panel_left = board_right + gap
                    log_panel_top = board_area_top
                    log_panel_width = use_w
                    log_panel_height = min(board_area_height, max(200, H - log_panel_top - 24))
                else:
                    # last resort: force fit the panel to the far right and reduce width to avoid overlap
                    forced_w = max(200, W - board_right - gap - right_margin)
                    if forced_w >= 200:
                        log_panel_left = board_right + gap
                        log_panel_top = board_area_top
                        log_panel_width = forced_w
                        log_panel_height = min(board_area_height, max(180, H - log_panel_top - 24))
                    else:
                        # give up on right side, place below the board full-width within margins
                        log_panel_left = layout['left_margin']
                        log_panel_top = board_top + board_size + int(12 * scale)
                        log_panel_width = min(preferred_w, W - 2 * layout['left_margin'] - 24)
                        log_panel_height = min(space_below_board - 12 if 'space_below_board' in locals() else 200, 420)

        # clamp to absolute maxima so huge monitors don't create gigantic panels
        MAX_LOG_W = 640
        MAX_LOG_H = 600
        log_panel_width = min(log_panel_width, MAX_LOG_W)
        log_panel_height = min(log_panel_height, MAX_LOG_H)

        # Ensure the panel is nudged right and fully visible (avoid overlapping board and prevent clipping).
        # Increase the desired gap so the log is pushed farther right (as the user requested),
        # then shrink the panel a bit so it can sit as far right as possible without being cut off.
        # push a bit more to the right as requested (try to keep the current width)
        desired_right_gap = int(112 * layout.get('scale', 1.0))
        right_margin = 12
        min_gap_to_board = int(8 * layout.get('scale', 1.0))
        desired_left = max(log_panel_left, board_right + desired_right_gap)

        # Prefer moving the panel to desired_left WITHOUT shrinking width
        if desired_left + log_panel_width + right_margin <= W:
            log_panel_left = desired_left
        else:
            # Can't place at desired_left with current width. Try to push it as far right as possible while keeping width.
            max_left = W - log_panel_width - right_margin
            if max_left >= board_right + min_gap_to_board:
                # push to the far right but keep width
                log_panel_left = max_left
            else:
                # As a last resort (very narrow window), allow minimal shrinking so it can sit at desired_left
                shrink_w = W - desired_left - right_margin
                if shrink_w >= min_gap_to_board and shrink_w >= 180:
                    log_panel_width = shrink_w
                    log_panel_left = desired_left
                else:
                    # fallback: place at max_left (may overlap slightly if window is too narrow)
                    log_panel_left = max(layout['left_margin'], max_left)

        # Final safety clamp to ensure we never draw off-screen
        if log_panel_left + log_panel_width + right_margin > W:
            log_panel_left = max(layout['left_margin'], W - log_panel_width - right_margin)

        # Force the log panel to be flush-right: try to keep its width but if that would overlap
        # shrink the width until it can be right-aligned without covering the board.
        try:
            scale = layout.get('scale', 1.0)
            right_margin = 12
            min_gap = int(8 * scale)
            # target fixed width (a bit narrower for safety)
            # increase fixed width on expanded/fullscreen to make the log bigger there only
            if layout.get('scale', 1.0) > 1.15:
                # larger fixed width for expanded screens; try to use most of the right space
                gap_exp = int(28 * layout.get('scale', 1.0))
                right_margin_exp = 12
                max_right_space = max(0, W - (board_right + gap_exp) - right_margin_exp)
                if max_right_space > 360:
                    # use ~75% of right space for fixed width, leave a small safety gap
                    FIXED_LOG_W = int(max_right_space * 0.75)
                    FIXED_LOG_W = max(FIXED_LOG_W, 420)
                    FIXED_LOG_W = min(FIXED_LOG_W, max_right_space - 8)
                else:
                    FIXED_LOG_W = int(520 * 1.2)
            else:
                FIXED_LOG_W = 300
            target_w = min(log_panel_width, FIXED_LOG_W)
            # maximum width allowed so the panel's left edge is at least `min_gap` from the board
            max_allowed_w = W - (board_right + min_gap) - right_margin
            if max_allowed_w < 20:
                max_allowed_w = 20
            # choose the smaller of target and allowed
            final_w = min(target_w, max_allowed_w)
            # ensure final width is at least a small readable minimum when possible
            if max_allowed_w >= 160:
                final_w = max(160, final_w)
            else:
                final_w = max(20, final_w)

            # set width and right-align (flush to right_margin)
            log_panel_width = int(final_w)
            log_panel_left = max(layout['left_margin'], W - log_panel_width - right_margin)
        except Exception:
            pass

        # ログパネル背景
        pygame.draw.rect(screen, (250, 250, 255),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height))
        pygame.draw.rect(screen, (100, 100, 120),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height), 2)

        # タイトル（クリックで閉じる）
        # 上部余白を確保して、見出し／ヒントに被らないようにする
        try:
            top_line_h = FONT.get_height() if 'FONT' in globals() and FONT is not None else 20
        except Exception:
            top_line_h = 20
        log_toggle_rect = draw_text(screen, "ログ履歴  [L]閉じる", log_panel_left + 10, log_panel_top + 8, (60, 60, 100))
        # 見出しのすぐ下にスクロールのヒントを表示（上下に余白を確保）
        draw_text(screen, "↑ ↓  /  ホイールでスクロール", log_panel_left + 10, log_panel_top + 32, (100, 100, 120))



        # ログの折り返し処理 — ビューに応じてフィルタを行い、各行に種類を付与（AI / player）して後続描画で差別化
        def _is_piece_line(s):
            """駒の移動に関するログかどうかを判定
            
            「移動」「飛び越」を含むログのみを駒行として判定
            ただし、カード行として判定されるログは除外
            """
            try:
                ss = str(s)
                # まず、カード行かどうかをチェック
                if _is_card_line(ss):
                    # 例外: 迅雷の追加移動のみ許可
                    if '迅雷' in ss and '移動' in ss:
                        return True
                    return False
                # 駒移動の典型的なパターン
                _piece_re = re.compile(r"移動|飛び越|→|->", re.UNICODE)
                return bool(_piece_re.search(ss))
            except Exception:
                return False

        def _is_card_line(s):
            """カード関連のログかどうかを判定（ギミックカード効果を含む）
            
            優先順位:
            1. 迅雷の追加移動は駒行として扱う（False返却）
            2. ギミックカード効果は全てカード行として扱う（True返却）
            """
            try:
                ss = str(s)
                # 迅雷の追加移動ログは駒ビューに表示するため、カード行として扱わない
                if '迅雷' in ss and '移動' in ss:
                    return False
                
                # ギミックカード名を含む場合は全てカード行
                gimmick_cards = ['氷結', '灼熱', '暴風', '迅雷', '鉄壁', '蘇生', '2ドロー', '3ドロー', '摂取', '錬成', '墓地ルーレット', '負けるわけないだろ']
                for card in gimmick_cards:
                    if card in ss:
                        return True
                
                # カード関連のキーワード
                card_keywords = ['『', 'カード', 'ドロー', '使用', '墓地', 'ギミック', '封鎖', '凍結', '効果', '適用', '解除', 'マスの封鎖', 'で封鎖マス', 'を凍結', 'ターン凍結']
                for kw in card_keywords:
                    if kw in ss:
                        return True
                
                return False
            except Exception:
                return False

        # Determine active view: prefer the canonical package module `ui.overlay`
        # (this is the module whose logger emits the set_log_view INFO messages).
        # Fallback order: importlib('ui.overlay') -> importlib('c.c.b.ui.overlay') -> overlay variable -> 'detail'
        try:
            import importlib
            active_view = 'detail'
            tried = []
            try:
                mod = importlib.import_module('ui.overlay')
                tried.append(('ui.overlay', id(mod)))
                if hasattr(mod, 'get_log_view'):
                    av = mod.get_log_view()
                    # print(f"[cardgame-debug-src] ui.overlay (id={id(mod)}) -> {av}")
                    active_view = av
                else:
                    mod = None
            except Exception:
                mod = None

            if mod is None:
                try:
                    mod2 = importlib.import_module('c.c.b.ui.overlay')
                    tried.append(('c.c.b.ui.overlay', id(mod2)))
                    if hasattr(mod2, 'get_log_view'):
                        av = mod2.get_log_view()
                        # print(f"[cardgame-debug-src] c.c.b.ui.overlay (id={id(mod2)}) -> {av}")
                        active_view = av
                    else:
                        mod2 = None
                except Exception:
                    mod2 = None

            # final fallback: the local `overlay` variable if it exposes get_log_view
            if (mod is None) and (mod2 is None):
                if 'overlay' in globals() and hasattr(overlay, 'get_log_view'):
                    try:
                        av = overlay.get_log_view()
                        # print(f"[cardgame-debug-src] overlay_var ({getattr(overlay,'__class__', overlay)}) id={id(overlay)} -> {av}")
                        active_view = av
                    except Exception:
                        pass
                # else:
                    # print("[cardgame-debug-src] no overlay module found; using fallback 'detail'")
        except Exception:
            active_view = 'detail'

        if active_view not in ('detail', 'piece', 'card'):
            active_view = 'detail'

        # Use the chronological master_log for all views so entries are shown
        # in the order they occurred instead of being grouped by source lists.
        try:
            # master_log is list of tuples (seq:int, source:str, msg:str)
            timeline = list(master_log) if isinstance(master_log, list) else []
            timeline.sort(key=lambda t: t[0])  # ensure chronological order
        except Exception:
            timeline = []

        if active_view == 'detail':
            # 詳細ビュー: 全てのログを時系列で表示
            source_lines = [t[2] for t in timeline]
        elif active_view == 'piece':
            # 駒ビュー: マスタータイムラインから駒移動に関係する行のみ時系列で抽出
            source_lines = [t[2] for t in timeline if _is_piece_line(t[2]) and (not _is_card_line(t[2]))]
        else:  # 'card'
            source_lines = [t[2] for t in timeline if _is_card_line(t[2])]

        # Debug: 描画ルートで現在のビューとフィルタ結果を端末に出力（診断用の一時出力）
        # try:
        #     sample = source_lines[:3]
        #     print(f"[cardgame-debug] active_view={active_view} source_lines={len(source_lines)} sample={sample}")
        # except Exception:
        #     pass

        wrapped_lines = []  # list of (text_line, kind, piece_letter, is_first_line) where kind in ('ai','player','separator')
        max_log_width = max(40, log_panel_width - 110)
        _ai_re = re.compile(r"^\s*AI(?=$|[:：\s\(])", re.IGNORECASE)
        # ターン区切り線の判定用正規表現
        _separator_re = re.compile(r"^\s*───+.*───+\s*$")
        # piece letter detection (e.g. 'P','N','B','R','Q','K')
        _piece_letter_re = re.compile(r"\b([KQRBNP])\b", re.IGNORECASE)
        for line in source_lines:
            try:
                sline = str(line)
                # ターン区切り線かどうかを判定
                if _separator_re.match(sline):
                    kind = 'separator'
                elif _ai_re.match(sline):
                    kind = 'ai'
                else:
                    kind = 'player'
            except Exception:
                sline = str(line)
                kind = 'player'
            # detect piece initial in the log line
            pl_match = _piece_letter_re.search(sline)
            piece_letter = pl_match.group(1).upper() if pl_match else None
            # remove the piece letter from the displayed text so the icon
            # isn't duplicated. Prefer removing when followed by 'を', space,
            # punctuation, or line end; fallback to removing the first match.
            display_sline = sline
            if piece_letter:
                try:
                    pl = re.escape(piece_letter)
                    m = re.search(rf"{pl}(?=を|\s|[:：,。.\)\(]|$)", sline, re.IGNORECASE)
                    if m:
                        display_sline = sline[:m.start()] + sline[m.end():]
                    else:
                        display_sline = re.sub(pl, '', sline, count=1, flags=re.IGNORECASE)
                    display_sline = display_sline.strip()
                except Exception:
                    display_sline = sline

            # ターン区切り線は折り返さず1行で扱う
            if kind == 'separator':
                wrapped_lines.append((display_sline, kind, piece_letter, True))
            else:
                wrapped = wrap_text(display_sline, max_log_width)
                for idx, wline in enumerate(wrapped):
                    is_first = (idx == 0)
                    wrapped_lines.append((wline, kind, piece_letter, is_first))

        # スクロールオフセットの範囲制限
        global log_scroll_offset
        # 行高さは現在のフォントから取得し、各文章ごとに1行分の余白を入れる
        line_h = FONT.get_height()
        # 表示行のステップはテキスト行 + 空行分（＝行高 * 2）
        line_step = line_h * 2
        # 下部に余白を設けて見やすくする（最後の行が枠にくっつかないように）
        bottom_padding_px = 28  # ここを調整すると余白サイズを変更できます
        max_lines_visible = max(0, (log_panel_height - 50 - bottom_padding_px) // line_step)
        total_wrapped = len(wrapped_lines)
        max_scroll = max(0, total_wrapped - max_lines_visible)
        log_scroll_offset = max(0, min(log_scroll_offset, max_scroll))
        # グローバル変数に保存（スクロールバードラッグ処理で使用）
        global _max_scroll
        _max_scroll = max_scroll

        # 表示範囲を計算（最新が下）
        if total_wrapped <= max_lines_visible:
            visible_lines = wrapped_lines
        else:
            start_idx = total_wrapped - max_lines_visible - log_scroll_offset
            start_idx = max(0, start_idx)
            visible_lines = wrapped_lines[start_idx:start_idx + max_lines_visible]

        # ログ描画開始位置（見出しとヒントの下に余白を確保）
        # overlay.py と揃えるため top_line_h を考慮する
        log_y = log_panel_top + 56 + top_line_h
        # reduce horizontal padding so more space is available for text
        pad_x = 6
        pad_y = 4
        # 診断用フラッシュ: モジュール側で記録された直近のビュー切替情報があれば表示
        try:
            try:
                from ui import overlay as _ov
            except Exception:
                import importlib
                _ov = importlib.import_module('c.c.b.ui.overlay') if 'c.c.b.ui.overlay' in sys.modules or True else None
            if _ov is not None:
                try:
                    _last_view_change_time = getattr(_ov, '_last_view_change_time', None)
                    _last_view_change_name = getattr(_ov, '_last_view_change_name', None)
                    if _last_view_change_name and _last_view_change_time and (_ct_time.time() - _last_view_change_time) < 1.0:
                        flash_label = {'detail': '詳細', 'piece': '駒', 'card': 'カード'}.get(_last_view_change_name, _last_view_change_name)
                        try:
                            flash_font = HELP_FONT if HELP_FONT else pygame.font.SysFont(None, 28, bold=True)
                        except Exception:
                            flash_font = pygame.font.SysFont(None, 28, bold=True)
                        s = flash_font.render(f"ログ: {flash_label}", True, (10, 10, 10))
                        bx = log_panel_left + (log_panel_width - s.get_width()) // 2 - 8
                        by = log_panel_top + 6
                        bw = s.get_width() + 16
                        bh = s.get_height() + 8
                        pygame.draw.rect(screen, (255, 250, 210), (bx, by, bw, bh))
                        pygame.draw.rect(screen, (140, 120, 90), (bx, by, bw, bh), 1)
                        screen.blit(s, (bx + 8, by + 4))
                except Exception:
                    pass
        except Exception:
            pass
        
        # ログアイコンのツールチップ表示用リスト（位置と駒の種類を記録）
        log_icon_tooltips = []
        
        # グループ化: 同じ文章（is_first=Falseが連続）をまとめる
        line_groups = []
        current_group = []
        for item in visible_lines:
            wline, kind, piece_letter, is_first = item
            if is_first and current_group:
                line_groups.append(current_group)
                current_group = []
            current_group.append((wline, kind, piece_letter))
        if current_group:
            line_groups.append(current_group)
        
        for group in line_groups:
            if log_y >= log_panel_top + log_panel_height - bottom_padding_px:
                break
            
            # グループの最初の行から種類とアイコン情報を取得
            first_wline, kind, piece_letter = group[0]
            
            # 各行のテキストサーフェスを準備
            text_surfs = []
            max_tw = 0
            total_th = 0
            for wline, _, _ in group:
                try:
                    ts = FONT.render(wline, True, (30, 30, 30))
                except Exception:
                    ts = pygame.font.SysFont(None, 18).render(wline, True, (30, 30, 30))
                text_surfs.append(ts)
                max_tw = max(max_tw, ts.get_width())
                total_th += ts.get_height()
            
            th = text_surfs[0].get_height() if text_surfs else line_h
            
            # アイコンの準備
            icon_surf = None
            icon_w = icon_h = 0
            try:
                if piece_letter and 'get_piece_image_surface' in globals() and get_piece_image_surface:
                    color = 'black' if kind == 'ai' else 'white'
                    icon_h = icon_w = th
                    icon_surf = get_piece_image_surface(piece_letter, color, (icon_w, icon_h))
                    if icon_surf is None:
                        icon_w = icon_h = 0
            except Exception:
                icon_surf = None
            
            # グループ全体の囲いを描画
            group_height = total_th + pad_y * 2
            
            if kind == 'separator':
                # ターン区切り線：1行で横いっぱいに「─」で埋めて、中央にテキストを配置
                ty = log_y
                # 区切り線テキストは1行のみ
                if text_surfs:
                    ts = text_surfs[0]
                    text_w = ts.get_width()
                    text_x = log_panel_left + (log_panel_width - text_w) // 2
                    
                    # フォント幅を取得
                    try:
                        dash_width = FONT.render('─', True, (30, 30, 30)).get_width()
                    except Exception:
                        dash_width = 10
                    
                    # パネル内の有効な領域（左右の余白、枠線、スクロールバー用の余白を確保）
                    panel_left = log_panel_left + 12  # 枠線2px + 余白10px
                    panel_right = log_panel_left + log_panel_width - 32  # 枠線2px + 余白30px
                    
                    # 左側の「─」の数を計算
                    left_available = max(0, text_x - panel_left)
                    left_dashes = max(0, left_available // dash_width)
                    
                    # 右側の「─」の数を計算
                    right_start_x = text_x + text_w
                    right_available_width = max(0, panel_right - right_start_x)
                    right_dashes = max(0, right_available_width // dash_width)
                    
                    # 左側の「─」を描画
                    if left_dashes > 0:
                        left_line = '─' * left_dashes
                        left_surf = FONT.render(left_line, True, (30, 30, 30))
                        # 描画位置がパネル内に収まるか確認
                        if panel_left < log_panel_left + log_panel_width:
                            screen.blit(left_surf, (panel_left, ty))
                    
                    # 中央のテキストを描画
                    screen.blit(ts, (text_x, ty))
                    
                    # 右側の「─」を描画（パネルの右端を超えないように）
                    if right_dashes > 0:
                        right_line = '─' * right_dashes
                        right_surf = FONT.render(right_line, True, (30, 30, 30))
                        # 実際の描画幅を確認
                        right_surf_width = right_surf.get_width()
                        # 右端がパネルを超えないように調整
                        if right_start_x + right_surf_width > panel_right:
                            # はみ出す場合は描画しない、または短くする
                            adjusted_dashes = max(0, (panel_right - right_start_x) // dash_width - 1)
                            if adjusted_dashes > 0:
                                right_line = '─' * adjusted_dashes
                                right_surf = FONT.render(right_line, True, (30, 30, 30))
                                screen.blit(right_surf, (right_start_x, ty))
                        else:
                            screen.blit(right_surf, (right_start_x, ty))
            elif kind == 'ai':
                # 左揃え、薄赤背景
                bx = log_panel_left + 10
                by = log_y - pad_y
                bw = max_tw + pad_x * 2 + (icon_w + 6 if icon_w else 0)
                bh = group_height
                pygame.draw.rect(screen, (255, 230, 230), (bx, by, bw, bh))
                pygame.draw.rect(screen, (200, 140, 140), (bx, by, bw, bh), 1)
                
                # アイコンを最初の行に描画
                tx = bx + pad_x
                if icon_surf:
                    try:
                        screen.blit(icon_surf, (tx, log_y))
                        icon_rect = pygame.Rect(tx, log_y, icon_w, icon_h)
                        log_icon_tooltips.append((icon_rect, piece_letter))
                        tx += icon_w + 6
                    except Exception:
                        pass
                
                # 各行のテキストを描画
                ty = log_y
                for idx, ts in enumerate(text_surfs):
                    text_x = bx + pad_x + (icon_w + 6 if icon_w and idx == 0 else 0)
                    screen.blit(ts, (text_x, ty))
                    ty += ts.get_height()
            else:
                # プレイヤー/右揃え、薄水色背景（スクロールバー用に右余白を増やす）
                bw = max_tw + pad_x * 2 + (icon_w + 6 if icon_w else 0)
                bx = log_panel_left + log_panel_width - 30 - bw  # 10→30pxに変更
                by = log_y - pad_y
                bh = group_height
                pygame.draw.rect(screen, (220, 240, 255), (bx, by, bw, bh))
                pygame.draw.rect(screen, (140, 170, 200), (bx, by, bw, bh), 1)
                
                # アイコンを最初の行に描画
                tx = bx + pad_x
                if icon_surf:
                    try:
                        screen.blit(icon_surf, (tx, log_y))
                        icon_rect = pygame.Rect(tx, log_y, icon_w, icon_h)
                        log_icon_tooltips.append((icon_rect, piece_letter))
                        tx += icon_w + 6
                    except Exception:
                        pass
                
                # 各行のテキストを描画
                ty = log_y
                for idx, ts in enumerate(text_surfs):
                    text_x = bx + pad_x + (icon_w + 6 if icon_w and idx == 0 else 0)
                    screen.blit(ts, (text_x, ty))
                    ty += ts.get_height()
            
            # 次の文章グループは適度な間隔を空けて描画（読みやすく）
            log_y += group_height + int(line_h * 1.3)  # 間隔を少し広げる
        
        # マウス位置がログアイコン上にある場合、ツールチップを表示
        try:
            mx, my = pygame.mouse.get_pos()
            for icon_rect, piece_letter in log_icon_tooltips:
                if icon_rect.collidepoint(mx, my):
                    # ツールチップを表示
                    piece_name = PIECE_NAMES.get(piece_letter, piece_letter)
                    try:
                        tooltip_font = SMALL if SMALL else pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
                    except Exception:
                        tooltip_font = pygame.font.SysFont(None, 18)
                    tooltip_surf = tooltip_font.render(piece_name, True, (255, 255, 255))
                    tooltip_w = tooltip_surf.get_width() + 12
                    tooltip_h = tooltip_surf.get_height() + 8
                    # ツールチップの位置（アイコンの下に固定表示）
                    tooltip_x = icon_rect.left + (icon_rect.width - tooltip_w) // 2
                    tooltip_y = icon_rect.bottom + 4
                    # 画面外に出ないように調整
                    if tooltip_x < 0:
                        tooltip_x = 0
                    if tooltip_x + tooltip_w > W:
                        tooltip_x = W - tooltip_w - 5
                    if tooltip_y + tooltip_h > H:
                        tooltip_y = icon_rect.top - tooltip_h - 4
                    # 背景を描画
                    pygame.draw.rect(screen, (60, 60, 80), (tooltip_x, tooltip_y, tooltip_w, tooltip_h))
                    pygame.draw.rect(screen, (200, 200, 220), (tooltip_x, tooltip_y, tooltip_w, tooltip_h), 1)
                    # テキストを描画
                    screen.blit(tooltip_surf, (tooltip_x + 6, tooltip_y + 4))
                    break  # 1つのツールチップのみ表示
        except Exception:
            pass

        # スクロールバー表示
        if max_scroll > 0:
            # スクロールバーのエリア
            scrollbar_x = log_panel_left + log_panel_width - 15
            scrollbar_y = log_panel_top + 56
            scrollbar_height = log_panel_height - 66
            scrollbar_width = 8
            # 背景（グレー）
            pygame.draw.rect(screen, (200, 200, 200), 
                           (scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height))
            # スクロール位置を計算
            total_lines = total_wrapped
            scroll_ratio = log_scroll_offset / max_scroll if max_scroll > 0 else 0
            # つまみのサイズと位置
            thumb_height = max(20, scrollbar_height * max_lines_visible / total_lines)
            thumb_y = scrollbar_y + (scrollbar_height - thumb_height) * (1 - scroll_ratio)
            # つまみ（濃いグレー）
            pygame.draw.rect(screen, (100, 100, 100), 
                           (scrollbar_x, thumb_y, scrollbar_width, thumb_height))
            # スクロールバーの矩形を保存（ドラッグ用）
            scrollbar_rect = pygame.Rect(scrollbar_x, thumb_y, scrollbar_width, thumb_height)
        else:
            scrollbar_rect = None
        
        # ログパネルの下にログ切り替え［C］を表示（ログ表示時にも表示）
        try:
            hint_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
            hint_s = hint_font.render("ログ切り替え［C］", True, (80, 80, 110))
            hint_y = log_panel_top + log_panel_height + 12
            screen.blit(hint_s, (layout['right_panel_x'] + 12, hint_y))
        except Exception:
            hint_y = log_panel_top + log_panel_height + 12
            draw_text(screen, "ログ切り替え［C］", layout['right_panel_x'] + 12, hint_y, (100, 100, 120), bold=True, scale=1.4)
    else:
        # ログ非表示時のヒント (右パネルに寄せる)
        # Make the label more visible by using a bolder font if available.
        try:
            lbl_font = HELP_FONT if HELP_FONT else pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
            lbl_s = lbl_font.render("[L] ログ表示", True, (80, 80, 110))
            screen.blit(lbl_s, (layout['right_panel_x'] + 12, board_area_top + board_area_height - 30))
        except Exception:
            draw_text(screen, "[L] ログ表示", layout['right_panel_x'] + 12, board_area_top + board_area_height - 30, (100, 100, 120))
        # ログ切り替え［C］を下に表示（大きく太字）
        try:
            hint_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
            hint_s = hint_font.render("ログ切り替え［C］", True, (80, 80, 110))
            screen.blit(hint_s, (layout['right_panel_x'] + 12, board_area_top + board_area_height + 8))
        except Exception:
            draw_text(screen, "ログ切り替え［C］", layout['right_panel_x'] + 12, board_area_top + board_area_height + 8, (100, 100, 120), bold=True, scale=1.4)

    # 下部エリア: 手札（横並び最大7枚、クリックで拡大）
    card_area_top = layout['card_area_top']
    hand_title_x = layout['left_margin']  # 左マージンから開始
    hand_title_y = card_area_top
    draw_text(screen, "手札 (1-7で使用 / クリックで拡大):", hand_title_x, hand_title_y, (40, 40, 40))
    
    # カードサイズ: レイアウトで計算した card_h をベースに視覚的に拡大
    scale = layout.get('scale', 1.0)
    base_card_h = layout.get('card_h', max(72, int(175 * scale)))
    # Apply a visual multiplier for thumbnails. Reduce the multiplier on
    # normal/smaller window sizes to avoid clipping; allow larger scale on
    # fullscreen where there's more space.
    try:
        ui_scale = layout.get('scale', 1.0)
        if ui_scale <= 1.0:
            # normal window: avoid any enlargement to prevent clipping
            VISUAL_CARD_SCALE = 0.9
        elif ui_scale <= 1.15:
            VISUAL_CARD_SCALE = 1.0
        else:
            VISUAL_CARD_SCALE = 1.15
    except Exception:
        VISUAL_CARD_SCALE = 1.05
    card_h = max(48, int(base_card_h * VISUAL_CARD_SCALE))

    # Clamp card_h so it doesn't overlap the board or other UI.
    try:
        bottom_slack = H - (layout['board_top'] + layout['board_size'])
        # leave a larger padding to prevent bottom clipping on usual windows
        avail_for_card = max(48, bottom_slack - int(64 * scale))
        max_by_board = int(layout['board_size'] * 0.75)
        allowed = max(48, min(max_by_board, avail_for_card))
        if card_h > allowed:
            card_h = allowed
    except Exception:
        pass

    # compute width preserving original aspect ratio used elsewhere (130x175 base)
    card_w = max(48, int(card_h * (130.0 / 175.0)))
    card_spacing = max(8, int(8 * scale))
    card_start_x = hand_title_x  # 左マージンから開始
    card_y = hand_title_y + 30
    
    # カード描画とクリック判定用の矩形保存
    global card_rects
    card_rects = []
    
    for i, c in enumerate(game.player.hand.cards[:7]):
        x = card_start_x + i * (card_w + card_spacing)
        rect = pygame.Rect(x, card_y, card_w, card_h)
        card_rects.append((rect, i))
        
        # カード画像のみ表示
        thumb = get_card_image(c.name, size=(card_w, card_h))
        screen.blit(thumb, (x, card_y))
        
        # 錬成で選択中のカードを金色の枠で強調
        if (getattr(game, 'pending', None) is not None and 
            game.pending.kind == 'discard' and 
            game.pending.info.get('selected') == i):
            # 太い金色の枠
            pygame.draw.rect(screen, (255, 215, 0), rect, 5)
            # 外側にもう一層、少し濃い金色
            pygame.draw.rect(screen, (218, 165, 32), rect.inflate(4, 4), 3)
        
        # カード下部にボタン番号を表示（数字キーで発動が有効なときのみ）
        if globals().get('gimmick_activation_mode', 'number_key') == 'number_key':
            button_number = f"[{i+1}]"
            # 背景ボックス
            button_bg_width = 35
            button_bg_height = 30
            button_bg_x = x + (card_w - button_bg_width) // 2
            button_bg_y = card_y + card_h - button_bg_height - 5
            
            # PP足りるかで色を変える
            if c.cost <= game.player.pp_current:
                bg_color = (100, 200, 100)  # 緑（使用可能）
            else:
                bg_color = (200, 100, 100)  # 赤（PP不足）
            
            pygame.draw.rect(screen, bg_color, (button_bg_x, button_bg_y, button_bg_width, button_bg_height))
            pygame.draw.rect(screen, (255, 255, 255), (button_bg_x, button_bg_y, button_bg_width, button_bg_height), 2)
            
            # 番号テキスト
            num_surf = FONT.render(button_number, True, (255, 255, 255))
            num_x = button_bg_x + (button_bg_width - num_surf.get_width()) // 2
            num_y = button_bg_y + (button_bg_height - num_surf.get_height()) // 2
            screen.blit(num_surf, (num_x, num_y))


    # 墓地オーバーレイ ([G]で表示/非表示)
    if show_grave:
        overlay_w = 600
        overlay_h = 500
        overlay_x = (W - overlay_w) // 2
        overlay_y = (H - overlay_h) // 2
        
        overlay = pygame.Surface((overlay_w, overlay_h))
        overlay.fill((255, 255, 255))
        overlay.set_alpha(245)
        screen.blit(overlay, (overlay_x, overlay_y))
        
        pygame.draw.rect(screen, (100, 100, 100), (overlay_x, overlay_y, overlay_w, overlay_h), 3)
        
        draw_text(screen, "墓地のカード一覧 [G]で閉じる", overlay_x + 20, overlay_y + 20, (120, 0, 0))
        draw_text(screen, "カードをクリックで拡大表示", overlay_x + 320, overlay_y + 20, (80, 80, 80))
        
        counts = {}
        for c in game.player.graveyard:
            counts[c.name] = counts.get(c.name, 0) + 1
        
        gy = overlay_y + 60
        gx = overlay_x + 30
        col_w = 280
        global grave_card_rects
        grave_card_rects = []
        for name, cnt in sorted(counts.items()):
            thumb = get_card_image(name, size=(70, 95))
            screen.blit(thumb, (gx, gy))
            draw_text(screen, f"{name}: {cnt}枚", gx + 80, gy + 35)
            # クリック用の矩形を保存
            grave_card_rects.append((pygame.Rect(gx, gy, 70, 95), name))
            gy += 110
            if gy > overlay_y + overlay_h - 80:
                gy = overlay_y + 60
                gx += col_w
                if gx > overlay_x + overlay_w - 100:
                    break

    # 相手手札オーバーレイ ([H]で表示/非表示)
    if show_opponent_hand:
        overlay_w = 600
        overlay_h = 400
        overlay_x = (W - overlay_w) // 2
        overlay_y = (H - overlay_h) // 2
        
        overlay = pygame.Surface((overlay_w, overlay_h))
        overlay.fill((230, 230, 240))
        overlay.set_alpha(245)
        screen.blit(overlay, (overlay_x, overlay_y))
        
        pygame.draw.rect(screen, (100, 100, 120), (overlay_x, overlay_y, overlay_w, overlay_h), 3)
        
        draw_text(screen, f"相手の手札 ({get_opponent_hand_count()}枚) [H]で閉じる", overlay_x + 20, overlay_y + 20, (100, 50, 100))
        
        # カード裏面を横並びで表示（画像未実装のため仮の矩形）
        card_back_w = 70
        card_back_h = 95
        start_x = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count(), 7) + 10 * (min(get_opponent_hand_count(), 7) - 1))) // 2
        cy = overlay_y + 80

        for i in range(get_opponent_hand_count()):
            if i >= 7:  # 1行に7枚まで
                cy += card_back_h + 20
                start_x = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count() - 7, 7) + 10 * (min(get_opponent_hand_count() - 7, 7) - 1))) // 2
                if i == 7:
                    pass  # 2行目の開始位置を再計算済み

            row = i // 7
            col = i % 7
            if row > 0:
                cx = overlay_x + (overlay_w - (card_back_w * min(get_opponent_hand_count() - 7, 7) + 10 * (min(get_opponent_hand_count() - 7, 7) - 1))) // 2 + col * (card_back_w + 10)
            else:
                cx = start_x + col * (card_back_w + 10)

            actual_cy = overlay_y + 80 + row * (card_back_h + 20)
            
            # カード裏面（仮実装：グレーの矩形とパターン）
            card_rect = pygame.Rect(cx, actual_cy, card_back_w, card_back_h)
            pygame.draw.rect(screen, (150, 150, 160), card_rect)
            pygame.draw.rect(screen, (80, 80, 90), card_rect, 2)
            # 裏面パターン（斜線）
            for j in range(0, card_back_w + card_back_h, 10):
                pygame.draw.line(screen, (120, 120, 130), (cx, actual_cy + j), (cx + j, actual_cy), 1)
            # 中央にテキスト
            draw_text(screen, "?", cx + card_back_w // 2 - 8, actual_cy + card_back_h // 2 - 10, (80, 80, 90))

    # カード拡大表示オーバーレイ（手札または墓地から）
    if enlarged_card_index is not None and 0 <= enlarged_card_index < len(game.player.hand.cards):
        c = game.player.hand.cards[enlarged_card_index]
        
        # 拡大カードサイズ（スケール倍率を適用）
        base_w = 300
        base_h = 420
        enlarged_w = int(base_w * enlarged_card_scale)
        enlarged_h = int(base_h * enlarged_card_scale)
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2
        
        # 背景暗転
        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))
        
        # 拡大画像のみ表示
        large_img = get_card_image(c.name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))
        
        # 拡大率表示（デバッグ用）
        scale_text = SMALL.render(f"拡大率: {enlarged_card_scale:.1f}x (マウスを上下に動かして調整)", True, (255, 255, 255))
        screen.blit(scale_text, (10, H - 30))
    elif enlarged_card_name is not None:
        # 手札以外（例: 墓地）からの拡大表示
        base_w = 300
        base_h = 420
        enlarged_w = int(base_w * enlarged_card_scale)
        enlarged_h = int(base_h * enlarged_card_scale)
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2

        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))

        large_img = get_card_image(enlarged_card_name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))
        
        # 拡大率表示
        scale_text = SMALL.render(f"拡大率: {enlarged_card_scale:.1f}x (マウスを上下に動かして調整)", True, (255, 255, 255))
        screen.blit(scale_text, (10, H - 30))

    # 保留中操作の説明オーバーレイ（捨て札選択、ターゲット指定等）
    if getattr(game, 'pending', None) is not None:
        # 操作説明テキストを決定
        if game.pending.kind == 'discard':
            instruction_text = "手札から捨てるカードを選択: [1-7]で選択 → [D]で確定"
        elif game.pending.kind == 'target_tile':
            instruction_text = "封鎖するマスを選択してください"
        elif game.pending.kind == 'target_piece':
            instruction_text = "凍結する相手コマを選択してください"
        elif game.pending.kind == 'heat_choice':
            instruction_text = "灼熱: 自分の凍結駒を解除するか、3マス封鎖をするか選択してください。"
        elif game.pending.kind == 'discard_opponent_hand':
            instruction_text = "相手の手札からランダムで1枚墓地に送ります..."
        elif game.pending.kind == 'gamble_promote':
            instruction_text = "命がけのギャンブル発動中..."
        elif game.pending.kind == 'board_reset':
            instruction_text = "「負けるわけないだろwww」発動！盤面をリセットします..."
        else:
            instruction_text = "選択を完了してください"
        
        # ボックスサイズ計算
        box_padding = 30
        
        # レイアウト情報を取得
        layout = compute_layout(W, H)
        left_margin = layout['left_margin']
        left_panel_width = layout['left_panel_width']
        
        # 左パネル内に収まる最大幅を計算
        max_box_width = left_panel_width - 20
        
        # テキストを左パネルの幅に合わせて自動改行
        if game.pending.kind == 'confirm':
            msg = game.pending.info.get('message', '実行してもよろしいですか？ [Y]=はい / [N]=いいえ')
        else:
            msg = instruction_text
        
        # メッセージを改行文字で分割
        original_lines = msg.split('\n')
        wrapped_lines = []
        
        # 各行を左パネルの幅に収まるように自動折り返し（より正確な計算）
        for original_line in original_lines:
            if len(original_line) == 0:
                wrapped_lines.append('')
                continue
            
            # 実際の描画幅を計算しながら折り返し
            words = original_line
            current_line = ""
            for char in words:
                test_line = current_line + char
                test_surface = FONT.render(test_line, True, (0, 0, 0))
                if test_surface.get_width() > (max_box_width - box_padding * 2):
                    if current_line:
                        wrapped_lines.append(current_line)
                    current_line = char
                else:
                    current_line = test_line
            if current_line:
                wrapped_lines.append(current_line)
        
        # 各行の幅を計算して最大幅を取得
        max_width = 0
        for line in wrapped_lines:
            line_surface = FONT.render(line, True, (0, 0, 0))
            max_width = max(max_width, line_surface.get_width())
        
        box_width = min(max_width + box_padding * 2, max_box_width)
        # タイトル + メッセージ行数分の高さ + 下部余白
        box_height = 50 + len(wrapped_lines) * 22 + 15
        
        # 左パネルエリアに配置（ターン開始ボタンの下）
        box_x = left_margin + 10
        # ターン開始ボタンの下に配置（start_turn_rectがあればその下、なければデフォルト位置）
        if 'start_turn_rect' in globals() and start_turn_rect is not None:
            box_y = start_turn_rect.bottom + 20  # ターン開始ボタンの下に20pxの余白
        else:
            box_y = max(80, (H - box_height) // 2 - 100)
        
        # 背景ボックス
        pygame.draw.rect(screen, (255, 255, 200), (box_x, box_y, box_width, box_height))
        pygame.draw.rect(screen, (180, 60, 0), (box_x, box_y, box_width, box_height), 4)
        
        # タイトル
        draw_text(screen, "⚠ 操作待ち", box_x + box_padding, box_y + 15, (180, 60, 0))
        
        # 操作説明テキスト（複数行対応）
        line_y = box_y + 45
        for line in wrapped_lines:
            draw_text(screen, line, box_x + box_padding, line_y, (60, 60, 60))
            line_y += 22  # 行間

        # 灼熱選択用の二択ボタン（保留が heat_choice のとき）
        global heat_choice_unfreeze_rect, heat_choice_block_rect
        heat_choice_unfreeze_rect = None
        heat_choice_block_rect = None
        if getattr(game, 'pending', None) is not None and game.pending.kind == 'heat_choice':
            btn_w, btn_h = 260, 40
            gap = 20
            # ボタンを画面中央に配置（heat_choiceの選択肢は従来通り中央）
            btn_y = box_y + box_height + 12
            total_w = btn_w * 2 + gap
            start_x = (W - total_w) // 2
            heat_choice_unfreeze_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
            heat_choice_block_rect = pygame.Rect(start_x + btn_w + gap, btn_y, btn_w, btn_h)
            pygame.draw.rect(screen, (70, 130, 180), heat_choice_unfreeze_rect)
            pygame.draw.rect(screen, (180, 100, 60), heat_choice_block_rect)
            pygame.draw.rect(screen, (255,255,255), heat_choice_unfreeze_rect, 2)
            pygame.draw.rect(screen, (255,255,255), heat_choice_block_rect, 2)
            t1 = FONT.render('自分の凍結駒を解除', True, (255,255,255))
            t2 = FONT.render('3マス封鎖をする', True, (255,255,255))
            screen.blit(t1, (heat_choice_unfreeze_rect.centerx - t1.get_width()//2, heat_choice_unfreeze_rect.centery - t1.get_height()//2))
            screen.blit(t2, (heat_choice_block_rect.centerx - t2.get_width()//2, heat_choice_block_rect.centery - t2.get_height()//2))

        # 確認ダイアログのボタン（はい/いいえ）- 警告ボックスの下に配置
        global confirm_yes_rect, confirm_no_rect
        confirm_yes_rect = None
        confirm_no_rect = None
        if game.pending.kind == 'confirm':
            btn_w, btn_h = 100, 36
            gap = 15
            # 警告ボックスの下、左パネル内に配置
            btn_y = box_y + box_height + 12
            total_w = btn_w * 2 + gap
            start_x = box_x + (box_width - total_w) // 2  # 警告ボックスの中央に配置
            yes_label = game.pending.info.get('yes_label', 'はい(Y)')
            no_label = game.pending.info.get('no_label', 'いいえ(N)')
            confirm_yes_rect = pygame.Rect(start_x, btn_y, btn_w, btn_h)
            confirm_no_rect = pygame.Rect(start_x + btn_w + gap, btn_y, btn_w, btn_h)
            pygame.draw.rect(screen, (80, 150, 80), confirm_yes_rect)
            pygame.draw.rect(screen, (160, 80, 80), confirm_no_rect)
            pygame.draw.rect(screen, (255, 255, 255), confirm_yes_rect, 2)
            pygame.draw.rect(screen, (255, 255, 255), confirm_no_rect, 2)
            yes_s = FONT.render(yes_label, True, (255, 255, 255))
            no_s = FONT.render(no_label, True, (255, 255, 255))
            screen.blit(yes_s, (confirm_yes_rect.centerx - yes_s.get_width()//2, confirm_yes_rect.centery - yes_s.get_height()//2))
            screen.blit(no_s, (confirm_no_rect.centerx - no_s.get_width()//2, confirm_no_rect.centery - no_s.get_height()//2))

    # プロモーション選択オーバーレイ (Q/R/B/N) - プレイヤー（白）の駒のみ
    # ゲームオーバー時は昇格UIを表示しない
    if chess.promotion_pending is not None and not game_over:
        promot = chess.promotion_pending
        promo_color = promot.get('color', None)
        
        # AIの駒（黒）の昇格は自動処理されるべきなので、UIは表示しない
        if promo_color == 'white':
            opts = ['Q','R','B','N']
            # サイズ・配置
            box_w = 460
            box_h = 160
            # Prefer positioning the promotion box so it stays within the chessboard area.
            # If possible, center the box over the promotion square; otherwise clamp to board bounds.
            try:
                piece = promot.get('piece')
                # tile origin (top-left) for the piece's square
                pr = getattr(piece, 'row', None)
                pc = getattr(piece, 'col', None)
                tile_x = board_left + (pc * (board_size // 8)) if pc is not None else None
                tile_y = board_top + (pr * (board_size // 8)) if pr is not None else None
            except Exception:
                tile_x = None
                tile_y = None

            # center promotion box within the chessboard area
            try:
                box_x = board_left + (board_size - box_w) // 2
                box_y = board_top + (board_size - box_h) // 2
            except Exception:
                # fallback to screen center if board metrics aren't available
                box_x = (W - box_w)//2
                box_y = (H - box_h)//2
            pygame.draw.rect(screen, (245,245,245), (box_x, box_y, box_w, box_h))
            pygame.draw.rect(screen, (80,80,80), (box_x, box_y, box_w, box_h), 2)
            # ヘッダ
            header_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28)
            hdr = header_font.render("昇格する駒を選択", True, (40,40,40))
            screen.blit(hdr, (box_x + (box_w - hdr.get_width())//2, box_y + 8))

            # 選択肢を横並びに描画（駒画像を使う）
            opt_w = 96
            spacing = (box_w - 24 - len(opts)*opt_w) // (len(opts)-1)
            ox = box_x + 12
            oy = box_y + 48
            promo_rects = []
            for i,o in enumerate(opts):
                r = pygame.Rect(ox + i*(opt_w+spacing), oy, opt_w, opt_w)
                pygame.draw.rect(screen, (230,230,230), r)
                pygame.draw.rect(screen, (120,120,120), r, 2)
                # piece image for promot['color']
                img = get_piece_image_surface(o, promot['color'], (opt_w-8, opt_w-8))
                if img is not None:
                    screen.blit(img, (r.x + 4, r.y + 4))
                else:
                    lab = FONT.render(o, True, (0,0,0))
                    screen.blit(lab, (r.x + (r.w - lab.get_width())//2, r.y + (r.h - lab.get_height())//2))
                promo_rects.append((r, o))
            draw_panel.promo_rects = promo_rects

    # AI 思考中オーバーレイ
    try:
        # Do not show AI thinking overlay while a player (white) promotion selection is pending.
        promotion_obj = getattr(chess, 'promotion_pending', None)
        player_promotion_pending = promotion_obj is not None and promotion_obj.get('color') == 'white'
        if cpu_wait and THINKING_ENABLED and not game_over and not player_promotion_pending:
            import time
            # Restrict overlay to the board area so it stays within the chessboard
            bs = board_size
            bx = board_left
            by = board_top
            overlay = pygame.Surface((bs, bs), pygame.SRCALPHA)
            overlay.fill((15,15,15,50) if not get_ui_effects_enabled() else (0,0,0,140))
            # draw the overlay onto the main screen at board position
            screen.blit(overlay, (bx, by))

            elapsed = time.time() - cpu_wait_start if cpu_wait_start else 0
            dots = int((elapsed * THINK_DOT_FREQ) % 4)
            msg = "思考中" + "." * dots
            # choose font size relative to board to avoid overflow
            font_size = max(20, bs // 12)
            msg_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", font_size, bold=True)
            txt = msg_font.render(msg, True, (250,250,250))
            # center within board area
            txt_x = bx + (bs - txt.get_width())//2
            txt_y = by + (bs - txt.get_height())//2
            screen.blit(txt, (txt_x, txt_y))
    except Exception:
        pass

    # ゲーム終了画面（勝敗表示と再戦ボタン）
    if game_over:
        # 半透明オーバーレイを全画面に表示（より強く暗くして文字を目立たせる）
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        # Always use a strong dark overlay for game-over so the end UI stands out.
        overlay.fill((0, 0, 0, 220) if get_ui_effects_enabled() else (15, 15, 15, 220))
        screen.blit(overlay, (0, 0))

        # (タイトルとボタン背後の専用パネルは表示しない)
        
        # 勝敗メッセージ
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 48, bold=True)
        
        # game_over_winnerがNoneの場合、キングの存在から勝者を推定
        current_winner = game_over_winner
        if current_winner is None:
            try:
                white_king_exists = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                black_king_exists = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                if white_king_exists and not black_king_exists:
                    current_winner = 'white'
                elif black_king_exists and not white_king_exists:
                    current_winner = 'black'
                else:
                    current_winner = 'draw'
            except Exception:
                current_winner = 'draw'

        # Defensive correction: if the stored result is 'draw' but the board
        # actually has only one king, prefer that side as the winner.
        try:
            if game_over_winner == 'draw':
                w_exists = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                b_exists = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                if w_exists and not b_exists:
                    current_winner = 'white'
                elif b_exists and not w_exists:
                    current_winner = 'black'
        except Exception:
            pass
        
        if current_winner == 'white':
            msg = "YOU WIN！"
            color = (255, 255, 100)
        elif current_winner == 'black':
            msg = "YOU LOSE！"
            color = (150, 150, 255)
        else:  # draw
            msg = "引き分け"
            color = (200, 200, 200)
        
        title_surf = title_font.render(msg, True, color)
        title_rect = title_surf.get_rect(center=(W//2, H//3))
        screen.blit(title_surf, title_rect)
        
        # 再戦ボタン
        btn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 32, bold=True)
        restart_text = "再戦 (R)"
        quit_text = "終了 (ESC)"
        
        restart_surf = btn_font.render(restart_text, True, (255, 255, 255))
        quit_surf = btn_font.render(quit_text, True, (255, 255, 255))
        
        btn_w = max(restart_surf.get_width(), quit_surf.get_width()) + 40
        btn_h = 60
        
        restart_rect = pygame.Rect(W//2 - btn_w//2, H//2, btn_w, btn_h)
        # add "change difficulty and rematch" button (gold)
        change_rect = pygame.Rect(W//2 - btn_w//2, H//2 + btn_h + 12, btn_w, btn_h)
        quit_rect = pygame.Rect(W//2 - btn_w//2, H//2 + 2*btn_h + 24, btn_w, btn_h)
        
        # ボタン描画
        pygame.draw.rect(screen, (50, 150, 50), restart_rect)
        # gold button for changing difficulty then rematch
        gold = (212, 175, 55)
        pygame.draw.rect(screen, gold, change_rect)
        pygame.draw.rect(screen, (150, 50, 50), quit_rect)
        # borders
        pygame.draw.rect(screen, (255, 255, 255), restart_rect, 3)
        pygame.draw.rect(screen, (255, 255, 255), change_rect, 3)
        pygame.draw.rect(screen, (255, 255, 255), quit_rect, 3)

        screen.blit(restart_surf, restart_surf.get_rect(center=restart_rect.center))
        # change button text
        change_text = "難易度変更"
        change_surf = btn_font.render(change_text, True, (30,30,30))
        screen.blit(change_surf, change_surf.get_rect(center=change_rect.center))
        screen.blit(quit_surf, quit_surf.get_rect(center=quit_rect.center))
        
        # ボタンの矩形を保存（クリック判定用）
        draw_panel.restart_rect = restart_rect
        draw_panel.change_difficulty_rect = change_rect
        draw_panel.quit_rect = quit_rect


def start_player_turn(ai_end_msg: str = None):
    """Centralized helper that starts a player's card-game turn and shows the YOUR TURN telop.

    Use this wrapper instead of calling `game.start_turn()` directly from the UI so
    the visual telop is always displayed when a turn begins (manual or automatic).

    If `ai_end_msg` is provided, append that message to the game log after the
    turn-start processing. This ensures any draw logs produced by `game.start_turn()`
    appear before the AI end message when the AI triggers an automatic player turn.
    """
    global turn_telop_msg, turn_telop_until, log_scroll_offset
    try:
        # start_turn handles PP reset and the 1-card draw
        if ai_end_msg:
            # If caller provided an AI-end message, capture new log entries
            # produced by start_turn so we can reorder draw-related lines
            prev_log_len = len(game.log)
            game.start_turn()
            # extract newly added entries
            new_entries = game.log[prev_log_len:]
            # identify draw-only entries produced by draw_to_hand() which start with "ドロー:"
            draw_entries = [e for e in new_entries if isinstance(e, str) and e.strip().startswith("ドロー:")]
            # keep other new entries (including the full "ターンN開始: ...ドロー...PP..." message)
            non_draw_new = [e for e in new_entries if e not in draw_entries]
            # rebuild game.log keeping only non-draw new entries (we will NOT append draw_entries or the AI-end message)
            try:
                # game.logをLogListのまま維持するため、インプレースで削除と追加を行う
                # まず、prev_log_len以降のエントリを削除
                del game.log[prev_log_len:]
                # 次に、non_draw_newを追加（appendを使って master_log にも記録）
                for entry in non_draw_new:
                    game.log.append(entry)
            except Exception:
                # fallback: if direct assignment fails, leave as-is
                pass
        else:
            game.start_turn()
    except Exception:
        return
    try:
        turn_telop_msg = "YOUR TURN"
        turn_telop_until = _ct_time.time() + 1.0
    except Exception:
        pass
    try:
        log_scroll_offset = 0
    except Exception:
        pass
    # If an AI-provided end message is requested, do NOT append it here
    # and also do NOT append the per-card "ドロー:" lines. This keeps the
    # full turn-start message ("ターンN開始: ...ドロー...PP...") intact while
    # hiding the AI-end and standalone draw-name lines as requested.


def attempt_start_turn():
    """[T]と同等のターン開始処理をUIやマウスからも呼べるように関数化。"""
    global notice_msg, notice_until, turn_telop_msg, turn_telop_until, log_scroll_offset
    if getattr(game, 'pending', None) is not None:
        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
        return
    # ターン開始時に区切り線を表示
    game.log.append("─── 自分のターン ───")
    # 既に開始済み
    if getattr(game, 'turn_active', False):
        game.log.append("既にターンが開始されています。カードや駒の操作を行ってください。")
        try:
            notice_msg = "既にターンが開始されています。カードや駒の操作を行ってください。"
            notice_until = _ct_time.time() + 1.0
        except Exception:
            pass
        return
    # チェス手番/AI待ち中は開始不可
    global chess_current_turn, cpu_wait
    if chess_current_turn != 'white' or cpu_wait:
        game.log.append("チェスの操作またはAIの処理が完了していないため、ターンを開始できません。")
        try:
            notice_msg = "チェスの操作またはAIの処理が完了していないため、ターンを開始できません。"
            notice_until = _ct_time.time() + 1.0
        except Exception:
            pass
        return
    # 開始
    start_player_turn()


def handle_keydown(key):
    global log_scroll_offset, show_log, enlarged_card_index, enlarged_card_scale, enlarged_card_mouse_y, notice_msg, notice_until, show_grave, show_opponent_hand, current_log_view
    
    # ゲーム終了時のキー操作
    if game_over:
        if key == pygame.K_r:
            restart_game()
            return
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit(0)
        return  # ゲーム終了時は他のキー操作を無効化
    
    if key == pygame.K_ESCAPE:
        pygame.quit()
        sys.exit(0)
    
    # ログ表示切替
    if key == pygame.K_l:
        show_log = not show_log
        return
    
    # ログスクロール（ログ表示中のみ）
    if show_log:
        # ビュー切替（ログ表示中はCキーのみでビューを切替）
        if key == pygame.K_c:
            # Cycle views: detail -> piece -> card -> detail
            try:
                # determine current canonical view (prefer package module)
                cur = None
                try:
                    from ui import overlay as _pkg_ov
                    if hasattr(_pkg_ov, 'get_log_view'):
                        cur = _pkg_ov.get_log_view()
                except Exception:
                    pass
                if cur is None:
                    try:
                        import importlib
                        _mod = importlib.import_module('c.c.b.ui.overlay')
                        if hasattr(_mod, 'get_log_view'):
                            cur = _mod.get_log_view()
                    except Exception:
                        pass
                if cur is None:
                    # fallback to local variable
                    try:
                        cur = current_log_view
                    except Exception:
                        cur = 'detail'

                order = ['detail', 'piece', 'card']
                try:
                    idx = order.index(cur)
                    nxt = order[(idx + 1) % len(order)]
                except Exception:
                    nxt = 'detail'

                # apply to available overlay implementations
                applied = False
                try:
                    if hasattr(overlay, 'set_log_view'):
                        overlay.set_log_view(nxt)
                        applied = True
                except Exception:
                    pass
                if not applied:
                    try:
                        from ui import overlay as _ov
                        if hasattr(_ov, 'set_log_view'):
                            _ov.set_log_view(nxt)
                            applied = True
                    except Exception:
                        pass
                if not applied:
                    try:
                        import importlib
                        _ov2 = importlib.import_module('c.c.b.ui.overlay')
                        if hasattr(_ov2, 'set_log_view'):
                            _ov2.set_log_view(nxt)
                            applied = True
                    except Exception:
                        pass

                try:
                    current_log_view = nxt
                except Exception:
                    pass
            except Exception:
                try:
                    current_log_view = 'detail'
                except Exception:
                    pass
            log_scroll_offset = 0
            return

        if key == pygame.K_UP:
            log_scroll_offset += 1
            return
        if key == pygame.K_DOWN:
            log_scroll_offset = max(0, log_scroll_offset - 1)
            return
    
    if key == pygame.K_t:
        attempt_start_turn()
        return
    
    if key == pygame.K_g:
        # 墓地表示切替（保留中でも閲覧だけは可能）
        prev = show_grave
        show_grave = not show_grave
        # 開くときは相手手札を閉じる（クリック時と同じ排他制御）
        if not prev and show_grave:
            show_opponent_hand = False
        return
    
    if key == pygame.K_h:
        # 相手の手札表示切替（クリック時と同じ排他制御を反映）
        prev = show_opponent_hand
        show_opponent_hand = not show_opponent_hand
        # 開くときは墓地を閉じる
        if not prev and show_opponent_hand:
            show_grave = False
        return

    # DEBUG: F1-F4で盤面セットショートカット
    if key == pygame.K_F1:
        debug_setup_castling()
        return
    if key == pygame.K_F2:
        debug_setup_en_passant()
        return
    if key == pygame.K_F3:
        debug_setup_promotion()
        return
    if key == pygame.K_F4:
        debug_reset_initial()
        return
    if key == pygame.K_F5:
        debug_setup_checkmate()
        return
    
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
        # If player chose "カードをクリックして発動" (i.e. not number_key top-mode),
        # disable numeric-key activation for normal play. Permit numeric keys for
        # promotion selection or when a pending 'discard' selection is active.
        if globals().get('gimmick_activation_mode', 'number_key') != 'number_key':
            # allow promotion/discard flows to still use numeric keys
            if not (chess.promotion_pending is not None and 0 <= idx <= 3) and not (
                getattr(game, 'pending', None) is not None and getattr(game.pending, 'kind', None) == 'discard'
            ):
                msg = "カードをクリックで発動"
                game.log.append(msg)
                try:
                    notice_msg = msg
                    notice_until = _ct_time.time() + 1.0
                except Exception:
                    pass
                return
        # プロモーション選択中ならカード使用を抑止して昇格選択に使う
        if chess.promotion_pending is not None and 0 <= idx <= 3:
            opts = ['Q','R','B','N']
            sel = opts[idx]
            piece = chess.promotion_pending['piece']
            piece.name = sel
            game.log.append(f"昇格: ポーンを{sel}に昇格させました。")
            chess.promotion_pending = None
            return
        # pending中: discardのみ選択を許可し、それ以外は行動不可
        if getattr(game, 'pending', None) is not None:
            if game.pending.kind == 'discard':
                game.pending.info['selected'] = idx
                # カード名を取得してログに表示
                if 0 <= idx < len(game.player.hand.cards):
                    card_name = game.player.hand.cards[idx].name
                    game.log.append(f"捨てるカードとして『{card_name}』を選択。[D]で確定")
                else:
                    game.log.append(f"捨てるカードとして手札{idx+1}番を選択。[D]で確定")
            else:
                game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return
        # ターン開始前はカード使用不可（既存のメッセージを表示）
        if not getattr(game, 'turn_active', False):
            msg = "ターンが開始されていませんTキーでターンを開始してください"
            game.log.append(msg)
            try:
                notice_msg = msg
                notice_until = _ct_time.time() + 1.0
            except Exception:
                pass
            return
        ok, msg = game.play_card(idx)
        if not ok:
            game.log.append(msg)
        else:
            # [DEBUG] カード直後のみ許可モード：カード使用扱いフラグを立てる
            _debug_mark_card_played()
        log_scroll_offset = 0  # カード使用後は最新ログへ
        return

    # Y/N: 確認ダイアログへの回答
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'confirm':
        if key in (pygame.K_y, pygame.K_RETURN):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                # 墓地ルーレットの確認「はい」→カードを実際に消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除、墓地へ
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。墓地が空のため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                    _debug_mark_card_played()
                else:
                    game.log.append("確認: はい → 効果なし（墓地が空）")
            elif confirm_id == 'confirm_second_lightning_overwrite':
                # 迅雷2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                    _debug_mark_card_played()
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_second_storm_overwrite':
                # 暴風2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                    _debug_mark_card_played()
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_heat_no_frozen':
                # 灼熱で凍結駒がない場合の確認「はい」→カードを消費して墓地へ
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。凍結駒がないため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                    _debug_mark_card_played()
                else:
                    game.log.append("確認: はい → 効果なし")
            else:
                # その他の確認（通常の墓地ルーレット実行など）
                game.log.append("確認: はい")
                # 保留されていた効果を実行
                if game.pending.info.get('execute_on_confirm'):
                    hand_idx = game.pending.info.get('hand_index')
                    if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                        # 墓地が空でない場合の墓地ルーレット実行
                        import random
                        if game.player.graveyard:
                            idx = random.randrange(len(game.player.graveyard))
                            recovered = game.player.graveyard.pop(idx)
                            game.player.hand.add(recovered)
                            game.log.append(f"墓地から『{recovered.name}』を回収。")
            game.pending = None
            log_scroll_offset = 0
            return
        if key in (pygame.K_n, pygame.K_ESCAPE):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            elif confirm_id == 'confirm_heat_no_frozen':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            log_scroll_offset = 0
            return
    
    # Dキー: discard pending の確定
    if key == pygame.K_d and getattr(game, 'pending', None) is not None and game.pending.kind == 'discard':
        sel = game.pending.info.get('selected')
        if isinstance(sel, int):
            removed = game.player.hand.remove_at(sel)
            if removed:
                game.player.graveyard.append(removed)
                game.log.append(f"『{removed.name}』を捨てました。")
                
                # If there's an execute_after_discard instruction, perform it now
                ex = game.pending.info.get('execute_after_discard')
                if ex:
                    draw_n = int(ex.get('draw', 0)) if ex.get('draw', 0) else 0
                    if draw_n > 0:
                        res = game.draw_to_hand(draw_n)
                        items = []
                        for c, added in res:
                            if c is None:
                                continue
                            items.append(c.name if added else f"{c.name}(墓地)")
                        if items:
                            game.log.append("ドロー: " + ", ".join(items))
                # 保留をクリア
                game.pending = None
                log_scroll_offset = 0  # 保留解決後は最新ログへ
                return
            else:
                game.log.append("捨てるカードを選択してください。")
                # don't clear pending so player can choose again
                return
        else:
            game.log.append("捨てるカードが選択されていません。")
            # keep pending active so player can choose a card and press D
            return


def handle_mouse_click(pos):
    """マウスクリック時の処理"""
    global enlarged_card_index, enlarged_card_name, enlarged_card_scale, enlarged_card_mouse_y, selected_piece, highlight_squares, chess_current_turn, show_grave, show_opponent_hand, notice_msg, notice_until, game_over
    
    # ゲーム終了画面のボタン処理
    if game_over:
        if hasattr(draw_panel, 'restart_rect') and draw_panel.restart_rect.collidepoint(pos):
            restart_game()
            return
        if hasattr(draw_panel, 'change_difficulty_rect') and draw_panel.change_difficulty_rect.collidepoint(pos):
            # go back to difficulty select, then restart game with chosen difficulty
            try:
                show_start_screen()
            except Exception:
                pass
            # After show_start_screen() returns it may have created a new
            # `game`/`ai_player`. Reset board/UI state without prompting
            # for deck selection again.
            try:
                _prepare_new_battle_after_deck_already_selected()
            except Exception:
                # fallback to full restart which will prompt if necessary
                try:
                    restart_game()
                except Exception:
                    pass
            return
        if hasattr(draw_panel, 'quit_rect') and draw_panel.quit_rect.collidepoint(pos):
            pygame.quit()
            sys.exit(0)
        return

    # Click timing for double-click detection
    # We use a combination of index-based detection (same logical card index
    # clicked twice within the interval) and the previous position-based
    # distance test as a fallback. This makes double-clicks robust when the
    # first click toggles an enlarged overlay which can move pixel coords.
    global last_click_time, last_click_pos, last_clicked_card_index
    now = _ct_time.time()
    is_double = False

    # Determine if this click hit a thumbnail card and capture its index
    clicked_target_index = None
    try:
        for rect, idx in card_rects:
            if rect.collidepoint(pos):
                clicked_target_index = idx
                break
    except Exception:
        # card_rects may not be initialized yet; ignore
        clicked_target_index = None

    try:
        dx = pos[0] - last_click_pos[0]
        dy = pos[1] - last_click_pos[1]
        dist = dx*dx + dy*dy
        time_ok = (now - last_click_time) <= DOUBLE_CLICK_INTERVAL
        # Double-click if within time AND either the same logical card index
        # was clicked twice, or the pixel distance between clicks is small.
        if time_ok and ((clicked_target_index is not None and clicked_target_index == last_clicked_card_index) or dist <= DOUBLE_CLICK_DIST_SQ):
            is_double = True
    except Exception:
        is_double = False

    # Update last click info for next time
    last_click_time = now
    last_click_pos = pos
    last_clicked_card_index = clicked_target_index

    # 1) 最優先: カード拡大の解除または(拡大クリックでの発動)
    if enlarged_card_index is not None and 0 <= enlarged_card_index < len(getattr(game, 'player').hand.cards):
        # compute enlarged rect same as drawing
        enlarged_w = 300
        enlarged_h = 420
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2
        er = pygame.Rect(enlarged_x, enlarged_y, enlarged_w, enlarged_h)
        if er.collidepoint(pos):
            # Clicking inside enlarged card: activation behavior depends on selected mode.
            # - 'click_enlarged': single click activates
            # - 'double_click': only a double-click activates
            should_activate = False
            if gimmick_activation_mode == 'click_enlarged':
                should_activate = True
            elif gimmick_activation_mode == 'double_click' and is_double:
                should_activate = True

            if should_activate:
                idx = enlarged_card_index
                # try to play card idx (reuse key-press logic)
                # pending/promote checks are done in play_card; but guard similar to key handler
                if chess.promotion_pending is not None:
                    # ignore; promotion selection shouldn't be triggered here
                    pass
                else:
                    if getattr(game, 'pending', None) is not None:
                        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
                    elif not getattr(game, 'turn_active', False):
                        msg = "ターンが開始されていませんTキーでターンを開始してください"
                        game.log.append(msg)
                        try:
                            notice_msg = msg
                            notice_until = _ct_time.time() + 1.0
                        except Exception:
                            pass
                    else:
                        try:
                            ok, m = game.play_card(idx)
                            if not ok:
                                game.log.append(m)
                            else:
                                _debug_mark_card_played()
                                try:
                                    log_scroll_offset = 0
                                except Exception:
                                    pass
                        except Exception:
                            game.log.append("カード使用に失敗しました。")
                # close enlarged after activation/click
                enlarged_card_index = None
                enlarged_card_scale = 1.0
                enlarged_card_mouse_y = None
                return
            else:
                # Not activating (e.g. double-click mode but this was a single click): just close overlay
                enlarged_card_index = None
                enlarged_card_name = None
                enlarged_card_scale = 1.0
                enlarged_card_mouse_y = None
                return
        # clicking anywhere when enlarged closes it
        enlarged_card_index = None
        enlarged_card_name = None
        enlarged_card_scale = 1.0
        enlarged_card_mouse_y = None
        return
    elif enlarged_card_name is not None:
        # for non-hand enlarged name (grave, etc.), a click closes the overlay
        enlarged_card_index = None
        enlarged_card_name = None
        enlarged_card_scale = 1.0
        enlarged_card_mouse_y = None
        return

    # 2) 次点: ラベルのクリックで墓地/相手手札の開閉（互いに排他）
    if grave_label_rect and grave_label_rect.collidepoint(pos):
        show_grave = not show_grave
        if show_grave:
            show_opponent_hand = False
        return
    if opponent_hand_rect and opponent_hand_rect.collidepoint(pos):
        show_opponent_hand = not show_opponent_hand
        if show_opponent_hand:
            show_grave = False
        return

    # 3) 最後に: オーバーレイ表示中は領域外クリックで閉じる（内部クリックは現状どおり）
    if show_grave:
        overlay_w = 600
        overlay_h = 500
        overlay_x = (W - overlay_w) // 2
        overlay_y = (H - overlay_h) // 2
        overlay_rect = pygame.Rect(overlay_x, overlay_y, overlay_w, overlay_h)
        if not overlay_rect.collidepoint(pos):
            show_grave = False
            return
        # オーバーレイ内のカードクリックで拡大表示（トグル）
        if grave_card_rects:
            for rect, card_name in grave_card_rects:
                if rect.collidepoint(pos):
                    if enlarged_card_name == card_name:
                        enlarged_card_name = None
                        enlarged_card_scale = 1.0
                        enlarged_card_mouse_y = None
                    else:
                        enlarged_card_name = card_name
                        enlarged_card_scale = 1.0
                        enlarged_card_mouse_y = None
                    return
        return

    if show_opponent_hand:
        overlay_w = 600
        overlay_h = 400
        overlay_x = (W - overlay_w) // 2
        overlay_y = (H - overlay_h) // 2
        overlay_rect = pygame.Rect(overlay_x, overlay_y, overlay_w, overlay_h)
        if not overlay_rect.collidepoint(pos):
            show_opponent_hand = False
            return
        return

    # 左パネルの『ターン開始』ボタン
    if start_turn_rect and start_turn_rect.collidepoint(pos):
        attempt_start_turn()
        return
    
    # 保留中の確認（ボタン）
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'confirm':
        if confirm_yes_rect and confirm_yes_rect.collidepoint(pos):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                # 墓地ルーレットの確認「はい」→カードを実際に消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除、墓地へ
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。墓地が空のため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_second_lightning_overwrite':
                # 迅雷2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_second_storm_overwrite':
                # 暴風2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_heat_no_frozen':
                # 灼熱で凍結駒がない場合の確認「はい」→カードを消費して墓地へ
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。凍結駒がないため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                else:
                    game.log.append("確認: はい → 効果なし")
            else:
                # その他の確認（通常の墓地ルーレット実行など）
                game.log.append("確認: はい")
                # 保留されていた効果を実行
                if game.pending.info.get('execute_on_confirm'):
                    hand_idx = game.pending.info.get('hand_index')
                    if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                        # 墓地が空でない場合の墓地ルーレット実行
                        import random
                        if game.player.graveyard:
                            idx = random.randrange(len(game.player.graveyard))
                            recovered = game.player.graveyard.pop(idx)
                            game.player.hand.add(recovered)
                            game.log.append(f"墓地から『{recovered.name}』を回収。")
            game.pending = None
            return
        if confirm_no_rect and confirm_no_rect.collidepoint(pos):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            elif confirm_id == 'confirm_heat_no_frozen':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            return

    # 灼熱の二択ボタンのクリック処理（保留が heat_choice のとき）
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'heat_choice':
        if heat_choice_unfreeze_rect and heat_choice_unfreeze_rect.collidepoint(pos):
            # 選択: 自分の凍結駒を解除 -> まず凍結駒の存在確認
            frozen = getattr(game, 'frozen_pieces', {})
            my_frozen_pieces = []
            # assume human player controls 'white'
            own_color = 'white'
            for p in chess.pieces:
                try:
                    is_fz = (p.color == own_color) and (((id(p) in frozen) and frozen.get(id(p), 0) > 0) or (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0))
                except Exception:
                    is_fz = (p.color == own_color) and (id(p) in frozen and frozen.get(id(p), 0) > 0)
                if is_fz:
                    my_frozen_pieces.append(p)

            if not my_frozen_pieces:
                # 凍結駒がない場合は警告表示（カードはまだ消費していない）
                game.pending = PendingAction(kind='confirm', info={
                    'id': 'confirm_heat_no_frozen',
                    'message': '凍結駒がありません。\nカードを使用しますか？',
                    'hand_index': game.pending.info.get('hand_index')
                })
                return
            else:
                # 凍結駒がある場合はカードを消費してから処理
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    # card usage already logged by game.play_card(); avoid duplicate log
                    _debug_mark_card_played()
                game.pending = PendingAction(kind='target_piece_unfreeze', info={'note': '自分の凍結駒を選択してください'})
                return
        if heat_choice_block_rect and heat_choice_block_rect.collidepoint(pos):
            # 選択: 複数マス封鎖へ（カードを消費してから）
            hand_idx = game.pending.info.get('hand_index')
            if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                card = game.player.hand.cards[hand_idx]
                game.player.spend_pp(card.cost)
                game.player.hand.remove_at(hand_idx)
                game.player.graveyard.append(card)
                # card usage already logged by game.play_card(); avoid duplicate log
                _debug_mark_card_played()
            info = {'turns': game.pending.info.get('turns', 2), 'max_tiles': game.pending.info.get('max_tiles', 3), 'selected': [], 'for_color': 'black'}
            game.pending = PendingAction(kind='target_tiles_multi', info=info)
            return
    
    # カードのクリック判定（優先）
    for rect, idx in card_rects:
        if rect.collidepoint(pos):
            # If double-click activation mode is selected, a double-click on the small card
            # should attempt to play it immediately. Otherwise, toggle enlarged view.
            if gimmick_activation_mode == 'double_click' and is_double:
                # Attempt to play the card directly
                if chess.promotion_pending is not None:
                    # ignore activation during promotion selection
                    pass
                else:
                    if getattr(game, 'pending', None) is not None:
                        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
                    elif not getattr(game, 'turn_active', False):
                        msg = "ターンが開始されていませんTキーでターンを開始してください"
                        game.log.append(msg)
                        try:
                            notice_msg = msg
                            notice_until = _ct_time.time() + 1.0
                        except Exception:
                            pass
                    else:
                        try:
                            ok, m = game.play_card(idx)
                            if not ok:
                                game.log.append(m)
                            else:
                                _debug_mark_card_played()
                                try:
                                    log_scroll_offset = 0
                                except Exception:
                                    pass
                        except Exception:
                            game.log.append("カード使用に失敗しました。")
                return
            # 閲覧（拡大表示）はターン開始前でも許可する
            if enlarged_card_index == idx:
                enlarged_card_index = None
                enlarged_card_scale = 1.0
                enlarged_card_mouse_y = None
            else:
                enlarged_card_index = idx
                enlarged_card_scale = 1.0
                enlarged_card_mouse_y = None
            return

    # プロモーション選択オーバーレイクリック対応
    if chess.promotion_pending is not None and hasattr(draw_panel, 'promo_rects'):
        for r, o in draw_panel.promo_rects:
            if r.collidepoint(pos):
                # chess.rulesモジュールでプロモーション処理を実行
                try:
                    success = chess_rules.handle_promotion_selection(chess, game, o)
                    if not success:
                        # フォールバック: 従来の処理
                        piece = chess.promotion_pending.get('piece')
                        if piece is not None:
                            piece.name = o
                            game.log.append(f"昇格: ポーンを{o}に昇格させました。")
                        chess.promotion_pending = None
                except Exception:
                    # chess_rulesモジュールが利用できない場合、従来のロジックを実行
                    piece = chess.promotion_pending.get('piece')
                    if piece is not None:
                        piece.name = o
                        game.log.append(f"昇格: ポーンを{o}に昇格させました。")
                    chess.promotion_pending = None
                # clear selection/highlights just in case
                selected_piece = None
                highlight_squares = []
                return

    # 盤面クリック判定 (draw_panel と同じ配置計算を行う)
    # Use the same compute_layout helper as draw_panel so click mapping matches rendering
    layout = compute_layout(W, H)
    board_left = layout['board_left']
    board_top = layout['board_top']
    board_size = layout['board_size']
    square_w = board_size // 8
    square_h = square_w

    board_rect = pygame.Rect(board_left, board_top, board_size, board_size)
    if board_rect.collidepoint(pos) and not game_over:
        # Prevent any piece selection/movement until the card-game turn has started.
        # The card system requires the player to press [T] to start the turn; until
        # then chess pieces should not be movable.
        if not getattr(game, 'turn_active', False):
            msg = "ターンが開始されていませんTキーでターンを開始してください"
            game.log.append(msg)
            try:
                notice_msg = msg
                notice_until = _ct_time.time() + 1.0
            except Exception:
                pass
            return
        col = (pos[0] - board_left) // square_w
        row = (pos[1] - board_top) // square_h
        # bounds safety
        col = int(max(0, min(7, col)))
        row = int(max(0, min(7, row)))

        clicked = get_piece_at(row, col)
        # If a card effect is waiting for a tile/piece target, handle it here first
        if getattr(game, 'pending', None) is not None:
            if game.pending.kind == 'target_tile':
                # require empty tile
                if clicked is None:
                    turns = game.pending.info.get('turns', 2)
                    # assume card used by player -> applies to opponent color
                    applies_to = game.pending.info.get('for_color', 'black')
                    # Determine source color
                    source_color = 'white' if applies_to == 'black' else 'black'
                    # Use apply_blocked_tile to respect iron wall
                    blocked = game.apply_blocked_tile((row, col), turns, applies_to, source_color, '灼熱')
                    if blocked:
                        try:
                            play_heat_gif_at(row, col)
                        except Exception:
                            pass
                        game.log.append(f"『灼熱』を使用しました: {(row,col)} を中心に3x3の範囲を {turns} ターン封鎖")
                        game.log.append(f"『灼熱』による封鎖: {(row,col)} を {turns} ターン封鎖 (対象: {applies_to})")
                    game.pending = None
                else:
                    game.log.append("そのマスは空ではありません。別のマスを選んでください。")
                    return
            elif getattr(game, 'pending', None) is not None and game.pending.kind == 'target_tiles_multi':
                # allow selecting up to max_tiles empty tiles; selection toggles and BLOCKING
                # only happens when player has selected max_tiles tiles.
                if clicked is None:
                    sel = game.pending.info.get('selected', [])
                    tmax = game.pending.info.get('max_tiles', 3)
                    if (row, col) in sel:
                        # toggle off
                        sel.remove((row, col))
                        game.pending.info['selected'] = sel
                        game.log.append(f"『灼熱』: 封鎖候補から {(row,col)} を解除 ({len(sel)}/{tmax})")
                        return
                    else:
                        # add if room
                        if len(sel) >= tmax:
                            game.log.append(f"選択は最大 {tmax} マスまでです。不要な選択を先に解除してください。")
                            return
                        sel.append((row, col))
                        try:
                            play_heat_gif_at(row, col)
                        except Exception:
                            pass
                        game.pending.info['selected'] = sel
                        game.log.append(f"『灼熱』: 封鎖候補に {(row,col)} を追加 ({len(sel)}/{tmax})")
                        # APPLY only when reached required count
                        if len(sel) >= tmax:
                            turns = game.pending.info.get('turns', 2)
                            applies_to = game.pending.info.get('for_color', 'black')
                            source_color = 'white' if applies_to == 'black' else 'black'
                            blocked_count = 0
                            for (r, c) in sel:
                                if game.apply_blocked_tile((r, c), turns, applies_to, source_color, '灼熱'):
                                    blocked_count += 1
                            if blocked_count > 0:
                                game.log.append(f"『灼熱』を使用しました: {blocked_count}マスを {turns} ターン封鎖")
                            game.pending = None
                            game.log.append(f"『灼熱』による封鎖: {sel} を {turns} ターン封鎖 (対象: {applies_to})")
                            game.pending = None
                        return
                else:
                    game.log.append("そのマスは空ではありません。別のマスを選んでください。")
                    return
            elif getattr(game, 'pending', None) is not None and game.pending.kind == 'target_piece_unfreeze':
                # must select one own frozen piece to unfreeze
                # assume player controls white pieces
                player_color = 'white'
                
                # Debug: Show what was clicked
                if clicked is None:
                    game.log.append("そのマスには駒がありません。凍結している自分の駒を選択してください。")
                    return
                
                clicked_color = None
                try:
                    clicked_color = clicked.color
                except Exception:
                    try:
                        clicked_color = clicked.get('color') if clicked is not None else None
                    except Exception:
                        clicked_color = None
                
                if clicked_color != player_color:
                    game.log.append("自分の駒を選択してください。")
                    return
                
                # Get piece ID
                pid = None
                try:
                    pid = id(clicked)
                except Exception:
                    try:
                        pid = clicked.get('id')
                    except Exception:
                        pass
                
                if pid is None:
                    game.log.append("駒の識別に失敗しました。もう一度お試しください。")
                    return
                
                # Check if piece is frozen
                is_frozen = False
                frozen_map = getattr(game, 'frozen_pieces', {})
                
                # Check both frozen_pieces dict and frozen_turns attribute
                if pid in frozen_map and frozen_map.get(pid, 0) > 0:
                    is_frozen = True
                elif hasattr(clicked, 'frozen_turns') and getattr(clicked, 'frozen_turns', 0) > 0:
                    is_frozen = True
                
                if not is_frozen:
                    try:
                        piece_name = clicked.name
                    except Exception:
                        piece_name = clicked.get('name', '駒') if clicked is not None else '駒'
                    game.log.append(f"その駒（{piece_name}）は凍結されていません。凍結している自分の駒を選択してください。")
                    return
                
                # Unfreeze the piece
                # Remove from frozen_pieces dictionary
                if pid in frozen_map:
                    try:
                        del frozen_map[pid]
                    except Exception:
                        pass
                
                # Clear frozen_turns attribute on the piece object
                if hasattr(clicked, 'frozen_turns'):
                    try:
                        clicked.frozen_turns = 0
                    except Exception:
                        pass
                
                try:
                    name = clicked.name
                except Exception:
                    name = clicked.get('name', str(clicked)) if clicked is not None else '駒'
                
                game.log.append(f"凍結解除: {name} の凍結を解除しました。")
                game.pending = None
                return
            elif getattr(game, 'pending', None) is not None and game.pending.kind == 'target_piece':
                # must select an opponent piece
                # assume player controls white
                player_color = 'white'
                # clicked may be a Piece object or dict; normalize check
                clicked_color = None
                try:
                    clicked_color = clicked.color
                except Exception:
                    try:
                        clicked_color = clicked.get('color') if clicked is not None else None
                    except Exception:
                        clicked_color = None
                if clicked is not None and clicked_color is not None and clicked_color != player_color:
                    turns = game.pending.info.get('turns', 1)
                    # Prefer to record the frozen state on the canonical engine piece
                    # so engine-level checks reliably detect it. Try to look up the
                    # engine Piece at the clicked coordinates.
                    tr = getattr(clicked, 'row', None)
                    tc = getattr(clicked, 'col', None)
                    try:
                        if tr is None and isinstance(clicked, dict):
                            tr = clicked.get('row')
                        if tc is None and isinstance(clicked, dict):
                            tc = clicked.get('col')
                    except Exception:
                        pass
                    engine_piece = None
                    try:
                        engine_piece = chess.get_piece_at(int(tr), int(tc)) if (tr is not None and tc is not None) else None
                    except Exception:
                        engine_piece = None
                    # Use game.apply_freeze_piece so iron-wall checks run consistently
                    try:
                        src_color = game.pending.info.get('source_color') if game.pending and isinstance(game.pending.info, dict) else None
                    except Exception:
                        src_color = None
                    try:
                        src_name = game.pending.info.get('source_card_name') if game.pending and isinstance(game.pending.info, dict) else None
                    except Exception:
                        src_name = None
                    target_obj = engine_piece if engine_piece is not None else clicked
                    try:
                        applied = game.apply_freeze_piece(target_obj, turns, target_color=('black' if player_color == 'white' else 'white'), source_color=src_color, source_card_name=src_name)
                    except Exception:
                        applied = False
                    if not applied:
                        # apply_freeze_piece already logs iron-wall messages; clear pending
                        game.pending = None
                    else:
                        target_for_log = engine_piece if engine_piece is not None else clicked
                        try:
                            name = getattr(target_for_log, 'name', None)
                            if name is None and isinstance(target_for_log, dict):
                                name = target_for_log.get('name')
                            if name is None:
                                name = str(target_for_log)
                        except Exception:
                            name = '駒'
                        game.log.append(f"凍結: {name} を {turns} ターン凍結")
                    # play ice GIF on the target square
                    try:
                        # clicked may be object or dict
                        tr = getattr(clicked, 'row', None)
                        tc = getattr(clicked, 'col', None)
                        if tr is None:
                            tr = clicked.get('row') if isinstance(clicked, dict) else None
                        if tc is None:
                            tc = clicked.get('col') if isinstance(clicked, dict) else None
                        if tr is not None and tc is not None:
                            play_ic_gif_at(int(tr), int(tc))
                    except Exception:
                        pass
                    game.pending = None
                else:
                    game.log.append("相手の駒を選んでください。")
                return
        # Normal piece selection / move handling
        if selected_piece is None:
            # If the clicked piece is frozen, play the ice GIF at that square as feedback
            try:
                is_clicked_frozen = False
                try:
                    frozen_map = getattr(game, 'frozen_pieces', {})
                    is_clicked_frozen = (clicked is not None) and ((id(clicked) in frozen_map and frozen_map.get(id(clicked), 0) > 0) or (hasattr(clicked, 'frozen_turns') and getattr(clicked, 'frozen_turns', 0) > 0))
                except Exception:
                    is_clicked_frozen = (clicked is not None) and (id(clicked) in getattr(game, 'frozen_pieces', {}))
                if is_clicked_frozen:
                    try:
                        play_ic_gif_at(row, col)
                    except Exception:
                        pass
                    # Show short telop informing player the piece is frozen (same area as other notices)
                    try:
                        msg = "凍結しているため動けません"
                        game.log.append(msg)
                        notice_msg = msg
                        notice_until = _ct_time.time() + 1.0
                    except Exception:
                        pass
                    # Do not select a frozen piece
                    return
            except Exception:
                pass
            if clicked and (getattr(clicked, 'color', None) == chess_current_turn or (isinstance(clicked, dict) and clicked.get('color') == chess_current_turn)):
                selected_piece = clicked
                highlight_squares = get_valid_moves(clicked)
        else:
            if (row, col) in highlight_squares:
                # Enforce one chess move per card-game turn unless player has extra_moves_this_turn
                try:
                    moved_flag = getattr(game, 'player_moved_this_turn', False)
                    extra = getattr(game.player, 'extra_moves_this_turn', 0)
                except Exception:
                    moved_flag = False
                    extra = 0
                # 反撃チェックのログ用に事前状態を取得
                try:
                    sel_color = getattr(selected_piece, 'color', selected_piece.get('color'))
                except Exception:
                    sel_color = 'white'
                try:
                    pre_self_in_check = is_in_check(chess.pieces, sel_color)
                except Exception:
                    pre_self_in_check = False
                try:
                    if sel_color == 'white':
                        lightning_active_now = getattr(game, 'player_consecutive_turns', 0) > 0
                    else:
                        lightning_active_now = globals().get('ai_consecutive_turns', 0) > 0
                except Exception:
                    lightning_active_now = False
                if chess_current_turn == 'white' and getattr(game, 'turn_active', False):
                    if moved_flag and extra <= 0:
                        game.log.append("このターンは既に駒を動かしました。次のターン開始まで待つか、カードで追加行動を付与してください。")
                        return
                # Apply the move
                # ログ用にポスト状態をシミュレート
                try:
                    post_sim = simulate_move(selected_piece, row, col)
                except Exception:
                    post_sim = None
                apply_move(selected_piece, row, col)
                # Consume storm jump effect after the player's next move (whether used or not)
                try:
                    if getattr(game.player, 'next_move_can_jump', False):
                        game.player.next_move_can_jump = False
                        game.log.append("暴風効果: 次の移動でのジャンプ可能を消費しました。")
                except Exception:
                    pass
                # [DEBUG] カード直後のみ許可モードのフラグを消費
                try:
                    if globals().get('DEBUG_COUNTER_CHECK_CARD_MODE', False) and getattr(game, '_debug_last_action_was_card', False):
                        setattr(game, '_debug_last_action_was_card', False)
                        try:
                            logger.debug("カード使用扱いフラグを消費しました。")
                        except Exception:
                            pass
                except Exception:
                    pass
                # 反撃チェック手の実行をログ
                try:
                    if post_sim is not None and pre_self_in_check and lightning_active_now:
                        opp_color = 'black' if sel_color == 'white' else 'white'
                        if is_in_check(post_sim, sel_color) and is_in_check(post_sim, opp_color):
                            game.log.append("迅雷: 相手にチェックを与える反撃手を実行（同時チェック判定へ）。")
                except Exception:
                    pass
                # If it was player's move, consume extra move or mark moved
                if chess_current_turn == 'white' and getattr(game, 'turn_active', False):
                    try:
                        if getattr(game.player, 'extra_moves_this_turn', 0) > 0:
                            game.player.extra_moves_this_turn -= 1
                            # keep turn active while extra moves remain
                        else:
                            game.player_moved_this_turn = True
                            # consume the active turn so player must press T next time
                            game.turn_active = False
                    except Exception:
                        # defensive: set flag
                        game.player_moved_this_turn = True
                        game.turn_active = False
                # log safely for both object and dict styles
                try:
                    name = selected_piece.name
                except Exception:
                    name = selected_piece.get('name', str(selected_piece)) if isinstance(selected_piece, dict) else str(selected_piece)
                log_msg = f"{name} を {(row,col)} へ移動"
                chess_log.append(log_msg)
                logger.debug("プレイヤー駒移動ログ追加: %s, master_log size=%d", log_msg, len(master_log))
                
                # 駒移動直後はキング存在チェック（即座に勝敗判定）
                # 迅雷使用中もそうでない場合も、駒移動直後に判定
                if not game_over:
                    white_king_exists = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                    black_king_exists = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                    
                    # 両キング取得テストモード（F9）の場合は即座に終了しない
                    if globals().get('dual_king_capture_test', False):
                        if not white_king_exists and not black_king_exists:
                            # 両方のキングが取られた場合のみゲーム終了（引き分け）
                            game_over = True
                            game_over_winner = 'draw'
                            game.log.append("両者のキングが取られました。引き分け。")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                            globals()['dual_king_capture_test'] = False
                            globals()['first_king_captured'] = None
                        elif not white_king_exists:
                            # 白Kが取られた
                            if globals().get('first_king_captured') is None:
                                globals()['first_king_captured'] = 'white'
                                game.log.append("[テストモード] 白のキングが取られました。ゲームを続行します...")
                            else:
                                # 2つ目のキング取得
                                game_over = True
                                game_over_winner = 'draw'
                                game.log.append("両者のキングが取られました。引き分け。")
                                globals()['dual_king_capture_test'] = False
                                globals()['first_king_captured'] = None
                        elif not black_king_exists:
                            # 黒Kが取られた
                            if globals().get('first_king_captured') is None:
                                globals()['first_king_captured'] = 'black'
                                game.log.append("[テストモード] 黒のキングが取られました。ゲームを続行します...")
                            else:
                                # 2つ目のキング取得
                                game_over = True
                                game_over_winner = 'draw'
                                game.log.append("両者のキングが取られました。引き分け。")
                                globals()['dual_king_capture_test'] = False
                                globals()['first_king_captured'] = None
                    else:
                        # 通常モード: 即座に勝敗判定
                        if not white_king_exists:
                            # 白キングが取られた → プレイヤーの負け
                            # 「負けるわけないだろwww」の発動チェック
                            if game.check_no_lose_trigger('white'):
                                # 発動条件を満たしている
                                game.log.append("「負けるわけないだろwww」の発動条件を満たしています...")
                                if game.trigger_no_lose('white'):
                                    # 発動成功 → 盤面をリセット
                                    chess.pieces[:] = chess.create_pieces()
                                    chess.en_passant_target = None
                                    # プロモーション状態をクリア
                                    try:
                                        chess_rules.clear_promotion_state(chess)
                                    except Exception:
                                        chess.promotion_pending = None
                                    
                                    # ゲーム状態フラグをリセット
                                    global simul_check_active, simul_white_result, simul_black_result
                                    simul_check_active = False
                                    simul_white_result = 'none'
                                    simul_black_result = 'none'
                                    
                                    # ターンをプレイヤーに戻す
                                    chess_current_turn = 'white'
                                    
                                    # カードゲームターンもリセット
                                    game.turn_active = False
                                    game.player_moved_this_turn = False
                                    
                                    game.log.append("盤面が初期状態にリセットされました！")
                                    game.log.append("ゲームを続行します。")
                                    
                                    # ゲームオーバーフラグは立てない
                                    # 選択状態をクリア
                                    selected_piece = None
                                    highlight_squares = []
                                else:
                                    # 発動失敗（通常通り負け）
                                    # 手札発動が不可設定の場合、自動発動を試行
                                    if hasattr(game, 'can_auto_no_lose') and game.can_auto_no_lose('white'):
                                        if game.auto_trigger_no_lose('white'):
                                            # pending処理により盤面リセット・続行
                                            selected_piece = None
                                            highlight_squares = []
                                            # ゲームオーバーにはしない
                                        else:
                                            game_over = True
                                            game_over_winner = 'black'
                                            game.log.append("「負けるわけないだろwww」の自動発動に失敗しました。")
                                            game.log.append("YOU LOSE！黒の勝利！")
                                            # ゲームオーバー時は昇格処理をクリア
                                            chess.promotion_pending = None
                                    else:
                                        game_over = True
                                        game_over_winner = 'black'
                                        game.log.append("「負けるわけないだろwww」の発動に失敗しました。")
                                        game.log.append("YOU LOSE！黒の勝利！")
                                        # ゲームオーバー時は昇格処理をクリア
                                        chess.promotion_pending = None
                            else:
                                # 発動条件を満たしていない（通常通り負け）
                                # 自動発動の緩和条件で救済できるか試行
                                if hasattr(game, 'can_auto_no_lose') and game.can_auto_no_lose('white'):
                                    if game.auto_trigger_no_lose('white'):
                                        selected_piece = None
                                        highlight_squares = []
                                        # 続行（ゲームオーバーにしない）
                                    else:
                                        game_over = True
                                        game_over_winner = 'black'
                                        game.log.append("YOU LOSE！黒の勝利！")
                                        # ゲームオーバー時は昇格処理をクリア
                                        chess.promotion_pending = None
                                else:
                                    game_over = True
                                    game_over_winner = 'black'
                                    game.log.append("YOU LOSE！黒の勝利！")
                                    # ゲームオーバー時は昇格処理をクリア
                                    chess.promotion_pending = None
                        elif not black_king_exists:
                            game_over = True
                            game_over_winner = 'white'
                            game.log.append("YOU WIN！白の勝利")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                
                # ゲーム終了していなければターン切替
                if not game_over:
                    # ターン切替
                    if chess_current_turn == 'white':
                        # If player has consecutive-turns remaining (from '迅雷'), consume one and keep the turn
                        cct = getattr(game, 'player_consecutive_turns', 0)
                        if cct and cct > 0:
                            try:
                                game.player_consecutive_turns -= 1
                            except Exception:
                                setattr(game, 'player_consecutive_turns', max(0, cct-1))
                            # keep chess_current_turn as white so player moves again immediately
                            chess_current_turn = 'white'
                            # reset per-move flags so player can move again
                            game.player_moved_this_turn = False
                            # ensure turn_active remains True so card plays are allowed
                            game.turn_active = True
                            game.log.append("迅雷効果: プレイヤーの連続ターンを1つ消費しました。")
                        else:
                            chess_current_turn = 'black'
                            # 白の手番終了後、黒キングがチェック状態か確認（表示用なので凍結駒も含む）
                            try:
                                if is_in_check_for_display(chess.pieces, 'black'):
                                    game.log.append("⚠ 黒キングがチェック状態です！")
                            except Exception:
                                pass
                            # 白の手番が終了したため、白に適用されている時間制限付き状態を減衰させる
                            # （例: 氷結や封鎖などのターン消費をここで進める）
                            try:
                                game.decay_statuses('white')
                            except Exception:
                                pass
                    else:
                        chess_current_turn = 'white'
                        # 黒の手番終了後、白キングがチェック状態か確認（表示用なので凍結駒も含む）
                        try:
                            if is_in_check_for_display(chess.pieces, 'white'):
                                game.log.append("⚠ 白キングがチェック状態です！")
                        except Exception:
                            pass
                        # 2ターン目以降: プレイヤーの手番になったらテロップ表示（Tキー不要でテロップのみ）
                        try:
                            if getattr(game, 'turn', 0) >= 1 and not getattr(game, 'turn_active', False) and getattr(game, 'pending', None) is None:
                                try:
                                    turn_telop_msg = "YOUR TURN"
                                    turn_telop_until = _ct_time.time() + 1.0
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    # クリア
                    selected_piece = None
                highlight_squares = []
                # AI の手
                if chess_current_turn == 'black':
                    import time
                    global cpu_wait, cpu_wait_start
                    # プレイヤーターン終了の区切り線を表示（横いっぱいに「─」で埋める）
                    game.log.append("─── 自分のターン終了 ───")
                    cpu_wait = True
                    cpu_wait_start = time.time()
            else:
                # If the player clicked a square that is blocked for their color, show a notice
                try:
                    # Use centralized tile-blocked check so owner-aware logic applies
                    try:
                        if getattr(game, 'is_tile_blocked_for', None) is not None and game.is_tile_blocked_for((row, col), chess_current_turn):
                            msg = "灼熱状態なので通れません"
                            game.log.append(msg)
                            try:
                                notice_msg = msg
                                notice_until = _ct_time.time() + 1.0
                            except Exception:
                                pass
                            return
                    except Exception:
                        # Fallback to legacy mapping
                        bmap = getattr(game, 'blocked_tiles', {}) or {}
                        bowner = getattr(game, 'blocked_tiles_owner', {}) or {}
                        if (row, col) in bmap:
                            owner = bowner.get((row, col))
                            if owner == chess_current_turn:
                                msg = "灼熱状態なので通れません"
                                game.log.append(msg)
                                try:
                                    notice_msg = msg
                                    notice_until = _ct_time.time() + 1.0
                                except Exception:
                                    pass
                                return
                except Exception:
                    pass
                # select another own piece, toggle deselect if clicking the same piece, or cancel
                def _same_piece(a, b):
                    if a is None or b is None:
                        return False
                    try:
                        if a is b:
                            return True
                    except Exception:
                        pass
                    # compare core attributes for object- or dict-style pieces
                    try:
                        ar = getattr(a, 'row', None); ac = getattr(a, 'col', None)
                        an = getattr(a, 'name', None); acol = getattr(a, 'color', None)
                    except Exception:
                        ar = a.get('row') if isinstance(a, dict) else None
                        ac = a.get('col') if isinstance(a, dict) else None
                        an = a.get('name') if isinstance(a, dict) else None
                        acol = a.get('color') if isinstance(a, dict) else None
                    try:
                        br = getattr(b, 'row', None); bc = getattr(b, 'col', None)
                        bn = getattr(b, 'name', None); bcol = getattr(b, 'color', None)
                    except Exception:
                        br = b.get('row') if isinstance(b, dict) else None
                        bc = b.get('col') if isinstance(b, dict) else None
                        bn = b.get('name') if isinstance(b, dict) else None
                        bcol = b.get('color') if isinstance(b, dict) else None
                    return ar == br and ac == bc and an == bn and acol == bcol

                if clicked and _same_piece(clicked, selected_piece):
                    # clicking the already-selected piece -> deselect
                    selected_piece = None
                    highlight_squares = []
                elif clicked and (getattr(clicked, 'color', None) == chess_current_turn or (isinstance(clicked, dict) and clicked.get('color') == chess_current_turn)):
                    # select the newly clicked own piece
                    selected_piece = clicked
                    highlight_squares = get_valid_moves(clicked)
                else:
                    selected_piece = None
                    highlight_squares = []
        return


def main_loop():
    global log_scroll_offset, cpu_wait, cpu_wait_start, chess_current_turn, game_over, game_over_winner
    # Ensure window/display-related globals are declared before any use in this function
    global W, H, screen, play_bg_img, play_bg_surf
    # スクロール関連の初期化（ローカル扱いによるUnboundLocalErrorを防止）
    global dragging_scrollbar, drag_start_y, drag_start_offset, scrollbar_rect
    # カード拡大表示関連の変数
    global enlarged_card_index, enlarged_card_name, enlarged_card_scale, enlarged_card_mouse_y
    dragging_scrollbar = False
    drag_start_y = 0
    drag_start_offset = 0
    # scrollbar_rect は draw_panel 内で更新されるが、初期 None を明示
    scrollbar_rect = None
    
    # DEBUG: 開始時のデッキ情報をログ出力
    try:
        if game and hasattr(game, 'player') and hasattr(game.player, 'hand'):
            hand_cards = [c.name for c in game.player.hand.cards]
            logger.debug("main_loop started - initial hand=%s", hand_cards)
    except Exception as e:
        logger.debug("Error logging initial hand: %s", e)
    
    # Transition audio: stop title BGM and start gameplay BGM (MusMus-BGM-173.mp3).
    try:
        # ensure mixer available
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass
        # Switch to gameplay BGM using centralized helper
        try:
            set_bgm_mode('game')
        except Exception:
            pass
    except Exception:
        pass

    while True:
        try:
            W, H = _refresh_display_size_from_pygame()
        except Exception:
            try:
                W, H = screen.get_size()
            except Exception:
                pass
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                # Handle fullscreen toggle (F11 or Alt+Enter) before other key handling
                try:
                    mods = event.mod if hasattr(event, 'mod') else pygame.key.get_mods()
                    is_alt_enter = (event.key == pygame.K_RETURN and (mods & pygame.KMOD_ALT))
                except Exception:
                    is_alt_enter = False

                if event.key == pygame.K_F11 or is_alt_enter:
                    try:
                        # toggle state
                        is_fullscreen = not globals().get('is_fullscreen', False)
                        globals()['is_fullscreen'] = is_fullscreen
                        if is_fullscreen:
                            # remember current windowed size
                            try:
                                _prev_window_size = (W, H)
                                globals()['_prev_window_size'] = _prev_window_size
                            except Exception:
                                pass
                            # enter fullscreen with SCALED so surface scales to display
                            try:
                                screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.SCALED)
                            except Exception:
                                screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                        else:
                            # restore previous windowed size if available
                            try:
                                pw, ph = globals().get('_prev_window_size', (1200, 800))
                            except Exception:
                                pw, ph = (1200, 800)
                            try:
                                screen = pygame.display.set_mode((pw, ph), pygame.RESIZABLE | pygame.SCALED)
                            except Exception:
                                screen = pygame.display.set_mode((pw, ph), pygame.RESIZABLE)

                        # update globals for width/height using actual display size
                        try:
                            _refresh_display_size_from_pygame()
                        except Exception:
                            pass

                        try:
                            # notify ui.window helper if available
                            update_window_size()
                        except Exception:
                            pass

                        try:
                            # clear font cache in board renderer if present so text/layout recomputes
                            if hasattr(draw_board, 'font_cache'):
                                draw_board.font_cache.clear()
                        except Exception:
                            pass

                        try:
                            pygame.display.flip()
                        except Exception:
                            pass
                    except Exception:
                        # fallback to existing key handling
                        handle_keydown(event.key)
                else:
                    handle_keydown(event.key)
            elif event.type == pygame.VIDEORESIZE:
                # Window was resized (including maximize). Update globals and recreate screen surface.
                try:
                    # window/display globals are declared at function top
                    W, H = max(200, event.w), max(200, event.h)
                    # use SCALED flag when available to keep UI scaling consistent
                    try:
                        screen = pygame.display.set_mode((W, H), pygame.RESIZABLE | pygame.SCALED)
                    except Exception:
                        screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                    # update helper window state
                    try:
                        update_window_size()
                    except Exception:
                        pass
                    # refresh play background surface so it is rescaled next frame
                    try:
                        play_bg_img = play_bg_img
                        play_bg_surf = None
                    except Exception:
                        pass
                    # clear font cache used by board renderer so layout texts recalc
                    try:
                        if hasattr(draw_board, 'font_cache'):
                            draw_board.font_cache.clear()
                    except Exception:
                        pass
                except Exception:
                    # If resizing fails for any reason, ignore and continue with previous size
                    pass
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左クリック
                    # スクロールバーつまみのドラッグ開始判定
                    # overlayモジュールのhandle_scrollbar_drag_start関数を使用
                    try:
                        if not overlay.handle_scrollbar_drag_start(event.pos, show_log, scrollbar_rect, log_scroll_offset):
                            handle_mouse_click(event.pos)
                    except Exception:
                        # フォールバック: 従来の処理
                        if show_log and scrollbar_rect and scrollbar_rect.collidepoint(event.pos):
                            dragging_scrollbar = True
                            drag_start_y = event.pos[1]
                            drag_start_offset = log_scroll_offset
                        else:
                            handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    # overlayモジュールのhandle_scrollbar_drag_end関数を使用
                    try:
                        overlay.handle_scrollbar_drag_end()
                    except Exception:
                        # フォールバック: 従来の処理
                        dragging_scrollbar = False
            elif event.type == pygame.MOUSEMOTION:
                # overlayモジュールのhandle_scrollbar_motion関数を使用
                try:
                    log_scroll_offset = overlay.handle_scrollbar_motion(event.pos, show_log, scrollbar_rect, log_scroll_offset, _max_scroll)
                except Exception:
                    # フォールバック: 従来の処理
                    if dragging_scrollbar and show_log and scrollbar_rect:
                        # ドラッグ量に応じてスクロールオフセットを変更
                        dy = event.pos[1] - drag_start_y
                        # scrollbar_rectの高さを使って比率計算
                        if scrollbar_rect.height > 0 and _max_scroll > 0:
                            scroll_delta = dy * _max_scroll / scrollbar_rect.height
                            new_offset = drag_start_offset + scroll_delta
                            log_scroll_offset = int(max(0, min(new_offset, _max_scroll)))
            elif event.type == pygame.MOUSEWHEEL:
                # マウスホイール: 拡大表示中はカードの拡大縮小に割り当てる
                try:
                    if (enlarged_card_index is not None) or (enlarged_card_name is not None):
                        # event.y > 0 => 上スクロール => 拡大
                        enlarged_card_scale = max(0.5, min(2.5, enlarged_card_scale + (event.y * 0.1)))
                        # マウスベースの増分は無効化してジャンプ防止
                        enlarged_card_mouse_y = None
                    else:
                        # ログスクロール: 上スクロール=過去（オフセット+1）、下スクロール=最新側（オフセット-1）
                        if show_log:
                            if event.y > 0:  # 上スクロール -> 古いログへ
                                try:
                                    log_scroll_offset = min(_max_scroll, log_scroll_offset + 1)
                                except Exception:
                                    log_scroll_offset = log_scroll_offset + 1
                            elif event.y < 0:  # 下スクロール -> 新しいログへ
                                log_scroll_offset = max(0, log_scroll_offset - 1)
                except Exception:
                    # フォールバック: 元のログスクロールのみ行う（同じ方向定義を維持）
                    if show_log:
                        if event.y > 0:
                            try:
                                log_scroll_offset = min(_max_scroll, log_scroll_offset + 1)
                            except Exception:
                                log_scroll_offset = log_scroll_offset + 1
                        elif event.y < 0:
                            log_scroll_offset = max(0, log_scroll_offset - 1)

        # --- 自動処理: AI の保留昇格を即時解決 ---
        # どこかの効果でAI（黒）のポーンがプロモーション待ちになった場合、
        # プレイヤーUIに選択を押し付けないようここで自動解決する。
        try:
            pending_promo = getattr(chess, 'promotion_pending', None)
            if pending_promo is not None:
                promo_color = pending_promo.get('color', None)
                if promo_color is not None and promo_color != 'white':
                    promoted_piece = pending_promo.get('piece')
                    if promoted_piece is not None:
                        # 現状は簡易ヒューリスティックでクイーンに昇格
                        try:
                            promoted_piece.name = 'Q'
                        except Exception:
                            pass
                        try:
                            game.log.append(f"AI: ポーンをQに昇格させました。")
                        except Exception:
                            pass
                    # clear pending in all cases to avoid UI prompt
                    try:
                        chess.promotion_pending = None
                    except Exception:
                        pass
        except Exception:
            # 安全のため例外は無視して続行
            pass

        # チェック/同時チェックの監視と勝敗処理
        if globals().get('last_turn_color', None) != chess_current_turn:
            # 手番インデックス更新
            if chess_current_turn == 'white':
                globals()['white_turn_index'] = globals().get('white_turn_index', 0) + 1
            else:
                globals()['black_turn_index'] = globals().get('black_turn_index', 0) + 1
            globals()['last_turn_color'] = chess_current_turn

            # 白番に戻った際のテロップ表示（2ターン目以降）
            try:
                # 条件: 色が白に変わった、プレイヤーが既に1ターン以上開始している、
                # プロモーション選択や保留中のUIが無く、テロップを出すべきタイミング
                if chess_current_turn == 'white' and getattr(game, 'turn', 0) >= 1:
                    if getattr(chess, 'promotion_pending', None) is None and getattr(game, 'pending', None) is None:
                        try:
                            turn_telop_msg = "YOUR TURN"
                            turn_telop_until = _ct_time.time() + 1.0
                        except Exception:
                            pass
            except Exception:
                pass

            # 同時チェック中なら、その色の期限判定を行う
            if globals().get('simul_check_active', False):
                try:
                    # 同時チェック開始直後のターンでは判定しない（1手指すチャンスを与える）
                    # 開始ターンを記録して、次のターン開始時に判定する
                    if chess_current_turn == 'white' and globals().get('simul_white_result') == 'pending':
                        # 白の期限ターンを記録（まだ設定されていなければ、次の白番開始で判定）
                        if not globals().get('simul_white_deadline_turn'):
                            # 次の白番開始時に判定する（つまり今回はスキップ）
                            globals()['simul_white_deadline_turn'] = globals().get('white_turn_index', 0) + 1
                            game.log.append("同時チェック: 白は次の白番開始までにチェック解除が必要です。")
                        elif globals().get('white_turn_index', 0) >= globals().get('simul_white_deadline_turn', 0):
                            # 期限到達：チェック状態で成否を確定
                            if is_in_check(chess.pieces, 'white'):
                                globals()['simul_white_result'] = 'failed'
                                game.log.append("同時チェック: 白は期限までにチェックを解除できませんでした（失敗）。")
                            else:
                                globals()['simul_white_result'] = 'cleared'
                                game.log.append("同時チェック: 白はチェックを解除しました（成功）。")
                    elif chess_current_turn == 'black' and globals().get('simul_black_result') == 'pending':
                        # 黒の期限ターンを記録（まだ設定されていなければ、次の黒番開始で判定）
                        if not globals().get('simul_black_deadline_turn'):
                            globals()['simul_black_deadline_turn'] = globals().get('black_turn_index', 0) + 1
                            game.log.append("同時チェック: 黒は次の黒番開始までにチェック解除が必要です。")
                        elif globals().get('black_turn_index', 0) >= globals().get('simul_black_deadline_turn', 0):
                            # 期限到達：チェック状態で成否を確定
                            if is_in_check(chess.pieces, 'black'):
                                globals()['simul_black_result'] = 'failed'
                                game.log.append("同時チェック: 黒は期限までにチェックを解除できませんでした（失敗）。")
                            else:
                                globals()['simul_black_result'] = 'cleared'
                                game.log.append("同時チェック: 黒はチェックを解除しました（成功）。")
                except Exception:
                    pass

                # 双方結果が出たら決着
                wres = globals().get('simul_white_result')
                bres = globals().get('simul_black_result')
                if wres in ('cleared','failed') and bres in ('cleared','failed') and not game_over:
                    # 両者のキングの存在確認（取られていないか）
                    white_king_exists = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                    black_king_exists = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                    
                    # 両者のキングが取られている場合は無条件で引き分け（優先順位 最上位）
                    if not white_king_exists and not black_king_exists:
                        game_over = True
                        game_over_winner = 'draw'
                        game.log.append("同時チェック: 両者のキングが取られました。引き分け。")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                    # 白のキングのみ取られた場合は黒の勝利
                    elif not white_king_exists:
                        game_over = True
                        game_over_winner = 'black'
                        game.log.append("同時チェック: 白のキングが取られました。黒の勝利！")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                    # 黒のキングのみ取られた場合は白の勝利
                    elif not black_king_exists:
                        game_over = True
                        game_over_winner = 'white'
                        game.log.append("同時チェック: 黒のキングが取られました。白の勝利！")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                    # 両者のキングが残っている場合
                    elif white_king_exists and black_king_exists:
                        # 両者とも解除失敗の場合は引き分け
                        if wres == 'failed' and bres == 'failed':
                            game_over = True
                            game_over_winner = 'draw'
                            game.log.append("同時チェック: 両者とも解除できませんでした。引き分け。")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                        # 白のみ解除成功
                        elif wres == 'cleared' and bres == 'failed':
                            game_over = True
                            game_over_winner = 'white'
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                            game.log.append("同時チェック: 白のみ解除成功。白の勝利！")
                        # 黒のみ解除成功
                        elif wres == 'failed' and bres == 'cleared':
                            game_over = True
                            game_over_winner = 'black'
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                            game.log.append("同時チェック: 黒のみ解除成功。黒の勝利！")
                        else:
                            # 両者解除成功 → 通常続行
                            game.log.append("同時チェック: 両者解除成功。通常ルールに復帰します。")
                    if game_over:
                        # 終了したら状態クリア
                        globals()['simul_check_active'] = False
                        globals()['simul_white_deadline_turn'] = None
                        globals()['simul_black_deadline_turn'] = None
                    else:
                        # 続行の場合も状態をクリア
                        globals()['simul_check_active'] = False
                        globals()['simul_white_deadline_turn'] = None
                        globals()['simul_black_deadline_turn'] = None
                    globals()['simul_white_result'] = 'none'
                    globals()['simul_black_result'] = 'none'

        # --- 早期強制チェックメイト判定（simul_check中でも適用） ---
        if not game_over:
            try:
                white_in_check = is_in_check(chess.pieces, 'white')
                white_has_moves = has_legal_moves_with_cards('white')
                
                # 白がチェック中かつ合法手なし = チェックメイト
                if white_in_check and not white_has_moves:
                    game.log.append('[強制判定] 白チェックメイト検出（合法手なし）')
                    # 「負けるわけないだろwww」自動発動試行
                    if game.check_no_lose_trigger('white'):
                        game.log.append('[自動発動試行] チェックメイト直前: 条件OK')
                        if game.trigger_no_lose('white'):
                            game.log.append('[自動発動成功] 盤面リセット pending 設定')
                            # board_reset に任せるため game_over にしない
                        else:
                            game_over = True
                            game_over_winner = 'black'
                            game.log.append('[自動発動失敗] カード消費失敗。YOU LOSE！黒の勝利！')
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                    else:
                        # 条件不足の詳細をログ
                        try:
                            pp = getattr(game.player, 'pp_current', 'NA')
                            has_card = any(c.name == '負けるわけないだろwww' for c in game.player.hand.cards)
                            has_leech = any(c.name == '摂取' for c in game.player.hand.cards)
                            game.log.append(f'[自動発動不可] 条件不足(pp={pp}, カード={has_card}, 摂取={has_leech})')
                        except Exception:
                            pass
                        game_over = True
                        game_over_winner = 'black'
                        game.log.append('YOU LOSE！黒の勝利！（チェックメイト）')
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                    # 同時チェック状態をクリア
                    if globals().get('simul_check_active', False):
                        globals()['simul_check_active'] = False
                        globals()['simul_white_deadline_turn'] = None
                        globals()['simul_black_deadline_turn'] = None
                        globals()['simul_white_result'] = 'none'
                        globals()['simul_black_result'] = 'none'
            except Exception as e:
                game.log.append(f'[ERROR] 早期チェックメイト判定でエラー: {e}')

        # 新たに同時チェックに突入したか監視（カード使用や直前の手の結果で発生しうる）
        if not game_over:
            try:
                white_in_check = is_in_check(chess.pieces, 'white')
                black_in_check = is_in_check(chess.pieces, 'black')
                if white_in_check and black_in_check and not globals().get('simul_check_active', False):
                    globals()['simul_check_active'] = True
                    globals()['simul_white_result'] = 'pending'
                    globals()['simul_black_result'] = 'pending'
                    # 期限ターンをリセット（次のターン開始時に設定される）
                    globals()['simul_white_deadline_turn'] = None
                    globals()['simul_black_deadline_turn'] = None
                    # 期限は「次の自分の手番開始」。カウンタは手番開始検知で進むのでここではログのみ。
                    game.log.append("同時チェック状態に突入：両者は次の自分の手番開始までにチェック解除が必要です。")
            except Exception:
                pass

        # チェックメイト判定と勝利条件チェック
        if chess_current_turn == 'white':
            lightning_active = getattr(game, 'player_consecutive_turns', 0) > 0
        else:
            lightning_active = globals().get('ai_consecutive_turns', 0) > 0
        
        if not game_over:
            # キング取得判定: 迅雷使用中は常に、通常時は同時チェック中でなければ判定
            should_check_kings = lightning_active or not globals().get('simul_check_active', False)
            
            if should_check_kings:
                white_king = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                black_king = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                
                # 両キング取得テストモード（F9）の処理
                if globals().get('dual_king_capture_test', False):
                    # まず両者のキング不在を最優先で引き分け判定
                    if not white_king and not black_king:
                        game_over = True
                        game_over_winner = 'draw'
                        game.log.append("両者のキングが取られました。引き分け。")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                        # テストモードを終了
                        globals()['dual_king_capture_test'] = False
                        globals()['first_king_captured'] = None
                    elif not white_king:
                        # 白Kが取られた場合
                        if globals().get('first_king_captured') is None:
                            # 最初のキング取得
                            globals()['first_king_captured'] = 'white'
                            game.log.append("[テストモード] 白のキングが取られました。黒の手番を続けます...")
                        else:
                            # 2つ目のキングが取られた（黒Kは既に取られている）
                            game_over = True
                            game_over_winner = 'draw'
                            game.log.append("両者のキングが取られました。引き分け。")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                            globals()['dual_king_capture_test'] = False
                            globals()['first_king_captured'] = None
                    elif not black_king:
                        # 黒Kが取られた場合
                        if globals().get('first_king_captured') is None:
                            # 最初のキング取得
                            globals()['first_king_captured'] = 'black'
                            game.log.append("[テストモード] 黒のキングが取られました。白の手番を続けます...")
                        else:
                            # 2つ目のキングが取られた（白Kは既に取られている）
                            game_over = True
                            game_over_winner = 'draw'
                            game.log.append("両者のキングが取られました。引き分け。")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                            globals()['dual_king_capture_test'] = False
                            globals()['first_king_captured'] = None
                else:
                    # 通常モード: 既存の処理
                    # まず両者のキング不在を最優先で引き分け判定
                    if not white_king and not black_king:
                        game_over = True
                        game_over_winner = 'draw'
                        game.log.append("両者のキングが取られました。引き分け。")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                        if globals().get('simul_check_active', False):
                            globals()['simul_check_active'] = False
                            globals()['simul_white_deadline_turn'] = None
                            globals()['simul_black_deadline_turn'] = None
                            globals()['simul_white_result'] = 'none'
                            globals()['simul_black_result'] = 'none'
                    elif not white_king:
                        # 黒勝利（白キング捕獲）直前に自動発動試行
                        if game.check_no_lose_trigger('white'):
                            game.log.append("[自動発動試行] 白キング捕獲による敗北前: 条件OK")
                            if game.trigger_no_lose('white'):
                                # pending(board_reset)に任せるので敗北フラグは立てない
                                game.log.append("[自動発動成功] 『負けるわけないだろwww』による盤面リセットへ移行")
                            else:
                                game_over = True
                                game_over_winner = 'black'
                                game.log.append("[自動発動失敗] カード消費処理失敗。YOU LOSE！黒の勝利！")
                                # ゲームオーバー時は昇格処理をクリア
                                chess.promotion_pending = None
                        else:
                            # 発動条件NGの詳細を併せてログ
                            try:
                                pp = getattr(game.player, 'pp_current', 'NA')
                                has_card = any(c.name == '負けるわけないだろwww' for c in game.player.hand.cards)
                                has_leech = any(c.name == '摂取' for c in game.player.hand.cards)
                                game.log.append(f"[自動発動不可] 条件不足(pp={pp}, noLose={has_card}, 摂取={has_leech})")
                            except Exception:
                                pass
                            game_over = True
                            game_over_winner = 'black'
                            game.log.append("YOU LOSE！黒の勝利！")
                            # ゲームオーバー時は昇格処理をクリア
                            chess.promotion_pending = None
                        # 同時チェック状態をクリア
                        if globals().get('simul_check_active', False):
                            globals()['simul_check_active'] = False
                            globals()['simul_white_deadline_turn'] = None
                            globals()['simul_black_deadline_turn'] = None
                            globals()['simul_white_result'] = 'none'
                            globals()['simul_black_result'] = 'none'
                    elif not black_king:
                        game_over = True
                        game_over_winner = 'white'
                        game.log.append("YOU WIN！白の勝利")
                        # ゲームオーバー時は昇格処理をクリア
                        chess.promotion_pending = None
                        # 同時チェック状態をクリア
                        if globals().get('simul_check_active', False):
                            globals()['simul_check_active'] = False
                            globals()['simul_white_deadline_turn'] = None
                            globals()['simul_black_deadline_turn'] = None
                            globals()['simul_white_result'] = 'none'
                            globals()['simul_black_result'] = 'none'
                        globals()['simul_white_result'] = 'none'
                        globals()['simul_black_result'] = 'none'
        
        # チェックメイト／ステイルメイトの判定（chess.rulesモジュールに委譲）
        if not game_over and not globals().get('simul_check_active', False):
            try:
                is_over, winner = chess_rules.check_game_over_conditions(
                    game,
                    chess,
                    is_in_check_for_display,
                    has_legal_moves_with_cards,
                    globals().get('simul_check_active', False),
                )
                if is_over:
                    # Apply reported result, but guard against stale 'draw' when
                    # the board actually contains only a single king (checkmate).
                    # Sometimes higher-level detectors may return 'draw' due to
                    # timing of turn switches — prefer actual king existence.
                    try:
                        if winner == 'draw':
                            # Prefer actual king existence as a primary correction
                            wk = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
                            bk = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
                            if wk and not bk:
                                corrected = 'white'
                            elif bk and not wk:
                                corrected = 'black'
                            else:
                                # If both kings exist, double-check for an actual
                                # checkmate situation that might have been misreported
                                # as a draw due to timing of turn switches.
                                try:
                                    white_mate = (not has_legal_moves_with_cards('white')) and is_in_check_for_display(chess.pieces, 'white')
                                    black_mate = (not has_legal_moves_with_cards('black')) and is_in_check_for_display(chess.pieces, 'black')
                                    if white_mate and not black_mate:
                                        corrected = 'black'
                                    elif black_mate and not white_mate:
                                        corrected = 'white'
                                    else:
                                        corrected = 'draw'
                                except Exception:
                                    corrected = 'draw'
                        else:
                            corrected = winner
                    except Exception:
                        corrected = winner

                    game_over = True
                    game_over_winner = corrected
                    if corrected != winner and game is not None:
                        game.log.append(f"勝敗補正: 盤面のキング状態に基づき勝者を {corrected} に訂正しました(元: {winner})")
            except Exception:
                # Fallback: basic local checks if chess_rules is unavailable
                try:
                    if not has_legal_moves_with_cards('white') and is_in_check(chess.pieces, 'white'):
                        game_over = True
                        game_over_winner = 'black'
                        game.log.append("YOU LOSE！黒の勝利！")
                    elif not has_legal_moves_with_cards('black') and is_in_check(chess.pieces, 'black'):
                        game_over = True
                        game_over_winner = 'white'
                        game.log.append("YOU WIN！白の勝利！")
                    elif not has_legal_moves_with_cards(chess_current_turn) and not is_in_check(chess.pieces, chess_current_turn):
                        game_over = True
                        game_over_winner = 'draw'
                        game.log.append("ステイルメイト（引き分け）")
                except Exception:
                    pass

        # === 自動処理されるpending ===
        if getattr(game, 'pending', None) is not None:
            # ハンです☆: 相手の手札をランダムで墓地に送る
            if game.pending.kind == 'discard_opponent_hand':
                import random
                # Check for iron wall on the target (ai_player) which blocks one incoming effect
                try:
                    source_color = game.pending.info.get('source_color') if game.pending and isinstance(game.pending.info, dict) else None
                    # Only block if the effect is incoming (source != target)
                    if source_color is not None and source_color == 'black':
                        # effect originated from AI targeting AI -> shouldn't happen, but skip blocking
                        pass
                    # target is ai_player (black)
                    if getattr(ai_player, 'iron_wall_active', False) and source_color is not None and source_color != 'black':
                        ai_player.iron_wall_active = False
                        game.log.append("『鉄壁』が効果を防いだ（相手の『ハンです☆』）。")
                        game.pending = None
                    else:
                        if ai_player.hand.cards:
                            idx = random.randrange(len(ai_player.hand.cards))
                            discarded_card = ai_player.hand.cards[idx]
                            ai_player.hand.remove_at(idx)
                            ai_player.graveyard.append(discarded_card)
                            game.log.append(f"『ハンです☆』: 相手の手札から『{discarded_card.name}』をランダムで墓地に送りました。")
                        else:
                            game.log.append("『ハンです☆』: 相手の手札が空です。")
                        game.pending = None
                except Exception:
                    # on error, clear pending to avoid locking UI
                    game.pending = None
            
            # 命がけのギャンブル: ルーク・キング以外の駒をクイーンに変える
            elif game.pending.kind == 'gamble_promote':
                target_color = game.pending.info.get('target_color', 'white')
                success = game.pending.info.get('success', False)

                promoted_count = 0
                pieces = getattr(chess, 'pieces', []) or []

                # Determine the target player object so we can honor iron_wall
                try:
                    target_player = game.player if target_color == 'white' else ai_player
                except Exception:
                    target_player = None

                # If target has iron_wall_active, block the effect entirely
                try:
                    source_color = game.pending.info.get('source_color') if game.pending and isinstance(game.pending.info, dict) else None
                    if target_player is not None and getattr(target_player, 'iron_wall_active', False) and source_color is not None and source_color != target_color:
                        # Only consume iron_wall if the effect is incoming (origin color != target color)
                        target_player.iron_wall_active = False
                        game.log.append("『鉄壁』が効果を防いだ（命がけのギャンブル）。")
                        game.pending = None
                        # Skip promotion processing
                        promoted_count = 0
                    else:
                        for piece in pieces:
                            try:
                                if isinstance(piece, dict):
                                    p_color = piece.get('color')
                                    p_kind = piece.get('kind') or piece.get('name')
                                    if p_color == target_color and p_kind not in ['K', 'R']:
                                        # update both name and kind for consistency
                                        piece['kind'] = 'Q'
                                        piece['name'] = 'Q'
                                        promoted_count += 1
                                else:
                                    p_color = getattr(piece, 'color', None)
                                    # some codebase uses .name for piece type
                                    p_kind = getattr(piece, 'kind', None) or getattr(piece, 'name', None)
                                    if p_color == target_color and p_kind not in ['K', 'R']:
                                        # set both attributes where possible so rendering and checks pick it up
                                        try:
                                            setattr(piece, 'name', 'Q')
                                        except Exception:
                                            pass
                                        try:
                                            setattr(piece, 'kind', 'Q')
                                        except Exception:
                                            try:
                                                piece.kind = 'Q'
                                            except Exception:
                                                pass
                                        promoted_count += 1
                            except Exception as perr:
                                # log per-piece errors but continue
                                logger.exception('error promoting piece in gamble_promote: %s', perr)
                                continue
                except Exception as e:
                    # If anything unexpected happens during promotion handling, log and clear pending
                    logger.exception('exception during gamble_promote overall handling: %s', e)
                    game.pending = None
                # end of promotion loop / iron_wall handling

                if success:
                    game.log.append(f"『命がけのギャンブル』成功！自分の{promoted_count}個の駒がクイーンに昇格しました！")
                else:
                    game.log.append(f"『命がけのギャンブル』失敗...相手の{promoted_count}個の駒がクイーンに昇格しました...")

                # ターンスキップは失敗時のみ（要求に基づく変更）
                if not success:
                    if chess_current_turn == 'white':
                        chess_current_turn = 'black'
                        cpu_wait = True
                        cpu_wait_start = _ct_time.time()
                        # mark the player's card-game turn as consumed so the
                        # automatic player-turn start will occur after the AI finishes.
                        try:
                            game.turn_active = False
                            game.player_moved_this_turn = True
                            # force the auto-start after AI finishes in case
                            # turn accounting elsewhere prevents the normal check
                            game._force_start_player_after_ai = True
                        except Exception:
                            pass
                        game.log.append("自ターンをスキップします。")

                # --- 互換性同期: dictベース実装がある場合はそちらも更新 ---
                try:
                    # chess is the engine module (object-based). chess_rules may be dict-based.
                    if 'chess_rules' in globals() and getattr(chess_rules, 'pieces', None) is not None:
                        cr_pcs = []
                        for p in getattr(chess, 'pieces', []) or []:
                            try:
                                row = getattr(p, 'row', None) if not isinstance(p, dict) else p.get('row')
                                col = getattr(p, 'col', None) if not isinstance(p, dict) else p.get('col')
                                name = getattr(p, 'name', None) if not isinstance(p, dict) else p.get('name')
                                color = getattr(p, 'color', None) if not isinstance(p, dict) else p.get('color')
                                has_moved = getattr(p, 'has_moved', False) if not isinstance(p, dict) else p.get('has_moved', False)
                                if row is None or col is None or name is None or color is None:
                                    continue
                                cr_pcs.append({'row': int(row), 'col': int(col), 'name': name, 'color': color, 'has_moved': bool(has_moved)})
                            except Exception:
                                continue
                        try:
                            chess_rules.pieces = cr_pcs
                        except Exception:
                            pass
                except Exception:
                    pass

                game.pending = None

            # 盤面リセット（「負けるわけないだろwww」カード）
            elif game.pending.kind == 'board_reset':
                try:
                    # --- DEBUG before snapshot ---
                    try:
                        player_hand_names = [c.name for c in getattr(game.player.hand, 'cards', [])]
                        ai_hand_names = [c.name for c in getattr(getattr(game, 'ai_player', None).hand, 'cards', [])] if getattr(game, 'ai_player', None) else []
                        logger.debug("board_reset before: player_hand=%s ai_hand=%s player_deck=%d ai_deck=%s", player_hand_names, ai_hand_names, len(getattr(game.player.deck,'cards',[])), (len(getattr(getattr(game,'ai_player',None).deck,'cards',[])) if getattr(game,'ai_player',None) else 'NA'))
                        logger.debug("board_reset before: iron_wall: player=%s ai=%s", getattr(game.player,'iron_wall_active',False), getattr(game,'ai_iron_wall_active',False))
                    except Exception:
                        logger.debug("board_reset before: snapshot failed")
                    # 盤面を初期状態にリセット
                    chess.pieces[:] = chess.create_pieces()
                    chess.en_passant_target = None
                    
                    # プロモーション状態をクリア
                    try:
                        chess_rules.clear_promotion_state(chess)
                    except Exception:
                        chess.promotion_pending = None
                    
                    # ゲーム状態フラグをリセット
                    global simul_check_active, simul_white_result, simul_black_result
                    simul_check_active = False
                    simul_white_result = 'none'
                    simul_black_result = 'none'
                    
                    # 選択状態をクリア
                    selected_piece = None
                    highlight_squares = []
                    
                    # ターンをプレイヤーに戻す
                    chess_current_turn = 'white'
                    
                    # カードゲームターンもリセット
                    game.turn_active = False
                    game.player_moved_this_turn = False
                    
                    game.log.append("★★★ 盤面が初期状態にリセットされました！ ★★★")
                    game.log.append("ゲームを続行します。")
                    # 敗北フラグを解除（自動/手動発動どちらでも蘇生扱い）
                    try:
                        game_over = False
                        game_over_winner = None
                    except Exception:
                        pass
                    # no_lose二重発動防止フラグをクリア
                    try:
                        if hasattr(game, 'no_lose_triggered'):
                            game.no_lose_triggered = False
                    except Exception:
                        pass
                    # --- DEBUG after snapshot ---
                    try:
                        player_hand_names = [c.name for c in getattr(game.player.hand, 'cards', [])]
                        ai_hand_names = [c.name for c in getattr(getattr(game, 'ai_player', None).hand, 'cards', [])] if getattr(game, 'ai_player', None) else []
                        logger.debug("board_reset after: player_hand=%s ai_hand=%s player_deck=%d ai_deck=%s", player_hand_names, ai_hand_names, len(getattr(game.player.deck,'cards',[])), (len(getattr(getattr(game,'ai_player',None).deck,'cards',[])) if getattr(game,'ai_player',None) else 'NA'))
                        logger.debug("board_reset after: iron_wall: player=%s ai=%s", getattr(game.player,'iron_wall_active',False), getattr(game,'ai_iron_wall_active',False))
                    except Exception:
                        logger.debug("board_reset after: snapshot failed")
                    
                except Exception as e:
                    game.log.append(f"盤面リセット中にエラーが発生しました: {e}")
                    import traceback
                    traceback.print_exc()
                
                game.pending = None

        draw_panel()
        pygame.display.flip()

        # Non-blocking AI wait handling (ゲーム終了時は無効化)
        if cpu_wait and THINKING_ENABLED and not game_over:
            import time
            # If a promotion selection is pending for a WHITE piece, postpone AI until the promotion is resolved by the player.
            # However, if it's a BLACK (AI) piece promotion, it should already have been auto-resolved in ai_make_move.
            # This check prevents race conditions where the UI is waiting for player promotion choice.
            pending_promo = getattr(chess, 'promotion_pending', None)
            if pending_promo is not None:
                promo_color = pending_promo.get('color', None)
                if promo_color == 'white':
                    # Player's piece needs promotion - wait for player to select
                    cpu_wait_start = time.time()
                else:
                    # This shouldn't happen (AI promotion should be auto-handled), but clear it defensively
                    try:
                        promoted_piece = pending_promo.get('piece')
                        if promoted_piece is not None:
                            promoted_piece.name = 'Q'
                            game.log.append("AI: ポーンをQに昇格させました（待機ループ内での防御処理）。")
                        chess.promotion_pending = None
                    except Exception:
                        chess.promotion_pending = None
            elif time.time() - cpu_wait_start >= AI_THINK_DELAY:
                # call AI move
                ai_make_move()
                # After AI move, check if AI has extra consecutive turns (迅雷)
                # Prefer game.ai_consecutive_turns over global for consistency
                try:
                    a_cct = getattr(game, 'ai_consecutive_turns', 0)
                    if a_cct == 0:
                        a_cct = globals().get('ai_consecutive_turns', 0)
                except Exception:
                    a_cct = globals().get('ai_consecutive_turns', 0)

                if a_cct and a_cct > 0:
                    # consume one AI extra-turn and schedule another AI think cycle
                    try:
                        # Update game attribute first
                        game.ai_consecutive_turns = max(0, a_cct - 1)
                        # Sync to globals
                        globals()['ai_consecutive_turns'] = game.ai_consecutive_turns
                    except Exception:
                        try:
                            if 'ai_consecutive_turns' in globals():
                                globals()['ai_consecutive_turns'] = max(0, globals().get('ai_consecutive_turns', 0) - 1)
                        except Exception:
                            pass
                    # keep AI's turn so it moves again
                    chess_current_turn = 'black'
                    # Mark that the next AI move is a continuation of the '迅雷' extra-turn
                    # so that start-of-turn effects (draw/PP reset) are skipped.
                    try:
                        globals()['ai_continuation'] = True
                    except Exception:
                        pass
                    # schedule next AI move after the think delay
                    cpu_wait = True
                    cpu_wait_start = time.time()
                else:
                    # no extra AI turns -> restore player turn
                    game.log.append("─── AIのターン終了 ───")
                    cpu_wait = False
                    chess_current_turn = 'white'
                    # プレイヤーターン開始テロップを1秒表示
                    try:
                        turn_telop_msg = "YOUR TURN"
                        turn_telop_until = _ct_time.time() + 1.0
                    except Exception:
                        pass
                    # Apply decay for time-limited card effects now that the opponent's turn finished.
                    # We pass the ended color ('black' here) so only statuses that apply to that
                    # color are decremented. This prevents freezes applied to white by the AI
                    # from being decremented immediately when the AI finishes its move.
                    try:
                        game.decay_statuses('black')
                    except Exception:
                        pass

                    # 自動ターン開始（2ターン目以降）
                    # プレイヤーが既に1ターン以上開始している場合、AIの手が終わったら
                    # 自動でプレイヤーのターン開始とドローを行います（Tキー不要）。
                    try:
                        # game.turn は start_turn() が呼ばれると 1,2,... と増えるため
                        # ここでは既にプレイヤーが1ターン以上開始している場合のみ自動開始する。
                        # auto-start if either the player already had at least one
                        # started turn OR a caller requested forcing the start after AI
                        should_auto = getattr(game, 'turn', 0) >= 1 or getattr(game, '_force_start_player_after_ai', False)
                        if should_auto:
                            # pending がある、または既に turn_active の場合は自動開始しない
                            if getattr(game, 'pending', None) is None and not getattr(game, 'turn_active', False):
                                try:
                                    start_player_turn("AI終了: 自動でターン開始と1枚ドローを行いました。")
                                except Exception:
                                    pass
                            # Clear the force-start flag so it doesn't persist
                            try:
                                if getattr(game, '_force_start_player_after_ai', False):
                                    delattr(game, '_force_start_player_after_ai')
                            except Exception:
                                try:
                                    if '_force_start_player_after_ai' in game.__dict__:
                                        del game.__dict__['_force_start_player_after_ai']
                                except Exception:
                                    pass
                    except Exception:
                        pass

        clock.tick(60)


if __name__ == "__main__":
    # show start screen to choose AI difficulty before starting
    show_start_screen()
    # Ensure game/ai_player created according to DECK_MODE (start screen may have set it)
    try:
        if globals().get('game') is None:
            globals()['game'] = new_game_with_mode(DECK_MODE)
        if globals().get('ai_player') is None:
            globals()['ai_player'] = build_ai_player(DECK_MODE)
            try:
                _init_ai_start_hand(globals()['ai_player'], 4, globals()['game'])
            except Exception:
                pass
    except Exception:
        pass
    main_loop()