import importlib.util, os, sys
p = os.path.join(os.getcwd(), 'Card Game.py')
spec = importlib.util.spec_from_file_location('card_game', p)
cg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cg)

print('modules loaded')
# simple board, single white pawn
cg.chess.pieces.clear()
wp = cg.chess.Piece(6,0,'P','white')
cg.chess.pieces.append(wp)
# ensure player's turn
cg.chess_current_turn = 'white'
# start player's card-game turn
cg.game.start_turn()
# give player the迅雷 card and play it
import card_core as cc
card = cc.Card('迅雷', 1, cc.eff_lightning_two_actions)
# append to hand and play
cg.game.player.hand.cards.append(card)
idx = len(cg.game.player.hand.cards)-1
ok,msg = cg.game.play_card(idx)
print('played 迅雷:', ok, msg)
print('player_consecutive_turns =', getattr(cg.game,'player_consecutive_turns',None))
# simulate first move
# compute pixel coordinates similar to verify script
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
sel_x = board_left + 0 * square_w + square_w//2
sel_y = board_top + 6 * square_h + square_h//2
dst_x = board_left + 0 * square_w + square_w//2
dst_y = board_top + 5 * square_h + square_h//2
cg.handle_mouse_click((sel_x, sel_y))
cg.handle_mouse_click((dst_x, dst_y))
print('after 1st move: player_consecutive_turns=', cg.game.player_consecutive_turns, 'chess_current_turn=', cg.chess_current_turn)
# perform second move (should still be player turn)
# select pawn again
cg.handle_mouse_click((sel_x, sel_y))
# try move to (4,0)
dst2_y = board_top + 4 * square_h + square_h//2
cg.handle_mouse_click((dst_x, dst2_y))
print('after 2nd move: player_consecutive_turns=', cg.game.player_consecutive_turns, 'chess_current_turn=', cg.chess_current_turn)
# attempt third move (should be blocked / switch to black)
cg.handle_mouse_click((sel_x, sel_y))
print('after attempt 3rd select: chess_current_turn=', cg.chess_current_turn)
print('game.log tail:')
for l in cg.game.log[-6:]:
    print('-', l)
print('done')
