import os

# The content of the new, robust web_server.py
file_content = r'''import aiohttp
from aiohttp import web
import socketio
import os
import logging
import json
import base64
from config import BOT_ID, BOT_SECRET, REDIRECT_URI
from db import DBManager
from settings_manager import MEDIA_OPTIONS, resolve_media_file

logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

MEDIA_DIR = os.path.join(os.getcwd(), "media")
# Ensure we point to the Nginx index file for the main root, but the bot handles specific API routes
INSTALL_URL = f"https://joystick.tv/api/oauth/authorize?client_id={BOT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=bot"

STYLE_COMMON = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Roboto+Mono:wght@400;700&display=swap');
    :root { --neon-pink: #ff00ff; --neon-cyan: #00ffff; --deep-purple: #2b003b; --grid-color: rgba(255, 0, 255, 0.2); }
    @keyframes scrollGrid { 0% { background-position: 0 0; } 100% { background-position: 0 50px; } }
    @keyframes pulseGlow { 0% { box-shadow: 0 0 5px var(--neon-cyan); } 50% { box-shadow: 0 0 20px var(--neon-cyan); } 100% { box-shadow: 0 0 5px var(--neon-cyan); } }
    body { 
        font-family: 'Roboto Mono', monospace; background-color: #050011; 
        background-image: linear-gradient(rgba(18,16,16,0) 50%, rgba(0,0,0,0.25) 50%), linear-gradient(90deg, rgba(255,0,0,0.06), rgba(255,0,0,0.02)), linear-gradient(var(--grid-color) 1px, transparent 1px), linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
        background-size: 100% 2px, 3px 100%, 50px 50px, 50px 50px; animation: scrollGrid 4s linear infinite;
        color: #fff; margin: 0; padding: 20px; line-height: 1.6; min-height: 100vh;
    }
    .container { position: relative; z-index: 5; max-width: 1200px; margin: 0 auto; padding: 30px; background: rgba(0,0,0,0.85); border: 2px solid var(--neon-cyan); box-shadow: 0 0 20px rgba(0,255,255,0.2); border-radius: 5px; }
    h1 { font-family: 'Press Start 2P', cursive; color: var(--neon-pink); text-shadow: 3px 3px 0px var(--deep-purple); text-align: center; margin-bottom: 20px; text-transform: uppercase; }
    h2, h3 { color: var(--neon-cyan); border-bottom: 2px solid var(--neon-pink); padding-bottom: 10px; margin-top: 30px; text-transform: uppercase; }
    a { color: var(--neon-pink); text-decoration: none; font-weight: bold; }
    .btn { display: inline-block; background: var(--neon-cyan); color: #000; padding: 15px 30px; font-family: 'Press Start 2P'; text-transform: uppercase; border: none; cursor: pointer; text-decoration: none; margin-top: 20px; box-shadow: 4px 4px 0px var(--neon-pink); }
    .footer { text-align: center; margin-top: 50px; font-size: 0.8em; color: #888; border-top: 1px solid #333; padding-top: 20px; }
    
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 15px; margin-bottom: 40px; }
    .gallery-item { background: rgba(0,0,0,0.6); border: 1px solid var(--neon-cyan); padding: 5px; text-align: center; cursor: pointer; transition: 0.2s; box-shadow: 0 0 5px var(--neon-cyan); animation: pulseGlow 3s infinite; }
    .gallery-item:hover { transform: scale(1.1); background: var(--deep-purple); }
    .gallery-item img { max-width: 100%; height: 80px; object-fit: contain; }
    
    .trigger-zone { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }
    .trigger-col { flex: 1 1 45%; min-width: 350px; background: rgba(0,0,0,0.5); padding: 20px; border: 1px solid var(--neon-pink); border-radius: 10px; }
    .trigger-row { background: #222; margin-bottom: 10px; padding: 10px; display: flex; align-items: center; gap: 10px; border-left: 3px solid var(--neon-cyan); }
    input[type="text"] { background: #000; color: #0f0; border: 1px solid #555; padding: 5px; width: 120px; }
    select { background: #333; color: white; border: none; padding: 5px; }
    .copy-box { background: #000; border: 1px dashed var(--neon-pink); padding: 15px; text-align: center; margin: 30px 0; }
    code { color: var(--neon-cyan); font-weight: bold; font-size: 1.1em; }
</style>
"""

class WebServer:
    def __init__(self, db_manager, bot_instance):
        self.db = db_manager; self.bot = bot_instance
        self.app = web.Application()
        self.sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
        self.sio.attach(self.app)
        # Nginx handles / (Home), /privacy, /terms via static files now.
        # We only handle the dynamic API routes here.
        self.app.router.add_get('/auth/callback', self.handle_oauth_callback)
        self.app.router.add_get('/overlay/{user_id}', self.handle_overlay_view)
        self.app.router.add_get('/settings/{user_id}', self.handle_settings_view)
        self.app.router.add_post('/api/settings/{user_id}', self.handle_save_settings)
        self.app.router.add_post('/api/test/{user_id}', self.handle_test_trigger)
        self.app.router.add_static('/media', MEDIA_DIR)
        self.sio.on('join_room', self.on_join)

    async def start(self):
        runner = web.AppRunner(self.app); await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080); await site.start()
        logger.info("Web Server running on port 8080")

    async def on_join(self, sid, data):
        if data.get("user_id"): self.sio.enter_room(sid, f"room_{data.get('user_id')}")

    async def trigger_overlay(self, user_id, media_key):
        filename = resolve_media_file(media_key)
        if filename: await self.sio.emit('play_media', {'file': filename}, room=f"room_{user_id}")

    def decode_user_id(self, token):
        try:
            parts = token.split('.')
            if len(parts) != 3: return None
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (4 - len(parts[1]) % 4)).decode('utf-8'))
            return payload.get('channel_id') or payload.get('sub') or payload.get('user_id')
        except: return None

    async def handle_oauth_callback(self, request):
        code = request.query.get('code')
        if not code: return web.Response(text="Error: No code provided.")
        async with aiohttp.ClientSession() as session:
            async with session.post("https://joystick.tv/api/oauth/token", 
                data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI}, 
                auth=aiohttp.BasicAuth(BOT_ID, BOT_SECRET), headers={"User-Agent": "TurboTackBot/1.0"}) as resp:
                if resp.status != 200: return web.Response(text=f"Auth Failed: {await resp.text()}")
                tokens = await resp.json()
            user_id = self.decode_user_id(tokens['access_token'])
        if not user_id: return web.Response(text="Error: Could not determine User ID.")
        self.db.update_streamer(str(user_id), tokens['access_token'], tokens.get('refresh_token'))
        await self.bot.add_subscription(str(user_id), tokens['access_token'])
        raise web.HTTPFound(f'/settings/{user_id}')

    async def handle_overlay_view(self, request):
        user_id = request.match_info['user_id']
        html = f"""<!DOCTYPE html><html><head><style>body{{margin:0;overflow:hidden;background:transparent}}#player{{width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}}img{{max-width:100%;max-height:100%;display:none}}</style><script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script></head><body><div id="player"><img id="target" src=""/></div><script>const socket=io();const userId="{user_id}";socket.on('connect',()=>{{socket.emit('join_room',{{user_id:userId}})}});socket.on('play_media',(data)=>{{const img=document.getElementById('target');img.src='/media/'+data.file;img.style.display='block';setTimeout(()=>{{img.style.display='none'}},8000)}});</script></body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_test_trigger(self, request):
        user_id = request.match_info['user_id']; data = await request.json()
        if data.get('media_key'): await self.trigger_overlay(user_id, data.get('media_key')); return web.Response(text="Triggered")
        return web.Response(text="Missing key", status=400)

    async def handle_settings_view(self, request):
        user_id = request.match_info['user_id']; settings = self.db.get_settings(user_id)
        # Escape single quotes in keys if present, though keys are usually safe
        options_html = "".join([f'<option value="{k}">{k}</option>' for k in sorted(MEDIA_OPTIONS.keys())])
        
        triggers = settings.get('triggers', [])
        if not triggers:
            triggers = [
                {"enabled": True, "type": "chat_text", "keyword": "!Turbotack", "media_key": "Random (Any)"},
                {"enabled": True, "type": "emote_reaction", "keyword": ":RustyBluTurboTack:", "media_key": "Random (Any)"},
                {"enabled": True, "type": "wheel_spin", "keyword": "Jackpot", "media_key": "Random (Any)"},
                {"enabled": True, "type": "tip_menu", "keyword": "TurboTack", "media_key": "Random (Any)"},
                {"enabled": False, "type": "tip_amount", "keyword": "1", "media_key": "Spooky 1"},
                {"enabled": False, "type": "tip_amount", "keyword": "2-50", "media_key": "Spooky 2"},
                {"enabled": False, "type": "tip_amount", "keyword": "50-100", "media_key": "Cottagecore"},
                {"enabled": False, "type": "tip_amount", "keyword": "100-500", "media_key": "Random (Any)"}
            ]
        rows_js = json.dumps(triggers)
        gallery_html = '<div class="gallery-grid">' + "".join([f'<div class="gallery-item" onclick="triggerTest(\'{k}\')" title="Click"><img src="/media/{v if isinstance(v, str) else v[0]}" loading="lazy"><p>{k}</p></div>' for k, v in sorted(MEDIA_OPTIONS.items()) if "Mix" not in k and k != "Random (Any)"]) + '</div>'

        # FIX: The backticks are crucial here for JS string interpolation
        html = f"""<!DOCTYPE html><html><head><title>TurboTack CONFIG</title>{STYLE_COMMON}</head><body>
            <div class="container">
                <h1>TURBOTACK MASTER CONTROL</h1>
                <p style="text-align: center; color: #aaa;">"The most Turbotacky Bot on JoyStick.TV"</p>
                <h3>Direct Manual Override</h3>{gallery_html}
                <div class="trigger-zone">
                    <div class="trigger-col"><h3>RAD ACTIONS</h3><div id="col-standard"></div><button type="button" class="btn" style="width:100%" onclick="addTrigger('standard')">+ ADD ACTION</button></div>
                    <div class="trigger-col"><h3>BODACIOUS TIPS</h3><div id="col-tips"></div><button type="button" class="btn" style="width:100%" onclick="addTrigger('tips')">+ ADD TIP RANGE</button></div>
                </div>
                <button type="button" onclick="saveConfig()" class="btn" style="width:100%; margin-top:30px;">SAVE CONFIGURATION</button>
                <div class="copy-box"><h3>OBS SETUP</h3><p>Copy URL:</p><code id="overlay-url">https://turbotack.rustyblu.com/overlay/{user_id}</code><br><br><button class="btn" id="copyBtn" onclick="copyUrl()" style="background:#333; color:white;">COPY URL</button></div>
                <div class="footer"><a href="/privacy">Privacy</a> | <a href="/terms">Terms</a></div>
            </div>
            <script>
                // FIX: Added backticks around options_html
                const mediaOptions = `{options_html}`; 
                let allTriggers = {rows_js}; 
                const userId = "{user_id}";
                
                function render() {{
                    const sc = document.getElementById('col-standard'); const tc = document.getElementById('col-tips');
                    sc.innerHTML = ''; tc.innerHTML = '';
                    allTriggers.forEach((t, i) => {{
                        const d = document.createElement('div'); d.className = 'trigger-row';
                        const isTip = (t.type === 'tip_amount');
                        const sel = isTip ? '<span style="width:100px; color:var(--neon-pink); font-size:0.8em;">TIP AMOUNT</span>' : 
                            `<select onchange="update(${{i}}, 'type', this.value)" style="width:100px;"><option value="chat_text" ${{t.type=='chat_text'?'selected':''}}>Chat Cmd</option><option value="emote_reaction" ${{t.type=='emote_reaction'?'selected':''}}>Emote</option><option value="wheel_spin" ${{t.type=='wheel_spin'?'selected':''}}>Wheel</option><option value="tip_menu" ${{t.type=='tip_menu'?'selected':''}}>Tip Menu</option></select>`;
                        d.innerHTML = `<input type="checkbox" ${{t.enabled ? 'checked' : ''}} onchange="update(${{i}}, 'enabled', this.checked)">${{sel}}<input type="text" value="${{t.keyword}}" oninput="update(${{i}}, 'keyword', this.value)"><select onchange="update(${{i}}, 'media_key', this.value)" style="width:100px;">${{mediaOptions}}</select><button style="background:red; color:white; border:none; cursor:pointer;" onclick="remove(${{i}})">X</button>`;
                        if(isTip) tc.appendChild(d); else sc.appendChild(d);
                        d.querySelectorAll('select')[isTip ? 0 : 1].value = t.media_key;
                    }});
                }}
                function addTrigger(z) {{ allTriggers.push(z === 'tips' ? {{ enabled: false, type: 'tip_amount', keyword: '10-20', media_key: "Random (Any)" }} :
