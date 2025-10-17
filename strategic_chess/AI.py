import sys
import random
import json
import time  # 追加

# AIの難易度設定
# 1: Easy (完全ランダム)
# 2: Medium (チェック回避のみ)
# 3: Hard (評価関数による最善手選択)
# 4: Expert (2手先読み + 高度な評価関数)
AI_DIFFICULTY = 2  # デフォルトは Medium

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

def evaluate_board(pieces):
    """
    盤面の評価値を計算（黒視点、高いほど黒有利）
    """
    piece_values = {
        'P': 1,    # ポーン
        'N': 3,    # ナイト
        'B': 3,    # ビショップ
        'R': 5,    # ルーク
        'Q': 9,    # クイーン
        'K': 0     # キング（価値は無限大だが評価には含めない）
    }
    
    score = 0
    for p in pieces:
        value = piece_values.get(p['name'], 0)
        if p['color'] == 'black':
            score += value
        else:
            score -= value
    return score

def evaluate_board_advanced(pieces):
    """
    高度な評価関数（Expert難易度用）
    駒の価値 + 位置ボーナス + モビリティ（動ける手の数）を考慮
    """
    piece_values = {
        'P': 1,
        'N': 3,
        'B': 3,
        'R': 5,
        'Q': 9,
        'K': 0
    }
    
    # 中央制御ボーナステーブル（中央に近いほど高い）
    center_bonus = [
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 1, 1, 1, 1, 1, 1, 0],
        [0, 1, 2, 2, 2, 2, 1, 0],
        [0, 1, 2, 3, 3, 2, 1, 0],
        [0, 1, 2, 3, 3, 2, 1, 0],
        [0, 1, 2, 2, 2, 2, 1, 0],
        [0, 1, 1, 1, 1, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0]
    ]
    
    score = 0
    black_mobility = 0
    white_mobility = 0
    
    for p in pieces:
        # 駒の基本価値
        value = piece_values.get(p['name'], 0)
        
        # 位置ボーナス（ナイト、ビショップ、ポーンに適用）
        position_bonus = 0
        if p['name'] in ['N', 'B', 'P']:
            position_bonus = center_bonus[p['row']][p['col']] * 0.1
        
        # モビリティ（動ける手の数）
        mobility = len(get_valid_moves(p, pieces))
        
        if p['color'] == 'black':
            score += value + position_bonus
            black_mobility += mobility
        else:
            score -= (value + position_bonus)
            white_mobility += mobility
    
    # モビリティボーナス
    mobility_score = (black_mobility - white_mobility) * 0.05
    score += mobility_score
    
    # キングの安全性チェック
    if is_in_check(pieces, 'black'):
        score -= 2  # チェックされているとペナルティ
    if is_in_check(pieces, 'white'):
        score += 2  # 相手をチェックしているとボーナス
    
    return score

def get_best_move(pieces, legal_moves, safe_moves):
    """
    評価関数を使って最善手を選択（Hard難易度用）
    """
    best_score = float('-inf')
    best_moves = []
    
    # 安全な手がある場合はその中から、なければ合法手から選ぶ
    moves_to_evaluate = safe_moves if safe_moves else legal_moves
    
    for move_dict in moves_to_evaluate:
        # 元の駒を見つける
        piece = None
        for p in pieces:
            if p['row'] == move_dict['from_row'] and p['col'] == move_dict['from_col'] and p['name'] == move_dict['name']:
                piece = p
                break
        
        if piece:
            # この手を指した後の盤面を評価
            new_pieces = make_move_and_update(piece, (move_dict['to_row'], move_dict['to_col']), pieces)
            score = evaluate_board(new_pieces)
            
            # 駒を取る手にボーナス
            is_capture = any(p['row'] == move_dict['to_row'] and p['col'] == move_dict['to_col'] 
                           for p in pieces if p['color'] == 'white')
            if is_capture:
                score += 0.5
            
            if score > best_score:
                best_score = score
                best_moves = [move_dict]
            elif score == best_score:
                best_moves.append(move_dict)
    
    return random.choice(best_moves) if best_moves else None

def minimax_evaluation(pieces, depth, maximizing_player, alpha, beta):
    """
    ミニマックス法による評価（Expert難易度用）
    alphaベータ枝刈りを使用して効率化
    """
    # 深さ0または終局状態なら評価値を返す
    if depth == 0:
        return evaluate_board_advanced(pieces)
    
    if maximizing_player:  # 黒（AI）のターン
        max_eval = float('-inf')
        for piece in pieces:
            if piece['color'] == 'black':
                for move in get_valid_moves(piece, pieces):
                    new_pieces = make_move_and_update(piece, move, pieces)
                    # チェックで自滅する手は除外
                    if is_in_check(new_pieces, 'black'):
                        continue
                    eval_score = minimax_evaluation(new_pieces, depth - 1, False, alpha, beta)
                    max_eval = max(max_eval, eval_score)
                    alpha = max(alpha, eval_score)
                    if beta <= alpha:
                        break  # ベータカット
                if beta <= alpha:
                    break
        return max_eval if max_eval != float('-inf') else evaluate_board_advanced(pieces)
    else:  # 白（相手）のターン
        min_eval = float('inf')
        for piece in pieces:
            if piece['color'] == 'white':
                for move in get_valid_moves(piece, pieces):
                    new_pieces = make_move_and_update(piece, move, pieces)
                    if is_in_check(new_pieces, 'white'):
                        continue
                    eval_score = minimax_evaluation(new_pieces, depth - 1, True, alpha, beta)
                    min_eval = min(min_eval, eval_score)
                    beta = min(beta, eval_score)
                    if beta <= alpha:
                        break  # アルファカット
                if beta <= alpha:
                    break
        return min_eval if min_eval != float('inf') else evaluate_board_advanced(pieces)

def get_expert_move(pieces, legal_moves, safe_moves):
    """
    ミニマックス法で最善手を選択（Expert難易度用）
    2手先まで読む
    """
    best_score = float('-inf')
    best_moves = []
    
    # 安全な手がある場合はその中から、なければ合法手から選ぶ
    moves_to_evaluate = safe_moves if safe_moves else legal_moves
    
    for move_dict in moves_to_evaluate:
        # 元の駒を見つける
        piece = None
        for p in pieces:
            if p['row'] == move_dict['from_row'] and p['col'] == move_dict['from_col'] and p['name'] == move_dict['name']:
                piece = p
                break
        
        if piece:
            # この手を指した後の盤面を2手先まで読んで評価
            new_pieces = make_move_and_update(piece, (move_dict['to_row'], move_dict['to_col']), pieces)
            # 深さ2でミニマックス探索（2手先まで読む）
            score = minimax_evaluation(new_pieces, 2, False, float('-inf'), float('inf'))
            
            if score > best_score:
                best_score = score
                best_moves = [move_dict]
            elif score == best_score:
                best_moves.append(move_dict)
    
    return random.choice(best_moves) if best_moves else None

def main():
    # 標準入力から盤面情報を受け取る
    board_json = sys.stdin.readline()
    time.sleep(0.5)  # 0.5秒待つ

    # --- main.pyからの新しい入力形式に対応 ---
    data = json.loads(board_json)
    if isinstance(data, dict) and "pieces" in data:
        pieces = data["pieces"]
        black_in_check = data.get("black_in_check", False)
        # 難易度設定を受け取る（指定がなければデフォルト値を使用）
        difficulty = data.get("difficulty", AI_DIFFICULTY)
    else:
        pieces = data
        black_in_check = is_in_check(pieces, 'black')
        difficulty = AI_DIFFICULTY

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
    
    # 難易度に応じて手を選択
    move = None
    
    if difficulty == 1:  # Easy: 完全ランダム
        if legal_moves:
            move = random.choice(legal_moves)
    
    elif difficulty == 2:  # Medium: チェック回避のみ考慮
        # チェック中ならsafe_movesから選ぶ。なければlegal_movesから選ぶ
        if black_in_check and safe_moves:
            move = random.choice(safe_moves)
        elif black_in_check and legal_moves:
            # チェック中でsafe_movesがない場合、詰みなのでランダム
            move = random.choice(legal_moves)
        elif legal_moves:
            move = random.choice(legal_moves)
    
    elif difficulty == 3:  # Hard: 評価関数による最善手選択
        if black_in_check and safe_moves:
            # チェック中は安全な手の中から最善手を選ぶ
            move = get_best_move(pieces, legal_moves, safe_moves)
        elif black_in_check and legal_moves:
            # 詰みの場合はランダム
            move = random.choice(legal_moves)
        elif legal_moves:
            # 通常時は評価関数で最善手を選ぶ
            move = get_best_move(pieces, legal_moves, safe_moves)
    
    elif difficulty == 4:  # Expert: 2手先読み + 高度な評価関数
        if black_in_check and safe_moves:
            # チェック中は安全な手の中からミニマックスで最善手を選ぶ
            move = get_expert_move(pieces, legal_moves, safe_moves)
        elif black_in_check and legal_moves:
            # 詰みの場合はランダム
            move = random.choice(legal_moves)
        elif legal_moves:
            # 通常時はミニマックス法で最善手を選ぶ
            move = get_expert_move(pieces, legal_moves, safe_moves)
    
    else:  # 不正な難易度の場合はMediumとして動作
        if black_in_check and safe_moves:
            move = random.choice(safe_moves)
        elif legal_moves:
            move = random.choice(legal_moves)
    
    print(json.dumps(move))
    sys.stdout.flush()

if __name__ == "__main__":
    main()
