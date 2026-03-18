import sqlite3
import json
import logging

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
                      refresh_token TEXT)''')
        
        # Settings Table: Stores the JSON config for triggers
        c.execute('''CREATE TABLE IF NOT EXISTS settings
                     (user_id TEXT PRIMARY KEY, 
                      config_json TEXT)''')
        
        conn.commit()
        conn.close()

    def update_streamer(self, user_id, access_token, refresh_token=None):
        """ Saves or updates a streamer's auth tokens """
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        
        if refresh_token:
            c.execute('''INSERT OR REPLACE INTO streamers (user_id, access_token, refresh_token)
                         VALUES (?, ?, ?)''', (user_id, access_token, refresh_token))
        else:
            # If we only got a new access token, keep the old refresh token
            c.execute('''UPDATE streamers SET access_token=? WHERE user_id=?''', 
                      (access_token, user_id))
            
            # If user didn't exist yet, insert them (rare edge case)
            if c.rowcount == 0:
                c.execute('''INSERT INTO streamers (user_id, access_token, refresh_token)
                             VALUES (?, ?, ?)''', (user_id, access_token, None))

        conn.commit()
        conn.close()
        logger.info(f"💾 Updated DB for user {user_id}")

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
