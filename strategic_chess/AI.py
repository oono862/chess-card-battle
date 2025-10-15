import sys
import random
import json
import time  # 追加

def get_valid_moves(piece, pieces, ROWS=8, COLS=8):
    # piece: dict, pieces: list of dict
    moves = []
    def is_occupied(row, col, same_color=None):
        for p in pieces:
            if p['row'] == row and p['col'] == col:
                if same_color is None:
                    return True
                if (p['color'] == piece['color']) == same_color:
                    return True
        return False

    def add_direction(dr, dc, max_steps=8):
        for step in range(1, max_steps + 1):
            nr, nc = piece['row'] + dr * step, piece['col'] + dc * step
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                if is_occupied(nr, nc, same_color=True):
                    break
                moves.append((nr, nc))
                if is_occupied(nr, nc, same_color=False):
                    break
            else:
                break

    name = piece['name']
    if name == 'K':
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr != 0 or dc != 0:
                    nr, nc = piece['row'] + dr, piece['col'] + dc
                    if 0 <= nr < ROWS and 0 <= nc < COLS and not is_occupied(nr, nc, same_color=True):
                        moves.append((nr, nc))
    elif name == 'Q':
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1), (-1,-1), (-1,1), (1,-1), (1,1)]:
            add_direction(dr, dc)
    elif name == 'B':
        for dr, dc in [(-1,-1), (-1,1), (1,-1), (1,1)]:
            add_direction(dr, dc)
    elif name == 'R':
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            add_direction(dr, dc)
    elif name == 'N':
        for dr, dc in [(2,1), (1,2), (-1,2), (-2,1), (-2,-1), (-1,-2), (1,-2), (2,-1)]:
            nr, nc = piece['row'] + dr, piece['col'] + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and not is_occupied(nr, nc, same_color=True):
                moves.append((nr, nc))
    elif name == 'P':
        dir = 1
        start_row = 1
        if not is_occupied(piece['row'] + dir, piece['col']):
            moves.append((piece['row'] + dir, piece['col']))
            if piece['row'] == start_row and not is_occupied(piece['row'] + 2 * dir, piece['col']):
                moves.append((piece['row'] + 2 * dir, piece['col']))
        for dc in [-1, 1]:
            nr, nc = piece['row'] + dir, piece['col'] + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and is_occupied(nr, nc, same_color=False):
                moves.append((nr, nc))
    return moves

def is_in_check(pieces, color):
    king = None
    for p in pieces:
        if p['name'] == 'K' and p['color'] == color:
            king = p
            break
    if not king:
        return False  # キングがいない場合はチェックでない
    king_pos = (king['row'], king['col'])
    opponent_color = 'white' if color == 'black' else 'black'
    for p in pieces:
        if p['color'] == opponent_color:
            moves = get_valid_moves(p, pieces)
            if king_pos in moves:
                return True
    return False

def make_move_and_update(piece, move, pieces):
    # pieces: list of dict, piece: dict, move: (row, col)
    # 新しい盤面リストを返す（ディープコピー）
    new_pieces = []
    for p in pieces:
        # 厳密な一致判定
        if (p['row'], p['col'], p['name'], p['color']) == (piece['row'], piece['col'], piece['name'], piece['color']):
            continue
        if (p['row'], p['col']) == (move[0], move[1]):
            continue  # 取られる駒は除外
        new_pieces.append(dict(p))
    moved = dict(piece)
    moved['row'] = move[0]
    moved['col'] = move[1]
    new_pieces.append(moved)
    return new_pieces

def main():
    # 標準入力から盤面情報を受け取る
    board_json = sys.stdin.readline()
    time.sleep(0.5)  # 0.5秒待つ

    # --- main.pyからの新しい入力形式に対応 ---
    data = json.loads(board_json)
    if isinstance(data, dict) and "pieces" in data:
        pieces = data["pieces"]
        black_in_check = data.get("black_in_check", False)
    else:
        pieces = data
        black_in_check = is_in_check(pieces, 'black')

    legal_moves = []
    safe_moves = []
    for piece in pieces:
        if piece['color'] == 'black':
            for move in get_valid_moves(piece, pieces):
                move_dict = {
                    'from_row': piece['row'],
                    'from_col': piece['col'],
                    'to_row': move[0],
                    'to_col': move[1],
                    'name': piece['name']
                }
                legal_moves.append(move_dict)
                # チェック回避判定
                new_pieces = make_move_and_update(piece, move, pieces)
                # ここで新しい盤面で黒キングが攻撃されていないか判定
                if not is_in_check(new_pieces, 'black'):
                    safe_moves.append(move_dict)
    # チェック中ならsafe_movesから選ぶ。なければlegal_movesから選ぶ
    if black_in_check and safe_moves:
        move = random.choice(safe_moves)
    elif black_in_check and legal_moves:
        # チェック中でsafe_movesがない場合、詰みなのでランダム
        move = random.choice(legal_moves)
    elif legal_moves:
        move = random.choice(legal_moves)
    else:
        move = None
    print(json.dumps(move))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
