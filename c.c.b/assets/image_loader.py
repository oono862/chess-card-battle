"""Image loading and caching for cards and chess pieces."""

import os
import sys
import pygame
import time

# Import path resolver for PyInstaller compatibility
try:
    from ..utils.path_resolver import get_resource_path, IMAGES_DIR, path_exists_cached
except Exception:
    try:
        from c.c.b.utils.path_resolver import get_resource_path, IMAGES_DIR, path_exists_cached
    except Exception:
        # Fallback: define locally if path_resolver is not available
        def get_resource_path(rel_path):
            if getattr(sys, 'frozen', False):
                return os.path.join(sys._MEIPASS, rel_path)
            else:
                return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), rel_path)
        IMAGES_DIR = get_resource_path('images')
        # フォールバック時はキャッシュなしで通常のos.path.existsを使用
        def path_exists_cached(path):
            return os.path.exists(path)

# Import animation module safely: try package-relative, then absolute, then fallback to None
try:
    from . import animation as animation_mod
except Exception:
    try:
        from c.c.b.assets import animation as animation_mod
    except Exception:
        try:
            import animation as animation_mod
        except Exception:
            animation_mod = None

# Determine image directory using path resolver (PyInstaller compatible)
IMG_DIR = IMAGES_DIR

# Image caches
_image_cache = {}
_piece_image_cache = {}
# GIF animation cache: {(name, size): {'frames': [Surface], 'durations': [ms], 'current_frame': int, 'last_update': time}}
_gif_animation_cache = {}

# 画像ファイル名インデックス（再帰検索の高速化）
# { normalized_filename_lower: full_path }
_image_file_index = None
_image_file_index_built = False


def _build_image_index():
    """画像ディレクトリ内の全ファイルをインデックス化する。
    
    PyInstaller環境での毎回のos.walk()を避けるため、
    最初の1回だけ実行してキャッシュする。
    """
    global _image_file_index, _image_file_index_built
    if _image_file_index_built:
        return _image_file_index
    
    _image_file_index = {}
    
    if not os.path.isdir(IMG_DIR):
        _image_file_index_built = True
        return _image_file_index
    
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'}
    
    try:
        for root, _dirs, files in os.walk(IMG_DIR):
            for f in files:
                fn, ext = os.path.splitext(f)
                if ext.lower() in valid_extensions:
                    full_path = os.path.join(root, f)
                    # 正規化したファイル名をキーとして保存
                    fn_lower = fn.lower()
                    fn_lower_nospace = fn_lower.replace(' ', '').replace('\u3000', '')
                    
                    # 両方のキーで保存（スペースあり/なし）
                    if fn_lower not in _image_file_index:
                        _image_file_index[fn_lower] = full_path
                    if fn_lower_nospace not in _image_file_index:
                        _image_file_index[fn_lower_nospace] = full_path
    except Exception:
        pass
    
    _image_file_index_built = True
    return _image_file_index


def _find_image_in_index(name):
    """インデックスから画像パスを検索する。
    
    Args:
        name: 画像名（拡張子なし）
        
    Returns:
        str or None: 見つかったパス、またはNone
    """
    index = _build_image_index()
    if not index:
        return None
    
    name_lower = name.lower()
    name_lower_nospace = name_lower.replace(' ', '').replace('\u3000', '')
    
    # 完全一致を優先
    if name_lower in index:
        return index[name_lower]
    if name_lower_nospace in index:
        return index[name_lower_nospace]
    
    return None


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
    
    For animated GIFs, returns the current frame of the animation.
    """
    # Check if this is an animated GIF
    if is_animated_gif(name):
        frame = get_current_gif_frame(name, size)
        if frame is not None:
            return frame
        # If GIF loading failed, fall through to normal image loading
    
    key = (name, size)
    if key in _image_cache:
        return _image_cache[key]

    surf = None

    NAME_TO_FILE = {
        # GIF animated cards
        '負けるわけないだろwww': '負けるわけないだろwww.gif',
        # Cards with special spacing or characters
        'ハンです☆': 'ハン です☆.png',
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
        if path_exists_cached(path):
            def _try_load(p):
                # Try pygame.image.load + convert_alpha
                try:
                    img = pygame.image.load(p).convert_alpha()
                    return img
                except Exception:
                    pass
                # Try pygame.image.load without convert
                try:
                    img = pygame.image.load(p)
                    return img
                except Exception:
                    pass
                # Pillow fallback
                try:
                    from PIL import Image
                    im = Image.open(p).convert('RGBA')
                    return pygame.image.fromstring(im.tobytes(), im.size, im.mode).convert_alpha()
                except Exception:
                    return None

            img = _try_load(path)
            if img is not None:
                try:
                    surf = pygame.transform.smoothscale(img, size)
                except Exception:
                    surf = None

    # 1) direct candidates
    if surf is None:
        for cand in candidates:
            path = os.path.join(IMG_DIR, cand)
            if path_exists_cached(path):
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

    # 2) normalized candidates
    if surf is None and norm_name != name:
        for cand in [f"{norm_name}.png", f"{norm_name}.PNG", f"{norm_name}.jpg", f"{norm_name}.jpeg", f"{norm_name}.webp", f"{norm_name}.bmp", f"{norm_name}.gif"]:
            path = os.path.join(IMG_DIR, cand)
            if path_exists_cached(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    surf = pygame.transform.smoothscale(img, size)
                    break
                except Exception:
                    pass

    # 3) インデックスベースの検索（os.walk()の代わり）
    if surf is None:
        indexed_path = _find_image_in_index(name)
        if indexed_path:
            try:
                img = pygame.image.load(indexed_path).convert_alpha()
                surf = pygame.transform.smoothscale(img, size)
            except Exception:
                pass

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
    """Check if the card name corresponds to an animated GIF."""
    NAME_TO_FILE = {
        '負けるわけないだろwww': '負けるわけないだろwww.gif',
    }
    
    def _normalize(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = s.strip().replace('\u3000', ' ')
        return ' '.join(s.split())
    
    norm_name = _normalize(name)
    
    # Check NAME_TO_FILE mapping
    for k in (name, norm_name, norm_name.replace(' ', ''), norm_name.replace('\u3000', '').replace(' ', '')):
        mapped = NAME_TO_FILE.get(k)
        if mapped and mapped.lower().endswith('.gif'):
            return True
    
    return False


def get_card_gif_animation(name: str, size=(72, 96)):
    """Load all frames from a GIF animation and cache them.
    
    Returns a dictionary with:
    - 'frames': list of pygame.Surface objects
    - 'durations': list of frame durations in milliseconds
    - 'current_frame': current frame index
    - 'last_update': last update timestamp
    """
    key = (name, size)
    if key in _gif_animation_cache:
        return _gif_animation_cache[key]
    
    # Find the GIF file
    NAME_TO_FILE = {
        '負けるわけないだろwww': '負けるわけないだろwww.gif',
    }
    
    def _normalize(s: str) -> str:
        if not isinstance(s, str):
            return s
        s = s.strip().replace('\u3000', ' ')
        return ' '.join(s.split())
    
    norm_name = _normalize(name)
    
    # Get filename from mapping
    gif_filename = None
    for k in (name, norm_name, norm_name.replace(' ', ''), norm_name.replace('\u3000', '').replace(' ', '')):
        mapped = NAME_TO_FILE.get(k)
        if mapped:
            gif_filename = mapped
            break
    
    if not gif_filename:
        return None
    
    gif_path = os.path.join(IMG_DIR, gif_filename)
    if not os.path.exists(gif_path):
        return None
    
    # Load all frames using PIL
    try:
        from PIL import Image
        
        gif = Image.open(gif_path)
        frames = []
        durations = []
        
        frame_count = 0
        while True:
            try:
                # Get current frame
                frame = gif.convert('RGBA')
                
                # Convert PIL image to pygame surface
                mode = frame.mode
                size_pil = frame.size
                data = frame.tobytes()
                
                pygame_surf = pygame.image.fromstring(data, size_pil, mode)
                pygame_surf = pygame.transform.smoothscale(pygame_surf, size)
                frames.append(pygame_surf)
                
                # Get frame duration (in milliseconds)
                duration = gif.info.get('duration', 100)  # default 100ms
                durations.append(duration)
                
                frame_count += 1
                gif.seek(frame_count)
                
            except EOFError:
                # End of frames
                break
        
        if not frames:
            return None
        
        try:
            scale = animation_mod.get_anim_time_scale() if hasattr(animation_mod, 'get_anim_time_scale') else 1.0
            scaled_durations = [int(d * scale) for d in durations]
            try:
                print(f"image_loader: loaded gif {gif_filename} key={key} scale={scale} durations_sample={scaled_durations[:5]}")
            except Exception:
                pass
        except Exception:
            scaled_durations = durations
        anim_data = {
            'frames': frames,
            'durations': scaled_durations,
            'current_frame': 0,
            'last_update': time.time()
        }
        
        _gif_animation_cache[key] = anim_data
        return anim_data
        
    except ImportError:
        return None
    except Exception:
        return None


def get_current_gif_frame(name: str, size=(72, 96)):
    """Get the current frame of an animated GIF, automatically advancing frames.
    
    Returns the pygame.Surface of the current frame, or None if animation not loaded.
    """
    key = (name, size)
    anim_data = _gif_animation_cache.get(key)
    
    if not anim_data:
        # Try to load the animation
        anim_data = get_card_gif_animation(name, size)
        if not anim_data:
            return None
    
    frames = anim_data['frames']
    durations = anim_data['durations']
    current_frame = anim_data['current_frame']
    last_update = anim_data['last_update']
    
    if not frames:
        return None
    
    # Check if we need to advance to next frame
    current_time = time.time()
    elapsed_ms = (current_time - last_update) * 1000
    
    frame_duration = durations[current_frame] if current_frame < len(durations) else 100
    
    if elapsed_ms >= frame_duration:
        # Advance to next frame
        anim_data['current_frame'] = (current_frame + 1) % len(frames)
        anim_data['last_update'] = current_time
        current_frame = anim_data['current_frame']
    
    return frames[current_frame]
