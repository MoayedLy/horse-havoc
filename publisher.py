"""
Automated Dispatch & Social Media Publisher for HORSE HAVOC
============================================================
Handles automated delivery of rendered race shorts and metadata:
1. Safe Primary Dispatch (Immediate setup):
   - Telegram Bot API: Sends video directly to your phone/channel with caption and tags.
   - Discord Webhook: (Optional) Posts video and metadata to a Discord channel.
2. Direct Social Media API Stubs:
   - YouTube Data API v3 (Shorts upload)
   - TikTok Content Posting API (v2)
   - Instagram Reels (Meta Graph API)
"""

import os
import sys
import json
import time
import math

# Reconfigure console encoding to UTF-8 to prevent Windows cp1252 crash with emojis
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Fallback .env parser if python-dotenv is not installed
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

try:
    import requests
except ImportError:
    requests = None

try:
    import boto3
except ImportError:
    boto3 = None

# ----------------------------------------------------------------------
# 1. PRIMARY SAFE DISPATCH: TELEGRAM BOT
# ----------------------------------------------------------------------
def send_telegram_video(video_path, title, description, tags, bot_token=None, chat_id=None, is_test=False):
    """
    Uploads the rendered short video directly to a Telegram channel or chat.
    Arrives on your phone ready to review and one-tap share to TikTok/Shorts.
    """
    bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        print("[DISPATCH: Telegram] Notice: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in .env.")
        print("                      Video and metadata are saved locally and ready for manual dispatch.")
        return {"status": "skipped", "channel": "telegram", "reason": "Missing credentials in .env"}

    if is_test:
        print("[DISPATCH: Telegram] (Test Mode) Validated credentials. Skipping actual network upload.")
        return {"status": "success (test)", "channel": "telegram"}

    if not requests:
        print("[DISPATCH: Telegram] Warning: `requests` library not found.")
        return {"status": "error", "channel": "telegram", "reason": "requests library missing"}

    if not os.path.exists(video_path):
        return {"status": "error", "channel": "telegram", "reason": f"Video file not found: {video_path}"}

    # Format caption within Telegram's 1024 character caption limit
    caption_lines = [
        f"🐎 {title}",
        "",
        description[:600] if len(description) > 600 else description,
        "",
        tags
    ]
    caption = "\n".join(caption_lines)[:1020]

    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    print(f"[DISPATCH: Telegram] Uploading {os.path.basename(video_path)} ({os.path.getsize(video_path) / (1024*1024):.1f} MB)...")

    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file, "video/mp4")}
            data = {
                "chat_id": chat_id,
                "caption": caption,
                "supports_streaming": True
            }
            response = requests.post(url, data=data, files=files, timeout=180)
            res_json = response.json()

            if res_json.get("ok"):
                msg_id = res_json.get("result", {}).get("message_id")
                print(f"[DISPATCH: Telegram] SUCCESS: Video sent to chat {chat_id} (Message ID: {msg_id})")
                return {"status": "success", "channel": "telegram", "message_id": msg_id}
            else:
                err_desc = res_json.get("description", "Unknown Telegram error")
                print(f"[DISPATCH: Telegram] ERROR: {err_desc}")
                return {"status": "error", "channel": "telegram", "reason": err_desc}
    except Exception as e:
        print(f"[DISPATCH: Telegram] Exception during upload: {e}")
        return {"status": "error", "channel": "telegram", "reason": str(e)}

# ----------------------------------------------------------------------
# 2. OPTIONAL DISPATCH: DISCORD WEBHOOK
# ----------------------------------------------------------------------
def send_discord_webhook(video_path, title, tags, webhook_url=None, is_test=False):
    """Posts notification and video file to a Discord webhook channel."""
    webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        return {"status": "skipped", "channel": "discord", "reason": "No webhook URL configured"}

    if is_test:
        return {"status": "success (test)", "channel": "discord"}

    if not requests or not os.path.exists(video_path):
        return {"status": "error", "channel": "discord", "reason": "Missing requests or video"}

    # Discord 25MB free attachment ceiling check
    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    content = f"🏁 **New Horse Havoc Video Ready!**\n**Title:** {title}\n**Tags:** {tags}"

    try:
        if file_size_mb <= 24.5:
            with open(video_path, "rb") as f:
                files = {"file": (os.path.basename(video_path), f, "video/mp4")}
                data = {"content": content}
                r = requests.post(webhook_url, data=data, files=files, timeout=120)
        else:
            r = requests.post(webhook_url, json={"content": f"{content}\n*(File size {file_size_mb:.1f}MB exceeds Discord 25MB limit - saved locally)*"}, timeout=30)

        if r.status_code in (200, 204):
            print("[DISPATCH: Discord] SUCCESS: Notification posted to Discord.")
            return {"status": "success", "channel": "discord"}
        else:
            return {"status": "error", "channel": "discord", "reason": f"Status code {r.status_code}"}
    except Exception as e:
        return {"status": "error", "channel": "discord", "reason": str(e)}

# ----------------------------------------------------------------------
# 3. DIRECT SOCIAL MEDIA API STUBS (YouTube, TikTok, Instagram)
# ----------------------------------------------------------------------
def get_youtube_access_token(token_file="token.json", secrets_file="client_secrets.json"):
    """
    Loads YouTube OAuth2 credentials from token_file and automatically refreshes
    expired access tokens using direct HTTP requests.
    Zero external Google SDKs or cryptography required.
    """
    if not os.path.exists(token_file):
        return None

    try:
        with open(token_file, "r", encoding="utf-8") as f:
            token_data = json.load(f)
    except Exception as e:
        print(f"[DISPATCH: YouTube] Warning: Could not read {token_file}: {e}")
        return None

    access_token = token_data.get("token") or token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    token_uri = token_data.get("token_uri") or "https://oauth2.googleapis.com/token"

    client_id = token_data.get("client_id")
    client_secret = token_data.get("client_secret")

    # If client_id or client_secret are missing in token.json, look in client_secrets.json
    if (not client_id or not client_secret) and os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                sdata = json.load(f)
                cinfo = sdata.get("installed") or sdata.get("web") or {}
                client_id = client_id or cinfo.get("client_id")
                client_secret = client_secret or cinfo.get("client_secret")
                token_uri = token_uri or cinfo.get("token_uri", "https://oauth2.googleapis.com/token")
        except Exception:
            pass

    # Check expiration if expiry field is present
    is_expired = False
    expiry_str = token_data.get("expiry")
    if expiry_str:
        try:
            import datetime
            clean_str = expiry_str.replace("Z", "+00:00")
            exp_dt = datetime.datetime.fromisoformat(clean_str)
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            # Expired or expiring within 60 seconds
            if now_dt >= (exp_dt - datetime.timedelta(seconds=60)):
                is_expired = True
        except Exception:
            pass
    elif not access_token:
        is_expired = True

    # If not expired and access token is present, return it
    if not is_expired and access_token:
        return access_token

    # Otherwise refresh access token
    if refresh_token and client_id and client_secret and requests:
        try:
            refresh_payload = {
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }
            resp = requests.post(token_uri, data=refresh_payload, timeout=25)
            if resp.status_code == 200:
                new_data = resp.json()
                new_token = new_data.get("access_token")
                if new_token:
                    token_data["token"] = new_token
                    token_data["access_token"] = new_token
                    expires_in = new_data.get("expires_in", 3600)
                    import datetime
                    exp_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
                    token_data["expiry"] = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    if new_data.get("refresh_token"):
                        token_data["refresh_token"] = new_data["refresh_token"]
                    if client_id:
                        token_data["client_id"] = client_id
                    if client_secret:
                        token_data["client_secret"] = client_secret

                    with open(token_file, "w", encoding="utf-8") as f:
                        json.dump(token_data, f, indent=2)

                    return new_token
            else:
                print(f"[DISPATCH: YouTube] Token refresh failed HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[DISPATCH: YouTube] Token refresh exception: {e}")

    return access_token


def authenticate_youtube(secrets_file="client_secrets.json", token_file="token.json"):
    """
    Lightweight interactive OAuth2 authorization flow for YouTube Data API v3.
    Uses Python standard library http.server and urllib with zero heavy Google SDKs.
    """
    import urllib.parse
    import webbrowser
    import http.server
    import socketserver

    if not os.path.exists(secrets_file):
        print(f"[DISPATCH: YouTube] Error: Secrets file '{secrets_file}' not found.")
        print("Please place your OAuth client secrets JSON file in the project directory.")
        return None

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            secrets_data = json.load(f)
    except Exception as e:
        print(f"[DISPATCH: YouTube] Failed to read {secrets_file}: {e}")
        return None

    client_info = secrets_data.get("installed") or secrets_data.get("web") or {}
    client_id = client_info.get("client_id")
    client_secret = client_info.get("client_secret")
    auth_uri = client_info.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")
    token_uri = client_info.get("token_uri", "https://oauth2.googleapis.com/token")

    if not client_id or not client_secret:
        print("[DISPATCH: YouTube] Invalid client_secrets.json: missing client_id or client_secret.")
        return None

    port = 8080
    redirect_uri = f"http://localhost:{port}/"
    scope = "https://www.googleapis.com/auth/youtube.upload"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{auth_uri}?{urllib.parse.urlencode(auth_params)}"

    print("=" * 70)
    print(" [HORSE HAVOC] LIGHTWEIGHT YOUTUBE OAUTH2 AUTHENTICATION")
    print("=" * 70)
    print(f" * Client Secrets File : {os.path.abspath(secrets_file)}")
    print(f" * Destination Token   : {os.path.abspath(token_file)}")
    print(f" * Required Scope      : {scope}")
    print("-" * 70)
    print(" Opening browser for Google authorization...")
    print(" If the browser does not open automatically, visit this URL:")
    print(f"\n{auth_url}\n")
    print("-" * 70)
    print(" [NOTE for Headless Linux VPS]")
    print(" If running on a headless VPS without physical browser, authorize locally")
    print(" on your PC, then upload the generated 'token.json' to the VPS.")
    print("=" * 70)
    sys.stdout.flush()

    auth_code = None

    class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            parsed_url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed_url.query)
            if "code" in query:
                auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = (
                    "<html><body style='font-family: sans-serif; text-align: center; padding: 50px;'>"
                    "<h2>Authentication Successful!</h2>"
                    "<p>Horse Havoc YouTube authorization code captured successfully.</p>"
                    "<p>You can close this tab and return to the terminal.</p>"
                    "</body></html>"
                )
                self.wfile.write(html.encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Authorization failed: no code parameter received.")

        def log_message(self, format, *args):
            pass

    server = None
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("127.0.0.1", port), OAuthCallbackHandler)
        server.timeout = 180

        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

        print(f"Waiting for authorization callback on {redirect_uri} (timeout: 180s)...")
        sys.stdout.flush()

        while not auth_code:
            server.handle_request()

    except Exception as se:
        print(f"[DISPATCH: YouTube] Local callback notice: {se}")
        print("Manual authorization fallback: Visit the auth URL above, grant access,")
        print("and if redirected to localhost fails, enter the 'code' parameter here.")
        try:
            auth_code = input("Enter authorization code: ").strip()
        except Exception:
            pass
    finally:
        if server:
            try:
                server.server_close()
            except Exception:
                pass

    if not auth_code:
        print("[DISPATCH: YouTube] Error: Did not receive authorization code.")
        return None

    # Exchange code for tokens
    print("[DISPATCH: YouTube] Exchanging authorization code for OAuth tokens...")
    token_payload = {
        "code": auth_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    try:
        resp = requests.post(token_uri, data=token_payload, timeout=30)
        if resp.status_code != 200:
            print(f"[DISPATCH: YouTube] Token exchange failed ({resp.status_code}): {resp.text}")
            return None

        token_data = resp.json()
        token_data["token"] = token_data.get("access_token")
        token_data["client_id"] = client_id
        token_data["client_secret"] = client_secret
        token_data["token_uri"] = token_uri
        token_data["scopes"] = [scope]
        expires_in = token_data.get("expires_in", 3600)
        import datetime
        expiry_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
        token_data["expiry"] = expiry_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

        print("\n" + "=" * 70)
        print(" SUCCESS: Lightweight YouTube OAuth2 authentication completed!")
        print(f" * Credentials saved to : {os.path.abspath(token_file)}")
        print(" All future YouTube Shorts uploads are now 100% automated!")
        print("=" * 70)
        return token_data
    except Exception as e:
        print(f"[DISPATCH: YouTube] Error during token exchange: {e}")
        return None


def publish_to_youtube(video_path, title, description, tags, client_secrets=None, token_path=None, privacy="public", is_test=False, privacy_status: str = "public"):
    """
    Lightweight YouTube Data API v3 implementation for automated YouTube Shorts publishing.
    Uses pure HTTP REST requests with ZERO heavy Google SDKs or cryptography dependencies.
    Workflow:
      1. Loads credentials from token.json (or client_secrets.json).
      2. Refreshes expired access token via https://oauth2.googleapis.com/token.
      3. Initiates resumable upload session with snippet metadata (Gaming category ID 20).
      4. Streams video binary via PUT to the acquired upload URL.
      5. Returns standardized status dict with video ID and Shorts URLs.
    """
    secrets_file = client_secrets or os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
    token_file = token_path or os.getenv("YOUTUBE_TOKEN_FILE", "token.json")

    if is_test:
        print(f"[DISPATCH: YouTube] (Test Mode) Lightweight REST integration ready. Configured secrets: {secrets_file}")
        return {"status": "test_ok", "channel": "youtube"}

    if not requests:
        print("[DISPATCH: YouTube] Error: `requests` library is required for YouTube upload.")
        return {"status": "error", "channel": "youtube", "reason": "requests library missing"}

    if not os.path.exists(video_path):
        return {"status": "error", "channel": "youtube", "reason": f"Video file not found: {video_path}"}

    if not os.path.exists(token_file) and not os.path.exists(secrets_file):
        print(f"[DISPATCH: YouTube] Notice: '{token_file}' or '{secrets_file}' not found.")
        print("                     Run 'python publisher.py --auth-youtube' to authenticate.")
        return {"status": "skipped", "channel": "youtube", "reason": f"Missing {token_file} / {secrets_file}"}

    access_token = get_youtube_access_token(token_file=token_file, secrets_file=secrets_file)
    if not access_token:
        return {"status": "error", "channel": "youtube", "reason": "Failed to obtain valid YouTube access token. Run --auth-youtube."}

    tag_list = tags if isinstance(tags, list) else [t.strip() for t in tags.replace('#', '').split()]
    target_privacy = privacy if privacy is not None else (privacy_status or os.getenv("YOUTUBE_PRIVACY_STATUS", "public"))
    privacy_status = target_privacy

    body = {
        "snippet": {
            "title": title[:100],
            "description": f"{description}\n\n{' '.join(['#' + t for t in tag_list])}",
            "tags": tag_list,
            "categoryId": "20"  # Gaming category
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)

    # 1. Initialize Resumable Upload Session
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    init_headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(file_size)
    }

    print(f"[DISPATCH: YouTube] Initiating upload session for {os.path.basename(video_path)} ({file_size_mb:.2f} MB) as '{target_privacy}'...")
    sys.stdout.flush()

    try:
        init_resp = requests.post(init_url, headers=init_headers, json=body, timeout=30)
    except Exception as e:
        return {"status": "error", "channel": "youtube", "reason": f"Network error initiating session: {e}"}

    # Handle expired token retry
    if init_resp.status_code == 401:
        print("[DISPATCH: YouTube] Token 401 Unauthorized received. Forcing token refresh...")
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            tdata["expiry"] = "2000-01-01T00:00:00Z"
            with open(token_file, "w", encoding="utf-8") as f:
                json.dump(tdata, f)
        except Exception:
            pass
        access_token = get_youtube_access_token(token_file=token_file, secrets_file=secrets_file)
        init_headers["Authorization"] = f"Bearer {access_token}"
        init_resp = requests.post(init_url, headers=init_headers, json=body, timeout=30)

    if init_resp.status_code not in (200, 201):
        err_msg = f"Failed to initiate upload session (HTTP {init_resp.status_code}): {init_resp.text}"
        print(f"[DISPATCH: YouTube] {err_msg}")
        return {"status": "error", "channel": "youtube", "reason": err_msg}

    upload_url = init_resp.headers.get("Location")
    if not upload_url:
        return {"status": "error", "channel": "youtube", "reason": "No 'Location' header returned in upload session response."}

    # 2. Upload video binary
    print(f"[DISPATCH: YouTube] Upload session acquired. Streaming {file_size_mb:.2f} MB...")
    sys.stdout.flush()

    upload_headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size),
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}"
    }

    try:
        with open(video_path, "rb") as vf:
            upload_resp = requests.put(upload_url, headers=upload_headers, data=vf, timeout=300)
    except Exception as e:
        return {"status": "error", "channel": "youtube", "reason": f"Upload streaming failed: {e}"}

    if upload_resp.status_code in (200, 201):
        resp_data = upload_resp.json()
        video_id = resp_data.get("id")
        watch_url = f"https://youtu.be/{video_id}"
        shorts_url = f"https://www.youtube.com/shorts/{video_id}"
        print(f"[DISPATCH: YouTube] SUCCESS (HTTP {upload_resp.status_code} OK)! Video ID: {video_id}")
        print(f"[DISPATCH: YouTube] Watch URL  : {watch_url}")
        print(f"[DISPATCH: YouTube] Shorts URL : {shorts_url}")
        return {
            "status": "success",
            "channel": "youtube",
            "video_id": video_id,
            "watch_url": watch_url,
            "shorts_url": shorts_url,
            "privacy": privacy_status
        }
    else:
        err_msg = f"Upload failed (HTTP {upload_resp.status_code}): {upload_resp.text}"
        print(f"[DISPATCH: YouTube] {err_msg}")
        return {"status": "error", "channel": "youtube", "reason": err_msg}

# ----------------------------------------------------------------------
# 4. TIKTOK CONTENT POSTING API (v2) & AGGREGATOR FALLBACK
# ----------------------------------------------------------------------
class TikTokPublisher:
    """
    Official TikTok Content Posting API (v2) Client.
    Workflow:
      1. Calls POST /v2/post/publish/video/init/ to register upload session and acquire upload_url.
      2. Uploads video binary in 10MB chunks using PUT with Content-Range headers.
      3. Polls POST /v2/post/publish/status/fetch/ to verify transcoding and publication.
    """
    BASE_URL = "https://open.tiktokapis.com"

    def __init__(self, access_token=None, client_key=None, client_secret=None, post_mode=None):
        self.client_key = client_key or os.getenv("TIKTOK_CLIENT_KEY", "").strip()
        self.client_secret = client_secret or os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
        self.post_mode = post_mode or os.getenv("TIKTOK_POST_MODE", "MEDIA_UPLOAD").strip()

        # Priority: passed token -> .env -> tiktok_token.json
        self.access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
        if not self.access_token and os.path.exists("tiktok_token.json"):
            try:
                with open("tiktok_token.json", "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                    self.access_token = tdata.get("access_token", "").strip()
            except Exception:
                pass

    def is_configured(self):
        return bool(self.access_token)

    def refresh_token(self):
        """Attempts to refresh an expired access token using stored refresh_token."""
        token_path = "tiktok_token.json"
        if not os.path.exists(token_path):
            return False
        try:
            with open(token_path, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            rft = tdata.get("refresh_token")
            if not rft:
                return False

            url = f"{self.BASE_URL}/v2/oauth/token/"
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            payload = {
                "client_key": self.client_key,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": rft
            }
            resp = requests.post(url, headers=headers, data=payload, timeout=30)
            data = resp.json()
            tok_data = data.get("data") if isinstance(data.get("data"), dict) else data
            new_access = tok_data.get("access_token")
            if new_access:
                self.access_token = new_access
                tdata["access_token"] = new_access
                if tok_data.get("refresh_token"):
                    tdata["refresh_token"] = tok_data["refresh_token"]
                tdata["obtained_at"] = time.time()
                with open(token_path, "w", encoding="utf-8") as f:
                    json.dump(tdata, f, indent=2)
                print("[DISPATCH: TikTok] Successfully auto-refreshed TikTok access token!")
                return True
        except Exception as e:
            print(f"[DISPATCH: TikTok] Token auto-refresh failed: {e}")
        return False

    def init_video_upload(self, video_path, caption, privacy_level="PUBLIC_TO_EVERYONE", disable_comment=False, disable_duet=False, disable_stitch=False, post_mode=None):
        """
        Initializes a video publishing session via TikTok Content Posting API.
        Supports:
          - post_mode = "MEDIA_UPLOAD" (Upload to Creator Inbox / Drafts) -> Only requires `video.upload` scope
          - post_mode = "DIRECT_POST" (Instant public feed publishing) -> Requires audited `video.publish` scope
        """
        if not requests:
            raise RuntimeError("`requests` library required for TikTok uploading.")

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = os.path.getsize(video_path)
        # TikTok Content Posting API Chunk rules:
        # Videos <= 64MB must be uploaded as a single chunk (chunk_size = video_size, total_chunk_count = 1).
        # Videos > 64MB use floor division for chunk calculation.
        if file_size <= 64 * 1024 * 1024:
            chunk_size = file_size
            total_chunks = 1
        else:
            chunk_size = 20 * 1024 * 1024
            total_chunks = file_size // chunk_size

        clean_caption = caption[:2200] if len(caption) > 2200 else caption
        mode = post_mode or self.post_mode or "MEDIA_UPLOAD"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }

        if mode in ("MEDIA_UPLOAD", "INBOX"):
            # Official TikTok Inbox/Drafts Upload endpoint (strictly requires only `video.upload` scope)
            url = f"{self.BASE_URL}/v2/post/publish/inbox/video/init/"
            payload = {
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunks
                }
            }
        else:
            # Direct Public Post endpoint (requires audited `video.publish` scope)
            url = f"{self.BASE_URL}/v2/post/publish/video/init/"
            post_info = {
                "title": clean_caption,
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_stitch": disable_stitch,
                "disable_comment": disable_comment,
                "video_cover_timestamp_ms": 1000
            }
            payload = {
                "post_mode": mode,
                "post_info": post_info,
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunks
                }
            }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        data = resp.json()

        error_info = data.get("error", {})
        if error_info.get("code") != "ok":
            code = error_info.get("code")
            msg = error_info.get("message")
            log_id = error_info.get("log_id", "")
            raise RuntimeError(f"TikTok init failed [code: {code}]: {msg} (log_id: {log_id})")

        pub_data = data.get("data", {})
        publish_id = pub_data.get("publish_id")
        upload_url = pub_data.get("upload_url")

        return {
            "publish_id": publish_id,
            "upload_url": upload_url,
            "chunk_size": chunk_size,
            "total_chunks": total_chunks,
            "file_size": file_size,
            "post_mode": mode
        }

    def upload_chunks(self, upload_url, video_path, chunk_size, file_size):
        """Transfers binary video chunks with Content-Range headers."""
        with open(video_path, "rb") as f:
            chunk_idx = 0
            start_byte = 0
            while start_byte < file_size:
                f.seek(start_byte)
                chunk_data = f.read(chunk_size)
                end_byte = start_byte + len(chunk_data) - 1

                headers = {
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                    "Content-Type": "video/mp4"
                }

                pct = int((end_byte + 1) / file_size * 100)
                print(f"[DISPATCH: TikTok] Uploading chunk {chunk_idx + 1} ({start_byte}-{end_byte}/{file_size} bytes - {pct}%)...")
                sys.stdout.flush()

                put_resp = requests.put(upload_url, headers=headers, data=chunk_data, timeout=120)
                if put_resp.status_code not in (200, 201, 206):
                    raise RuntimeError(f"TikTok chunk upload failed with HTTP {put_resp.status_code}: {put_resp.text}")

                start_byte += len(chunk_data)
                chunk_idx += 1

        print("[DISPATCH: TikTok] Video upload transfer completed! Verifying processing status...")

    def poll_publish_status(self, publish_id, max_wait_sec=60, poll_interval=3):
        """Polls POST /v2/post/publish/status/fetch/ until processing completes."""
        url = f"{self.BASE_URL}/v2/post/publish/status/fetch/"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        payload = {"publish_id": publish_id}

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            time.sleep(poll_interval)
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=20)
                if resp.status_code != 200:
                    continue

                data = resp.json().get("data", {})
                status = data.get("status")
                fail_reason = data.get("fail_reason", "")

                print(f"[DISPATCH: TikTok] Processing status: {status} (elapsed: {int(time.time() - start_time)}s)...")
                sys.stdout.flush()

                if status in ("SUCCESS", "PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                    return {"status": "success", "publish_id": publish_id}
                elif status in ("FAILED", "FAILED_TO_PROCESS"):
                    raise RuntimeError(f"TikTok publishing failed: {fail_reason or 'Internal processing failure'}")
            except Exception as e:
                if "TikTok publishing failed" in str(e):
                    raise
                continue

        return {
            "status": "processing",
            "publish_id": publish_id,
            "message": "Upload complete. TikTok is processing the video asynchronously in the background."
        }

    def publish(self, video_path, caption, privacy_level=None, post_mode=None, max_wait_sec=60):
        """Full publishing workflow: init -> upload -> poll."""
        if not self.is_configured():
            return {
                "status": "skipped",
                "channel": "tiktok",
                "reason": "Missing TIKTOK_ACCESS_TOKEN in .env"
            }

        mode = post_mode or self.post_mode or "MEDIA_UPLOAD"
        privacy = privacy_level or os.getenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE").strip()

        if mode == "MEDIA_UPLOAD":
            print(f"[DISPATCH: TikTok] Initiating Content Posting API session [Draft/Inbox Mode: MEDIA_UPLOAD]...")
        else:
            print(f"[DISPATCH: TikTok] Initiating Content Posting API session [Direct Post Mode: {privacy}]...")
        sys.stdout.flush()

        try:
            init_res = self.init_video_upload(
                video_path=video_path,
                caption=caption,
                privacy_level=privacy,
                post_mode=mode
            )
        except Exception as e:
            err_str = str(e).lower()
            if any(k in err_str for k in ("401", "unauthorized", "token", "expire", "scope")) and self.refresh_token():
                print("[DISPATCH: TikTok] Retrying video upload with refreshed access token...")
                init_res = self.init_video_upload(
                    video_path=video_path,
                    caption=caption,
                    privacy_level=privacy,
                    post_mode=mode
                )
            else:
                raise

        publish_id = init_res["publish_id"]
        upload_url = init_res["upload_url"]
        chunk_size = init_res["chunk_size"]
        file_size = init_res["file_size"]

        self.upload_chunks(upload_url, video_path, chunk_size, file_size)
        status_res = self.poll_publish_status(publish_id, max_wait_sec=max_wait_sec)

        if mode == "MEDIA_UPLOAD":
            print(f"[DISPATCH: TikTok] SUCCESS: Video uploaded to TikTok Studio Inbox/Drafts! Publish ID: {publish_id}")
            print(f"[DISPATCH: TikTok] -> Notification sent to TikTok app! Open your TikTok inbox/drafts to review and tap Post.")
            success_msg = "Uploaded to TikTok drafts/inbox successfully! Open the TikTok app to review and tap Post."
        else:
            print(f"[DISPATCH: TikTok] SUCCESS: Video published directly to TikTok profile! Publish ID: {publish_id}")
            success_msg = "Published successfully to TikTok!"

        return {
            "status": status_res.get("status", "success"),
            "channel": "tiktok",
            "post_mode": mode,
            "publish_id": publish_id,
            "privacy": privacy if mode != "MEDIA_UPLOAD" else "DRAFT_INBOX",
            "message": status_res.get("message", success_msg)
        }


def publish_via_fallback_aggregator(video_path, caption):
    """
    Alternative / Fallback Social Media Publisher:
    If direct TikTok Developer App review is pending, allows publishing via:
    1. Ayrshare API (AYRSHARE_API_KEY in .env) - enterprise multi-network publisher
    2. Buffer API (BUFFER_ACCESS_TOKEN in .env) - scheduling buffer
    3. Custom Webhook (TIKTOK_WEBHOOK_URL or PUBLISHER_WEBHOOK_URL) - Zapier, Make.com, or n8n
    """
    ayrshare_key = os.getenv("AYRSHARE_API_KEY", "").strip()
    buffer_token = os.getenv("BUFFER_ACCESS_TOKEN", "").strip()
    webhook_url = os.getenv("TIKTOK_WEBHOOK_URL", "").strip() or os.getenv("PUBLISHER_WEBHOOK_URL", "").strip()

    if not requests:
        return None

    # 1. Ayrshare API
    if ayrshare_key:
        print("[DISPATCH: Ayrshare Fallback] Pushing video to TikTok via Ayrshare API...")
        try:
            upload_url = "https://app.ayrshare.com/api/media/upload"
            with open(video_path, "rb") as vf:
                up_resp = requests.post(
                    upload_url,
                    headers={"Authorization": f"Bearer {ayrshare_key}"},
                    files={"file": (os.path.basename(video_path), vf, "video/mp4")},
                    timeout=90
                )
            if up_resp.status_code == 200:
                media_url = up_resp.json().get("url")
                post_url = "https://app.ayrshare.com/api/post"
                post_payload = {
                    "post": caption,
                    "platforms": ["tiktok"],
                    "mediaUrls": [media_url]
                }
                post_resp = requests.post(
                    post_url,
                    headers={"Authorization": f"Bearer {ayrshare_key}", "Content-Type": "application/json"},
                    json=post_payload,
                    timeout=30
                )
                if post_resp.status_code in (200, 201):
                    data = post_resp.json()
                    print(f"[DISPATCH: Ayrshare] SUCCESS: Pushed to TikTok! Post ID: {data.get('id')}")
                    return {"status": "success", "channel": "tiktok_ayrshare", "post_id": data.get("id")}
        except Exception as e:
            print(f"[DISPATCH: Ayrshare] Error: {e}")

    # 2. Buffer API
    if buffer_token:
        print("[DISPATCH: Buffer Fallback] Sending post to Buffer queue...")
        try:
            profile_id = os.getenv("BUFFER_PROFILE_ID", "").strip()
            url = "https://api.bufferapp.com/1/updates/create.json"
            data = {
                "access_token": buffer_token,
                "profile_ids[]": profile_id,
                "text": caption,
                "now": True
            }
            resp = requests.post(url, data=data, timeout=30)
            if resp.status_code == 200:
                print("[DISPATCH: Buffer] SUCCESS: Queued in Buffer!")
                return {"status": "success", "channel": "tiktok_buffer", "data": resp.json()}
        except Exception as e:
            print(f"[DISPATCH: Buffer] Error: {e}")

    # 3. Automation Webhook (Make / Zapier / n8n)
    if webhook_url:
        print(f"[DISPATCH: Webhook Fallback] Pushing video to automation webhook: {webhook_url}...")
        try:
            with open(video_path, "rb") as vf:
                files = {"video": (os.path.basename(video_path), vf, "video/mp4")}
                data = {"caption": caption, "platform": "tiktok", "title": caption[:100]}
                resp = requests.post(webhook_url, data=data, files=files, timeout=90)
            if resp.status_code in (200, 201, 202):
                print("[DISPATCH: Webhook] SUCCESS: Received by automation webhook!")
                return {"status": "success", "channel": "tiktok_webhook"}
        except Exception as e:
            print(f"[DISPATCH: Webhook] Error: {e}")

    return None


def publish_to_tiktok(video_path, caption, access_token=None, privacy="PUBLIC_TO_EVERYONE", post_mode=None, is_test=False):
    """
    TikTok Content Posting API (v2) Integration with Fallback Support.
    Workflow:
      1. If test mode, reports configuration readiness and active post mode (MEDIA_UPLOAD / DIRECT_POST).
      2. If TIKTOK_ACCESS_TOKEN is configured, executes chunked upload to drafts (MEDIA_UPLOAD) or feed (DIRECT_POST).
      3. If direct token is absent, attempts configured fallback aggregator (Ayrshare, Buffer, Webhook).
      4. If no credentials are found, returns skipped status.
    """
    token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    mode = post_mode or os.getenv("TIKTOK_POST_MODE", "MEDIA_UPLOAD").strip()

    if is_test:
        mode_desc = "Draft/Inbox Mode (MEDIA_UPLOAD)" if mode == "MEDIA_UPLOAD" else f"Direct Post Mode ({mode})"
        print(f"[DISPATCH: TikTok] (Test Mode) TikTok Content Posting API v2 ready [{mode_desc}].")
        return {"status": "test_ok", "channel": "tiktok", "post_mode": mode}

    direct_err = None

    # 1. Official Direct Content Posting API
    if token:
        publisher = TikTokPublisher(access_token=token, post_mode=mode)
        try:
            return publisher.publish(video_path, caption, privacy_level=privacy, post_mode=mode)
        except Exception as e:
            direct_err = str(e)
            print(f"[DISPATCH: TikTok] Direct upload notice: {e}")
            print("                   Checking fallback aggregators...")

    # 2. Fallback Aggregator (Ayrshare, Buffer, Webhook)
    fallback_res = publish_via_fallback_aggregator(video_path, caption)
    if fallback_res:
        return fallback_res

    # 3. Final status report
    if direct_err:
        return {
            "status": "failed",
            "channel": "tiktok",
            "post_mode": mode,
            "reason": f"Direct upload failed: {direct_err}"
        }

    print("[DISPATCH: TikTok] Notice: TIKTOK_ACCESS_TOKEN (or fallback keys) not set in .env.")
    print("                   Video and metadata are saved locally and ready for manual dispatch.")
    return {
        "status": "skipped",
        "channel": "tiktok",
        "post_mode": mode,
        "reason": "Missing TIKTOK_ACCESS_TOKEN in .env (or AYRSHARE_API_KEY / BUFFER_ACCESS_TOKEN / TIKTOK_WEBHOOK_URL)"
    }


# ----------------------------------------------------------------------
# 5. PUBLIC MEDIA HOSTING SERVICE (FOR INSTAGRAM REELS INGESTION)
# ----------------------------------------------------------------------
class MediaHostingService:
    """
    Manages public video hosting so Meta Graph API (Instagram Reels) can ingest the video stream.
    Hierarchy:
      1. S3 / Cloudflare R2 / Custom Bucket:
         - Uses boto3 if installed and S3_BUCKET_NAME / AWS_ACCESS_KEY_ID configured in .env.
         - Supports custom endpoint (e.g. Cloudflare R2: S3_ENDPOINT_URL).
         - Returns public URL (e.g. S3_PUBLIC_BASE_URL or S3 bucket URL).
      2. Custom Public Host:
         - Uses PUBLIC_MEDIA_URL_BASE if provided in .env.
      3. Zero-setup Public Temporary Hosting:
         - Uploads directly via Catbox (https://catbox.moe/user/api.php), returns direct video/mp4 stream URL.
    """
    @staticmethod
    def upload_video(video_path):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        file_size = os.path.getsize(video_path)
        base_name = os.path.basename(video_path)
        unique_name = f"{int(time.time())}_{base_name}"

        # 1. Check AWS S3 / Cloudflare R2
        s3_bucket = os.getenv("S3_BUCKET_NAME", "").strip() or os.getenv("AWS_S3_BUCKET", "").strip()
        aws_key = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
        aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
        s3_region = os.getenv("AWS_REGION", "us-east-1").strip()
        s3_endpoint = os.getenv("S3_ENDPOINT_URL", "").strip()
        s3_public_base = os.getenv("S3_PUBLIC_BASE_URL", "").strip()

        if s3_bucket and aws_key and aws_secret:
            try:
                import boto3
            except ImportError:
                boto3 = None

            if boto3 is not None:
                try:
                    print(f"[HOSTING] Uploading video ({file_size / (1024*1024):.1f}MB) to S3 bucket '{s3_bucket}'...")
                    s3_kwargs = {
                        "aws_access_key_id": aws_key,
                        "aws_secret_access_key": aws_secret,
                        "region_name": s3_region,
                    }
                    if s3_endpoint:
                        s3_kwargs["endpoint_url"] = s3_endpoint
                    s3_client = boto3.client("s3", **s3_kwargs)
                    s3_client.upload_file(
                        video_path,
                        s3_bucket,
                        unique_name,
                        ExtraArgs={"ContentType": "video/mp4"}
                    )
                    if s3_public_base:
                        public_url = f"{s3_public_base.rstrip('/')}/{unique_name}"
                    elif s3_endpoint and "r2.cloudflarestorage.com" in s3_endpoint:
                        public_url = f"https://{s3_bucket}.r2.dev/{unique_name}"
                    else:
                        public_url = f"https://{s3_bucket}.s3.{s3_region}.amazonaws.com/{unique_name}"
                    print(f"[HOSTING] S3 upload successful! Public URL: {public_url}")
                    return public_url
                except Exception as e:
                    print(f"[HOSTING] S3 upload notice ({e}). Falling back to temporary host...")
            else:
                print("[HOSTING] Notice: S3 credentials present but 'boto3' is not installed. Falling back to temporary host...")

        # 2. Check Custom Public URL Base or Tunnel
        public_url_base = os.getenv("PUBLIC_MEDIA_URL_BASE", "").strip() or os.getenv("NGROK_TUNNEL_URL", "").strip()
        if public_url_base:
            public_url = f"{public_url_base.rstrip('/')}/{base_name}"
            print(f"[HOSTING] Using configured custom media URL: {public_url}")
            return public_url

        # 3. Zero-setup Temporary Hosting with Multi-Host Fallback & Stream Integrity Verification
        # Verified fast stream hosts: Uguu.se (Primary, proven HTTP 206 support) | Catbox.moe (Fallback)
        def _verify_stream_integrity(stream_url, min_bytes):
            try:
                r = requests.get(
                    stream_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Range": "bytes=0-10"},
                    stream=True,
                    timeout=10
                )
                if r.status_code in (200, 206):
                    cr = r.headers.get("Content-Range", "")
                    if "/" in cr:
                        total = int(cr.split("/")[-1])
                        return total >= min_bytes
                    cl = r.headers.get("Content-Length", "")
                    if r.status_code == 200 and cl and cl.isdigit():
                        return int(cl) >= min_bytes
                    return True
            except Exception:
                pass
            return False

        min_expected_bytes = int(file_size * 0.8)
        errors = []

        # Attempt A: Uguu.se (High-speed temporary direct host, zero buffering, verified with Meta Reels)
        print(f"[HOSTING] Uploading video ({file_size / (1024*1024):.1f}MB) to public stream host (Uguu.se)...")
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            with open(video_path, "rb") as vf:
                resp = requests.post(
                    "https://uguu.se/upload.php",
                    headers=headers,
                    files={"files[]": (unique_name, vf, "video/mp4")},
                    timeout=120
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("files"):
                    uguu_url = data["files"][0].get("url", "").strip()
                    if uguu_url.startswith("http") and _verify_stream_integrity(uguu_url, min_expected_bytes):
                        print(f"[HOSTING] Stream URL verified & ready (Uguu): {uguu_url}")
                        return uguu_url
                    else:
                        errors.append(f"Uguu URL failed integrity check: {uguu_url}")
            else:
                errors.append(f"Uguu HTTP {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"[HOSTING] Uguu upload notice ({e}). Trying fallback host...")
            errors.append(f"Uguu: {e}")

        # Attempt B: Catbox.moe
        print(f"[HOSTING] Uploading video ({file_size / (1024*1024):.1f}MB) to fallback host (Catbox.moe)...")
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            with open(video_path, "rb") as vf:
                resp = requests.post(
                    "https://catbox.moe/user/api.php",
                    headers=headers,
                    data={"reqtype": "fileupload"},
                    files={"fileToUpload": (unique_name, vf, "video/mp4")},
                    timeout=120
                )
            catbox_url = resp.text.strip()
            if resp.status_code == 200 and (catbox_url.startswith("http://") or catbox_url.startswith("https://")):
                if _verify_stream_integrity(catbox_url, min_expected_bytes):
                    print(f"[HOSTING] Stream URL verified & ready (Catbox): {catbox_url}")
                    return catbox_url
                else:
                    err_detail = f"Catbox returned truncated/stale cached file ({catbox_url})"
                    print(f"[HOSTING] Notice: {err_detail}.")
                    errors.append(err_detail)
            else:
                err_detail = f"Catbox HTTP {resp.status_code}: {catbox_url[:100]}"
                errors.append(err_detail)
        except Exception as e:
            errors.append(f"Catbox: {e}")

        raise RuntimeError(f"Could not host video publicly for Meta Graph API. All hosting providers failed: {'; '.join(errors)}")


# ----------------------------------------------------------------------
# 6. INSTAGRAM REELS (META GRAPH API v20.0) & TOKEN LIFECYCLE MANAGEMENT
# ----------------------------------------------------------------------

def update_env_variable(key, value, env_file=None):
    """Safely updates or appends a key in .env and updates os.environ."""
    if env_file is None:
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

    os.environ[key] = str(value)

    # Attempt dotenv set_key first
    try:
        from dotenv import set_key
        set_key(env_file, key, str(value), quote_mode="never")
        return True
    except Exception:
        pass

    # Safe text rewrite fallback
    try:
        lines = []
        found = False
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

        new_lines = []
        for line in lines:
            if line.strip().startswith(f"{key}="):
                new_lines.append(f"{key}={value}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"{key}={value}\n")

        with open(env_file, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except Exception as e:
        print(f"[!] Warning: Could not write {key} to {env_file}: {e}")
        return False


def check_instagram_token_health(access_token=None, app_id=None, app_secret=None):
    """
    Queries Meta Graph API /debug_token to inspect token validity, scopes,
    token type, and exact expiration timestamp.
    """
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    app_id = app_id or os.getenv("META_APP_ID", "").strip()
    app_secret = app_secret or os.getenv("META_APP_SECRET", "").strip()

    if not token:
        return {
            "is_valid": False,
            "error": "No INSTAGRAM_ACCESS_TOKEN found in environment",
            "never_expires": False,
            "days_remaining": 0.0,
            "scopes": [],
            "token_type": "NONE"
        }

    if not app_id or not app_secret:
        return {
            "is_valid": False,
            "error": "Missing META_APP_ID or META_APP_SECRET for debug_token check",
            "never_expires": False,
            "days_remaining": 0.0,
            "scopes": [],
            "token_type": "UNKNOWN"
        }

    url = "https://graph.facebook.com/debug_token"
    params = {
        "input_token": token,
        "access_token": f"{app_id}|{app_secret}"
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        d = resp.json()
    except Exception as e:
        return {
            "is_valid": False,
            "error": f"Network error during debug_token check: {e}",
            "never_expires": False,
            "days_remaining": 0.0,
            "scopes": [],
            "token_type": "UNKNOWN"
        }

    if "error" in d:
        err = d["error"]
        return {
            "is_valid": False,
            "error": err.get("message", "Unknown Meta error"),
            "code": err.get("code"),
            "never_expires": False,
            "days_remaining": 0.0,
            "scopes": [],
            "token_type": "UNKNOWN"
        }

    data = d.get("data", {})
    is_valid = bool(data.get("is_valid", False))
    token_type = data.get("type", "UNKNOWN")
    expires_at = int(data.get("expires_at", 0))
    issued_at = int(data.get("issued_at", 0))
    app_name = data.get("application", "")
    scopes = data.get("scopes", [])
    user_id = data.get("user_id", "")

    # expires_at == 0 indicates a permanent token (Page Token / System User Token)
    never_expires = (expires_at == 0)
    if never_expires:
        days_remaining = float("inf")
    else:
        now_ts = time.time()
        days_remaining = max(0.0, (expires_at - now_ts) / 86400.0)

    has_required_scopes = bool("instagram_content_publish" in scopes and "instagram_basic" in scopes)

    err_msg = None
    if not is_valid:
        err_msg = data.get("error", {}).get("message", "Token is marked invalid by Meta")

    return {
        "is_valid": is_valid,
        "token_type": token_type,
        "expires_at": expires_at,
        "issued_at": issued_at,
        "never_expires": never_expires,
        "days_remaining": days_remaining,
        "scopes": scopes,
        "has_required_scopes": has_required_scopes,
        "app_name": app_name,
        "app_id": app_id,
        "user_id": user_id,
        "error": err_msg,
        "raw_data": data
    }


def refresh_instagram_token(access_token=None, app_id=None, app_secret=None, graph_version=None, target_account_id=None, env_file=None):
    """
    Exchanges an existing token for a fresh long-lived token via Meta Graph API:
    1. Calls GET /oauth/access_token with grant_type=fb_exchange_token.
    2. If a connected Facebook Page with Instagram Business Account is available via /me/accounts,
       captures the permanent Page access token.
    3. Saves the refreshed token to .env and updates os.environ.
    4. Updates instagram_token.json if present.
    """
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    app_id = app_id or os.getenv("META_APP_ID", "").strip()
    app_secret = app_secret or os.getenv("META_APP_SECRET", "").strip()
    graph_version = graph_version or os.getenv("META_GRAPH_VERSION", "v20.0").strip()
    target_id = target_account_id or os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()

    if not token:
        raise ValueError("Cannot refresh: INSTAGRAM_ACCESS_TOKEN is missing.")
    if not app_id or not app_secret:
        raise ValueError("Cannot refresh: META_APP_ID or META_APP_SECRET is missing in .env.")

    # 1. Meta OAuth long-lived token exchange
    url = f"https://graph.facebook.com/{graph_version}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": token
    }

    resp = requests.get(url, params=params, timeout=30)
    data = resp.json()

    if "error" in data:
        err = data["error"]
        msg = err.get("message", "Unknown Meta error")
        raise RuntimeError(f"Meta token exchange (fb_exchange_token) failed: {msg}")

    new_token = data.get("access_token")
    if not new_token:
        raise RuntimeError(f"Meta returned no access_token: {data}")

    expires_in = data.get("expires_in")
    token_type = data.get("token_type", "bearer")

    # 2. Check /me/accounts for permanent Page Token
    try:
        acc_url = f"https://graph.facebook.com/{graph_version}/me/accounts"
        acc_params = {
            "fields": "name,id,access_token,instagram_business_account{id,username,name}",
            "access_token": new_token
        }
        acc_resp = requests.get(acc_url, params=acc_params, timeout=20)
        acc_data = acc_resp.json()
        pages = acc_data.get("data", [])

        if pages:
            chosen_page = None
            if target_id:
                for p in pages:
                    ig_acc = p.get("instagram_business_account") or {}
                    if str(ig_acc.get("id")) == str(target_id):
                        chosen_page = p
                        break
            if not chosen_page:
                for p in pages:
                    if p.get("instagram_business_account"):
                        chosen_page = p
                        break
            if chosen_page and chosen_page.get("access_token"):
                new_token = chosen_page["access_token"]
                token_type = "PAGE"
                print(f"[AUTH: Instagram] Captured permanent Page Access Token from Page '{chosen_page.get('name')}'.")
    except Exception:
        pass

    # 3. Update .env
    update_env_variable("INSTAGRAM_ACCESS_TOKEN", new_token, env_file=env_file)

    # 4. Update instagram_token.json if exists
    token_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instagram_token.json")
    if os.path.exists(token_json_path):
        try:
            with open(token_json_path, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            tdata["page_access_token"] = new_token
            tdata["obtained_at"] = int(time.time())
            with open(token_json_path, "w", encoding="utf-8") as f:
                json.dump(tdata, f, indent=2)
        except Exception:
            pass

    return new_token, token_type, expires_in


def ensure_instagram_token(access_token=None, app_id=None, app_secret=None, refresh_threshold_days=7.0):
    """
    Diagnoses token health and automatically triggers renewal if the token
    is expiring within `refresh_threshold_days` or invalid.
    """
    health = check_instagram_token_health(access_token=access_token, app_id=app_id, app_secret=app_secret)

    if health.get("never_expires"):
        exp_desc = "Never Expires (Permanent Token)"
    elif health.get("expires_at"):
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(health["expires_at"], tz=timezone.utc)
        exp_desc = f"{health['days_remaining']:.1f} days remaining (Expires: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')})"
    else:
        exp_desc = "Unknown"

    status_str = "VALID" if health.get("is_valid") else "INVALID"
    print(f"[AUTH: Instagram] Token health check: {status_str} [Type: {health.get('token_type', 'UNKNOWN')}, Lifespan: {exp_desc}]")

    needs_refresh = False
    if not health.get("is_valid"):
        print(f"[AUTH: Instagram] Token is marked invalid ({health.get('error', 'Unknown error')}). Attempting emergency renewal...")
        needs_refresh = True
    elif not health.get("never_expires") and health.get("days_remaining", 0) < refresh_threshold_days:
        print(f"[AUTH: Instagram] Token expiring in {health.get('days_remaining', 0):.1f} days (< {refresh_threshold_days} days). Auto-refreshing long-lived token...")
        needs_refresh = True

    if needs_refresh:
        try:
            new_token, t_type, _ = refresh_instagram_token(
                access_token=access_token,
                app_id=app_id,
                app_secret=app_secret
            )
            print(f"[AUTH: Instagram] SUCCESS: Token refreshed and updated in .env and memory.")
            return new_token
        except Exception as e:
            print(f"[AUTH: Instagram] Warning: Token refresh attempt failed: {e}")

    return access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()


class InstagramReelsPublisher:
    """
    Official Meta Graph API (v20.0) Instagram Reels Publisher.
    Workflow:
      0. Token Health & Refresh: Inspects token lifespan and automatically renews expiring tokens.
      1. Uploads video to a public hosting endpoint (S3, Cloudflare R2, or temporary host) so Meta can fetch the MP4 stream.
      2. Calls POST /v20.0/{account_id}/media with media_type=REELS, video_url, caption, share_to_feed=true to create a media container.
      3. Polls GET /v20.0/{container_id}?fields=status_code,status until status_code == 'FINISHED'.
      4. Calls POST /v20.0/{account_id}/media_publish with creation_id={container_id} to publish the Reel.
      5. Fetches the live Reel permalink.
    """
    BASE_URL = "https://graph.facebook.com"

    def __init__(self, access_token=None, account_id=None, graph_version=None, app_id=None, app_secret=None):
        self.access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
        self.account_id = account_id or os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
        self.graph_version = graph_version or os.getenv("META_GRAPH_VERSION", "v20.0").strip()
        self.app_id = app_id or os.getenv("META_APP_ID", "").strip()
        self.app_secret = app_secret or os.getenv("META_APP_SECRET", "").strip()

        # Check for cached token file if not in .env
        if (not self.access_token or not self.account_id) and os.path.exists("instagram_token.json"):
            try:
                with open("instagram_token.json", "r", encoding="utf-8") as f:
                    tdata = json.load(f)
                    self.access_token = self.access_token or tdata.get("page_access_token", "").strip()
                    self.account_id = self.account_id or tdata.get("instagram_account_id", "").strip()
            except Exception:
                pass

    def is_configured(self):
        return bool(self.access_token and self.account_id)

    def check_token_health(self):
        """Diagnoses token health via Meta debug_token."""
        return check_instagram_token_health(
            access_token=self.access_token,
            app_id=self.app_id,
            app_secret=self.app_secret
        )

    def refresh_token(self):
        """Exchanges current token for renewed long-lived token."""
        new_token, token_type, expires_in = refresh_instagram_token(
            access_token=self.access_token,
            app_id=self.app_id,
            app_secret=self.app_secret,
            graph_version=self.graph_version,
            target_account_id=self.account_id
        )
        self.access_token = new_token
        return new_token

    def ensure_token_health(self, refresh_threshold_days=7.0):
        """Checks and refreshes token before publishing jobs."""
        new_token = ensure_instagram_token(
            access_token=self.access_token,
            app_id=self.app_id,
            app_secret=self.app_secret,
            refresh_threshold_days=refresh_threshold_days
        )
        if new_token:
            self.access_token = new_token
        return self.access_token

    def create_reel_container(self, video_url, caption, share_to_feed=True):
        """Initializes a Reel container on Instagram via Meta Graph API."""
        url = f"{self.BASE_URL}/{self.graph_version}/{self.account_id}/media"
        clean_caption = caption[:2200] if len(caption) > 2200 else caption

        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": clean_caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": self.access_token
        }

        resp = requests.post(url, data=payload, timeout=45)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            msg = err.get("message", "Unknown error")
            code = err.get("code")
            subcode = err.get("error_subcode", "")
            fbtrace = err.get("fbtrace_id", "")
            raise RuntimeError(f"Meta Graph API container creation failed [{code}:{subcode}]: {msg} (trace: {fbtrace})")

        container_id = data.get("id")
        if not container_id:
            raise RuntimeError(f"No container ID returned by Meta: {data}")

        return container_id

    def poll_container_status(self, container_id, max_wait_sec=180, poll_interval=5):
        """Polls GET /{container_id} until status_code is 'FINISHED'."""
        url = f"{self.BASE_URL}/{self.graph_version}/{container_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.access_token
        }

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            time.sleep(poll_interval)
            try:
                resp = requests.get(url, params=params, timeout=20)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                status_code = data.get("status_code", "").upper()
                status_desc = data.get("status", "")
                elapsed = int(time.time() - start_time)

                print(f"[DISPATCH: Instagram] Container processing: {status_code or status_desc} ({elapsed}s elapsed)...")
                sys.stdout.flush()

                if status_code == "FINISHED":
                    return True
                elif status_code in ("ERROR", "EXPIRED"):
                    raise RuntimeError(f"Instagram video processing failed [{status_code}]: {status_desc}")
            except Exception as e:
                if "Instagram video processing failed" in str(e):
                    raise
                continue

        raise TimeoutError(f"Instagram media container {container_id} processing timed out after {max_wait_sec}s.")

    def publish_container(self, container_id):
        """Publishes the finalized container live to the Instagram profile."""
        url = f"{self.BASE_URL}/{self.graph_version}/{self.account_id}/media_publish"
        payload = {
            "creation_id": container_id,
            "access_token": self.access_token
        }

        resp = requests.post(url, data=payload, timeout=45)
        data = resp.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Meta Graph API media_publish failed: {err.get('message')}")

        media_id = data.get("id")
        return media_id

    def get_media_permalink(self, media_id):
        """Fetches the live public permalink of the published Reel."""
        url = f"{self.BASE_URL}/{self.graph_version}/{media_id}"
        params = {
            "fields": "permalink,id",
            "access_token": self.access_token
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json().get("permalink", "")
        except Exception:
            pass
        return f"https://www.instagram.com/p/{media_id}/"

    def publish(self, video_path, caption, share_to_feed=True, max_wait_sec=180):
        """Full publishing workflow: host video -> create container -> poll -> publish."""
        if not self.is_configured():
            return {
                "status": "skipped",
                "channel": "instagram",
                "reason": "Missing INSTAGRAM_ACCOUNT_ID or INSTAGRAM_ACCESS_TOKEN in .env"
            }

        # Step 0: Token Health & Automated Expiration Management
        try:
            self.ensure_token_health(refresh_threshold_days=7.0)
        except Exception as te:
            print(f"[AUTH: Instagram] Token health check notice: {te}")

        print(f"[DISPATCH: Instagram] Starting Meta Graph API Reels publishing (Account: {self.account_id})...")
        sys.stdout.flush()

        try:
            # Step 1: Upload to public host
            video_url = MediaHostingService.upload_video(video_path)

            # Step 2: Create media container
            print(f"[DISPATCH: Instagram] Initializing Reels container on Meta Graph API ({self.graph_version})...")
            container_id = self.create_reel_container(video_url, caption, share_to_feed=share_to_feed)
            print(f"[DISPATCH: Instagram] Media container registered: {container_id}. Waiting for Meta transcoding...")
            sys.stdout.flush()

            # Step 3: Poll status
            self.poll_container_status(container_id, max_wait_sec=max_wait_sec)

            # Step 4: Publish
            print(f"[DISPATCH: Instagram] Transcoding finished! Publishing container {container_id} live...")
            media_id = self.publish_container(container_id)

            # Step 5: Get permalink
            permalink = self.get_media_permalink(media_id)

            print(f"[DISPATCH: Instagram] SUCCESS: Instagram Reel published live!")
            print(f"[DISPATCH: Instagram] * Media ID : {media_id}")
            if permalink:
                print(f"[DISPATCH: Instagram] * Link     : {permalink}")

            return {
                "status": "success",
                "channel": "instagram",
                "media_id": media_id,
                "permalink": permalink,
                "message": "Reel published successfully to Instagram!"
            }
        except Exception as e:
            print(f"[DISPATCH: Instagram] Error during Reels publishing: {e}")
            return {
                "status": "failed",
                "channel": "instagram",
                "reason": str(e)
            }


def publish_to_instagram_reels(video_path, caption, access_token=None, account_id=None, is_test=False):
    """
    Instagram Reels (Meta Graph API) Integration with Auto-Hosting.
    Workflow:
      1. If test mode, reports configuration readiness.
      2. If configured, hosts video and completes two-step container publish.
      3. If credentials missing, returns skipped status.
    """
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    acc_id = account_id or os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()

    if is_test:
        configured = bool(token and acc_id)
        config_desc = f"Configured (Account: {acc_id})" if configured else "Stub Ready (Set INSTAGRAM_ACCESS_TOKEN & INSTAGRAM_ACCOUNT_ID to publish live)"
        print(f"[DISPATCH: Instagram] (Test Mode) Meta Graph API Reels publisher ready [{config_desc}].")
        if configured:
            try:
                ensure_instagram_token(access_token=token, refresh_threshold_days=7.0)
            except Exception as te:
                print(f"[AUTH: Instagram] (Test Mode) Token diagnostic notice: {te}")
        return {"status": "test_ok", "channel": "instagram", "configured": configured}

    if not token or not acc_id:
        print("[DISPATCH: Instagram] Notice: INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID not set in .env.")
        print("                      Video and metadata are saved locally and ready for manual dispatch.")
        return {
            "status": "skipped",
            "channel": "instagram",
            "reason": "Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID in .env"
        }

    try:
        publisher = InstagramReelsPublisher(access_token=token, account_id=acc_id)
        return publisher.publish(video_path, caption)
    except Exception as e:
        print(f"[DISPATCH: Instagram] Failed to initialize/publish Reel: {e}")
        return {
            "status": "failed",
            "channel": "instagram",
            "reason": str(e)
        }

# ----------------------------------------------------------------------
# 7. MASTER DISPATCH CONTROLLER
# ----------------------------------------------------------------------
def dispatch_video(video_path, metadata, is_test=False, enable_youtube=True, enable_tiktok=True, enable_instagram=True, youtube_privacy="public"):
    """
    Dispatches the finalized video and metadata across all configured channels simultaneously:
    - Primary: Telegram Bot (Safe mobile delivery)
    - Optional: Discord Webhook
    - Social Media:
        1. YouTube Shorts (Direct OAuth API)
        2. TikTok Video / Drafts (Content Posting API)
        3. Instagram Reels (Meta Graph API)
    """
    tiktok_mode = os.getenv("TIKTOK_POST_MODE", "MEDIA_UPLOAD").strip()
    tiktok_label = f"ENABLED ({'Draft/Inbox Mode' if tiktok_mode == 'MEDIA_UPLOAD' else 'Direct Post'})" if enable_tiktok else "DISABLED"

    yt_privacy = youtube_privacy or os.getenv("YOUTUBE_PRIVACY_STATUS", "public")
    yt_label = f"ENABLED ({yt_privacy.upper()})" if enable_youtube else "DISABLED"

    print("\n" + "=" * 70)
    print(" [DISPATCHER] INITIATING SOCIAL MEDIA DISPATCH")
    print("=" * 70)
    print(f" * Video Target  : {os.path.abspath(video_path)}")
    print(f" * Title         : {metadata.get('primary_title')}")
    print(f" * Test Mode     : {is_test}")
    print(f" * YouTube Shorts: {yt_label}")
    print(f" * TikTok Video  : {tiktok_label}")
    print(f" * Instagram Reel: {'ENABLED' if enable_instagram else 'DISABLED'}")
    print("-" * 70)

    results = {}

    # Extract platform-specific copywriting generated by metadata_engine
    yt_meta = metadata.get("youtube", {})
    ig_meta = metadata.get("instagram", {})
    tt_meta = metadata.get("tiktok", {})

    title = yt_meta.get("title") or metadata.get("primary_title", "Horse Havoc Race Highlights")
    desc = yt_meta.get("description") or metadata.get("description", "")
    tags = metadata.get("tags_string", "#Shorts #HorseHavoc")
    yt_tags = yt_meta.get("tags") or metadata.get("hashtags", ["Horse Havoc", "Shorts", "Gaming"])

    # 1. Telegram (Primary)
    try:
        results["telegram"] = send_telegram_video(
            video_path=video_path,
            title=title,
            description=desc,
            tags=tags,
            is_test=is_test
        )
    except Exception as e:
        print(f"[DISPATCH: Telegram] Notice/Error: {e}")
        results["telegram"] = {"status": "failed", "channel": "telegram", "reason": str(e)}

    # 2. Discord Webhook (Optional)
    try:
        results["discord"] = send_discord_webhook(
            video_path=video_path,
            title=title,
            tags=tags,
            is_test=is_test
        )
    except Exception as e:
        print(f"[DISPATCH: Discord] Notice/Error: {e}")
        results["discord"] = {"status": "failed", "channel": "discord", "reason": str(e)}

    # 3. YouTube Shorts Publishing (Dynamic Catchy Title, Engaging Story, Fixed Callouts, Tags)
    if enable_youtube:
        try:
            results["youtube"] = publish_to_youtube(video_path, title, desc, yt_tags, privacy=yt_privacy, is_test=is_test)
        except Exception as e:
            print(f"[DISPATCH: YouTube] Notice/Error: {e}")
            results["youtube"] = {"status": "failed", "channel": "youtube", "reason": str(e)}
    else:
        results["youtube"] = {"status": "skipped", "channel": "youtube", "reason": "Disabled via flag"}

    # 4. TikTok Video Publishing (Punchy Match Climax Hook & FYP Hashtags)
    if enable_tiktok:
        try:
            tiktok_caption = tt_meta.get("caption") or f"{title}\n\n{tags}"
            results["tiktok"] = publish_to_tiktok(video_path, tiktok_caption, post_mode=tiktok_mode, is_test=is_test)
        except Exception as e:
            print(f"[DISPATCH: TikTok] Notice/Error: {e}")
            results["tiktok"] = {"status": "failed", "channel": "tiktok", "reason": str(e)}
    else:
        results["tiktok"] = {"status": "skipped", "channel": "tiktok", "reason": "Disabled via flag"}

    # 5. Instagram Reels Publishing (Interactive Event Story, Follow Callout, Clean Hashtags)
    if enable_instagram:
        try:
            ig_caption = ig_meta.get("caption") or f"{title}\n\n{desc}\n\n{tags}"
            results["instagram"] = publish_to_instagram_reels(video_path, ig_caption, is_test=is_test)
        except Exception as e:
            print(f"[DISPATCH: Instagram] Notice/Error: {e}")
            results["instagram"] = {"status": "failed", "channel": "instagram", "reason": str(e)}
    else:
        results["instagram"] = {"status": "skipped", "channel": "instagram", "reason": "Disabled via flag"}

    print("-" * 70)
    print(" [DISPATCH SUMMARY]")
    for ch, res in results.items():
        status_label = res.get("status", "unknown").upper()
        reason = f" ({res.get('reason')})" if res.get("reason") else ""
        print(f"  * {ch.capitalize():<12} : {status_label}{reason}")
    print("=" * 70)

    # Automatic Retention & Disk Cleanup Policy (Enforce 24h limit on old videos)
    try:
        import cleanup_manager
        cleanup_manager.run_retention_policy(max_age_hours=24.0)
    except Exception as ce:
        print(f"[CLEANUP NOTICE] Dispatcher post-upload cleanup notice: {ce}")

    return results

if __name__ == "__main__":
    import argparse

    def parse_platform_flag(val, explicit_no):
        if explicit_no:
            return False
        if val is None:
            return None
        if isinstance(val, bool):
            return val
        s = str(val).lower().strip()
        if s in ("false", "0", "no", "disable", "disabled"):
            return False
        return True

    def resolve_platforms(arg_all, raw_yt, no_yt, raw_tt, no_tt, raw_ig, no_ig):
        yt = parse_platform_flag(raw_yt, no_yt)
        tt = parse_platform_flag(raw_tt, no_tt)
        ig = parse_platform_flag(raw_ig, no_ig)

        has_positive = any(x is True for x in [yt, tt, ig])

        if arg_all:
            enable_yt = (yt is not False)
            enable_tt = (tt is not False)
            enable_ig = (ig is not False)
        elif has_positive:
            enable_yt = (yt is True)
            enable_tt = (tt is True)
            enable_ig = (ig is True)
        else:
            enable_yt = (yt is not False)
            enable_tt = (tt is not False)
            enable_ig = (ig is not False)

        return enable_yt, enable_tt, enable_ig

    parser = argparse.ArgumentParser(description="HORSE HAVOC Publisher & OAuth Tool")
    parser.add_argument("-v", "--video", default="final_short.mp4", help="Path to video file")
    parser.add_argument("--test", action="store_true", help="Run in test mode without live publishing")
    parser.add_argument("--auth-youtube", action="store_true", help="Trigger one-time OAuth2 local server consent flow for YouTube")
    parser.add_argument("--auth-tiktok", action="store_true", help="Trigger one-time OAuth2 local server consent flow for TikTok")
    parser.add_argument("--auth-instagram", action="store_true", help="Trigger one-time OAuth2 local server consent flow for Instagram Reels")
    parser.add_argument("--refresh-instagram", action="store_true", help="Diagnose and auto-refresh Instagram Reels Meta access token")
    parser.add_argument("--secrets", default="client_secrets.json", help="Path to client_secrets.json (default: client_secrets.json)")
    parser.add_argument("--token", default="token.json", help="Path to save token.json (default: token.json)")
    parser.add_argument("--tiktok-mode", choices=["MEDIA_UPLOAD", "DIRECT_POST"], default=None, help="TikTok post mode: MEDIA_UPLOAD (drafts/inbox) or DIRECT_POST")

    # Platform toggles
    parser.add_argument("--all", action="store_true", help="Publish to all platforms (YouTube, TikTok, Instagram)")
    parser.add_argument("--youtube", nargs="?", const=True, default=None, help="Enable YouTube Shorts publishing (or --youtube=false)")
    parser.add_argument("--no-youtube", action="store_true", help="Explicitly disable YouTube Shorts")
    parser.add_argument("--tiktok", nargs="?", const=True, default=None, help="Enable TikTok publishing (or --tiktok=false)")
    parser.add_argument("--no-tiktok", action="store_true", help="Explicitly disable TikTok")
    parser.add_argument("--instagram", nargs="?", const=True, default=None, help="Enable Instagram Reels publishing (or --instagram=false)")
    parser.add_argument("--no-instagram", action="store_true", help="Explicitly disable Instagram Reels")

    # YouTube Privacy Controls
    default_yt_privacy = os.getenv("YOUTUBE_PRIVACY_STATUS", "public").strip().lower()
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default=default_yt_privacy, help="YouTube Shorts privacy status: public, unlisted, private (default: public)")
    parser.add_argument("--public", dest="privacy", action="store_const", const="public", help="Force public YouTube video privacy (default)")
    parser.add_argument("--unlisted", dest="privacy", action="store_const", const="unlisted", help="Set YouTube video privacy to unlisted")

    args = parser.parse_args()

    if args.auth_youtube:
        authenticate_youtube(secrets_file=args.secrets, token_file=args.token)
    elif args.auth_tiktok:
        from auth_tiktok import run_oauth_flow
        run_oauth_flow(
            client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
            client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
            redirect_uri=os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8080/callback/"),
            scopes="user.info.basic,video.upload"
        )
    elif args.auth_instagram:
        from auth_instagram import run_instagram_auth_flow
        run_instagram_auth_flow(
            app_id=os.getenv("META_APP_ID", ""),
            app_secret=os.getenv("META_APP_SECRET", ""),
            redirect_uri=os.getenv("META_REDIRECT_URI", "http://localhost:8080/callback/")
        )
    elif args.refresh_instagram:
        from refresh_instagram_token import diagnose_and_refresh_token
        diagnose_and_refresh_token(force=True)
    else:
        # Load match-specific metadata if available, otherwise use structured defaults
        meta = None
        base_name = os.path.splitext(args.video)[0]
        meta_candidates = [
            f"{base_name}_metadata.json",
            "final_short_metadata.json"
        ]
        for mc in meta_candidates:
            if os.path.exists(mc):
                try:
                    with open(mc, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        print(f"[DISPATCHER] Loaded dynamic match metadata from '{mc}'")
                        break
                except Exception as e:
                    print(f"[DISPATCHER] Notice reading '{mc}': {e}")

        if not meta:
            meta = {
                "primary_title": "TEST RUN: Cristiano Ronaldo Insane Photo Finish! 🐎🔥",
                "description": "Test description for automated publishing pipeline.",
                "tags_string": "#HorseHavoc #Shorts #Gaming #Viral",
                "hashtags": ["#HorseHavoc", "#Shorts", "#Gaming"],
                "youtube": {
                    "title": "TEST RUN: Cristiano Ronaldo Insane Photo Finish! 🐎🔥 #Shorts",
                    "description": "Test description for automated publishing pipeline.\n\n#HorseHavoc #Shorts #Gaming",
                    "tags": ["Horse Havoc", "Shorts", "Gaming"]
                },
                "instagram": {
                    "caption": "TEST RUN: Cristiano Ronaldo Insane Photo Finish! 🐎🔥\n\nWho was your pick? Drop a comment below! 👇\n\n#HorseHavoc #Gaming #Reels"
                },
                "tiktok": {
                    "caption": "TEST RUN: Cristiano Ronaldo Insane Photo Finish! 🐎🔥 #HorseHavoc #Gaming #FYP"
                }
            }

        enable_yt, enable_tt, enable_ig = resolve_platforms(
            args.all,
            args.youtube, args.no_youtube,
            args.tiktok, args.no_tiktok,
            args.instagram, args.no_instagram
        )

        dispatch_video(
            video_path=args.video,
            metadata=meta,
            is_test=args.test,
            enable_youtube=enable_yt,
            enable_tiktok=enable_tt,
            enable_instagram=enable_ig,
            youtube_privacy=args.privacy
        )
