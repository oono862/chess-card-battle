"""Image loading and caching for cards and chess pieces."""

import os
import sys
import pygame

# Determine image directory
try:
    # When imported as module from BBC folder structure
    # BBC/assets/image_loader.py -> go up to BBC -> go up to project root -> images
    _current_dir = os.path.dirname(__file__)  # BBC/assets
    _bbc_dir = os.path.dirname(_current_dir)  # BBC
    _project_root = os.path.dirname(_bbc_dir)  # project root
    IMG_DIR = os.path.join(_project_root, "images")
except Exception:
    # Fallback
    IMG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "images")

# Image caches
_image_cache = {}
_piece_image_cache = {}
_gif_animation_cache = {}  # Cache for GIF animation frames: {card_name: {'frames': [...], 'durations': [...], 'current_frame': 0, 'last_update': 0.0}}


def get_main_module():
    """Get the main B.B.C module for accessing FONT, SMALL, etc."""
    # Try to find the main module (B.B.C)
    main_mod_name = "B.B.C"
    if main_mod_name in sys.modules:
        return sys.modules[main_mod_name]
    # Fallback: try __main__
    if "__main__" in sys.modules:
        return sys.modules["__main__"]
    return None


def get_card_image(name: str, size=(72, 96)):
    """Load and cache a card image by name.

    Returns a pygame.Surface. Tries mapping, candidate filenames, normalized
    filenames, and finally a recursive search. Falls back to a placeholder.
    
    For animated GIFs, returns the current frame (updates automatically).
    """
    # Check if this is an animated GIF
    if is_animated_gif(name):
        frame = get_current_gif_frame(name, size)
        if frame is not None:
            return frame
        # If GIF loading failed, fall through to static image loading
    
    key = (name, size)
    if key in _image_cache:
        return _image_cache[key]

    surf = None

    NAME_TO_FILE = {
        "ハンです☆": "ハン です☆.png",
        "命がけのギャンブル": "命がけのギャンブル.png",
        "負けるわけないだろwww": "負けるわけないだろwww.gif",
        "鉄壁": "鉄壁.png",
    }

    def _normalize(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = s.strip().replace('\u3000', ' ')
        return ' '.join(s.split())

    norm_name = _normalize(name)

    candidates = [f"{name}.png", f"{name}.PNG", f"{name}.jpg", f"{name}.jpeg", f"{name}.webp", f"{name}.bmp", f"{name}.gif"]

    # 0) mapping
    mapped = None
    for k in (name, norm_name, norm_name.replace(' ', ''), norm_name.replace('\u3000', '').replace(' ', '')):
        mapped = NAME_TO_FILE.get(k)
        if mapped:
            break
    if mapped:
        path = os.path.join(IMG_DIR, mapped)
        print(f"image_loader: mapping {name} -> {mapped}, fullpath={path}, exists={os.path.exists(path)}")
        if os.path.exists(path):
            def _try_load(p):
                # Try pygame.image.load + convert_alpha
                try:
                    img = pygame.image.load(p).convert_alpha()
                    print(f"image_loader: _try_load - pygame.convert_alpha succeeded for {p}")
                    return img
                except Exception as e:
                    print(f"image_loader: _try_load - pygame.convert_alpha failed for {p}: {e}")
                # Try pygame.image.load without convert
                try:
                    img = pygame.image.load(p)
                    print(f"image_loader: _try_load - pygame.load succeeded for {p}")
                    return img
                except Exception as e:
                    print(f"image_loader: _try_load - pygame.load failed for {p}: {e}")
                # Pillow fallback
                try:
                    from PIL import Image
                    im = Image.open(p).convert('RGBA')
                    print(f"image_loader: _try_load - Pillow opened {p}")
                    return pygame.image.fromstring(im.tobytes(), im.size, im.mode).convert_alpha()
                except Exception as e:
                    print(f"image_loader: _try_load - Pillow failed for {p}: {e}")
                    return None

            img = _try_load(path)
            if img is not None:
                try:
                    surf = pygame.transform.smoothscale(img, size)
                    print(f"image_loader: loaded mapped image for '{name}' -> {mapped}")
                except Exception:
                    surf = None

    # 1) direct candidates
    if surf is None:
        for cand in candidates:
            path = os.path.join(IMG_DIR, cand)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.smoothscale(img, size)
                    print(f"image_loader: loaded candidate image for '{name}' -> {path}")
                    break
                except Exception:
                    try:
                        img = pygame.image.load(path)
                        surf = pygame.transform.smoothscale(img, size)
                        print(f"image_loader: loaded candidate image for '{name}' -> {path}")
                        break
                    except Exception:
                        pass

    # 2) normalized candidates
    if surf is None and norm_name != name:
        for cand in [f"{norm_name}.png", f"{norm_name}.PNG", f"{norm_name}.jpg", f"{norm_name}.jpeg", f"{norm_name}.webp", f"{norm_name}.bmp", f"{norm_name}.gif"]:
            path = os.path.join(IMG_DIR, cand)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.smoothscale(img, size)
                    print(f"image_loader: loaded normalized image for '{name}' -> {path}")
                    break
                except Exception:
                    pass

    # 3) recursive search
    if surf is None and os.path.isdir(IMG_DIR):
        base_l = name.lower()
        base_l_nospace = base_l.replace(' ', '').replace('\u3000', '')
        for root, _dirs, files in os.walk(IMG_DIR):
            for f in files:
                fn, ext = os.path.splitext(f)
                fn_l = fn.lower()
                fn_l_nospace = fn_l.replace(' ', '').replace('\u3000', '')
                if ext.lower() in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"] and (fn_l == base_l or fn_l_nospace == base_l_nospace):
                    try:
                        path = os.path.join(root, f)
                        img = pygame.image.load(path).convert_alpha()
                        surf = pygame.transform.smoothscale(img, size)
                        print(f"image_loader: loaded recursive image for '{name}' -> {path}")
                        break
                    except Exception:
                        continue
            if surf is not None:
                break

    # placeholder
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((220, 220, 230))
        pygame.draw.rect(surf, (80, 80, 80), (0, 0, size[0], size[1]), 2)
        try:
            main = get_main_module()
            if main and hasattr(main, 'SMALL'):
                txt = main.SMALL.render(name, True, (30, 30, 30))
                surf.blit(txt, ((size[0]-txt.get_width())//2, (size[1]-txt.get_height())//2))
        except Exception:
            pass
        try:
            print(f"image_loader: no image found for '{name}', using placeholder")
        except Exception:
            pass

    _image_cache[key] = surf
    return surf


def get_piece_image_surface(name: str, color: str, size: tuple):
    """Return a pygame.Surface for the given chess piece.
    
    Args:
        name: Piece name (single letter: 'K', 'Q', 'R', 'B', 'N', 'P')
        color: Piece color ('white' or 'black')
        size: Target size tuple (width, height)
        
    Returns:
        pygame.Surface with the piece image or None if not found
    """
    key = (name, color, size)
    if key in _piece_image_cache:
        return _piece_image_cache[key]
    
    # Filename convention: Chess_{letter_lower}_{color}.png
    fname = f"Chess_{name.lower()}_{color}.png"
    path = os.path.join(IMG_DIR, fname)
    surf = None
    
    try:
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            surf = pygame.transform.smoothscale(img, size)
    except Exception:
        surf = None
    
    _piece_image_cache[key] = surf
    return surf


def is_animated_gif(name: str) -> bool:
    """Check if a card uses an animated GIF."""
    NAME_TO_FILE = {
        "ハンです☆": "ハン です☆.png",
        "命がけのギャンブル": "命がけのギャンブル.png",
        "負けるわけないだろwww": "負けるわけないだろwww.gif",
        "鉄壁": "鉄壁.png",
    }
    mapped = NAME_TO_FILE.get(name, f"{name}.gif")
    return mapped.lower().endswith('.gif')


def get_card_gif_animation(name: str, size=(72, 96)):
    """Load and cache GIF animation frames for a card.
    
    Returns dict with 'frames', 'durations', 'current_frame', 'last_update'
    or None if not a GIF or loading fails.
    """
    if not is_animated_gif(name):
        return None
    
    if name in _gif_animation_cache:
        return _gif_animation_cache[name]
    
    NAME_TO_FILE = {
        "ハンです☆": "ハン です☆.png",
        "命がけのギャンブル": "命がけのギャンブル.png",
        "負けるわけないだろwww": "負けるわけないだろwww.gif",
        "鉄壁": "鉄壁.png",
    }
    
    mapped = NAME_TO_FILE.get(name, f"{name}.gif")
    path = os.path.join(IMG_DIR, mapped)
    
    if not os.path.exists(path):
        return None
    
    try:
        from PIL import Image
        im = Image.open(path)
        
        frames = []
        durations = []
        
        try:
            while True:
                # Convert current frame to RGBA
                frame = im.convert('RGBA')
                # Convert PIL image to pygame surface
                mode = frame.mode
                data = frame.tobytes()
                surf = pygame.image.fromstring(data, frame.size, mode)
                # Scale to target size
                scaled = pygame.transform.smoothscale(surf, size)
                frames.append(scaled)
                
                # Get frame duration (in milliseconds)
                duration = im.info.get('duration', 100)  # default 100ms
                durations.append(duration)
                
                # Move to next frame
                im.seek(im.tell() + 1)
        except EOFError:
            pass  # End of GIF frames
        
        if frames:
            anim_data = {
                'frames': frames,
                'durations': durations,
                'current_frame': 0,
                'last_update': 0.0
            }
            _gif_animation_cache[name] = anim_data
            print(f"image_loader: loaded {len(frames)} frames for animated GIF '{name}'")
            return anim_data
    except Exception as e:
        print(f"image_loader: failed to load GIF animation for '{name}': {e}")
        return None
    
    return None


def get_current_gif_frame(name: str, size=(72, 96)):
    """Get current frame of animated GIF for a card.
    
    Updates frame based on time elapsed since last update.
    Returns a pygame.Surface or None.
    """
    import time
    
    anim_data = get_card_gif_animation(name, size)
    if not anim_data:
        return None
    
    current_time = time.time() * 1000  # milliseconds
    elapsed = current_time - anim_data['last_update']
    
    current_idx = anim_data['current_frame']
    frame_duration = anim_data['durations'][current_idx]
    
    # Check if it's time to advance to next frame
    if elapsed >= frame_duration:
        anim_data['current_frame'] = (current_idx + 1) % len(anim_data['frames'])
        anim_data['last_update'] = current_time
    
    return anim_data['frames'][anim_data['current_frame']]
