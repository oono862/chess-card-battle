import runpy
import pathlib

root = pathlib.Path(__file__).resolve().parents[1]
card_core_path = str(root / 'c.c.b' / 'card_core.py')
cc_globals = runpy.run_path(card_core_path)

class CC: pass
cc = CC()
for k, v in cc_globals.items():
    setattr(cc, k, v)

print('=== Test: human protected (iron_wall_active) should block multiple tile attempts ===')
g = cc.new_game_with_rule_deck()
# Activate iron wall on human
human = g.player
print('initial player_ironwall_protection_turns =', getattr(g, 'player_ironwall_protection_turns', None))
res = cc.eff_iron_wall(g, human)
print('eff_iron_wall returned:', res)
# Try applying multiple blocked tiles from enemy source
applied = []
for i in range(3):
    ok = g.apply_blocked_tile((0, i), 2, applies_to='white', source_color='black', source_card_name='灼熱')
    applied.append(ok)
print('apply results (should be all False):', applied)

print('\n=== Test: human protection_turns should block as well ===')
g2 = cc.new_game_with_rule_deck()
# Set protection turns directly
setattr(g2, 'player_ironwall_protection_turns', 1)
print('player_ironwall_protection_turns =', g2.player_ironwall_protection_turns)
applied2 = []
for i in range(3):
    ok = g2.apply_blocked_tile((1, i), 2, applies_to='white', source_color='black', source_card_name='灼熱')
    applied2.append(ok)
print('apply results (should be all False):', applied2)

print('\n=== Test: AI side protection works too ===')
g3 = cc.new_game_with_rule_deck()
# Activate iron wall on AI
ai_player = getattr(g3, 'ai_player', None)
# Mark AI protection flags on game
setattr(g3, 'ai_ironwall_protection_turns', 1)
print('ai_ironwall_protection_turns =', g3.ai_ironwall_protection_turns)
applied3 = []
for i in range(3):
    ok = g3.apply_blocked_tile((2, i), 2, applies_to='black', source_color='white', source_card_name='灼熱')
    applied3.append(ok)
print('apply results (should be all False):', applied3)
