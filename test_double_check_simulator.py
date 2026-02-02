"""
両チェック状態シミュレーター

両方の王が同時にチェック状態になっているシナリオを
実際のプレイのように再現・確認するツール
"""

import sys
import os
import importlib.util

# C.C.B モジュールの読み込み
base_path = os.path.dirname(os.path.abspath(__file__))
ccb_path = os.path.join(base_path, 'C.C.B')

# chess_engine.py をロード
chess_engine_path = os.path.join(ccb_path, 'chess_engine.py')
spec = importlib.util.spec_from_file_location("chess_engine", chess_engine_path)
chess_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chess_engine)

# Piece クラスはchess_engine内で定義されている
Piece = chess_engine.Piece

# rules.py をロード
rules_path = os.path.join(ccb_path, 'chess', 'rules.py')
spec = importlib.util.spec_from_file_location("rules", rules_path)
rules_module = importlib.util.module_from_spec(spec)
sys.modules['chess'] = importlib.util.find_spec('chess')  # プレースホルダー
spec.loader.exec_module(rules_module)
is_in_check_for_display = rules_module.is_in_check_for_display


def setup_double_check_scenario():
    """
    両チェック状態を設定
    
    例：
    - 白王：d4
    - 黒王：e5
    - 黒ルーク：d1（白王をチェック）
    - 白ルーク：e8（黒王をチェック）
    """
    chess_engine.pieces = []
    
    # 白の駒
    white_king = Piece(3, 3, 'K', 'white')  # d4
    white_king.has_moved = False
    chess_engine.pieces.append(white_king)
    
    white_rook = Piece(7, 4, 'R', 'white')  # e8
    white_rook.has_moved = True
    chess_engine.pieces.append(white_rook)
    
    # 黒の駒
    black_king = Piece(4, 4, 'K', 'black')  # e5
    black_king.has_moved = False
    chess_engine.pieces.append(black_king)
    
    black_rook = Piece(0, 3, 'R', 'black')  # d1
    black_rook.has_moved = True
    chess_engine.pieces.append(black_rook)
    
    return chess_engine.pieces


def display_board(pieces):
    """盤面を表示"""
    board = [['.' for _ in range(8)] for _ in range(8)]
    
    piece_symbols = {
        'K': {'white': 'K', 'black': 'k'},
        'Q': {'white': 'Q', 'black': 'q'},
        'R': {'white': 'R', 'black': 'r'},
        'B': {'white': 'B', 'black': 'b'},
        'N': {'white': 'N', 'black': 'n'},
        'P': {'white': 'P', 'black': 'p'},
    }
    
    for piece in pieces:
        symbol = piece_symbols.get(piece.name, {}).get(piece.color, '?')
        board[piece.row][piece.col] = symbol
    
    print("\n" + "=" * 40)
    print("       0   1   2   3   4   5   6   7")
    print("     " + "-" * 36)
    for row in range(8):
        row_str = f"  {row} | "
        row_str += " | ".join(board[row])
        row_str += " |"
        print(row_str)
    print("     " + "-" * 36)
    print("=" * 40)


def check_status(pieces):
    """チェック状態を確認して表示"""
    print("\n【チェック状態の確認】")
    
    white_in_check = is_in_check_for_display(pieces, 'white', chess_engine)
    black_in_check = is_in_check_for_display(pieces, 'black', chess_engine)
    
    print(f"白のチェック状態: {'✓ チェック中' if white_in_check else '✗ チェックなし'}")
    print(f"黒のチェック状態: {'✓ チェック中' if black_in_check else '✗ チェックなし'}")
    
    if white_in_check and black_in_check:
        print("\n🔴 【両チェック状態が検出されました】")
        return True
    elif white_in_check or black_in_check:
        print("\n🟡 【片方がチェック状態です】")
        return False
    else:
        print("\n🟢 【チェック状態ではありません】")
        return False


def display_piece_info(pieces):
    """駒情報を表示"""
    print("\n【駒配置情報】")
    print("-" * 50)
    
    col_names = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    piece_names = {'K': 'キング', 'Q': 'クイーン', 'R': 'ルーク', 
                   'B': 'ビショップ', 'N': 'ナイト', 'P': 'ポーン'}
    
    for piece in pieces:
        pos = f"{col_names[piece.col]}{8 - piece.row}"
        piece_name = piece_names.get(piece.name, piece.name)
        color = "白" if piece.color == 'white' else "黒"
        print(f"{color} {piece_name:8} {pos}")
    
    print("-" * 50)


def main():
    print("【チェスカードバトル - 両チェック状態シミュレーター】")
    print("\n初期盤面を設定中...")
    
    # 両チェック状態をセットアップ
    pieces = setup_double_check_scenario()
    
    # 盤面表示
    display_board(pieces)
    
    # 駒情報表示
    display_piece_info(pieces)
    
    # チェック状態確認
    is_double_check = check_status(pieces)
    
    print("\n【シミュレーション結果】")
    print("-" * 50)
    if is_double_check:
        print("✓ 両チェック状態が正常に検出されました")
        print("  このシナリオは通常チェスでは不正な盤面ですが、")
        print("  カード効果による特殊な状況として認識されています")
    else:
        print("✗ 両チェック状態が検出されませんでした")
    print("-" * 50)
    
    # 追加テスト：各駒の移動可能範囲確認
    print("\n【駒の移動可能範囲（例）】")
    white_king = pieces[0]
    valid_moves = white_king.get_valid_moves(pieces)
    if valid_moves:
        col_names = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        moves_str = ", ".join([f"{col_names[c]}{8-r}" for r, c in valid_moves])
        print(f"白キングの移動可能マス: {moves_str}")
    else:
        print(f"白キングの移動可能マス: なし（スタックメイト可能性）")


if __name__ == "__main__":
    main()
