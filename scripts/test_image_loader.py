import os
import importlib.util
spec = importlib.util.spec_from_file_location('image_loader', r'c.c.b/assets/image_loader.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('IMG_DIR =', mod.IMG_DIR)
for name in ['ハンです☆','命がけのギャンブル','負けるわけないだろwww','鉄壁']:
    print('\nNAME:', name)
    candidates = ['card_death_1.png','card_kaiji_Jo.png','card_you_lose.gif','card_sh.png']
    for f in candidates:
        p = os.path.join(mod.IMG_DIR, f)
        print('  exists', f, os.path.exists(p), p)
    try:
        import pygame
        pygame.init()
        surf = mod.get_card_image(name, size=(10,10))
        print('  get_card_image returned surface:', type(surf))
    except Exception as e:
        print('  get_card_image failed:', e)
