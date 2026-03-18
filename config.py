import os
import base64
from dotenv import load_dotenv

load_dotenv()

# --- Credentials ---
BOT_ID = os.getenv("JOYSTICK_BOT_ID")
BOT_SECRET = os.getenv("JOYSTICK_BOT_SECRET")
# We don't need manual access tokens anymore, the DB handles them
# ACCESS_TOKEN = os.getenv("JOYSTICK_ACCESS_TOKEN") 
# REFRESH_TOKEN = os.getenv("JOYSTICK_REFRESH_TOKEN")

REDIRECT_URI = os.getenv("JOYSTICK_REDIRECT_URI")  # <--- ADD THIS LINE

# --- Connection Settings ---
WS_URL = "wss://joystick.tv/cable"
CHANNEL_NAME = "GatewayChannel"

def get_basic_auth_token():
    if not BOT_ID or not BOT_SECRET:
        raise ValueError("Missing JOYSTICK_BOT_ID or JOYSTICK_BOT_SECRET")
    
    auth_str = f"{BOT_ID}:{BOT_SECRET}"
    return base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
