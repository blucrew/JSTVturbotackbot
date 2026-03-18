import asyncio
import websockets
import json
import logging
from config import BOT_ID, BOT_SECRET, REDIRECT_URI
from db import DBManager
from web_server import WebServer

# --- FIX APPLIED: Changed level from INFO to WARNING to stop disk filling ---
logging.basicConfig(filename='bot.log', level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
WS_URL = "wss://joystick.tv/cable"

class TurboTackBot:
    def __init__(self):
        self.db = DBManager()
        self.websocket = None
        self.running = True
        self.web_server = WebServer(self.db, self)

    async def send_command(self, command):
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.send(json.dumps(command))
        except Exception as e:
            logger.error(f"Error sending command: {e}")

    async def subscribe_user(self, channel_id, token):
        payload = {"command": "subscribe", "identifier": json.dumps({"channel": "GatewayChannel", "id": str(channel_id)})}
        await self.send_command(payload)
        # logger.info calls are now ignored unless they are warnings/errors
        logger.info(f"Subscribed to events for User {channel_id}")

    async def add_subscription(self, user_id, token):
        await self.subscribe_user(user_id, token)

    async def handle_message(self, message):
        try:
            data = json.loads(message)
            if "ping" in data or "type" not in data: return
            if data.get("type") == "confirm_subscription": return
            if "message" in data and "event" in data["message"]:
                event_type = data["message"]["event"]
                payload = data["message"].get("data", {})
                channel_id = data["message"].get("channelId")
                if not channel_id: return

                settings = self.db.get_settings(str(channel_id))
                triggers = settings.get("triggers", [])
                
                # This log line was the main spammer:
                logger.info(f"Event: {event_type} for Channel {channel_id}")

                if event_type == "ChatMessage":
                    text = payload.get("text", "")
                    for trigger in triggers:
                        if trigger['enabled'] and trigger['type'] == 'chat_text':
                            if trigger['keyword'].lower() in text.lower():
                                await self.web_server.trigger_overlay(str(channel_id), trigger['media_key'])
                elif event_type == "WheelSpinEvent":
                    label = payload.get("label", "")
                    for trigger in triggers:
                        if trigger['enabled'] and trigger['type'] == 'wheel_spin':
                            if trigger['keyword'].lower() in label.lower() or trigger['keyword'] == "Any":
                                await self.web_server.trigger_overlay(str(channel_id), trigger['media_key'])
                elif event_type == "TipEvent":
                    amount = int(payload.get("amount", 0)) / 100
                    text = payload.get("message", "")
                    for trigger in triggers:
                        if trigger['enabled']:
                            if trigger['type'] == 'tip_menu' and trigger['keyword'].lower() in text.lower():
                                await self.web_server.trigger_overlay(str(channel_id), trigger['media_key'])
                            elif trigger['type'] == 'tip_amount':
                                try:
                                    if "-" in trigger['keyword']:
                                        low, high = map(float, trigger['keyword'].split('-'))
                                        if low <= amount <= high:
                                            await self.web_server.trigger_overlay(str(channel_id), trigger['media_key'])
                                    else:
                                        if float(trigger['keyword']) == amount:
                                            await self.web_server.trigger_overlay(str(channel_id), trigger['media_key'])
                                except: pass
        except Exception as e:
            logger.error(f"Message Error: {e}")

    async def connect_and_listen(self):
        while self.running:
            try:
                all_streamers = self.db.get_all_streamers()
                logger.info(f"Connecting to Joystick.TV... (Re-subscribing {len(all_streamers)} users)")
                async with websockets.connect(WS_URL, subprotocols=["actioncable-v1-json", "actioncable-unsupported"]) as ws:
                    self.websocket = ws
                    for streamer in all_streamers:
                        await self.subscribe_user(streamer['user_id'], streamer['access_token'])
                    async for message in ws:
                        await self.handle_message(message)
            except Exception as e:
                logger.error(f"Connection lost: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)

    async def start(self):
        await self.web_server.start()
        await self.connect_and_listen()

if __name__ == "__main__":
    bot = TurboTackBot()
    try: asyncio.run(bot.start())
    except KeyboardInterrupt: pass
