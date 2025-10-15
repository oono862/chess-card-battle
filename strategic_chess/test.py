import pygame
import sys
from gimmick import get_gimmick_list, FireGimmick, IceGimmick, ThunderGimmick, WindGimmick
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

# チェス盤サイズ
WIDTH = 640
HEIGHT = 640
SQUARE_SIZE = WIDTH // 8
GIMMICK_COL_WIDTH = 60  # ギミック枠の幅（狭くする）
BOARD_OFFSET_X = GIMMICK_COL_WIDTH  # 盤面の左端オフセット
BOARD_OFFSET_Y = 0  # 必要なら上下も調整

# ウィンドウサイズをギミック枠分広げる
WINDOW_WIDTH = WIDTH + GIMMICK_COL_WIDTH * 2
WINDOW_HEIGHT = HEIGHT

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("チェスエレメント")

font = pygame.font.SysFont("Noto_SansJP", 32)


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
    # options: 常に['Q', 'R', 'B', 'N'] + ギミック名
    normal_options = ['Q', 'R', 'B', 'N']
    gimmick_options = [g.name for g in gimmicks]
    selected = None

    # サイズ・配置設定
    normal_img_size = 100
    normal_spacing = 40
    gimmick_img_size = 60
    gimmick_spacing = 30

    # 上段（通常駒）の配置
    total_normal_width = len(normal_options) * normal_img_size + (len(normal_options) - 1) * normal_spacing
    normal_start_x = (WINDOW_WIDTH - total_normal_width) // 2
    normal_y = HEIGHT // 2 - 80

    # 下段（ギミック）の配置
    total_gimmick_width = len(gimmick_options) * gimmick_img_size + (len(gimmick_options) - 1) * gimmick_spacing
    gimmick_start_x = (WINDOW_WIDTH - total_gimmick_width) // 2
    gimmick_y = HEIGHT // 2 + 40

    while selected is None:
        screen.fill((220, 220, 220))
        title_font = pygame.font.SysFont("Noto_SansJP", 36)
        text = title_font.render("昇格する駒またはギミックを選択", True, (0, 0, 0))
        screen.blit(text, (WIDTH // 2 - text.get_width() // 2, 50))

        positions = []

        # 上段：通常駒
        for i, opt in enumerate(normal_options):
            x = normal_start_x + i * (normal_img_size + normal_spacing)
            img = pygame.transform.scale(promotion_images[piece_color][opt], (normal_img_size, normal_img_size))
            screen.blit(img, (x, normal_y))
            positions.append((x, x + normal_img_size, normal_y, normal_y + normal_img_size, opt))

        # 下段：ギミック
        for i, opt in enumerate(gimmick_options):
            x = gimmick_start_x + i * (gimmick_img_size + gimmick_spacing)
            pygame.draw.rect(screen, GOLD, (x, gimmick_y, gimmick_img_size, gimmick_img_size))
            gimmick_font = pygame.font.SysFont("Noto_SansJP", 24)
            gimmick_text = gimmick_font.render(opt, True, (0, 0, 0))
            screen.blit(gimmick_text, (x + (gimmick_img_size - gimmick_text.get_width()) // 2, gimmick_y + (gimmick_img_size - gimmick_text.get_height()) // 2))
            # --- ギミック個数表示（プレイヤー用のみ） ---
            count = player_gimmick_counts.get(opt, 0)
            count_font = pygame.font.SysFont("Noto_SansJP", 18)
            count_text = count_font.render(f"x{count}", True, (0, 0, 0))
            screen.blit(count_text, (x + gimmick_img_size - count_text.get_width() - 4, gimmick_y + gimmick_img_size - count_text.get_height() - 2))
            positions.append((x, x + gimmick_img_size, gimmick_y, gimmick_y + gimmick_img_size, opt))

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

class Piece:
    def __init__(self, row, col, name, color):
        self.row = row
        self.col = col
        self.name = name
        self.color = color
        self.has_moved = False
        # HPの初期化はここで一度だけ
        hp_table =  {'P': 20, 'N': 30, 'B': 25, 'R': 35, 'Q': 40, 'K': 50}    # HPテーブル
        attack_table = {'P': 5, 'N': 16, 'B': 10, 'R': 15, 'Q': 8, 'K': 9}  # 攻撃力テーブル
        self.max_hp = hp_table[self.name]
        self.hp = self.max_hp
        self.attack = attack_table[self.name]
        self.gimmick = None  # ギミック取得用

    def draw(self, surface):
        # オフセットを考慮して描画
        x = BOARD_OFFSET_X + self.col * SQUARE_SIZE
        y = BOARD_OFFSET_Y + self.row * SQUARE_SIZE
        img = piece_images[self.color][self.name]
        img = pygame.transform.scale(img, (SQUARE_SIZE, SQUARE_SIZE))
        surface.blit(img, (x, y))

        # HPバーの描写
        bar_height = 4
        bar_margin = 6
        bar_y = y + SQUARE_SIZE - bar_height - bar_margin
        bar_x = x + 4
        bar_width = SQUARE_SIZE - 8

        # 1. 黒い外枠
        pygame.draw.rect(surface, (0, 0, 0), (bar_x - 1, bar_y - 1, bar_width + 2, bar_height + 2), 1)

        # 2. 赤い背景
        pygame.draw.rect(surface, (RED), (bar_x, bar_y, bar_width, bar_height))
        # 緑のHP
        hp_width = int((self.hp / self.max_hp) * bar_width)
        pygame.draw.rect(surface, (GREEN), (bar_x, bar_y, hp_width, bar_height))

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
    # 盤面をオフセット位置から描画
    for row in range(8):
        for col in range(8):
            color = WHITE if (row + col) % 2 == 0 else GRAY
            pygame.draw.rect(
                screen, color,
                (BOARD_OFFSET_X + col * SQUARE_SIZE, BOARD_OFFSET_Y + row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
            )
    # ギミック枠（盤面の外側）
    # --- 事前にフォント・サーフェスをキャッシュ ---
    if not hasattr(draw_board, "font_cache"):
        draw_board.font_cache = {}
    font_cache = draw_board.font_cache

    def get_font(size):
        key = ("Noto_SansJP", size)
        if key not in font_cache:
            font_cache[key] = pygame.font.SysFont("Noto_SansJP", size)
        return font_cache[key]

    for row in range(8):
        pygame.draw.rect(screen, GOLD, (0, BOARD_OFFSET_Y + row * SQUARE_SIZE, GIMMICK_COL_WIDTH, SQUARE_SIZE))
        SILVER = (192, 192, 192)
        pygame.draw.rect(screen, SILVER, (WINDOW_WIDTH - GIMMICK_COL_WIDTH, BOARD_OFFSET_Y + row * SQUARE_SIZE, GIMMICK_COL_WIDTH, SQUARE_SIZE))
        if row < len(gimmicks):
            gimmick_name = gimmicks[row].name
            count_player = player_gimmick_counts.get(gimmick_name, 0)
            count_cpu = cpu_gimmick_counts.get(gimmick_name, 0)
            # --- 円形をやや小さく ---
            circle_radius = 20
            # --- 左側（プレイヤー用） ---
            circle_center_left = (GIMMICK_COL_WIDTH // 2 - 2, BOARD_OFFSET_Y + row * SQUARE_SIZE + SQUARE_SIZE // 2)
            pygame.draw.circle(screen, GOLD, circle_center_left, circle_radius)
            pygame.draw.circle(screen, BLACK, circle_center_left, circle_radius, 2)
            text_font = get_font(18)
            count_font = get_font(16)
            x_font = get_font(16)
            # --- サーフェスもキャッシュ ---
            cache_key = (gimmick_name, "left")
            if cache_key not in font_cache:
                gimmick_text_surface = text_font.render(gimmick_name, True, BLACK)
                x_surface = x_font.render("×", True, BLACK)
                font_cache[cache_key] = (gimmick_text_surface, x_surface)
            else:
                gimmick_text_surface, x_surface = font_cache[cache_key]
            gimmick_text_rect = gimmick_text_surface.get_rect(center=circle_center_left)
            screen.blit(gimmick_text_surface, gimmick_text_rect)
            count_surface = count_font.render(str(count_player), True, BLACK)
            x_rect = x_surface.get_rect()
            count_rect = count_surface.get_rect()
            right_of_circle = circle_center_left[0] + circle_radius - 26
            below_circle = circle_center_left[1] + circle_radius - 4
            x_rect.topleft = (right_of_circle, below_circle)
            count_rect.topleft = (x_rect.right + 2, below_circle)
            screen.blit(x_surface, x_rect)
            screen.blit(count_surface, count_rect)
            # --- 右側（CPU用） ---
            circle_center_right = (WINDOW_WIDTH - GIMMICK_COL_WIDTH // 2 + 2, BOARD_OFFSET_Y + row * SQUARE_SIZE + SQUARE_SIZE // 2)
            pygame.draw.circle(screen, SILVER, circle_center_right, circle_radius)
            pygame.draw.circle(screen, BLACK, circle_center_right, circle_radius, 2)
            cache_key = (gimmick_name, "right")
            if cache_key not in font_cache:
                gimmick_text_surface = text_font.render(gimmick_name, True, BLACK)
                x_surface = x_font.render("×", True, BLACK)
                font_cache[cache_key] = (gimmick_text_surface, x_surface)
            else:
                gimmick_text_surface, x_surface = font_cache[cache_key]
            gimmick_text_rect = gimmick_text_surface.get_rect(center=circle_center_right)
            screen.blit(gimmick_text_surface, gimmick_text_rect)
            count_surface = count_font.render(str(count_cpu), True, BLACK)
            x_rect = x_surface.get_rect()
            count_rect = count_surface.get_rect()
            right_of_circle = circle_center_right[0] + circle_radius - 26
            below_circle = circle_center_right[1] + circle_radius - 4
            x_rect.topleft = (right_of_circle, below_circle)
            count_rect.topleft = (x_rect.right + 2, below_circle)
            screen.blit(x_surface, x_rect)
            screen.blit(count_surface, count_rect)
    if game_over:
        end_text = f"{game_over_winner.upper()} の勝利！ チェックメイト"
        text = font.render(end_text, True, RED)
        rect = text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2))
        screen.blit(text, rect)

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

def attack_facing_enemy(moved_piece, pieces):
    """
    移動後に「その駒の動ける範囲」かつ「移動先から半径1マス以内」にいる敵駒すべてに
    移動駒の攻撃力分ダメージを与える（自分自身は除外）
    ポーンはさらに前方1マスも攻撃範囲に含める
    """
    if moved_piece is None:
        return
    # 1. 動ける範囲を取得
    valid_moves = set(moved_piece.get_valid_moves(pieces))
    # 2. 半径1マス以内のマスを取得
    area = set()
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            nr, nc = moved_piece.row + dr, moved_piece.col + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                area.add((nr, nc))
    # 3. ポーンの場合は前方1マスも追加（すでに含まれていなければ）
    if moved_piece.name == 'P':
        dir = -1 if moved_piece.color == 'white' else 1
        nr, nc = moved_piece.row + dir, moved_piece.col
        if 0 <= nr < 8 and 0 <= nc < 8:
            area.add((nr, nc))
    # 4. 両方に含まれるマスだけ攻撃
    targets = valid_moves & area
    # ポーンの場合は前方1マスも攻撃対象に追加
    if moved_piece.name == 'P':
        dir = -1 if moved_piece.color == 'white' else 1
        nr, nc = moved_piece.row + dir, moved_piece.col
        if 0 <= nr < 8 and 0 <= nc < 8:
            targets.add((nr, nc))
    for nr, nc in targets:
        target = get_piece_at(nr, nc, pieces)
        if target and target.color != moved_piece.color:
            target.hp -= moved_piece.attack
            if target.hp <= 0:
                pieces.remove(target)

cpu_wait = False
cpu_wait_start = 0

while running:
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
            # 表示
            for idx, color in enumerate(draw_board.last_check_colors):
                msg = f"{'白' if color == 'white' else '黒'}チェック中"
                check_text = font.render(msg, True, (255, 165, 0))
                screen.blit(check_text, (20, 20 + idx * 40))

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

    # ゲーム終了時はウィンドウを閉じるまでループ
    if game_over:
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
            draw_board()
            for piece in pieces:
                piece.draw(screen)
            pygame.display.flip()
        break  # while running を抜けて終了処理へ

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if game_over:
                continue
            row, col = get_clicked_pos(pygame.mouse.get_pos())
            clicked = get_piece_at(row, col, pieces)

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

                    # --- 攻撃処理をここで呼び出し（昇格前） ---
                    attack_facing_enemy(selected_piece, pieces)

                    # --- 勝利判定をプロモーションより先に ---
                    white_king = any(p.name == 'K' and p.color == 'white' for p in pieces)
                    black_king = any(p.name == 'K' and p.color == 'black' for p in pieces)
                    if not white_king:
                        game_over = True
                        game_over_winner = 'black'
                    elif not black_king:
                        game_over = True
                        game_over_winner = 'white'

                    # ポーンのプロモーション処理（UIあり＋ギミック対応）
                    if not game_over and selected_piece and selected_piece.name == 'P':
                        if (selected_piece.color == 'white' and selected_piece.row == 0) or \
                           (selected_piece.color == 'black' and selected_piece.row == 7):
                            promoted = show_promotion_menu_with_images(screen, selected_piece.color)
                            if promoted in promotion_images[selected_piece.color]:
                                # --- HP回復処理 ---
                                old_max_hp = selected_piece.max_hp
                                selected_piece.name = promoted
                                # 新しい最大HPを設定
                                hp_table =  {'P': 20, 'N': 30, 'B': 25, 'R': 35, 'Q': 40, 'K': 50}
                                selected_piece.max_hp = hp_table[selected_piece.name]
                                # HP回復（増加分だけ回復、最大値を超えない）
                                selected_piece.hp = min(selected_piece.hp + (selected_piece.max_hp - old_max_hp), selected_piece.max_hp)
                                # 攻撃力も更新
                                attack_table = {'P': 5, 'N': 16, 'B': 10, 'R': 15, 'Q': 8, 'K': 9}
                                selected_piece.attack = attack_table[selected_piece.name]
                            else:
                                # ギミックを取得し、その場で待機（昇格しない）
                                selected_piece.gimmick = promoted
                                # --- ギミック個数を増やす（プレイヤー用のみ） ---
                                if promoted in player_gimmick_counts:
                                    player_gimmick_counts[promoted] += 1
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

                    # 向かい合い攻撃処理
                    attack_facing_enemy(selected_piece, pieces)
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
                    attack_facing_enemy,
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

                    # --- AI移動後にも攻撃処理を呼び出し ---
                    attack_facing_enemy(piece, pieces)

                    # ポーンのプロモーション
                    if piece.name == 'P' and piece.row == 7:
                        piece.name = 'Q'
                    current_turn = 'white'
                    # ターン切り替え時にイベントを発火（50ms後に処理）
                    pygame.time.set_timer(TURN_CHANGE_EVENT, 50, loops=1)
            continue

pygame.quit()
sys.exit()

def cpu_make_move(
    pieces,
    get_piece_at,
    attack_facing_enemy,
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

            # 攻撃処理
            attack_facing_enemy(piece, pieces)

            # ポーンのプロモーション
            if piece.name == 'P' and piece.row == 7:
                # プロモーションUIを使わず自動でクイーンに昇格
                old_max_hp = piece.max_hp
                piece.name = 'Q'
                hp_table =  {'P': 20, 'N': 30, 'B': 25, 'R': 35, 'Q': 40, 'K': 50}
                piece.max_hp = hp_table[piece.name]
                piece.hp = min(piece.hp + (piece.max_hp - old_max_hp), piece.max_hp)
                attack_table = {'P': 5, 'N': 16, 'B': 10, 'R': 15, 'Q': 8, 'K': 9}
                piece.attack = attack_table[piece.name]

            # ターン切り替え
            global_vars['current_turn'] = 'white'
            pygame.time.set_timer(global_vars['TURN_CHANGE_EVENT'], 50, loops=1)