"""チュートリアル統合モジュール v2

CardGame.py との統合用ヘルパー関数を提供します。
シンプルな設計で、既存コードへの影響を最小限に抑えます。
"""

from game.tutorial import TutorialManager, TutorialPhase
from game.state import GameState


def init_tutorial_mode(state: GameState, mode: str) -> bool:
    """チュートリアルモードで初期化
    
    Args:
        state: GameState インスタンス
        mode: ゲームモード ('tutorial', 'local', 'cpu', etc.)
        
    Returns:
        bool: チュートリアルモードが有効化されたかどうか
    """
    if mode == 'tutorial':
        if not getattr(state, 'tutorial_manager', None):
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
    
    # UI操作は常に許可（ログ表示、墓地表示、相手の手札表示など）
    ui_actions = {'toggle_log', 'show_log', 'show_grave', 'show_opponent_hand', 
                  'debug', 'escape', 'resize', 'scroll'}
    if action in ui_actions:
        return True
    
    return state.tutorial_manager.is_action_allowed(action)


def on_tutorial_piece_moved(state: GameState, from_pos: tuple, to_pos: tuple):
    """チュートリアル: 駒移動時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_piece_moved(from_pos, to_pos)


def on_tutorial_card_played(state: GameState, card_index: int, card_name: str = ''):
    """チュートリアル: カード使用時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_card_played(card_index, card_name)


def on_tutorial_turn_ended(state: GameState):
    """チュートリアル: ターン終了時のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_turn_ended()


def on_tutorial_effect_resolved(state: GameState, effect_type: str):
    """チュートリアル: カード効果解決後のコールバック"""
    if state.tutorial_manager:
        state.tutorial_manager.on_effect_resolved(effect_type)


def handle_tutorial_esc_key(state: GameState) -> bool:
    """ESCキーでチュートリアルをスキップ
    
    Returns:
        bool: チュートリアルをスキップしたらTrue
    """
    if state.tutorial_manager and state.tutorial_manager.enabled:
        state.tutorial_manager.skip()
        return True
    return False


def handle_tutorial_click(state: GameState, pos: tuple) -> bool:
    """チュートリアル専用クリック処理
    
    開始ボタンや完了ボタンのクリック処理を行います。
    
    Args:
        state: GameState インスタンス
        pos: クリック位置 (x, y)
        
    Returns:
        bool: クリックが処理された場合True（他の処理を無効化）
    """
    tm = getattr(state, 'tutorial_manager', None)
    if not tm:
        return False
    
    if not tm.enabled:
        return False
    
    # 完了画面のボタン処理
    if tm.completed or tm.state.phase == TutorialPhase.COMPLETE:
        cpu_rect = getattr(tm, 'completion_cpu_rect', None)
        retry_rect = getattr(tm, 'completion_retry_rect', None)
        
        if cpu_rect and hasattr(cpu_rect, 'collidepoint') and cpu_rect.collidepoint(pos):
            _transition_to_cpu_battle(state)
            return True
        
        if retry_rect and hasattr(retry_rect, 'collidepoint') and retry_rect.collidepoint(pos):
            _restart_tutorial(state)
            return True
        
        # 完了画面中もUI操作（ログ展開など）は許可
        return False
    
    # Turn 5のボタン処理
    if tm.state.phase == TutorialPhase.TURN5_CHECKMATE:
        cpu_rect = getattr(tm, 'completion_cpu_rect', None)
        retry_rect = getattr(tm, 'completion_retry_rect', None)
        
        if cpu_rect and hasattr(cpu_rect, 'collidepoint') and cpu_rect.collidepoint(pos):
            _transition_to_cpu_battle(state)
            return True
        
        if retry_rect and hasattr(retry_rect, 'collidepoint') and retry_rect.collidepoint(pos):
            _restart_tutorial(state)
            return True
        
        return True  # ロック中
    
    # 開始前画面のボタン処理
    if tm.waiting_for_start:
        btn = getattr(tm, 'start_button_rect', None)
        if btn is not None and hasattr(btn, 'collidepoint') and btn.collidepoint(pos):
            tm.begin_after_intro()
            return True
        return True  # 開始前は他の操作を無効化
    
    # ロック中のフェーズでは入力を無効化
    step = tm.get_current_step()
    if step and getattr(step, 'lock_ui', False):
        return True
    
    return False


def _transition_to_cpu_battle(state: GameState):
    """チュートリアル完了後にCPU戦へ遷移（難易度選択画面へ）"""
    try:
        import sys
        
        # __main__モジュールを取得（CardGame.pyを直接実行している場合）
        main_mod = sys.modules.get('__main__')
        CardGame = sys.modules.get('CardGame', main_mod)
        
        if CardGame is None:
            return
        
        # === チュートリアル状態を完全にリセット ===
        
        # 1. IS_TUTORIAL_MODEフラグを無効化
        try:
            CardGame.IS_TUTORIAL_MODE = False
            if main_mod and main_mod is not CardGame:
                main_mod.IS_TUTORIAL_MODE = False
        except Exception:
            pass
        
        # 2. 現在のtutorial_managerを完全に無効化
        try:
            _ct = getattr(CardGame, '_current_tutorial', None)
            if _ct is None and main_mod:
                _ct = getattr(main_mod, '_current_tutorial', None)
            if _ct is not None:
                _ct.enabled = False
                _ct.completed = False
        except Exception:
            pass
        
        # 3. グローバルのチュートリアル参照をクリア
        try:
            CardGame._current_tutorial = None
        except Exception:
            pass
        try:
            if main_mod:
                main_mod._current_tutorial = None
        except Exception:
            pass
        
        # 4. PP無限モードを無効化
        try:
            import card_core
            card_core.TUTORIAL_INFINITE_PP = False
        except Exception:
            pass
        
        # 5. 引数のstateのtutorial_managerをクリア
        if state:
            state.tutorial_manager = None
        
        # 6. game_stateのtutorial_managerもクリア
        try:
            gs = getattr(CardGame, 'game_state', None)
            if gs is None and main_mod:
                gs = getattr(main_mod, 'game_state', None)
            if gs is not None:
                gs.tutorial_manager = None
        except Exception:
            pass
        
        # === 盤面状態を完全にリセット ===
        
        # 7. チェス盤の駒を初期位置にリセット
        try:
            chess = getattr(CardGame, 'chess', None)
            if chess is None and main_mod:
                chess = getattr(main_mod, 'chess', None)
            if chess is not None:
                # 駒を初期配置に戻す
                if hasattr(chess, 'pieces') and hasattr(chess, 'create_pieces'):
                    chess.pieces[:] = chess.create_pieces()
                # アンパッサン状態をクリア
                if hasattr(chess, 'en_passant_target'):
                    chess.en_passant_target = None
        except Exception:
            pass
        
        # 8. ゲームオブジェクトの状態をリセット
        try:
            game = getattr(CardGame, 'game', None)
            if game is None and main_mod:
                game = getattr(main_mod, 'game', None)
            if game is not None:
                # 氷結状態をクリア
                if hasattr(game, 'frozen_pieces'):
                    game.frozen_pieces.clear() if hasattr(game.frozen_pieces, 'clear') else setattr(game, 'frozen_pieces', {})
                # 封鎖タイルをクリア
                if hasattr(game, 'blocked_tiles'):
                    game.blocked_tiles.clear() if hasattr(game.blocked_tiles, 'clear') else setattr(game, 'blocked_tiles', {})
                if hasattr(game, 'blocked_tiles_owner'):
                    game.blocked_tiles_owner.clear() if hasattr(game.blocked_tiles_owner, 'clear') else setattr(game, 'blocked_tiles_owner', {})
                if hasattr(game, 'blocked_tiles_entries'):
                    game.blocked_tiles_entries.clear() if hasattr(game.blocked_tiles_entries, 'clear') else setattr(game, 'blocked_tiles_entries', {})
                # ターン状態をリセット
                game.turn = 0
                game.turn_active = False
                game.player_moved_this_turn = False
                # 特殊効果をクリア
                if hasattr(game, 'pending'):
                    game.pending = None
                if hasattr(game, 'ai_next_move_can_jump'):
                    game.ai_next_move_can_jump = False
                if hasattr(game, 'ai_iron_wall_active'):
                    game.ai_iron_wall_active = False
                if hasattr(game, 'player_ironwall_protection_turns'):
                    game.player_ironwall_protection_turns = 0
                if hasattr(game, 'ai_ironwall_protection_turns'):
                    game.ai_ironwall_protection_turns = 0
        except Exception:
            pass
        
        # 9. UI状態をリセット
        try:
            if main_mod:
                if hasattr(main_mod, 'game_over'):
                    main_mod.game_over = False
                if hasattr(main_mod, 'game_over_winner'):
                    main_mod.game_over_winner = None
                if hasattr(main_mod, 'chess_current_turn'):
                    main_mod.chess_current_turn = 'white'
                if hasattr(main_mod, 'selected_piece'):
                    main_mod.selected_piece = None
                if hasattr(main_mod, 'highlight_squares'):
                    main_mod.highlight_squares = []
        except Exception:
            pass
        
        # 10. 難易度選択画面に戻る
        try:
            show_start = getattr(CardGame, 'show_start_screen', None)
            if show_start is None and main_mod:
                show_start = getattr(main_mod, 'show_start_screen', None)
            if show_start:
                show_start()
        except Exception as e:
            import logging
            logging.debug("show_start_screen呼び出しエラー: %s", e)
                
    except Exception as e:
        import logging
        logging.debug("CPU戦遷移エラー: %s", e)


def _restart_tutorial(state: GameState):
    """チュートリアルを最初から再開"""
    try:
        import CardGame
        
        # チュートリアルモードを有効に保つ
        CardGame.IS_TUTORIAL_MODE = True
        
        # PP無限モードを有効化
        try:
            import card_core
            card_core.TUTORIAL_INFINITE_PP = True
        except Exception:
            pass
        
        # 新しいTutorialManagerを作成
        new_tm = TutorialManager()
        new_tm.start()
        
        # グローバルとstateに設定
        CardGame._current_tutorial = new_tm
        if state:
            state.tutorial_manager = new_tm
        try:
            if CardGame.game_state is not None:
                CardGame.game_state.tutorial_manager = new_tm
        except Exception:
            pass
        
        # ゲームをリセット（チュートリアル用）
        CardGame.restart_game()
    except Exception as e:
        import logging
        logging.debug("チュートリアル再開エラー: %s", e)


def render_tutorial_ui(screen, state: GameState, layout, draw_text,
                       board_left, board_top, square_w, square_h, card_rects):
    """チュートリアルUIを描画
    
    draw_panel() の最後に呼び出します。
    
    Args:
        screen: pygame display surface
        state: GameState インスタンス
        layout: レイアウト情報
        draw_text: テキスト描画関数
        board_left, board_top: チェス盤の左上座標
        square_w, square_h: マスのサイズ
        card_rects: カードの矩形リスト
    """
    # stateがなければ何もしない
    if not state:
        return
    
    tm = state.tutorial_manager
    
    # グローバルから取得（フォールバック）
    if tm is None:
        try:
            import sys
            # __main__モジュールから取得（CardGame.pyを直接実行している場合）
            if '__main__' in sys.modules:
                main_mod = sys.modules['__main__']
                tm = getattr(main_mod, '_current_tutorial', None)
            # CardGameモジュールからも試す
            if tm is None and 'CardGame' in sys.modules:
                CardGame = sys.modules['CardGame']
                tm = getattr(CardGame, '_current_tutorial', None)
        except Exception:
            pass
    
    if tm is None:
        return
    
    # enabledでなければ描画しない（CPU戦遷移後のリセット状態を検出）
    if not getattr(tm, 'enabled', False):
        # stateからも削除して完全にクリア
        if state and state.tutorial_manager is tm:
            state.tutorial_manager = None
        return
    
    # 完了済みかつIS_TUTORIAL_MODEがFalseの場合は描画しない（CPU戦遷移後）
    if getattr(tm, 'completed', False):
        try:
            import sys
            main_mod = sys.modules.get('__main__')
            is_tutorial = getattr(main_mod, 'IS_TUTORIAL_MODE', False) if main_mod else False
            if not is_tutorial:
                # 完了後でチュートリアルモードがOFFなら描画しない
                if state and state.tutorial_manager is tm:
                    state.tutorial_manager = None
                return
        except Exception:
            pass
    
    # stateに設定されていなければ設定
    if state.tutorial_manager is None:
        state.tutorial_manager = tm
    
    from ui.renderer import draw_tutorial_overlay, draw_tutorial_highlights
    
    # カード名ヒントから動的にカードインデックスを計算
    try:
        hints = tm.get_card_name_hints() if tm else []
        
        if hints:
            dynamic_indices = []
            try:
                game_instance = state.game
                if game_instance is None:
                    import CardGame
                    game_instance = CardGame.game
                
                if game_instance and hasattr(game_instance, 'player') and hasattr(game_instance.player, 'hand'):
                    hand_cards = getattr(game_instance.player.hand, 'cards', [])
                    for idx, c in enumerate(hand_cards):
                        nm = getattr(c, 'name', '')
                        for h in hints:
                            if h in nm:
                                dynamic_indices.append(idx)
                                break
            except Exception:
                pass
            
            # ハイライトカードインデックスを設定
            try:
                tm.set_highlight_card_indices(list(set(dynamic_indices)))
            except Exception:
                pass
    except Exception:
        pass
    
    # ハイライト描画
    try:
        draw_tutorial_highlights(
            screen, tm,
            board_left, board_top, square_w, square_h,
            card_rects, layout
        )
    except Exception:
        pass
    
    # メッセージオーバーレイ描画
    try:
        draw_tutorial_overlay(screen, tm, layout, draw_text)
    except Exception:
        pass
