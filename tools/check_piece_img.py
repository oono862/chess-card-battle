import pygame, os, sys
pygame.init()
# Make project root importable
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
from importlib.machinery import SourceFileLoader
loader = SourceFileLoader('image_loader', os.path.join(root, 'c.c.b', 'assets', 'image_loader.py'))
image_loader = loader.load_module()
print('image_loader.IMG_DIR =', getattr(image_loader, 'IMG_DIR', None))
print('exists IMG_DIR?', os.path.isdir(getattr(image_loader, 'IMG_DIR', '')))
print('files under IMG_DIR:')
try:
    for f in os.listdir(image_loader.IMG_DIR):
        print(' -', f)
except Exception as e:
    print('list failed', e)

for name in ['K','Q','R','B','N','P']:
    for color in ['white','black','White','Black']:
        surf = image_loader.get_piece_image_surface(name, color, (60,60))
        print(name, color, '->', 'OK' if surf is not None else 'None')
        # Direct load test
        fname = f"Chess_{name.lower()}_{color}.png"
        p = os.path.join(image_loader.IMG_DIR, fname)
        try:
            ok = os.path.exists(p)
            print('   path exists?', ok, 'path=', p)
            if ok:
                try:
                    im = pygame.image.load(p)
                    print('   direct pygame load OK size=', im.get_size())
                except Exception as e:
                    print('   direct pygame load failed ->', e)
                    # Try with convert_alpha and smoothscale like image_loader does
                    try:
                        im = pygame.image.load(p)
                        ima = im.convert_alpha()
                        s = pygame.transform.smoothscale(ima, (60,60))
                        print('   convert_alpha+scale OK size=', s.get_size())
                    except Exception as e:
                        print('   convert_alpha+scale failed ->', repr(e))
        import inspect
        print('\n--- image_loader.get_piece_image_surface source ---')
        print(inspect.getsource(image_loader.get_piece_image_surface))
        except Exception as e:
            print('   path check failed ->', e)
pygame.quit()
