import json
import logging
import asyncio
import websockets

logger = logging.getLogger(__name__)

class JoystickAPI:
    def __init__(self, bot):
        self.bot = bot
        self.uri = "wss://joystick.tv/cable"
        self.ws = None
        # Store subscriptions as a set of tuples: (user_id, token)
        self.connected_streamers = set()

    async def connect(self):
        logger.info("Starting WebSocket connection loop...")
        while True:
            try:
                async with websockets.connect(self.uri) as ws:
                    self.ws = ws
                    logger.info("Connected to Joystick Gateway!")

                    # Resubscribe to existing streamers if this is a reconnect
                    for user_id, token in self.connected_streamers:
                        await self._do_subscribe(user_id, token)

                    async for msg in ws:
                        await self.handle_message(msg)
            except Exception as e:
                logger.error(f"WebSocket Error (Retrying in 5s): {e}")
                self.ws = None
                await asyncio.sleep(5)

    async def subscribe(self, user_id, token):
        # Store for reconnects
        self.connected_streamers.add((user_id, token))
        if self.ws:
            await self._do_subscribe(user_id, token)

    async def _do_subscribe(self, user_id, token):
        # Subscribe to the GatewayChannel for this streamer
        identifier = json.dumps({
            "channel": "GatewayChannel", 
            "streamer_id": user_id
        })

        payload = {
            "command": "subscribe",
            "identifier": identifier
        }
        try:
            await self.ws.send(json.dumps(payload))
            logger.info(f"Subscribed to events for {user_id}")
        except Exception as e:
            logger.error(f"Failed to subscribe {user_id}: {e}")

    async def handle_message(self, message):
        try:
            data = json.loads(message)

            # Ignore keep-alive pings
            if data.get("type") == "ping":
                return

            # Check if this is a real event message
            if "message" in data:
                content = data["message"]

                # Extract Streamer ID so we know who this event is for
                streamer_id = None
                if "identifier" in data:
                    try:
                        ident = json.loads(data["identifier"])
                        streamer_id = ident.get("streamer_id")
                    except:
                        pass

                # The event type is usually inside the inner message (e.g. "type": "ChatMessage")
                event_type = content.get("type")

                # Pass the data back to the main bot logic
                if event_type and streamer_id:
                    await self.bot.process_event(event_type, content, streamer_id)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
