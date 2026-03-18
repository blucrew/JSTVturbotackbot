import logging
import asyncio

logger = logging.getLogger(__name__)

class EventHandler:
    def __init__(self, api_client, chat_callback, overlay_server, settings_manager):
        self.api = api_client
        self.send_chat = chat_callback
        self.server = overlay_server
        self.sm = settings_manager
        
        self.state = {
            "viewer_count": 0,
            "session_tips": 0
        }
        self.commands = {
            "!ping": self.cmd_ping,
        }

    async def check_triggers(self, trigger_type, text_content):
        """Checks if the event matches any user-configured trigger."""
        if not text_content: return

        triggers = self.sm.settings.get("triggers", [])
        
        for t in triggers:
            if not t.get("enabled", True): continue
            
            # Match Type
            if t.get("type") != trigger_type: continue
            
            # Match Content (Case insensitive)
            keyword = t.get("keyword", "").lower()
            content = text_content.lower()
            
            # Logic: keyword must appear in content
            if keyword in content:
                # Fire the overlay
                await self.server.trigger_media(t.get("media_key"))

    async def process_event(self, event_type, data):
        try:
            handler_name = f"handle_{event_type.lower()}"
            handler = getattr(self, handler_name, self.handle_unknown)
            await handler(data)
        except Exception as e:
            logger.error(f"Error processing {event_type}: {e}", exc_info=True)

    async def handle_chatmessage(self, data):
        text = data.get("text", "").strip()
        user = data.get("author", {})
        
        logger.info(f"[CHAT] {user.get('username')}: {text}")
        
        # 1. Check Chat Triggers
        await self.check_triggers("chat_text", text)

        # 2. Check Emote Triggers (Specific Requirement: "Any emote with word turbotack")
        # Assuming emotes might be in text or metadata. For now, check text.
        if "turbotack" in text.lower():
             await self.check_triggers("emote_reaction", "turbotack")

        # 3. Standard Commands
        if text.startswith("!"):
            parts = text.split(" ")
            cmd = parts[0].lower()
            if cmd in self.commands:
                await self.commands[cmd](user, parts[1:])

    async def handle_tipped(self, data):
        amount = data.get("how_much", 0)
        menu_item = data.get("tip_menu_item")
        item_name = menu_item.get("name", "") if menu_item else ""
        
        logger.info(f"[TIP] {amount} - {item_name}")
        
        # Check Tip Menu Triggers
        await self.check_triggers("tip_menu", item_name)

    async def handle_wheelspinclaimed(self, data):
        reward = data.get("reward_text", "")
        logger.info(f"[WHEEL] {reward}")
        
        # Check Wheel Triggers
        await self.check_triggers("wheel_spin", reward)

    # ... [Keep other handlers like handle_userpresence] ...

    async def cmd_ping(self, user, args):
        await self.send_chat("Pong!")
    
    async def handle_unknown(self, data):
        pass