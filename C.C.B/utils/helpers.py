"""ヘルパー関数群"""


def on_board(r, c):
    """盤面座標チェック: (r, c) が 8x8 ボード内にあるか判定"""
    return 0 <= r < 8 and 0 <= c < 8


def get_piece_at(row, col):
    """指定座標の駒を取得する（chess_engineへの薄いラッパー）"""
    try:
        # chess_engine モジュールを動的にインポート
        import sys
        if 'chess_engine' in sys.modules:
            chess = sys.modules['chess_engine']
        else:
            try:
                import chess_engine as chess
            except ImportError:
                return None
        return chess.get_piece_at(row, col)
    except Exception:
        return None


def simulate_move(src_piece, to_r, to_c):
    """移動シミュレーション（chess_engineへの薄いラッパー）"""
    try:
        # chess_engine モジュールを動的にインポート
        import sys
        if 'chess_engine' in sys.modules:
            chess = sys.modules['chess_engine']
        else:
            try:
                import chess_engine as chess
            except ImportError:
                return []
        return chess.simulate_move(src_piece, to_r, to_c)
    except Exception:
        return []


def get_opponent_hand_count():
    """相手（AI）の手札枚数を取得する（UI はこれを参照する）"""
    try:
        # グローバルスコープから ai_player を参照
        # 循環インポートを避けるため、関数内でインポート
        import sys
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return 0
        
        ai_player = getattr(main_module, 'ai_player', None)
        if ai_player is None:
            return 0
        return len(getattr(ai_player, 'hand').cards)
    except Exception:
        # フォールバック: 初期値や何らかの理由で参照できない場合は 0 を返す
        return 0
