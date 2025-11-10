#カードゲーム部分実装
import pygame
from pygame import Rect
import sys
import traceback
import os
import json

try:
    from .card_core import new_game_with_sample_deck, new_game_with_rule_deck, PlayerState, make_rule_cards_deck, PendingAction, Card, Game
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck, PlayerState, make_rule_cards_deck, PendingAction, Card, Game

# チェスロジックを外部モジュール化（Chess MainのPieceクラス実装）
try:
    from . import chess_engine as chess
except Exception:
    import chess_engine as chess


pygame.init()

# 画面設定
W, H = 1200, 800
# Allow the user to resize/minimize/maximize the game window
# If another module (e.g. main launcher) already created a display surface,
# reuse it to avoid creating multiple windows / stealing events when this
# module is imported rather than executed directly.
existing_surf = None
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

# Base UI resolution used for consistent scaling between windowed and fullscreen
BASE_UI_W = 1200
BASE_UI_H = 800

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)

# ゲーム状態
# NOTE: defer creating the actual game and AI decks until after the
# user selects difficulty and deck mode in the start flow. We'll
# initialize `game` and `ai_player` via `new_game_with_mode()` so the
# deck sizes can match the player's choice (fixed=24 / custom=20).
game = None
# AI placeholder; will be created at game start
ai_player = None
# ヘルパー: 相手（AI）の手札枚数を取得する（UI はこれを参照する）
def get_opponent_hand_count():
    try:
        return len(getattr(ai_player, 'hand').cards)
    except Exception:
        # フォールバック: 初期値や何らかの理由で参照できない場合は 0 を返す
        return 0
# AI 用のギミックフラグ
ai_next_move_can_jump = False
ai_extra_moves_this_turn = 0
ai_consecutive_turns = 0
# When True, the next ai_make_move() call is a continuation of an existing AI
# '迅雷' extra-turn and should NOT perform start-of-turn effects (draw/PP reset).
ai_continuation = False
show_grave = False
show_log = False  # ログ表示切替（デフォルト非表示）
log_scroll_offset = 0  # ログスクロール用オフセット（0=最新）
enlarged_card_index = None  # 拡大表示中のカードインデックス（None=非表示）
enlarged_card_name = None  # 墓地など手札以外の拡大表示用カード名（未定義での参照を防止）
show_opponent_hand = False  # 相手の手札表示切替（デフォルト非表示）
# （注意）従来の固定変数 `opponent_hand_count` は使わず、
# UI 表示時に `get_opponent_hand_count()` を呼んで実際の枚数を参照します。

# ---- BGM 設定 (UI から変更可能) ----
# BGM を再生するかどうか (設定画面で切替)
bgm_enabled = True
# BGM ボリューム (0.0 - 1.0)
bgm_volume = 0.8

# track current logical bgm mode so callers can reapply when toggling
current_bgm_mode = None

# Deck selection mode: 'fixed' uses the rule deck (24 cards),
# 'custom' uses the created deck (20 cards). This is set after the
# difficulty + deck choice modal.
DECK_MODE = 'fixed'


def _custom_decks_dir():
    """Return path to custom decks directory (may not exist)."""
    return os.path.join(os.path.dirname(__file__), 'decks')


def list_custom_decks():
    """Return a list of custom deck basenames (without .json)."""
    d = _custom_decks_dir()
    out = []
    try:
        if os.path.isdir(d):
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith('.json'):
                    out.append(os.path.splitext(fn)[0])
    except Exception:
        pass
    return out


def load_custom_deck_by_name(name: str):
    """Load a custom deck (list of card names) from decks/<name>.json.

    Returns list of card names or None on error.
    """
    d = _custom_decks_dir()
    path = os.path.join(d, f"{name}.json")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                return [str(x) for x in data]
    except Exception:
        pass
    return None


def build_game_from_card_names(names):
    """Build a Game whose player's deck contains cards named in `names`.

    This maps names to prototypes from make_rule_cards_deck(); unknown
    names are skipped. On failure, fall back to new_game_with_mode('custom').
    """
    try:
        proto_deck = make_rule_cards_deck()
        proto_map = {c.name: c for c in proto_deck.cards}

        pool = []
        for nm in names:
            p = proto_map.get(nm)
            if p is None:
                continue
            try:
                # clone prototype (best-effort)
                pool.append(Card(p.name, p.cost, p.effect, getattr(p, 'precheck', None)))
            except Exception:
                try:
                    pool.append(Card(p.name, p.cost, p.effect))
                except Exception:
                    continue

        if not pool:
            deck = build_deck_for_mode('custom')
        else:
            from .card_core import Deck
            deck = Deck(pool)

        deck.shuffle()
        player = PlayerState(deck=deck)
        g = Game(player=player)
        try:
            g.setup_battle()
        except Exception:
            pass
        return g
    except Exception:
        return new_game_with_mode('custom')


# Helper: safely switch BGM. mode is 'title' or 'game' or None to stop.
def set_bgm_mode(mode: str | None) -> None:
    """Atomically switch background music according to mode.

    - 'title' -> MusMus-BGM-162.mp3
    - 'game'  -> MusMus-BGM-173.mp3
    - None    -> stop music

    This function is defensive: it initializes the mixer if needed and
    catches exceptions so UI flow is not interrupted.
    """
    try:
        # ensure mixer is initialized
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception:
                pass
        # stop any currently playing music first
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

        if not bgm_enabled or mode is None:
            # Ensure volume is muted when disabled
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.set_volume(0.0)
            except Exception:
                pass
            try:
                globals()['current_bgm_mode'] = None
            except Exception:
                pass
            return

        if mode == 'title':
            bgm_path = os.path.join(os.path.dirname(__file__), 'mugic', 'MusMus-BGM-162.mp3')
        elif mode == 'game':
            bgm_path = os.path.join(os.path.dirname(__file__), 'mugic', 'MusMus-BGM-173.mp3')
        else:
            # unknown mode -> stop
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            return

        if os.path.exists(bgm_path):
            try:
                pygame.mixer.music.load(bgm_path)
                pygame.mixer.music.play(-1)
                try:
                    pygame.mixer.music.set_volume(max(0.0, min(1.0, bgm_volume)))
                except Exception:
                    pass
            except Exception:
                # ignore audio errors
                pass
            try:
                globals()['current_bgm_mode'] = mode
            except Exception:
                pass
    except Exception:
        # swallow any unexpected errors to avoid breaking UI
        pass


def build_deck_for_mode(mode: str):
    """Return a Deck object appropriate for the chosen deck mode.

    - 'fixed' -> full rule deck (24 cards)
    - 'custom' -> trimmed deck (20 cards)
    """
    try:
        deck = make_rule_cards_deck()
        # make_rule_cards_deck already shuffles its pool; for custom decks
        # we trim to 20 and reshuffle so randomness is preserved.
        if mode == 'custom':
            try:
                deck.cards = deck.cards[:20]
                deck.shuffle()
            except Exception:
                pass
        return deck
    except Exception:
        # fallback: return whatever rule deck returns or raise
        try:
            return make_rule_cards_deck()
        except Exception:
            return None


def build_ai_player(mode: str):
    """Create and return a PlayerState for the AI matching the deck mode."""
    try:
        deck = build_deck_for_mode(mode)
        if deck is None:
            return None
        p = PlayerState(deck=deck)
        # initial pp and draw as before
        try:
            p.reset_pp()
            for _ in range(4):
                c = p.deck.draw()
                if c is not None:
                    p.hand.add(c)
        except Exception:
            pass
        return p
    except Exception:
        return None


def new_game_with_mode(mode: str):
    """Create a new Game with player's deck and return the Game object.

    This mirrors new_game_with_rule_deck but allows trimming the deck
    based on the selected mode.
    """
    try:
        deck = build_deck_for_mode(mode)
        if deck is None:
            # fallback to rule deck
            deck = make_rule_cards_deck()
        deck.shuffle()
        player = PlayerState(deck=deck)
        game = Game(player=player)
        try:
            game.setup_battle()
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

    Sets global `DECK_MODE` to 'fixed' or 'custom'. If user selects the
    created deck option, opens the deck list modal for inspection.
    """
    global DECK_MODE
    clk = pygame.time.Clock()
    w, h = 560, 240
    x = (W - w)//2
    y = (H - h)//2

    # Button geometry
    btn_w = 220
    btn_h = 80
    left_x = x + 32
    right_x = x + w - btn_w - 32
    by = y + 80

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                # default to fixed if user cancels
                DECK_MODE = 'fixed'
                return
            if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1) or ev.type == pygame.FINGERDOWN:
                if ev.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = ev.pos
                else:
                    mx = int(ev.x * W)
                    my = int(ev.y * H)
                # fixed deck
                if left_x <= mx <= left_x + btn_w and by <= my <= by + btn_h:
                    DECK_MODE = 'fixed'
                    return
                # created deck
                if right_x <= mx <= right_x + btn_w and by <= my <= by + btn_h:
                    DECK_MODE = 'custom'
                    # Open the read-only custom deck selection menu (do not allow editing).
                    try:
                        show_custom_deck_selection(screen)
                    except Exception as e:
                        # Make exceptions visible so we can debug why the menu
                        # sometimes doesn't appear. Fall back to the simple list.
                        print("Error in show_custom_deck_selection:", e, file=sys.stderr)
                        traceback.print_exc()
                        try:
                            show_deck_modal(screen)
                        except Exception as e2:
                            print("Error in show_deck_modal fallback:", e2, file=sys.stderr)
                            traceback.print_exc()
                    return

        # draw overlay/modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((245,245,250))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)

        title = FONT.render("デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        # fixed deck button
        fixed_rect = pygame.Rect(left_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), fixed_rect)
        pygame.draw.rect(surf, (70,70,70), fixed_rect, 2)
        t1 = SMALL.render("固定デッキ （デフォルト）", True, (30,30,30))
        t2 = SMALL.render("カード数: 24 / 24", True, (80,80,80))
        surf.blit(t1, (fixed_rect.x + (btn_w - t1.get_width())//2, fixed_rect.y + 12))
        surf.blit(t2, (fixed_rect.x + (btn_w - t2.get_width())//2, fixed_rect.y + 40))

        # custom deck button
        custom_rect = pygame.Rect(right_x - x, by - y, btn_w, btn_h)
        pygame.draw.rect(surf, (220,220,220), custom_rect)
        pygame.draw.rect(surf, (70,70,70), custom_rect, 2)
        c1 = SMALL.render("作成したデッキ（暫定）", True, (30,30,30))
        c2 = SMALL.render("カード数: 20 / 20", True, (80,80,80))
        surf.blit(c1, (custom_rect.x + (btn_w - c1.get_width())//2, custom_rect.y + 12))
        surf.blit(c2, (custom_rect.x + (btn_w - c2.get_width())//2, custom_rect.y + 40))

        screen.blit(surf, (x,y))
        pygame.display.flip()
        clk.tick(30)

# CPU 難易度 (1=Easy,2=Medium,3=Hard,4=Expert)
CPU_DIFFICULTY = 2

# 画像の読み込み（カード名と同じファイル名.png を images 配下から探す）
IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
_image_cache = {}
card_rects = []  # カードのクリック判定用矩形リスト
_piece_image_cache = {}
chess_log = []  # チェス専用ログ（カード用の game.log と分離）

# プレイ画面用背景画像の候補とキャッシュ
PLAY_BG_FILENAME = "ChatGPT Image 2025年11月4日 11_12_06.png"
play_bg_img = None      # 元画像を保持（リサイズ用）
play_bg_surf = None     # 現在のウィンドウサイズに合わせたスケール済みサーフ

# クリックターゲットなどのグローバル初期値（未定義参照による例外を防止）
confirm_yes_rect = None
confirm_no_rect = None
grave_label_rect = None
opponent_hand_rect = None
grave_card_rects = []
scrollbar_rect = None
dragging_scrollbar = False
drag_start_y = 0
drag_start_offset = 0
# Heat choice button rects (灼熱の二択ボタン)
heat_choice_unfreeze_rect = None
heat_choice_block_rect = None

# GIF animation cache / player for heat effect (Image_F.gif)
heat_gif_frames_cache = None  # list of pygame.Surface frames or single-surface fallback
heat_gif_durations = None  # list of per-frame durations (ms)
heat_gif_anim = {
    'playing': False,
    'start_time': 0.0,
    'total_duration': 0.0,
    'frames': None,
    'durations': None,
    'pos': None,  # (row, col)
}

# MG GIF (blocked-tile persistent effect) cache
mg_gif_frames_cache = None
mg_gif_durations = None
mg_gif_total_duration = 0.0
mg_gif_load_attempted = False
mg_gif_load_success = False

# 2P-color variant for AI-applied blocked tiles
mg_gif_2p_frames_cache = None
mg_gif_2p_durations = None
mg_gif_2p_total_duration = 0.0
mg_gif_2p_load_attempted = False
mg_gif_2p_load_success = False

# Ice GIF (氷結) cache + player (Image_ic (1).gif)
ic_gif_frames_cache = None  # 凍結の追加
ic_gif_durations = None
ic_gif_load_attempted = False
ic_gif_load_success = False

ic_gif_anim = {
    'playing': False,
    'start_time': 0.0,
    'total_duration': 0.0,
    'frames': None,
    'durations': None,
    'pos': None,  # (row, col)
}

# === DEBUG: 反撃チェックを「カード使用直後のみ許可」する検証モード ===
# F6 で ON/OFF。ON の間、実カード使用または F7 で
# game._debug_last_action_was_card を立てると、その次の1手に限り
# 「自身チェック中でも相手にチェックを与える手（反撃チェック）」を許可します。
DEBUG_COUNTER_CHECK_CARD_MODE = False

def _debug_mark_card_played():
    """カードを使用した（またはF7相当）として次の1手に反撃チェックを許可する。
    デバッグモード（F6）がONのときのみ意味を持つ。
    """
    if globals().get('DEBUG_COUNTER_CHECK_CARD_MODE', False):
        try:
            setattr(game, '_debug_last_action_was_card', True)
            try:
                game.log.append("[DEBUG] カード使用扱いフラグをセット（次の1手）。")
            except Exception:
                pass
        except Exception:
            pass

def _ensure_mg_gif_2p_loaded():
    """Lazily load Image_MG_2P.gif frames into mg_gif_2p_* globals."""
    global mg_gif_2p_frames_cache, mg_gif_2p_durations, mg_gif_2p_total_duration
    global mg_gif_2p_load_attempted, mg_gif_2p_load_success
    if mg_gif_2p_frames_cache is not None and mg_gif_2p_durations is not None:
        return
    if mg_gif_2p_load_attempted:
        return
    mg_gif_2p_load_attempted = True
    gif_path = os.path.join(IMG_DIR, 'Image_MG_2P.gif')
    frames, durations = _load_gif_frames(gif_path)
    if not frames:
        # fallback: try the standard MG gif
        gif_path2 = os.path.join(IMG_DIR, 'Image_MG.gif')
        frames, durations = _load_gif_frames(gif_path2)
    if not frames:
        mg_gif_2p_frames_cache = None
        mg_gif_2p_durations = None
        mg_gif_2p_total_duration = 0.0
        mg_gif_2p_load_success = False
        return
    mg_gif_2p_frames_cache = frames
    mg_gif_2p_durations = durations
    try:
        mg_gif_2p_total_duration = sum(durations) / 1000.0
    except Exception:
        mg_gif_2p_total_duration = 0.0
    mg_gif_2p_load_success = True
# How much to slow down the ice GIF playback (multiplier on per-frame durations).
# Increase to make the animation slower/longer. Default 2.5x for better visibility.
IC_GIF_SPEED_FACTOR = 2.5
# Scale multiplier for ice GIF when rendering over a tile (1.0 = tile size)
IC_GIF_SCALE = 1.4

def _load_gif_frames(path: str):
    """Try to load GIF frames using Pillow if available, fallback to single surface.

    Returns (frames_list, durations_list). frames_list is a list of pygame.Surface.
    durations_list is list of durations in milliseconds.
    If Pillow is not available or loading fails, returns ([surface], [1000]).
    """
    global heat_gif_frames_cache, heat_gif_durations
    try:
        from PIL import Image
    except Exception:
        # Pillow not available: fallback to loading the GIF as a single image
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None

    try:
        img = Image.open(path)
    except Exception:
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None

    frames = []
    durations = []
    try:
        for frame_index in range(0, getattr(img, 'n_frames', 1)):
            img.seek(frame_index)
            frame = img.convert('RGBA')
            mode = frame.mode
            size = frame.size
            data = frame.tobytes()
            surf = pygame.image.fromstring(data, size, mode).convert_alpha()
            frames.append(surf)
            dur = img.info.get('duration', 100)  # milliseconds
            durations.append(dur)
    except EOFError:
        pass
    if not frames:
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None
    return frames, durations

def _ensure_mg_gif_loaded():
    """Lazily load Image_MG.gif frames into mg_gif_* globals."""
    global mg_gif_frames_cache, mg_gif_durations, mg_gif_total_duration
    global mg_gif_load_attempted, mg_gif_load_success
    if mg_gif_frames_cache is not None and mg_gif_durations is not None:
        return
    if mg_gif_load_attempted:
        return
    mg_gif_load_attempted = True
    gif_path = os.path.join(IMG_DIR, 'Image_MG.gif')
    frames, durations = _load_gif_frames(gif_path)
    if not frames:
        mg_gif_frames_cache = None
        mg_gif_durations = None
        mg_gif_total_duration = 0.0
        mg_gif_load_success = False
        # fallback: try pygame.image.load as a single-surface fallback
        try:
            surf = pygame.image.load(gif_path).convert_alpha()
            mg_gif_frames_cache = [surf]
            mg_gif_durations = [1000]
            mg_gif_total_duration = 1.0
            mg_gif_load_success = True
            # note: intentionally do not log image/GIF internal loading to game.log
            return
        except Exception:
            return
    mg_gif_frames_cache = frames
    mg_gif_durations = durations
    try:
        mg_gif_total_duration = sum(durations) / 1000.0
    except Exception:
        mg_gif_total_duration = len(durations) * 0.1 if durations else 0.0
    mg_gif_load_success = True

def play_heat_gif_at(row: int, col: int):
    """Start playing the heat GIF animation centered at board square (row,col)."""
    global heat_gif_frames_cache, heat_gif_durations, heat_gif_anim
    gif_path = os.path.join(IMG_DIR, 'Image_F.gif')
    if heat_gif_frames_cache is None or heat_gif_durations is None:
        frames, durations = _load_gif_frames(gif_path)
        heat_gif_frames_cache = frames



    frames = heat_gif_frames_cache
    durations = heat_gif_durations
    if not frames:
        return
    heat_gif_anim['frames'] = frames
    heat_gif_anim['durations'] = durations
    heat_gif_anim['playing'] = True
    heat_gif_anim['start_time'] = _ct_time.time()
    heat_gif_anim['total_duration'] = sum(durations) / 1000.0
    heat_gif_anim['pos'] = (row, col)


def _ensure_ic_gif_loaded():
    """Lazily load Image_ic GIF frames into ic_gif_* globals."""
    global ic_gif_frames_cache, ic_gif_durations, ic_gif_load_attempted, ic_gif_load_success
    if ic_gif_frames_cache is not None and ic_gif_durations is not None:
        return
    if ic_gif_load_attempted:
        return
    ic_gif_load_attempted = True
    candidates = [
        'Image_ic (1).gif',
        'Image_ic.gif',
        'Image_ic(1).gif',
        'Image_ic_1.gif',
        'Image_ic1.gif',
        'ice.gif',
    ]
    frames = None
    durations = None
    for cand in candidates:
        path = os.path.join(IMG_DIR, cand)
        f, d = _load_gif_frames(path)
        if f:
            frames = f
            durations = d
            # suppress GIF load logging (internal asset loading)
            break
    if not frames and os.path.isdir(IMG_DIR):
        for fn in os.listdir(IMG_DIR):
            if fn.lower().startswith('image_ic'):
                path = os.path.join(IMG_DIR, fn)
                f, d = _load_gif_frames(path)
                if f:
                    frames = f
                    durations = d
                    # suppress GIF load logging (internal asset loading)
                    break
    if not frames:
        try:
            path = os.path.join(IMG_DIR, 'Image_ic (1).gif')
            surf = pygame.image.load(path).convert_alpha()
            frames = [surf]
            durations = [1000]
            # suppress GIF load logging (internal asset loading)
            ic_gif_load_success = True
        except Exception:
            ic_gif_load_success = False
            # suppress GIF load failure logging (internal asset loading)
            return
    ic_gif_frames_cache = frames
    # Apply speed factor to make ice animation slower and more visible
    try:
        # ensure durations is a list of ints
        durations = [int(d) for d in (durations or [1000])]
        slowed = [max(int(d * IC_GIF_SPEED_FACTOR), 120) for d in durations]
        ic_gif_durations = slowed
        ic_gif_anim['total_duration'] = sum(ic_gif_durations) / 1000.0
        # suppress GIF playback-setting logging (internal asset loading)
    except Exception:
        ic_gif_durations = durations
        try:
            ic_gif_anim['total_duration'] = sum(durations) / 1000.0
        except Exception:
            ic_gif_anim['total_duration'] = len(durations) * 0.1 if durations else 0.0
    ic_gif_load_success = True


def play_ic_gif_at(row: int, col: int):
    """Start playing the ice GIF centered at board square (row,col)."""
    global ic_gif_frames_cache, ic_gif_durations, ic_gif_anim
    if ic_gif_frames_cache is None or ic_gif_durations is None:
        _ensure_ic_gif_loaded()
    frames = ic_gif_frames_cache
    durations = ic_gif_durations
    if not frames:
        # suppress GIF playback debug logging
        return
    ic_gif_anim['frames'] = frames
    ic_gif_anim['durations'] = durations
    ic_gif_anim['playing'] = True
    ic_gif_anim['start_time'] = _ct_time.time()
    try:
        ic_gif_anim['total_duration'] = sum(durations) / 1000.0
    except Exception:
        ic_gif_anim['total_duration'] = len(durations) * 0.1 if durations else 0.0
    ic_gif_anim['pos'] = (row, col)
    # suppress GIF playback debug logging


# Register hook on module-level `game` so core logic can request GIF playback
try:
    game.play_ic_gif = play_ic_gif_at
except Exception:
    pass

def get_piece_image_surface(name: str, color: str, size: tuple):
    """Return a pygame.Surface for the given piece (name like 'K','Q', color 'white'/'black').
    Cache scaled images by (name,color,size). If file not found, return None to indicate fallback.
    """
    key = (name, color, size)
    if key in _piece_image_cache:
        return _piece_image_cache[key]
    # Filename convention: Chess_{letter_lower}_{color}.png (as used elsewhere)
    fname = f"Chess_{name.lower()}_{color}.png"
    path = os.path.join(IMG_DIR, fname)
    surf = None
    try:
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            surf = pygame.transform.smoothscale(img, size)
    except Exception:
        surf = None
    _piece_image_cache[key] = surf
    return surf


def draw_dashed_rect(surf, color, rect, dash=6, gap=4, width=2):
    """Draw a dashed rectangle on surf. rect is pygame.Rect."""
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    # top
    sx = x
    while sx < x + w:
        ex = min(sx + dash, x + w)
        pygame.draw.line(surf, color, (sx, y), (ex, y), width)
        sx += dash + gap
    # bottom
    sx = x
    by = y + h
    while sx < x + w:
        ex = min(sx + dash, x + w)
        pygame.draw.line(surf, color, (sx, by), (ex, by), width)
        sx += dash + gap
    # left
    sy = y
    while sy < y + h:
        ey = min(sy + dash, y + h)
        pygame.draw.line(surf, color, (x, sy), (x, ey), width)
        sy += dash + gap
    # right
    sy = y
    rx = x + w
    while sy < y + h:
        ey = min(sy + dash, y + h)
        pygame.draw.line(surf, color, (rx, sy), (rx, ey), width)
        sy += dash + gap

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

# --- 同時チェック管理（特殊ルール） ---
# 仕様:
# - 両者が同時にチェックになった瞬間に同時チェック状態に突入。
# - それぞれ「次の自分のチェス手番開始」時点でチェック解除できていなければ失敗。
# - 両者とも失敗 → 引き分け。片方のみ解除成功 → そのプレイヤーの勝利。両方解除 → 通常継続。
simul_check_active = False
simul_white_result = 'none'  # 'none'|'pending'|'cleared'|'failed'
simul_black_result = 'none'
white_turn_index = 0
black_turn_index = 0
last_turn_color = None
simul_white_deadline = None  # 次の自分の手番開始のターンインデックス
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

# --- Debug setup helpers (F1-F4) for quick rule testing ---
def debug_setup_castling():
    """Set a simple board where white can castle both sides (no black pieces)."""
    chess.pieces.clear()
    # white king and rooks only
    chess.pieces.append(chess.Piece(7,4,'K','white'))
    chess.pieces.append(chess.Piece(7,0,'R','white'))
    chess.pieces.append(chess.Piece(7,7,'R','white'))
    # Ensure they are unmoved
    for p in chess.pieces:
        p.has_moved = False
    # Clear en passant and selections
    globals()['selected_piece'] = None
    globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    chess.en_passant_target = None
    game.log.append("[DEBUG] キャスリング検証用の盤面をセットしました（白番）。e1のKとa1/h1のRのみ配置。")

def debug_setup_en_passant():
    """Set a board where white can perform en passant to the right."""
    chess.pieces.clear()
    wp = chess.Piece(3,4,'P','white')  # e5
    bp = chess.Piece(3,5,'P','black')  # f5 (assume just moved two steps)
    chess.pieces.extend([wp, bp])
    # Set EP target square (the intermediate square the pawn passed)
    chess.en_passant_target = (2,5)  # f6 from white perspective (row 2)
    globals()['selected_piece'] = None
    globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    game.log.append("[DEBUG] アンパサン検証用の盤面をセットしました（白番）。e5の白Pがf6へアンパサン可能です。")

def debug_setup_promotion():
    """Set a board where white pawn can promote next move."""
    chess.pieces.clear()
    wp = chess.Piece(1,0,'P','white')  # a7 -> a8 で昇格
    chess.pieces.append(wp)
    chess.en_passant_target = None
    globals()['selected_piece'] = None
    globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    game.log.append("[DEBUG] 昇格検証用の盤面をセットしました（白番）。a7の白Pをa8へ移動すると昇格ダイアログが出ます。")

def debug_reset_initial():
    chess.pieces[:] = chess.create_pieces()
    chess.en_passant_target = None
    globals()['selected_piece'] = None
    globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    game.log.append("[DEBUG] 初期配置にリセットしました（白番）。")


def debug_setup_checkmate():
    """簡単なチェックメイト検証用盤面（白を詰ませる）"""
    chess.pieces.clear()
    # 白キングを隅に追い詰める
    wk = chess.Piece(7, 0, 'K', 'white')  # a1
    # 黒のクイーンとルークで詰み
    bq = chess.Piece(6, 1, 'Q', 'black')  # b2
    br = chess.Piece(7, 1, 'R', 'black')  # b1
    chess.pieces.extend([wk, bq, br])
    globals()['selected_piece'] = None
    globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    chess.en_passant_target = None
    game.log.append("[DEBUG] チェックメイト検証用の盤面をセットしました（白番・詰み状態）。")

def debug_setup_counter_check_white():
    """白がチェック中で、次の1手で『自分は依然チェックだが相手にチェックを与える』反撃チェック手が存在する局面にセット。

    配置:
      - 白K: e1 (7,4)
      - 黒R: e8 (0,4) → 白Kに一直線でチェック中
      - 白R: b1 (7,1)
      - 黒K: a6 (2,0)

    このとき、白の手番で Rb1-b6 (7,1)->(2,1) は、
    白は依然Re8のチェック下にいるが、黒K a6 に横からチェックを与える『反撃チェック』になります。
    通常は不合法ですが、迅雷有効時、または[F6]デバッグモードONかつカード直後扱い（F7）でのみ合法。
    """
    # 盤面リセット
    chess.pieces.clear()
    chess.en_passant_target = None
    # 駒配置
    wk = chess.Piece(7, 4, 'K', 'white')  # e1
    br = chess.Piece(0, 4, 'R', 'black')  # e8 (白Kを縦にチェック)
    wr = chess.Piece(7, 1, 'R', 'white')  # b1 （b6へ上がるとa6の黒Kに横チェック）
    bk = chess.Piece(2, 0, 'K', 'black')  # a6
    chess.pieces.extend([wk, br, wr, bk])

    # UI/ターン関連を整える
    globals()['selected_piece'] = wr
    try:
        # 直ちにハイライト表示（通常は不合法のため、F6でON & F7でカード直後扱いを推奨）
        globals()['highlight_squares'] = get_valid_moves(wr)
    except Exception:
        globals()['highlight_squares'] = []
    globals()['chess_current_turn'] = 'white'
    try:
        game.turn_active = True
        game.player_moved_this_turn = False
    except Exception:
        pass

def debug_setup_simul_check_start():
    """F9: 白が黒Kを取る手を実行し、その後黒が白Kを取れるかをテストする局面をセット。

    例の配置:
      - 白K: e1 (7,4)
      - 黒K: a6 (2,0)
      - 白R: a1 (7,0) → 黒K a6 に縦で取れる
      - 黒R: e8 (0,4) → 白K e1 に縦で取れる

    白Rがa1からa6へ移動して黒Kを取り、その後黒Rがe8からe1へ移動して白Kを取ることができる。
    両方のKが取られた場合は引き分け、片方だけが残っている場合はそのプレイヤーの勝ち。
    """
    # 盤面リセット
    chess.pieces.clear()
    chess.en_passant_target = None

    # 駒配置
    wk = chess.Piece(7, 4, 'K', 'white')  # e1
    bk = chess.Piece(2, 0, 'K', 'black')  # a6
    wr = chess.Piece(7, 0, 'R', 'white')  # a1（a6の黒Kを取れる）
    br = chess.Piece(0, 4, 'R', 'black')  # e8（e1の白Kを取れる）
    chess.pieces.extend([wk, bk, wr, br])

    # 白Rを選択状態にして、a6（黒K）への移動をハイライト
    globals()['selected_piece'] = wr
    try:
        globals()['highlight_squares'] = get_valid_moves(wr)
    except Exception:
        globals()['highlight_squares'] = []
    
    globals()['chess_current_turn'] = 'white'
    try:
        game.turn_active = True
        game.player_moved_this_turn = False
    except Exception:
        pass

    # 両キング取得テストモードをONにする（片方のキングが取られても即座に終了しない）
    globals()['dual_king_capture_test'] = True
    globals()['first_king_captured'] = None  # 最初に取られたキングの色を記録

    # ログ案内
    try:
        game.log.append("[DEBUG] F9: 両キング取得テスト局面をセットしました（白番）。")
        game.log.append("  白K:e1 / 黒K:a6 / 白R:a1(選択済) / 黒R:e8")
        game.log.append("  白Ra1→a6で黒Kを取ってください。その後、黒Re8→e1で白Kを取ります。")
        game.log.append("  両方のKが取られた場合は引き分けになります。")
    except Exception:
        pass

    # デバッグモードONなら、利便性のため自動で「カード直後扱い」を付与
    if globals().get('DEBUG_COUNTER_CHECK_CARD_MODE', False):
        _debug_mark_card_played()
        pass


def restart_game():
    """ゲームを初期状態にリセットして再戦する"""
    global game_over, game_over_winner, chess_current_turn, selected_piece, highlight_squares, cpu_wait
    global log_scroll_offset
    
    # チェス盤を初期配置に
    chess.pieces[:] = chess.create_pieces()
    chess.en_passant_target = None
    chess.promotion_pending = None
    
    # ゲーム状態をリセット
    game_over = False
    game_over_winner = None
    chess_current_turn = 'white'
    selected_piece = None
    highlight_squares = []
    cpu_wait = False
    
    # カードゲーム部分もリセット
    global game, ai_player
    # Recreate game and AI according to the chosen deck mode
    game = new_game_with_mode(DECK_MODE)
    # ensure ai_player is also rebuilt to match deck size
    try:
        ai_player = build_ai_player(DECK_MODE)
    except Exception:
        ai_player = None
    log_scroll_offset = 0
    
    game.log.append("=== ゲームを再開しました ===")
    game.log.append("白のターンです。")

def create_pieces():
    # 互換のためのエイリアス（将来的に削除予定）
    return chess.create_pieces()


def show_start_screen():
    """起動時に難易度を選択する簡易メニュー。
    1-4 のキーか、画面上のボタンで選択可能。選択はグローバル CPU_DIFFICULTY に保存される。
    """
    # 選択結果をグローバルに反映
    global CPU_DIFFICULTY, W, H, screen
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
        # recompute fonts/layout each frame so start screen responds to VIDEORESIZE
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", max(32, int(H * 0.05)), bold=True)
        btn_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", max(20, int(H * 0.03)), bold=True)
        options = [("1 - 簡単", 1), ("2 - ノーマル", 2), ("3 - ハード", 3), ("4 - ベリーハード", 4)]
        # ボタン幅を広げてテキストが見切れないようにする
        btn_w = 240
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
                        show_deck_choice_modal(screen)
                    except Exception:
                        pass
                    # initialize game and AI according to chosen deck mode
                    try:
                        globals()['game'] = new_game_with_mode(DECK_MODE)
                        globals()['ai_player'] = build_ai_player(DECK_MODE)
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
                            show_deck_choice_modal(screen)
                        except Exception:
                            pass
                        try:
                            globals()['game'] = new_game_with_mode(DECK_MODE)
                            globals()['ai_player'] = build_ai_player(DECK_MODE)
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
                    # show deck editor (matches difficulty-screen behavior)
                    try:
                        show_deck_editor(screen)
                    except Exception:
                        show_deck_modal(screen)

        # draw background (image if available) - prefer sepia image
        if bg is not None:
            screen.blit(bg, (0,0))
            # If repo image is used, it's likely already properly exposed; apply a tiny brighten.
            if repo_bg_used:
                bright = pygame.Surface((W, H), pygame.SRCALPHA)
                bright.fill((255,255,255,20))
                screen.blit(bright, (0,0))
            else:
                # For user-provided images, apply stronger brighten to reach the desired level
                bright = pygame.Surface((W, H), pygame.SRCALPHA)
                bright.fill((255,255,255,100))
                screen.blit(bright, (0,0))
        else:
            # lighter sepia fallback
            screen.fill((150, 100, 50))

        # gentle dark overlay to maintain contrast but keep background visible
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,80))
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


# === デッキ管理システム ===
import json
from datetime import datetime

DECK_SAVE_FILE = os.path.join(os.path.dirname(__file__), 'saved_decks.json')

def load_saved_decks():
    """保存されたデッキをJSONファイルから読み込む。最大9個。"""
    if not os.path.exists(DECK_SAVE_FILE):
        return [None] * 9  # 空の9スロット
    try:
        with open(DECK_SAVE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 9スロット確保
            decks = data.get('decks', [])
            while len(decks) < 9:
                decks.append(None)
            return decks[:9]  # 最大9個まで
    except Exception:
        return [None] * 9

def save_decks_to_file(decks):
    """デッキリストをJSONファイルに保存"""
    try:
        with open(DECK_SAVE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'decks': decks}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"デッキ保存エラー: {e}")

def show_deck_modal(screen):
    """デッキリスト画面（3x3グリッド表示）"""
    decks = load_saved_decks()
    clock = pygame.time.Clock()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                
                # 戻るボタン
                back_rect = pygame.Rect(20, H - 70, 120, 50)
                if back_rect.collidepoint(mx, my):
                    return
                
                # 3x3グリッドのクリック判定
                grid_size = 240
                spacing = 30
                start_x = (W - (grid_size * 3 + spacing * 2)) // 2
                start_y = 120
                
                for row in range(3):
                    for col in range(3):
                        slot_idx = row * 3 + col
                        slot_x = start_x + col * (grid_size + spacing)
                        slot_y = start_y + row * (grid_size + spacing)
                        slot_rect = pygame.Rect(slot_x, slot_y, grid_size, grid_size)
                        
                        if slot_rect.collidepoint(mx, my):
                            if decks[slot_idx] is None:
                                # デッキ作成
                                new_deck = show_deck_editor(screen, None, slot_idx)
                                if new_deck:
                                    decks[slot_idx] = new_deck
                                    save_decks_to_file(decks)
                            else:
                                # デッキ編集/削除選択
                                action = show_deck_options(screen, decks[slot_idx])
                                if action == 'edit':
                                    edited = show_deck_editor(screen, decks[slot_idx], slot_idx)
                                    if edited:
                                        decks[slot_idx] = edited
                                        save_decks_to_file(decks)
                                elif action == 'delete':
                                    decks[slot_idx] = None
                                    save_decks_to_file(decks)
                            break
        
        # 背景
        screen.fill((240, 235, 230))
        
        # タイトル
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 36, bold=True)
        title = title_font.render("デッキリスト", True, (30, 30, 30))
        screen.blit(title, ((W - title.get_width()) // 2, 40))
        
        # 3x3グリッド描画
        grid_size = 240
        spacing = 30
        start_x = (W - (grid_size * 3 + spacing * 2)) // 2
        start_y = 120
        
        slot_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20, bold=True)
        for row in range(3):
            for col in range(3):
                slot_idx = row * 3 + col
                slot_x = start_x + col * (grid_size + spacing)
                slot_y = start_y + row * (grid_size + spacing)
                
                # スロット枠
                slot_rect = pygame.Rect(slot_x, slot_y, grid_size, grid_size)
                if decks[slot_idx] is None:
                    # 空きスロット
                    pygame.draw.rect(screen, (200, 200, 200), slot_rect)
                    pygame.draw.rect(screen, (100, 100, 100), slot_rect, 3)
                    text = slot_font.render("デッキ作成", True, (100, 100, 100))
                    screen.blit(text, (slot_x + (grid_size - text.get_width()) // 2, 
                                      slot_y + (grid_size - text.get_height()) // 2))
                else:
                    # デッキあり
                    pygame.draw.rect(screen, (220, 240, 255), slot_rect)
                    pygame.draw.rect(screen, (60, 100, 160), slot_rect, 4)
                    deck_name = decks[slot_idx].get('name', f'デッキ{slot_idx + 1}')
                    text = slot_font.render(deck_name, True, (30, 30, 30))
                    screen.blit(text, (slot_x + (grid_size - text.get_width()) // 2,
                                      slot_y + 20))
                    
                    # カード枚数表示
                    card_count = len(decks[slot_idx].get('cards', []))
                    count_text = SMALL.render(f"{card_count}枚", True, (60, 60, 60))
                    screen.blit(count_text, (slot_x + (grid_size - count_text.get_width()) // 2,
                                            slot_y + grid_size - 30))
        
        # 戻るボタン
        back_rect = pygame.Rect(20, H - 70, 120, 50)
        pygame.draw.rect(screen, (200, 200, 200), back_rect)
        pygame.draw.rect(screen, (80, 80, 80), back_rect, 3)
        back_text = FONT.render("戻る", True, (30, 30, 30))
        screen.blit(back_text, (back_rect.x + (back_rect.width - back_text.get_width()) // 2,
                               back_rect.y + (back_rect.height - back_text.get_height()) // 2))
        
        pygame.display.flip()
        clock.tick(30)


def show_deck_options(screen, deck):
    """デッキの編集/削除選択ダイアログ"""
    clock = pygame.time.Clock()
    
    while True:
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
        overlay.fill((0, 0, 0, 160))
        screen.blit(overlay, (0, 0))
        
        # ダイアログ
        dialog_w, dialog_h = 400, 250
        dialog_x = (W - dialog_w) // 2
        dialog_y = (H - dialog_h) // 2
        dialog_surf = pygame.Surface((dialog_w, dialog_h))
        dialog_surf.fill((245, 245, 250))
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
    
    # 日本語入力を有効化
    pygame.key.start_text_input()
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            
            # TEXTINPUT イベントで日本語・英数字入力を受け取る（Pygame 2.x以降）
            if event.type == pygame.TEXTINPUT and input_active:
                if len(input_text) < 20:
                    input_text += event.text
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.key.stop_text_input()
                    return None
                if input_active:
                    if event.key == pygame.K_RETURN:
                        input_active = False
                    elif event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                
                # 保存ボタン
                save_rect = pygame.Rect(win_w - 250, win_h - 70, 120, 50)
                if save_rect.collidepoint(mx, my):
                    # デッキ枚数チェック
                    if len(deck_cards) < 20:
                        print(f"DEBUG: save clicked with {len(deck_cards)} cards (<20) - entering confirmation dialog")
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
                                        print("DEBUG: user selected DISCARD in low-deck dialog")
                                        pygame.key.stop_text_input()
                                        return None  # 変更破棄してデッキリストへ

                                    # 保存するボタン
                                    save_anyway_rect = pygame.Rect(dialog_x + 280, dialog_y + 140, 160, 50)
                                    if save_anyway_rect.collidepoint(wmx, wmy):
                                        print("DEBUG: user selected SAVE ANYWAY in low-deck dialog")
                                        # 20枚未満だが保存して戻る
                                        pygame.key.stop_text_input()
                                        return {
                                            'name': input_text if input_text.strip() else f'デッキ{slot_idx + 1}',
                                            'cards': deck_cards,
                                            'created_at': existing_deck.get('created_at', datetime.now().isoformat()) if existing_deck else datetime.now().isoformat()
                                        }

                            # 警告ダイアログ描画
                            overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
                            overlay.fill((0, 0, 0, 160))
                            screen.blit(overlay, (0, 0))

                            dialog_surf = pygame.Surface((dialog_w, dialog_h))
                            dialog_surf.fill((245, 245, 250))
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
                
                # 名前入力欄
                name_rect = pygame.Rect(150, 20, 400, 40)
                if name_rect.collidepoint(mx, my):
                    input_active = True
                else:
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
        title_font = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 28, bold=True)
        title = title_font.render("デッキ作成/編集", True, (30, 30, 30))
        screen.blit(title, (20, 25))
        
        # 名前入力欄
        name_rect = pygame.Rect(150, 20, 400, 40)
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


def show_deck_modal_old(screen):
    """Simple deck modal - click/touch to close."""
    clock = pygame.time.Clock()
    w, h = 640, 420
    x = (W - w)//2
    y = (H - h)//2
    modal_surf = pygame.Surface((w, h))
    modal_surf.fill((245,245,250))
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
        overlay.fill((0,0,0,160))
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
    """Display a read-only menu of available custom decks; selecting one
    sets the game's deck to that selection (DECK_MODE='custom').
    """
    global DECK_MODE
    clk = pygame.time.Clock()
    decks = list_custom_decks() if 'list_custom_decks' in globals() else []
    if not decks:
        decks = ["作成デッキ(デフォルト)"]

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
                if 0 <= idx < len(decks):
                    sel = decks[idx]
                    if sel == "作成デッキ(デフォルト)":
                        DECK_MODE = 'custom'
                        globals()['game'] = new_game_with_mode(DECK_MODE)
                        globals()['ai_player'] = build_ai_player(DECK_MODE)
                        return
                    names = None
                    if 'load_custom_deck_by_name' in globals():
                        names = load_custom_deck_by_name(sel)
                    if names is None:
                        DECK_MODE = 'custom'
                        globals()['game'] = new_game_with_mode(DECK_MODE)
                        globals()['ai_player'] = build_ai_player(DECK_MODE)
                        return
                    DECK_MODE = 'custom'
                    try:
                        if 'build_game_from_card_names' in globals():
                            globals()['game'] = build_game_from_card_names(names)
                        else:
                            globals()['game'] = new_game_with_mode(DECK_MODE)
                        globals()['ai_player'] = build_ai_player(DECK_MODE)
                    except Exception:
                        globals()['game'] = new_game_with_mode(DECK_MODE)
                        globals()['ai_player'] = build_ai_player(DECK_MODE)
                    return

        # draw overlay and modal
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((245,245,250))
        pygame.draw.rect(surf, (80,80,80), (0,0,w,h), 3)
        title = FONT.render("作成デッキを選択してください", True, (30,30,30))
        surf.blit(title, (20, 12))

        ty = 0
        for i, name in enumerate(decks):
            ex = pygame.Rect(pad, start_y - y + ty, w - pad*2, entry_h)
            pygame.draw.rect(surf, (220,220,220), ex)
            pygame.draw.rect(surf, (70,70,70), ex, 2)
            ntxt = SMALL.render(name, True, (30,30,30))
            surf.blit(ntxt, (ex.x + 12, ex.y + (entry_h - ntxt.get_height())//2))
            cnt_txt = ""
            if name != "作成デッキ(デフォルト)":
                if 'load_custom_deck_by_name' in globals():
                    nms = load_custom_deck_by_name(name)
                    if nms is not None:
                        cnt_txt = f"{len(nms)} 枚"
            else:
                cnt_txt = "20 枚"
            if cnt_txt:
                ctxt = SMALL.render(cnt_txt, True, (80,80,80))
                surf.blit(ctxt, (ex.right - ctxt.get_width() - 12, ex.y + (entry_h - ctxt.get_height())//2))
            ty += entry_h + pad

        screen.blit(surf, (x,y))
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

    # layout
    w = 640
    h = 280
    x = (W - w) // 2
    y = (H - h) // 2

    # slider geometry
    slider_x = x + 40
    slider_y = y + 120
    slider_w = w - 80
    slider_h = 6

    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
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
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))

        surf = pygame.Surface((w, h))
        surf.fill((245,245,250))
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
            surf.blit(vol_txt, (40, sy + 24))
        except Exception:
            pass

        # Back button
        back_rect = pygame.Rect(w - 120, h - 56, 100, 40)
        pygame.draw.rect(surf, (220,220,220), back_rect)
        pygame.draw.rect(surf, (70,70,70), back_rect, 2)
        back_txt = SMALL.render("戻る", True, (30,30,30))
        surf.blit(back_txt, (back_rect.x + (back_rect.w - back_txt.get_width())//2, back_rect.y + (back_rect.h - back_txt.get_height())//2))

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
            cx = 12
            cy = h - credit_surf.get_height() - 12
            # draw outline slightly offset then main text
            surf.blit(outline, (cx + 1, cy + 1))
            surf.blit(credit_surf, (cx, cy))
        except Exception:
            pass

        screen.blit(surf, (x, y))
        pygame.display.flip()
        clk.tick(30)

        pygame.display.flip()
        clock.tick(30)

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
        else:
            ai_player.reset_pp()
            # draw 1 card if available and hand limit not exceeded
            if len(ai_player.hand.cards) < getattr(ai_player, 'hand_limit', 7):
                c = ai_player.deck.draw()
                if c:
                    ai_player.hand.add(c)
                    game.log.append("AI: ターン開始で1枚ドローしました。")
    except Exception:
        # defensive: ignore if ai_player not properly initialized
        pass

    # --- AI: consider playing a card before moving ---
    def ai_consider_play_card():
        # Ensure assignments to module-level AI flags affect globals (nested function)
        global ai_next_move_can_jump, ai_extra_moves_this_turn, ai_consecutive_turns
        # aggressiveness / per-attempt probability by difficulty
        # increased base play probability so AI uses cards more often on Easy/Normal
        probs = {1: 0.35, 2: 0.60, 3: 0.80, 4: 0.98}
        p_play = probs.get(CPU_DIFFICULTY, 0.45)
        if not ai_player.hand.cards:
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
        max_attempts = {1: 1, 2: 2, 3: 3, 4: 4}.get(CPU_DIFFICULTY, 2)
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
                            base = (len(prefer) - prefer.index(name)) * 10
                        else:
                            base = 5
                        score = base
                        # heuristics per card
                        if name == '暴風':
                            added = estimate_jump_added()
                            # reward if jump actually increases mobility
                            score += max(0, added) * 8
                        elif name == '氷結':
                            # prefer freezing non-king high-value pieces
                            try:
                                best_v = 0
                                for p in chess.pieces:
                                    if getattr(p, 'color', None) == 'white' and getattr(p, 'name', '') != 'K':
                                        v = {'P':1,'N':3,'B':3,'R':5,'Q':9}.get(getattr(p, 'name', ''), 0)
                                        best_v = max(best_v, v)
                                score += best_v * 6
                            except Exception:
                                pass
                        elif name == '灼熱':
                            # useful when opponent mobility >> ours
                            score += max(0, opp_move_count - my_move_count) * 6
                        elif name == '迅雷':
                            # prefer if capture opportunities exist or we have mobility to exploit
                            score += capture_ops * 8
                            # also prefer when AI mobility is lower than opponent
                            if my_move_count < opp_move_count:
                                score += 6
                        elif name == '2ドロー':
                            if len(ai_player.hand.cards) <= 2:
                                score += 20
                        elif name == '錬成':
                            # small preference to generate immediate value
                            score += 5
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

    # attempt to play a card (may mutate ai state)
    try:
        prev_turn_active = getattr(game, 'turn_active', False)
        # allow AI to play via game.play_card_for which requires turn_active
        game.turn_active = True
        ai_consider_play_card()
        game.turn_active = prev_turn_active
    except Exception:
        try:
            game.turn_active = prev_turn_active
        except Exception:
            pass
        pass

    # (animation rendering moved to draw_panel where board metrics are available)
    candidates = []  # list of (piece, move)
    for p in chess.pieces:
        if p.color != 'black':
            continue
        # Use wrapper to respect freeze/blocked tiles; ignore self-check here and handle per difficulty
        v = get_valid_moves(p, ignore_check=True)
        for mv in v:
            candidates.append((p, mv))

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
    apply_move(p, mv[0], mv[1])
    game.log.append(f"AI({CPU_DIFFICULTY}): {p.name} を {mv} に移動")
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


def get_card_image(name: str, size=(72, 96)):
    key = (name, size)
    if key in _image_cache:
        return _image_cache[key]
    surf = None
    # 1) 直接候補
    candidates = [f"{name}.png", f"{name}.PNG", f"{name}.jpg", f"{name}.jpeg", f"{name}.webp", f"{name}.bmp"]
    for cand in candidates:
        path = os.path.join(IMG_DIR, cand)
        if os.path.exists(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                surf = pygame.transform.smoothscale(img, size)
                break
            except Exception:
                pass
    # 2) 再帰的にベース名一致を探索（拡張子/大文字小文字を無視）
    if surf is None and os.path.isdir(IMG_DIR):
        base_l = name.lower()
        for root, _dirs, files in os.walk(IMG_DIR):
            for f in files:
                fn, ext = os.path.splitext(f)
                if fn.lower() == base_l and ext.lower() in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                    try:
                        path = os.path.join(root, f)
                        img = pygame.image.load(path).convert_alpha()
                        surf = pygame.transform.smoothscale(img, size)
                        break
                    except Exception:
                        continue
    # If no image was found, create a simple placeholder surface so callers can blit safely
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((220, 220, 230))
        pygame.draw.rect(surf, (80, 80, 80), (0, 0, size[0], size[1]), 2)
        try:
            txt = SMALL.render(name, True, (30, 30, 30))
            surf.blit(txt, ((size[0]-txt.get_width())//2, (size[1]-txt.get_height())//2))
        except Exception:
            pass

    _image_cache[key] = surf
    return surf

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


def draw_text(surf, text, x, y, color=(20, 20, 20)):
    img = FONT.render(text, True, color)
    rect = surf.blit(img, (x, y))
    return rect


def wrap_text(text: str, max_width: int):
    """Return list of lines wrapped to fit max_width using FONT metrics."""
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


def compute_layout(win_w: int, win_h: int):
    """Compute common layout metrics used by draw_panel and input handling.
    Returns a dict with keys:
        left_margin, left_panel_width, right_panel_width, right_panel_x,
        board_left, board_top, board_size, board_area_top, board_area_height,
        card_area_top, scale
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


def draw_panel():
    # 背景画像があればそれを描画し、なければ従来の塗りつぶしを行う
    global log_toggle_rect, play_bg_img, play_bg_surf
    try:
        # 初回: 画像ファイルがあればロードしてキャッシュ
        if play_bg_img is None and play_bg_surf is None:
            try:
                bg_path = os.path.join(IMG_DIR, PLAY_BG_FILENAME)
                if os.path.exists(bg_path):
                    play_bg_img = pygame.image.load(bg_path)
            except Exception:
                play_bg_img = None

        # play_bg_img が存在すれば現在のウィンドウサイズに合わせてスケールして描画
        if play_bg_img is not None:
            try:
                play_bg_surf = pygame.transform.smoothscale(play_bg_img, (W, H)).convert()
                screen.blit(play_bg_surf, (0, 0))
            except Exception:
                # スケーリングや描画に失敗した場合は単色で塗りつぶす
                screen.fill((240, 240, 245))
        else:
            screen.fill((240, 240, 245))
    except Exception:
        # どこかで例外が出ても UI が壊れないようにフォールバック
        try:
            screen.fill((240, 240, 245))
        except Exception:
            pass

    # === レイアウト設定: 左側に基本情報、その右にチェス盤を画面上部から配置 ===
    # Use shared responsive layout so left/right panels and board stay balanced
    layout = compute_layout(W, H)
    left_panel_width = layout['left_panel_width']
    left_margin = layout['left_margin']
    top_margin = layout['board_area_top']

    # 基本情報の配置（左側）
    info_x = left_margin
    info_y = top_margin
    line_height = 35
    
    # ターン数
    draw_text(screen, f"ターン: {game.turn}", info_x, info_y)
    info_y += line_height
    
    # PP
    draw_text(screen, f"PP: {game.player.pp_current}/{game.player.pp_max}", info_x, info_y)
    info_y += line_height
    # 現在のチェック状態を左パネル上部に明示（同時チェック時は両方表示）
    # PPの下の表示を非表示（下部に表示されるため）
    # try:
    #     w_check = is_in_check_for_display(chess.pieces, 'white')
    #     b_check = is_in_check_for_display(chess.pieces, 'black')
    #     if w_check or b_check:
    #         col = (230, 120, 0)
    #         if w_check:
    #             draw_text(screen, "白チェック中", info_x, info_y, col)
    #             info_y += line_height - 10
    #         if b_check:
    #             draw_text(screen, "黒チェック中", info_x, info_y, col)
    #             info_y += line_height - 10
    # except Exception:
    #     pass
    # 簡易エフェクト表示: 次に発動する特別アクションを左パネルに表示
    # 表記ルール: 「次：飛越可」「次：追加行動×n」
    if getattr(game.player, 'next_move_can_jump', False):
        draw_text(screen, "次：飛越可", info_x, info_y, (10, 40, 180))
        info_y += line_height - 6
    # 迅雷効果の表示（player_consecutive_turnsを使用）
    consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    if consecutive_turns > 0:
        info_y += 6
        label = "次：追加行動" if consecutive_turns == 1 else f"次：追加行動×{consecutive_turns}"
        draw_text(screen, label, info_x, info_y, (10, 120, 10))
        info_y += line_height - 6
    info_y += line_height
    
    # 山札
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", info_x, info_y, (40,40,90))
    info_y += line_height
    
    # 墓地表示（クリック可能領域として矩形を保存）
    grave_text = f"墓地: {len(game.player.graveyard)}枚"
    global grave_label_rect
    grave_label_rect = draw_text(screen, grave_text, info_x, info_y, (90,40,40))
    info_y += line_height
    
    # 相手の手札表示（クリック可能領域として矩形を保存）
    opponent_hand_text = f"相手の手札: {get_opponent_hand_count()}枚"
    global opponent_hand_rect
    opponent_hand_rect = draw_text(screen, opponent_hand_text, info_x, info_y, (100,50,100))
    info_y += line_height

    # マウスでも押せる『ターン開始(T)』ボタンを左パネルに配置
    global start_turn_rect
    btn_w, btn_h = 160, 36
    start_turn_rect = pygame.Rect(info_x, info_y, btn_w, btn_h)
    # 押下可否に応じて色分け
    can_start = (getattr(game, 'pending', None) is None) and (not getattr(game, 'turn_active', False)) and (chess_current_turn == 'white') and (not cpu_wait) and (not game_over)
    bg_col = (60, 140, 220) if can_start else (140, 140, 140)
    pygame.draw.rect(screen, bg_col, start_turn_rect)
    pygame.draw.rect(screen, (255,255,255), start_turn_rect, 2)
    lab = FONT.render("ターン開始 (T)", True, (255,255,255))
    screen.blit(lab, (start_turn_rect.x + (btn_w - lab.get_width())//2, start_turn_rect.y + (btn_h - lab.get_height())//2))
    info_y += line_height
    
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
    draw_text(screen, "操作:", help_x, help_y, (60, 60, 100))
    help_y += 24
    for hl in HELP_LINES:  # 全ての操作を表示
        draw_text(screen, hl, help_x, help_y, (30, 30, 90))
        help_y += 20

    # === チェス盤エリア: 左側パネルの右、画面上部から開始 ===
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

    # --- カード効果の視覚化オーバーレイ ---
    # 表示: 封鎖マス (赤の半透明)、凍結駒 (青の半透明に「凍」マーク)
    try:
        for (br, bc), turns in getattr(game, 'blocked_tiles', {}).items():
            bx = board_left + bc * square_w
            by = board_top + br * square_h
            s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
            s.fill((200, 30, 30, 120))
            screen.blit(s, (bx, by))
            # ターン数を小さく表示
            ttxt = TINY.render(str(turns), True, (255,255,255))
            screen.blit(ttxt, (bx + 4, by + 4))
            # 所有者表示（白/黒の頭文字）
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
        if heat_gif_anim.get('playing') and heat_gif_anim.get('frames'):
            elapsed = _ct_time.time() - heat_gif_anim.get('start_time', 0.0)
            total = heat_gif_anim.get('total_duration', 0.0)
            frames = heat_gif_anim.get('frames')
            durations = heat_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                # stop animation
                heat_gif_anim['playing'] = False
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
                pos = heat_gif_anim.get('pos')
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
        if ic_gif_anim.get('playing') and ic_gif_anim.get('frames'):
            elapsed = _ct_time.time() - ic_gif_anim.get('start_time', 0.0)
            total = ic_gif_anim.get('total_duration', 0.0)
            frames = ic_gif_anim.get('frames')
            durations = ic_gif_anim.get('durations') or [1000]
            if elapsed >= total:
                ic_gif_anim['playing'] = False
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
                pos = ic_gif_anim.get('pos')
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

    # --- 封鎖タイルでのループ再生: Image_MG.gif (player) / Image_MG_2P.gif (AI) ---
    try:
        # ensure both variants are loaded (2P may fallback to standard MG)
        _ensure_mg_gif_loaded()
        _ensure_mg_gif_2p_loaded()

        # if neither is available, skip
        if not (mg_gif_frames_cache or mg_gif_2p_frames_cache):
            raise Exception("no mg gif available")

        # We'll compute per-variant total_ms as needed
        now_ms = int(_ct_time.time() * 1000)

        for (br, bc), turns in getattr(game, 'blocked_tiles', {}).items():
            # only show while turns > 0
            if not turns:
                continue
            bx = board_left + bc * square_w
            by = board_top + br * square_h

            # select which gif variant to use based on blocked_tiles_owner
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

    # --- ターン表示テロップ（中央・1秒表示） ---
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
            screen.blit(shadow, (tx + 2, ty + 2))
            screen.blit(telop_surf, (tx, ty))
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
            # background box
            try:
                tmp = pygame.Surface((notice_surf.get_width()+20, notice_surf.get_height()+12), pygame.SRCALPHA)
                tmp.fill((0,0,0,160))
                screen.blit(tmp, (bx-10, by-6))
            except Exception:
                pygame.draw.rect(screen, (0,0,0), (bx-10, by-6, notice_surf.get_width()+20, notice_surf.get_height()+12))
            screen.blit(shadow, (bx+2, by+2))
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
    
    # === チェック中の表示（Chess Main準拠）===
    if not game_over:
        check_colors = []
        # 表示用には凍結駒も含めた全ての脅威を表示
        # またカード効果（迅雷の追加行動・暴風のジャンプ等）でキングを攻撃可能なら表示する
        if is_in_check_for_display(chess.pieces, 'white') or can_attack_king_with_cards(chess.pieces, 'white'):
            check_colors.append('white')
        if is_in_check_for_display(chess.pieces, 'black') or can_attack_king_with_cards(chess.pieces, 'black'):
            check_colors.append('black')
        
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
                    tmp.fill((0, 0, 0, 160))
                    screen.blit(tmp, (bg_rect.x, bg_rect.y))
                except Exception:
                    pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(screen, (255, 165, 0), bg_rect, 2)
                screen.blit(check_text, (check_x, check_y + idx * (text_h + 10)))

    # === 右側エリア: ログ（切替式）===
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
        log_toggle_rect = draw_text(screen, "ログ履歴 [L]閉じる", log_panel_left + 10, log_panel_top + 8, (60, 60, 100))
        # 見出しのすぐ下にスクロールのヒントを表示
        draw_text(screen, "↑↓ / ホイールでスクロール", log_panel_left + 10, log_panel_top + 30, (100, 100, 120))

        # ログの折り返し処理
        wrapped_lines = []
        max_log_width = log_panel_width - 30
        for line in game.log:
            for wline in wrap_text(f"• {line}", max_log_width):
                wrapped_lines.append(wline)

        # スクロールオフセットの範囲制限
        global log_scroll_offset
        # 下部に余白を設けて見やすくする（最後の行が枠にくっつかないように）
        bottom_padding_px = 28  # ここを調整すると余白サイズを変更できます
        max_lines_visible = max(0, (log_panel_height - 50 - bottom_padding_px) // 22)
        max_scroll = max(0, len(wrapped_lines) - max_lines_visible)
        log_scroll_offset = max(0, min(log_scroll_offset, max_scroll))

        # 表示範囲を計算（最新が下）
        if len(wrapped_lines) <= max_lines_visible:
            visible_lines = wrapped_lines
        else:
            start_idx = len(wrapped_lines) - max_lines_visible - log_scroll_offset
            start_idx = max(0, start_idx)
            visible_lines = wrapped_lines[start_idx:start_idx + max_lines_visible]

        # ログ描画開始位置（見出しとヒントの下）
        log_y = log_panel_top + 56
        for wline in visible_lines:
            if log_y < log_panel_top + log_panel_height - bottom_padding_px:
                draw_text(screen, wline, log_panel_left + 10, log_y, (60, 60, 60))
                log_y += 22

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
            total_lines = len(wrapped_lines)
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
    else:
        # ログ非表示時のヒント (右パネルに寄せる)
        draw_text(screen, "[L] ログ表示", layout['right_panel_x'] + 12, board_area_top + board_area_height - 30, (100, 100, 120))

    # === 下部エリア: 手札（左から横並び最大7枚） ===
    # ボードの下に左詰めで横並びで表示
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
        
        # カード下部にボタン番号を表示
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


    # === 状態表示（右下）===
    # ご要望により、右下の『封鎖/凍結/追加行動/次』の簡易表示は非表示にします。
    # （必要になったら下記を有効化してください）
    # state_x = layout['right_panel_x'] + 12
    # state_y = layout['card_area_top'] + 40
    # draw_text(screen, f"封鎖: {len(getattr(game, 'blocked_tiles', {}))}", state_x, state_y, (80, 80, 80))
    # state_y += 20
    # draw_text(screen, f"凍結: {len(getattr(game, 'frozen_pieces', {}))}", state_x, state_y, (80, 80, 80))
    # state_y += 20
    # consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    # draw_text(screen, f"追加行動: {consecutive_turns}", state_x, state_y, (80, 80, 80))
    # state_y += 20
    # if game.player.next_move_can_jump:
    #     draw_text(screen, "次: 飛越可", state_x, state_y, (0, 120, 0))

    # === 墓地オーバーレイ ===
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

    # === 相手の手札オーバーレイ ===
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

    # === カード拡大表示オーバーレイ ===
    if enlarged_card_index is not None and 0 <= enlarged_card_index < len(game.player.hand.cards):
        c = game.player.hand.cards[enlarged_card_index]
        
        # 拡大カードサイズ
        enlarged_w = 300
        enlarged_h = 420
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
    elif enlarged_card_name is not None:
        # 手札以外（例: 墓地）からの拡大表示
        enlarged_w = 300
        enlarged_h = 420
        enlarged_x = (W - enlarged_w) // 2
        enlarged_y = (H - enlarged_h) // 2

        dark_overlay = pygame.Surface((W, H))
        dark_overlay.fill((0, 0, 0))
        dark_overlay.set_alpha(150)
        screen.blit(dark_overlay, (0, 0))

        large_img = get_card_image(enlarged_card_name, size=(enlarged_w, enlarged_h))
        screen.blit(large_img, (enlarged_x, enlarged_y))

    # === 保留中の操作説明オーバーレイ ===
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

    # === プロモーション選択オーバーレイ ===
    if chess.promotion_pending is not None:
        promot = chess.promotion_pending
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
        # Do not show AI thinking overlay while a promotion selection is pending.
        if cpu_wait and THINKING_ENABLED and not game_over and getattr(chess, 'promotion_pending', None) is None:
            import time
            # Restrict overlay to the board area so it stays within the chessboard
            bs = board_size
            bx = board_left
            by = board_top
            overlay = pygame.Surface((bs, bs), pygame.SRCALPHA)
            overlay.fill((0,0,0,140))
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

    # --- ゲーム終了画面（勝敗表示と再戦ボタン） ---
    if game_over:
        # 半透明オーバーレイを全画面に表示
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))
        
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



def attempt_start_turn():
    """[T]と同等のターン開始処理をUIやマウスからも呼べるように関数化。"""
    global notice_msg, notice_until, turn_telop_msg, turn_telop_until, log_scroll_offset
    if getattr(game, 'pending', None) is not None:
        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
        return
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
    game.start_turn()
    try:
        turn_telop_msg = "YOUR TURN"
        turn_telop_until = _ct_time.time() + 1.0
    except Exception:
        pass
    log_scroll_offset = 0


def handle_keydown(key):
    global log_scroll_offset, show_log, enlarged_card_index, notice_msg, notice_until, show_grave, show_opponent_hand
    
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

    # --- DEBUG: 盤面セットショートカット ---
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
    # F8とF9のデバッグ機能を無効化（通常プレイ時に誤操作を防ぐため）
    # if key == pygame.K_F8:
    #     debug_setup_counter_check_white()
    #     return
    # if key == pygame.K_F9:
    #     debug_setup_simul_check_start()
    #     return
    
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
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
    global enlarged_card_index, enlarged_card_name, selected_piece, highlight_squares, chess_current_turn, show_grave, show_opponent_hand, notice_msg, notice_until, game_over
    
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
            restart_game()
            return
        if hasattr(draw_panel, 'quit_rect') and draw_panel.quit_rect.collidepoint(pos):
            pygame.quit()
            sys.exit(0)
        return

    # 1) 最優先: カード拡大の解除（他の操作より先に判定して閉じる）
    if enlarged_card_index is not None or enlarged_card_name is not None:
        enlarged_card_index = None
        enlarged_card_name = None
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
                    else:
                        enlarged_card_name = card_name
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
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。PPは{game.player.pp_current}/{game.player.pp_max}。")
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
                game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。PPは{game.player.pp_current}/{game.player.pp_max}。")
                _debug_mark_card_played()
            info = {'turns': game.pending.info.get('turns', 2), 'max_tiles': game.pending.info.get('max_tiles', 3), 'selected': [], 'for_color': 'black'}
            game.pending = PendingAction(kind='target_tiles_multi', info=info)
            return
    
    # カードのクリック判定（優先）
    for rect, idx in card_rects:
        if rect.collidepoint(pos):
            # 閲覧（拡大表示）はターン開始前でも許可する
            if enlarged_card_index == idx:
                enlarged_card_index = None
            else:
                enlarged_card_index = idx
            return

    # --- プロモーション選択オーバーレイクリック対応 ---
    if chess.promotion_pending is not None and hasattr(draw_panel, 'promo_rects'):
        for r, o in draw_panel.promo_rects:
            if r.collidepoint(pos):
                # 選択された昇格駒で置き換え
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
                    try:
                        game.blocked_tiles[(row, col)] = turns
                        game.blocked_tiles_owner[(row, col)] = applies_to
                    except Exception:
                        # Fallback to simple int-only mapping
                        game.blocked_tiles[(row, col)] = turns
                    try:
                        play_heat_gif_at(row, col)
                    except Exception:
                        pass
                    game.log.append(f"封鎖: {(row,col)} を {turns} ターン封鎖 (対象: {applies_to})")
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
                        game.log.append(f"封鎖候補から {(row,col)} を解除 ({len(sel)}/{tmax})")
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
                        game.log.append(f"封鎖候補に {(row,col)} を追加 ({len(sel)}/{tmax})")
                        # APPLY only when reached required count
                        if len(sel) >= tmax:
                            turns = game.pending.info.get('turns', 2)
                            applies_to = game.pending.info.get('for_color', 'black')
                            for (r, c) in sel:
                                try:
                                    game.blocked_tiles[(r, c)] = turns
                                    game.blocked_tiles_owner[(r, c)] = applies_to
                                except Exception:
                                    game.blocked_tiles[(r, c)] = turns
                            game.log.append(f"封鎖: {sel} を {turns} ターン封鎖 (対象: {applies_to})")
                            game.pending = None
                        return
                else:
                    game.log.append("そのマスは空ではありません。別のマスを選んでください。")
                    return
            elif getattr(game, 'pending', None) is not None and game.pending.kind == 'target_piece_unfreeze':
                # must select one own frozen piece to unfreeze
                # assume player controls white pieces
                player_color = 'white'
                clicked_color = None
                try:
                    clicked_color = clicked.color
                except Exception:
                    try:
                        clicked_color = clicked.get('color') if clicked is not None else None
                    except Exception:
                        clicked_color = None
                if clicked is not None and clicked_color is not None and clicked_color == player_color:
                    pid = None
                    try:
                        pid = id(clicked)
                    except Exception:
                        try:
                            pid = clicked.get('id')
                        except Exception:
                            pid = None
                    if pid is not None and pid in game.frozen_pieces:
                        try:
                            del game.frozen_pieces[pid]
                        except Exception:
                            pass
                            # Also clear transient attribute on the piece object if present
                            try:
                                if clicked is not None and hasattr(clicked, 'frozen_turns'):
                                    try:
                                        delattr(clicked, 'frozen_turns')
                                    except Exception:
                                        try:
                                            del clicked.frozen_turns
                                        except Exception:
                                            pass
                            except Exception:
                                pass
                        try:
                            name = clicked.name
                        except Exception:
                            name = clicked.get('name', str(clicked)) if clicked is not None else '駒'
                        game.log.append(f"凍結解除: {name} の凍結を解除しました。")
                        game.pending = None
                    else:
                        game.log.append("その駒は凍結されていません。自分の凍結駒を選択してください。")
                else:
                    game.log.append("自分の駒を選択してください。")
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
                    if engine_piece is not None:
                        # record on canonical engine piece
                        try:
                            game.frozen_pieces[id(engine_piece)] = turns
                        except Exception:
                            game.frozen_pieces[id(engine_piece)] = turns
                        try:
                            setattr(engine_piece, 'frozen_turns', turns)
                        except Exception:
                            pass
                        target_for_log = engine_piece
                    else:
                        # fallback: record on clicked object (dict or other)
                        try:
                            game.frozen_pieces[id(clicked)] = turns
                        except Exception:
                            game.frozen_pieces[id(clicked)] = turns
                        try:
                            setattr(clicked, 'frozen_turns', turns)
                        except Exception:
                            pass
                        target_for_log = clicked
                    # try to get a readable name
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
                            game.log.append("[DEBUG] カード使用扱いフラグを消費しました。")
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
                chess_log.append(f"{name} を {(row,col)} へ移動")
                
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
                            game_over = True
                            game_over_winner = 'black'
                            game.log.append("YOU LOSE！黒の勝利！")
                        elif not black_king_exists:
                            game_over = True
                            game_over_winner = 'white'
                            game.log.append("YOU WIN！白の勝利")
                
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
                            # 白の手番が終了したので、白にかかっている時限効果（氷結など）を減衰させる
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
                    # クリア
                    selected_piece = None
                highlight_squares = []
                # AI の手
                if chess_current_turn == 'black':
                    import time
                    global cpu_wait, cpu_wait_start
                    cpu_wait = True
                    cpu_wait_start = time.time()
            else:
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
    # スクロール関連の初期化（ローカル扱いによるUnboundLocalErrorを防止）
    global dragging_scrollbar, drag_start_y, drag_start_offset, scrollbar_rect
    dragging_scrollbar = False
    drag_start_y = 0
    drag_start_offset = 0
    # scrollbar_rect は draw_panel 内で更新されるが、初期 None を明示
    scrollbar_rect = None
    
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
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit(0)
            elif event.type == pygame.KEYDOWN:
                handle_keydown(event.key)
            elif event.type == pygame.VIDEORESIZE:
                # Window was resized (including maximize). Update globals and recreate screen surface.
                try:
                    global W, H, screen
                    W, H = max(200, event.w), max(200, event.h)
                    screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
                except Exception:
                    # If resizing fails for any reason, ignore and continue with previous size
                    pass
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左クリック
                    # スクロールバーつまみのドラッグ開始判定
                    if show_log and scrollbar_rect and scrollbar_rect.collidepoint(event.pos):
                        dragging_scrollbar = True
                        drag_start_y = event.pos[1]
                        drag_start_offset = log_scroll_offset
                    else:
                        handle_mouse_click(event.pos)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging_scrollbar = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging_scrollbar and show_log and scrollbar_rect:
                    # ドラッグ量に応じてスクロールオフセットを変更
                    thumb_top = scrollbar_rect.top
                    thumb_height = scrollbar_rect.height
                    # スクロールバー全体の高さ
                    bar_top = scrollbar_rect.top - (log_scroll_offset / max(1, log_scroll_offset)) * thumb_height
                    bar_height = scrollbar_rect.height / max(1, thumb_height)
                    # ドラッグした距離
                    dy = event.pos[1] - drag_start_y
                    # スクロールバーの移動量をログオフセットに変換
                    # draw_panelで計算したmax_scroll, scrollbar_height, thumb_heightを再利用
                    # ここではスクロールバーの移動量をmax_scrollに比例させる
                    # まずdraw_panelを呼び出して最新の値を取得
                    # ただし、draw_panelは毎フレーム呼ばれるので、ここではlog_scroll_offsetのみ更新
                    # スクロールバーの高さ（draw_panelで定義）
                    # つまみの移動可能範囲 = scrollbar_height - thumb_height
                    # dy / (scrollbar_height - thumb_height) = scroll_ratioの変化
                    # scroll_ratio = log_scroll_offset / max_scroll
                    # 新しいscroll_ratio = (thumb_y + dy - scrollbar_y) / (scrollbar_height - thumb_height)
                    # まずdraw_panelで必要な値を取得
                    # draw_panel()の中でmax_scroll, scrollbar_height, thumb_height, scrollbar_yが定義されている
                    # ここではそれらをグローバル変数にしておくと良い
                    # ただし、draw_panel()の中でしか値が確定しないので、
                    # ここでは簡易的にdyをscroll_offsetに変換
                    # つまみの移動可能範囲
                    move_range = max(1, scrollbar_rect.height * 10)  # 仮の値（実際はdraw_panelの値を使うべき）
                    # 仮のmax_scroll（draw_panelの値を使うべき）
                    max_scroll = 30  # 仮の値（実際はdraw_panelの値を使うべき）
                    # dyをmax_scrollに比例させる
                    new_offset = drag_start_offset + int(dy * max_scroll / move_range)
                    log_scroll_offset = max(0, min(new_offset, max_scroll))
            elif event.type == pygame.MOUSEWHEEL:
                # マウスホイールでログスクロール（ログ表示中のみ）
                if show_log:
                    if event.y > 0:  # 上スクロール
                        log_scroll_offset += 1
                    elif event.y < 0:  # 下スクロール
                        log_scroll_offset = max(0, log_scroll_offset - 1)

        # --- チェック/同時チェックの監視と勝敗処理 ---
        # チェス手番の開始を検知（色が切り替わったフレーム）
        if globals().get('last_turn_color', None) != chess_current_turn:
            # 手番インデックス更新
            if chess_current_turn == 'white':
                globals()['white_turn_index'] = globals().get('white_turn_index', 0) + 1
            else:
                globals()['black_turn_index'] = globals().get('black_turn_index', 0) + 1
            globals()['last_turn_color'] = chess_current_turn

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
                    # 白のキングのみ取られた場合は黒の勝利
                    elif not white_king_exists:
                        game_over = True
                        game_over_winner = 'black'
                        game.log.append("同時チェック: 白のキングが取られました。黒の勝利！")
                    # 黒のキングのみ取られた場合は白の勝利
                    elif not black_king_exists:
                        game_over = True
                        game_over_winner = 'white'
                        game.log.append("同時チェック: 黒のキングが取られました。白の勝利！")
                    # 両者のキングが残っている場合
                    elif white_king_exists and black_king_exists:
                        # 両者とも解除失敗の場合は引き分け
                        if wres == 'failed' and bres == 'failed':
                            game_over = True
                            game_over_winner = 'draw'
                            game.log.append("同時チェック: 両者とも解除できませんでした。引き分け。")
                        # 白のみ解除成功
                        elif wres == 'cleared' and bres == 'failed':
                            game_over = True
                            game_over_winner = 'white'
                            game.log.append("同時チェック: 白のみ解除成功。白の勝利！")
                        # 黒のみ解除成功
                        elif wres == 'failed' and bres == 'cleared':
                            game_over = True
                            game_over_winner = 'black'
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

        # --- チェックメイト判定と勝利条件チェック ---
        # 迅雷使用中はキング取得判定を常に行う（同時チェック中でも即座に勝敗判定）
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
                            globals()['dual_king_capture_test'] = False
                            globals()['first_king_captured'] = None
                else:
                    # 通常モード: 既存の処理
                    # まず両者のキング不在を最優先で引き分け判定
                    if not white_king and not black_king:
                        game_over = True
                        game_over_winner = 'draw'
                        game.log.append("両者のキングが取られました。引き分け。")
                        if globals().get('simul_check_active', False):
                            globals()['simul_check_active'] = False
                            globals()['simul_white_deadline_turn'] = None
                            globals()['simul_black_deadline_turn'] = None
                            globals()['simul_white_result'] = 'none'
                            globals()['simul_black_result'] = 'none'
                    elif not white_king:
                        game_over = True
                        game_over_winner = 'black'
                        game.log.append("YOU LOSE！黒の勝利！")
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
                        # 同時チェック状態をクリア
                        if globals().get('simul_check_active', False):
                            globals()['simul_check_active'] = False
                            globals()['simul_white_deadline_turn'] = None
                            globals()['simul_black_deadline_turn'] = None
                            globals()['simul_white_result'] = 'none'
                            globals()['simul_black_result'] = 'none'
                        globals()['simul_white_result'] = 'none'
                        globals()['simul_black_result'] = 'none'
        
        # チェックメイトとステイルメイトの判定（同時チェック中はスキップ）
        if not game_over and not globals().get('simul_check_active', False):
            # どちらかが詰みの場合も勝利判定（カード効果込みの合法手判定を使用）
            if not has_legal_moves_with_cards('white') and is_in_check(chess.pieces, 'white'):
                game_over = True
                game_over_winner = 'black'
                game.log.append("YOU LOSE！黒の勝利！")
            elif not has_legal_moves_with_cards('black') and is_in_check(chess.pieces, 'black'):
                game_over = True
                game_over_winner = 'white'
                game.log.append("YOU WIN！白の勝利！")
            # ステイルメイト（合法手がないがチェックでない）の判定（カード効果込み）
            elif not has_legal_moves_with_cards(chess_current_turn) and not is_in_check(chess.pieces, chess_current_turn):
                game_over = True
                game_over_winner = 'draw'
                game.log.append("ステイルメイト（引き分け）")

        # === 自動処理されるpending ===
        if getattr(game, 'pending', None) is not None:
            # ハンです☆: 相手の手札をランダムで墓地に送る
            if game.pending.kind == 'discard_opponent_hand':
                import random
                if ai_player.hand.cards:
                    idx = random.randrange(len(ai_player.hand.cards))
                    discarded_card = ai_player.hand.cards[idx]
                    ai_player.hand.remove_at(idx)
                    ai_player.graveyard.append(discarded_card)
                    game.log.append(f"『ハンです☆』: 相手の手札から『{discarded_card.name}』をランダムで墓地に送りました。")
                else:
                    game.log.append("『ハンです☆』: 相手の手札が空です。")
                game.pending = None
            
            # 命がけのギャンブル: ルーク・キング以外の駒をクイーンに変える
            elif game.pending.kind == 'gamble_promote':
                target_color = game.pending.info.get('target_color', 'white')
                success = game.pending.info.get('success', False)
                
                promoted_count = 0
                for piece in chess.pieces:
                    if piece.color == target_color and piece.kind not in ['K', 'R']:
                        piece.kind = 'Q'  # クイーンに昇格
                        promoted_count += 1
                
                if success:
                    game.log.append(f"『命がけのギャンブル』成功！自分の{promoted_count}個の駒がクイーンに昇格しました！")
                else:
                    game.log.append(f"『命がけのギャンブル』失敗...相手の{promoted_count}個の駒がクイーンに昇格しました...")
                
                # ターンスキップ（プレイヤーの手番を終了）
                if chess_current_turn == 'white':
                    chess_current_turn = 'black'
                    cpu_wait = True
                    cpu_wait_start = _ct_time.time()
                    game.log.append("自ターンをスキップします。")
                
                game.pending = None

        draw_panel()
        pygame.display.flip()

        # Non-blocking AI wait handling (ゲーム終了時は無効化)
        if cpu_wait and THINKING_ENABLED and not game_over:
            import time
            # If a promotion selection is pending, postpone AI until the promotion is resolved by the player.
            # This avoids the AI automatically playing while the UI is waiting for the player to choose
            # the promotion piece.
            if getattr(chess, 'promotion_pending', None) is not None:
                # reset timer so AI wait restarts after promotion is handled
                cpu_wait_start = time.time()
            elif time.time() - cpu_wait_start >= AI_THINK_DELAY:
                # call AI move
                ai_make_move()
                # After AI move, check if AI has extra consecutive turns (迅雷)
                try:
                    a_cct = getattr(game, 'ai_consecutive_turns', 0)
                except Exception:
                    a_cct = 0

                if a_cct and a_cct > 0:
                    # consume one AI extra-turn and schedule another AI think cycle
                    try:
                        game.ai_consecutive_turns -= 1
                    except Exception:
                        setattr(game, 'ai_consecutive_turns', max(0, a_cct-1))
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
    except Exception:
        pass
    main_loop()