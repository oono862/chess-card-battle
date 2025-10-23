#カードゲーム部分実装
import pygame
from pygame import Rect
import sys
import os

try:
    from .card_core import new_game_with_sample_deck, new_game_with_rule_deck
except Exception:
    # 直接実行用パス解決（フォルダ直接実行時）
    from card_core import new_game_with_sample_deck, new_game_with_rule_deck


pygame.init()

# 画面設定
W, H = 1200, 800
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("カードゲーム デモ")
clock = pygame.time.Clock()

FONT = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 20)
SMALL = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 18)
TINY = pygame.font.SysFont("Noto Sans JP, Meiryo, MS Gothic", 16)

# ゲーム状態
# ルール表のカードを試したい場合は下を使う
game = new_game_with_rule_deck()
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

# ------------------ Chess integration (embedded) ------------------
# Simple piece representation compatible with AI module expectations
pieces = []  # list of dicts: {'row':int,'col':int,'name':str,'color':'white'|'black'}
selected_piece = None  # selected piece dict or None
highlight_squares = []  # list of (r,c) legal moves to highlight
chess_current_turn = 'white'
en_passant_target = None
promotion_pending = None  # {'piece': piece, 'color': str} when a pawn reached last rank

# AI thinking/display settings (recreate behavior from Chess  Main.py)
THINKING_ENABLED = True
AI_THINK_DELAY = 0.5
THINK_DOT_FREQ = 4.0

# CPU waiting state
cpu_wait = False
cpu_wait_start = 0.0

def create_pieces():
    p = []
    # White on bottom (rows 6-7), black on top (rows 0-1)
    p += [{'row':7, 'col':0, 'name':'R', 'color':'white'}, {'row':7, 'col':1, 'name':'N', 'color':'white'},
          {'row':7, 'col':2, 'name':'B', 'color':'white'}, {'row':7, 'col':3, 'name':'Q', 'color':'white'},
          {'row':7, 'col':4, 'name':'K', 'color':'white'}, {'row':7, 'col':5, 'name':'B', 'color':'white'},
          {'row':7, 'col':6, 'name':'N', 'color':'white'}, {'row':7, 'col':7, 'name':'R', 'color':'white'}]
    p += [{'row':6, 'col':i, 'name':'P', 'color':'white'} for i in range(8)]
    p += [{'row':0, 'col':0, 'name':'R', 'color':'black'}, {'row':0, 'col':1, 'name':'N', 'color':'black'},
          {'row':0, 'col':2, 'name':'B', 'color':'black'}, {'row':0, 'col':3, 'name':'Q', 'color':'black'},
          {'row':0, 'col':4, 'name':'K', 'color':'black'}, {'row':0, 'col':5, 'name':'B', 'color':'black'},
          {'row':0, 'col':6, 'name':'N', 'color':'black'}, {'row':0, 'col':7, 'name':'R', 'color':'black'}]
    p += [{'row':1, 'col':i, 'name':'P', 'color':'black'} for i in range(8)]
    return p


def show_start_screen(screen):
    """起動時に難易度を選択する簡易メニュー。
    1-4 のキーか、画面上のボタンで選択可能。選択はグローバル CPU_DIFFICULTY に保存される。
    """
    # 選択結果をグローバルに反映
    global CPU_DIFFICULTY
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

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
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
    for pc in pieces:
        if pc['row'] == row and pc['col'] == col:
            return pc
    return None

def on_board(r,c):
    return 0 <= r < 8 and 0 <= c < 8

def simulate_move(src_piece, to_r, to_c):
    # return new pieces list after move (deep copy of dicts)
    new = [dict(p) for p in pieces if not (p['row']==to_r and p['col']==to_c)]
    moved = dict(src_piece)
    # remove source from new
    new = [p for p in new if not (p['row']==src_piece['row'] and p['col']==src_piece['col'] and p['name']==src_piece['name'] and p['color']==src_piece['color'])]
    moved['row'] = to_r
    moved['col'] = to_c
    new.append(moved)
    return new

def is_in_check(pcs, color):
    # find king
    king = None
    for p in pcs:
        if p['name'] == 'K' and p['color'] == color:
            king = p
            break
    if not king:
        return False
    kpos = (king['row'], king['col'])
    # check opponent moves
    for p in pcs:
        if p['color'] == ('white' if color=='black' else 'black'):
            for mv in get_valid_moves(p, pcs, ignore_check=True):
                if mv == kpos:
                    return True
    return False

def get_valid_moves(piece, pcs=None, ignore_check=False):
    # pcs: list of piece dicts; if None, use global pieces
    if pcs is None:
        pcs = pieces
    moves = []
    name = piece['name']
    r,c = piece['row'], piece['col']
    def occupied(rr,cc):
        return get_piece_at(rr,cc) is not None
    def occupied_by_color(rr,cc,color):
        p = get_piece_at(rr,cc)
        return p is not None and p['color']==color

    if name == 'P':
        dir = -1 if piece['color']=='white' else 1
        # forward
        if on_board(r+dir, c) and not occupied(r+dir,c):
            moves.append((r+dir,c))
            # double from starting rank
            start_row = 6 if piece['color']=='white' else 1
            if r==start_row and on_board(r+2*dir,c) and not occupied(r+2*dir,c):
                moves.append((r+2*dir,c))
        # captures
        for dc in (-1,1):
            nr,nc = r+dir, c+dc
            if on_board(nr,nc) and occupied(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                moves.append((nr,nc))
    elif name == 'N':
        for dr,dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
            nr,nc = r+dr, c+dc
            if on_board(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                moves.append((nr,nc))
    elif name in ('B','R','Q'):
        directions = []
        if name in ('B','Q'):
            directions += [(-1,-1),(-1,1),(1,-1),(1,1)]
        if name in ('R','Q'):
            directions += [(-1,0),(1,0),(0,-1),(0,1)]
        for dr,dc in directions:
            step = 1
            while True:
                nr,nc = r+dr*step, c+dc*step
                if not on_board(nr,nc):
                    break
                if occupied(nr,nc):
                    if not occupied_by_color(nr,nc,piece['color']):
                        moves.append((nr,nc))
                    break
                moves.append((nr,nc))
                step += 1
    elif name == 'K':
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                nr,nc = r+dr, c+dc
                if on_board(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                    moves.append((nr,nc))

    # filter moves that leave king in check
    if not ignore_check:
        legal = []
        for mv in moves:
            newp = simulate_move(piece, mv[0], mv[1])
            if not is_in_check(newp, piece['color']):
                legal.append(mv)
        return legal
    return moves

def has_legal_moves_for(color):
    for p in pieces:
        if p['color']==color and get_valid_moves(p):
            return True
    return False

def apply_move(piece, to_r, to_c):
    global en_passant_target, chess_current_turn
    # remove captured
    target = get_piece_at(to_r,to_c)
    if target:
        pieces.remove(target)
    # move piece
    piece['row'] = to_r
    piece['col'] = to_c
    # pawn promotion: enqueue selection instead of auto-promote
    global promotion_pending
    if piece['name']=='P' and (piece['row']==0 or piece['row']==7):
        # mark promotion pending; keep piece as pawn until selection
        promotion_pending = {'piece': piece, 'color': piece['color']}
    # turn change handled by caller

def ai_make_move():
    # AI difficulty-aware move selection (black)
    import random
    global CPU_DIFFICULTY
    candidates = []  # list of (piece, move)
    for p in pieces:
        if p['color'] != 'black':
            continue
        v = get_valid_moves(p)
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
            tgt = get_piece_at(mv[0], mv[1])
            score = values.get(tgt['name'],0) if tgt else 0
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
            tgt = get_piece_at(mv[0], mv[1])
            score = values.get(tgt['name'],0) if tgt else 0
            if score > best_score:
                best_score = score
                best = [(p,mv)]
            elif score == best_score:
                best.append((p,mv))
        sel = random.choice(best) if best else random.choice(candidates)

    p, mv = sel
    apply_move(p, mv[0], mv[1])
    game.log.append(f"AI({CPU_DIFFICULTY}): {p['name']} を {mv} に移動")

# initialize pieces
pieces = create_pieces()


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
    surf.blit(img, (x, y))


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


def draw_panel():
    screen.fill((240, 240, 245))

    # === レイアウト設定: 左側に基本情報、その右にチェス盤を画面上部から配置 ===
    left_panel_width = 180  # 左側の基本情報パネルの幅
    left_margin = 20
    top_margin = 20
    
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
    
    # 山札
    draw_text(screen, f"山札: {len(game.player.deck.cards)}枚", info_x, info_y, (40,40,90))
    info_y += line_height
    
    # 墓地表示（クリック可能領域として矩形を保存）
    grave_text = f"墓地: {len(game.player.graveyard)}枚"
    grave_surf = FONT.render(grave_text, True, (90,40,40))
    global grave_label_rect
    grave_label_rect = pygame.Rect(info_x, info_y, grave_surf.get_width(), grave_surf.get_height())
    draw_text(screen, grave_text, info_x, info_y, (90,40,40))
    info_y += line_height
    
    # 相手の手札表示（クリック可能領域として矩形を保存）
    opponent_hand_text = f"相手の手札: {opponent_hand_count}枚"
    opponent_hand_surf = FONT.render(opponent_hand_text, True, (100,50,100))
    global opponent_hand_rect
    opponent_hand_rect = pygame.Rect(info_x, info_y, opponent_hand_surf.get_width(), opponent_hand_surf.get_height())
    draw_text(screen, opponent_hand_text, info_x, info_y, (100,50,100))
    
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

    # 右上: ヘルプ（簡潔に）
    help_x = W - 250
    help_y = 20
    draw_text(screen, "操作:", help_x, help_y, (60, 60, 100))
    help_y += 24
    for hl in HELP_LINES:  # 全ての操作を表示
        draw_text(screen, hl, help_x, help_y, (30, 30, 90))
        help_y += 20

    # === チェス盤エリア: 左側パネルの右、画面上部から開始 ===
    board_area_left = left_margin + left_panel_width + 20  # 左パネル + 余白
    board_area_top = top_margin  # 画面上部から開始
    # 手札エリアとの干渉を避けるため、下部の予約領域を計算
    card_h = 140
    reserved_bottom = card_h + 80  # hand area + margin
    avail_height = H - board_area_top - reserved_bottom
    # 盤面を正方形にするため、利用可能な幅と高さの小さい方を使用
    avail_width = W - board_area_left - 20  # 右端までの余白を考慮
    board_size = min(avail_width, avail_height)
    # 他の箇所で参照されるため、board_area_width と board_area_height を定義
    board_area_width = board_size
    board_area_height = board_size
    
    # チェス盤の描画（8x8）- 画面上部から直接配置（センタリングなし）
    square_w = board_size // 8
    square_h = square_w
    board_left = board_area_left
    board_top = board_area_top
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
    for p in pieces:
        cell_x = board_left + p['col']*square_w
        cell_y = board_top + p['row']*square_h
        # leave small padding so piece images don't touch square edges
        padding = max(6, int(square_w * 0.08))
        img_w = square_w - padding*2
        img_h = square_h - padding*2
        img = get_piece_image_surface(p['name'], p['color'], (img_w, img_h))
        if img is not None:
            screen.blit(img, (cell_x + padding, cell_y + padding))
        else:
            cx = cell_x + square_w//2
            cy = cell_y + square_h//2
            radius = min(square_w, square_h)//2 - padding
            if p['color'] == 'white':
                pygame.draw.circle(screen, (250,250,250), (cx,cy), radius)
                label = SMALL.render(p['name'], True, (0,0,0))
            else:
                pygame.draw.circle(screen, (40,40,40), (cx,cy), radius)
                label = SMALL.render(p['name'], True, (255,255,255))
            screen.blit(label, (cx - label.get_width()//2, cy - label.get_height()//2))

    # ハイライト（選択可能な移動先）
    for hr,hc in highlight_squares:
        hrect = pygame.Rect(board_left + hc*square_w, board_top + hr*square_h, square_w, square_h)
        s = pygame.Surface((square_w, square_h), pygame.SRCALPHA)
        s.fill((255,255,0,80))
        screen.blit(s, hrect.topleft)
    # 盤面の左右に太めの黒線を描画して境界を明確に（元実装に近づける）
    left_x = board_left
    right_x = board_left + 8 * square_w
    pygame.draw.rect(screen, (20,20,20), (left_x-3, board_top, 6, 8 * square_h))
    pygame.draw.rect(screen, (20,20,20), (right_x-3, board_top, 6, 8 * square_h))

    # === 右側エリア: ログ（切替式）===
    global scrollbar_rect, dragging_scrollbar, drag_start_y, drag_start_offset
    if show_log:
        log_panel_left = board_area_left + board_area_width + 20
        log_panel_top = board_area_top
        log_panel_width = W - log_panel_left - 24
        log_panel_height = board_area_height

        # ログパネル背景
        pygame.draw.rect(screen, (250, 250, 255),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height))
        pygame.draw.rect(screen, (100, 100, 120),
                         (log_panel_left, log_panel_top, log_panel_width, log_panel_height), 2)

        draw_text(screen, "ログ履歴 [L]閉じる", log_panel_left + 10, log_panel_top + 8, (60, 60, 100))
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
        max_lines_visible = (log_panel_height - 50) // 22
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
            if log_y < log_panel_top + log_panel_height - 10:
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
        # ログ非表示時のヒント
        draw_text(screen, "[L] ログ表示", W - 240, board_area_top + board_area_height - 30, (100, 100, 120))

    # === 下部エリア: 手札（横並び最大7枚） ===
    card_area_top = board_area_top + board_area_height + 20
    draw_text(screen, "手札 (1-7で使用 / クリックで拡大):", 24, card_area_top, (40, 40, 40))
    
    card_w = 100
    card_h = 140
    card_spacing = 8
    card_start_x = 30
    card_y = card_area_top + 30
    
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
        
        # カード下部にボタン番号を大きく表示
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
    state_x = W - 240
    state_y = card_area_top + 40
    draw_text(screen, f"封鎖: {len(getattr(game, 'blocked_tiles', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    draw_text(screen, f"凍結: {len(getattr(game, 'frozen_pieces', {}))}", state_x, state_y, (80, 80, 80))
    state_y += 20
    draw_text(screen, f"追加行動: {game.player.extra_moves_this_turn}", state_x, state_y, (80, 80, 80))
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
            instruction_text = "封鎖するマスを選択してください（未実装）"
        elif game.pending.kind == 'target_piece':
            instruction_text = "凍結する相手コマを選択してください（未実装）"
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
    global promotion_pending
    if promotion_pending is not None:
        promot = promotion_pending
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
        if cpu_wait and THINKING_ENABLED:
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



def handle_keydown(key):
    global log_scroll_offset, show_log, enlarged_card_index
    
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
        if getattr(game, 'pending', None) is not None:
            game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return
        game.start_turn()
        log_scroll_offset = 0  # 新しいターンで最新ログへ
        return
    
    if key == pygame.K_g:
        # 保留中でも閲覧だけは可能にする
        global show_grave
        show_grave = not show_grave
        return
    
    if key == pygame.K_h:
        # 相手の手札表示切替
        global show_opponent_hand
        show_opponent_hand = not show_opponent_hand
        return
    
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
        # プロモーション選択中ならカード使用を抑止して昇格選択に使う
        global promotion_pending
        if promotion_pending is not None and 0 <= idx <= 3:
            opts = ['Q','R','B','N']
            sel = opts[idx]
            piece = promotion_pending['piece']
            piece['name'] = sel
            game.log.append(f"昇格: ポーンを{sel}に昇格させました。")
            promotion_pending = None
            return
        # pending中: discardのみ選択を許可し、それ以外は行動不可
        if getattr(game, 'pending', None) is not None:
            if game.pending.kind == 'discard':
                game.pending.info['selected'] = idx
                game.log.append(f"捨てるカードとして手札{idx+1}番を選択。[D]で確定")
            else:
                game.log.append("操作待ち: 先に保留中の選択を完了してください。")
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
            else:
                game.log.append("捨てるカードを選択してください。")
        else:
            game.log.append("捨てるカードが選択されていません。")
        game.pending = None
        log_scroll_offset = 0  # 保留解決後は最新ログへ
        return


def handle_mouse_click(pos):
    """マウスクリック時の処理"""
    global enlarged_card_index, enlarged_card_name, selected_piece, highlight_squares, promotion_pending, chess_current_turn, show_grave, show_opponent_hand
    
    # 拡大表示中ならどこクリックしても閉じる
    if enlarged_card_index is not None or enlarged_card_name is not None:
        enlarged_card_index = None
        enlarged_card_name = None
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
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            return
    
    # 墓地ラベルのクリックで墓地表示切替
    if grave_label_rect and grave_label_rect.collidepoint(pos):
        show_grave = not show_grave
        return
    
    # 相手の手札ラベルのクリックで表示切替
    if opponent_hand_rect and opponent_hand_rect.collidepoint(pos):
        show_opponent_hand = not show_opponent_hand
        return
    
    # 墓地オーバーレイ内のカードクリックで拡大表示
    if show_grave and grave_card_rects:
        for rect, card_name in grave_card_rects:
            if rect.collidepoint(pos):
                # toggle enlarged display
                if enlarged_card_name == card_name:
                    enlarged_card_name = None
                else:
                    enlarged_card_name = card_name
                return
    
    # カードのクリック判定（優先）
    for rect, idx in card_rects:
        if rect.collidepoint(pos):
            # toggle
            if enlarged_card_index == idx:
                enlarged_card_index = None
            else:
                enlarged_card_index = idx
            return

    # --- プロモーション選択オーバーレイクリック対応 ---
    global promotion_pending
    if promotion_pending is not None and hasattr(draw_panel, 'promo_rects'):
        for r, o in draw_panel.promo_rects:
            if r.collidepoint(pos):
                # 選択された昇格駒で置き換え
                piece = promotion_pending.get('piece')
                if piece is not None:
                    piece['name'] = o
                    game.log.append(f"昇格: ポーンを{o}に昇格させました。")
                promotion_pending = None
                # clear selection/highlights just in case
                selected_piece = None
                highlight_squares = []
                return

    # 盤面クリック判定 (draw_panel と同じ配置計算を行う)
    # レイアウト: 左側に基本情報パネル、その右にチェス盤
    left_panel_width = 180
    left_margin = 20
    top_margin = 20
    
    board_area_left = left_margin + left_panel_width + 20
    board_area_top = top_margin
    card_h = 140
    reserved_bottom = card_h + 80
    avail_height = H - board_area_top - reserved_bottom
    avail_width = W - board_area_left - 20
    board_size = min(avail_width, avail_height)

    # 盤面は画面上部から直接配置（センタリングなし）
    square_w = board_size // 8
    square_h = square_w
    board_left = board_area_left
    board_top = board_area_top

    board_rect = pygame.Rect(board_left, board_top, board_size, board_size)
    if board_rect.collidepoint(pos):
        col = (pos[0] - board_left) // square_w
        row = (pos[1] - board_top) // square_h
        # bounds safety
        col = int(max(0, min(7, col)))
        row = int(max(0, min(7, row)))

        clicked = get_piece_at(row, col)
        # 選択していない場合は自分の駒を選択
        if selected_piece is None:
            if clicked and clicked['color'] == chess_current_turn:
                selected_piece = clicked
                highlight_squares = get_valid_moves(clicked)
        else:
            # 目的地に含まれていれば移動
            if (row, col) in highlight_squares:
                apply_move(selected_piece, row, col)
                game.log.append(f"{selected_piece['name']} を {(row,col)} へ移動")
                # ターン切替
                chess_current_turn = 'black' if chess_current_turn == 'white' else 'white'
                # クリア
                selected_piece = None
                highlight_squares = []
                # AI の手
                if chess_current_turn == 'black':
                    # start non-blocking AI wait; main_loop will invoke the AI after delay
                    import time
                    global cpu_wait, cpu_wait_start
                    cpu_wait = True
                    cpu_wait_start = time.time()
                    # do not flip turn here; ai_make_move() will perform moves and
                    # main_loop will flip turn back to player after AI completes
            else:
                # 別の自駒を選択するかキャンセル
                if clicked and clicked['color'] == chess_current_turn:
                    selected_piece = clicked
                    highlight_squares = get_valid_moves(clicked)
                else:
                    selected_piece = None
                    highlight_squares = []
        return


def main_loop():
    global log_scroll_offset, cpu_wait, cpu_wait_start, chess_current_turn
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

        draw_panel()
        pygame.display.flip()

        # Non-blocking AI wait handling
        if cpu_wait and THINKING_ENABLED:
            import time
            if time.time() - cpu_wait_start >= AI_THINK_DELAY:
                # call AI move
                ai_make_move()
                cpu_wait = False
                # restore player turn
                chess_current_turn = 'white'

        clock.tick(60)


if __name__ == "__main__":
    # show start screen to choose AI difficulty before starting
    show_start_screen(screen)
    main_loop()