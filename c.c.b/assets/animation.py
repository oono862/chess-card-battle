"""GIF animation loading and playback for special effects."""

import os
import sys
import pygame
import time as _ct_time

# Import path resolver for PyInstaller compatibility
try:
    from ..utils.path_resolver import get_resource_path, IMAGES_DIR
except Exception:
    try:
        from utils.path_resolver import get_resource_path, IMAGES_DIR
    except Exception:
        # Fallback: define locally if path_resolver is not available
        def get_resource_path(rel_path):
            if getattr(sys, 'frozen', False):
                return os.path.join(sys._MEIPASS, rel_path)
            else:
                return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), rel_path)
        IMAGES_DIR = get_resource_path('images')

# Use path resolver for image directory (PyInstaller compatible)
IMG_DIR = IMAGES_DIR

# GIF animation state and caches
heat_gif_frames_cache = None
heat_gif_durations = None
heat_gif_anim = {
    'playing': False,
    'start_time': 0.0,
    'total_duration': 0.0,
    'frames': None,
    'durations': None,
    'pos': None,  # (row, col)
}

# MG GIF (blocked-tile persistent effect) cache
mg_gif_frames_cache = None
mg_gif_durations = None
mg_gif_total_duration = 0.0
mg_gif_load_attempted = False
mg_gif_load_success = False

# 2P-color variant for AI-applied blocked tiles
mg_gif_2p_frames_cache = None
mg_gif_2p_durations = None
mg_gif_2p_total_duration = 0.0
mg_gif_2p_load_attempted = False
mg_gif_2p_load_success = False

# Ice GIF (氷結) cache + player
ic_gif_frames_cache = None
ic_gif_durations = None
ic_gif_load_attempted = False
ic_gif_load_success = False

ic_gif_anim = {
    'playing': False,
    'start_time': 0.0,
    'total_duration': 0.0,
    'frames': None,
    'durations': None,
    'pos': None,  # (row, col)
}

# Ice GIF speed factor (multiplier on per-frame durations)
IC_GIF_SPEED_FACTOR = 2.5
# Scale multiplier for ice GIF when rendering over a tile
IC_GIF_SCALE = 1.4

# Global time scale for animations (multiply frame durations).
# Set to 2.0 to make animations twice as long.
ANIM_TIME_SCALE = 2.0


def get_anim_time_scale():
    """Return the current global animation time scale (float)."""
    try:
        return float(ANIM_TIME_SCALE)
    except Exception:
        return 1.0


def set_anim_time_scale(scale: float):
    """Set the global animation time scale used when computing frame durations.

    Args:
        scale: positive float multiplier (e.g. 1.0 for normal, 2.0 for twice-as-long)
    """
    global ANIM_TIME_SCALE
    try:
        s = float(scale)
        if s <= 0:
            return
        ANIM_TIME_SCALE = s
        try:
            print(f"animation.py: set_anim_time_scale called -> {ANIM_TIME_SCALE}")
        except Exception:
            pass
    except Exception:
        pass
    # Invalidate some cached duration data so new scale takes effect
    try:
        global mg_gif_durations, mg_gif_total_duration, mg_gif_frames_cache
        global mg_gif_2p_durations, mg_gif_2p_total_duration, mg_gif_2p_frames_cache
        global heat_gif_durations, heat_gif_anim
        global ic_gif_durations, ic_gif_frames_cache, ic_gif_anim
        # recompute totals by setting to None so loaders recalc
        if 'mg_gif_durations' in globals():
            mg_gif_durations = None
            mg_gif_total_duration = 0.0
            try:
                mg_gif_frames_cache = None
            except Exception:
                pass
        if 'mg_gif_2p_durations' in globals():
            mg_gif_2p_durations = None
            mg_gif_2p_total_duration = 0.0
            try:
                mg_gif_2p_frames_cache = None
            except Exception:
                pass
        if 'heat_gif_durations' in globals():
            heat_gif_durations = None
            heat_gif_anim['durations'] = None
            heat_gif_anim['total_duration'] = 0.0
            try:
                heat_gif_frames_cache = None
            except Exception:
                pass
        if 'ic_gif_durations' in globals():
            ic_gif_durations = None
            ic_gif_anim['durations'] = None
            ic_gif_anim['total_duration'] = 0.0
            try:
                ic_gif_frames_cache = None
            except Exception:
                pass
        # Reset load attempts so loaders will re-run and pick up new durations
        try:
            mg_gif_load_attempted = False
        except Exception:
            pass
        try:
            mg_gif_2p_load_attempted = False
        except Exception:
            pass
        try:
            ic_gif_load_attempted = False
        except Exception:
            pass
    except Exception:
        pass


def _load_gif_frames(path: str):
    """Try to load GIF frames using Pillow if available, fallback to single surface.

    Returns (frames_list, durations_list). frames_list is a list of pygame.Surface.
    durations_list is list of durations in milliseconds.
    If Pillow is not available or loading fails, returns ([surface], [1000]).
    """
    try:
        from PIL import Image
    except Exception:
        # Pillow not available: fallback to loading the GIF as a single image
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None

    try:
        img = Image.open(path)
    except Exception:
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None

    frames = []
    durations = []
    try:
        for frame_index in range(0, getattr(img, 'n_frames', 1)):
            img.seek(frame_index)
            frame = img.convert('RGBA')
            mode = frame.mode
            size = frame.size
            data = frame.tobytes()
            surf = pygame.image.fromstring(data, size, mode).convert_alpha()
            frames.append(surf)
            dur = img.info.get('duration', 100)  # milliseconds
            durations.append(dur)
    except EOFError:
        pass
    
    if not frames:
        try:
            surf = pygame.image.load(path).convert_alpha()
            return [surf], [1000]
        except Exception:
            return None, None
    
    return frames, durations


def _ensure_mg_gif_loaded():
    """Lazily load Image_MG.gif frames into mg_gif_* globals."""
    global mg_gif_frames_cache, mg_gif_durations, mg_gif_total_duration
    global mg_gif_load_attempted, mg_gif_load_success
    
    if mg_gif_frames_cache is not None and mg_gif_durations is not None:
        return
    if mg_gif_load_attempted:
        return
    
    mg_gif_load_attempted = True
    gif_path = os.path.join(IMG_DIR, 'Image_MG.gif')
    frames, durations = _load_gif_frames(gif_path)
    
    if not frames:
        mg_gif_frames_cache = None
        mg_gif_durations = None
        mg_gif_total_duration = 0.0
        mg_gif_load_success = False
        # fallback: try pygame.image.load as a single-surface fallback
        try:
            surf = pygame.image.load(gif_path).convert_alpha()
            mg_gif_frames_cache = [surf]
            mg_gif_durations = [1000]
            mg_gif_total_duration = 1.0
            mg_gif_load_success = True
            return
        except Exception:
            return
    
    mg_gif_frames_cache = frames
    try:
        mg_gif_durations = [int(d * ANIM_TIME_SCALE) for d in (durations or [])]
    except Exception:
        mg_gif_durations = durations
    try:
        mg_gif_total_duration = sum(mg_gif_durations) / 1000.0
    except Exception:
        mg_gif_total_duration = len(mg_gif_durations) * 0.001 * 100 if mg_gif_durations else 0.0
    mg_gif_load_success = True


def _ensure_mg_gif_2p_loaded():
    """Lazily load Image_MG_2P.gif frames into mg_gif_2p_* globals."""
    global mg_gif_2p_frames_cache, mg_gif_2p_durations, mg_gif_2p_total_duration
    global mg_gif_2p_load_attempted, mg_gif_2p_load_success
    
    if mg_gif_2p_frames_cache is not None and mg_gif_2p_durations is not None:
        return
    if mg_gif_2p_load_attempted:
        return
    
    mg_gif_2p_load_attempted = True
    gif_path = os.path.join(IMG_DIR, 'Image_MG_2P.gif')
    frames, durations = _load_gif_frames(gif_path)
    
    if not frames:
        # fallback: try the standard MG gif
        gif_path2 = os.path.join(IMG_DIR, 'Image_MG.gif')
        frames, durations = _load_gif_frames(gif_path2)
    
    if not frames:
        mg_gif_2p_frames_cache = None
        mg_gif_2p_durations = None
        mg_gif_2p_total_duration = 0.0
        mg_gif_2p_load_success = False
        return
    
    mg_gif_2p_frames_cache = frames
    try:
        mg_gif_2p_durations = [int(d * ANIM_TIME_SCALE) for d in (durations or [])]
    except Exception:
        mg_gif_2p_durations = durations
    try:
        mg_gif_2p_total_duration = sum(mg_gif_2p_durations) / 1000.0
    except Exception:
        mg_gif_2p_total_duration = 0.0
    mg_gif_2p_load_success = True


def play_heat_gif_at(row: int, col: int):
    """Start playing the heat GIF animation centered at board square (row,col)."""
    global heat_gif_frames_cache, heat_gif_durations, heat_gif_anim
    
    gif_path = os.path.join(IMG_DIR, 'Image_F.gif')
    if heat_gif_frames_cache is None or heat_gif_durations is None:
        frames, durations = _load_gif_frames(gif_path)
        heat_gif_frames_cache = frames
        heat_gif_durations = durations

    frames = heat_gif_frames_cache
    durations = heat_gif_durations
    if not frames:
        return
    
    # Gimmick GIFs (heat) should use their native frame timings
    # and not be affected by the global ANIM_TIME_SCALE which is
    # intended only for piece-movement animations.
    try:
        # ensure integer ms values
        scaled = [int(d) for d in durations]
    except Exception:
        scaled = durations
    heat_gif_anim['frames'] = frames
    heat_gif_anim['durations'] = scaled
    heat_gif_anim['playing'] = True
    heat_gif_anim['start_time'] = _ct_time.time()
    heat_gif_anim['total_duration'] = sum(scaled) / 1000.0
    heat_gif_anim['pos'] = (row, col)


def _ensure_ic_gif_loaded():
    """Lazily load Image_ic GIF frames into ic_gif_* globals."""
    global ic_gif_frames_cache, ic_gif_durations, ic_gif_load_attempted, ic_gif_load_success
    
    if ic_gif_frames_cache is not None and ic_gif_durations is not None:
        return
    if ic_gif_load_attempted:
        return
    
    ic_gif_load_attempted = True
    candidates = [
        'image_ic2.gif',
        'Image_ic (1).gif',
        'Image_ic.gif',
        'Image_ic(1).gif',
        'Image_ic_1.gif',
        'Image_ic1.gif',
        'ice.gif',
    ]
    
    frames = None
    durations = None
    for cand in candidates:
        path = os.path.join(IMG_DIR, cand)
        f, d = _load_gif_frames(path)
        if f:
            frames = f
            durations = d
            break
    
    # Fallback: search directory for any file starting with 'image_ic'
    if not frames and os.path.isdir(IMG_DIR):
        for fn in os.listdir(IMG_DIR):
            if fn.lower().startswith('image_ic'):
                path = os.path.join(IMG_DIR, fn)
                f, d = _load_gif_frames(path)
                if f:
                    frames = f
                    durations = d
                    break
    
    # Final fallback: try loading as single image
    if not frames:
        try:
            path = os.path.join(IMG_DIR, 'image_ic2.gif')
            surf = pygame.image.load(path).convert_alpha()
            frames = [surf]
            durations = [1000]
            ic_gif_load_success = True
        except Exception:
            ic_gif_load_success = False
            return
    
    ic_gif_frames_cache = frames
    # Apply speed factor to make ice animation slower and more visible.
    # Do NOT apply ANIM_TIME_SCALE here: ice GIF timings are part of
    # the gimmick visual and should remain independent of piece-move
    # speed settings.
    try:
        durations = [int(d) for d in (durations or [1000])]
        slowed = [max(int(d * IC_GIF_SPEED_FACTOR), 120) for d in durations]
        ic_gif_durations = [int(d) for d in slowed]
        ic_gif_anim['total_duration'] = sum(ic_gif_durations) / 1000.0
    except Exception:
        ic_gif_durations = durations
        try:
            ic_gif_anim['total_duration'] = sum(durations) / 1000.0
        except Exception:
            ic_gif_anim['total_duration'] = len(durations) * 0.1 if durations else 0.0
    
    ic_gif_load_success = True


def play_ic_gif_at(row: int, col: int):
    """Start playing the ice GIF centered at board square (row,col)."""
    global ic_gif_frames_cache, ic_gif_durations, ic_gif_anim
    
    if ic_gif_frames_cache is None or ic_gif_durations is None:
        _ensure_ic_gif_loaded()
    
    frames = ic_gif_frames_cache
    durations = ic_gif_durations
    if not frames:
        return
    
    ic_gif_anim['frames'] = frames
    ic_gif_anim['durations'] = durations
    ic_gif_anim['playing'] = True
    ic_gif_anim['start_time'] = _ct_time.time()
    try:
        ic_gif_anim['total_duration'] = sum(durations) / 1000.0
    except Exception:
        ic_gif_anim['total_duration'] = len(durations) * 0.1 if durations else 0.0
    ic_gif_anim['pos'] = (row, col)
