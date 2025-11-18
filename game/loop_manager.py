"""メインゲームループ管理モジュール

このモジュールは、メインゲームループの各種処理を担当します。
- イベント処理
- 同時チェック状態の更新
- 勝敗判定
- 保留中処理の実行
- AI思考処理
"""

import pygame
import sys
import time
import time as _ct_time
import random


def update_turn_tracking(chess_current_turn, game, chess):
    """ターン切替を検知してターンインデックスを更新する
    
    Args:
        chess_current_turn: 現在のターン色
        game: ゲームオブジェクト
        chess: chessモジュール
    
    Returns:
        dict: 更新された値 (turn_telop_msg, turn_telop_until)
    """
    result = {}
    
    # チェス手番の開始を検知（色が切り替わったフレーム）
    if globals().get('last_turn_color', None) != chess_current_turn:
        # 手番インデックス更新
        if chess_current_turn == 'white':
            globals()['white_turn_index'] = globals().get('white_turn_index', 0) + 1
        else:
            globals()['black_turn_index'] = globals().get('black_turn_index', 0) + 1
        globals()['last_turn_color'] = chess_current_turn

        # --- 追加: 白番に戻った際のテロップ表示（2ターン目以降） ---
        try:
            # 条件: 色が白に変わった、プレイヤーが既に1ターン以上開始している、
            # プロモーション選択や保留中のUIが無く、テロップを出すべきタイミング
            if chess_current_turn == 'white' and getattr(game, 'turn', 0) >= 1:
                if getattr(chess, 'promotion_pending', None) is None and getattr(game, 'pending', None) is None:
                    try:
                        result['turn_telop_msg'] = "YOUR TURN"
                        result['turn_telop_until'] = _ct_time.time() + 1.0
                    except Exception:
                        pass
        except Exception:
            pass
    
    return result


def update_simultaneous_check_deadlines(chess_current_turn, game, is_in_check_func, chess):
    """同時チェックの期限判定を更新する
    
    Args:
        chess_current_turn: 現在のターン色
        game: ゲームオブジェクト
        is_in_check_func: is_in_check関数
        chess: chessモジュール
    
    Returns:
        None (グローバル変数を直接更新)
    """
    if not chess:
        return
    
    # 同時チェック中なら、その色の期限判定を行う
    if globals().get('simul_check_active', False):
        try:
            # 同時チェック開始直後のターンでは判定しない（1手指すチャンスを与える）
            # 開始ターンを記録して、次のターン開始時に判定する
            if chess_current_turn == 'white' and globals().get('simul_white_result') == 'pending':
                # 白の期限ターンを記録（まだ設定されていなければ、次の白番開始で判定）
                if not globals().get('simul_white_deadline_turn'):
                    # 次の白番開始時に判定する（つまり今回はスキップ）
                    globals()['simul_white_deadline_turn'] = globals().get('white_turn_index', 0) + 1
                    game.log.append("同時チェック: 白は次の白番開始までにチェック解除が必要です。")
                elif globals().get('white_turn_index', 0) >= globals().get('simul_white_deadline_turn', 0):
                    # 期限到達：チェック状態で成否を確定
                    if is_in_check_func(chess.pieces, 'white'):
                        globals()['simul_white_result'] = 'failed'
                        game.log.append("同時チェック: 白は期限までにチェックを解除できませんでした（失敗）。")
                    else:
                        globals()['simul_white_result'] = 'cleared'
                        game.log.append("同時チェック: 白はチェックを解除しました（成功）。")
            elif chess_current_turn == 'black' and globals().get('simul_black_result') == 'pending':
                # 黒の期限ターンを記録（まだ設定されていなければ、次の黒番開始で判定）
                if not globals().get('simul_black_deadline_turn'):
                    globals()['simul_black_deadline_turn'] = globals().get('black_turn_index', 0) + 1
                    game.log.append("同時チェック: 黒は次の黒番開始までにチェック解除が必要です。")
                elif globals().get('black_turn_index', 0) >= globals().get('simul_black_deadline_turn', 0):
                    # 期限到達：チェック状態で成否を確定
                    if is_in_check_func(chess.pieces, 'black'):
                        globals()['simul_black_result'] = 'failed'
                        game.log.append("同時チェック: 黒は期限までにチェックを解除できませんでした（失敗）。")
                    else:
                        globals()['simul_black_result'] = 'cleared'
                        game.log.append("同時チェック: 黒はチェックを解除しました（成功）。")
        except Exception:
            pass


def check_simultaneous_check_victory(game, game_over, chess):
    """同時チェックの勝敗判定を行う
    
    Args:
        game: ゲームオブジェクト
        game_over: 現在のゲームオーバー状態
        chess: chessモジュール
    
    Returns:
        tuple: (game_over, game_over_winner) 更新された値
    """
    if not chess:
        return game_over, None
    
    # 双方結果が出たら決着
    wres = globals().get('simul_white_result')
    bres = globals().get('simul_black_result')
    game_over_winner = None
    
    if wres in ('cleared','failed') and bres in ('cleared','failed') and not game_over:
        # 両者のキングの存在確認（取られていないか）
        white_king_exists = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
        black_king_exists = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
        
        # 両者のキングが取られている場合は無条件で引き分け（優先順位 最上位）
        if not white_king_exists and not black_king_exists:
            game_over = True
            game_over_winner = 'draw'
            game.log.append("同時チェック: 両者のキングが取られました。引き分け。")
        # 白のキングのみ取られた場合は黒の勝利
        elif not white_king_exists:
            game_over = True
            game_over_winner = 'black'
            game.log.append("同時チェック: 白のキングが取られました。黒の勝利！")
        # 黒のキングのみ取られた場合は白の勝利
        elif not black_king_exists:
            game_over = True
            game_over_winner = 'white'
            game.log.append("同時チェック: 黒のキングが取られました。白の勝利！")
        # 両者のキングが残っている場合
        elif white_king_exists and black_king_exists:
            # 両者とも解除失敗の場合は引き分け
            if wres == 'failed' and bres == 'failed':
                game_over = True
                game_over_winner = 'draw'
                game.log.append("同時チェック: 両者とも解除できませんでした。引き分け。")
            # 白のみ解除成功
            elif wres == 'cleared' and bres == 'failed':
                game_over = True
                game_over_winner = 'white'
                game.log.append("同時チェック: 白のみ解除成功。白の勝利！")
            # 黒のみ解除成功
            elif wres == 'failed' and bres == 'cleared':
                game_over = True
                game_over_winner = 'black'
                game.log.append("同時チェック: 黒のみ解除成功。黒の勝利！")
            else:
                # 両者解除成功 → 通常続行
                game.log.append("同時チェック: 両者解除成功。通常ルールに復帰します。")
        
        if game_over:
            # 終了したら状態クリア
            globals()['simul_check_active'] = False
            globals()['simul_white_deadline_turn'] = None
            globals()['simul_black_deadline_turn'] = None
        else:
            # 続行の場合も状態をクリア
            globals()['simul_check_active'] = False
            globals()['simul_white_deadline_turn'] = None
            globals()['simul_black_deadline_turn'] = None
        globals()['simul_white_result'] = 'none'
        globals()['simul_black_result'] = 'none'
    
    return game_over, game_over_winner


def detect_new_simultaneous_check(game, is_in_check_func, chess):
    """新たに同時チェック状態に突入したかを検出する
    
    Args:
        game: ゲームオブジェクト
        is_in_check_func: is_in_check関数
        chess: chessモジュール
    
    Returns:
        None (グローバル変数を直接更新)
    """
    if not chess:
        return
    
    try:
        white_in_check = is_in_check_func(chess.pieces, 'white')
        black_in_check = is_in_check_func(chess.pieces, 'black')
        if white_in_check and black_in_check and not globals().get('simul_check_active', False):
            globals()['simul_check_active'] = True
            globals()['simul_white_result'] = 'pending'
            globals()['simul_black_result'] = 'pending'
            # 期限ターンをリセット（次のターン開始時に設定される）
            globals()['simul_white_deadline_turn'] = None
            globals()['simul_black_deadline_turn'] = None
            # 期限は「次の自分の手番開始」。カウンタは手番開始検知で進むのでここではログのみ。
            game.log.append("同時チェック状態に突入：両者は次の自分の手番開始までにチェック解除が必要です。")
    except Exception:
        pass


def check_king_capture_victory(chess_current_turn, game, game_over, chess):
    """キング取得による勝利判定を行う
    
    Args:
        chess_current_turn: 現在のターン色
        game: ゲームオブジェクト
        game_over: 現在のゲームオーバー状態
    
    Returns:
        tuple: (game_over, game_over_winner) 更新された値
    """
    if not chess:
        return game_over, None
    
    game_over_winner = None
    
    # 迅雷使用中はキング取得判定を常に行う（同時チェック中でも即座に勝敗判定）
    if chess_current_turn == 'white':
        lightning_active = getattr(game, 'player_consecutive_turns', 0) > 0
    else:
        lightning_active = globals().get('ai_consecutive_turns', 0) > 0
    
    # キング取得判定: 迅雷使用中は常に、通常時は同時チェック中でなければ判定
    should_check_kings = lightning_active or not globals().get('simul_check_active', False)
    
    if should_check_kings:
        white_king = any(p.name == 'K' and p.color == 'white' for p in chess.pieces)
        black_king = any(p.name == 'K' and p.color == 'black' for p in chess.pieces)
        
        # 両キング取得テストモード（F9）の処理
        if globals().get('dual_king_capture_test', False):
            # まず両者のキング不在を最優先で引き分け判定
            if not white_king and not black_king:
                game_over = True
                game_over_winner = 'draw'
                game.log.append("両者のキングが取られました。引き分け。")
                # テストモードを終了
                globals()['dual_king_capture_test'] = False
                globals()['first_king_captured'] = None
            elif not white_king:
                # 白Kが取られた場合
                if globals().get('first_king_captured') is None:
                    # 最初のキング取得
                    globals()['first_king_captured'] = 'white'
                    game.log.append("[テストモード] 白のキングが取られました。黒の手番を続けます...")
                else:
                    # 2つ目のキングが取られた（黒Kは既に取られている）
                    game_over = True
                    game_over_winner = 'draw'
                    game.log.append("両者のキングが取られました。引き分け。")
                    globals()['dual_king_capture_test'] = False
                    globals()['first_king_captured'] = None
            elif not black_king:
                # 黒Kが取られた場合
                if globals().get('first_king_captured') is None:
                    # 最初のキング取得
                    globals()['first_king_captured'] = 'black'
                    game.log.append("[テストモード] 黒のキングが取られました。白の手番を続けます...")
                else:
                    # 2つ目のキングが取られた（白Kは既に取られている）
                    game_over = True
                    game_over_winner = 'draw'
                    game.log.append("両者のキングが取られました。引き分け。")
                    globals()['dual_king_capture_test'] = False
                    globals()['first_king_captured'] = None
        else:
            # 通常モード: 既存の処理
            # まず両者のキング不在を最優先で引き分け判定
            if not white_king and not black_king:
                game_over = True
                game_over_winner = 'draw'
                game.log.append("両者のキングが取られました。引き分け。")
                if globals().get('simul_check_active', False):
                    clear_simultaneous_check_state()
            elif not white_king:
                game_over = True
                game_over_winner = 'black'
                game.log.append("YOU LOSE！黒の勝利！")
                # 同時チェック状態をクリア
                if globals().get('simul_check_active', False):
                    clear_simultaneous_check_state()
            elif not black_king:
                game_over = True
                game_over_winner = 'white'
                game.log.append("YOU WIN！白の勝利")
                # 同時チェック状態をクリア
                if globals().get('simul_check_active', False):
                    clear_simultaneous_check_state()
                globals()['simul_white_result'] = 'none'
                globals()['simul_black_result'] = 'none'
    
    return game_over, game_over_winner


def clear_simultaneous_check_state():
    """同時チェック状態をクリアする"""
    globals()['simul_check_active'] = False
    globals()['simul_white_deadline_turn'] = None
    globals()['simul_black_deadline_turn'] = None
    globals()['simul_white_result'] = 'none'
    globals()['simul_black_result'] = 'none'


def check_checkmate_and_stalemate(chess_current_turn, game, game_over, has_legal_moves_func, is_in_check_func, chess):
    """チェックメイトとステイルメイトを判定する
    
    Args:
        chess_current_turn: 現在のターン色
        game: ゲームオブジェクト
        game_over: 現在のゲームオーバー状態
        has_legal_moves_func: has_legal_moves_with_cards関数
        is_in_check_func: is_in_check関数
        chess: chessモジュール
    
    Returns:
        tuple: (game_over, game_over_winner) 更新された値
    """
    if not chess:
        return game_over, None
    
    game_over_winner = None
    
    # チェックメイトとステイルメイトの判定（同時チェック中はスキップ）
    if not game_over and not globals().get('simul_check_active', False):
        # どちらかが詰みの場合も勝利判定（カード効果込みの合法手判定を使用）
        if not has_legal_moves_func('white') and is_in_check_func(chess.pieces, 'white'):
            game_over = True
            game_over_winner = 'black'
            game.log.append("YOU LOSE！黒の勝利！")
        elif not has_legal_moves_func('black') and is_in_check_func(chess.pieces, 'black'):
            game_over = True
            game_over_winner = 'white'
            game.log.append("YOU WIN！白の勝利！")
        # ステイルメイト（合法手がないがチェックでない）の判定（カード効果込み）
        elif not has_legal_moves_func(chess_current_turn) and not is_in_check_func(chess.pieces, chess_current_turn):
            game_over = True
            game_over_winner = 'draw'
            game.log.append("ステイルメイト（引き分け）")
    
    return game_over, game_over_winner


def process_pending_actions(game, ai_player, chess_current_turn):
    """保留中の処理を実行する
    
    Args:
        game: ゲームオブジェクト
        ai_player: AIプレイヤーオブジェクト
        chess_current_turn: 現在のターン色
    
    Returns:
        str: 更新されたチェス現在ターン（ターンスキップの場合）
    """
    if getattr(game, 'pending', None) is None:
        return chess_current_turn
    
    # ハンです☆: 相手の手札をランダムで墓地に送る
    if game.pending.kind == 'discard_opponent_hand':
        try:
            source_color = game.pending.info.get('source_color') if game.pending and isinstance(game.pending.info, dict) else None
            # Only block if the effect is incoming (source != target)
            if source_color is not None and source_color == 'black':
                # effect originated from AI targeting AI -> shouldn't happen, but skip blocking
                pass
            # target is ai_player (black)
            if getattr(ai_player, 'iron_wall_active', False) and source_color != 'black':
                ai_player.iron_wall_active = False
                game.log.append("『鉄壁』が効果を防いだ（相手の『ハンです☆』）。")
                game.pending = None
            else:
                if ai_player.hand.cards:
                    idx = random.randrange(len(ai_player.hand.cards))
                    discarded_card = ai_player.hand.cards[idx]
                    ai_player.hand.remove_at(idx)
                    ai_player.graveyard.append(discarded_card)
                    game.log.append(f"『ハンです☆』: 相手の手札から『{discarded_card.name}』をランダムで墓地に送りました。")
                else:
                    game.log.append("『ハンです☆』: 相手の手札が空です。")
                game.pending = None
        except Exception:
            # on error, clear pending to avoid locking UI
            game.pending = None
    
    # 命がけのギャンブル: ルーク・キング以外の駒をクイーンに変える
    elif game.pending.kind == 'gamble_promote':
        chess_current_turn = process_gamble_promote(game, ai_player, chess_current_turn)
    
    return chess_current_turn


def process_gamble_promote(game, ai_player, chess_current_turn):
    """命がけのギャンブルの処理を実行する
    
    Args:
        game: ゲームオブジェクト
        ai_player: AIプレイヤーオブジェクト
        chess_current_turn: 現在のターン色
    
    Returns:
        str: 更新されたチェス現在ターン
    """
    chess_module = globals().get('chess')
    if not chess_module:
        game.pending = None
        return chess_current_turn
    
    target_color = game.pending.info.get('target_color', 'white')
    success = game.pending.info.get('success', False)

    promoted_count = 0
    pieces = getattr(chess_module, 'pieces', []) or []

    # Determine the target player object so we can honor iron_wall
    try:
        target_player = game.player if target_color == 'white' else ai_player
    except Exception:
        target_player = None

    # If target has iron_wall_active, block the effect entirely
    try:
        source_color = game.pending.info.get('source_color') if game.pending and isinstance(game.pending.info, dict) else None
        if target_player is not None and getattr(target_player, 'iron_wall_active', False) and source_color != target_color:
            # Only consume iron_wall if the effect is incoming (origin color != target color)
            target_player.iron_wall_active = False
            game.log.append("『鉄壁』が効果を防いだ（命がけのギャンブル）。")
            game.pending = None
            # Skip promotion processing
            promoted_count = 0
        else:
            for piece in pieces:
                try:
                    if isinstance(piece, dict):
                        p_color = piece.get('color')
                        p_kind = piece.get('kind') or piece.get('name')
                        if p_color == target_color and p_kind not in ['K', 'R']:
                            # update both name and kind for consistency
                            piece['kind'] = 'Q'
                            piece['name'] = 'Q'
                            promoted_count += 1
                    else:
                        p_color = getattr(piece, 'color', None)
                        # some codebase uses .name for piece type
                        p_kind = getattr(piece, 'kind', None) or getattr(piece, 'name', None)
                        if p_color == target_color and p_kind not in ['K', 'R']:
                            # set both attributes where possible so rendering and checks pick it up
                            try:
                                setattr(piece, 'name', 'Q')
                            except Exception:
                                pass
                            try:
                                setattr(piece, 'kind', 'Q')
                            except Exception:
                                try:
                                    piece.kind = 'Q'
                                except Exception:
                                    pass
                            promoted_count += 1
                except Exception as perr:
                    # log per-piece errors but continue
                    try:
                        import traceback
                        print('DEBUG: error promoting piece in gamble_promote:')
                        traceback.print_exc()
                    except Exception:
                        print(f'DEBUG: error promoting piece: {perr}')
                    continue
    except Exception as e:
        # If anything unexpected happens during promotion handling, log and clear pending
        try:
            import traceback
            print('DEBUG: exception during gamble_promote overall handling:')
            traceback.print_exc()
        except Exception:
            print(f'DEBUG: exception during gamble_promote overall handling: {e}')
        game.pending = None
        return chess_current_turn
    # end of promotion loop / iron_wall handling

    if success:
        game.log.append(f"『命がけのギャンブル』成功！自分の{promoted_count}個の駒がクイーンに昇格しました！")
    else:
        game.log.append(f"『命がけのギャンブル』失敗...相手の{promoted_count}個の駒がクイーンに昇格しました...")

    # ターンスキップは失敗時のみ（要求に基づく変更）
    if not success:
        if chess_current_turn == 'white':
            chess_current_turn = 'black'
            # cpu_waitはmain_loopで設定される
            globals()['_skip_turn_cpu_wait'] = True
            # mark the player's card-game turn as consumed so the
            # automatic player-turn start will occur after the AI finishes.
            try:
                game.turn_active = False
                game.player_moved_this_turn = True
                # force the auto-start after AI finishes in case
                # turn accounting elsewhere prevents the normal check
                game._force_start_player_after_ai = True
            except Exception:
                pass
            game.log.append("自ターンをスキップします。")

    game.pending = None
    return chess_current_turn
