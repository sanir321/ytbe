"""Generate a YouTube OAuth refresh token and save it to .env."""

import json
import os
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

import requests

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
CLIENT_SECRET_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "client_secret_1019500787445-7hk1dg0f9ecq9pu4l2k820hdnujdrh5a.apps.googleusercontent.com.json",
)

with open(CLIENT_SECRET_FILE) as f:
    config = json.load(f)["installed"]

CLIENT_ID = config["client_id"]
CLIENT_SECRET = config["client_secret"]
REDIRECT_URI = "http://localhost"

auth_params = urlencode({
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "response_type": "code",
    "scope": " ".join(SCOPES),
    "access_type": "offline",
    "prompt": "consent",
})
AUTH_URL = f"{config['auth_uri']}?{auth_params}"

print("=" * 60)
print("YouTube OAuth - Generate Refresh Token")
print("=" * 60)
print(f"\n1. Visit this URL:\n   {AUTH_URL}\n")
print("2. Sign in & authorize")
print("3. After redirect to localhost, COPY the full URL")
print("4. Paste it below\n")

redirect_result = input("Paste the full redirect URL: ").strip()

code = parse_qs(urlparse(redirect_result).query).get("code", [None])[0]
if not code:
    code = parse_qs(urlparse("?" + redirect_result.split("?")[-1]).query).get("code", [None])[0]
if not code:
    print("Could not extract authorization code from URL")
    exit(1)

resp = requests.post(config["token_uri"], data={
    "code": code,
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "redirect_uri": REDIRECT_URI,
    "grant_type": "authorization_code",
})
tokens = resp.json()

if "refresh_token" not in tokens:
    print(f"Error getting refresh token: {tokens}")
    exit(1)

refresh_token = tokens["refresh_token"]
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
with open(env_path, "a") as f:
    f.write(f"\nYT_REFRESH_TOKEN={refresh_token}\n")

print(f"\nRefresh token saved to .env")
print(f"Token: {refresh_token[:20]}...{refresh_token[-10:]}")
