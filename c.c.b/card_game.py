"""Compatibility wrapper for C.C.B package: execute the original 'CardGame.py'."""
import os
import runpy

_orig = os.path.join(os.path.dirname(__file__), 'CardGame.py')
_ns = runpy.run_path(_orig, run_name='c_c_b_cardgame_module')
globals().update(_ns)
