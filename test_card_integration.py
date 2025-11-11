import importlib.util, os, sys
p = os.path.join(os.getcwd(), 'Card Game.py')
spec = importlib.util.spec_from_file_location('card_game', p)
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)
import card_core as cc

print('modules loaded:', cg.__name__)
# clear board and set up simple pieces
cg.chess.pieces.clear()
# white pawn at (6,0)
cg.chess.pieces.append(cg.chess.Piece(6,0,'P','white'))
# black pawn at (5,1) (will try to move to 6,1)
cg.chess.pieces.append(cg.chess.Piece(5,1,'P','black'))

# start player's turn to allow card play
cg.game.start_turn()
print('turn:', cg.game.turn, 'pp:', cg.game.player.pp_current)

# -- Test 1: Block tile (灼熱) --
card_block = cc.Card('灼熱', 1, cc.eff_heat_block_tile)
cg.game.player.hand.cards.append(card_block)
idx = len(cg.game.player.hand.cards)-1
ok,msg = cg.game.play_card(idx)
print('\nPlayed block card:', ok, msg)
print('pending after play:', cg.game.pending)
# simulate selecting empty tile (6,1)
r,c = 6,1
# ensure tile empty
print('get_piece_at(6,1):', cg.get_piece_at(r,c))
# UI would set blocked_tiles; emulate selection
if cg.game.pending and cg.game.pending.kind=='target_tile':
    turns = cg.game.pending.info.get('turns',2)
    applies_to = cg.game.pending.info.get('for_color','black')
    cg.game.blocked_tiles[(r,c)] = turns
    cg.game.blocked_tiles_owner[(r,c)] = applies_to
    cg.game.pending = None
    print('applied blocked_tiles:', cg.game.blocked_tiles, cg.game.blocked_tiles_owner)
else:
    print('no pending target_tile')
# Now check black pawn moves (should not include (6,1))
black_piece = None
for p in cg.chess.pieces:
    if getattr(p,'color',None)=='black':
        black_piece = p
        break
print('black piece at:', getattr(black_piece,'row',None), getattr(black_piece,'col',None))
print('black valid moves:', cg.get_valid_moves(black_piece))

# -- Test 2: Freeze piece (氷結) --
# add freeze card and a fresh turn
card_freeze = cc.Card('氷結',1, cc.eff_freeze_piece)
cg.game.player.hand.cards.append(card_freeze)
idx = len(cg.game.player.hand.cards)-1
ok,msg = cg.game.play_card(idx)
print('\nPlayed freeze card:', ok, msg)
print('pending after play:', cg.game.pending)
# simulate selecting the black piece to freeze
if cg.game.pending and cg.game.pending.kind=='target_piece':
    turns = cg.game.pending.info.get('turns',1)
    cg.game.frozen_pieces[id(black_piece)] = turns
    cg.game.pending = None
    print('applied frozen_pieces:', cg.game.frozen_pieces)
else:
    print('no pending target_piece')
# Now get_valid_moves for frozen black piece should be []
print('black valid moves after freeze:', cg.get_valid_moves(black_piece))

# -- Test 3: Storm jump once --
card_jump = cc.Card('暴風', 1, cc.eff_storm_jump_once)
cg.game.player.hand.cards.append(card_jump)
idx = len(cg.game.player.hand.cards)-1
ok,msg = cg.game.play_card(idx)
print('\nPlayed jump card:', ok, msg)
print('player.next_move_can_jump:', cg.game.player.next_move_can_jump)
# To test jump effect, create a white rook with a blocking piece in front and check moves
# Clear and set scenario: white rook at (4,0), blocking piece at (5,0), target (6,0)
cg.chess.pieces.clear()
white_rook = cg.chess.Piece(4,0,'R','white')
blocker = cg.chess.Piece(5,0,'P','white')
target = cg.chess.Piece(6,0,'P','black')
cg.chess.pieces.extend([white_rook, blocker, target])
# get_valid_moves for white_rook should include (6,0) due to jump
moves = cg.get_valid_moves(white_rook)
print('white rook moves with jump (expect include (6,0)):', moves)

print('\nTests done')
