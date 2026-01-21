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
        # TutorialManagerが既に設定されていなければ新規作成
        if not getattr(state, 'tutorial_manager', None):
            state.tutorial_manager = TutorialManager()
            state.tutorial_manager.start()
        
        # 注意: 固定デッキは new_game_with_mode() で既に設定されているため、
        # ここでは上書きしない（順序が崩れるため）
        
        return True
    else:
        state.tutorial_manager = None
        return False


def _apply_tutorial_fixed_deck(state: GameState):
    """チュートリアル用の固定デッキを適用"""
    if not state.tutorial_manager:
        return
    
    step = state.tutorial_manager.get_current_step()
    if not step or not step.fixed_deck:
        # ステップ0の固定デッキを取得
        try:
            steps = state.tutorial_manager.steps
            if steps and len(steps) > 0:
                step = steps[0]
            else:
                return
        except Exception:
            return
    
    if not step.fixed_deck:
        return
    
    # カード名リストからCardオブジェクトを生成
    import card_core
    
    fixed_cards = []
    for card_name in step.fixed_deck:
        # card_core内のカード定義から該当するカードを探す
        # make_rule_cards_deckで定義されているカードを参照
        card_def = None
        if card_name == '2ドロー':
            card_def = card_core.Card('2ドロー', 1, card_core.eff_draw2)
        elif card_name == '氷結':
            card_def = card_core.Card('氷結', 2, card_core.eff_freeze_piece)
        elif card_name == '灼熱':
            card_def = card_core.Card('灼熱', 2, card_core.eff_heat_block_tile)
        elif card_name == '暴風':
            card_def = card_core.Card('暴風', 3, card_core.eff_storm_jump_once)
        elif card_name == '迅雷':
            card_def = card_core.Card('迅雷', 3, card_core.eff_lightning_two_actions)
        elif card_name == '錬成':
            card_def = card_core.Card('錬成', 0, card_core.eff_alchemy)
        elif card_name == '墓地ルーレット':
            card_def = card_core.Card('墓地ルーレット', 1, card_core.eff_graveyard_roulette)
        elif card_name == '摂取':
            card_def = card_core.Card('摂取', 1, card_core.eff_leech_pp2)
        
        if card_def:
            fixed_cards.append(card_def)
    
    # プレイヤーのデッキを固定デッキで置き換え
    if state.game and hasattr(state.game, 'player'):
        try:
            state.game.player.deck = card_core.Deck(fixed_cards.copy())
            # 手札をクリアして再ドロー
            if hasattr(state.game.player, 'hand'):
                state.game.player.hand.cards.clear()
                for _ in range(min(4, len(fixed_cards))):
                    card = state.game.player.deck.draw()
                    if card:
                        state.game.player.hand.add(card)
        except Exception:
            pass


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


def handle_tutorial_click(state: GameState, pos) -> bool:
    """チュートリアル専用クリック処理（開始ボタンなど）"""
    tm = getattr(state, 'tutorial_manager', None)
    if not tm:
        return False

    # チュートリアル完了時のボタン処理
    if getattr(tm, 'completed', False):
        cpu_rect = getattr(tm, 'completion_cpu_rect', None)
        retry_rect = getattr(tm, 'completion_retry_rect', None)
        
        if cpu_rect and hasattr(cpu_rect, 'collidepoint') and cpu_rect.collidepoint(pos):
            # CPU戦へ遷移
            _transition_to_cpu_battle(state)
            return True
        
        if retry_rect and hasattr(retry_rect, 'collidepoint') and retry_rect.collidepoint(pos):
            # チュートリアル再開
            _restart_tutorial(state)
            return True
        
        return True  # 完了画面中は他のクリックを無効化
    
    if not tm.enabled:
        return False

    step = None
    try:
        step = tm.get_current_step()
    except Exception:
        step = None

    # 開始前ロック中は開始ボタンのみ反応させる
    if getattr(tm, 'waiting_for_start', False):
        btn = getattr(tm, 'start_button_rect', None)
        if btn is not None and hasattr(btn, 'collidepoint') and btn.collidepoint(pos):
            tm.begin_after_intro()
            return True
        return True  # ロック中は他UIをすべて無効化
    
    # 完了画面など lock_ui 中は入力を無効化
    try:
        if step and getattr(step, 'lock_ui', False):
            # ステップ5（最終ステップ）の場合はボタン処理
            if step.step_id == 5:
                cpu_rect = getattr(tm, 'completion_cpu_rect', None)
                retry_rect = getattr(tm, 'completion_retry_rect', None)
                
                if cpu_rect and hasattr(cpu_rect, 'collidepoint') and cpu_rect.collidepoint(pos):
                    _transition_to_cpu_battle(state)
                    return True
                
                if retry_rect and hasattr(retry_rect, 'collidepoint') and retry_rect.collidepoint(pos):
                    _restart_tutorial(state)
                    return True
            return True
    except Exception:
        pass
    return False


def _transition_to_cpu_battle(state: GameState):
    """チュートリアル完了後にCPU戦へ遷移"""
    try:
        # チュートリアルモードを無効化
        import CardGame
        CardGame.IS_TUTORIAL_MODE = False
        if state.tutorial_manager:
            state.tutorial_manager.enabled = False
            state.tutorial_manager = None
        
        # ゲームを再起動
        CardGame.restart_game()
    except Exception as e:
        import logging
        logging.debug("CPU戦遷移エラー: %s", e)


def _restart_tutorial(state: GameState):
    """チュートリアルを最初から再開"""
    try:
        from game.tutorial import TutorialManager
        state.tutorial_manager = TutorialManager()
        state.tutorial_manager.start()
        
        # ゲームをリセット
        import CardGame
        CardGame.restart_game()
    except Exception as e:
        import logging
        logging.debug("チュートリアル再開エラー: %s", e)


# CardGame.py の draw_panel に追加する描画呼び出し
def render_tutorial_ui(screen, state: GameState, layout, draw_text, 
                       board_left, board_top, square_w, square_h, card_rects):
    """チュートリアルUIを描画
    
    draw_panel() の最後に呼び出します（他の要素より手前に表示）
    """
    if not state:
        return
    
    # tutorial_managerの取得（state.tutorial_managerを優先、なければグローバルから）
    tm = state.tutorial_manager
    
    if tm is None:
        try:
            import CardGame
            tm = getattr(CardGame, '_current_tutorial', None)
        except Exception:
            pass
    
    if tm is None:
        return
    
    # state.tutorial_managerが設定されていなければ設定
    if state.tutorial_manager is None:
        state.tutorial_manager = tm
    
    from ui.renderer import draw_tutorial_overlay, draw_tutorial_highlights
    
    # ハイライト描画（カード名ヒントから動的ハイライト）
    try:
        step = tm.get_current_step()
        hints = []
        try:
            hints = tm.get_card_name_hints()
        except Exception:
            hints = []
        if step and hints:
            dynamic_indices = []
            try:
                # state.gameがNoneの場合はグローバルのgameを使用
                game_instance = state.game
                if game_instance is None:
                    import CardGame
                    game_instance = CardGame.game
                
                if game_instance and hasattr(game_instance, 'player') and hasattr(game_instance.player, 'hand'):
                    hand_cards = getattr(game_instance.player.hand, 'cards', [])
                    for idx, c in enumerate(hand_cards):
                        nm = getattr(c, 'name', '')
                        lower_nm = nm.lower()
                        for h in hints:
                            if h.lower() in lower_nm:
                                dynamic_indices.append(idx)
                                break
            except Exception:
                dynamic_indices = []
            try:
                cur = set(getattr(step, 'highlight_cards', []) or [])
                for di in dynamic_indices:
                    cur.add(di)
                step.highlight_cards = list(sorted(cur))
            except Exception:
                pass
    except Exception:
        pass

    try:
        draw_tutorial_highlights(
            screen, tm,
            board_left, board_top, square_w, square_h,
            card_rects, layout
        )
    except Exception:
        pass
    
    try:
        # メッセージオーバーレイ
        draw_tutorial_overlay(screen, tm, layout, draw_text)
    except Exception:
        pass


def on_tutorial_effect_resolved(state: GameState, event: str):
    """カード効果解決後の進行通知"""
    if state.tutorial_manager:
        state.tutorial_manager.on_effect_resolved(event)


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
