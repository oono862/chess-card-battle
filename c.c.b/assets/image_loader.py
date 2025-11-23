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
    
    Args:
        name: Card name (without extension)
        size: Target size tuple (width, height)
        
    Returns:
        pygame.Surface with the card image or placeholder
    """
    key = (name, size)
    if key in _image_cache:
        return _image_cache[key]

    surf = None
    # explicit name -> file mapping for special cards
    NAME_TO_FILE = {
        # map card display name to an image filename in images/
        "ハンです☆": "card_death_1.png",
        "命がけのギャンブル": "card_kaiji_Jo.png",
        "負けるわけないだろwww": "card_you_lose.gif",
        "鉄壁": "card_sh.png",
    }

    def _normalize(n: str) -> str:
        if not isinstance(n, str):
            return n
        # strip and convert full-width spaces to normal spaces, then collapse multiple spaces
        s = n.strip().replace('\u3000', ' ')
        # collapse runs of spaces
        while '  ' in s:
            s = s.replace('  ', ' ')
        return s

    norm_name = _normalize(name)

    # preferred candidate filenames (including GIF)
    candidates = [
        f"{name}.png", f"{name}.PNG",
        f"{name}.jpg", f"{name}.jpeg",
        f"{name}.webp", f"{name}.bmp", f"{name}.gif"
    ]

    # if there is an explicit mapping for this card name, try multiple variants
    mapped = None
    for k in (name, norm_name, norm_name.replace(' ', ''), norm_name.replace('\u3000', '').replace(' ', '')):
        mapped = NAME_TO_FILE.get(k)
        if mapped:
            break
    if mapped:
        path = os.path.join(IMG_DIR, mapped)
        if os.path.exists(path):
            # try multiple ways to load image to handle corrupted headers / formats
            def _try_load(p):
                # 1) pygame.load + convert_alpha
                try:
                    img = pygame.image.load(p).convert_alpha()
                    return img
                except Exception:
                    pass
                # 2) pygame.load without convert
                try:
                    img = pygame.image.load(p)
                    return img
                except Exception:
                    pass
                # 3) Pillow fallback
                try:
                    from PIL import Image
                    im = Image.open(p).convert('RGBA')
                    mode = im.mode
                    size_px = im.size
                    data = im.tobytes()
                    surf_local = pygame.image.fromstring(data, size_px, mode).convert_alpha()
                    return surf_local
                except Exception:
                    return None

            img = _try_load(path)
            if img is not None:
                try:
                    surf = pygame.transform.smoothscale(img, size)
                except Exception:
                    surf = None

    # try direct candidate filenames
    if surf is None:
        for cand in candidates:
            path = os.path.join(IMG_DIR, cand)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.smoothscale(img, size)
                    break
                except Exception:
                    try:
                        img = pygame.image.load(path)
                        surf = pygame.transform.smoothscale(img, size)
                        break
                    except Exception:
                        pass

    # try normalized name candidates if different
    if surf is None and norm_name != name:
        for cand in [f"{norm_name}.png", f"{norm_name}.PNG", f"{norm_name}.jpg", f"{norm_name}.jpeg", f"{norm_name}.webp", f"{norm_name}.bmp", f"{norm_name}.gif"]:
            path = os.path.join(IMG_DIR, cand)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.smoothscale(img, size)
                    break
                except Exception:
                    pass
    
    # 2) Recursive search (case-insensitive base name match)
    if surf is None and os.path.isdir(IMG_DIR):
        base_l = name.lower()
        base_l_nospace = base_l.replace(' ', '').replace('\u3000', '')
        for root, _dirs, files in os.walk(IMG_DIR):
            for f in files:
                fn, ext = os.path.splitext(f)
                fn_l = fn.lower()
                fn_l_nospace = fn_l.replace(' ', '').replace('\u3000', '')
                if ext.lower() in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"] and (
                    fn_l == base_l or fn_l_nospace == base_l_nospace
                ):
                    try:
                        path = os.path.join(root, f)
                        img = pygame.image.load(path).convert_alpha()
                        surf = pygame.transform.smoothscale(img, size)
                        break
                    except Exception:
                        continue
            if surf is not None:
                break
    
    # 3) Create placeholder if image not found
    if surf is None:
        surf = pygame.Surface(size, pygame.SRCALPHA)
        surf.fill((220, 220, 230))
        pygame.draw.rect(surf, (80, 80, 80), (0, 0, size[0], size[1]), 2)
        
        # Try to render card name on placeholder
        try:
            main = get_main_module()
            if main and hasattr(main, 'SMALL'):
                txt = main.SMALL.render(name, True, (30, 30, 30))
                surf.blit(txt, ((size[0]-txt.get_width())//2, (size[1]-txt.get_height())//2))
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
