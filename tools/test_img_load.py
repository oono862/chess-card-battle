import pygame, sys, os
pygame.init()
paths = [r"images/Chess_k_white.png", r"images/ChatGPT Image 2025年10月21日 14_06_32.png"]
for p in paths:
    full = os.path.abspath(p)
    print('Trying', full)
    try:
        surf = pygame.image.load(full)
        print('Loaded', p, 'size=', surf.get_size())
    except Exception as e:
        print('Failed to load', p, '->', repr(e))
pygame.quit()
