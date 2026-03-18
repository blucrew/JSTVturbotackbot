import aiohttp
from aiohttp import web
import socketio
import os
import logging
import json
import base64
from config import BOT_ID, BOT_SECRET, REDIRECT_URI
from db import DBManager
from settings_manager import MEDIA_OPTIONS, resolve_media_file

# --- FIX 1: Changed level to WARNING to prevent 17GB log files ---
logging.basicConfig(filename='bot.log', level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
MEDIA_DIR = os.path.join(os.getcwd(), "media")

STYLE_COMMON = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Roboto+Mono:wght@400;700&display=swap');
    :root { --neon-pink: #ff00ff; --neon-cyan: #00ffff; --deep-purple: #2b003b; --grid-color: rgba(255, 0, 255, 0.2); }
    @keyframes scrollGrid { 0% { background-position: 0 0; } 100% { background-position: 0 50px; } }
    body { font-family: 'Roboto Mono', monospace; background-color: #050011; background-image: linear-gradient(rgba(18,16,16,0) 50%, rgba(0,0,0,0.25) 50%), linear-gradient(90deg, rgba(255,0,0,0.06), rgba(255,0,0,0.02)), linear-gradient(var(--grid-color) 1px, transparent 1px), linear-gradient(90deg, var(--grid-color) 1px, transparent 1px); background-size: 100% 2px, 3px 100%, 50px 50px, 50px 50px; animation: scrollGrid 4s linear infinite; color: #fff; margin: 0; padding: 20px; line-height: 1.6; min-height: 100vh; }
    .container { position: relative; z-index: 5; max-width: 1200px; margin: 0 auto; padding: 30px; background: rgba(0,0,0,0.85); border: 2px solid var(--neon-cyan); box-shadow: 0 0 20px rgba(0,255,255,0.2); border-radius: 5px; }
    h1 { font-family: 'Press Start 2P', cursive; color: var(--neon-pink); text-shadow: 3px 3px 0px var(--deep-purple); text-align: center; margin-bottom: 20px; text-transform: uppercase; }
    h2, h3 { color: var(--neon-cyan); border-bottom: 2px solid var(--neon-pink); padding-bottom: 10px; margin-top: 30px; text-transform: uppercase; }
    h4 { color: var(--neon-pink); margin-bottom: 10px; font-family: 'Press Start 2P'; font-size: 0.8em; }
    a { color: var(--neon-pink); text-decoration: none; font-weight: bold; transition: 0.3s; }
    .btn { display: inline-block; background: var(--neon-cyan); color: #000; padding: 15px 30px; font-family: 'Press Start 2P'; text-transform: uppercase; border: none; cursor: pointer; text-decoration: none; margin-top: 20px; box-shadow: 4px 4px 0px var(--neon-pink); transition: 0.2s; }
    .btn:hover { transform: translate(2px, 2px); box-shadow: 2px 2px 0px var(--neon-pink); background: white; }
    .footer { text-align: center; margin-top: 50px; font-size: 0.8em; color: #888; border-top: 1px solid #333; padding-top: 20px; }
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 15px; margin-bottom: 40px; }
    .gallery-item { background: rgba(0,0,0,0.6); border: 1px solid var(--neon-cyan); padding: 5px; text-align: center; cursor: pointer; transition: 0.2s; box-shadow: 0 0 5px var(--neon-cyan); }
    .gallery-item:hover { transform: scale(1.1); background: var(--deep-purple); }
    .gallery-item img { max-width: 100%; height: 80px; object-fit: contain; }
    .trigger-zone { display: flex; flex-wrap: wrap; gap: 20px; justify-content: center; }
    .trigger-col { flex: 1 1 45%; min-width: 350px; background: rgba(0,0,0,0.5); padding: 20px; border: 1px solid var(--neon-pink); border-radius: 10px; }
    .trigger-row { background: #222; margin-bottom: 10px; padding: 10px; display: flex; align-items: center; gap: 10px; border-left: 3px solid var(--neon-cyan); }
    input[type="text"] { background: #000; color: #0f0; border: 1px solid #555; padding: 5px; width: 120px; }
    select { background: #333; color: white; border: none; padding: 5px; }
    .copy-box { background: #000; border: 1px dashed var(--neon-pink); padding: 15px; text-align: center; margin: 30px 0; }
    code { color: var(--neon-cyan); font-weight: bold; font-size: 1.1em; }
    .instructions { background: rgba(43,0,59,0.5); padding: 20px; border: 1px dashed var(--neon-cyan); margin-top: 40px; font-size: 0.9em; color: #ccc; text-align: left; }
    .snazzy-link { display: inline-block; margin-top: 40px; padding: 20px; border: 2px dashed var(--neon-cyan); color: var(--neon-pink); font-family: 'Press Start 2P'; font-size: 0.8em; background: rgba(0,0,0,0.5); }
    .snazzy-link:hover { background: var(--deep-purple); color: white; border-color: var(--neon-pink); }
    .legal-text { text-align: left; background: rgba(0,0,0,0.6); padding: 20px; border: 1px solid #333; margin-top: 20px; }
    .legal-text h3 { border-bottom: 1px solid #444; color: var(--neon-cyan); margin-top: 30px; }
    .legal-text p { margin-bottom: 15px; color: #ddd; }
    .legal-text ul { margin-left: 20px; color: #bbb; }
</style>
"""

class WebServer:
    def __init__(self, db_manager, bot_instance):
        self.db = db_manager
        self.bot = bot_instance
        self.app = web.Application()
        self.sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
        self.sio.attach(self.app)
        
        self.app.router.add_get('/auth/callback', self.handle_oauth_callback)
        self.app.router.add_get('/overlay/{user_id}', self.handle_overlay_view)
        self.app.router.add_get('/settings/{user_id}', self.handle_settings_view)
        self.app.router.add_post('/api/settings/{user_id}', self.handle_save_settings)
        self.app.router.add_post('/api/test/{user_id}', self.handle_test_trigger)
        self.app.router.add_get('/privacy', self.handle_privacy)
        self.app.router.add_get('/terms', self.handle_terms)
        self.app.router.add_static('/media', MEDIA_DIR)
        
        self.sio.on('join_room', self.on_join)

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        logger.warning("Web Server running on port 8080")

    async def on_join(self, sid, data):
        if data.get("user_id"): 
            room = f"room_{data.get('user_id')}"
            await self.sio.enter_room(sid, room)
            logger.info(f"Socket joined room: {room}")

    # --- FIX 2: Only trigger for the specific room ---
    async def trigger_overlay(self, user_id, media_key):
        filename = resolve_media_file(media_key)
        if filename:
            target_room = f"room_{user_id}"
            logger.info(f"Triggering File: {filename} for Room: {target_room}")
            await self.sio.emit('play_media', {'file': filename}, room=target_room)
        else:
            logger.error(f"Failed to resolve media key: {media_key}")

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
        html = f"""<!DOCTYPE html><html><head><style>
            body{{margin:0;overflow:hidden;background:transparent}}
            #player{{width:100vw;height:100vh;display:flex;justify-content:center;align-items:center}}
            img{{max-width:100%;max-height:100%;display:none}}
        </style><script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script></head><body>
        <div id="player"><img id="target" src=""/></div>
        <script>
            const socket=io();
            const userId="{user_id}";
            console.log("Overlay initialized for user:", userId);
            socket.on('connect', () => {{ console.log("Connected!"); socket.emit('join_room', {{user_id: userId}}); }});
            socket.on('play_media', (data) => {{
                const img = document.getElementById('target');
                img.src = '/media/' + data.file;
                img.style.display = 'block';
                setTimeout(() => {{ img.style.display = 'none'; }}, 8500);
            }});
        </script></body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_test_trigger(self, request):
        user_id = request.match_info['user_id']; data = await request.json()
        if data.get('media_key'): 
            await self.trigger_overlay(user_id, data.get('media_key'))
            return web.Response(text="Triggered")
        return web.Response(text="Missing key", status=400)

    async def handle_settings_view(self, request):
        user_id = request.match_info['user_id']
        settings = self.db.get_settings(user_id)
        media_options_list = sorted(MEDIA_OPTIONS.keys())
        gallery_data = []
        for k, v in sorted(MEDIA_OPTIONS.items()):
            if "Mix" not in k and k != "Random (Any)":
                filename = v if isinstance(v, str) else v[0]
                gallery_data.append({"name": k, "file": filename})

        triggers = settings.get('triggers', [])
        if not triggers:
            triggers = [
                {"enabled": True, "type": "chat_text", "keyword": "!Turbotack", "media_key": "Random (Any)"},
                {"enabled": True, "type": "emote_reaction", "keyword": ":RustyBluTurboTack:", "media_key": "Random (Any)"},
                {"enabled": True, "type": "wheel_spin", "keyword": "Jackpot", "media_key": "Random (Any)"},
                {"enabled": True, "type": "tip_menu", "keyword": "TurboTack", "media_key": "Random (Any)"},
                {"enabled": False, "type": "tip_amount", "keyword": "50", "media_key": "Spooky 1"},
                {"enabled": False, "type": "tip_amount", "keyword": "100-500", "media_key": "Spooky 2"},
                {"enabled": False, "type": "tip_amount", "keyword": "500-1000", "media_key": "Cottagecore"},
                {"enabled": False, "type": "tip_amount", "keyword": "1000", "media_key": "Random (Any)"}
            ]

        triggers_json = json.dumps(triggers)
        media_options_json = json.dumps(media_options_list)
        gallery_data_json = json.dumps(gallery_data)

        html = f"""<!DOCTYPE html><html><head><title>TurboTack CONFIG</title>{STYLE_COMMON}</head><body>
            <div class="container">
                <h1>TURBOTACK MASTER CONTROL</h1>
                <p style="text-align: center; color: #aaa; margin-bottom: 20px;">"The most Turbotacky Bot on JoyStick.TV"</p>

                <h3>Direct Manual Override</h3>
                <div id="gallery-container" class="gallery-grid"></div>

                <div class="trigger-zone">
                    <div class="trigger-col"><h3>RAD ACTIONS</h3><div id="col-standard"></div><button type="button" class="btn" style="width:100%" onclick="addTrigger('standard')">+ ADD ACTION</button></div>
                    <div class="trigger-col"><h3>BODACIOUS TIPS</h3><div id="col-tips"></div><button type="button" class="btn" style="width:100%" onclick="addTrigger('tips')">+ ADD TIP RANGE</button></div>
                </div>
                <button type="button" onclick="saveConfig()" class="btn" style="width:100%; margin-top:30px;">SAVE CONFIGURATION</button>

                <div class="copy-box"><h3>OBS SETUP URL</h3><p>Copy this URL:</p><code id="overlay-url">https://turbotack.rustyblu.com/overlay/{user_id}</code><br><br><button class="btn" id="copyBtn" onclick="copyUrl()" style="background:#333; color:white;">COPY URL</button></div>

                <div class="instructions">
                    <div style="display: flex; flex-wrap: wrap; gap: 20px;">
                        <div style="flex: 1; min-width: 300px;">
                            <h4>OBS SETUP GUIDE</h4>
                            <p>Never added a Browser Source? It's easy!</p>
                            <ol>
                                <li>Copy the <strong>URL</strong> from the box above.</li>
                                <li>In OBS, look at the <strong>Sources</strong> dock and click the <strong>+</strong> button.</li>
                                <li>Select <strong>Browser</strong>. Name it "TurboTack".</li>
                                <li>Paste the URL into the <strong>URL</strong> field.</li>
                                <li>Set Width to <strong>1920</strong> and Height to <strong>1080</strong>.</li>
                                <li>Click <strong>OK</strong>. You're done!</li>
                            </ol>
                        </div>
                        <div style="flex: 1; min-width: 300px;">
                            <h4>BOT CONFIG GUIDE</h4>
                            <ul>
                                <li><strong>Manual Override:</strong> Click any GIF above to test it instantly.</li>
                                <li><strong>Rad Actions:</strong> Link keywords or emotes to GIFs.</li>
                                <li><strong>Bodacious Tips:</strong> React to specific Token amounts. 
                                    <br><em>Example: "500" for exactly 500 tokens, or "100-500" for a range.</em>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>

                <div style="text-align: center;">
                    <a href="/" class="snazzy-link">Check out Rusty's Big (joystick.tv) Tools</a>
                </div>

                <div class="footer">
                    <a href="/privacy">Privacy</a> | <a href="/terms">Terms</a>
                </div>
            </div>
            <script>
                const mediaOptionsList = {media_options_json};
                const galleryData = {gallery_data_json};
                let allTriggers = {triggers_json}; 
                const userId = "{user_id}";

                const galleryContainer = document.getElementById('gallery-container');
                galleryData.forEach(item => {{
                    const div = document.createElement('div');
                    div.className = 'gallery-item';
                    div.title = "Click";
                    div.onclick = function() {{ triggerTest(item.name); }};
                    div.innerHTML = `<img src="/media/${{item.file}}" loading="lazy"><p>${{item.name}}</p>`;
                    galleryContainer.appendChild(div);
                }});

                let optionsHtml = "";
                mediaOptionsList.forEach(opt => {{
                    optionsHtml += `<option value="${{opt}}">${{opt}}</option>`;
                }});

                function render() {{
                    const sc = document.getElementById('col-standard'); const tc = document.getElementById('col-tips');
                    sc.innerHTML = ''; tc.innerHTML = '';
                    allTriggers.forEach((t, i) => {{
                        const d = document.createElement('div'); d.className = 'trigger-row';
                        const isTip = (t.type === 'tip_amount');
                        const sel = isTip ? '<span style="width:100px; color:var(--neon-pink); font-size:0.8em;">TOKENS</span>' : 
                            `<select onchange="update(${{i}}, 'type', this.value)" style="width:100px;"><option value="chat_text" ${{t.type=='chat_text'?'selected':''}}>Chat Cmd</option><option value="emote_reaction" ${{t.type=='emote_reaction'?'selected':''}}>Emote</option><option value="wheel_spin" ${{t.type=='wheel_spin'?'selected':''}}>Wheel</option><option value="tip_menu" ${{t.type=='tip_menu'?'selected':''}}>Tip Menu</option></select>`;
                        d.innerHTML = `<input type="checkbox" ${{t.enabled ? 'checked' : ''}} onchange="update(${{i}}, 'enabled', this.checked)">${{sel}}<input type="text" value="${{t.keyword}}" oninput="update(${{i}}, 'keyword', this.value)"><select onchange="update(${{i}}, 'media_key', this.value)" style="width:100px;">${{optionsHtml}}</select><button style="background:red; color:white; border:none; cursor:pointer;" onclick="remove(${{i}})">X</button>`;
                        if(isTip) tc.appendChild(d); else sc.appendChild(d);
                        d.querySelectorAll('select')[isTip ? 0 : 1].value = t.media_key;
                    }});
                }}
                function addTrigger(z) {{ allTriggers.push(z === 'tips' ? {{ enabled: false, type: 'tip_amount', keyword: '500-1000', media_key: "Random (Any)" }} : {{ enabled: true, type: 'chat_text', keyword: '!new', media_key: "Random (Any)" }}); render(); }}
                function remove(i) {{ if(confirm("Delete?")) {{ allTriggers.splice(i, 1); render(); }} }}
                function update(i, f, v) {{ allTriggers[i][f] = v; }}
                async function triggerTest(k) {{ await fetch('/api/test/' + userId, {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ media_key: k }}) }}); }}
                function copyUrl() {{ navigator.clipboard.writeText(document.getElementById('overlay-url').innerText); document.getElementById('copyBtn').innerText = "COPIED!"; }}
                async function saveConfig() {{ await fetch('/api/settings/' + userId, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ triggers: allTriggers }}) }}); alert('SAVED!'); }}
                render();
            </script>
        </body></html>
        """
        return web.Response(text=html, content_type='text/html')

    async def handle_save_settings(self, request):
        user_id = request.match_info['user_id']
        data = await request.json()
        self.db.save_settings(user_id, data)
        return web.Response(text="Saved")

    async def handle_privacy(self, request):
        html = f"""<!DOCTYPE html><html><head><title>TurboTack - Privacy</title>{STYLE_COMMON}</head><body>
            <div class="container">
                <h1>PRIVACY PROTOCOL</h1>
                <div class="legal-text">
                    <h3>1. Data Collection</h3>
                    <p>TurboTack collects only the absolute minimum required to function:</p>
                    <ul>
                        <li><strong>Joystick.TV User ID & Channel ID:</strong> Used to uniquely identify your stream.</li>
                        <li><strong>Access Tokens:</strong> Stored securely to allow the bot to listen for events (chat, tips, wheel spins) on your behalf.</li>
                        <li><strong>Configuration Data:</strong> The triggers and settings you save in this dashboard.</li>
                    </ul>

                    <h3>2. Data Usage</h3>
                    <p>Your data is used strictly for the operation of this bot service. Specifically:</p>
                    <ul>
                        <li>To maintain a real-time WebSocket connection with Joystick.TV.</li>
                        <li>To listen for the events you have configured (e.g., waiting for the word "!TurboTack").</li>
                        <li>To trigger the browser source overlay when those events occur.</li>
                    </ul>
                    <p>We do not sell, trade, or analyze your data for marketing purposes. We are here for the aesthetics, not the analytics.</p>

                    <h3>3. Data Retention</h3>
                    <p>Your authentication tokens are stored in a local database on our secure server. If you uninstall the bot, you may revoke access via your Joystick.TV settings, which renders our stored tokens useless immediately.</p>
                </div>
                <div class="footer"><a href="/">Back to Home</a></div>
            </div>
        </body></html>"""
        return web.Response(text=html, content_type='text/html')

    async def handle_terms(self, request):
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>RustyBlu Tools - Terms</title>
    {STYLE_COMMON}
</head>
<body>
    <div class="container">
        <h1>TERMS OF SERVICE</h1>
        <h4>For RustyBlu Tools & Services</h4>

        <div class="legal-text">
            <p>Welcome! By creating an account, installing any of our bots, or otherwise utilizing the digital tools provided by <strong>RustyBlu</strong>, you agree to be bound by these terms.</p>

            <h3>1. The Services</h3>
            <p>RustyBlu provides a suite of interactive tools, chatbots, and automation services designed for streaming platforms (e.g. Joystick.TV). These services include, but are not limited to:</p>
            <ul>
                <li><strong>Emoji Buddy Bot:</strong> An interactive overlay allowing viewers to trigger animations and sounds via chat.</li>
                <li><strong>TurboTack Bot:</strong> A chat automation, moderation, and media-triggering tool.</li>
            </ul>

            <h3>2. User Conduct</h3>
            <p>By using any of these tools, you agree NOT to:</p>
            <ul>
                <li>Use the services to harass, spam, or violate the terms of service of the streaming platform you are broadcasting on.</li>
                <li>Attempt to reverse engineer, hack, or exploit our infrastructure or bots.</li>
                <li>Use custom text/paint features to display offensive or hate speech.</li>
            </ul>

            <h3>3. Data & Privacy</h3>
            <p>Our tools may temporarily store public user data (such as usernames, chat command usage, and subscriber status) solely for the purpose of functionality (e.g., remembering a viewer's chosen avatar or tracking cooldowns). We do not sell or share this data with third parties.</p>

            <h3>4. Limitation of Liability</h3>
            <p>RustyBlu is not liable for any interruptions in service, data loss, or unintended "physics mishaps" (e.g., if a bouncing element covers a critical part of your game UI). Please test your overlay placement before going live.</p>

            <h3>5. Termination</h3>
            <p>We reserve the right to update these terms as our toolset grows. We also reserve the right to terminate access to any of our services for users who violate these terms or attempt to compromise our security.</p>
        </div>

        <div class="footer">
            &copy; 2025 RustyBlu Tools. All Rights Reserved.<br><br>
            <a href="/">Back to Home</a>
        </div>
    </div>
</body>
</html>"""
        return web.Response(text=html, content_type='text/html')
