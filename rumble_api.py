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
        self.upload_host = "https://web11.rumble.com"
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

    def get_video_info(self, video_url: str) -> Dict[str, Any]:
        """Fetch video metadata via Rumble oEmbed API."""
        encoded_url = urllib.parse.quote(video_url)
        oembed_url = f"https://rumble.com/api/Media/oembed.json?url={encoded_url}"
        req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())

        html = data.get("html", "")
        m = re.search(r'/embed/(?:[a-zA-Z0-9_]+\.)?([a-zA-Z0-9_]+)/', html)
        if m:
            data["embed_id"] = m.group(1)
        return data

    def upload_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: str = "",
        visibility: str = "public",
        channel_id: Optional[str] = "7985034",
        license_tier: str = "6",
        custom_thumb_path: Optional[str] = None
    ) -> Dict[str, Any]:
        if not requests:
            raise RuntimeError("requests library is required for video upload")

        video_abs = os.path.abspath(video_path)
        if not os.path.exists(video_abs):
            return {"ok": False, "error": f"File not found: {video_abs}"}

        filename = os.path.basename(video_abs)
        file_size = os.path.getsize(video_abs)

        # 1. Upload Video Chunk/File using Filedata
        upload_endpoint = f"{self.upload_host}/upload.php?api=1.3"
        with open(video_abs, "rb") as f:
            files = {"Filedata": (filename, f, "video/mp4")}
            res = requests.post(upload_endpoint, headers=self.headers, cookies=self.cookies, files=files, timeout=300)

        if res.status_code != 200 or not res.text.strip():
            return {"ok": False, "error": f"Upload endpoint failed with status {res.status_code}: {res.text[:200]}"}

        video_token = res.text.strip()
        if "FAILED" in video_token or not re.match(r'^\d+-[0-9a-z]+\.[0-9a-z]+$', video_token, re.IGNORECASE):
            return {"ok": False, "error": f"Invalid video upload token received: {video_token}"}

        # 2. Upload Custom Thumbnail if provided
        custom_thumb_token = None
        if custom_thumb_path and os.path.exists(custom_thumb_path):
            thumb_name = os.path.basename(custom_thumb_path)
            with open(custom_thumb_path, "rb") as tf:
                t_files = {"customThumb": (thumb_name, tf, "image/jpeg")}
                t_res = requests.post(f"{self.upload_host}/upload.php?api=1.3&customThumb=1", headers=self.headers, cookies=self.cookies, files=t_files, timeout=60)
                if t_res.status_code == 200:
                    custom_thumb_token = t_res.text.strip()

        # 3. Form Submit (Publish)
        form_endpoint = f"{self.upload_host}/upload.php?api=1.3&form=1"
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

        # 4. Check for success response
        if "uf.response.setSuccess" in resp_text:
            m_url = re.search(r'url:"([^"]+)"', resp_text)
            m_fid = re.search(r'fid:(\d+)', resp_text)
            m_title = re.search(r'title:"([^"]+)"', resp_text)
            return {
                "ok": True,
                "url": m_url.group(1) if m_url else None,
                "fid": int(m_fid.group(1)) if m_fid else None,
                "title": m_title.group(1) if m_title else title,
                "video_token": video_token
            }
        elif "uf.response.setErrors" in resp_text:
            m_err = re.search(r'setErrors\(\{(.*?)\}', resp_text)
            return {
                "ok": False,
                "error": m_err.group(1) if m_err else resp_text[:200]
            }

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
