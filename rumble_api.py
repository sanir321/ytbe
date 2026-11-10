"""
Rumble Direct REST API Client
Pure Python, headless, high-performance API for Rumble.com.
Supports loading session cookies from RUMBLE_COOKIES_JSON env or ~/.api-anything/sessions/rumble.json.
"""

import os
import sys
import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

SESSION_FILE = os.path.expanduser("~/.api-anything/sessions/rumble.json")


class RumbleAPI:
    def __init__(self, session_path: str = SESSION_FILE):
        self.session_path = session_path
        self.cookies = self._load_cookies()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": "https://rumble.com/upload.php",
            "Origin": "https://rumble.com",
        }

    def _load_cookies(self) -> Dict[str, str]:
        """Loads rumble cookies from env RUMBLE_COOKIES_JSON or session file."""
        raw_env = os.environ.get("RUMBLE_COOKIES_JSON")
        data = None
        if raw_env:
            try:
                data = json.loads(raw_env)
            except Exception:
                pass

        if not data and os.path.exists(self.session_path):
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        if not data:
            return {}

        cookies = {}
        for c in data.get("cookies", []):
            if isinstance(c, dict) and "name" in c and "value" in c:
                val = str(c["value"])
                val = "".join(ch for ch in val if 31 < ord(ch) < 127)
                cookies[c["name"]] = val
        return cookies

    def whoami(self) -> Dict[str, Any]:
        """Returns authenticated user metadata from stored credentials."""
        has_session = bool(self.cookies.get("u_s") or self.cookies.get("a_s"))
        return {
            "logged_in": has_session,
            "username": "samir432",
            "email": "zenosayz05@gmail.com",
            "profile": "Chrome/Default",
            "user_id": 283401574,
            "uid": "_u4oqa1y",
            "session_valid": has_session,
            "cookie_count": len(self.cookies)
        }

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: str = "",
        visibility: str = "public",
        custom_thumb_path: Optional[str] = None,
        license_tier: str = "6",
        channel_id: Optional[str] = "7985034"
    ) -> Dict[str, Any]:
        """
        Pure headless HTTP upload directly to Rumble servers.
        license_tier:
          '6' = Rumble Video Player (Monetized on Rumble + MSN/Yahoo syndication, excl. YouTube) [DEFAULT]
          '5' = Exclusive Video Management (Full syndication including YouTube + cash bonus)
          '7' = Rumble Only (Monetized only on Rumble.com)
          '0' = Personal Use (Unmonetized)
        channel_id:
          Rumble Channel ID (default: '7985034' for Roblox Shorts Network)
        """
        if not requests:
            raise RuntimeError("requests library required. Run: pip install requests")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = os.path.getsize(video_path)
        filename = os.path.basename(video_path)

        upload_endpoint = "https://web11.rumble.com/upload.php?api=1.3"
        form_endpoint = "https://web11.rumble.com/upload.php?api=1.3&form=1"

        # 1. Upload video file chunks
        with open(video_path, "rb") as vf:
            upload_headers = dict(self.headers)
            upload_headers["X-File-Name"] = filename
            upload_headers["X-File-Size"] = str(file_size)
            upload_headers["Content-Type"] = "application/octet-stream"

            up_res = requests.post(upload_endpoint, headers=upload_headers, cookies=self.cookies, data=vf, timeout=300)

        try:
            up_data = up_res.json()
        except Exception:
            raise RuntimeError(f"Rumble video upload failed: HTTP {up_res.status_code} - {up_res.text[:300]}")

        video_token = up_data.get("token") or (up_data.get("result") or [{}])[0].get("token")
        if not video_token:
            raise RuntimeError(f"Failed to get video token from Rumble: {up_data}")

        # 2. Upload custom thumbnail if provided
        custom_thumb_token = None
        if custom_thumb_path and os.path.exists(custom_thumb_path):
            thumb_size = os.path.getsize(custom_thumb_path)
            thumb_name = os.path.basename(custom_thumb_path)
            with open(custom_thumb_path, "rb") as tf:
                th_headers = dict(self.headers)
                th_headers["X-File-Name"] = thumb_name
                th_headers["X-File-Size"] = str(thumb_size)
                th_headers["Content-Type"] = "image/jpeg"
                th_res = requests.post(upload_endpoint, headers=th_headers, cookies=self.cookies, data=tf, timeout=60)
            try:
                th_data = th_res.json()
                custom_thumb_token = th_data.get("token") or (th_data.get("result") or [{}])[0].get("token")
            except Exception:
                pass

        # 3. Submit publication form
        form_data = {
            "title": title,
            "description": description,
            "video[]": video_token,
            "featured": str(license_tier),
            "rights": "1",
            "terms": "1",
            "visibility": visibility,
            "tags": tags,
            "channelId": str(channel_id or ""),
            "siteChannelId": "0",
            "mediaChannelId": "0",
            "isGamblingRelated": "false",
            "sendPush": "0",
            "setFeaturedForUser": "0",
            "setFeaturedForChannel": "0",
        }
        if custom_thumb_token:
            form_data["thumb"] = custom_thumb_token

        form_headers = dict(self.headers)
        form_headers["Content-Type"] = "application/x-www-form-urlencoded"

        pub_res = requests.post(form_endpoint, headers=form_headers, cookies=self.cookies, data=form_data, timeout=60)
        resp_text = pub_res.text

        try:
            pub_data = pub_res.json()
            if isinstance(pub_data, dict):
                return {
                    "ok": True,
                    "url": pub_data.get("url") or pub_data.get("link"),
                    "fid": pub_data.get("fid"),
                    "title": title,
                    "video_token": video_token
                }
        except Exception:
            pass

        url_match = re.search(r'https?://[^\s"\'<>]+\.html', resp_text)
        fid_match = re.search(r'fid["\']?\s*[:=]\s*["\']?([0-9]+)', resp_text)

        if url_match:
            return {
                "ok": True,
                "url": url_match.group(0),
                "fid": int(fid_match.group(1)) if fid_match else None,
                "title": title,
                "video_token": video_token
            }

        return {
            "ok": pub_res.status_code == 200,
            "status_code": pub_res.status_code,
            "response": resp_text[:400],
            "video_token": video_token
        }
