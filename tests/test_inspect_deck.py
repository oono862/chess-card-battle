import runpy
import os
p = os.path.join('c.c.b','Card Game.py')
mod = runpy.run_path(p)
ng = mod.get('new_game_with_mode')
if ng is None:
    print('new_game_with_mode not found')
else:
    g = ng('fixed')
    print('deck_count=', len(getattr(g.player.deck,'cards', [])))
    print('hand_count=', len(getattr(g.player.hand,'cards', [])))
    print('hand_names=', [c.name for c in g.player.hand.cards])
