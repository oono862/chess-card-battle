"""キーボード入力処理モジュール

このモジュールは、ゲーム内のキーボード入力を処理します。
- ゲーム終了時の操作
- ログ表示とスクロール
- ターン開始
- 墓地・相手手札表示
- デバッグキー
- カード使用(1-9キー)
- 確認ダイアログ(Y/N)
- 捨て札確定(D)
"""

import pygame
import sys
import time as _ct_time


def handle_keydown(key, game_state_globals):
    """キーボード入力を処理する
    
    Args:
        key: pygame.K_* キーコード
        game_state_globals: グローバル状態変数を含む辞書
            - game: ゲームオブジェクト
            - chess: チェスエンジンモジュール
            - game_over: ゲーム終了フラグ
            - cpu_wait: CPU待機フラグ
            - show_log: ログ表示フラグ
            - log_scroll_offset: ログスクロールオフセット
            - show_grave: 墓地表示フラグ
            - show_opponent_hand: 相手手札表示フラグ
            - enlarged_card_index: 拡大表示中のカードインデックス
            - notice_msg, notice_until: 通知メッセージ
            - restart_game: ゲーム再起動関数
            - attempt_start_turn: ターン開始試行関数
            - get_gimmick_activation_mode: ギミック発動モード取得関数
            - _debug_mark_card_played: デバッグマーク関数
            - debug_* : デバッグセットアップ関数群
    
    Returns:
        dict: 更新された状態変数 (show_log, log_scroll_offset, show_grave, show_opponent_hand, notice_msg, notice_until)
    """
    # 状態変数を展開
    game = game_state_globals['game']
    chess = game_state_globals['chess']
    game_over = game_state_globals['game_over']
    cpu_wait = game_state_globals.get('cpu_wait', False)
    show_log = game_state_globals.get('show_log', False)
    log_scroll_offset = game_state_globals.get('log_scroll_offset', 0)
    show_grave = game_state_globals.get('show_grave', False)
    show_opponent_hand = game_state_globals.get('show_opponent_hand', False)
    enlarged_card_index = game_state_globals.get('enlarged_card_index', None)
    enlarged_card_name = game_state_globals.get('enlarged_card_name', None)
    notice_msg = game_state_globals.get('notice_msg', None)
    notice_until = game_state_globals.get('notice_until', 0.0)
    
    restart_game = game_state_globals.get('restart_game')
    attempt_start_turn = game_state_globals.get('attempt_start_turn')
    get_gimmick_activation_mode = game_state_globals.get('get_gimmick_activation_mode')
    _debug_mark_card_played = game_state_globals.get('_debug_mark_card_played')
    
    # デバッグ関数
    debug_setup_castling = game_state_globals.get('debug_setup_castling')
    debug_setup_en_passant = game_state_globals.get('debug_setup_en_passant')
    debug_setup_promotion = game_state_globals.get('debug_setup_promotion')
    debug_reset_initial = game_state_globals.get('debug_reset_initial')
    debug_setup_checkmate = game_state_globals.get('debug_setup_checkmate')
    debug_setup_counter_check_white = game_state_globals.get('debug_setup_counter_check_white')
    debug_setup_simul_check_start = game_state_globals.get('debug_setup_simul_check_start')
    set_debug_counter_check_mode = game_state_globals.get('set_debug_counter_check_mode')
    get_debug_counter_check_mode = game_state_globals.get('get_debug_counter_check_mode')
    
    # 結果を格納する辞書
    result = {}
    
    # ゲーム終了時のキー操作
    if game_over:
        if key == pygame.K_r:
            if restart_game:
                restart_game()
            return result
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit(0)
        return result  # ゲーム終了時は他のキー操作を無効化
    
    if key == pygame.K_ESCAPE:
        pygame.quit()
        sys.exit(0)
    
    # ログ表示切替
    if key == pygame.K_l:
        show_log = not show_log
        result['show_log'] = show_log
        return result
    
    # ログスクロール（ログ表示中のみ）
    if show_log:
        if key == pygame.K_UP:
            log_scroll_offset += 1
            result['log_scroll_offset'] = log_scroll_offset
            return result
        if key == pygame.K_DOWN:
            log_scroll_offset = max(0, log_scroll_offset - 1)
            result['log_scroll_offset'] = log_scroll_offset
            return result
    
    if key == pygame.K_t:
        if attempt_start_turn:
            attempt_start_turn()
        return result
    
    if key == pygame.K_g:
        # 墓地表示切替（保留中でも閲覧だけは可能）
        prev = show_grave
        show_grave = not show_grave
        # 開くときは相手手札を閉じる（クリック時と同じ排他制御）
        if not prev and show_grave:
            show_opponent_hand = False
        result['show_grave'] = show_grave
        result['show_opponent_hand'] = show_opponent_hand
        return result
    
    if key == pygame.K_h:
        # 相手の手札表示切替（クリック時と同じ排他制御を反映）
        prev = show_opponent_hand
        show_opponent_hand = not show_opponent_hand
        # 開くときは墓地を閉じる
        if not prev and show_opponent_hand:
            show_grave = False
        result['show_opponent_hand'] = show_opponent_hand
        result['show_grave'] = show_grave
        return result

    # --- DEBUG: 盤面セットショートカット ---
    if key == pygame.K_F1:
        if debug_setup_castling:
            debug_setup_castling()
        return result
    if key == pygame.K_F2:
        if debug_setup_en_passant:
            debug_setup_en_passant()
        return result
    if key == pygame.K_F3:
        if debug_setup_promotion:
            debug_setup_promotion()
        return result
    if key == pygame.K_F4:
        if debug_reset_initial:
            debug_reset_initial()
        return result
    if key == pygame.K_F5:
        if debug_setup_checkmate:
            debug_setup_checkmate()
        return result
    if key == pygame.K_F6:
        # 反撃チェックデバッグ盤面
        if debug_setup_counter_check_white:
            debug_setup_counter_check_white()
        return result
    if key == pygame.K_F7:
        # 同時チェックデバッグ盤面
        if debug_setup_simul_check_start:
            debug_setup_simul_check_start()
        return result
    if key == pygame.K_F8:
        # 反撃チェックカードモード切替
        if set_debug_counter_check_mode and get_debug_counter_check_mode:
            current = get_debug_counter_check_mode()
            new_mode = not current
            set_debug_counter_check_mode(new_mode)
            mode_str = "有効" if new_mode else "無効"
            if game:
                try:
                    game.log.append(f"反撃チェックカード強制発動モード: {mode_str}")
                except:
                    pass
        return result
    if key == pygame.K_F9:
        # 両キング取得テストモード切替
        current = game_state_globals.get('dual_king_capture_test', False)
        new_mode = not current
        result['dual_king_capture_test'] = new_mode
        mode_str = "有効" if new_mode else "無効"
        if game:
            try:
                game.log.append(f"両キング取得テストモード: {mode_str}")
            except:
                pass
        return result
    
    # 1-9 キーでカード使用
    if pygame.K_1 <= key <= pygame.K_9:
        idx = key - pygame.K_1
        # If player chose "カードをクリックして発動" (i.e. not number_key top-mode),
        # disable numeric-key activation for normal play. Permit numeric keys for
        # promotion selection or when a pending 'discard' selection is active.
        if get_gimmick_activation_mode and get_gimmick_activation_mode() != 'number_key':
            # allow promotion/discard flows to still use numeric keys
            if not (chess.promotion_pending is not None and 0 <= idx <= 3) and not (
                getattr(game, 'pending', None) is not None and getattr(game.pending, 'kind', None) == 'discard'
            ):
                msg = "カードをクリックで発動"
                game.log.append(msg)
                try:
                    notice_msg = msg
                    notice_until = _ct_time.time() + 1.0
                    result['notice_msg'] = notice_msg
                    result['notice_until'] = notice_until
                except Exception:
                    pass
                return result
        # プロモーション選択中ならカード使用を抑止して昇格選択に使う
        if chess.promotion_pending is not None and 0 <= idx <= 3:
            opts = ['Q','R','B','N']
            sel = opts[idx]
            piece = chess.promotion_pending['piece']
            piece.name = sel
            game.log.append(f"昇格: ポーンを{sel}に昇格させました。")
            chess.promotion_pending = None
            return result
        # pending中: discardのみ選択を許可し、それ以外は行動不可
        if getattr(game, 'pending', None) is not None:
            if game.pending.kind == 'discard':
                game.pending.info['selected'] = idx
                # カード名を取得してログに表示
                if 0 <= idx < len(game.player.hand.cards):
                    card_name = game.player.hand.cards[idx].name
                    game.log.append(f"捨てるカードとして『{card_name}』を選択。[D]で確定")
                else:
                    game.log.append(f"捨てるカードとして手札{idx+1}番を選択。[D]で確定")
            else:
                game.log.append("操作待ち: 先に保留中の選択を完了してください。")
            return result
        # ターン開始前はカード使用不可（既存のメッセージを表示）
        if not getattr(game, 'turn_active', False):
            msg = "ターンが開始されていませんTキーでターンを開始してください"
            game.log.append(msg)
            try:
                notice_msg = msg
                notice_until = _ct_time.time() + 1.0
                result['notice_msg'] = notice_msg
                result['notice_until'] = notice_until
            except Exception:
                pass
            return result
        ok, msg = game.play_card(idx)
        if not ok:
            game.log.append(msg)
        else:
            # [DEBUG] カード直後のみ許可モード：カード使用扱いフラグを立てる
            if _debug_mark_card_played:
                _debug_mark_card_played()
        log_scroll_offset = 0  # カード使用後は最新ログへ
        result['log_scroll_offset'] = log_scroll_offset
        return result

    # Y/N: 確認ダイアログへの回答
    if getattr(game, 'pending', None) is not None and game.pending.kind == 'confirm':
        if key in (pygame.K_y, pygame.K_RETURN):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                # 墓地ルーレットの確認「はい」→カードを実際に消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除、墓地へ
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。墓地が空のため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                    if _debug_mark_card_played:
                        _debug_mark_card_played()
                else:
                    game.log.append("確認: はい → 効果なし（墓地が空）")
            elif confirm_id == 'confirm_second_lightning_overwrite':
                # 迅雷2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                    if _debug_mark_card_played:
                        _debug_mark_card_played()
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_second_storm_overwrite':
                # 暴風2回目使用の確認「はい」→通常通り効果を適用してカード消費
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    # PP消費、手札から削除
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    # 効果適用（上書きだが明示的に実行）
                    try:
                        msg = card.effect(game, game.player)
                    except Exception:
                        msg = "効果の適用に失敗しました。"
                    # 墓地へ
                    game.player.graveyard.append(card)
                    # ログ
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。{msg} PPは{game.player.pp_current}/{game.player.pp_max}。")
                    if _debug_mark_card_played:
                        _debug_mark_card_played()
                else:
                    game.log.append("確認: はい")
            elif confirm_id == 'confirm_heat_no_frozen':
                # 灼熱で凍結駒がない場合の確認「はい」→カードを消費して墓地へ
                hand_idx = game.pending.info.get('hand_index')
                if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                    card = game.player.hand.cards[hand_idx]
                    game.player.spend_pp(card.cost)
                    game.player.hand.remove_at(hand_idx)
                    game.player.graveyard.append(card)
                    game.log.append(f"『{card.name}』（コスト{card.cost}）を使用。凍結駒がないため効果なし。PPは{game.player.pp_current}/{game.player.pp_max}。")
                    if _debug_mark_card_played:
                        _debug_mark_card_played()
                else:
                    game.log.append("確認: はい → 効果なし")
            else:
                # その他の確認（通常の墓地ルーレット実行など）
                game.log.append("確認: はい")
                # 保留されていた効果を実行
                if game.pending.info.get('execute_on_confirm'):
                    hand_idx = game.pending.info.get('hand_index')
                    if hand_idx is not None and 0 <= hand_idx < len(game.player.hand.cards):
                        # 墓地が空でない場合の墓地ルーレット実行
                        import random
                        if game.player.graveyard:
                            idx = random.randrange(len(game.player.graveyard))
                            recovered = game.player.graveyard.pop(idx)
                            game.player.hand.add(recovered)
                            game.log.append(f"墓地から『{recovered.name}』を回収。")
            game.pending = None
            log_scroll_offset = 0
            result['log_scroll_offset'] = log_scroll_offset
            return result
        if key in (pygame.K_n, pygame.K_ESCAPE):
            confirm_id = game.pending.info.get('id')
            if confirm_id == 'confirm_grave_roulette_empty':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            elif confirm_id == 'confirm_heat_no_frozen':
                game.log.append("確認: いいえ → キャンセル（カードは消費されません）")
            else:
                game.log.append("確認: いいえ → キャンセル（効果なし）")
            game.pending = None
            log_scroll_offset = 0
            result['log_scroll_offset'] = log_scroll_offset
            return result
    
    # Dキー: discard pending の確定
    if key == pygame.K_d and getattr(game, 'pending', None) is not None and game.pending.kind == 'discard':
        sel = game.pending.info.get('selected')
        if isinstance(sel, int):
            removed = game.player.hand.remove_at(sel)
            if removed:
                game.player.graveyard.append(removed)
                game.log.append(f"『{removed.name}』を捨てました。")
                
                # If there's an execute_after_discard instruction, perform it now
                ex = game.pending.info.get('execute_after_discard')
                if ex:
                    draw_n = int(ex.get('draw', 0)) if ex.get('draw', 0) else 0
                    if draw_n > 0:
                        res = game.draw_to_hand(draw_n)
                        items = []
                        for c, added in res:
                            if c is None:
                                continue
                            items.append(c.name if added else f"{c.name}(墓地)")
                        if items:
                            game.log.append("ドロー: " + ", ".join(items))
                # 保留をクリア
                game.pending = None
                log_scroll_offset = 0  # 保留解決後は最新ログへ
                result['log_scroll_offset'] = log_scroll_offset
                return result
            else:
                game.log.append("捨てるカードを選択してください。")
                # don't clear pending so player can choose again
                return result
        else:
            game.log.append("捨てるカードが選択されていません。")
            # keep pending active so player can choose a card and press D
            return result
    
    return result
