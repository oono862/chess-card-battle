"""チェスルール・ロジックモジュール

このモジュールは、チェスのルール判定とカード効果を考慮した移動生成を提供します。
- チェック判定（表示用/ゲームルール用）
- 駒の移動可能範囲計算
- 合法手判定
"""


def is_in_check_for_display(pcs, color, chess_module):
    """
    表示用のチェック判定。
    - 凍結は無視（表示は出す）
    - ルールの合法手生成に依存せず、幾何学的な"攻撃"で判定する
      （駒の種類ごとの攻撃方向・到達可能マスでキングが射程内かを見る）
    
    Args:
        pcs: 駒のリスト
        color: チェック判定する色 ('white' or 'black')
        chess_module: chess_engineモジュール（駒取得用）
    
    Returns:
        bool: チェック状態ならTrue
    """
    # キング位置
    king = None
    for p in pcs:
        try:
            if p.name == 'K' and p.color == color:
                king = p
                break
        except Exception:
            if isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color:
                king = p
                break
    if not king:
        return False

    # 安全な属性/辞書アクセス
    def _pget(obj, key):
        try:
            return getattr(obj, key)
        except Exception:
            try:
                return obj.get(key)
            except Exception:
                return None

    kr = _pget(king, 'row')
    kc = _pget(king, 'col')

    opponent = 'black' if color == 'white' else 'white'

    # 盤上の駒を取得する関数
    def piece_at(r, c):
        try:
            return chess_module.get_piece_at(r, c)
        except Exception:
            # フォールバック（pcsを走査）
            for q in pcs:
                rr = _pget(q, 'row')
                cc = _pget(q, 'col')
                if rr == r and cc == c:
                    return q
            return None

    # 1) ナイトの攻撃
    for dr, dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
        pr, pc = kr + dr, kc + dc
        p = piece_at(pr, pc)
        if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'N':
            return True

    # 2) ポーンの攻撃
    pawn_dirs = [(-1, -1), (-1, 1)] if opponent == 'white' else [(1, -1), (1, 1)]
    for dr, dc in pawn_dirs:
        pr, pc = kr + dr, kc + dc
        p = piece_at(pr, pc)
        if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'P':
            return True

    # 3) キングの隣接攻撃
    for dr in (-1,0,1):
        for dc in (-1,0,1):
            if dr == 0 and dc == 0:
                continue
            pr, pc = kr + dr, kc + dc
            p = piece_at(pr, pc)
            if p and _pget(p, 'color') == opponent and _pget(p, 'name') == 'K':
                return True

    # 4) 直線・斜めのレイ（R/B/Q）
    ray_dirs = [
        (-1,0),(1,0),(0,-1),(0,1),   # R, Q
        (-1,-1),(-1,1),(1,-1),(1,1)  # B, Q
    ]
    for dr, dc in ray_dirs:
        pr, pc = kr + dr, kc + dc
        while 0 <= pr < 8 and 0 <= pc < 8:
            p = piece_at(pr, pc)
            if p is None:
                pr += dr
                pc += dc
                continue
            pcol = _pget(p, 'color')
            pname = _pget(p, 'name')
            if pcol != opponent:
                break
            # この方向に応じて当たり判定
            if dr == 0 or dc == 0:  # 縦横
                if pname in ('R', 'Q'):
                    return True
            if dr != 0 and dc != 0:  # 斜め
                if pname in ('B', 'Q'):
                    return True
            break

    return False


def is_in_check(pcs, color, game_obj):
    """
    ゲームルール用のチェック判定。
    凍結されている駒は動けないため、その駒からの攻撃は無視する。
    
    Args:
        pcs: 駒のリスト
        color: チェック判定する色 ('white' or 'black')
        game_obj: ゲームオブジェクト（凍結情報取得用）
    
    Returns:
        bool: チェック状態ならTrue
    """
    # find king of color
    king = None
    for p in pcs:
        if (hasattr(p, 'name') and p.name == 'K' and p.color == color) or \
           (isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color):
            king = p
            break
    if not king:
        return False
    
    king_row = king.row if hasattr(king, 'row') else king.get('row')
    king_col = king.col if hasattr(king, 'col') else king.get('col')
    king_pos = (king_row, king_col)
    opponent = 'black' if color == 'white' else 'white'
    
    frozen = getattr(game_obj, 'frozen_pieces', {})

    for p in pcs:
        p_color = p.color if hasattr(p, 'color') else p.get('color')
        if p_color == opponent:
            # 凍結されている駒は攻撃できないため、チェック判定から除外
            is_frozen = False
            try:
                is_frozen = (id(p) in frozen and frozen.get(id(p), 0) > 0) or (hasattr(p, 'frozen_turns') and getattr(p, 'frozen_turns', 0) > 0)
            except Exception:
                is_frozen = (id(p) in frozen and frozen.get(id(p), 0) > 0)
            if is_frozen:
                continue
            
            # この駒の有効手を取得(ignore_castling=Trueで高速化)
            if hasattr(p, 'get_valid_moves'):
                m = p.get_valid_moves(pcs, ignore_castling=True)
            else:
                # dict形式の場合はスキップ(通常はPieceオブジェクト)
                continue
                
            if king_pos in m:
                return True
    return False


def can_attack_king_with_cards(pcs, color, get_valid_moves_func):
    """
    カード効果（迅雷や暴風のジャンプ等）を考慮して、相手が現在の手でキングを攻撃できるかを判定する（表示用）。
    get_valid_moves(..., ignore_check=True) を用いて、カード付与の特殊手を含めて射程を検査する。
    
    Args:
        pcs: 駒のリスト
        color: キングの色 ('white' or 'black')
        get_valid_moves_func: get_valid_moves関数（カード効果考慮）
    
    Returns:
        bool: キングを攻撃可能ならTrue
    """
    # find king pos
    king = None
    for p in pcs:
        try:
            if p.name == 'K' and p.color == color:
                king = p
                break
        except Exception:
            if isinstance(p, dict) and p.get('name') == 'K' and p.get('color') == color:
                king = p
                break
    if not king:
        return False
    kr = getattr(king, 'row', None) if hasattr(king, 'row') else king.get('row')
    kc = getattr(king, 'col', None) if hasattr(king, 'col') else king.get('col')
    if kr is None or kc is None:
        return False

    opponent = 'black' if color == 'white' else 'white'
    try:
        for p in pcs:
            pcol = getattr(p, 'color', None) if hasattr(p, 'color') else (p.get('color') if isinstance(p, dict) else None)
            if pcol != opponent:
                continue
            try:
                moves = get_valid_moves_func(p, ignore_check=True)
            except Exception:
                moves = []
            for mv in moves:
                if mv == (kr, kc):
                    return True
    except Exception:
        return False
    return False


def has_legal_moves_with_cards(color, chess_module, get_valid_moves_func, is_in_check_func):
    """カード効果（暴風のジャンプ、封鎖、凍結）込みで合法手が存在するかを判定。
    盤面は chess_engine の pieces を参照しつつ、移動生成は get_valid_moves を使う。
    
    Args:
        color: 判定する色 ('white' or 'black')
        chess_module: chess_engineモジュール
        get_valid_moves_func: get_valid_moves関数
        is_in_check_func: is_in_check関数
    
    Returns:
        bool: 合法手が存在するならTrue
    """
    try:
        for p in chess_module.pieces:
            # カラー取得（オブジェクト/辞書対応）
            try:
                pcolor = getattr(p, 'color', None)
            except Exception:
                pcolor = p.get('color') if isinstance(p, dict) else None
            if pcolor != color:
                continue
            moves = get_valid_moves_func(p, ignore_check=True)
            for mv in moves:
                # simulate_moveは utils.helpers からインポート
                from utils.helpers import simulate_move
                newp = simulate_move(p, mv[0], mv[1])
                if not is_in_check_func(newp, color):
                    return True
        return False
    except Exception:
        # フォールバック: 既存のチェスエンジン関数
        return chess_module.has_legal_moves_for(color)


def get_valid_moves(piece, game, chess_module, get_piece_at_func, simulate_move_func, 
                   is_in_check_func, on_board_func, pcs=None, ignore_check=False,
                   simul_check_active=False, debug_counter_check_card_mode=False,
                   ai_next_move_can_jump=False, ai_consecutive_turns=0):
    """駒の有効な移動先を計算する（カード効果、凍結、封鎖を考慮）
    
    Args:
        piece: 移動する駒（オブジェクトまたは辞書）
        game: Gameインスタンス（凍結・封鎖情報取得用）
        chess_module: chess_engineモジュール
        get_piece_at_func: get_piece_at関数
        simulate_move_func: simulate_move関数
        is_in_check_func: is_in_check関数
        on_board_func: on_board関数
        pcs: 駒のリスト（Noneの場合はchess_module.piecesを使用）
        ignore_check: チェック判定を無視するか
        simul_check_active: 同時チェックが有効か
        debug_counter_check_card_mode: デバッグモード（反撃チェック許可）
        ai_next_move_can_jump: AI暴風ジャンプフラグ
        ai_consecutive_turns: AI迅雷連続ターン数
    
    Returns:
        list: 有効な移動先座標のリスト [(row, col), ...]
    """
    # pcs: list of piece dicts; if None, use chess.pieces
    if pcs is None:
        pcs = chess_module.pieces
    
    moves = []
    
    # 凍結チェック
    frozen_map = getattr(game, 'frozen_pieces', {}) or {}
    try:
        # get row/col from either object attributes or dict keys
        prow = getattr(piece, 'row', None)
        pcol = getattr(piece, 'col', None)
    except Exception:
        prow = None
        pcol = None
    try:
        if (prow is None or pcol is None) and isinstance(piece, dict):
            prow = prow if prow is not None else piece.get('row')
            pcol = pcol if pcol is not None else piece.get('col')
    except Exception:
        pass

    engine_piece = None
    try:
        if prow is not None and pcol is not None:
            engine_piece = chess_module.get_piece_at(int(prow), int(pcol))
    except Exception:
        engine_piece = None

    # Check freeze on canonical engine piece first
    try:
        if engine_piece is not None:
            if (id(engine_piece) in frozen_map and frozen_map.get(id(engine_piece), 0) > 0) or \
               (hasattr(engine_piece, 'frozen_turns') and getattr(engine_piece, 'frozen_turns', 0) > 0):
                return []
    except Exception:
        pass

    # Fallback: check freeze on the passed-in piece object itself
    try:
        if (id(piece) in frozen_map and frozen_map.get(id(piece), 0) > 0) or \
           (hasattr(piece, 'frozen_turns') and getattr(piece, 'frozen_turns', 0) > 0):
            return []
    except Exception:
        pass

    # small accessor to support both object-style Piece and dict-style pieces
    def _pget(p, key, default=None):
        if hasattr(p, key):
            return getattr(p, key)
        try:
            return p[key]
        except Exception:
            return default

    name = _pget(piece, 'name')
    r, c = _pget(piece, 'row'), _pget(piece, 'col')
    color = _pget(piece, 'color')

    def occupied(rr, cc):
        return get_piece_at_func(rr, cc) is not None
    
    def occupied_by_color(rr, cc, col):
        p = get_piece_at_func(rr, cc)
        return p is not None and _pget(p, 'color') == col
    
    def is_blocked_tile(rr, cc, col):
        # If a blocked tile applies to this color, disallow moving there
        try:
            # Prefer model helper if available (handles multi-entry representation)
            if getattr(game, 'is_tile_blocked_for', None) is not None:
                try:
                    if game.is_tile_blocked_for((rr, cc), col):
                        return True
                except Exception:
                    pass
            # Fallback to legacy single-owner mapping
            if getattr(game, 'blocked_tiles_owner', None) is not None:
                owner = game.blocked_tiles_owner.get((rr, cc))
                if owner == col:
                    return True
        except Exception:
            pass
        return False

    if name == 'P':
        dir = -1 if color == 'white' else 1
        # storm jump for pawn: if next_move_can_jump and front square is blocked, jump over it
        try:
            if color == 'white':
                can_jump = getattr(game, 'player', None) is not None and \
                          getattr(game.player, 'next_move_can_jump', False)
            else:
                can_jump = getattr(game, 'ai_next_move_can_jump', ai_next_move_can_jump)
        except Exception:
            can_jump = False
        
        # Check if storm jump applies (front square occupied)
        front_occupied = on_board_func(r+dir, c) and occupied(r+dir, c)
        
        if can_jump and front_occupied:
            # Jump over the front piece to 2 squares ahead (can capture enemy there)
            nr2 = r + 2*dir
            if on_board_func(nr2, c) and not occupied_by_color(nr2, c, color) and \
               not is_blocked_tile(nr2, c, color):
                moves.append((nr2, c))
        else:
            # Normal forward movement
            if on_board_func(r+dir, c) and not occupied(r+dir, c) and \
               not is_blocked_tile(r+dir, c, color):
                moves.append((r+dir, c))
                # double from starting rank
                start_row = 6 if color == 'white' else 1
                if r == start_row and on_board_func(r+2*dir, c) and not occupied(r+2*dir, c) and \
                   not is_blocked_tile(r+2*dir, c, color):
                    moves.append((r+2*dir, c))
        # captures
        for dc in (-1, 1):
            nr, nc = r+dir, c+dc
            if on_board_func(nr, nc) and occupied(nr, nc) and \
               not occupied_by_color(nr, nc, color) and not is_blocked_tile(nr, nc, color):
                moves.append((nr, nc))
        # en passant
        if getattr(chess_module, 'en_passant_target', None) is not None:
            target_r, target_c = chess_module.en_passant_target
            if color == 'white' and r == 3:
                if abs(c - target_c) == 1 and target_r == 2 and \
                   not is_blocked_tile(target_r, target_c, color):
                    moves.append((target_r, target_c))
            elif color == 'black' and r == 4:
                if abs(c - target_c) == 1 and target_r == 5 and \
                   not is_blocked_tile(target_r, target_c, color):
                    moves.append((target_r, target_c))
    
    elif name == 'N':
        for dr, dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
            nr, nc = r+dr, c+dc
            if on_board_func(nr, nc) and not occupied_by_color(nr, nc, color) and \
               not is_blocked_tile(nr, nc, color):
                moves.append((nr, nc))
    
    elif name in ('B', 'R', 'Q'):
        directions = []
        if name in ('B', 'Q'):
            directions += [(-1,-1),(-1,1),(1,-1),(1,1)]
        if name in ('R', 'Q'):
            directions += [(-1,0),(1,0),(0,-1),(0,1)]
        for dr, dc in directions:
            step = 1
            jumped = False
            while True:
                nr, nc = r+dr*step, c+dc*step
                if not on_board_func(nr, nc):
                    break
                if is_blocked_tile(nr, nc, color):
                    break

                if occupied(nr, nc):
                    if not occupied_by_color(nr, nc, color):
                        if not is_blocked_tile(nr, nc, color):
                            moves.append((nr, nc))
                    # storm jump ability
                    try:
                        if color == 'white':
                            can_jump = getattr(game, 'player', None) is not None and \
                                      getattr(game.player, 'next_move_can_jump', False)
                        else:
                            can_jump = getattr(game, 'ai_next_move_can_jump', ai_next_move_can_jump)
                    except Exception:
                        can_jump = False
                    if can_jump and not jumped:
                        step2 = step + 1
                        nr2, nc2 = r+dr*step2, c+dc*step2
                        if on_board_func(nr2, nc2) and not occupied_by_color(nr2, nc2, color) and \
                           not is_blocked_tile(nr2, nc2, color):
                            moves.append((nr2, nc2))
                    break

                moves.append((nr, nc))
                step += 1
    
    elif name == 'K':
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0: continue
                nr, nc = r+dr, c+dc
                if on_board_func(nr, nc) and not occupied_by_color(nr, nc, color) and \
                   not is_blocked_tile(nr, nc, color):
                    moves.append((nr, nc))

        # キャスリング
        if not _pget(piece, 'has_moved', False) and not ignore_check:
            if color == 'white':
                king_row = 7
            else:
                king_row = 0

            rook_kingside = get_piece_at_func(king_row, 7)
            if (rook_kingside and _pget(rook_kingside, 'name') == 'R' and
                _pget(rook_kingside, 'color') == color and
                not _pget(rook_kingside, 'has_moved', False)):
                if (not occupied(king_row, 5) and not occupied(king_row, 6) and
                    not is_blocked_tile(king_row, 5, color) and \
                    not is_blocked_tile(king_row, 6, color)):
                    moves.append((king_row, 6))

            rook_queenside = get_piece_at_func(king_row, 0)
            if (rook_queenside and _pget(rook_queenside, 'name') == 'R' and
                _pget(rook_queenside, 'color') == color and
                not _pget(rook_queenside, 'has_moved', False)):
                if (not occupied(king_row, 1) and not occupied(king_row, 2) and \
                    not occupied(king_row, 3) and
                    not is_blocked_tile(king_row, 1, color) and \
                    not is_blocked_tile(king_row, 2, color) and \
                    not is_blocked_tile(king_row, 3, color)):
                    moves.append((king_row, 2))

    # filter moves that leave king in check
    if not ignore_check and not simul_check_active:
        legal = []
        try:
            self_in_check = is_in_check_func(chess_module.pieces, color)
        except Exception:
            self_in_check = False
        # 迅雷の有効判定
        try:
            if color == 'white':
                lightning_active = getattr(game, 'player_consecutive_turns', 0) > 0
            else:
                lightning_active = ai_consecutive_turns > 0
        except Exception:
            lightning_active = False
        # デバッグモードのゲート
        try:
            debug_card_gate = debug_counter_check_card_mode and \
                            getattr(game, '_debug_last_action_was_card', False)
        except Exception:
            debug_card_gate = False
        opp = 'black' if color == 'white' else 'white'
        for mv in moves:
            newp = simulate_move_func(piece, mv[0], mv[1])
            if not is_in_check_func(newp, color):
                legal.append(mv)
                continue
            # 反撃チェックの特例
            if self_in_check and (lightning_active or debug_card_gate):
                try:
                    if is_in_check_func(newp, opp):
                        legal.append(mv)
                        continue
                except Exception:
                    pass
            if not self_in_check and (lightning_active or debug_card_gate):
                try:
                    if is_in_check_func(newp, opp):
                        legal.append(mv)
                        continue
                except Exception:
                    pass
        return legal
    return moves


def check_game_over_conditions(game, chess_module, is_in_check_func, has_legal_moves_with_cards_func, simul_check_active=False):
    """ゲーム終了条件（チェックメイト、ステイルメイト）をチェックする。
    
    Args:
        game: Gameオブジェクト（ログ出力用）
        chess_module: chess_engineモジュール（pieces, chess_current_turn取得用）
        is_in_check_func: チェック判定関数
        has_legal_moves_with_cards_func: カード効果込み合法手判定関数
        simul_check_active: 同時チェック中かどうか（デフォルトFalse）
    
    Returns:
        tuple: (game_over: bool, winner: str or None)
               winnerは 'white', 'black', 'draw' のいずれか
    """
    if simul_check_active:
        return False, None
    
    try:
        pieces = chess_module.pieces
        current_turn = chess_module.chess_current_turn
    except Exception:
        # フォールバック: モジュールから取得できない場合
        return False, None
    
    # 白のチェックメイト判定
    if not has_legal_moves_with_cards_func('white') and is_in_check_func(pieces, 'white'):
        if game:
            game.log.append("YOU LOSE！黒の勝利！")
        return True, 'black'
    
    # 黒のチェックメイト判定
    if not has_legal_moves_with_cards_func('black') and is_in_check_func(pieces, 'black'):
        if game:
            game.log.append("YOU WIN！白の勝利！")
        return True, 'white'
    
    # ステイルメイト判定（合法手がないがチェックでない）
    if not has_legal_moves_with_cards_func(current_turn) and not is_in_check_func(pieces, current_turn):
        if game:
            game.log.append("ステイルメイト（引き分け）")
        return True, 'draw'
    
    return False, None


def handle_promotion_selection(chess_module, game, selected_piece_name):
    """プロモーション選択を処理する。
    
    Args:
        chess_module: chess_engineモジュール（promotion_pending取得・更新用）
        game: Gameオブジェクト（ログ出力用）
        selected_piece_name: 選択された駒の名前 ('Q', 'R', 'B', 'N')
    
    Returns:
        bool: 処理が成功したかどうか
    """
    try:
        if not hasattr(chess_module, 'promotion_pending') or chess_module.promotion_pending is None:
            return False
        
        piece = chess_module.promotion_pending.get('piece')
        if piece is None:
            return False
        
        # 駒の名前を昇格先に変更
        if hasattr(piece, 'name'):
            piece.name = selected_piece_name
        elif isinstance(piece, dict):
            piece['name'] = selected_piece_name
        
        # ログ出力
        if game:
            game.log.append(f"昇格: ポーンを{selected_piece_name}に昇格させました。")
        
        # プロモーション待ち状態をクリア
        chess_module.promotion_pending = None
        return True
        
    except Exception:
        return False


def clear_promotion_state(chess_module):
    """プロモーション待ち状態をクリアする。
    
    Args:
        chess_module: chess_engineモジュール
    """
    try:
        if hasattr(chess_module, 'promotion_pending'):
            chess_module.promotion_pending = None
    except Exception:
        pass


def update_simul_check_state(chess_module, game, is_in_check_func, chess_current_turn, game_over, simul_state):
    """同時チェック状態を更新し、期限判定と決着処理を行う。
    
    Args:
        chess_module: chess_engineモジュール（pieces取得用）
        game: Gameオブジェクト（ログ出力用）
        is_in_check_func: チェック判定関数
        chess_current_turn: 現在の手番 ('white' or 'black')
        game_over: ゲーム終了フラグ
        simul_state: 同時チェック状態を保持する辞書
            {
                'active': bool,
                'white_result': 'none'|'pending'|'cleared'|'failed',
                'black_result': 'none'|'pending'|'cleared'|'failed',
                'white_turn_index': int,
                'black_turn_index': int,
                'last_turn_color': str or None,
                'white_deadline_turn': int or None,
                'black_deadline_turn': int or None
            }
    
    Returns:
        tuple: (game_over: bool, winner: str or None, updated_state: dict)
    """
    try:
        pieces = chess_module.pieces
    except Exception:
        return game_over, None, simul_state
    
    # 手番インデックス更新
    if simul_state.get('last_turn_color') != chess_current_turn:
        if chess_current_turn == 'white':
            simul_state['white_turn_index'] = simul_state.get('white_turn_index', 0) + 1
        else:
            simul_state['black_turn_index'] = simul_state.get('black_turn_index', 0) + 1
        simul_state['last_turn_color'] = chess_current_turn
        
        # 同時チェック中の期限判定
        if simul_state.get('active', False):
            try:
                # 白の期限判定
                if chess_current_turn == 'white' and simul_state.get('white_result') == 'pending':
                    if simul_state.get('white_deadline_turn') is None:
                        # 次の白番開始時に判定する
                        simul_state['white_deadline_turn'] = simul_state.get('white_turn_index', 0) + 1
                        if game:
                            game.log.append("同時チェック: 白は次の白番開始までにチェック解除が必要です。")
                    elif simul_state.get('white_turn_index', 0) >= simul_state.get('white_deadline_turn', 0):
                        # 期限到達：チェック状態で成否を確定
                        if is_in_check_func(pieces, 'white'):
                            simul_state['white_result'] = 'failed'
                            if game:
                                game.log.append("同時チェック: 白は期限までにチェックを解除できませんでした（失敗）。")
                        else:
                            simul_state['white_result'] = 'cleared'
                            if game:
                                game.log.append("同時チェック: 白はチェックを解除しました（成功）。")
                
                # 黒の期限判定
                elif chess_current_turn == 'black' and simul_state.get('black_result') == 'pending':
                    if simul_state.get('black_deadline_turn') is None:
                        simul_state['black_deadline_turn'] = simul_state.get('black_turn_index', 0) + 1
                        if game:
                            game.log.append("同時チェック: 黒は次の黒番開始までにチェック解除が必要です。")
                    elif simul_state.get('black_turn_index', 0) >= simul_state.get('black_deadline_turn', 0):
                        # 期限到達：チェック状態で成否を確定
                        if is_in_check_func(pieces, 'black'):
                            simul_state['black_result'] = 'failed'
                            if game:
                                game.log.append("同時チェック: 黒は期限までにチェックを解除できませんでした（失敗）。")
                        else:
                            simul_state['black_result'] = 'cleared'
                            if game:
                                game.log.append("同時チェック: 黒はチェックを解除しました（成功）。")
            except Exception:
                pass
            
            # 双方結果が出たら決着
            wres = simul_state.get('white_result')
            bres = simul_state.get('black_result')
            if wres in ('cleared', 'failed') and bres in ('cleared', 'failed') and not game_over:
                # 両者のキングの存在確認
                white_king_exists = any(p.name == 'K' and p.color == 'white' for p in pieces)
                black_king_exists = any(p.name == 'K' and p.color == 'black' for p in pieces)
                
                winner = None
                
                # 両者のキングが取られている場合は無条件で引き分け
                if not white_king_exists and not black_king_exists:
                    game_over = True
                    winner = 'draw'
                    if game:
                        game.log.append("同時チェック: 両者のキングが取られました。引き分け。")
                # 白のキングのみ取られた場合は黒の勝利
                elif not white_king_exists:
                    game_over = True
                    winner = 'black'
                    if game:
                        game.log.append("同時チェック: 白のキングが取られました。黒の勝利！")
                # 黒のキングのみ取られた場合は白の勝利
                elif not black_king_exists:
                    game_over = True
                    winner = 'white'
                    if game:
                        game.log.append("同時チェック: 黒のキングが取られました。白の勝利！")
                # 両者のキングが残っている場合
                elif white_king_exists and black_king_exists:
                    # 両者とも解除失敗の場合は引き分け
                    if wres == 'failed' and bres == 'failed':
                        game_over = True
                        winner = 'draw'
                        if game:
                            game.log.append("同時チェック: 両者とも解除できませんでした。引き分け。")
                    # 白のみ解除成功
                    elif wres == 'cleared' and bres == 'failed':
                        game_over = True
                        winner = 'white'
                        if game:
                            game.log.append("同時チェック: 白のみ解除成功。白の勝利！")
                    # 黒のみ解除成功
                    elif wres == 'failed' and bres == 'cleared':
                        game_over = True
                        winner = 'black'
                        if game:
                            game.log.append("同時チェック: 黒のみ解除成功。黒の勝利！")
                    else:
                        # 両者解除成功 → 通常続行
                        if game:
                            game.log.append("同時チェック: 両者解除成功。通常ルールに復帰します。")
                
                # 状態をクリア
                simul_state['active'] = False
                simul_state['white_deadline_turn'] = None
                simul_state['black_deadline_turn'] = None
                simul_state['white_result'] = 'none'
                simul_state['black_result'] = 'none'
                
                return game_over, winner, simul_state
    
    return game_over, None, simul_state


def check_simul_check_entry(chess_module, game, is_in_check_func, game_over, simul_state):
    """新たに同時チェック状態に突入したかをチェックする。
    
    Args:
        chess_module: chess_engineモジュール（pieces取得用）
        game: Gameオブジェクト（ログ出力用）
        is_in_check_func: チェック判定関数
        game_over: ゲーム終了フラグ
        simul_state: 同時チェック状態を保持する辞書
    
    Returns:
        dict: 更新された同時チェック状態
    """
    if game_over:
        return simul_state
    
    try:
        pieces = chess_module.pieces
        white_in_check = is_in_check_func(pieces, 'white')
        black_in_check = is_in_check_func(pieces, 'black')
        
        if white_in_check and black_in_check and not simul_state.get('active', False):
            simul_state['active'] = True
            simul_state['white_result'] = 'pending'
            simul_state['black_result'] = 'pending'
            simul_state['white_deadline_turn'] = None
            simul_state['black_deadline_turn'] = None
            if game:
                game.log.append("同時チェック状態に突入：両者は次の自分の手番開始までにチェック解除が必要です。")
    except Exception:
        pass
    
    return simul_state
