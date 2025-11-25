import os, sys, pygame
pygame.init()
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path: sys.path.insert(0, root)
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader('image_loader', os.path.join(root,'c.c.b','assets','image_loader.py'))
image_loader = loader.load_module()
cc_loader = SourceFileLoader('card_core', os.path.join(root,'c.c.b','card_core.py'))
card_core = cc_loader.load_module()

rule_deck = card_core.make_rule_cards_deck()
unique = sorted({c.name for c in rule_deck.cards})
print('Reloading card images (force) ...')
for n in unique:
    surf = image_loader.get_card_image(n, force_reload=True)
    border = surf.get_at((0,0))[:3]
    center = surf.get_at((surf.get_width()//2, surf.get_height()//2))[:3]
    placeholder_like = (border==(80,80,80) and center==(220,220,230))
    print(f' {n}: placeholder={placeholder_like}')
pygame.quit()
