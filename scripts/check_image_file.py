import os
IMG=os.path.abspath('images')
print('IMG_DIR=',IMG)
print('exists Image_F.gif ->', os.path.exists(os.path.join(IMG,'Image_F.gif')))
print('listing Image_*.gif ->', [f for f in os.listdir(IMG) if f.lower().startswith('image_')])
