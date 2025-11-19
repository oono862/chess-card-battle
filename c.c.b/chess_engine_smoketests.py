# Minimal smoke tests for chess_engine core rules
# Run: python strategic_chess/chess_engine_smoketests.py

import sys

try:
    from . import chess_engine as chess
except Exception:
    import chess_engine as chess


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_castling():
    chess.pieces[:] = []
    k = chess.Piece(7,4,'K','white')
    r1 = chess.Piece(7,0,'R','white')
    r2 = chess.Piece(7,7,'R','white')
    k.has_moved = False
    r1.has_moved = False
    r2.has_moved = False
    chess.pieces.extend([k,r1,r2])
    chess.en_passant_target = None
    moves = set(k.get_valid_moves(chess.pieces))
    assert_true((7,6) in moves, "Kingside castling (7,6) expected")
    assert_true((7,2) in moves, "Queenside castling (7,2) expected")


def test_en_passant():
    chess.pieces[:] = []
    wp = chess.Piece(3,4,'P','white')  # e5
    bp = chess.Piece(3,5,'P','black')  # f5 (assume just double moved)
    chess.pieces.extend([wp, bp])
    chess.en_passant_target = (2,5)    # f6 square from white POV
    moves = set(wp.get_valid_moves(chess.pieces))
    assert_true((2,5) in moves, "En passant capture (2,5) expected")


def test_promotion_pending():
    chess.pieces[:] = []
    wp = chess.Piece(1,0,'P','white')  # a7
    chess.pieces.append(wp)
    chess.en_passant_target = None
    chess.apply_move(wp, 0, 0)  # move to a8
    assert_true(chess.promotion_pending is not None, "Promotion pending should be set after pawn reaches last rank")


def test_is_in_check():
    chess.pieces[:] = []
    wk = chess.Piece(7,4,'K','white')  # e1
    br = chess.Piece(0,4,'R','black')  # e8 rook down the file
    chess.pieces.extend([wk, br])
    chess.en_passant_target = None
    assert_true(chess.is_in_check(chess.pieces, 'white'), "White should be in check along the e-file")


def run_all():
    tests = [test_castling, test_en_passant, test_promotion_pending, test_is_in_check]
    for t in tests:
        t()
    print("OK: ", ", ".join(t.__name__ for t in tests))


if __name__ == "__main__":
    try:
        run_all()
    except AssertionError as e:
        print("FAIL:", e)
        sys.exit(1)
