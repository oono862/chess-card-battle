import importlib.util, os, sys
p = os.path.join(os.getcwd(), 'Card Game.py')
spec = importlib.util.spec_from_file_location('card_game', p)
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

print('module loaded')
# small board: white pawn at (6,0), white pawn at (6,1), black pawn at (1,0)
cg.chess.pieces.clear()
wp1 = cg.chess.Piece(6,0,'P','white')
wp2 = cg.chess.Piece(6,1,'P','white')
bp = cg.chess.Piece(1,0,'P','black')
cg.chess.pieces.extend([wp1, wp2, bp])
# ensure player starts
cg.chess_current_turn = 'white'
# start card-game turn
cg.game.start_turn()
print('turn_active after start_turn:', cg.game.turn_active)
# compute pixel position for square (6,0)
left_panel_width = 180
left_margin = 20
top_margin = 20
board_area_left = left_margin + left_panel_width + 20
board_area_top = top_margin
card_h = 140
reserved_bottom = card_h + 80
avail_height = cg.H - board_area_top - reserved_bottom
avail_width = cg.W - board_area_left - 20
board_size = min(avail_width, avail_height)
square_w = board_size // 8
square_h = square_w
board_left = board_area_left
board_top = board_area_top
# click to select wp1
sel_x = board_left + 0 * square_w + square_w//2
sel_y = board_top + 6 * square_h + square_h//2
cg.handle_mouse_click((sel_x, sel_y))
# click to move to (5,0)
dst_x = board_left + 0 * square_w + square_w//2
dst_y = board_top + 5 * square_h + square_h//2
cg.handle_mouse_click((dst_x, dst_y))
print('after first move: turn_active=', cg.game.turn_active, 'player_moved_this_turn=', getattr(cg.game,'player_moved_this_turn',None))
# mimic AI finishing its move: normally main_loop calls ai_make_move and sets back to white and decay_statuses
# For test, call ai_make_move (it will act on black pieces) then do the cleanup
try:
    cg.ai_make_move()
except Exception as e:
    print('ai_make_move exception (ignored):', e)
# simulate end-of-AI housekeeping
cg.chess_current_turn = 'white'
try:
    cg.game.decay_statuses()
except Exception as e:
    print('decay_statuses exception (ignored):', e)
# Now attempt to select wp2 and move (should be blocked because turn_active is False)
sel2_x = board_left + 1 * square_w + square_w//2
sel2_y = board_top + 6 * square_h + square_h//2
cg.handle_mouse_click((sel2_x, sel2_y))
dst2_x = board_left + 1 * square_w + square_w//2
dst2_y = board_top + 5 * square_h + square_h//2
cg.handle_mouse_click((dst2_x, dst2_y))
print('after attempted second move: turn_active=', cg.game.turn_active)
# inspect last log messages
print('last game.log entries:')
for l in cg.game.log[-6:]:
    print('-', l)

print('verify done')
