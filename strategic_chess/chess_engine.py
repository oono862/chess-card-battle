# Chess engine (Piece-class based) adapted from Chess Main implementation
from __future__ import annotations
from typing import List, Optional, Tuple

# Module-level state
pieces: List["Piece"] = []
en_passant_target: Optional[Tuple[int,int]] = None
promotion_pending: Optional[dict] = None  # {'piece': Piece, 'color': str}


def _get_piece_at(pcs: List["Piece"], row: int, col: int) -> Optional["Piece"]:
    if row is None or col is None or not (0 <= row < 8 and 0 <= col < 8):
        return None
    for p in pcs:
        if p.row == row and p.col == col:
            return p
    return None


def get_piece_at(row: int, col: int) -> Optional["Piece"]:
    return _get_piece_at(pieces, row, col)


class Piece:
    def __init__(self, row: int, col: int, name: str, color: str):
        self.row = row
        self.col = col
        self.name = name  # 'K','Q','R','B','N','P'
        self.color = color  # 'white' or 'black'
        self.has_moved = False
        self.gimmick = None

    def is_occupied(self, row: int, col: int, pcs: List["Piece"], same_color: Optional[bool] = None) -> bool:
        for piece in pcs:
            if piece.row == row and piece.col == col:
                if same_color is None:
                    return True
                if (piece.color == self.color) == same_color:
                    return True
        return False

    def get_valid_moves(self, pcs: List["Piece"], ignore_castling: bool = False):
        moves = []

        def add_direction(dr: int, dc: int, max_steps: int = 8):
            for step in range(1, max_steps + 1):
                nr = self.row + dr * step
                nc = self.col + dc * step
                if 0 <= nr < 8 and 0 <= nc < 8:
                    if self.is_occupied(nr, nc, pcs, same_color=True):
                        break
                    moves.append((nr, nc))
                    if self.is_occupied(nr, nc, pcs, same_color=False):
                        break
                else:
                    break

        if self.name == 'K':
            for dr in (-1,0,1):
                for dc in (-1,0,1):
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = self.row + dr, self.col + dc
                    if 0 <= nr < 8 and 0 <= nc < 8 and not self.is_occupied(nr, nc, pcs, same_color=True):
                        moves.append((nr, nc))
            # Castling checks (more strict per Chess Main)
            if not ignore_castling:
                # must not have moved, be on file e, and not currently in check
                if not self.has_moved and self.col == 4 and not is_in_check(pcs, self.color):
                    row = self.row
                    # Kingside
                    rook_k = _get_piece_at(pcs, row, 7)
                    if rook_k and rook_k.name == 'R' and rook_k.color == self.color and not rook_k.has_moved:
                        if all(_get_piece_at(pcs, row, c) is None for c in (5,6)):
                            safe = True
                            for c in (4,5,6):
                                temp_pcs: List[Piece] = []
                                for p in pcs:
                                    if p is self:
                                        tk = Piece(row, c, 'K', self.color)
                                        tk.has_moved = True
                                        temp_pcs.append(tk)
                                    elif p is rook_k:
                                        tr = Piece(row, 7, 'R', self.color)
                                        tr.has_moved = True
                                        temp_pcs.append(tr)
                                    else:
                                        temp_pcs.append(p)
                                if is_in_check(temp_pcs, self.color):
                                    safe = False
                                    break
                            if safe:
                                moves.append((row, 6))
                    # Queenside
                    rook_q = _get_piece_at(pcs, row, 0)
                    if rook_q and rook_q.name == 'R' and rook_q.color == self.color and not rook_q.has_moved:
                        if all(_get_piece_at(pcs, row, c) is None for c in (1,2,3)):
                            safe = True
                            for c in (4,3,2):
                                temp_pcs: List[Piece] = []
                                for p in pcs:
                                    if p is self:
                                        tk = Piece(row, c, 'K', self.color)
                                        tk.has_moved = True
                                        temp_pcs.append(tk)
                                    elif p is rook_q:
                                        tr = Piece(row, 0, 'R', self.color)
                                        tr.has_moved = True
                                        temp_pcs.append(tr)
                                    else:
                                        temp_pcs.append(p)
                                if is_in_check(temp_pcs, self.color):
                                    safe = False
                                    break
                            if safe:
                                moves.append((row, 2))
        elif self.name == 'Q':
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]:
                add_direction(dr, dc)
        elif self.name == 'B':
            for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                add_direction(dr, dc)
        elif self.name == 'R':
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                add_direction(dr, dc)
        elif self.name == 'N':
            for dr, dc in [(2,1),(1,2),(-1,2),(-2,1),(-2,-1),(-1,-2),(1,-2),(2,-1)]:
                nr, nc = self.row + dr, self.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and not self.is_occupied(nr, nc, pcs, same_color=True):
                    moves.append((nr, nc))
        elif self.name == 'P':
            dir = -1 if self.color == 'white' else 1
            start_row = 6 if self.color == 'white' else 1
            # forward
            if not self.is_occupied(self.row + dir, self.col, pcs):
                moves.append((self.row + dir, self.col))
                if self.row == start_row and not self.is_occupied(self.row + 2*dir, self.col, pcs):
                    moves.append((self.row + 2*dir, self.col))
            # captures
            for dc in (-1,1):
                nr, nc = self.row + dir, self.col + dc
                if 0 <= nr < 8 and 0 <= nc < 8 and self.is_occupied(nr, nc, pcs, same_color=False):
                    moves.append((nr, nc))
            # en passant
            global en_passant_target
            for dc in (-1,1):
                nr, nc = self.row + dir, self.col + dc
                if en_passant_target is not None and (nr, nc) == en_passant_target and abs(self.col - nc) == 1:
                    if (self.color == 'white' and self.row == 3) or (self.color == 'black' and self.row == 4):
                        moves.append((nr, nc))
        return moves


def is_in_check(pcs: List[Piece], color: str) -> bool:
    # find king of color
    king = None
    for p in pcs:
        if p.name == 'K' and p.color == color:
            king = p
            break
    if not king:
        return False
    king_pos = (king.row, king.col)
    opponent = 'black' if color == 'white' else 'white'
    for p in pcs:
        if p.color == opponent:
            m = p.get_valid_moves(pcs, ignore_castling=True)
            if king_pos in m:
                return True
    return False


def has_legal_moves_for(color: str) -> bool:
    for p in pieces:
        if p.color == color:
            m = p.get_valid_moves(pieces)
            for mv in m:
                temp = simulate_move(p, mv[0], mv[1])
                if not is_in_check(temp, color):
                    return True
    return False


def create_pieces() -> List[Piece]:
    ps: List[Piece] = []
    ps += [Piece(7,0,'R','white'), Piece(7,1,'N','white'), Piece(7,2,'B','white'),
           Piece(7,3,'Q','white'), Piece(7,4,'K','white'), Piece(7,5,'B','white'),
           Piece(7,6,'N','white'), Piece(7,7,'R','white')]
    ps += [Piece(6,i,'P','white') for i in range(8)]
    ps += [Piece(0,0,'R','black'), Piece(0,1,'N','black'), Piece(0,2,'B','black'),
           Piece(0,3,'Q','black'), Piece(0,4,'K','black'), Piece(0,5,'B','black'),
           Piece(0,6,'N','black'), Piece(0,7,'R','black')]
    ps += [Piece(1,i,'P','black') for i in range(8)]
    return ps


# initialize module pieces
pieces = create_pieces()


def simulate_move(src_piece: Piece, to_r: int, to_c: int) -> List[Piece]:
    # Build a new piece list representing the position after moving src_piece to (to_r,to_c)
    new_list: List[Piece] = []
    # remove captured piece at destination
    for p in pieces:
        if p.row == to_r and p.col == to_c and p is not src_piece:
            continue
        if p is src_piece:
            continue
        new_list.append(p)
    # add moved king/other piece clone to new list
    moved = Piece(to_r, to_c, src_piece.name, src_piece.color)
    moved.has_moved = True
    new_list.append(moved)
    return new_list


def apply_move(piece: Piece, to_r: int, to_c: int) -> None:
    global en_passant_target, promotion_pending
    from_r, from_c = piece.row, piece.col

    # en passant capture
    target = get_piece_at(to_r, to_c)
    if piece.name == 'P' and target is None and en_passant_target is not None and (to_r, to_c) == en_passant_target:
        captured_row = to_r + (1 if piece.color == 'white' else -1)
        captured_piece = get_piece_at(captured_row, to_c)
        if captured_piece and captured_piece.name == 'P':
            pieces.remove(captured_piece)

    # normal capture
    if target is not None and target in pieces:
        pieces.remove(target)

    # castling rook move
    if piece.name == 'K' and abs(to_c - from_c) == 2:
        if to_c == 6:  # kingside
            rook = get_piece_at(to_r, 7)
            if rook and rook.name == 'R':
                rook.col = 5
                rook.has_moved = True
        elif to_c == 2:  # queenside
            rook = get_piece_at(to_r, 0)
            if rook and rook.name == 'R':
                rook.col = 3
                rook.has_moved = True

    # move the piece
    piece.row = to_r
    piece.col = to_c
    piece.has_moved = True

    # set en passant target only on double pawn move
    if piece.name == 'P' and abs(to_r - from_r) == 2:
        en_passant_target = ((from_r + to_r)//2, to_c)
    else:
        en_passant_target = None

    # promotion: mark pending for UI handling
    if piece.name == 'P' and (piece.row == 0 or piece.row == 7):
        promotion_pending = {'piece': piece, 'color': piece.color}
