"""チュートリアル統合モジュール

CardGame.py の main_loop に組み込むためのヘルパー関数を提供します。
既存のコードを最小限に変更してチュートリアル機能を追加します。
"""

from game.tutorial import TutorialManager
from game.state import GameState


def init_tutorial_mode(state: GameState, mode: str):
    """チュートリアルモードで初期化
    
    Args:
        state: GameState インスタンス
        mode: ゲームモード ('tutorial', 'local', 'cpu', etc.)
    """
    if mode == 'tutorial':
        from game.tutorial import TutorialManager
        state.tutorial_manager = TutorialManager()
        state.tutorial_manager.start()
        return True
    else:
        state.tutorial_manager = None
        return False


def check_tutorial_action(state: GameState, action: str) -> bool:
    """チュートリアル中の操作制限をチェック
    
    Args:
        state: GameState インスタンス
        action: 操作名 ('move_piece', 'play_card', 'end_turn')
        
    Returns:
        bool: 操作が許可されていればTrue
    """
    if state.tutorial_manager is None:
        return True
    
    return state.tutorial_manager.is_action_allowed(action)


def on_tutorial_piece_moved(state: GameState, from_pos: tuple, to_pos: tuple):
    """チュートリアル: 駒移動時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_piece_moved(from_pos, to_pos)


def on_tutorial_card_played(state: GameState, card_index: int):
    """チュートリアル: カード使用時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_card_played(card_index)


def on_tutorial_turn_ended(state: GameState):
    """チュートリアル: ターン終了時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_turn_ended()


def handle_tutorial_esc_key(state: GameState) -> bool:
    """ESCキーでチュートリアルをスキップ
    
    Returns:
        bool: チュートリアルをスキップしたらTrue
    """
    if state.tutorial_manager and state.tutorial_manager.enabled:
        state.tutorial_manager.skip()
        return True
    return False


# CardGame.py の draw_panel に追加する描画呼び出し
def render_tutorial_ui(screen, state: GameState, layout, draw_text, 
                       board_left, board_top, square_w, square_h, card_rects):
    """チュートリアルUIを描画
    
    draw_panel() の最後に呼び出します（他の要素より手前に表示）
    """
    if not state.tutorial_manager:
        return
    
    from ui.renderer import draw_tutorial_overlay, draw_tutorial_highlights
    
    # ハイライト描画（Step1では手札中の『Quick Draw』を動的にハイライト）
    try:
        step = state.tutorial_manager.get_current_step()
        if step and getattr(step, 'step_id', None) == 1:
            dynamic_indices = []
            try:
                # 手札から『Quick Draw』相当のカードを探索（英語名・部分一致）
                hand_cards = getattr(state.game.player.hand, 'cards', [])
                for idx, c in enumerate(hand_cards):
                    nm = getattr(c, 'name', '')
                    if nm == 'Quick Draw' or 'draw' in nm.lower():
                        dynamic_indices.append(idx)
            except Exception:
                pass
            # 現ステップのハイライトカードに反映（重複除去）
            try:
                cur = set(getattr(step, 'highlight_cards', []) or [])
                for di in dynamic_indices:
                    cur.add(di)
                step.highlight_cards = list(sorted(cur))
            except Exception:
                pass
    except Exception:
        pass

    draw_tutorial_highlights(
        screen, state.tutorial_manager,
        board_left, board_top, square_w, square_h,
        card_rects, layout
    )
    
    # メッセージオーバーレイ
    draw_tutorial_overlay(screen, state.tutorial_manager, layout, draw_text)


# 使用例（CardGame.py への組み込み方）
"""
# === CardGame.py の変更箇所 ===

# 1) インポート追加（ファイル先頭付近）
from game.tutorial_integration import (
    init_tutorial_mode, check_tutorial_action,
    on_tutorial_piece_moved, on_tutorial_card_played, on_tutorial_turn_ended,
    handle_tutorial_esc_key, render_tutorial_ui
)

# 2) show_start_screen() でモード取得後
def show_start_screen():
    ...
    # mode_select を呼び出してモードを取得
    from mode_select import select_game_mode
    mode = select_game_mode(screen, btn_font)
    
    # チュートリアルモード判定
    global IS_TUTORIAL_MODE
    IS_TUTORIAL_MODE = (mode == 'tutorial')
    
    if mode == 'tutorial':
        # チュートリアル用に簡易初期化
        CPU_DIFFICULTY = 1  # 簡単な敵
        init_tutorial_mode(game_state, 'tutorial')
        return 'cpu'  # CPU戦として開始
    ...

# 3) 駒移動処理（チェス盤クリック時）
if clicked_piece:
    if not check_tutorial_action(game_state, 'move_piece'):
        # チュートリアル: この操作は許可されていません
        continue
    ...
    # 移動後
    on_tutorial_piece_moved(game_state, (from_row, from_col), (to_row, to_col))

# 4) カード使用処理
if card_clicked:
    if not check_tutorial_action(game_state, 'play_card'):
        # チュートリアル: この操作は許可されていません
        continue
    ...
    # 使用後
    on_tutorial_card_played(game_state, card_index)

# 5) ターン開始ボタン
if start_turn_button_clicked:
    if not check_tutorial_action(game_state, 'end_turn'):
        # チュートリアル: この操作は許可されていません
        continue
    ...
    # ターン終了後
    on_tutorial_turn_ended(game_state)

# 6) ESCキー処理
if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
    if handle_tutorial_esc_key(game_state):
        # チュートリアルをスキップしました
        pass

# 7) draw_panel() の最後（pygame.display.flip() の直前）
def draw_panel():
    ...
    # 全ての描画の最後
    render_tutorial_ui(
        screen, game_state, layout, draw_text,
        board_left, board_top, square_w, square_h,
        card_rects
    )
    pygame.display.flip()
"""
