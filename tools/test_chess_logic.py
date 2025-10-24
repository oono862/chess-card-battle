# simple test for castling and en-passant in Card Game.py
import importlib.util
import sys
from types import ModuleType

path = r"c:\Users\Student\Desktop\chess-card-battle\chess-card-battle\strategic_chess\Card Game.py"
# create a minimal mock for card_core expected by Card Game.py
import types
mock_core = types.ModuleType('card_core')
class DummyGame:
    def __init__(self):
        class Player:
            def __init__(self):
                self.pp_current = 0
                self.pp_max = 0
                self.hand = type('H', (), {'cards': []})()
                self.deck = type('D', (), {'cards': []})()
                self.graveyard = []
                self.extra_moves_this_turn = 0
                self.next_move_can_jump = False
        self.player = Player()
        self.turn = 1
        self.pending = None
mock_core.new_game_with_rule_deck = lambda: DummyGame()
mock_core.new_game_with_sample_deck = lambda: DummyGame()
sys.modules['card_core'] = mock_core

spec = importlib.util.spec_from_file_location('cardgame', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

pieces = mod.create_pieces()
mod.pieces = pieces

# Set up a position for white kingside castling: clear f1/g1 squares and ensure neither king nor rook has moved
# In our representation, white king starts at row 7, col 4
wk = mod.get_piece_at(7,4)
wr = mod.get_piece_at(7,7)
# ensure has_moved flags
wk['has_moved'] = False
wr['has_moved'] = False
# clear squares f1 (7,5) and g1 (7,6)
for sq in [(7,5),(7,6)]:
    p = mod.get_piece_at(sq[0], sq[1])
    if p:
        mod.pieces.remove(p)

moves = mod.get_valid_moves(wk)
print('White king moves:', moves)
print('King can castle kingside (should include (7,6)):', (7,6) in moves)

# En-passant test: place white pawn at row 3,col4 and black pawn move from row1,col5 to row3,col5
# Reset pieces
mod.pieces = mod.create_pieces()
# move white pawn from (6,4) to (4,4) (simulate white double move earlier)
wp = mod.get_piece_at(6,4)
mod.apply_move(wp,4,4)
# move black pawn from (1,5) to (3,5) (double move) and set en_passant target as Card Game would
bp = mod.get_piece_at(1,5)
mod.apply_move(bp,3,5)
print('en_passant_target after black double move should be (2,5):', mod.en_passant_target)
# Now white pawn at (4,4) should be able to capture en-passant to (3,5)
wp2 = mod.get_piece_at(4,4)
moves_wp = mod.get_valid_moves(wp2)
print('White pawn moves (should include en-passant):', moves_wp)
print('En-passant available to (3,5):', (3,5) in moves_wp)
