import aiohttp
import asyncio
import base64
import logging
import time
from config import (
    BOT_ID, BOT_SECRET, ACCESS_TOKEN, REFRESH_TOKEN
)

# Configure Logging
logger = logging.getLogger(__name__)

class JoystickAPI:
    def __init__(self):
        self.base_url = "https://joystick.tv/api"
        self.token_url = f"{self.base_url}/oauth/token"
        
        # State management for tokens
        self.access_token = ACCESS_TOKEN
        self.refresh_token = REFRESH_TOKEN
        self.token_expires_at = 0  # Unix timestamp
        
        # Lock to prevent multiple concurrent refresh attempts
        self._refresh_lock = asyncio.Lock()

    def _get_auth_headers(self):
        """Returns the Bearer headers for standard API calls."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _get_basic_auth_header(self):
        """Returns Basic Auth headers for the Token Refresh endpoint."""
        auth_str = f"{BOT_ID}:{BOT_SECRET}"
        b64_auth = base64.b64encode(auth_str.encode("utf-8")).decode("utf-8")
        return {
            "Authorization": f"Basic {b64_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

    async def request(self, method, endpoint, **kwargs):
        """
        A wrapper around aiohttp.request that handles 401 Unauthorized
        by refreshing the token and retrying exactly once.
        """
        url = f"{self.base_url}{endpoint}"
        
        async with aiohttp.ClientSession() as session:
            try:
                # 1. Attempt the request
                async with session.request(
                    method, url, headers=self._get_auth_headers(), **kwargs
                ) as response:
                    
                    if response.status == 401:
                        logger.warning(f"[API] 401 Unauthorized for {endpoint}. Attempting refresh...")
                        
                        # 2. Refresh Token Flow
                        if await self.refresh_access_token():
                            # 3. Retry the request with new headers
                            logger.info(f"[API] Retrying {endpoint} with new token.")
                            async with session.request(
                                method, url, headers=self._get_auth_headers(), **kwargs
                            ) as retry_response:
                                return await self._handle_response(retry_response)
                        else:
                            logger.error("[API] Token refresh failed. Cannot retry request.")
                            return None

                    # Handle success or other errors
                    return await self._handle_response(response)

            except Exception as e:
                logger.error(f"[API] Request failed: {e}", exc_info=True)
                return None

    async def _handle_response(self, response):
        """Standardizes API response handling."""
        if 200 <= response.status < 300:
            try:
                return await response.json()
            except:
                return await response.text()
        else:
            logger.error(f"[API] Error {response.status}: {await response.text()}")
            return None

    async def refresh_access_token(self):
        """
        Performs the OAuth2 Refresh Grant flow.
        Thread-safe using asyncio.Lock.
        """
        async with self._refresh_lock:
            # Check if another task just refreshed it while we were waiting
            # (Optional optimization: check self.token_expires_at)
            
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token
            }
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.token_url,
                        data=payload,
                        headers=self._get_basic_auth_header()
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            
                            # Update instance state
                            self.access_token = data["access_token"]
                            self.refresh_token = data.get("refresh_token", self.refresh_token) # Sometimes it rotates
                            expires_in = data.get("expires_in", 3600)
                            self.token_expires_at = time.time() + expires_in
                            
                            logger.info("[API] Token successfully refreshed.")
                            
                            # TODO: Save new tokens to DB or .env here to persist across restarts
                            # save_tokens(self.access_token, self.refresh_token)
                            
                            return True
                        else:
                            text = await resp.text()
                            logger.critical(f"[API] Fatal: Refresh failed {resp.status}. Response: {text}")
                            return False
            except Exception as e:
                logger.error(f"[API] Refresh connection error: {e}")
                return False

    # --- Polling Methods ---

    async def get_stream_settings(self):
        """Fetches the streamer's settings (Title, etc)."""
        # Note: Endpoint inferred from common Joystick structures. verify actual path in docs.
        return await self.request("GET", "/v1/streamer/settings")

    async def get_live_status(self):
        """
        Polls for live status. 
        NOTE: WebSocket 'UserPresence' events are preferred for real-time status.
        Use this only for initial state checks or redundancy.
        """
        # Assuming a profile or user endpoint that returns status
        # Endpoint is a placeholder based on standard REST conventions
        data = await self.request("GET", "/v1/users/me") 
        if data:
            # Adjust key based on actual API response structure
            return data.get("is_live", False)
        return False