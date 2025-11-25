"""ターン制御システム

このモジュールは、ゲームのターン管理機能を提供します。
- プレイヤーターンの開始
- ターン開始の試行（条件チェック付き）
- プレイヤーの駒移動後処理
- ターン切り替え
"""
import time as _time_module


def _get_state():
    """ゲーム状態インスタンスを取得するヘルパー関数
    
    Returns:
        GameStateインスタンス、またはNone（取得失敗時）
    """
    try:
        from game.state import get_game_state
        return get_game_state()
    except Exception:
        return None


def _get_chess():
    """チェスエンジンモジュールを取得するヘルパー関数
    
    Returns:
        chessモジュール、またはNone（取得失敗時）
    """
    try:
        import sys
        # Try to get from main module
        if 'C.C.B.Card Game' in sys.modules:
            main_module = sys.modules['C.C.B.Card Game']
            return getattr(main_module, 'chess', None)
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            return getattr(main_module, 'chess', None)
        # Fallback: import directly
        import chess_engine
        return chess_engine
    except Exception:
        return None


def _get_is_in_check_for_display():
    """is_in_check_for_display関数を取得するヘルパー関数
    
    Returns:
        is_in_check_for_display関数、またはNone（取得失敗時）
    """
    try:
        import sys
        if 'C.C.B.Card Game' in sys.modules:
            main_module = sys.modules['C.C.B.Card Game']
            return getattr(main_module, 'is_in_check_for_display', None)
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            return getattr(main_module, 'is_in_check_for_display', None)
    except Exception:
        pass
    return None


def start_player_turn(ai_end_msg: str = None):
    """プレイヤーのカードゲームターンを開始し、「YOUR TURN」テロップを表示します。

    UI から game.start_turn() を直接呼び出す代わりにこのラッパーを使用することで、
    ターンが開始される際に常に視覚的なテロップが表示されます（手動/自動の両方）。

    ai_end_msg が提供された場合、ターン開始処理後にそのメッセージをゲームログに
    追加します。これにより、game.start_turn() が生成するドローログが、AI が
    自動プレイヤーターンをトリガーしたときの AI 終了メッセージの前に表示されます。
    
    Args:
        ai_end_msg: AI からのオプションメッセージ（現在は UX リクエストにより追加されません）
    """
    state = _get_state()
    if state is None or state.game is None:
        return
    
    game = state.game
    
    try:
        # start_turn は PP リセットと 1 枚ドローを処理
        if ai_end_msg:
            # AI 終了メッセージが提供された場合、start_turn が生成する新しいログエントリを
            # キャプチャして、ドロー関連の行を並び替えできるようにする
            prev_log_len = len(game.log)
            game.start_turn()
            # 新しく追加されたエントリを抽出
            new_entries = game.log[prev_log_len:]
            # draw_to_hand() が生成した「ドロー:」で始まるドロー専用エントリを識別
            draw_entries = [e for e in new_entries if isinstance(e, str) and e.strip().startswith("ドロー:")]
            # 他の新しいエントリを保持（「ターンN開始: ...ドロー...PP...」の完全メッセージを含む）
            non_draw_new = [e for e in new_entries if e not in draw_entries]
            # ドロー以外の新しいエントリのみを保持して game.log を再構築
            # （draw_entries や AI 終了メッセージは追加しません）
            try:
                game.log = game.log[:prev_log_len] + non_draw_new
            except Exception:
                # フォールバック: 直接代入が失敗した場合は、そのまま残す
                pass
        else:
            game.start_turn()
    except Exception:
        return
    
    # UI 状態を更新
    try:
        # ターンテロップメッセージを設定
        state.turn_telop_msg = "YOUR TURN"
        try:
            state.turn_telop_until = _time_module.time() + 1.0
        except Exception:
            state.turn_telop_until = 0.0
    except Exception:
        pass
    
    try:
        # 最新メッセージを表示するためにログスクロールオフセットをリセット
        state.log_scroll_offset = 0
    except Exception:
        pass
    
    # AI 提供の終了メッセージがリクエストされた場合、ここでは追加しません
    # また、カードごとの「ドロー:」行も追加しません。これにより、
    # 完全なターン開始メッセージ（「ターンN開始: ...ドロー...PP...」）を
    # そのまま維持しながら、AI 終了とスタンドアロンのドロー名行を
    # リクエスト通りに非表示にします。


def attempt_start_turn():
    """[T]キーと同等のターン開始処理を UI やマウスからも呼べるように関数化。
    
    以下の条件をチェックし、問題があればメッセージを表示してターン開始を拒否します：
    - 保留中の操作がある
    - 既にターンが開始されている
    - チェスのターンが黒（AI）または CPU 待機中
    
    条件を満たせば start_player_turn() を呼び出してターンを開始します。
    """
    state = _get_state()
    if state is None or state.game is None:
        return
    
    game = state.game
    
    # 保留中の操作があるかチェック
    if getattr(game, 'pending', None) is not None:
        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
        return
    
    # 既に開始済み
    if getattr(game, 'turn_active', False):
        game.log.append("既にターンが開始されています。カードや駒の操作を行ってください。")
        try:
            state.notice_msg = "既にターンが開始されています。カードや駒の操作を行ってください。"
            try:
                state.notice_until = _time_module.time() + 1.0
            except Exception:
                state.notice_until = 0.0
        except Exception:
            pass
        return
    
    # チェス手番/AI待ち中は開始不可
    if state.chess_current_turn != 'white' or state.cpu_wait:
        game.log.append("チェスの操作またはAIの処理が完了していないため、ターンを開始できません。")
        try:
            state.notice_msg = "チェスの操作またはAIの処理が完了していないため、ターンを開始できません。"
            try:
                state.notice_until = _time_module.time() + 1.0
            except Exception:
                state.notice_until = 0.0
        except Exception:
            pass
        return
    
    # 開始
    start_player_turn()


def end_player_chess_move():
    """プレイヤーの駒移動後の処理（ターンアクティブ状態の更新）。
    
    プレイヤーが駒を動かした後、extra_moves があればそれを消費し、
    なければ turn_active を False にして次のターン開始待ち状態にします。
    """
    state = _get_state()
    if state is None or state.game is None:
        return
    
    game = state.game
    
    # プレイヤーの移動の場合、追加移動を消費するか移動済みフラグを設定
    if state.chess_current_turn == 'white' and getattr(game, 'turn_active', False):
        try:
            if getattr(game.player, 'extra_moves_this_turn', 0) > 0:
                game.player.extra_moves_this_turn -= 1
                # 追加移動が残っている間はターンをアクティブに保つ
            else:
                game.player_moved_this_turn = True
                # アクティブターンを消費するので、次回は T キーを押す必要がある
                game.turn_active = False
        except Exception:
            # 防御的: フラグを設定
            game.player_moved_this_turn = True
            game.turn_active = False


def switch_turn():
    """ターン切り替え処理。
    
    駒移動後、ゲーム終了していなければターンを切り替えます。
    - プレイヤーターン終了時: decay_statuses('white')を呼び、AIターンへ
    - AIターン終了時: decay_statuses('black')を呼び、プレイヤーターンへ
    - 迅雷による連続ターンがある場合はそれを消費
    """
    state = _get_state()
    if state is None or state.game is None:
        return
    
    game = state.game
    chess = _get_chess()
    is_in_check_for_display = _get_is_in_check_for_display()
    
    # ゲーム終了していなければターン切替
    if not state.game_over:
        # ターン切替
        if state.chess_current_turn == 'white':
            # プレイヤーに連続ターンが残っている場合（「迅雷」から）、1つ消費してターンを維持
            cct = getattr(game, 'player_consecutive_turns', 0)
            if cct and cct > 0:
                try:
                    game.player_consecutive_turns -= 1
                except Exception:
                    setattr(game, 'player_consecutive_turns', max(0, cct-1))
                # chess_current_turn を white のままにしてプレイヤーが再度すぐに移動できるようにする
                state.chess_current_turn = 'white'
                # 移動ごとのフラグをリセットしてプレイヤーが再度移動できるようにする
                game.player_moved_this_turn = False
                # turn_active を True のままにしてカードプレイを許可
                game.turn_active = True
                game.log.append("迅雷効果: プレイヤーの連続ターンを1つ消費しました。")
            else:
                state.chess_current_turn = 'black'
                # 白の手番終了後、黒キングがチェック状態か確認（表示用なので凍結駒も含む）
                try:
                    if is_in_check_for_display and chess and is_in_check_for_display(chess.pieces, 'black'):
                        game.log.append("⚠ 黒キングがチェック状態です！")
                except Exception:
                    pass
                # 白の手番が終了したため、白に適用されている時間制限付き状態を減衰させる
                # （例: 氷結や封鎖などのターン消費をここで進める）
                try:
                    game.decay_statuses('white')
                except Exception:
                    pass
        else:
            state.chess_current_turn = 'white'
            # 黒の手番終了後、白キングがチェック状態か確認（表示用なので凍結駒も含む）
            try:
                if is_in_check_for_display and chess and is_in_check_for_display(chess.pieces, 'white'):
                    game.log.append("⚠ 白キングがチェック状態です！")
            except Exception:
                pass
            # 2ターン目以降: プレイヤーの手番になったらテロップ表示（Tキー不要でテロップのみ）
            try:
                if getattr(game, 'turn', 0) >= 1 and not getattr(game, 'turn_active', False) and getattr(game, 'pending', None) is None:
                    try:
                        state.turn_telop_msg = "YOUR TURN"
                        try:
                            state.turn_telop_until = _time_module.time() + 1.0
                        except Exception:
                            state.turn_telop_until = 0.0
                    except Exception:
                        pass
            except Exception:
                pass
            # 黒の手番が終了したため、黒に適用されている時間制限付き状態を減衰させる
            try:
                game.decay_statuses('black')
            except Exception:
                pass

    """Centralized helper that starts a player's card-game turn and shows the YOUR TURN telop.

    Use this wrapper instead of calling `game.start_turn()` directly from the UI so
    the visual telop is always displayed when a turn begins (manual or automatic).

    If `ai_end_msg` is provided, append that message to the game log after the
    turn-start processing. This ensures any draw logs produced by `game.start_turn()`
    appear before the AI end message when the AI triggers an automatic player turn.
    
    Args:
        ai_end_msg: Optional message from AI to append to log (currently not appended per UX request)
    """
    # Import globals dynamically to avoid circular imports
    import sys
    if 'B.B.C' in sys.modules:
        main_module = sys.modules['B.B.C']
    elif '__main__' in sys.modules:
        main_module = sys.modules['__main__']
    else:
        # Fallback: try to import directly
        try:
            import B.B.C as main_module  # type: ignore
        except ImportError:
            return False
    
    # Get global variables
    game = getattr(main_module, 'game', None)
    if game is None:
        return
    
    try:
        # start_turn handles PP reset and the 1-card draw
        if ai_end_msg:
            # If caller provided an AI-end message, capture new log entries
            # produced by start_turn so we can reorder draw-related lines
            prev_log_len = len(game.log)
            game.start_turn()
            # extract newly added entries
            new_entries = game.log[prev_log_len:]
            # identify draw-only entries produced by draw_to_hand() which start with "ドロー:"
            draw_entries = [e for e in new_entries if isinstance(e, str) and e.strip().startswith("ドロー:")]
            # keep other new entries (including the full "ターンN開始: ...ドロー...PP..." message)
            non_draw_new = [e for e in new_entries if e not in draw_entries]
            # rebuild game.log keeping only non-draw new entries (we will NOT append draw_entries or the AI-end message)
            try:
                game.log = game.log[:prev_log_len] + non_draw_new
            except Exception:
                # fallback: if direct assignment fails, leave as-is
                pass
        else:
            game.start_turn()
    except Exception:
        return
    
    # Update UI globals
    try:
        # Set turn telop message
        setattr(main_module, 'turn_telop_msg', "YOUR TURN")
        try:
            telop_until = _time_module.time() + 1.0
        except Exception:
            telop_until = 0.0
        setattr(main_module, 'turn_telop_until', telop_until)
    except Exception:
        pass
    
    try:
        # Reset log scroll offset to show latest messages
        setattr(main_module, 'log_scroll_offset', 0)
    except Exception:
        pass
    
    # If an AI-provided end message is requested, do NOT append it here
    # and also do NOT append the per-card "ドロー:" lines. This keeps the
    # full turn-start message ("ターンN開始: ...ドロー...PP...") intact while
    # hiding the AI-end and standalone draw-name lines as requested.


def attempt_start_turn():
    """[T]と同等のターン開始処理をUIやマウスからも呼べるように関数化。"""
    # Import globals dynamically to avoid circular imports
    import sys
    if 'B.B.C' in sys.modules:
        main_module = sys.modules['B.B.C']
    elif '__main__' in sys.modules:
        main_module = sys.modules['__main__']
    else:
        # Fallback: try to import directly
        try:
            import B.B.C as main_module  # type: ignore
        except ImportError:
            return
    
    # Get global variables
    game = getattr(main_module, 'game', None)
    if game is None:
        return
    
    chess_current_turn = getattr(main_module, 'chess_current_turn', 'white')
    cpu_wait = getattr(main_module, 'cpu_wait', False)
    
    # Check if there's a pending action
    if getattr(game, 'pending', None) is not None:
        game.log.append("操作待ち: 先に保留中の選択を完了してください。")
        return
    
    # 既に開始済み
    if getattr(game, 'turn_active', False):
        game.log.append("既にターンが開始されています。カードや駒の操作を行ってください。")
        try:
            setattr(main_module, 'notice_msg', "既にターンが開始されています。カードや駒の操作を行ってください。")
            try:
                notice_until = _time_module.time() + 1.0
            except Exception:
                notice_until = 0.0
            setattr(main_module, 'notice_until', notice_until)
        except Exception:
            pass
        return
    
    # チェス手番/AI待ち中は開始不可
    if chess_current_turn != 'white' or cpu_wait:
        game.log.append("チェスの操作またはAIの処理が完了していないため、ターンを開始できません。")
        try:
            setattr(main_module, 'notice_msg', "チェスの操作またはAIの処理が完了していないため、ターンを開始できません。")
            try:
                notice_until = _time_module.time() + 1.0
            except Exception:
                notice_until = 0.0
            setattr(main_module, 'notice_until', notice_until)
        except Exception:
            pass
        return
    
    # 開始
    start_player_turn()


def end_player_chess_move():
    """プレイヤーの駒移動後の処理（ターンアクティブ状態の更新）。
    
    プレイヤーが駒を動かした後、extra_movesがあればそれを消費し、
    なければturn_activeをFalseにして次のターン開始待ち状態にします。
    """
    # Import globals dynamically to avoid circular imports
    import sys
    if 'B.B.C' in sys.modules:
        main_module = sys.modules['B.B.C']
    elif '__main__' in sys.modules:
        main_module = sys.modules['__main__']
    else:
        # Fallback: try to import directly
        try:
            import B.B.C as main_module  # type: ignore
        except ImportError:
            return
    
    # Get global variables
    game = getattr(main_module, 'game', None)
    if game is None:
        return
    
    chess_current_turn = getattr(main_module, 'chess_current_turn', 'white')
    
    # If it was player's move, consume extra move or mark moved
    if chess_current_turn == 'white' and getattr(game, 'turn_active', False):
        try:
            if getattr(game.player, 'extra_moves_this_turn', 0) > 0:
                game.player.extra_moves_this_turn -= 1
                # keep turn active while extra moves remain
            else:
                game.player_moved_this_turn = True
                # consume the active turn so player must press T next time
                game.turn_active = False
        except Exception:
            # defensive: set flag
            game.player_moved_this_turn = True
            game.turn_active = False


def switch_turn():
    """ターン切り替え処理。
    
    駒移動後、ゲーム終了していなければターンを切り替えます。
    - プレイヤーターン終了時: decay_statuses('white')を呼び、AIターンへ
    - AIターン終了時: decay_statuses('black')を呼び、プレイヤーターンへ
    - 迅雷による連続ターンがある場合はそれを消費
    """
    # Import globals dynamically to avoid circular imports
    import sys
    if 'B.B.C' in sys.modules:
        main_module = sys.modules['B.B.C']
    elif '__main__' in sys.modules:
        main_module = sys.modules['__main__']
    else:
        # Fallback: try to import directly
        try:
            import B.B.C as main_module  # type: ignore
        except ImportError:
            return
    
    # Get global variables
    game = getattr(main_module, 'game', None)
    if game is None:
        return
    
    chess_current_turn = getattr(main_module, 'chess_current_turn', 'white')
    game_over = getattr(main_module, 'game_over', False)
    
    # Import chess_engine for piece check
    try:
        chess = getattr(main_module, 'chess', None)
        if chess is None:
            import chess_engine as chess
    except Exception:
        chess = None
    
    # Import is_in_check_for_display function
    try:
        is_in_check_for_display = getattr(main_module, 'is_in_check_for_display', None)
    except Exception:
        is_in_check_for_display = None
    
    # ゲーム終了していなければターン切替
    if not game_over:
        # ターン切替
        if chess_current_turn == 'white':
            # If player has consecutive-turns remaining (from '迅雷'), consume one and keep the turn
            cct = getattr(game, 'player_consecutive_turns', 0)
            if cct and cct > 0:
                try:
                    game.player_consecutive_turns -= 1
                except Exception:
                    setattr(game, 'player_consecutive_turns', max(0, cct-1))
                # keep chess_current_turn as white so player moves again immediately
                setattr(main_module, 'chess_current_turn', 'white')
                # reset per-move flags so player can move again
                game.player_moved_this_turn = False
                # ensure turn_active remains True so card plays are allowed
                game.turn_active = True
                game.log.append("迅雷効果: プレイヤーの連続ターンを1つ消費しました。")
            else:
                setattr(main_module, 'chess_current_turn', 'black')
                # 白の手番終了後、黒キングがチェック状態か確認（表示用なので凍結駒も含む）
                try:
                    if is_in_check_for_display and chess and is_in_check_for_display(chess.pieces, 'black'):
                        game.log.append("⚠ 黒キングがチェック状態です！")
                except Exception:
                    pass
                # 白の手番が終了したため、白に適用されている時間制限付き状態を減衰させる
                # （例: 氷結や封鎖などのターン消費をここで進める）
                try:
                    game.decay_statuses('white')
                except Exception:
                    pass
        else:
            setattr(main_module, 'chess_current_turn', 'white')
            # 黒の手番終了後、白キングがチェック状態か確認（表示用なので凍結駒も含む）
            try:
                if is_in_check_for_display and chess and is_in_check_for_display(chess.pieces, 'white'):
                    game.log.append("⚠ 白キングがチェック状態です！")
            except Exception:
                pass
            # 2ターン目以降: プレイヤーの手番になったらテロップ表示（Tキー不要でテロップのみ）
            try:
                if getattr(game, 'turn', 0) >= 1 and not getattr(game, 'turn_active', False) and getattr(game, 'pending', None) is None:
                    try:
                        setattr(main_module, 'turn_telop_msg', "YOUR TURN")
                        try:
                            telop_until = _time_module.time() + 1.0
                        except Exception:
                            telop_until = 0.0
                        setattr(main_module, 'turn_telop_until', telop_until)
                    except Exception:
                        pass
            except Exception:
                pass
