"""デバッグツール - 各種テスト用盤面設定とデバッグモード管理"""
import sys
import logging

logger = logging.getLogger(__name__)

# === DEBUG: 反撃チェックを「カード使用直後のみ許可」する検証モード ===
# F6 で ON/OFF。ON の間、実カード使用または F7 で
# game._debug_last_action_was_card を立てると、その次の1手に限り
# 「自身チェック中でも相手にチェックを与える手（反撃チェック）」を許可します。
DEBUG_COUNTER_CHECK_CARD_MODE = False


def set_debug_counter_check_mode(enabled: bool):
    """デバッグモードの設定"""
    global DEBUG_COUNTER_CHECK_CARD_MODE
    DEBUG_COUNTER_CHECK_CARD_MODE = enabled
    # メインモジュールのグローバル変数も更新
    try:
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        setattr(main_module, 'DEBUG_COUNTER_CHECK_CARD_MODE', enabled)
    except Exception:
        pass


def get_debug_counter_check_mode() -> bool:
    """デバッグモードの取得"""
    global DEBUG_COUNTER_CHECK_CARD_MODE
    return DEBUG_COUNTER_CHECK_CARD_MODE


def _debug_mark_card_played():
    """カードを使用した（またはF7相当）として次の1手に反撃チェックを許可する。
    デバッグモード（F6）がONのときのみ意味を持つ。
    """
    if get_debug_counter_check_mode():
        try:
            # メインモジュールのgameオブジェクトを取得
            if 'B.B.C' in sys.modules:
                main_module = sys.modules['B.B.C']
            elif '__main__' in sys.modules:
                main_module = sys.modules['__main__']
            else:
                return
            
            game = getattr(main_module, 'game', None)
            if game is None:
                return
            
            setattr(game, '_debug_last_action_was_card', True)
            try:
                logger.debug("カード使用扱いフラグをセット（次の1手）。")
            except Exception:
                pass
        except Exception:
            pass


def debug_setup_castling():
    """Set a simple board where white can castle both sides (no black pieces)."""
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        if chess is None or game is None:
            return
        
        chess.pieces.clear()
        # white king and rooks only
        chess.pieces.append(chess.Piece(7, 4, 'K', 'white'))
        chess.pieces.append(chess.Piece(7, 0, 'R', 'white'))
        chess.pieces.append(chess.Piece(7, 7, 'R', 'white'))
        # Ensure they are unmoved
        for p in chess.pieces:
            p.has_moved = False
        # Clear en passant and selections
        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        chess.en_passant_target = None
        logger.debug("キャスリング検証用の盤面をセットしました（白番）。e1のKとa1/h1のRのみ配置。")
    except Exception as e:
        logger.debug("debug_setup_castling failed: %s", e)


def debug_setup_en_passant():
    """Set a board where white can perform en passant to the right."""
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        if chess is None or game is None:
            return
        
        chess.pieces.clear()
        wp = chess.Piece(3, 4, 'P', 'white')  # e5
        bp = chess.Piece(3, 5, 'P', 'black')  # f5 (assume just moved two steps)
        chess.pieces.extend([wp, bp])
        # Set EP target square (the intermediate square the pawn passed)
        chess.en_passant_target = (2, 5)  # f6 from white perspective (row 2)
        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        logger.debug("アンパサン検証用の盤面をセットしました（白番）。e5の白Pがf6へアンパサン可能です。")
    except Exception as e:
        logger.debug("debug_setup_en_passant failed: %s", e)


def debug_setup_promotion():
    """Set a board where white pawn can promote next move."""
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        if chess is None or game is None:
            return
        
        chess.pieces.clear()
        wp = chess.Piece(1, 0, 'P', 'white')  # a7 -> a8 で昇格
        chess.pieces.append(wp)
        chess.en_passant_target = None
        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        logger.debug("昇格検証用の盤面をセットしました（白番）。a7の白Pをa8へ移動すると昇格ダイアログが出ます。")
    except Exception as e:
        logger.debug("debug_setup_promotion failed: %s", e)


def debug_reset_initial():
    """盤面を初期配置にリセット"""
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        if chess is None or game is None:
            return
        
        chess.pieces[:] = chess.create_pieces()
        chess.en_passant_target = None
        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        logger.debug("初期配置にリセットしました（白番）。")
    except Exception as e:
        logger.debug("debug_reset_initial failed: %s", e)


def debug_setup_checkmate():
    """簡単なチェックメイト検証用盤面（白を詰ませる）"""
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        if chess is None or game is None:
            return
        
        chess.pieces.clear()
        # 白キングを隅に追い詰める
        wk = chess.Piece(7, 0, 'K', 'white')  # a1
        # 黒のクイーンとルークで詰み
        bq = chess.Piece(6, 1, 'Q', 'black')  # b2
        br = chess.Piece(7, 1, 'R', 'black')  # b1
        chess.pieces.extend([wk, bq, br])
        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        chess.en_passant_target = None
        logger.debug("チェックメイト検証用の盤面をセットしました（白番・詰み状態）。")
    except Exception as e:
        logger.debug("debug_setup_checkmate failed: %s", e)


def debug_setup_counter_check_white():
    """白がチェック中で、次の1手で『自分は依然チェックだが相手にチェックを与える』反撃チェック手が存在する局面にセット。

    配置:
      - 白K: e1 (7,4)
      - 黒R: e8 (0,4) → 白Kに一直線でチェック中
      - 白R: b1 (7,1)
      - 黒K: a6 (2,0)

    このとき、白の手番で Rb1-b6 (7,1)->(2,1) は、
    白は依然Re8のチェック下にいるが、黒K a6 に横からチェックを与える『反撃チェック』になります。
    通常は不合法ですが、迅雷有効時、または[F6]デバッグモードONかつカード直後扱い（F7）でのみ合法。
    """
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        get_valid_moves = getattr(main_module, 'get_valid_moves', None)
        if chess is None or game is None or get_valid_moves is None:
            return
        
        # 盤面リセット
        chess.pieces.clear()
        chess.en_passant_target = None
        # 駒配置
        wk = chess.Piece(7, 4, 'K', 'white')  # e1
        br = chess.Piece(0, 4, 'R', 'black')  # e8 (白Kを縦にチェック)
        wr = chess.Piece(7, 1, 'R', 'white')  # b1 （b6へ上がるとa6の黒Kに横チェック）
        bk = chess.Piece(2, 0, 'K', 'black')  # a6
        chess.pieces.extend([wk, br, wr, bk])

        # UI/ターン関連を整える
        setattr(main_module, 'selected_piece', wr)
        try:
            moves = get_valid_moves(wr)
            setattr(main_module, 'highlight_squares', moves)
        except Exception:
            setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        try:
            game.turn_active = True
            game.player_moved_this_turn = False
        except Exception:
            pass
        try:
            logger.debug("反撃チェック検証用の盤面をセットしました（白番・白Kはe8の黒Rからチェック中）。")
            logger.debug("白Rb1→b6で黒Kにチェックを与える手は通常不合法ですが、迅雷有効時またはF6+F7時のみ合法です。")
        except Exception:
            pass
    except Exception as e:
        logger.debug("debug_setup_counter_check_white failed: %s", e)


def debug_setup_simul_check_start():
    """F7: 同時チェック開始のテスト局面をセット。
    
    両方のプレイヤーが互いにチェック状態にある局面を作成します。
    """
    try:
        # メインモジュールを取得
        if 'B.B.C' in sys.modules:
            main_module = sys.modules['B.B.C']
        elif '__main__' in sys.modules:
            main_module = sys.modules['__main__']
        else:
            return
        
        chess = getattr(main_module, 'chess', None)
        game = getattr(main_module, 'game', None)
        get_valid_moves = getattr(main_module, 'get_valid_moves', None)
        if chess is None or game is None:
            return
        
        # 盤面リセット
        chess.pieces.clear()
        chess.en_passant_target = None

        # 駒配置: 両者がチェック状態になるような配置
        wk = chess.Piece(7, 4, 'K', 'white')  # e1
        bk = chess.Piece(0, 4, 'K', 'black')  # e8
        wr = chess.Piece(0, 0, 'R', 'white')  # a8 (黒Kにチェック)
        br = chess.Piece(7, 0, 'R', 'black')  # a1 (白Kにチェック)
        chess.pieces.extend([wk, bk, wr, br])

        setattr(main_module, 'selected_piece', None)
        setattr(main_module, 'highlight_squares', [])
        setattr(main_module, 'chess_current_turn', 'white')
        
        try:
            game.turn_active = True
            game.player_moved_this_turn = False
        except Exception:
            pass

        # 同時チェック状態を設定
        try:
            setattr(main_module, 'simul_check_active', True)
            setattr(main_module, 'simul_white_result', 'pending')
            setattr(main_module, 'simul_black_result', 'pending')
            setattr(main_module, 'simul_white_deadline_turn', None)
            setattr(main_module, 'simul_black_deadline_turn', None)
        except Exception:
            pass

        try:
            logger.debug("同時チェック検証用の盤面をセットしました（白番）。")
            logger.debug("両者がチェック状態です。次の自分の手番開始までにチェックを解除する必要があります。")
        except Exception:
            pass
    except Exception as e:
        logger.debug("debug_setup_simul_check_start failed: %s", e)
