"""ゲーム状態管理モジュール

このモジュールは、ゲームの状態を一元管理します。
- ターン状態
- 選択中の駒
- ゲームオーバー状態
- UI表示状態
"""


class GameState:
    """ゲーム状態を管理するクラス"""
    
    def __init__(self):
        # チェス盤の状態
        self.selected_piece = None
        self.highlight_squares = []
        self.chess_current_turn = 'white'
        
        # 同時チェック管理
        self.simul_check_active = False
        self.simul_white_result = 'none'  # 'none'|'pending'|'cleared'|'failed'
        self.simul_black_result = 'none'
        self.white_turn_index = 0
        self.black_turn_index = 0
        self.last_turn_color = None
        self.simul_white_deadline = None
        self.simul_black_deadline = None
        
        # ゲーム終了状態
        self.game_over = False
        self.game_over_winner = None
        
        # UI表示状態
        self.show_grave = False
        self.show_log = False
        self.log_scroll_offset = 0
        self.enlarged_card_index = None
        self.enlarged_card_name = None
        self.show_opponent_hand = False
        
        # ターン表示テロップ
        self.turn_telop_msg = None
        self.turn_telop_until = 0.0
        
        # 通知メッセージ
        self.notice_msg = None
        self.notice_until = 0.0
        
        # CPU待機状態
        self.cpu_wait = False
        self.cpu_wait_start = 0.0
        
        # AI用フラグ
        self.ai_next_move_can_jump = False
        self.ai_extra_moves_this_turn = 0
        self.ai_consecutive_turns = 0
        self.ai_continuation = False
        
        # クリック判定用矩形
        self.card_rects = []
        self.confirm_yes_rect = None
        self.confirm_no_rect = None
        self.start_turn_rect = None
        self.grave_label_rect = None
        self.opponent_hand_rect = None
        self.grave_card_rects = []
        self.scrollbar_rect = None
        self.dragging_scrollbar = False
        self.drag_start_y = 0
        self.drag_start_offset = 0
        self.heat_choice_unfreeze_rect = None
        self.heat_choice_block_rect = None
        self.log_toggle_rect = None
    
    def reset_for_new_game(self):
        """新規ゲーム用に状態をリセット"""
        self.selected_piece = None
        self.highlight_squares = []
        self.chess_current_turn = 'white'
        self.game_over = False
        self.game_over_winner = None
        self.show_grave = False
        self.show_log = False
        self.log_scroll_offset = 0
        self.enlarged_card_index = None
        self.enlarged_card_name = None
        self.cpu_wait = False
        self.cpu_wait_start = 0.0
        
        # 同時チェック状態もリセット
        self.simul_check_active = False
        self.simul_white_result = 'none'
        self.simul_black_result = 'none'
        self.white_turn_index = 0
        self.black_turn_index = 0
        self.last_turn_color = None
        self.simul_white_deadline = None
        self.simul_black_deadline = None
    
    def switch_turn(self):
        """ターンを切り替える"""
        self.chess_current_turn = 'black' if self.chess_current_turn == 'white' else 'white'
        
        # ターンカウント更新
        if self.chess_current_turn == 'white':
            self.white_turn_index += 1
        else:
            self.black_turn_index += 1
        
        self.last_turn_color = 'black' if self.chess_current_turn == 'white' else 'white'


# グローバルインスタンス（後方互換性のため）
_game_state = GameState()


def get_game_state():
    """ゲーム状態のグローバルインスタンスを取得"""
    return _game_state


def reset_game_state():
    """ゲーム状態をリセット"""
    _game_state.reset_for_new_game()
