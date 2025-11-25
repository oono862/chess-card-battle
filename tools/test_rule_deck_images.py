import os, sys, pygame
pygame.init()
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader('image_loader', os.path.join(root, 'c.c.b', 'assets', 'image_loader.py'))
image_loader = loader.load_module()
# card_core import
import importlib.machinery
cc_path = os.path.join(root, 'c.c.b', 'card_core.py')
loader_cc = importlib.machinery.SourceFileLoader('card_core_module', cc_path)
card_core = loader_cc.load_module()

IMG_DIR = image_loader.IMG_DIR
print('IMG_DIR =', IMG_DIR)

# Unique card names from rule deck
rule_deck = card_core.make_rule_cards_deck()
unique_names = sorted({c.name for c in rule_deck.cards})
print('Card names:', unique_names)

exts = ['.png','.PNG','.jpg','.jpeg','.webp','.bmp']
results = []
for name in unique_names:
    surf = image_loader.get_card_image(name, size=(72,96))
    # heuristic: placeholder has a gray border pixel (80,80,80) at (0,0) and fill (220,220,230)
    border_px = surf.get_at((0,0))[:3]
    center_px = surf.get_at((surf.get_width()//2, surf.get_height()//2))[:3]
    placeholder_like = (border_px == (80,80,80) and center_px == (220,220,230))
    file_exists = any(os.path.exists(os.path.join(IMG_DIR, f'{name}{e}')) for e in exts)
    results.append((name, file_exists, placeholder_like))

missing = [r for r in results if not r[1]]
placeholder = [r for r in results if r[2]]

print('\nResult per card:')
for name, file_exists, placeholder_like in results:
    print(f' - {name}: file={"YES" if file_exists else "NO"}, placeholder={"YES" if placeholder_like else "NO"}')

print(f'\nTotal cards: {len(results)}')
print(f'Files missing: {len(missing)} -> {[m[0] for m in missing]}')
print(f'Using placeholder: {len(placeholder)} -> {[p[0] for p in placeholder]}')

pygame.quit()
