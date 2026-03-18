import random
import logging

logger = logging.getLogger(__name__)

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
