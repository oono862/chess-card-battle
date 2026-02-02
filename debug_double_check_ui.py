"""
両チェック状態デバッグUI

実際のプレイ中に両チェック状態を確認・検証するための
インタラクティブなデバッグツール
"""

import sys
import os
import importlib.util
import json

# C.C.B モジュールの読み込み
base_path = os.path.dirname(os.path.abspath(__file__))
ccb_path = os.path.join(base_path, 'C.C.B')

# chess_engine.py をロード
chess_engine_path = os.path.join(ccb_path, 'chess_engine.py')
spec = importlib.util.spec_from_file_location("chess_engine", chess_engine_path)
chess_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chess_engine)

Piece = chess_engine.Piece

# rules.py をロード
rules_path = os.path.join(ccb_path, 'chess', 'rules.py')
spec = importlib.util.spec_from_file_location("rules", rules_path)
rules_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules_module)
is_in_check_for_display = rules_module.is_in_check_for_display


class DoubleCheckDebugUI:
    """両チェック状態のデバッグUIクラス"""
    
    def __init__(self):
        self.col_names = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self.piece_names_jp = {
            'K': 'キング',
            'Q': 'クイーン',
            'R': 'ルーク',
            'B': 'ビショップ',
            'N': 'ナイト',
            'P': 'ポーン'
        }
        self.scenarios = {}
        self._setup_scenarios()
    
    def _setup_scenarios(self):
        """シナリオの定義"""
        # シナリオ1: 基本的な両チェック
        self.scenarios['basic'] = {
            'name': '基本的な両チェック状態',
            'description': '白ルークが黒王をチェック、黒ルークが白王をチェック',
            'setup': [
                {'type': 'K', 'color': 'white', 'row': 3, 'col': 3},  # d5
                {'type': 'R', 'color': 'white', 'row': 7, 'col': 4},  # e1
                {'type': 'K', 'color': 'black', 'row': 4, 'col': 4},  # e4
                {'type': 'R', 'color': 'black', 'row': 0, 'col': 3},  # d8
            ]
        }
        
        # シナリオ2: ビショップとルークによる両チェック
        self.scenarios['bishop_rook'] = {
            'name': 'ビショップ＆ルークによる両チェック',
            'description': '異なる駒からのチェック',
            'setup': [
                {'type': 'K', 'color': 'white', 'row': 4, 'col': 4},  # e4
                {'type': 'B', 'color': 'black', 'row': 1, 'col': 1},  # b7
                {'type': 'K', 'color': 'black', 'row': 4, 'col': 2},  # c4
                {'type': 'R', 'color': 'white', 'row': 4, 'col': 7},  # h4
            ]
        }
        
        # シナリオ3: ナイトとポーンによる両チェック
        self.scenarios['knight_pawn'] = {
            'name': 'ナイト＆ポーンによる両チェック',
            'description': 'より複雑な駒の組み合わせ',
            'setup': [
                {'type': 'K', 'color': 'white', 'row': 5, 'col': 5},  # f3
                {'type': 'N', 'color': 'black', 'row': 3, 'col': 4},  # e5
                {'type': 'K', 'color': 'black', 'row': 3, 'col': 3},  # d5
                {'type': 'P', 'color': 'white', 'row': 2, 'col': 4},  # e6
            ]
        }
    
    def create_board_from_scenario(self, scenario_key):
        """シナリオから盤面を作成"""
        if scenario_key not in self.scenarios:
            print(f"エラー: シナリオ '{scenario_key}' が見つかりません")
            return None
        
        scenario = self.scenarios[scenario_key]
        pieces = []
        
        for piece_data in scenario['setup']:
            piece = Piece(
                piece_data['row'],
                piece_data['col'],
                piece_data['type'],
                piece_data['color']
            )
            pieces.append(piece)
        
        return pieces
    
    def display_board(self, pieces):
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
        
        print("\n" + "=" * 50)
        print("       0   1   2   3   4   5   6   7")
        print("     " + "-" * 44)
        for row in range(8):
            row_str = f"  {row} | "
            row_str += " | ".join(board[row])
            row_str += " |"
            print(row_str)
        print("     " + "-" * 44)
        print("=" * 50)
    
    def display_pieces(self, pieces):
        """駒情報を表示"""
        print("\n【駒配置情報】")
        print("-" * 50)
        
        for piece in pieces:
            pos = f"{self.col_names[piece.col]}{8 - piece.row}"
            piece_name = self.piece_names_jp.get(piece.name, piece.name)
            color = "白" if piece.color == 'white' else "黒"
            print(f"  {color} {piece_name:8} {pos}")
        
        print("-" * 50)
    
    def check_double_check_status(self, pieces):
        """両チェック状態を確認"""
        print("\n【チェック状態の確認】")
        
        # chess_engine.pieces を更新
        chess_engine.pieces = pieces
        
        white_in_check = is_in_check_for_display(pieces, 'white', chess_engine)
        black_in_check = is_in_check_for_display(pieces, 'black', chess_engine)
        
        print(f"  白のチェック状態: {'✓ チェック中' if white_in_check else '✗ チェックなし'}")
        print(f"  黒のチェック状態: {'✓ チェック中' if black_in_check else '✗ チェックなし'}")
        
        if white_in_check and black_in_check:
            print("\n  🔴 【両チェック状態が検出されました】")
            return True
        elif white_in_check or black_in_check:
            print("\n  🟡 【片方がチェック状態です】")
            return False
        else:
            print("\n  🟢 【チェック状態ではありません】")
            return False
    
    def display_piece_moves(self, pieces):
        """駒の移動可能範囲を表示"""
        print("\n【駒の移動可能範囲】")
        print("-" * 50)
        
        for piece in pieces:
            try:
                valid_moves = piece.get_valid_moves(pieces)
                if valid_moves:
                    moves_str = ", ".join([f"{self.col_names[c]}{8-r}" for r, c in valid_moves])
                    color = "白" if piece.color == 'white' else "黒"
                    piece_name = self.piece_names_jp.get(piece.name, piece.name)
                    print(f"  {color} {piece_name:8}: {moves_str}")
                else:
                    color = "白" if piece.color == 'white' else "黒"
                    piece_name = self.piece_names_jp.get(piece.name, piece.name)
                    print(f"  {color} {piece_name:8}: (移動不可)")
            except Exception as e:
                print(f"  エラー: {piece.name} - {str(e)}")
        
        print("-" * 50)
    
    def display_scenario_menu(self):
        """シナリオメニューを表示"""
        print("\n【利用可能なシナリオ】")
        for idx, (key, scenario) in enumerate(self.scenarios.items(), 1):
            print(f"  {idx}. {scenario['name']}")
            print(f"     {scenario['description']}")
    
    def interactive_mode(self):
        """インタラクティブモード"""
        print("=" * 50)
        print("【チェスカードバトル - 両チェック状態デバッグUI】")
        print("=" * 50)
        
        while True:
            self.display_scenario_menu()
            print("\n  0. 終了")
            choice = input("\nシナリオを選択 (0-3): ").strip()
            
            if choice == '0':
                print("終了します。")
                break
            
            scenario_key = None
            scenario_idx = 0
            for idx, key in enumerate(self.scenarios.keys(), 1):
                if str(choice) == str(idx):
                    scenario_key = key
                    break
            
            if scenario_key is None:
                print("無効な入力です。")
                continue
            
            scenario = self.scenarios[scenario_key]
            print(f"\n▶ {scenario['name']} を開始します")
            print(f"  {scenario['description']}")
            
            pieces = self.create_board_from_scenario(scenario_key)
            if pieces:
                self.display_board(pieces)
                self.display_pieces(pieces)
                is_double = self.check_double_check_status(pieces)
                self.display_piece_moves(pieces)
                
                input("\n[Enter キーを押して続行...]")


def main():
    """メイン関数"""
    debug_ui = DoubleCheckDebugUI()
    
    # コマンドラインオプションをチェック
    if len(sys.argv) > 1:
        if sys.argv[1] == 'interactive':
            debug_ui.interactive_mode()
        else:
            scenario_key = sys.argv[1]
            scenario = debug_ui.scenarios.get(scenario_key)
            if scenario:
                print(f"▶ {scenario['name']}")
                pieces = debug_ui.create_board_from_scenario(scenario_key)
                debug_ui.display_board(pieces)
                debug_ui.display_pieces(pieces)
                debug_ui.check_double_check_status(pieces)
                debug_ui.display_piece_moves(pieces)
            else:
                print(f"シナリオ '{scenario_key}' が見つかりません")
                print("利用可能なシナリオ:", list(debug_ui.scenarios.keys()))
    else:
        # デフォルト: 全シナリオを表示
        for scenario_key in debug_ui.scenarios.keys():
            scenario = debug_ui.scenarios[scenario_key]
            print(f"\n{'='*50}")
            print(f"▶ {scenario['name']}")
            pieces = debug_ui.create_board_from_scenario(scenario_key)
            debug_ui.display_board(pieces)
            debug_ui.display_pieces(pieces)
            debug_ui.check_double_check_status(pieces)
            debug_ui.display_piece_moves(pieces)


if __name__ == "__main__":
    main()
