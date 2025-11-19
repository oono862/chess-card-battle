import os, runpy, traceback

# Headless smoke test for Card Game.py
# Set SDL_VIDEODRIVER=dummy before running this (done by caller)
try:
    os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
    ns = runpy.run_path('Card Game.py', run_name='cardgame_module')
    keys = sorted(k for k in ns.keys() if not k.startswith('__'))
    print('MODULE_KEYS:', keys)
    print('has_get_valid_moves:', 'get_valid_moves' in ns)
    chess = ns.get('chess')
    pieces = None
    if chess is not None and hasattr(chess, 'pieces'):
        pieces = chess.pieces
    else:
        pieces = ns.get('pieces')
    print('pieces_present:', bool(pieces))
    if pieces:
        p = pieces[0]
        gv = ns.get('get_valid_moves')
        if gv:
            try:
                mv = gv(p)
                print('first_piece_moves_count:', len(mv))
            except Exception as e:
                print('error_calling_get_valid_moves:', repr(e))
        else:
            print('get_valid_moves not found')
    else:
        print('no pieces found to test moves')
except Exception:
    traceback.print_exc()
