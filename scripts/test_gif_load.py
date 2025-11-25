import pygame, os
pygame.init()
path=os.path.abspath('images/Image_F.gif')
print('path', path, 'exists', os.path.exists(path))
try:
    s=pygame.image.load(path)
    print('pygame loaded', type(s))
except Exception as e:
    print('pygame load error', e)
try:
    from PIL import Image
    im=Image.open(path)
    print('PIL opened, frames=', getattr(im,'n_frames',1))
except Exception as e:
    print('PIL open error', e)
