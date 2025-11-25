"""Compatibility wrapper: provide a module name without spaces.

This file executes the original "Card Game.py" (which contains the
real implementation) and injects its namespace into this module so
other scripts can import `card_game` or reference `card_game.py`.

Keeping the original file name avoids disturbing existing tooling
but callers can now use `card_game.py` (no space) which is safer.
"""
import os
import runpy

_orig = os.path.join(os.path.dirname(__file__), 'Card Game.py')
_ns = {}
try:
    # Execute the original file and capture its top-level namespace
    _ns = runpy.run_path(_orig, run_name='cardgame_module')
except FileNotFoundError:
    raise
except Exception:
    # If execution fails, re-raise to surface the error to callers
    raise

# Inject into this module's globals for convenience
globals().update(_ns)
