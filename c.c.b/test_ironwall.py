import sys, os
# ensure the package folder is importable
pkg_path = os.path.join(os.path.dirname(__file__), 'chess-card-battle')
if pkg_path not in sys.path:
    sys.path.insert(0, pkg_path)

import card_core

print('== create game ==')
game = card_core.new_game_with_sample_deck()
print('Initial frozen_pieces:', game.frozen_pieces)

print('\n== human iron wall prevents freeze on white ==')
print('Set iron_wall on human')
card_core.eff_iron_wall(game, game.player)
print('human.iron_wall_active:', getattr(game.player, 'iron_wall_active', None))

class FakePiece:
    def __init__(self, name='P', color='white', row=1, col=1):
        self.name = name
        self.color = color
        self.row = row
        self.col = col
    def __repr__(self):
        return f"<Piece {self.name} {self.color} ({self.row},{self.col})>"

p = FakePiece()
res = game.apply_freeze_piece(p, 1, target_color='white', source_color='black', source_card_name='氷結')
print('apply_freeze_piece returned:', res)
print('human.iron_wall_active after:', getattr(game.player, 'iron_wall_active', None))
print('frozen_pieces:', game.frozen_pieces)

print('\n== human iron wall prevents blocked tile ==')
card_core.eff_iron_wall(game, game.player)
print('Set iron_wall again:', getattr(game.player, 'iron_wall_active', None))
ok = game.apply_blocked_tile((3,3), 2, applies_to='white', source_color='black', source_card_name='灼熱')
print('apply_blocked_tile returned:', ok)
print('blocked_tiles:', game.blocked_tiles)
print('blocked_tiles_owner:', game.blocked_tiles_owner)
print('\n== AI iron wall prevents player effect on black ==')
# set AI flag directly
game.ai_iron_wall_active = True
ok2 = game.apply_freeze_piece(p, 1, target_color='black', source_color='white', source_card_name='氷結')
print('apply_freeze_piece on black returned:', ok2)
print('ai_iron_wall_active now:', getattr(game, 'ai_iron_wall_active', None))
print('\nDone')
