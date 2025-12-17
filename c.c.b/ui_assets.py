# ui_assets: helper utilities for loading images/GIFs and related assets
# This module extracts GIF frame loading logic from Card Game.py so it
# can be tested and reused.
import pygame
from typing import List, Tuple, Optional


def _load_gif_frames(path: str) -> Tuple[Optional[List[pygame.Surface]], Optional[List[int]]]:
    """Try to load GIF frames using Pillow if available, fallback to a single surface.

    Returns (frames_list, durations_list). frames_list is a list of pygame.Surface.
    durations_list is list of durations in milliseconds.
    If Pillow is not available or loading fails, returns ([surface], [1000]) when
    a single-image fallback succeeds, otherwise (None, None).
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
