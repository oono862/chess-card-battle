#カードゲーム部分実装
import pygame
from pygame import Rect
import sys
import os

try:
    from .card_core import new_game_with_sample_deck, new_game_with_rule_deck, PlayerState, make_rule_cards_deck, PendingAction
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck, PlayerState, make_rule_cards_deck, PendingAction

# チェスロジックを外部モジュール化（Chess MainのPieceクラス実装）
try:
    from . import chess_engine as chess
except Exception:
    import chess_engine as chess


pygame.init()

# 画面設定
W, H = 1200, 800
# Allow the user to resize/minimize/maximize the game window
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("カードゲーム デモ")
clock = pygame.time.Clock()

# Base UI resolution used for consistent scaling between windowed and fullscreen
BASE_UI_W = 1200
BASE_UI_H = 800

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)

# ゲーム状態
# ルール表のカードを試したい場合は下を使う
game = new_game_with_rule_deck()
# --- AI 用のカードプレイヤー状態を作る ---
ai_player = PlayerState(deck=make_rule_cards_deck())
# 初期 PP と手札を配る（簡易）
ai_player.reset_pp()
for _ in range(4):
    c = ai_player.deck.draw()
    if c is not None:
        ai_player.hand.add(c)
# AI 用のギミックフラグ
ai_next_move_can_jump = False
ai_extra_moves_this_turn = 0
ai_consecutive_turns = 0
show_grave = False
show_log = False  # ログ表示切替（デフォルト非表示）
log_scroll_offset = 0  # ログスクロール用オフセット（0=最新）
enlarged_card_index = None  # 拡大表示中のカードインデックス（None=非表示）
enlarged_card_name = None  # 墓地など手札以外の拡大表示用カード名（未定義での参照を防止）
show_opponent_hand = False  # 相手の手札表示切替（デフォルト非表示）
opponent_hand_count = 5  # 相手の手札枚数（仮の値、実際はゲームロジックから取得）

# CPU 難易度 (1=Easy,2=Medium,3=Hard,4=Expert)
CPU_DIFFICULTY = 2

# 画像の読み込み（カード名と同じファイル名.png を images 配下から探す）
IMG_DIR = os.path.join(os.path.dirname(__file__), "images")
_image_cache = {}
card_rects = []  # カードのクリック判定用矩形リスト
_piece_image_cache = {}
chess_log = []  # チェス専用ログ（カード用の game.log と分離）

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
        try:
            game.log.append(f"Image_MG.gif を読み込めませんでした: {gif_path}")
        except Exception:
            pass
        # fallback: try pygame.image.load as a single-surface fallback
        try:
            surf = pygame.image.load(gif_path).convert_alpha()
            mg_gif_frames_cache = [surf]
            mg_gif_durations = [1000]
            mg_gif_total_duration = 1.0
            mg_gif_load_success = True
            try:
                game.log.append(f"Image_MG.gif を pygame.image.load で単一フレームとして読み込みました")
            except Exception:
                pass
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
    try:
        game.log.append(f"Image_MG.gif を読み込みました: {len(frames)} フレーム")
    except Exception:
        pass

def play_heat_gif_at(row: int, col: int):
    """Start playing the heat GIF animation centered at board square (row,col)."""
    global heat_gif_frames_cache, heat_gif_durations, heat_gif_anim
    gif_path = os.path.join(IMG_DIR, 'Image_F.gif')
    if heat_gif_frames_cache is None or heat_gif_durations is None:
        frames, durations = _load_gif_frames(gif_path)
        heat_gif_frames_cache = frames
        heat_gif_durations = durations
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
    global game
    game = new_game_with_rule_deck()
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

    while True:
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
                        return

                # deck button (centered below)
                deck_w = 200
                deck_h = 56
                deck_x = (W - deck_w)//2
                # deck_y is computed later when drawing; approximate here using same formula
                deck_y = start_y + btn_h + 48 + 56
                if deck_x <= mx <= deck_x + deck_w and deck_y <= my <= deck_y + deck_h:
                    # show a simple deck modal
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

        pygame.display.flip()
        clock.tick(30)


def show_deck_modal(screen):
    """Simple deck modal - click/touch to close."""
    clock = pygame.time.Clock()
    w, h = 640, 420
    x = (W - w)//2
    y = (H - h)//2
    modal_surf = pygame.Surface((w, h))
    modal_surf.fill((245,245,250))
    pygame.draw.rect(modal_surf, (80,80,80), (0,0,w,h), 3)

    # build a textual list of player's deck
    lines = [f"{i+1}. {c.name} (cost {c.cost})" for i,c in enumerate(game.player.deck.cards[:20])]

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

        pygame.display.flip()
        clock.tick(30)
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit(0)
                if pygame.K_1 <= event.key <= pygame.K_4:
                    CPU_DIFFICULTY = event.key - pygame.K_0
                    return
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                # check horizontal buttons
                btn_x = (W - (btn_w*4 + 16*3))//2
                for i, (_lab, val) in enumerate(options):
                    bx = btn_x + i * (btn_w + 16)
                    by = start_y
                    if bx <= mx <= bx + btn_w and by <= my <= by + btn_h:
                        CPU_DIFFICULTY = val
                        return
                # deck button area
                deck_btn = pygame.Rect((W-160)//2, start_y + btn_h + 80, 160, 48)
                if deck_btn.collidepoint((mx,my)):
                    show_deck_editor()
                    continue

        # draw background
        if bg is not None:
            screen.blit(bg, (0,0))
        else:
            screen.fill((200, 150, 90))

        # semi-transparent dark overlay to improve text contrast
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0,0,0,90))
        screen.blit(overlay, (0,0))

        # Title with outline
        title_surf = title_font.render("CPUの難易度を選択してください", True, (245,245,240))
        tx = (W - title_surf.get_width())//2
        ty = start_y - 90
        for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
            screen.blit(title_font.render("CPUの難易度を選択してください", True, (30,30,30)), (tx+ox, ty+oy))
        screen.blit(title_surf, (tx, ty))

        # buttons (wide grey boxes like original, arranged horizontally)
        btn_x = (W - (btn_w*4 + 16*3))//2
        for i, (lab, val) in enumerate(options):
            bx = btn_x + i * (btn_w + 16)
            by = start_y
            rect = pygame.Rect(bx, by, btn_w, btn_h)
            pygame.draw.rect(screen, (200,200,200), rect)
            pygame.draw.rect(screen, (70,70,70), rect, 4)
            txt = btn_font.render(lab, True, (30,30,30))
            screen.blit(txt, (bx + (btn_w-txt.get_width())//2, by + (btn_h-txt.get_height())//2))

        # hint text and deck button
        hint = SMALL.render("キー1-4でも選択できます。Escで終了", True, (230,230,230))
        screen.blit(hint, ((W-hint.get_width())//2, start_y + btn_h + 40))

        deck_btn = pygame.Rect((W-160)//2, start_y + btn_h + 80, 160, 48)
        pygame.draw.rect(screen, (230,230,230), deck_btn)
        pygame.draw.rect(screen, (60,60,60), deck_btn, 3)
        dbtxt = btn_font.render("デッキ作成", True, (30,30,30))
        screen.blit(dbtxt, (deck_btn.x + (deck_btn.w-dbtxt.get_width())//2, deck_btn.y + (deck_btn.h-dbtxt.get_height())//2))

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
            if id(p) in frozen and frozen[id(p)] > 0:
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

def get_valid_moves(piece, pcs=None, ignore_check=False):
    # pcs: list of piece dicts; if None, use global pieces
    if pcs is None:
        # prefer local 'pieces' (dict-style) if present, otherwise fall back to chess.pieces
        pcs = globals().get('pieces', chess.pieces)
    moves = []
    # If this piece is frozen by a card effect, it cannot move
    if getattr(game, 'frozen_pieces', None) is not None:
        if id(piece) in game.frozen_pieces and game.frozen_pieces[id(piece)] > 0:
            return []

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
                can_jump = globals().get('ai_next_move_can_jump', False)
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
            if on_board(nr,nc) and not occupied_by_color(nr,nc,color):
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
                            can_jump = globals().get('ai_next_move_can_jump', False)
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
                if on_board(nr,nc) and not occupied_by_color(nr,nc,color):
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
                if not occupied(king_row, 5) and not occupied(king_row, 6):
                    moves.append((king_row, 6))  # キャスリング後のキングの位置

            rook_queenside = get_piece_at(king_row, 0)
            if (rook_queenside and _pget(rook_queenside, 'name') == 'R' and
                _pget(rook_queenside, 'color') == color and
                not _pget(rook_queenside, 'has_moved', False)):
                if not occupied(king_row, 1) and not occupied(king_row, 2) and not occupied(king_row, 3):
                    moves.append((king_row, 2))  # キャスリング後のキングの位置

    # filter moves that leave king in check
    if not ignore_check:
        legal = []
        for mv in moves:
            newp = simulate_move(piece, mv[0], mv[1])
            if not is_in_check(newp, color):
                legal.append(mv)
        return legal
    return moves

def has_legal_moves_for(color):
    return chess.has_legal_moves_for(color)

def apply_move(piece, to_r, to_c):
    return chess.apply_move(piece, to_r, to_c)

def ai_make_move():
    # AI difficulty-aware move selection (black)
    import random
    global CPU_DIFFICULTY
    global ai_player, ai_next_move_can_jump, ai_extra_moves_this_turn, ai_consecutive_turns

    # Begin AI turn: restore PP and draw 1 card (simple turn-start behavior for AI)
    try:
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
        # decide whether to attempt a card play based on difficulty
        probs = {1: 0.08, 2: 0.18, 3: 0.45, 4: 0.7}
        p_play = probs.get(CPU_DIFFICULTY, 0.18)
        if not ai_player.hand.cards:
            return False
        if random.random() > p_play:
            return False

        # collect playable indices
        playable = [i for i, c in enumerate(ai_player.hand.cards) if c.can_play(ai_player)]
        if not playable:
            return False

        # heuristic: prefer disruptive cards
        names = [ai_player.hand.cards[i].name for i in playable]
        # ranking order
        prefer = ['氷結', '灼熱', '暴風', '迅雷', '2ドロー', '錬成']
        chosen_idx = None
        for pref in prefer:
            if pref in names:
                chosen_idx = playable[names.index(pref)]
                break
        if chosen_idx is None:
            chosen_idx = random.choice(playable)

        card = ai_player.hand.remove_at(chosen_idx)
        if not card:
            return False
        # pay PP
        if not ai_player.spend_pp(card.cost):
            # cannot pay, return card to hand
            ai_player.hand.add(card)
            return False

        # apply simplified effects directly (auto-targeting)
        nm = card.name
        if nm == '灼熱':
            # block a square near white's highest-value piece
            target = None
            best_val = -1
            vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
            for wp in chess.pieces:
                if getattr(wp, 'color', None) == 'white':
                    v = vals.get(getattr(wp, 'name', ''), 0)
                    if v > best_val:
                        best_val = v
                        target = wp
            if target:
                tr, tc = target.row, target.col
                # choose a neighboring empty square if possible
                for dr, dc in [(0,1),(0,-1),(1,0),(-1,0),(1,1),(1,-1),(-1,1),(-1,-1)]:
                    nr, nc = tr+dr, tc+dc
                    if 0<=nr<8 and 0<=nc<8 and chess.get_piece_at(nr,nc) is None:
                        game.blocked_tiles[(nr,nc)] = 2
                        game.blocked_tiles_owner[(nr,nc)] = 'black'
                        game.log.append(f"AI: 灼熱でマス {(nr,nc)} を封鎖しました。")
                        break
        elif nm == '氷結':
            # freeze highest-value white piece for 1 turn
            target = None
            best_val = -1
            vals = {'P':1,'N':3,'B':3,'R':5,'Q':9,'K':10}
            for wp in chess.pieces:
                if getattr(wp, 'color', None) == 'white':
                    v = vals.get(getattr(wp,'name',''),0)
                    if v > best_val and id(wp) not in game.frozen_pieces:
                        best_val = v
                        target = wp
            if target:
                game.frozen_pieces[id(target)] = 1
                game.log.append(f"AI: 氷結で {target.name} を凍結しました。")
        elif nm == '暴風':
            # set module-level AI jump flag so get_valid_moves can consult it for black
            ai_next_move_can_jump = True
            game.log.append("AI: 暴風を使用、次の移動で1駒飛び越え可能。")
        elif nm == '迅雷':
            # grant AI an extra/continuous-turn marker (consumed elsewhere if implemented)
            ai_consecutive_turns = max(ai_consecutive_turns, 1)
            game.log.append("AI: 迅雷を使用、連続ターンを獲得しました。")
        elif nm == '2ドロー':
            for _ in range(2):
                c = ai_player.deck.draw()
                if c:
                    ai_player.hand.add(c)
            game.log.append("AI: 2ドローを使用しました。")
        elif nm == '錬成':
            # draw 1 and discard random if over hand limit
            c = ai_player.deck.draw()
            if c:
                ai_player.hand.add(c)
            if ai_player.hand.cards:
                ai_player.hand.remove_at(random.randrange(len(ai_player.hand.cards)))
            game.log.append("AI: 錬成を使用しました。")
        else:
            # fallback: do nothing special
            game.log.append(f"AI: {nm} を使用しました（効果は簡略適用）。")

        # move card to graveyard
        ai_player.graveyard.append(card)
        return True

    # attempt to play a card (may mutate ai state)
    try:
        ai_consider_play_card()
    except Exception:
        pass

    # --- 封鎖タイル向けの継続アニメーション (Image_MG.gif) ---
    try:
        _ensure_mg_gif_loaded()
        if mg_gif_frames_cache and mg_gif_durations:
            # compute global loop time in ms
            try:
                total_ms = int(sum(mg_gif_durations))
            except Exception:
                total_ms = max(1, int(mg_gif_total_duration * 1000))
            now_ms = int(_ct_time.time() * 1000) if total_ms > 0 else 0
            for (br, bc), turns in getattr(game, 'blocked_tiles', {}).items():
                # only show while turns > 0
                if not turns:
                    continue
                bx = board_left + bc * square_w
                by = board_top + br * square_h
                # frame index by modulo looping
                if total_ms > 0:
                    tmod = now_ms % total_ms
                    acc = 0
                    idx = 0
                    for i, d in enumerate(mg_gif_durations):
                        acc += d
                        if tmod < acc:
                            idx = i
                            break
                else:
                    idx = 0
                frame = mg_gif_frames_cache[idx]
                try:
                    f_surf = pygame.transform.smoothscale(frame, (square_w, square_h))
                except Exception:
                    f_surf = frame
                # draw on tile top-left so it covers the tile area
                screen.blit(f_surf, (bx, by))
    except Exception:
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
        if ai_next_move_can_jump:
            # consumed for one move
            ai_next_move_can_jump = False
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
    base_left_margin = max(12, int(BASE_UI_W * 0.02))
    base_left_panel_width = max(140, min(360, int(BASE_UI_W * 0.18)))
    base_right_panel_width = max(160, min(380, int(BASE_UI_W * 0.18)))
    base_board_area_top = max(12, int(BASE_UI_H * 0.02))
    inner_gap = int(20 * scale)

    left_margin = max(12, int(base_left_margin * scale))
    left_panel_width = max(12, int(base_left_panel_width * scale))
    right_panel_width = max(12, int(base_right_panel_width * scale))

    board_area_top = max(8, int(base_board_area_top * scale))

    central_left = left_margin + left_panel_width + inner_gap
    central_right = win_w - left_margin - right_panel_width - inner_gap
    central_width = max(0, central_right - central_left)

    # reserve bottom area for hand display (card height scaled)
    # On large screens, prefer larger card thumbnails so cards can be "big" as requested.
    base_card_h = max(120, int(BASE_UI_H * 0.18))
    # make cards substantially larger on big displays so artwork is prominent
    if scale > 1.05:
        # scale factor grows with UI scale, capped to avoid excessive sizes
        extra = min(2.0, 1.0 + (scale - 1.0) * 1.0)
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
        horiz_bias = int(max(0, (scale - 1.0) * central_width * 0.12))
    except Exception:
        horiz_bias = 0
    board_left = central_left + max(0, center_dx - horiz_bias)

    # vertical bias: if there is extra vertical slack, push the board upward to minimize top whitespace
    slack = avail_height - board_size
    if slack > 0:
        # remove most of the top slack so the board moves up; keep a small safe margin
        move_up = int(slack * 0.9)
        board_top = max(8, board_area_top - move_up)
    else:
        board_top = board_area_top

    right_panel_x = win_w - left_margin - right_panel_width

    card_area_top = board_top + board_size + int(20 * scale)

    # expose computed card height so draw_panel can size card thumbnails consistently
    card_h = max(48, int(base_card_h * scale))

    return {
        'left_margin': left_margin,
        'left_panel_width': left_panel_width,
        'right_panel_width': right_panel_width,
        'right_panel_x': right_panel_x,
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
    screen.fill((240, 240, 245))
    global log_toggle_rect

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
    # 簡易エフェクト表示: 次の移動でジャンプ/追加行動がある場合に左パネルへ表示
    # Draw each effect on its own full line to avoid overlapping with other telops
    if getattr(game.player, 'next_move_can_jump', False):
        draw_text(screen, "[効果] 次の移動でジャンプ可能", info_x, info_y, (10, 40, 180))
        info_y += line_height - 6
    # 迅雷効果の表示（player_consecutive_turnsを使用）
    consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    if consecutive_turns > 0:
        info_y += 6
        draw_text(screen, f"[効果] 追加行動: {consecutive_turns}", info_x, info_y, (10, 120, 10))
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
    opponent_hand_text = f"相手の手札: {opponent_hand_count}枚"
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

    # --- 封鎖タイルでのループ再生: Image_MG.gif ---
    try:
        _ensure_mg_gif_loaded()
        if mg_gif_frames_cache and mg_gif_durations:
            try:
                total_ms = int(sum(mg_gif_durations))
            except Exception:
                total_ms = max(1, int(mg_gif_total_duration * 1000))
            now_ms = int(_ct_time.time() * 1000) if total_ms > 0 else 0
            for (br, bc), turns in getattr(game, 'blocked_tiles', {}).items():
                # only show while turns > 0
                if not turns:
                    continue
                bx = board_left + bc * square_w
                by = board_top + br * square_h
                # frame index by modulo looping
                if total_ms > 0:
                    tmod = now_ms % total_ms
                    acc = 0
                    idx = 0
                    for i, d in enumerate(mg_gif_durations):
                        acc += d
                        if tmod < acc:
                            idx = i
                            break
                else:
                    idx = 0
                frame = mg_gif_frames_cache[idx]
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
            if id(p) in getattr(game, 'frozen_pieces', {}):
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
        for hr, hc in highlight_squares:
            hrect = pygame.Rect(board_left + hc*square_w, board_top + hr*square_h, square_w, square_h)
            
            # 移動先の色分け判定
            is_en_passant = False
            is_castling = False
            is_checkmate = False
            
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
            
            # 色決定（Chess Main準拠）
            if is_checkmate:
                highlight_color = (255, 0, 0, 100)  # 赤: チェックメイト/キング捕獲
            elif is_en_passant:
                highlight_color = (0, 0, 255, 100)  # 青: アンパサン
            elif is_castling:
                highlight_color = (255, 215, 0, 100)  # 金: キャスリング
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
        if is_in_check_for_display(chess.pieces, 'white'):
            check_colors.append('white')
        if is_in_check_for_display(chess.pieces, 'black'):
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
        log_panel_left = board_area_left + board_area_width + 20
        log_panel_top = board_area_top
        # compute panel size but clamp to a reasonable maximum so full-screen doesn't make it huge
        log_panel_width = W - log_panel_left - 24
        log_panel_height = board_area_height
        MAX_LOG_W = 640
        MAX_LOG_H = 600
        if log_panel_width > MAX_LOG_W:
            # center the clamped panel so it doesn't stick to the right edge awkwardly
            log_panel_left = max(board_area_left + board_area_width + 20, W - MAX_LOG_W - 24)
            log_panel_width = MAX_LOG_W
        if log_panel_height > MAX_LOG_H:
            # keep top aligned but reduce height
            log_panel_height = MAX_LOG_H

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
    
    # カードサイズ
    card_w = 100
    card_h = 135
    card_spacing = 8
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
    state_x = layout['right_panel_x'] + 12
    state_y = layout['card_area_top'] + 40
    draw_text(screen, f"封鎖: {len(getattr(game, 'blocked_tiles', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    draw_text(screen, f"凍結: {len(getattr(game, 'frozen_pieces', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    # 迅雷効果の表示（player_consecutive_turnsを使用）
    consecutive_turns = getattr(game, 'player_consecutive_turns', 0)
    draw_text(screen, f"追加行動: {consecutive_turns}", state_x, state_y, (80, 80, 80))
    state_y += 20
    if game.player.next_move_can_jump:
        draw_text(screen, "次: 飛越可", state_x, state_y, (0, 120, 0))

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
        
        draw_text(screen, f"相手の手札 ({opponent_hand_count}枚) [H]で閉じる", overlay_x + 20, overlay_y + 20, (100, 50, 100))
        
        # カード裏面を横並びで表示（画像未実装のため仮の矩形）
        card_back_w = 70
        card_back_h = 95
        start_x = overlay_x + (overlay_w - (card_back_w * min(opponent_hand_count, 7) + 10 * (min(opponent_hand_count, 7) - 1))) // 2
        cy = overlay_y + 80
        
        for i in range(opponent_hand_count):
            if i >= 7:  # 1行に7枚まで
                cy += card_back_h + 20
                start_x = overlay_x + (overlay_w - (card_back_w * min(opponent_hand_count - 7, 7) + 10 * (min(opponent_hand_count - 7, 7) - 1))) // 2
                if i == 7:
                    pass  # 2行目の開始位置を再計算済み
            
            row = i // 7
            col = i % 7
            if row > 0:
                cx = overlay_x + (overlay_w - (card_back_w * min(opponent_hand_count - 7, 7) + 10 * (min(opponent_hand_count - 7, 7) - 1))) // 2 + col * (card_back_w + 10)
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
        else:
            instruction_text = "選択を完了してください"
        
        # ボックスサイズ計算
        box_padding = 30
        
        # confirmの場合は複数行対応
        if game.pending.kind == 'confirm':
            msg = game.pending.info.get('message', '実行してもよろしいですか？ [Y]=はい / [N]=いいえ')
            lines = msg.split('\n')
            # 各行の幅を計算して最大幅を取得
            max_width = 0
            for line in lines:
                line_surface = FONT.render(line, True, (0, 0, 0))
                max_width = max(max_width, line_surface.get_width())
            box_width = max_width + box_padding * 2
            # タイトル + メッセージ行数分の高さ + 下部余白
            box_height = 50 + len(lines) * 22 + 15
        else:
            text_surface = FONT.render(instruction_text, True, (0, 0, 0))
            text_width = text_surface.get_width()
            box_width = text_width + box_padding * 2
            box_height = 80
        
        # カード拡大表示の横に配置（右側）
        if enlarged_card_index is not None:
            box_x = (W - 300) // 2 + 300 + 30  # カードの右側
        else:
            box_x = (W - box_width) // 2  # 中央
        box_y = (H - box_height) // 2
        
        # 背景ボックス
        pygame.draw.rect(screen, (255, 255, 200), (box_x, box_y, box_width, box_height))
        pygame.draw.rect(screen, (180, 60, 0), (box_x, box_y, box_width, box_height), 4)
        
        # タイトル
        draw_text(screen, "⚠ 操作待ち", box_x + box_padding, box_y + 15, (180, 60, 0))
        # 操作説明テキスト
        if game.pending.kind == 'confirm':
            msg = game.pending.info.get('message', '実行してもよろしいですか？ [Y]=はい / [N]=いいえ')
            # 改行対応: \nで分割して複数行描画
            lines = msg.split('\n')
            line_y = box_y + 45
            for line in lines:
                draw_text(screen, line, box_x + box_padding, line_y, (60, 60, 60))
                line_y += 22  # 行間
        else:
            draw_text(screen, instruction_text, box_x + box_padding, box_y + 45, (60, 60, 60))

        # 灼熱選択用の二択ボタン（保留が heat_choice のとき）
        global heat_choice_unfreeze_rect, heat_choice_block_rect
        heat_choice_unfreeze_rect = None
        heat_choice_block_rect = None
        if getattr(game, 'pending', None) is not None and game.pending.kind == 'heat_choice':
            btn_w, btn_h = 260, 40
            gap = 20
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

        # 確認ダイアログのボタン（はい/いいえ）
        global confirm_yes_rect, confirm_no_rect
        confirm_yes_rect = None
        confirm_no_rect = None
        if game.pending.kind == 'confirm':
            btn_w, btn_h = 120, 36
            gap = 20
            btn_y = box_y + box_height + 12
            total_w = btn_w * 2 + gap
            start_x = (W - total_w) // 2
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
        if game_over_winner == 'white':
            msg = "白の勝利！"
            color = (255, 255, 100)
        elif game_over_winner == 'black':
            msg = "黒の勝利！"
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
        quit_rect = pygame.Rect(W//2 - btn_w//2, H//2 + btn_h + 20, btn_w, btn_h)
        
        # ボタン描画
        pygame.draw.rect(screen, (50, 150, 50), restart_rect)
        pygame.draw.rect(screen, (150, 50, 50), quit_rect)
        pygame.draw.rect(screen, (255, 255, 255), restart_rect, 3)
        pygame.draw.rect(screen, (255, 255, 255), quit_rect, 3)
        
        screen.blit(restart_surf, restart_surf.get_rect(center=restart_rect.center))
        screen.blit(quit_surf, quit_surf.get_rect(center=quit_rect.center))
        
        # ボタンの矩形を保存（クリック判定用）
        draw_panel.restart_rect = restart_rect
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
    global enlarged_card_index, enlarged_card_name, selected_piece, highlight_squares, chess_current_turn, show_grave, show_opponent_hand, notice_msg, notice_until
    
    # ゲーム終了画面のボタン処理
    if game_over:
        if hasattr(draw_panel, 'restart_rect') and draw_panel.restart_rect.collidepoint(pos):
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
            for p in chess.pieces:
                if p.color == 'black' and id(p) in frozen and frozen[id(p)] > 0:
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
                # 凍結駒がある場合は通常の解除処理へ（カードを消費してから）
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。PPは{game.player.pp_current}/{game.player.pp_max}。")
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
                    try:
                        game.frozen_pieces[id(clicked)] = turns
                    except Exception:
                        game.frozen_pieces[id(clicked)] = turns
                    # try to get a readable name
                    try:
                        name = clicked.name
                    except Exception:
                        name = clicked.get('name', str(clicked)) if clicked is not None else '駒'
                    game.log.append(f"凍結: {name} を {turns} ターン凍結")
                    game.pending = None
                else:
                    game.log.append("相手の駒を選んでください。")
                return
        # Normal piece selection / move handling
        if selected_piece is None:
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
                if chess_current_turn == 'white' and getattr(game, 'turn_active', False):
                    if moved_flag and extra <= 0:
                        game.log.append("このターンは既に駒を動かしました。次のターン開始まで待つか、カードで追加行動を付与してください。")
                        return
                # Apply the move
                apply_move(selected_piece, row, col)
                # Consume storm jump effect after the player's next move (whether used or not)
                try:
                    if getattr(game.player, 'next_move_can_jump', False):
                        game.player.next_move_can_jump = False
                        game.log.append("暴風効果: 次の移動でのジャンプ可能を消費しました。")
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

        # --- チェックメイト判定と勝利条件チェック ---
        if not game_over:
            # キングが盤面にいない場合は即座に勝敗を決定
            white_king = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
            black_king = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
            if not white_king:
                game_over = True
                game_over_winner = 'black'
                game.log.append("白のキングが捕獲されました！黒の勝利！")
            elif not black_king:
                game_over = True
                game_over_winner = 'white'
                game.log.append("黒のキングが捕獲されました！白の勝利！")
            # どちらかが詰みの場合も勝利判定
            elif not chess.has_legal_moves_for('white') and is_in_check(chess.pieces, 'white'):
                game_over = True
                game_over_winner = 'black'
                game.log.append("白がチェックメイト！黒の勝利！")
            elif not chess.has_legal_moves_for('black') and is_in_check(chess.pieces, 'black'):
                game_over = True
                game_over_winner = 'white'
                game.log.append("黒がチェックメイト！白の勝利！")
            # ステイルメイト（合法手がないがチェックでない）の判定
            elif not chess.has_legal_moves_for(chess_current_turn) and not is_in_check(chess.pieces, chess_current_turn):
                game_over = True
                game_over_winner = 'draw'
                game.log.append("ステイルメイト（引き分け）")

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
                cpu_wait = False
                # restore player turn
                chess_current_turn = 'white'
                # プレイヤーターン開始テロップを1秒表示
                try:
                    turn_telop_msg = "YOUR TURN"
                    turn_telop_until = _ct_time.time() + 1.0
                except Exception:
                    pass
                # Apply decay for time-limited card effects now that the opponent's turn finished.
                # Do NOT automatically start the player's card-game turn; the player must press [T]
                # to start their own turn. This keeps chess movement locked until the player
                # explicitly starts their turn.
                try:
                    game.decay_statuses()
                except Exception:
                    pass

        clock.tick(60)


if __name__ == "__main__":
    # show start screen to choose AI difficulty before starting
    show_start_screen()
    main_loop()