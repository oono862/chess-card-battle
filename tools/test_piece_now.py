import importlib.machinery, os, pygame
pygame.init()
loader = importlib.machinery.SourceFileLoader('image_loader', os.path.abspath('c.c.b/assets/image_loader.py'))
image_loader = loader.load_module()

print('IMG_DIR =', image_loader.IMG_DIR)
for name in ['K','Q','R','B','N','P']:
    surf_w = image_loader.get_piece_image_surface(name, 'white', (60,60))
    surf_b = image_loader.get_piece_image_surface(name, 'black', (60,60))
    print(f'{name}: white ->', 'OK' if surf_w is not None else 'None', ', black ->', 'OK' if surf_b is not None else 'None')

pygame.quit()
