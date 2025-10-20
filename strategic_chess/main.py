import pygame
import sys
from gimmick import get_gimmick_list, FireGimmick, IceGimmick, ThunderGimmick, WindGimmick, DoubleGimmick, ExplosionGimmick, CollectGimmick, RecoveryGimmick
import subprocess  # 追加
import json        # 追加
import time  # 追加

pygame.init()

# 色定数（draw_boardより前に必ず定義）
WHITE = (240, 240, 240)
GRAY = (100, 100, 100)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
BLACK = (30, 30, 30)
GOLD = (255, 215, 0)
RED  = (255,0,0)

# --- ギミック一覧の取得と表示（例） ---
gimmicks = get_gimmick_list()
print("利用可能なギミック:")
for g in gimmicks:
    print(f"{g.name}: {g.get_description()}")

# ギミック所持数管理（初期値0）
player_gimmick_counts = {g.name: 0 for g in gimmicks}  # 左側（プレイヤー用）
cpu_gimmick_counts = {g.name: 0 for g in gimmicks}     # 右側（CPU用）

# 画面表示の設定
info = pygame.display.Info()
SCREEN_WIDTH = info.current_w
SCREEN_HEIGHT = info.current_h

# フルスクリーンフラグ（起動時はウィンドウモードにする）
is_fullscreen = False
# CPU(黒)の難易度: 1=Easy, 2=Medium, 3=Hard, 4=Expert
CPU_DIFFICULTY = 3

# 画面サイズとレイアウトを計算する関数
def calculate_layout(is_fullscreen_mode, window_width=None, window_height=None):
    if is_fullscreen_mode:
        width, height = SCREEN_WIDTH, SCREEN_HEIGHT
    else:
        # ウィンドウモード時：指定されたサイズまたはデフォルトサイズ
        if window_width is not None and window_height is not None:
            width, height = window_width, window_height
        else:
            width, height = 1200, 800  # デフォルトサイズ
    
    # チェス盤サイズを画面サイズに応じて調整
    board_size = min(width * 0.6, height * 0.7)
    board_width = int(board_size)
    board_height = int(board_size)
    square_size = board_width // 8
    gimmick_row_height = int(height * 0.15)
    
    # 盤面を中央に配置するためのオフセット
    board_offset_x = (width - board_width) // 2
    board_offset_y = gimmick_row_height
    
    return width, height, board_width, board_height, square_size, gimmick_row_height, board_offset_x, board_offset_y

# 初期レイアウト計算
WINDOW_WIDTH, WINDOW_HEIGHT, WIDTH, HEIGHT, SQUARE_SIZE, GIMMICK_ROW_HEIGHT, BOARD_OFFSET_X, BOARD_OFFSET_Y = calculate_layout(is_fullscreen)

# 画面モードを設定（起動時はリサイズ可能なウィンドウ）
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("チェスエレメント")

# フォントサイズを画面サイズに応じて調整
base_font_size = int(SCREEN_HEIGHT * 0.04)  # 画面高さの4%
font = pygame.font.SysFont("Noto_SansJP", base_font_size)



def render_text_with_outline(font, text, fg_color, outline_color=(255,255,255)):
    """テキストにアウトラインを付けたサーフェスを返す。
    周囲8方向に1pxのアウトラインを描画して視認性を高める。
    アンチエイリアスは False にして輪郭をシャープにする。
    """
    aa = False
    txt = font.render(text, aa, fg_color)
    outline = font.render(text, aa, outline_color)
    w = txt.get_width() + 2
    h = txt.get_height() + 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    offsets = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1),(-1,1),(1,-1)]
    for ox, oy in offsets:
        surf.blit(outline, (ox+1, oy+1))
    surf.blit(txt, (1,1))
    return surf


def wrap_text_for_width(text, font, max_width):
    """フォントで測りながら幅に合わせて改行したリストを返す（日本語は文字単位で切る）。"""
    lines = []
    if text == "":
        return [""]
    cur = ""
    for ch in text:
        test = cur + ch
        w, _ = font.size(test)
        if w <= max_width:
            cur = test
        else:
            if cur == "":
                # 1文字も入らない場合はその文字を強制的に行に入れる
                lines.append(test)
                cur = ""
            else:
                lines.append(cur)
                cur = ch
    if cur:
        lines.append(cur)
    return lines


def show_start_screen(screen):
    """起動時に難易度を選択する簡易メニューを表示する。
    1-4 のキーか、画面上のボタンで選択可能。
    選択した難易度はグローバル `CPU_DIFFICULTY` に設定される。
    """
    global CPU_DIFFICULTY
    clock = pygame.time.Clock()
    title_font = pygame.font.SysFont("Noto_SansJP", max(36, int(SCREEN_HEIGHT * 0.06)))
    btn_font = pygame.font.SysFont("Noto_SansJP", max(24, int(SCREEN_HEIGHT * 0.035)))
    options = [("1 - Easy", 1), ("2 - Medium", 2), ("3 - Hard", 3), ("4 - Expert", 4)]

    def show_deck_editor():
        """簡易デッキ作成画面のプレースホルダ。閉じるボタンで戻る。"""
        editor_clock = pygame.time.Clock()
        title_font = pygame.font.SysFont("Noto_SansJP", max(32, int(SCREEN_HEIGHT * 0.05)))
        info_font = pygame.font.SysFont("Noto_SansJP", max(18, int(SCREEN_HEIGHT * 0.03)))
        btn_font_local = pygame.font.SysFont("Noto_SansJP", max(20, int(SCREEN_HEIGHT * 0.03)))
        while True:
            screen.fill((240, 240, 240))
            win_w, win_h = screen.get_size()
            title = title_font.render("デッキ作成", True, BLACK)
            screen.blit(title, (win_w//2 - title.get_width()//2, 60))

            # プレースホルダ説明
            info = info_font.render("ここにデッキ編集UIを実装します。戻るには下のボタンを押してください。", True, BLACK)
            screen.blit(info, (win_w//2 - info.get_width()//2, 150))

            # 閉じるボタン
            bw, bh = 220, 64
            bx = win_w//2 - bw//2
            by = win_h - 140
            brect = pygame.Rect(bx, by, bw, bh)
            mx, my = pygame.mouse.get_pos()
            bcolor = (180,180,180) if brect.collidepoint((mx,my)) else (210,210,210)
            pygame.draw.rect(screen, bcolor, brect)
            pygame.draw.rect(screen, BLACK, brect, 2)
            bl = btn_font_local.render("戻る", True, BLACK)
            screen.blit(bl, (bx + bw//2 - bl.get_width()//2, by + bh//2 - bl.get_height()//2))

            pygame.display.flip()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if brect.collidepoint(ev.pos):
                        return
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        return
            editor_clock.tick(30)

    while True:
        screen.fill((200, 200, 200))
        win_w, win_h = screen.get_size()
        title_surf = title_font.render("CPUの難易度を選択してください", True, BLACK)
        screen.blit(title_surf, (win_w // 2 - title_surf.get_width() // 2, 80))

        btn_w = 300
        btn_h = 80
        spacing = 30
        total_w = len(options) * btn_w + (len(options) - 1) * spacing
        start_x = win_w // 2 - total_w // 2
        y = win_h // 2 - btn_h // 2

        mx, my = pygame.mouse.get_pos()
        clicked = False
        for i, (label, val) in enumerate(options):
            x = start_x + i * (btn_w + spacing)
            rect = pygame.Rect(x, y, btn_w, btn_h)
            color = (180, 180, 180)
            if rect.collidepoint((mx, my)):
                color = (150, 150, 150)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, BLACK, rect, 2)
            lab = btn_font.render(label, True, BLACK)
            screen.blit(lab, (x + btn_w//2 - lab.get_width()//2, y + btn_h//2 - lab.get_height()//2))

        instruct = btn_font.render("キー1-4でも選択できます。Escで終了", True, BLACK)
        screen.blit(instruct, (win_w//2 - instruct.get_width()//2, y + btn_h + 40))

        # デッキ作成ボタン（難易度選択の下部、中央に配置）
        deck_w, deck_h = 260, 60
        deck_x = win_w//2 - deck_w//2
        deck_y = y + btn_h + 100
        deck_rect = pygame.Rect(deck_x, deck_y, deck_w, deck_h)
        mx, my = pygame.mouse.get_pos()
        deck_color = (180,180,180) if deck_rect.collidepoint((mx,my)) else (210,210,210)
        pygame.draw.rect(screen, deck_color, deck_rect)
        pygame.draw.rect(screen, BLACK, deck_rect, 2)
        deck_label = btn_font.render("デッキ作成", True, BLACK)
        screen.blit(deck_label, (deck_x + deck_w//2 - deck_label.get_width()//2, deck_y + deck_h//2 - deck_label.get_height()//2))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # まず難易度ボタンのクリック判定（既存）
                for i, (label, val) in enumerate(options):
                    x = start_x + i * (btn_w + spacing)
                    rect = pygame.Rect(x, y, btn_w, btn_h)
                    if rect.collidepoint(event.pos):
                        CPU_DIFFICULTY = val
                        return
                # デッキ作成ボタンのクリック判定
                if deck_rect.collidepoint(event.pos):
                    show_deck_editor()
                    # デッキ編集から戻ってきたら再描画して継続
                    continue
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.unicode in ("1", "2", "3", "4"):
                    CPU_DIFFICULTY = int(event.unicode)
                    return
        clock.tick(30)


piece_images = {
    'white': {
        'K': pygame.image.load("images/Chess_k_white.png"),
        'Q': pygame.image.load("images/Chess_q_white.png"),
        'R': pygame.image.load("images/Chess_r_white.png"),
        'B': pygame.image.load("images/Chess_b_white.png"),
        'N': pygame.image.load("images/Chess_n_white.png"),
        'P': pygame.image.load("images/Chess_p_white.png"),
    },
    'black': {
        'K': pygame.image.load("images/Chess_k_black.png"),
        'Q': pygame.image.load("images/Chess_q_black.png"),
        'R': pygame.image.load("images/Chess_r_black.png"),
        'B': pygame.image.load("images/Chess_b_black.png"),
        'N': pygame.image.load("images/Chess_n_black.png"),
        'P': pygame.image.load("images/Chess_p_black.png"),
    }
}
promotion_images = {
    'white': {k: piece_images['white'][k] for k in ['Q', 'R', 'B', 'N']},
    'black': {k: piece_images['black'][k] for k in ['Q', 'R', 'B', 'N']},
}


current_turn = 'white' # 今どちらのプレイヤーの番か
game_over = False      # ゲームが終わったかどうか
check_state = False    #  チェック中かどうか
game_over_winner = None # 勝者（まだ決まっていない）
def show_promotion_menu_with_images(screen, piece_color):
    # プロモーションは通常の駒のみ（Q, R, B, N）
    promotion_options = ['Q', 'R', 'B', 'N']
    selected = None

    # サイズ・配置設定
    img_size = 100
    spacing = 40

    # 駒の配置（盤面の中央に配置）
    total_width = len(promotion_options) * img_size + (len(promotion_options) - 1) * spacing
    start_x = (WINDOW_WIDTH - total_width) // 2
    center_y = BOARD_OFFSET_Y + HEIGHT // 2

    while selected is None:
        screen.fill((220, 220, 220))
        title_font = pygame.font.SysFont("Noto_SansJP", max(36, int(SCREEN_HEIGHT * 0.04)))
        text = title_font.render("昇格する駒を選択", True, (0, 0, 0))
        screen.blit(text, (WINDOW_WIDTH // 2 - text.get_width() // 2, center_y - 100))

        positions = []

        # 通常駒の表示
        for i, opt in enumerate(promotion_options):
            x = start_x + i * (img_size + spacing)
            y = center_y - img_size // 2
            img = pygame.transform.scale(promotion_images[piece_color][opt], (img_size, img_size))
            screen.blit(img, (x, y))
            positions.append((x, x + img_size, y, y + img_size, opt))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                for x1, x2, y1, y2, opt in positions:
                    if x1 <= mx <= x2 and y1 <= my <= y2:
                        selected = opt
                        break
    return selected

# 起動時に難易度選択画面を表示（関数定義の後で呼び出す）
show_start_screen(screen)

class Piece:
    def __init__(self, row, col, name, color):
        self.row = row
        self.col = col
        self.name = name
        self.color = color
        self.has_moved = False
        self.gimmick = None  # ギミック取得用

    def draw(self, surface):
        # オフセットを考慮して描画
        x = BOARD_OFFSET_X + self.col * SQUARE_SIZE
        y = BOARD_OFFSET_Y + self.row * SQUARE_SIZE
        img = piece_images[self.color][self.name]
        img = pygame.transform.scale(img, (SQUARE_SIZE, SQUARE_SIZE))
        surface.blit(img, (x, y))

    def is_occupied(self, row, col, pieces, same_color=None):
        for piece in pieces:
            if piece.row == row and piece.col == col:
                if same_color is None:
                    return True
                if (piece.color == self.color) == same_color:
                    return True
        return False

    def get_valid_moves(self, pieces, ignore_castling=False):
        moves = []
        def add_direction(dr, dc, max_steps=8):
            for step in range(1, max_steps + 1):
                new_row = self.row + dr * step
                new_col = self.col + dc * step
                if 0 <= new_row < 8 and 0 <= new_col < 8:
                    if self.is_occupied(new_row, new_col, pieces, same_color=True):
                        break
                    moves.append((new_row, new_col))
                    if self.is_occupied(new_row, new_col, pieces, same_color=False):
                        break
                else:
                    break

        if self.name == 'K':
            directions = [(dr, dc) for dr in [-1, 0, 1] for dc in [-1, 0, 1] if dr != 0 or dc != 0]
            for dr, dc in directions:
                nr, nc = self.row + dr, self.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and not self.is_occupied(nr, nc, pieces, same_color=True):
                    moves.append((nr, nc))
            # --- キャスリング判定 ---
            if not ignore_castling:
                # キングが初期位置(e列)にいること
                if not self.has_moved and self.col == 4 and not is_in_check(pieces, self.color):
                    row = self.row
                    # kingside
                    kingside_rook = get_piece_at(row, 7, pieces)
                    if (
                        kingside_rook and kingside_rook.name == 'R' and
                        kingside_rook.color == self.color and not kingside_rook.has_moved
                    ):
                        if all(get_piece_at(row, c, pieces) is None for c in [5, 6]):
                            safe = True
                            for c in [4, 5, 6]:
                                temp_pieces = []
                                for p in pieces:
                                    if p == self:
                                        temp_king = Piece(row, c, 'K', self.color)
                                        temp_king.has_moved = True
                                        temp_pieces.append(temp_king)
                                    elif p == kingside_rook:
                                        temp_rook = Piece(row, 7, 'R', self.color)
                                        temp_rook.has_moved = True
                                        temp_pieces.append(temp_rook)
                                    else:
                                        temp_pieces.append(p)
                                if is_in_check(temp_pieces, self.color):
                                    safe = False
                                    break
                            if safe:
                                moves.append((row, 6)) # g列
                    # queenside
                    queenside_rook = get_piece_at(row, 0, pieces)
                    if (
                        queenside_rook and queenside_rook.name == 'R' and
                        queenside_rook.color == self.color and not queenside_rook.has_moved
                    ):
                        # 1,2,3列が空であること
                        if all(get_piece_at(row, c, pieces) is None for c in [1, 2, 3]):
                            # 2,3,4列が攻撃されていないこと
                            safe = True
                            for c in [4, 3, 2]:
                                temp_pieces = []
                                for p in pieces:
                                    if p == self:
                                        temp_king = Piece(row, c, 'K', self.color)
                                        temp_king.has_moved = True
                                        temp_pieces.append(temp_king)
                                    elif p == queenside_rook:
                                        temp_rook = Piece(row, 0, 'R', self.color)
                                        temp_rook.has_moved = True
                                        temp_pieces.append(temp_rook)
                                    else:
                                        temp_pieces.append(p)
                                if is_in_check(temp_pieces, self.color):
                                    safe = False
                                    break
                            if safe:
                                moves.append((row, 2)) # c列

        elif self.name == 'Q':
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
                add_direction(dr, dc)

        elif self.name == 'B':
            for dr, dc in [(-1, -1), (-1, 1), (1, -1), (1, 1)]:
                add_direction(dr, dc)

        elif self.name == 'R':
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                add_direction(dr, dc)

        elif self.name == 'N':
            for dr, dc in [(2, 1), (1, 2), (-1, 2), (-2, 1), (-2, -1), (-1, -2), (1, -2), (2, -1)]:
                nr, nc = self.row + dr, self.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and not self.is_occupied(nr, nc, pieces, same_color=True):
                    moves.append((nr, nc))

        elif self.name == 'P':
            dir = -1 if self.color == 'white' else 1
            start_row = 6 if self.color == 'white' else 1
            # 前進
            if not self.is_occupied(self.row + dir, self.col, pieces):
                moves.append((self.row + dir, self.col))
                if self.row == start_row and not self.is_occupied(self.row + 2 * dir, self.col, pieces):
                    moves.append((self.row + 2 * dir, self.col))
            # 通常の斜め取り
            for dc in [-1, 1]:
                nr, nc = self.row + dir, self.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and self.is_occupied(nr, nc, pieces, same_color=False):
                    moves.append((nr, nc))
            # --- アンパサン ---
            for dc in [-1, 1]:
                nr, nc = self.row + dir, self.col + dc
                if (
                    en_passant_target is not None and
                    (nr, nc) == en_passant_target and
                    abs(self.col - nc) == 1 and
                    ((self.color == 'white' and self.row == 3) or (self.color == 'black' and self.row == 4))
                ):
                    moves.append((nr, nc))
        return moves

def create_pieces(): #初期状態の作成
    pieces = []
    pieces += [Piece(7, 0, 'R', 'white'), Piece(7, 1, 'N', 'white'), Piece(7, 2, 'B', 'white'),
               Piece(7, 3, 'Q', 'white'), Piece(7, 4, 'K', 'white'), Piece(7, 5, 'B', 'white'),
               Piece(7, 6, 'N', 'white'), Piece(7, 7, 'R', 'white')]
    pieces += [Piece(6, i, 'P', 'white') for i in range(8)]
    pieces += [Piece(0, 0, 'R', 'black'), Piece(0, 1, 'N', 'black'), Piece(0, 2, 'B', 'black'),
               Piece(0, 3, 'Q', 'black'), Piece(0, 4, 'K', 'black'), Piece(0, 5, 'B', 'black'),
               Piece(0, 6, 'N', 'black'), Piece(0, 7, 'R', 'black')]
    pieces += [Piece(1, i, 'P', 'black') for i in range(8)]
    return pieces

def draw_board():
    # --- フォント・サーフェスをキャッシュ ---
    if not hasattr(draw_board, "font_cache"):
        draw_board.font_cache = {}
    font_cache = draw_board.font_cache

    def get_font(size):
        key = ("Noto_SansJP", size)
        if key not in font_cache:
            font_cache[key] = pygame.font.SysFont("Noto_SansJP", size)
        return font_cache[key]

    # 全体背景を白色で塗りつぶし（両端の余白部分も真っ白）
    screen.fill(WHITE)

    # フレームごとにクリック領域リストを初期化（必ず存在させる）
    draw_board.player_gimmick_click_areas = []

    # 盤面をオフセット位置から描画
    for row in range(8):
        for col in range(8):
            color = WHITE if (row + col) % 2 == 0 else GRAY
            pygame.draw.rect(
                screen, color,
                (BOARD_OFFSET_X + col * SQUARE_SIZE, BOARD_OFFSET_Y + row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
            )
    # 盤面の左右端に太めの黒線を描画して境界を明確にする
    left_x = BOARD_OFFSET_X
    right_x = BOARD_OFFSET_X + 8 * SQUARE_SIZE
    pygame.draw.rect(screen, BLACK, (left_x-2, BOARD_OFFSET_Y, 4, 8 * SQUARE_SIZE))
    pygame.draw.rect(screen, BLACK, (right_x-2, BOARD_OFFSET_Y, 4, 8 * SQUARE_SIZE))
    # ギミック枠（上下配置）
    SILVER = (192, 192, 192)
    
    # 上部のギミック枠（AI用・銀色）
    pygame.draw.rect(screen, SILVER, (0, 0, WINDOW_WIDTH, GIMMICK_ROW_HEIGHT))
    
    # 下部のギミック枠（プレイヤー用・金色）
    pygame.draw.rect(screen, GOLD, (0, WINDOW_HEIGHT - GIMMICK_ROW_HEIGHT, WINDOW_WIDTH, GIMMICK_ROW_HEIGHT))
    
    # --- 右上余白にギミックカード画像を表示 ---
    # カード画像は一度オリジナルを読み込み、必要時だけ高品質に縮小/拡大してキャッシュする
    # カード描画に使うパス（外部から更新可能）。初期状態では表示しない（None）
    if not hasattr(draw_board, 'current_card_path'):
        draw_board.current_card_path = None

    # current_card_path が None の場合はカード描画をスキップ
    if draw_board.current_card_path is None:
        draw_board.card_img_orig = None
        draw_board.card_aspect_ratio = 63 / 88
        draw_board.card_img_scaled = None
        draw_board.card_scaled_size = (0, 0)
    else:
        if not hasattr(draw_board, "card_img_orig") or getattr(draw_board, 'card_img_path_loaded', None) != draw_board.current_card_path:
            try:
                img = pygame.image.load(draw_board.current_card_path)
                draw_board.card_img_orig = img.convert_alpha()
                draw_board.card_aspect_ratio = draw_board.card_img_orig.get_width() / draw_board.card_img_orig.get_height()
                draw_board.card_img_scaled = None
                draw_board.card_scaled_size = (0, 0)
                draw_board.card_img_path_loaded = draw_board.current_card_path
            except Exception:
                draw_board.card_img_orig = None
                draw_board.card_aspect_ratio = 63 / 88  # デフォルトのカード比率
                draw_board.card_img_scaled = None
                draw_board.card_scaled_size = (0, 0)

    try:
        if draw_board.card_img_orig is not None:
            aspect_ratio = draw_board.card_aspect_ratio

            # 利用可能な余白スペースを計算
            available_width = WINDOW_WIDTH - (BOARD_OFFSET_X + WIDTH) - 40
            available_height = WINDOW_HEIGHT - GIMMICK_ROW_HEIGHT * 2 - 40

            # アスペクト比を保持しながら、余白に収まる最大サイズを計算
            if available_width / aspect_ratio <= available_height:
                card_width = int(available_width * 0.8)
                card_height = int(card_width / aspect_ratio)
            else:
                card_height = int(available_height * 0.8)
                card_width = int(card_height * aspect_ratio)

            # 高品質縮小（必要なときだけ行う）
            if not hasattr(draw_board, 'card_img_cache'):
                draw_board.card_img_cache = {}

            cache_key = (id(draw_board.card_img_orig), card_width, card_height)
            if cache_key in draw_board.card_img_cache:
                draw_board.card_img_scaled = draw_board.card_img_cache[cache_key]
                draw_board.card_scaled_size = (card_width, card_height)
            else:
                try:
                    # iterative downscale: 大きく縮小する場合は段階的に半分ずつ縮小してから最終サイズにする
                    def high_quality_scale(src_surf, target_w, target_h):
                        src_w, src_h = src_surf.get_size()
                        cur = src_surf
                        # while we can comfortably halve both dimensions and still be >= target, do half-step smoothscale
                        while src_w // 2 >= target_w and src_h // 2 >= target_h:
                            next_w, next_h = max(target_w, src_w // 2), max(target_h, src_h // 2)
                            cur = pygame.transform.smoothscale(cur, (next_w, next_h)).convert_alpha()
                            src_w, src_h = cur.get_size()
                        # final smoothscale to exact target if needed
                        if (src_w, src_h) != (target_w, target_h):
                            cur = pygame.transform.smoothscale(cur, (target_w, target_h)).convert_alpha()
                        return cur

                    draw_board.card_img_scaled = high_quality_scale(draw_board.card_img_orig, card_width, card_height)
                except Exception:
                    # フォールバック
                    try:
                        draw_board.card_img_scaled = pygame.transform.smoothscale(draw_board.card_img_orig, (card_width, card_height)).convert_alpha()
                    except Exception:
                        draw_board.card_img_scaled = pygame.transform.scale(draw_board.card_img_orig, (card_width, card_height)).convert_alpha()
                draw_board.card_scaled_size = (card_width, card_height)
                draw_board.card_img_cache[cache_key] = draw_board.card_img_scaled

            card_img = draw_board.card_img_scaled
        else:
            card_img = None

        # 右上余白の座標（ギミック枠の下、盤面の右端よりさらに右）
        card_x = BOARD_OFFSET_X + WIDTH + 20
        card_y = GIMMICK_ROW_HEIGHT + 20

        if card_img is not None and card_x + card_img.get_width() <= WINDOW_WIDTH - 10:
            screen.blit(card_img, (card_x, card_y))
        elif draw_board.current_card_path is not None and card_img is None and card_x + card_width <= WINDOW_WIDTH - 10:
            # 画像が無い場合は代替表示（四角形）
            pygame.draw.rect(screen, (200, 200, 200), (card_x, card_y, card_width, card_height))
            pygame.draw.rect(screen, BLACK, (card_x, card_y, card_width, card_height), 2)
            card_font = get_font(max(16, int(SCREEN_HEIGHT * 0.02)))
            card_text = card_font.render("カード画像", True, BLACK)
            text_rect = card_text.get_rect(center=(card_x + card_width//2, card_y + card_height//2))
            screen.blit(card_text, text_rect)
        else:
            # 非表示または収まらない場合は何もしない
            pass
    except Exception as e:
        # 何らかの理由で失敗した場合の代替表示（ただし current_card_path が設定されていない場合は何もしない）
        if draw_board.current_card_path is not None:
            try:
                pygame.draw.rect(screen, (200, 200, 200), (card_x, card_y, 120, 160))
                pygame.draw.rect(screen, BLACK, (card_x, card_y, 120, 160), 2)
            except Exception:
                pass
            aspect_ratio = draw_board.card_aspect_ratio
            available_width = WINDOW_WIDTH - (BOARD_OFFSET_X + WIDTH) - 40
            available_height = WINDOW_HEIGHT - GIMMICK_ROW_HEIGHT * 2 - 40
            
            if available_width / aspect_ratio <= available_height:
                card_width = int(available_width * 0.8)
                card_height = int(card_width / aspect_ratio)
            else:
                card_height = int(available_height * 0.8)
                card_width = int(card_height * aspect_ratio)
                
            card_x = BOARD_OFFSET_X + WIDTH + 20
            card_y = GIMMICK_ROW_HEIGHT + 20
            if card_x + card_width <= WINDOW_WIDTH - 10:
                pygame.draw.rect(screen, (200, 200, 200), (card_x, card_y, card_width, card_height))
                pygame.draw.rect(screen, BLACK, (card_x, card_y, card_width, card_height), 2)
                # "カード画像" テキストを表示
                card_font = get_font(max(16, int(SCREEN_HEIGHT * 0.02)))
                card_text = card_font.render("カード画像", True, BLACK)
                text_rect = card_text.get_rect(center=(card_x + card_width//2, card_y + card_height//2))
                screen.blit(card_text, text_rect)

                # --- カード下にギミック説明を描画 ---
                # ここでは最初のギミックの説明を例として表示（必要なら選択中のカード説明に差し替え）
                try:
                    desc_font = get_font(max(14, int(SCREEN_HEIGHT * 0.018)))
                    desc_max_w = card_width - 20
                    # 例: 表示する説明テキスト（ここは選択中のカードに応じて変更可）
                    desc_text = gimmicks[0].get_description() if gimmicks else ""
                    wrapped = wrap_text_for_width(desc_text, desc_font, desc_max_w)
                    # 背景ボックス
                    desc_h = len(wrapped) * (desc_font.get_height() + 2) + 8
                    desc_x = card_x
                    desc_y = card_y + card_height + 8
                    overlay = pygame.Surface((card_width, desc_h), pygame.SRCALPHA)
                    overlay.fill((255, 255, 255, 220))  # 白背景（少しだけ透過）
                    screen.blit(overlay, (desc_x, desc_y))
                    # テキスト描画（アウトライン付きで見やすく）
                    for i, line in enumerate(wrapped):
                        ln_surf = render_text_with_outline(desc_font, line, BLACK, outline_color=(255,255,255))
                        screen.blit(ln_surf, (desc_x + 10, desc_y + 6 + i * (desc_font.get_height() + 2)))
                except Exception:
                    pass

    # ギミックアイコンを2段構成で描画（画面サイズに応じて調整）
    circle_radius = max(20, int(SCREEN_HEIGHT * 0.025))  # 画面高さの2.5%
    text_font = get_font(max(16, int(SCREEN_HEIGHT * 0.02)))  # 画面高さの2%
    count_font = get_font(max(12, int(SCREEN_HEIGHT * 0.015)))  # 画面高さの1.5%
    x_font = get_font(max(12, int(SCREEN_HEIGHT * 0.015)))
    
    # 1段あたり4つのギミックを配置
    gimmicks_per_row = 4
    gimmick_width = WINDOW_WIDTH // gimmicks_per_row
    row_height = GIMMICK_ROW_HEIGHT // 2
    
    for i, gimmick in enumerate(gimmicks):
        gimmick_name = gimmick.name
        count_player = player_gimmick_counts.get(gimmick_name, 0)
        count_cpu = cpu_gimmick_counts.get(gimmick_name, 0)
        
        # 上段(0-3)と下段(4-7)の配置を決定
        row = i // gimmicks_per_row  # 0 or 1
        col = i % gimmicks_per_row   # 0, 1, 2, 3
        
        # --- 上部のギミック枠（AI用・銀色） ---
        y_top_upper = row_height // 2 + row * row_height
        circle_center_top = (col * gimmick_width + gimmick_width // 2, y_top_upper)
        pygame.draw.circle(screen, SILVER, circle_center_top, circle_radius)
        pygame.draw.circle(screen, BLACK, circle_center_top, circle_radius, 2)
        
        cache_key = (gimmick_name, "top")
        if cache_key not in font_cache:
            gimmick_text_surface = text_font.render(gimmick_name, True, BLACK)
            x_surface = x_font.render("×", True, BLACK)
            font_cache[cache_key] = (gimmick_text_surface, x_surface)
        else:
            gimmick_text_surface, x_surface = font_cache[cache_key]
        
        gimmick_text_rect = gimmick_text_surface.get_rect(center=circle_center_top)
        screen.blit(gimmick_text_surface, gimmick_text_rect)
        
        count_surface = count_font.render(str(count_cpu), True, BLACK)
        x_rect = x_surface.get_rect()
        count_rect = count_surface.get_rect()
        right_of_circle = circle_center_top[0] + circle_radius - 15
        below_circle = circle_center_top[1] + circle_radius - 2
        x_rect.topleft = (right_of_circle, below_circle)
        count_rect.topleft = (x_rect.right + 1, below_circle)
        screen.blit(x_surface, x_rect)
        screen.blit(count_surface, count_rect)
        
        # --- 下部のギミック枠（プレイヤー用・金色） ---
        # プレイヤー側は配置を逆にする：上段に炎氷雷風、下段に２ｅ収回
        player_row = 1 - row  # 行を逆転（0→1, 1→0）
        player_gimmick_index = player_row * gimmicks_per_row + col
        if player_gimmick_index < len(gimmicks):
            player_gimmick = gimmicks[player_gimmick_index]
            player_gimmick_name = player_gimmick.name
            player_count = player_gimmick_counts.get(player_gimmick_name, 0)
            
            y_bottom_upper = WINDOW_HEIGHT - GIMMICK_ROW_HEIGHT + row_height // 2 + row * row_height
            circle_center_bottom = (col * gimmick_width + gimmick_width // 2, y_bottom_upper)
            pygame.draw.circle(screen, GOLD, circle_center_bottom, circle_radius)
            pygame.draw.circle(screen, BLACK, circle_center_bottom, circle_radius, 2)
            
            cache_key = (player_gimmick_name, "bottom")
            if cache_key not in font_cache:
                gimmick_text_surface = text_font.render(player_gimmick_name, True, BLACK)
                x_surface = x_font.render("×", True, BLACK)
                font_cache[cache_key] = (gimmick_text_surface, x_surface)
            else:
                gimmick_text_surface, x_surface = font_cache[cache_key]
            
            gimmick_text_rect = gimmick_text_surface.get_rect(center=circle_center_bottom)
            screen.blit(gimmick_text_surface, gimmick_text_rect)
            
            count_surface = count_font.render(str(player_count), True, BLACK)
            x_rect = x_surface.get_rect()
            count_rect = count_surface.get_rect()
            right_of_circle = circle_center_bottom[0] + circle_radius - 15
            below_circle = circle_center_bottom[1] + circle_radius - 2
            x_rect.topleft = (right_of_circle, below_circle)
            count_rect.topleft = (x_rect.right + 1, below_circle)
            screen.blit(x_surface, x_rect)
            screen.blit(count_surface, count_rect)
            # プレイヤーのギミックサークルをクリック可能にするため、
            # クリック領域と名前を draw_board に保存しておく（イベント処理で参照）
            if not hasattr(draw_board, 'player_gimmick_click_areas'):
                draw_board.player_gimmick_click_areas = []
            # 各フレームで上書きするので一旦リストをクリアするのは呼び出し元で行う
            draw_board.player_gimmick_click_areas.append((player_gimmick_name, pygame.Rect(circle_center_bottom[0]-circle_radius, circle_center_bottom[1]-circle_radius, circle_radius*2, circle_radius*2)))
    # game_over の表示はメインループ側で再戦画面を表示するため、ここでは描画しない

def get_clicked_pos(pos):
    x, y = pos
    # オフセットを考慮
    col = (x - BOARD_OFFSET_X) // SQUARE_SIZE
    row = (y - BOARD_OFFSET_Y) // SQUARE_SIZE
    if col < 0 or col > 7 or row < 0 or row > 7:
        return None, None
    return row, col

def get_piece_at(row, col, pieces):
    if row is None or col is None or not (0 <= row < 8 and 0 <= col < 8):
        return None
    for piece in pieces:
        if piece.row == row and piece.col == col:
            return piece
    return None

def is_in_check(pieces, color):
    # 指定色のキングの位置を探す
    king = None
    for p in pieces:
        if p.name == 'K' and p.color == color:
            king = p
            break
    if not king:
        return False  # キングがいない場合はチェックでない
    king_pos = (king.row, king.col)
    # 相手の全駒の合法手にキングの位置が含まれるか
    opponent_color = 'black' if color == 'white' else 'white'
    for p in pieces:
        if p.color == opponent_color:
            moves = p.get_valid_moves(pieces, ignore_castling=True)
            if king_pos in moves:
                return True
    return False

def has_legal_moves(pieces, color):
    # 指定色の全駒について、合法手が存在するか
    for p in pieces:
        if p.color == color:
            moves = p.get_valid_moves(pieces)
            for move in moves:
                # move後の盤面を仮想的に作成
                temp_pieces = []
                for q in pieces:
                    if q == p:
                        temp_piece = Piece(move[0], move[1], p.name, p.color)
                        temp_piece.has_moved = True
                        temp_pieces.append(temp_piece)
                    elif q.row == move[0] and q.col == move[1]:
                        continue  # 取られる駒は除外
                    else:
                        temp_pieces.append(q)
                # キングが盤面にいない場合は合法手なしとみなす
                if not any(tp.name == 'K' and tp.color == color for tp in temp_pieces):
                    # 盤面の駒も描写（draw_boardはメインループで毎回呼ばれるのでここでは何もしない）
                    continue
                if not is_in_check(temp_pieces, color):
                    return True
    return False

en_passant_target = None  # アンパサン可能なマス (row, col) or None

pieces = create_pieces()  #チェスの初期配置作成
selected_piece = None  #今選ばれている駒はない
running = True  #ゲーム実行中

TURN_CHANGE_EVENT = pygame.USEREVENT + 1  # カスタムイベント定義

def ai_move(pieces):
    # AI.pyをサブプロセスとして呼び出し、合法手を取得
    ai_path = "AI.py"
    # piecesをdictリストに変換
    pieces_dict = []
    for p in pieces:
        pieces_dict.append({
            'row': p.row,
            'col': p.col,
            'name': p.name,
            'color': p.color
        })
    # チェック中かどうかも渡す
    black_in_check = is_in_check(pieces, 'black')
    ai_input = {
        "pieces": pieces_dict,
        "black_in_check": black_in_check
    }
    # include difficulty so AI can adjust strength
    try:
        ai_input["difficulty"] = CPU_DIFFICULTY
    except NameError:
        # fallback default
        ai_input["difficulty"] = 3
    proc = subprocess.Popen(
        [sys.executable, ai_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    board_json = json.dumps(ai_input)
    try:
        out, err = proc.communicate(input=board_json + "\n", timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        return None
    if out:
        try:
            move = json.loads(out.strip())
            return move
        except Exception:
            return None
    return None

def cpu_make_move(
    pieces,
    get_piece_at,
    is_in_check,
    has_legal_moves,
    show_promotion_menu_with_images,
    global_vars,
    get_valid_moves_func
):
    """
    黒AIの手番で0.5秒後に呼ばれる。AIの指し手を取得し、盤面を更新する。
    """
    ai_result = ai_move(pieces)
    if ai_result:
        from_row = ai_result['from_row']
        from_col = ai_result['from_col']
        to_row = ai_result['to_row']
        to_col = ai_result['to_col']
        piece = get_piece_at(from_row, from_col, pieces)
        if piece:
            # 移動先に駒がいれば取る
            target = get_piece_at(to_row, to_col, pieces)
            if target:
                pieces.remove(target)
            piece.row, piece.col = to_row, to_col
            piece.has_moved = True

            # ポーンのプロモーション
            if piece.name == 'P' and piece.row == 7:
                # プロモーションUIを使わず自動でクイーンに昇格
                piece.name = 'Q'

            # ターン切り替え
            global_vars['current_turn'] = 'white'
            pygame.time.set_timer(global_vars['TURN_CHANGE_EVENT'], 50, loops=1)

cpu_wait = False
cpu_wait_start = 0

# フレームレート制限のためのクロック
clock = pygame.time.Clock()

while running:
    # フレームレートを60FPSに制限
    clock.tick(60)
    
    # --- 追加: OS応答性向上のため ---
    pygame.event.pump()

    # キングが盤面にいない場合は即座に勝敗を決定
    white_king = any(p.name == 'K' and p.color == 'white' for p in pieces)
    black_king = any(p.name == 'K' and p.color == 'black' for p in pieces)
    if not white_king:
        game_over = True
        game_over_winner = 'black'
    elif not black_king:
        game_over = True
        game_over_winner = 'white'

    # --- 追加: どちらかが詰みの場合も勝利判定 ---
    if not game_over:
        if not has_legal_moves(pieces, 'white') and is_in_check(pieces, 'white'):
            game_over = True
            game_over_winner = 'black'
        elif not has_legal_moves(pieces, 'black') and is_in_check(pieces, 'black'):
            game_over = True
            game_over_winner = 'white'

    draw_board()
    for piece in pieces:
        piece.draw(screen)

    # チェック中の表示（両者チェック中対応）
    if not game_over:
        check_colors = []
        if is_in_check(pieces, 'white'):
            check_colors.append('white')
        if is_in_check(pieces, 'black'):
            check_colors.append('black')
        if check_colors:
            # 直近でチェックになった色を下に表示
            # チェック状態が変化した場合に備えて、前回の状態を保存
            if not hasattr(draw_board, "last_check_colors"):
                draw_board.last_check_colors = []
            # 新しいチェック状態が前回と異なる場合、順序を更新
            if check_colors != draw_board.last_check_colors:
                draw_board.last_check_colors = check_colors.copy()
            # 表示（駒の色に応じて位置を変える）
            for color in draw_board.last_check_colors:
                msg = f"{'白' if color == 'white' else '黒'}チェック中"
                check_text = font.render(msg, True, (255, 165, 0))
                
                # 駒の色に応じて位置を調整
                if color == 'black':
                    # 黒チェック中：現在の位置（盤面右寄り）
                    text_x = BOARD_OFFSET_X - check_text.get_width() - 30
                    text_y = BOARD_OFFSET_Y + 100 - SQUARE_SIZE
                else:  # white
                    # 白チェック中：黒チェック中の左側
                    text_x = BOARD_OFFSET_X - check_text.get_width() - 150  # さらに左に120px移動
                    text_y = BOARD_OFFSET_Y + 100 - SQUARE_SIZE
                
                # 背景を半透明の黒で塗りつぶして視認性を向上
                bg_rect = pygame.Rect(text_x - 10, text_y - 5, check_text.get_width() + 20, check_text.get_height() + 10)
                pygame.draw.rect(screen, (0, 0, 0, 180), bg_rect)
                pygame.draw.rect(screen, (255, 165, 0), bg_rect, 2)  # オレンジの枠線
                screen.blit(check_text, (text_x, text_y))

    if selected_piece:
        valid_moves = selected_piece.get_valid_moves(pieces)
        for move in valid_moves:
            r, c = move
            # アンパサン・キャスリング・チェックメイトの移動可能マスの色分け
            is_en_passant = False
            is_castling = False
            is_checkmate = False
            # アンパサン判定
            if selected_piece.name == 'P' and en_passant_target is not None:
                if (r, c) == en_passant_target:
                    if ((selected_piece.color == 'white' and selected_piece.row == 3) or
                        (selected_piece.color == 'black' and selected_piece.row == 4)):
                        is_en_passant = True
            # キャスリング判定
            if selected_piece.name == 'K' and abs(c - selected_piece.col) == 2:
                is_castling = True
            # --- 修正: キングを取れるマスも赤色に ---
            target_piece = get_piece_at(r, c, pieces)
            if target_piece and target_piece.name == 'K' and target_piece.color != selected_piece.color:
                is_checkmate = True
            else:
                # チェックメイト判定（相手詰み）
                temp_pieces = pieces[:]
                temp_piece = selected_piece
                captured = get_piece_at(r, c, temp_pieces)
                temp_pieces.remove(temp_piece)
                if captured:
                    temp_pieces.remove(captured)
                # 移動後の駒の状態を再現
                new_piece = Piece(r, c, temp_piece.name, temp_piece.color)
                new_piece.has_moved = True
                temp_pieces.append(new_piece)
                next_turn = 'black' if temp_piece.color == 'white' else 'white'
                if any(p.name == 'K' and p.color == next_turn for p in temp_pieces):
                    if is_in_check(temp_pieces, next_turn) and not has_legal_moves(temp_pieces, next_turn):
                        is_checkmate = True
            # 色決定
            if is_checkmate:
                color = RED #チェックメイト可能範囲 or キングを取れる範囲
            elif is_en_passant:
                color = BLUE #アンパサン可能範囲
            elif is_castling:
                color = GOLD #キャスリング可能範囲
            else:
                color = GREEN
            pygame.draw.rect(
                screen, color,
                (BOARD_OFFSET_X + c * SQUARE_SIZE, BOARD_OFFSET_Y + r * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE), 3
            )

    pygame.display.flip()

    # ゲーム終了時はリスタート/終了の選択肢を表示
    if game_over:
        # 表示テキスト（太字・視認性向上）
        restart_font = pygame.font.SysFont("Noto_SansJP", max(28, int(SCREEN_HEIGHT * 0.035)), bold=True)
        info_font = pygame.font.SysFont("Noto_SansJP", max(18, int(SCREEN_HEIGHT * 0.02)), bold=True)
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    # R で再戦、Q または ESC で終了
                    if event.key == pygame.K_r:
                        # ゲーム状態をリセット
                        pieces = create_pieces()
                        selected_piece = None
                        current_turn = 'white'
                        game_over = False
                        game_over_winner = None
                        en_passant_target = None
                        cpu_wait = False
                        cpu_wait_start = 0
                        # フォントキャッシュをクリア
                        if hasattr(draw_board, 'font_cache'):
                            draw_board.font_cache.clear()
                        # ループを抜けてゲーム再開
                        break
                    elif event.key in (pygame.K_q, pygame.K_ESCAPE):
                        pygame.quit()
                        sys.exit()

            # リスタート画面を描画
            draw_board()
            for piece in pieces:
                piece.draw(screen)

            # 勝者表示（半透明背景＋アウトライン）
            if game_over_winner:
                winner_text = f"{game_over_winner.upper()} の勝利！"
                text_surf = restart_font.render(winner_text, True, RED)
                tx = WINDOW_WIDTH // 2 - text_surf.get_width() // 2
                ty = WINDOW_HEIGHT // 2 - 110
                # 半透明の背景矩形
                try:
                    overlay = pygame.Surface((text_surf.get_width() + 40, text_surf.get_height() + 30), pygame.SRCALPHA)
                    overlay.fill((0, 0, 0, 160))  # 半透明黒
                    screen.blit(overlay, (tx - 20, ty - 10))
                except Exception:
                    # 古いpygameでも問題が出ないように保険
                    pygame.draw.rect(screen, (0, 0, 0), (tx - 20, ty - 10, text_surf.get_width() + 40, text_surf.get_height() + 30))
                # アウトラインを描く（黒の4方向に軽くオフセットして太く見せる）
                outline_color = (0, 0, 0)
                for ox, oy in [(-2,0),(2,0),(0,-2),(0,2)]:
                    o_surf = restart_font.render(winner_text, True, outline_color)
                    screen.blit(o_surf, (tx+ox, ty+oy))
                # 本文
                screen.blit(text_surf, (tx, ty))

            prompt = "[R] 再戦    [Q] 終了"
            prompt_surf = info_font.render(prompt, True, GOLD)
            screen.blit(prompt_surf, (WINDOW_WIDTH // 2 - prompt_surf.get_width() // 2, WINDOW_HEIGHT // 2))

            note = "再戦時に盤面が初期化されます"
            note_surf = info_font.render(note, True, RED)
            screen.blit(note_surf, (WINDOW_WIDTH // 2 - note_surf.get_width() // 2, WINDOW_HEIGHT // 2 + 40))

            pygame.display.flip()
            # 再戦指示でループを抜ける
            if not game_over:
                break

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        elif event.type == pygame.VIDEORESIZE:
            # ウィンドウサイズが変更された場合の処理
            if not is_fullscreen:
                WINDOW_WIDTH, WINDOW_HEIGHT = event.w, event.h
                # ウィンドウモード用のレイアウト再計算
                layout_result = calculate_layout(False, WINDOW_WIDTH, WINDOW_HEIGHT)
                WIDTH, HEIGHT, SQUARE_SIZE, GIMMICK_ROW_HEIGHT, BOARD_OFFSET_X, BOARD_OFFSET_Y = layout_result[2:]
                screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
                # フォントキャッシュをクリアして新しい画面サイズに対応
                if hasattr(draw_board, "font_cache"):
                    draw_board.font_cache.clear()
        
        elif event.type == pygame.KEYDOWN:
            # 修正: 起動直後の視認性問題を避けるためESCでの切替を無効化
            # F11 または Alt+Enter で全画面⇔ウィンドウ切替
            mods = event.mod if hasattr(event, 'mod') else pygame.key.get_mods()
            is_alt_enter = (event.key == pygame.K_RETURN and (mods & pygame.KMOD_ALT))

            if event.key == pygame.K_F11 or is_alt_enter:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    WINDOW_WIDTH, WINDOW_HEIGHT, WIDTH, HEIGHT, SQUARE_SIZE, GIMMICK_ROW_HEIGHT, BOARD_OFFSET_X, BOARD_OFFSET_Y = calculate_layout(True)
                    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.FULLSCREEN)
                else:
                    # ウィンドウモードへ戻す際は直近のウィンドウサイズを保持
                    try:
                        WINDOW_WIDTH, WINDOW_HEIGHT, WIDTH, HEIGHT, SQUARE_SIZE, GIMMICK_ROW_HEIGHT, BOARD_OFFSET_X, BOARD_OFFSET_Y = calculate_layout(False, WINDOW_WIDTH, WINDOW_HEIGHT)
                    except Exception:
                        WINDOW_WIDTH, WINDOW_HEIGHT, WIDTH, HEIGHT, SQUARE_SIZE, GIMMICK_ROW_HEIGHT, BOARD_OFFSET_X, BOARD_OFFSET_Y = calculate_layout(False)
                    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)

                if hasattr(draw_board, "font_cache"):
                    draw_board.font_cache.clear()

            # Ctrl+M で最小化
            elif event.key == pygame.K_m and (mods & pygame.KMOD_CTRL):
                try:
                    pygame.display.iconify()
                except Exception:
                    pass

            # Alt+F4 または Ctrl+Q で終了
            elif (event.key == pygame.K_F4 and (mods & pygame.KMOD_ALT)) or (event.key == pygame.K_q and (mods & pygame.KMOD_CTRL)):
                running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if game_over:
                continue
            row, col = get_clicked_pos(pygame.mouse.get_pos())
            clicked = get_piece_at(row, col, pieces)
            # ギミックのアイコンをクリックしたかチェック
            try:
                if hasattr(draw_board, 'player_gimmick_click_areas'):
                    mx, my = pygame.mouse.get_pos()
                    for name, rect in draw_board.player_gimmick_click_areas:
                        if rect.collidepoint((mx, my)):
                            # '2' のギミックがクリックされたら右上カードを差し替える
                            # map gimmick names to image paths
                            if name == '2':
                                draw_board.current_card_path = 'images/m9(^Д^)/card_TEST_D2_2.png'
                            elif name == 'e':
                                draw_board.current_card_path = 'images/m9(^Д^)/card_test_r.png'
                            elif name == 'ボ収':
                                draw_board.current_card_path = 'images/m9(^Д^)/dummy_card_a.png'
                            elif name == '２回復':
                                draw_board.current_card_path = 'images/m9(^Д^)/card_TEST_S.png'
                            elif name == '炎':
                                draw_board.current_card_path = 'images/m9(^Д^)/dummy_card_t.png'
                            elif name == '氷':
                                draw_board.current_card_path = 'images/m9(^Д^)/dummy_card_m.png'
                            elif name == '雷':
                                draw_board.current_card_path = 'images/m9(^Д^)/dummy_card_c.png'
                            elif name == '風':
                                draw_board.current_card_path = 'images/m9(^Д^)/dummy_card_i.png'
                            else:
                                # 他のギミックは未対応（何もせず継続）
                                continue
                            # キャッシュをクリアして即時反映
                            if hasattr(draw_board, 'card_img_cache'):
                                draw_board.card_img_cache.clear()
                            print('DEBUG: Gimmick clicked, set current_card_path ->', draw_board.current_card_path)
                            break
            except Exception:
                pass

            if selected_piece:
                valid_moves = selected_piece.get_valid_moves(pieces)
                if (row, col) in valid_moves:
                    # --- キャスリング処理 ---
                    if selected_piece.name == 'K' and abs(col - selected_piece.col) == 2:
                        # kingside
                        if col == 6:
                            rook = get_piece_at(selected_piece.row, 7, pieces)
                            if rook:
                                rook.col = 5
                                rook.has_moved = True
                        # queenside
                        elif col == 2:
                            rook = get_piece_at(selected_piece.row, 0, pieces)
                            if rook:
                                rook.col = 3
                                rook.has_moved = True
                        # キングのhas_movedも必ずTrueに
                        selected_piece.has_moved = True
                    else:
                        # 通常移動時もhas_movedをTrueに
                        selected_piece.has_moved = True
                    # --- アンパサン処理 ---
                    if selected_piece.name == 'P' and en_passant_target is not None:
                        if (row, col) == en_passant_target:
                            # 取られる側のポーンを消す
                            dir = -1 if selected_piece.color == 'white' else 1
                            captured_row = row + (1 if selected_piece.color == 'white' else -1)
                            captured = get_piece_at(captured_row, col, pieces)
                            if captured and captured.name == 'P' and captured.color != selected_piece.color:
                                pieces.remove(captured)
                    target = get_piece_at(row, col, pieces)
                    if target:
                        pieces.remove(target)
                    # --- アンパサンターゲットの更新 ---
                    # ポーンが2マス進んだ場合のみセット
                    if selected_piece.name == 'P' and abs(row - selected_piece.row) == 2:
                        en_passant_target = ((selected_piece.row + row) // 2, col)
                    else:
                        en_passant_target = None
                    selected_piece.row, selected_piece.col = row, col

                    # --- 勝利判定をプロモーションより先に ---
                    white_king = any(p.name == 'K' and p.color == 'white' for p in pieces)
                    black_king = any(p.name == 'K' and p.color == 'black' for p in pieces)
                    if not white_king:
                        game_over = True
                        game_over_winner = 'black'
                    elif not black_king:
                        game_over = True
                        game_over_winner = 'white'

                    # ポーンのプロモーション処理（通常の駒のみ）
                    if not game_over and selected_piece and selected_piece.name == 'P':
                        if (selected_piece.color == 'white' and selected_piece.row == 0) or \
                           (selected_piece.color == 'black' and selected_piece.row == 7):
                            promoted = show_promotion_menu_with_images(screen, selected_piece.color)
                            selected_piece.name = promoted
                    selected_piece.has_moved = True

                    current_turn = 'black' if current_turn == 'white' else 'white'
                    # ターン切り替え時にイベントを発火（50ms後に処理）
                    pygame.time.set_timer(TURN_CHANGE_EVENT, 50, loops=1)
                selected_piece = None
            else:
                if clicked and clicked.color == current_turn:
                    selected_piece = clicked

        elif event.type == TURN_CHANGE_EVENT:
            # ターン切り替え後の処理をここで実行
            check_state = is_in_check(pieces, current_turn)
            # チェックメイト時のみ勝利判定
            if any(p.name == 'K' and p.color == current_turn for p in pieces):
                if check_state and not has_legal_moves(pieces, current_turn):
                    game_over = True
                    game_over_winner = 'white' if current_turn == 'black' else 'black'

                    if selected_piece.name == 'P':
                        if (selected_piece.color == 'white' and selected_piece.row == 0) or \
                            (selected_piece.color == 'black' and selected_piece.row == 7):
                            promoted = show_promotion_menu_with_images(screen, selected_piece.color)
                            selected_piece.name = promoted
                    selected_piece.has_moved = True
                    current_turn = 'black' if current_turn == 'white' else 'white'
                    check_state = is_in_check(pieces, current_turn)
                    if check_state and not has_legal_moves(pieces, current_turn):
                        game_over = True
                        game_over_winner = 'white' if current_turn == 'black' else 'black'
                    # プレイヤー操作後にCPU待機フラグをセット
                    if current_turn == 'black' and not game_over:
                        cpu_wait = True
                        cpu_wait_start = time.time()
                selected_piece = None

    # 黒の手番なら0.5秒待ってからAIで指す
    if current_turn == 'black' and not game_over:
        if 'cpu_wait' in globals() and cpu_wait:
            if time.time() - cpu_wait_start >= 1.0:
                # cpu_make_move関数が必要です。未定義の場合は定義してください。
                cpu_make_move(
                    pieces,
                    get_piece_at,
                    is_in_check,
                    has_legal_moves,
                    show_promotion_menu_with_images,
                    globals(),
                    Piece.get_valid_moves  # get_valid_movesをAI.pyに渡す
                )
                cpu_wait = False
        else:
            # 既存のAI自動指し手処理
            ai_result = ai_move(pieces)
            if ai_result:
                from_row = ai_result['from_row']
                from_col = ai_result['from_col']
                to_row = ai_result['to_row']
                to_col = ai_result['to_col']
                piece = get_piece_at(from_row, from_col, pieces)
                if piece:
                    # 移動先に駒がいれば取る
                    target = get_piece_at(to_row, to_col, pieces)
                    if target:
                        pieces.remove(target)
                    piece.row, piece.col = to_row, to_col
                    piece.has_moved = True

                    # ポーンのプロモーション
                    if piece.name == 'P' and piece.row == 7:
                        piece.name = 'Q'
                    current_turn = 'white'
                    # ターン切り替え時にイベントを発火（50ms後に処理）
                    pygame.time.set_timer(TURN_CHANGE_EVENT, 50, loops=1)
            continue

pygame.quit()
sys.exit()