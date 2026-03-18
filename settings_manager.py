import os
import random
import logging
from PIL import Image

logger = logging.getLogger(__name__)

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")

def _build_duration_cache():
    cache = {}
    try:
        for filename in os.listdir(MEDIA_DIR):
            if filename.lower().endswith(".gif"):
                try:
                    with Image.open(os.path.join(MEDIA_DIR, filename)) as img:
                        total_ms = 0
                        if getattr(img, "is_animated", False):
                            for frame in range(img.n_frames):
                                img.seek(frame)
                                total_ms += img.info.get("duration", 100)
                        cache[filename] = total_ms if total_ms > 0 else 8000
                except Exception:
                    cache[filename] = 8000
    except FileNotFoundError:
        pass
    return cache

_DURATION_CACHE = _build_duration_cache()

def get_gif_duration_ms(filename):
    """Returns the total playback duration of a GIF in milliseconds."""
    return _DURATION_CACHE.get(filename, 8000)

# Media Mapping: Display Name -> Filename(s)
MEDIA_OPTIONS = {
    "90's 1": ["90s1TurboTack.gif"],
    "90's 2": ["90s2TurboTack.gif"],
    "90's (Mix)": ["90s1TurboTack.gif", "90s2TurboTack.gif"],
    "Cottagecore": ["CottageCoreTurboTack.gif"],
    "Fantasy Dragon": ["FantasyDragonTurboTack.gif"],
    "Retro 4": ["Retro4TurboTack.gif"],
    "Spooky 1": ["Spooky1TurboTack.gif"],
    "Spooky 2": ["Spooky2TurboTack.gif"],
    "Spooky (Mix)": ["Spooky1TurboTack.gif", "Spooky2TurboTack.gif"],
    "TV Static": ["StaticTVTurboTack.gif"],
    "Train Luggage": ["TrainLuggageTurboTack.gif"],
    "Western": ["WesternTurboTack.gif"],
    "Random (Any)": "ALL"
}

def resolve_media_file(media_key):
    """
    Resolves a User Selection (e.g. '90's Mix') to a single filename.
    Now a standalone function so web_server.py can import it.
    """
    options = []
    
    if media_key == "Random (Any)":
        # Flatten all lists in MEDIA_OPTIONS except 'Random (Any)'
        all_files = []
        for k, v in MEDIA_OPTIONS.items():
            if k != "Random (Any)" and isinstance(v, list):
                all_files.extend(v)
        options = all_files
    elif media_key in MEDIA_OPTIONS:
        options = MEDIA_OPTIONS[media_key]
    
    if not options:
        return None
        
    # Pick one at random (Handles the 'Doubles' logic automatically)
    return random.choice(options)
