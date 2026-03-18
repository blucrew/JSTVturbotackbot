import sqlite3
import json
import logging
import time

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, db_name="turbotack.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """ Creates the necessary tables if they don't exist """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        # Streamers Table: Stores Auth Tokens
        c.execute('''CREATE TABLE IF NOT EXISTS streamers
                     (user_id TEXT PRIMARY KEY,
                      access_token TEXT,
                      refresh_token TEXT,
                      installed_at REAL,
                      last_seen REAL)''')
        # Migrate: add columns if they don't exist (for existing DBs)
        for col in ("installed_at REAL", "last_seen REAL"):
            try:
                c.execute(f"ALTER TABLE streamers ADD COLUMN {col}")
            except Exception:
                pass
        
        # Settings Table: Stores the JSON config for triggers
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (user_id TEXT PRIMARY KEY, 
                      config_json TEXT)''')
        
        conn.commit()
        conn.close()

    def update_streamer(self, user_id, access_token, refresh_token=None):
        """ Saves or updates a streamer's auth tokens. Sets installed_at on first install. """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        now = time.time()

        c.execute("SELECT installed_at FROM streamers WHERE user_id=?", (user_id,))
        row = c.fetchone()

        if row:
            # Existing streamer — update tokens, preserve installed_at
            c.execute('''UPDATE streamers SET access_token=?, refresh_token=COALESCE(?, refresh_token)
                         WHERE user_id=?''', (access_token, refresh_token, user_id))
        else:
            # New install
            c.execute('''INSERT INTO streamers (user_id, access_token, refresh_token, installed_at)
                         VALUES (?, ?, ?, ?)''', (user_id, access_token, refresh_token, now))

        conn.commit()
        conn.close()
        logger.info(f"💾 Updated DB for user {user_id}")

    def update_streamer_tokens(self, user_id, access_token, refresh_token):
        """ Updates tokens only — used by the token refresh flow. """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("UPDATE streamers SET access_token=?, refresh_token=? WHERE user_id=?",
                  (access_token, refresh_token, user_id))
        conn.commit()
        conn.close()

    def touch_streamer(self, user_id):
        """ Updates last_seen timestamp for a streamer. """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("UPDATE streamers SET last_seen=? WHERE user_id=?", (time.time(), user_id))
        conn.commit()
        conn.close()

    def get_all_streamers(self):
        """ Returns a list of all users to reconnect on startup """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT user_id, access_token FROM streamers")
        rows = c.fetchall()
        conn.close()
        
        return [{'user_id': r[0], 'access_token': r[1]} for r in rows]

    def get_streamer_tokens(self, user_id):
        """ Fetches both access and refresh tokens for the Refresher Logic """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT access_token, refresh_token FROM streamers WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return {'access_token': row[0], 'refresh_token': row[1]}
        return None

    def save_settings(self, user_id, data):
        """ Saves the JSON config from the web dashboard """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (user_id, config_json) VALUES (?, ?)", 
                  (user_id, json.dumps(data)))
        conn.commit()
        conn.close()

    def get_settings(self, user_id):
        """ Loads settings, returns empty dict if none exist """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute("SELECT config_json FROM settings WHERE user_id=?", (user_id,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return {}
