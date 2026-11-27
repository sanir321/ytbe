#!/usr/bin/env python3
"""
Multi-Channel YouTube Re-Authorizer for sanir321/ytbe
Auto-detects selected channel (SH SARKAR, GTA6_DS, ROBLOX OING)
and updates the correct GitHub Secret and local token files.
"""

import os
import sys
import json
import pickle
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import subprocess
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

CLIENT_SECRETS_FILE = "/home/samirkhadka/client_secret.json"
REPO = "sanir321/ytbe"
REDIRECT_URI = "http://localhost:8080"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

CHANNELS = {
    "UCN5kwanpmxeRNKeqs-4fzMQ": {
        "name": "SH SARKAR",
        "secret": "SARKAR_YT_REFRESH_TOKEN",
        "pickle": os.path.expanduser("~/.sarkar_token.pickle")
    },
    "UCU4JAQ7BGkZW1BYkeZWBCww": {
        "name": "GTA6_DS",
        "secret": "GTA6_YT_REFRESH_TOKEN",
        "pickle": os.path.expanduser("~/.gta6_token.pickle")
    },
    "UC_Jngx7J4YyWaeD18FyEniw": {
        "name": "ROBLOX OING",
        "secret": "YT_REFRESH_TOKEN",
        "json": os.path.expanduser("~/youtube_token.json"),
        "pickle": os.path.expanduser("~/.youtube_token.pickle")
    }
}

auth_code = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed_url = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed_url.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>YouTube Authorization Successful</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 60px 20px; }
                    .card { background: #1e293b; max-width: 500px; margin: 0 auto; padding: 40px; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); border: 1px solid #334155; }
                    h1 { color: #22c55e; margin-bottom: 12px; font-size: 26px; }
                    p { color: #94a3b8; font-size: 16px; line-height: 1.5; }
                    .badge { display: inline-block; background: #0284c7; color: white; padding: 6px 14px; border-radius: 9999px; font-weight: 600; margin-top: 15px; }
                </style>
            </head>
            <body>
                <div class="card">
                    <h1>✅ Authorization Successful!</h1>
                    <p>OAuth tokens received. Antigravity is updating your GitHub Secrets now.</p>
                    <div class="badge">You may close this tab</div>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No authorization code received.")

    def log_message(self, format, *args):
        pass

def authorize_once():
    global auth_code
    auth_code = None

    with open(CLIENT_SECRETS_FILE, "r") as f:
        client_config = json.load(f)

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, _ = flow.authorization_url(
        prompt="consent select_account",
        access_type="offline"
    )

    print("\n" + "=" * 75, flush=True)
    print("👉 GOOGLE YOUTUBE OAUTH AUTHENTICATION LINK:", flush=True)
    print(auth_url, flush=True)
    print("=" * 75 + "\n", flush=True)

    # Launch Chrome on DISPLAY=:0
    try:
        subprocess.Popen(["google-chrome", auth_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("[BROWSER] Opened Google Chrome automatically.", flush=True)
    except Exception as e:
        print(f"[BROWSER] Could not auto-launch browser: {e}", flush=True)

    print("[SERVER] Listening on http://localhost:8080 for callback...", flush=True)
    server = HTTPServer(("127.0.0.1", 8080), OAuthCallbackHandler)
    while not auth_code:
        server.handle_request()
    server.server_close()

    print("[AUTH] Exchanging auth code for tokens...", flush=True)
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    if not creds or not creds.refresh_token:
        print("❌ [ERROR] No refresh token returned. Ensure you granted offline access.", flush=True)
        return None

    # Inspect authenticated channel
    yt = build("youtube", "v3", credentials=creds)
    ch_resp = yt.channels().list(part="snippet", mine=True).execute()

    if not ch_resp.get("items"):
        print("❌ [ERROR] Could not retrieve channel information for authenticated user.", flush=True)
        return None

    ch_item = ch_resp["items"][0]
    ch_id = ch_item["id"]
    ch_title = ch_item["snippet"]["title"]
    print(f"\n🎯 [DETECTED CHANNEL] {ch_title} (ID: {ch_id})", flush=True)

    ch_config = CHANNELS.get(ch_id)
    if ch_config:
        secret_name = ch_config["secret"]
        print(f"[GITHUB] Setting secret {secret_name} on {REPO}...", flush=True)
        try:
            subprocess.run(
                ["gh", "secret", "set", secret_name, "-R", REPO, "-b", creds.refresh_token],
                check=True
            )
            print(f"✅ [SUCCESS] Updated GitHub secret {secret_name} successfully!", flush=True)
        except Exception as e:
            print(f"❌ [GITHUB ERROR] Failed to set secret {secret_name}: {e}", flush=True)

        # Save local files
        if "pickle" in ch_config:
            with open(ch_config["pickle"], "wb") as f:
                pickle.dump(creds, f)
            print(f"[LOCAL] Saved credentials pickle to {ch_config['pickle']}", flush=True)

        if "json" in ch_config:
            client_type = list(client_config.keys())[0]
            token_json = {
                "client_id": client_config[client_type]["client_id"],
                "client_secret": client_config[client_type]["client_secret"],
                "refresh_token": creds.refresh_token,
                "token": creds.token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": SCOPES
            }
            with open(ch_config["json"], "w") as f:
                json.dump(token_json, f, indent=2)
            print(f"[LOCAL] Saved credentials JSON to {ch_config['json']}", flush=True)

        return ch_config["name"]
    else:
        print(f"⚠️ [UNKNOWN CHANNEL] Authenticated to channel '{ch_title}' ({ch_id}) which is not recognized in config.", flush=True)
        return None

if __name__ == "__main__":
    authorized = authorize_once()
    if authorized:
        print(f"\n🎉 Successfully re-authorized {authorized}!")
    else:
        print("\n❌ Authorization did not complete.")
