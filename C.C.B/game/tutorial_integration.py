"""チュートリアル統合モジュール v2

CardGame.py との統合用ヘルパー関数を提供します。
シンプルな設計で、既存コードへの影響を最小限に抑えます。
"""

from game.tutorial import TutorialManager, TutorialPhase, get_checkmate_board_setup
from game.state import GameState


def setup_checkmate_board():
    """Turn 5用のチェックメイト一歩手前の盤面をセットアップ
    
    既存の駒をすべてクリアし、get_checkmate_board_setup()で定義された
    配置に置き換えます。
    """
    try:
        import sys
        
        # chess_engineモジュールを取得
        chess = None
        try:
            import chess_engine as chess
        except ImportError:
            main_mod = sys.modules.get('__main__')
            if main_mod:
                chess = getattr(main_mod, 'chess', None)
        
        if chess is None:
            return False
        
        # 盤面設定を取得
        board_setup = get_checkmate_board_setup()
        
        # Pieceクラスを取得
        Piece = getattr(chess, 'Piece', None)
        if Piece is None:
            return False
        
        # 既存の駒をクリア
        if hasattr(chess, 'pieces'):
            chess.pieces.clear()
        
        # 新しい駒を配置
        for piece_info in board_setup:
            p = Piece(
                piece_info['row'],
                piece_info['col'],
                piece_info['name'],
                piece_info['color']
            )
            p.has_moved = True  # すべての駒が既に動いたことにする
            chess.pieces.append(p)
        
        # アンパッサン状態をクリア
        if hasattr(chess, 'en_passant_target'):
            chess.en_passant_target = None
        
        return True
        
    except Exception as e:
        import logging
        logging.debug("チェックメイト盤面セットアップエラー: %s", e)
        return False


def is_checkmate_phase(state: GameState) -> bool:
    """現在のフェーズがTurn 5（チェックメイト）かどうかを判定"""
    tm = getattr(state, 'tutorial_manager', None)
    if tm is None:
        return False
    return tm.state.phase == TutorialPhase.TURN5_CHECKMATE


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
        # Turn 5への遷移後に盤面切り替えが必要かチェック
        check_and_setup_checkmate_board(state)


def check_and_setup_checkmate_board(state: GameState) -> bool:
    """チェックメイト盤面のセットアップが必要かチェックし、必要なら実行
    
    Returns:
        bool: 盤面切り替えを実行した場合True
    """
    tm = getattr(state, 'tutorial_manager', None)
    if tm is None:
        return False
    
    if tm.should_setup_checkmate_board():
        success = setup_checkmate_board()
        if success:
            # UI状態もリセット（選択状態のクリアなど）
            try:
                import sys
                main_mod = sys.modules.get('__main__')
                if main_mod:
                    # 選択状態をクリア
                    if hasattr(main_mod, 'selected_piece'):
                        main_mod.selected_piece = None
                    if hasattr(main_mod, 'highlight_squares'):
                        main_mod.highlight_squares = []
                    # ゲームオブジェクトの状態もクリア
                    game = getattr(main_mod, 'game', None)
                    if game:
                        # 氷結・灼熱状態をクリア
                        if hasattr(game, 'frozen_pieces'):
                            game.frozen_pieces.clear() if hasattr(game.frozen_pieces, 'clear') else None
                        if hasattr(game, 'blocked_tiles'):
                            game.blocked_tiles.clear() if hasattr(game.blocked_tiles, 'clear') else None
                        if hasattr(game, 'blocked_tiles_owner'):
                            game.blocked_tiles_owner.clear() if hasattr(game.blocked_tiles_owner, 'clear') else None
            except Exception:
                pass
        return success
    return False


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
    
    # Turn 5（チェックメイト）: 駒の選択・移動は許可（ボタンなし）
    if tm.state.phase == TutorialPhase.TURN5_CHECKMATE:
        # Turn 5では駒の移動を許可するのでFalseを返す
        return False
    
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
        
        # === ゲームオブジェクトを完全にリセット ===
        
        # 7. gameオブジェクトをNoneに設定（show_start_screenで新規作成させる）
        try:
            CardGame.game = None
            if main_mod and main_mod is not CardGame:
                main_mod.game = None
        except Exception:
            pass
        
        # 8. ai_playerオブジェクトもNoneに設定
        try:
            CardGame.ai_player = None
            if main_mod and main_mod is not CardGame:
                main_mod.ai_player = None
        except Exception:
            pass
        
        # === 盤面状態を完全にリセット ===
        
        # 9. チェス盤の駒を初期位置にリセット
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
                # プロモーション状態をクリア
                if hasattr(chess, 'promotion_pending'):
                    chess.promotion_pending = None
        except Exception:
            pass
        
        # 10. UI状態をリセット
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
                if hasattr(main_mod, 'cpu_wait'):
                    main_mod.cpu_wait = False
                if hasattr(main_mod, 'log_scroll_offset'):
                    main_mod.log_scroll_offset = 0
        except Exception:
            pass
        
        # 11. ログをクリア
        try:
            if main_mod and hasattr(main_mod, 'master_log'):
                try:
                    main_mod.master_log.clear()
                except Exception:
                    main_mod.master_log = []
            if main_mod and hasattr(main_mod, '_log_seq'):
                main_mod._log_seq = 0
        except Exception:
            pass
        
        # 12. 難易度選択画面に戻る
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
        import sys
        
        main_mod = sys.modules.get('__main__')
        CardGame = sys.modules.get('CardGame', main_mod)
        
        if CardGame is None:
            return
        
        # === 既存のチュートリアル状態をクリア ===
        try:
            _ct = getattr(CardGame, '_current_tutorial', None)
            if _ct is None and main_mod:
                _ct = getattr(main_mod, '_current_tutorial', None)
            if _ct is not None:
                _ct.enabled = False
                _ct.completed = False
        except Exception:
            pass
        
        # === ゲーム状態を完全にリセット ===
        
        # チェス盤を初期状態にリセット
        try:
            chess = getattr(CardGame, 'chess', None)
            if chess is None and main_mod:
                chess = getattr(main_mod, 'chess', None)
            if chess is not None:
                if hasattr(chess, 'pieces') and hasattr(chess, 'create_pieces'):
                    chess.pieces[:] = chess.create_pieces()
                if hasattr(chess, 'en_passant_target'):
                    chess.en_passant_target = None
                if hasattr(chess, 'promotion_pending'):
                    chess.promotion_pending = None
        except Exception:
            pass
        
        # UI状態をリセット
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
                if hasattr(main_mod, 'cpu_wait'):
                    main_mod.cpu_wait = False
                if hasattr(main_mod, 'log_scroll_offset'):
                    main_mod.log_scroll_offset = 0
        except Exception:
            pass
        
        # ログをクリア
        try:
            if main_mod and hasattr(main_mod, 'master_log'):
                try:
                    main_mod.master_log.clear()
                except Exception:
                    main_mod.master_log = []
            if main_mod and hasattr(main_mod, '_log_seq'):
                main_mod._log_seq = 0
        except Exception:
            pass
        
        # === チュートリアルモードで再起動 ===
        
        # チュートリアルモードを有効化
        try:
            CardGame.IS_TUTORIAL_MODE = True
            if main_mod and main_mod is not CardGame:
                main_mod.IS_TUTORIAL_MODE = True
        except Exception:
            pass
        
        # PP無限モードを有効化
        try:
            import card_core
            card_core.TUTORIAL_INFINITE_PP = True
        except Exception:
            pass
        
        # 新しいTutorialManagerを作成
        new_tm = TutorialManager()
        new_tm.start()
        
        # グローバルに設定
        try:
            CardGame._current_tutorial = new_tm
            if main_mod and main_mod is not CardGame:
                main_mod._current_tutorial = new_tm
        except Exception:
            pass
        
        if state:
            state.tutorial_manager = new_tm
        
        try:
            gs = getattr(CardGame, 'game_state', None)
            if gs is None and main_mod:
                gs = getattr(main_mod, 'game_state', None)
            if gs is not None:
                gs.tutorial_manager = new_tm
        except Exception:
            pass
        
        # === チュートリアル用のゲームオブジェクトを新規作成 ===
        try:
            from card_core import (Card, Deck, PlayerState, Game, 
                eff_draw2, eff_freeze_piece, eff_heat_block_tile,
                eff_storm_jump_once, eff_lightning_two_actions,
                eff_alchemy, eff_graveyard_roulette, eff_leech_pp2)
            
            # チュートリアル用の固定デッキ（順序固定、シャッフルなし）
            tutorial_deck_cards = [
                Card('2ドロー', 1, eff_draw2),
                Card('氷結', 2, eff_freeze_piece),
                Card('灼熱', 2, eff_heat_block_tile),
                Card('錬成', 0, eff_alchemy),
                Card('暴風', 3, eff_storm_jump_once),
                Card('迅雷', 3, eff_lightning_two_actions),
                Card('墓地ルーレット', 1, eff_graveyard_roulette),
                Card('摂取', 1, eff_leech_pp2),
                Card('2ドロー', 1, eff_draw2),
                Card('氷結', 2, eff_freeze_piece),
                Card('灼熱', 2, eff_heat_block_tile),
            ]
            
            deck = Deck(tutorial_deck_cards)
            player = PlayerState(deck=deck)
            new_game = Game(player=player)
            
            # ログを初期化
            try:
                LogList = getattr(CardGame, 'LogList', None)
                if LogList is None and main_mod:
                    LogList = getattr(main_mod, 'LogList', None)
                if LogList:
                    new_game.log = LogList('game')
            except Exception:
                pass
            
            player.reset_pp()
            new_game.log.append("チュートリアル開始: PPを最大まで回復しました。")
            
            # 最初の4枚をドロー
            for _ in range(4):
                c = player.deck.draw()
                if c:
                    player.hand.add(c)
            new_game.log.append(f"初期手札: {[c.name for c in player.hand.cards]}")
            
            # ゲームオブジェクトの状態を初期化
            new_game.frozen_pieces = {}
            new_game.blocked_tiles = {}
            new_game.blocked_tiles_owner = {}
            new_game.blocked_tiles_entries = {}
            new_game.pending = None
            new_game.ai_next_move_can_jump = False
            new_game.ai_iron_wall_active = False
            new_game.player_ironwall_protection_turns = 0
            new_game.ai_ironwall_protection_turns = 0
            new_game.turn = 1
            new_game.turn_active = True
            new_game.player_moved_this_turn = False
            
            # グローバルに設定
            try:
                CardGame.game = new_game
                if main_mod and main_mod is not CardGame:
                    main_mod.game = new_game
            except Exception:
                pass
            
            # AIプレイヤーも新規作成
            try:
                build_ai = getattr(CardGame, 'build_ai_player', None)
                if build_ai is None and main_mod:
                    build_ai = getattr(main_mod, 'build_ai_player', None)
                if build_ai:
                    new_ai = build_ai('fixed')
                    CardGame.ai_player = new_ai
                    if main_mod and main_mod is not CardGame:
                        main_mod.ai_player = new_ai
                    # AI初期手札
                    try:
                        init_ai_hand = getattr(CardGame, '_init_ai_start_hand', None)
                        if init_ai_hand is None and main_mod:
                            init_ai_hand = getattr(main_mod, '_init_ai_start_hand', None)
                        if init_ai_hand:
                            init_ai_hand(new_ai, 4, new_game)
                    except Exception:
                        pass
            except Exception:
                pass
            
            # GameStateにも設定
            try:
                gs = getattr(CardGame, 'game_state', None)
                if gs is None and main_mod:
                    gs = getattr(main_mod, 'game_state', None)
                if gs is not None:
                    gs.game = new_game
            except Exception:
                pass
            
        except Exception as e:
            import logging
            logging.debug("チュートリアル用ゲームオブジェクト作成エラー: %s", e)
            
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
