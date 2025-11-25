import importlib.util, os

def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mods = {
    'c': r'c.c.b/assets/image_loader.py',
    'C': r'C.C.B/assets/image_loader.py'
}
for k,p in mods.items():
    p_abs = os.path.join(os.getcwd(), p.replace('/', os.sep))
    print('\n-- Module', k, p_abs)
    mod = load_mod(p_abs, f'image_loader_{k}')
    print('IMG_DIR =', mod.IMG_DIR)
    import pygame
    pygame.init()
    for name in ['ハンです☆','命がけのギャンブル','負けるわけないだろwww','鉄壁']:
        try:
            surf = mod.get_card_image(name, size=(10,10))
            print(' ', name, '->', type(surf))
        except Exception as e:
            print(' ', name, 'failed', e)
