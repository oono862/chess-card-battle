# Simple chess rules and state extracted from Card Game.py (dict-based pieces)
# No dependency on pygame or card game state.

from typing import List, Tuple, Optional, Dict

# Module-level state
pieces: List[Dict] = []  # list of dicts: {'row':int,'col':int,'name':str,'color':'white'|'black','has_moved':bool}
en_passant_target: Optional[Tuple[int,int]] = None
promotion_pending: Optional[Dict] = None  # {'piece': piece, 'color': str}


def create_pieces() -> List[Dict]:
    p = []
    # White on bottom (rows 6-7), black on top (rows 0-1)
    p += [{'row':7, 'col':0, 'name':'R', 'color':'white', 'has_moved':False},
          {'row':7, 'col':1, 'name':'N', 'color':'white', 'has_moved':False},
          {'row':7, 'col':2, 'name':'B', 'color':'white', 'has_moved':False},
          {'row':7, 'col':3, 'name':'Q', 'color':'white', 'has_moved':False},
          {'row':7, 'col':4, 'name':'K', 'color':'white', 'has_moved':False},
          {'row':7, 'col':5, 'name':'B', 'color':'white', 'has_moved':False},
          {'row':7, 'col':6, 'name':'N', 'color':'white', 'has_moved':False},
          {'row':7, 'col':7, 'name':'R', 'color':'white', 'has_moved':False}]
    p += [{'row':6, 'col':i, 'name':'P', 'color':'white', 'has_moved':False} for i in range(8)]
    p += [{'row':0, 'col':0, 'name':'R', 'color':'black', 'has_moved':False},
          {'row':0, 'col':1, 'name':'N', 'color':'black', 'has_moved':False},
          {'row':0, 'col':2, 'name':'B', 'color':'black', 'has_moved':False},
          {'row':0, 'col':3, 'name':'Q', 'color':'black', 'has_moved':False},
          {'row':0, 'col':4, 'name':'K', 'color':'black', 'has_moved':False},
          {'row':0, 'col':5, 'name':'B', 'color':'black', 'has_moved':False},
          {'row':0, 'col':6, 'name':'N', 'color':'black', 'has_moved':False},
          {'row':0, 'col':7, 'name':'R', 'color':'black', 'has_moved':False}]
    p += [{'row':1, 'col':i, 'name':'P', 'color':'black', 'has_moved':False} for i in range(8)]
    return p


def get_piece_at(row: int, col: int) -> Optional[Dict]:
    for pc in pieces:
        if pc['row'] == row and pc['col'] == col:
            return pc
    return None


def on_board(r: int, c: int) -> bool:
    return 0 <= r < 8 and 0 <= c < 8


def simulate_move(src_piece: Dict, to_r: int, to_c: int) -> List[Dict]:
    # return new pieces list after move (deep copy of dicts)
    new = [dict(p) for p in pieces if not (p['row']==to_r and p['col']==to_c)]
    moved = dict(src_piece)
    # remove source from new
    new = [p for p in new if not (p['row']==src_piece['row'] and p['col']==src_piece['col'] and p['name']==src_piece['name'] and p['color']==src_piece['color'])]
    moved['row'] = to_r
    moved['col'] = to_c
    new.append(moved)
    return new


def is_in_check(pcs: List[Dict], color: str) -> bool:
    # find king
    king = None
    for p in pcs:
        if p['name'] == 'K' and p['color'] == color:
            king = p
            break
    if not king:
        return False
    kpos = (king['row'], king['col'])
    # check opponent moves
    for p in pcs:
        if p['color'] == ('white' if color=='black' else 'black'):
            for mv in get_valid_moves(p, pcs, ignore_check=True):
                if mv == kpos:
                    return True
    return False


def get_valid_moves(piece: Dict, pcs: Optional[List[Dict]] = None, ignore_check: bool = False):
    # pcs: list of piece dicts; if None, use global pieces
    if pcs is None:
        pcs = pieces
    moves = []
    name = piece['name']
    r,c = piece['row'], piece['col']

    def occupied(rr,cc):
        return get_piece_at(rr,cc) is not None

    def occupied_by_color(rr,cc,color):
        p = get_piece_at(rr,cc)
        return p is not None and p['color']==color

    global en_passant_target

    if name == 'P':
        dir = -1 if piece['color']=='white' else 1
        # forward
        if on_board(r+dir, c) and not occupied(r+dir,c):
            moves.append((r+dir,c))
            # double from starting rank
            start_row = 6 if piece['color']=='white' else 1
            if r==start_row and on_board(r+2*dir,c) and not occupied(r+2*dir,c):
                moves.append((r+2*dir,c))
        # captures
        for dc in (-1,1):
            nr,nc = r+dir, c+dc
            if on_board(nr,nc) and occupied(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                moves.append((nr,nc))
        # en passant
        if en_passant_target is not None:
            target_r, target_c = en_passant_target
            if piece['color'] == 'white' and r == 3:  # white on 5th rank
                if abs(c - target_c) == 1 and target_r == 2:
                    moves.append((target_r, target_c))
            elif piece['color'] == 'black' and r == 4:  # black on 4th rank
                if abs(c - target_c) == 1 and target_r == 5:
                    moves.append((target_r, target_c))
    elif name == 'N':
        for dr,dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
            nr,nc = r+dr, c+dc
            if on_board(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                moves.append((nr,nc))
    elif name in ('B','R','Q'):
        directions = []
        if name in ('B','Q'):
            directions += [(-1,-1),(-1,1),(1,-1),(1,1)]
        if name in ('R','Q'):
            directions += [(-1,0),(1,0),(0,-1),(0,1)]
        for dr,dc in directions:
            step = 1
            while True:
                nr,nc = r+dr*step, c+dc*step
                if not on_board(nr,nc):
                    break
                if occupied(nr,nc):
                    if not occupied_by_color(nr,nc,piece['color']):
                        moves.append((nr,nc))
                    break
                moves.append((nr,nc))
                step += 1
    elif name == 'K':
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                nr,nc = r+dr, c+dc
                if on_board(nr,nc) and not occupied_by_color(nr,nc,piece['color']):
                    moves.append((nr,nc))
        # castling (basic path empty + rook unmoved). Check filtering handled below when ignore_check=False
        if not piece.get('has_moved', False) and not ignore_check:
            king_row = 7 if piece['color'] == 'white' else 0
            # king side
            rook_k = get_piece_at(king_row, 7)
            if (rook_k and rook_k['name']=='R' and rook_k['color']==piece['color'] and not rook_k.get('has_moved', False)):
                if not occupied(king_row,5) and not occupied(king_row,6):
                    moves.append((king_row,6))
            # queen side
            rook_q = get_piece_at(king_row, 0)
            if (rook_q and rook_q['name']=='R' and rook_q['color']==piece['color'] and not rook_q.get('has_moved', False)):
                if not occupied(king_row,1) and not occupied(king_row,2) and not occupied(king_row,3):
                    moves.append((king_row,2))

    # filter moves that leave king in check
    if not ignore_check:
        legal = []
        for mv in moves:
            newp = simulate_move(piece, mv[0], mv[1])
            if not is_in_check(newp, piece['color']):
                legal.append(mv)
        return legal
    return moves


def has_legal_moves_for(color: str) -> bool:
    for p in pieces:
        if p['color']==color and get_valid_moves(p):
            return True
    return False


def apply_move(piece: Dict, to_r: int, to_c: int) -> None:
    global en_passant_target, promotion_pending
    from_r, from_c = piece['row'], piece['col']

    # en passant capture
    target = get_piece_at(to_r, to_c)
    if piece['name'] == 'P' and target is None and en_passant_target is not None:
        if (to_r, to_c) == en_passant_target:
            captured_row = to_r + (1 if piece['color'] == 'white' else -1)
            captured_piece = get_piece_at(captured_row, to_c)
            if captured_piece and captured_piece['name'] == 'P':
                pieces.remove(captured_piece)

    # normal capture
    if target:
        pieces.remove(target)

    # castling rook move
    if piece['name'] == 'K' and abs(to_c - from_c) == 2:
        if to_c == 6:
            rook = get_piece_at(to_r, 7)
            if rook and rook['name'] == 'R':
                rook['col'] = 5
                rook['has_moved'] = True
        elif to_c == 2:
            rook = get_piece_at(to_r, 0)
            if rook and rook['name'] == 'R':
                rook['col'] = 3
                rook['has_moved'] = True

    # move piece
    piece['row'] = to_r
    piece['col'] = to_c
    piece['has_moved'] = True

    # update en passant target (only when pawn double steps)
    if piece['name'] == 'P' and abs(to_r - from_r) == 2:
        en_passant_target = ((from_r + to_r)//2, to_c)
    else:
        en_passant_target = None

    # promotion pending
    if piece['name']=='P' and (piece['row']==0 or piece['row']==7):
        promotion_pending = {'piece': piece, 'color': piece['color']}


# initialize default starting position
pieces = create_pieces()
