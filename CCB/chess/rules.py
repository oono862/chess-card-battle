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
