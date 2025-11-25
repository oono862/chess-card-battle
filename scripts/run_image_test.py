import importlib.util, os, sys
p = os.path.abspath(r'c.c.b/assets/image_loader.py')
if not os.path.exists(p):
    print('missing file', p); sys.exit(1)
spec = importlib.util.spec_from_file_location('c_c_b_image_loader', p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
names = ['ハンです☆','命がけのギャンブル','負けるわけないだろwww','鉄壁']
for n in names:
    try:
        s = mod.get_card_image(n, (10,10))
        print('->', n, type(s))
    except Exception as e:
        print('ERROR for', n, e)
