import os
from PIL import Image

media_dir = "media"

print(f"{'FILENAME':<30} | {'SECONDS':<10} | {'MILLISECONDS'}")
print("-" * 60)

try:
    for filename in sorted(os.listdir(media_dir)):
        if filename.lower().endswith(".gif"):
            filepath = os.path.join(media_dir, filename)
            try:
                with Image.open(filepath) as img:
                    # Calculate total duration by summing up every frame's duration
                    total_duration_ms = 0
                    if getattr(img, "is_animated", False):
                        for frame in range(img.n_frames):
                            img.seek(frame)
                            # Default to 100ms if duration info is missing
                            total_duration_ms += img.info.get("duration", 100)
                    else:
                        # Static image default
                        total_duration_ms = 0 
                    
                    seconds = total_duration_ms / 1000
                    print(f"{filename:<30} | {seconds:<10.2f} | {total_duration_ms}")
            except Exception as e:
                print(f"{filename:<30} | ERROR      | {e}")
except FileNotFoundError:
    print("Media directory not found! Make sure you are in /opt/turbotack-bot")
