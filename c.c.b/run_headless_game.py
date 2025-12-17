import os
import runpy
import threading
import time
import sys
import pygame
import logging
from datetime import datetime

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')

# prepare log directory and file
logs_dir = os.path.join(os.path.dirname(__file__), 'headless_logs')
os.makedirs(logs_dir, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
logfile = os.path.join(logs_dir, f'headless_run_{ts}.log')

# configure logging to file (and keep console writes minimal)
logging.basicConfig(level=logging.DEBUG, filename=logfile,
                    format='%(asctime)s %(levelname)s %(name)s: %(message)s')

# Also capture stdout/stderr to the same file for complete trace
f = open(logfile, 'a', encoding='utf-8')
sys.stdout = f
sys.stderr = f

print('=== run_headless_game.py starting ===')
print('logfile:', logfile)
logging.getLogger().info('run_headless_game.py starting; logfile=%s', logfile)

ns = runpy.run_path('card_game.py', run_name='cardgame_module')
main_loop = ns.get('main_loop')
if main_loop is None:
    print('ERROR: main_loop not found in card_game.py')
    logging.getLogger().error('main_loop not found in card_game.py')
    sys.exit(1)


# Stopper thread: post QUIT after N seconds
def stopper(secs=6):
    time.sleep(secs)
    try:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        print('stopper: posted QUIT event')
        logging.getLogger().info('stopper posted QUIT event')
    except Exception as e:
        print('stopper error:', e)
        logging.getLogger().exception('stopper error')

thr = threading.Thread(target=stopper, args=(6,), daemon=True)
thr.start()

try:
    print('Starting headless main_loop (will stop after ~6s)')
    logging.getLogger().info('Starting headless main_loop')
    main_loop()
except SystemExit:
    print('main_loop exited via SystemExit')
    logging.getLogger().info('main_loop exited via SystemExit')
except Exception:
    import traceback
    traceback.print_exc()
    logging.getLogger().exception('main_loop raised unexpected exception')

print('headless run complete')
logging.getLogger().info('headless run complete')
f.flush()
f.close()
