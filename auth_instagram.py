#!/usr/bin/env python3
"""
HORSE HAVOC - Meta / Instagram Reels OAuth Authentication Tool (Audited & Verified)

Key Features:
1. Re-architected with clean HTTP server on port 8082 (avoiding port 8080 conflicts with Windows services).
2. Dual-Capture Strategy: Listens on local server AND allows pasting the redirected URL/code into the terminal.
3. Full 3-tier token upgrade flow:
   - code -> Short-Lived User Token
   - Short-Lived User Token -> 60-day Long-Lived User Token (fb_exchange_token)
   - /me/accounts -> NEVER-EXPIRING Page Access Token & connected Instagram Business Account ID.
4. Automatically updates .env and saves instagram_token.json.
"""

import os
import sys
import json
import time
import secrets
from urllib.parse import urlparse, parse_qs, quote
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

META_APP_ID = os.getenv("META_APP_ID", "").strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v20.0").strip()

# Default to port 8082 to avoid Windows ApplicationWebServer.exe occupying 8080
DEFAULT_PORT = 8082
REDIRECT_URI = os.getenv("META_REDIRECT_URI", f"http://localhost:{DEFAULT_PORT}/callback/").strip()
DEFAULT_SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"

GRAPH_BASE = "https://graph.facebook.com"


class CapturedState:
    code = None
    error = None
    server_running = False


class MetaCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if "code" in qs:
            CapturedState.code = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"><title>Instagram Authorized</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { background: #1e293b; border-radius: 16px; padding: 40px; max-width: 480px; text-align: center; border: 1px solid #334155; }
    h1 { color: #e1306c; font-size: 24px; margin-bottom: 12px; }
    p { color: #94a3b8; font-size: 15px; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Instagram Authorization Successful!</h1>
    <p>Your Meta authorization code has been captured. Permanent Page credentials are being saved. You can close this tab and return to your terminal.</p>
  </div>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
        elif "error" in qs:
            CapturedState.error = qs.get("error_description", qs["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization Denied</h1>")
        else:
            self.send_response(404)
            self.end_headers()


def start_background_server(port):
    """Starts local callback listener."""
    try:
        class ReusableServer(HTTPServer):
            allow_reuse_address = True

        server = ReusableServer(("", port), MetaCallbackHandler)
        server.timeout = 1.0

        def serve():
            CapturedState.server_running = True
            while CapturedState.code is None and CapturedState.error is None and CapturedState.server_running:
                server.handle_request()
            server.server_close()

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        return server
    except OSError:
        return None


def execute_token_upgrade_flow(code, app_id, app_secret, redirect_uri):
    """
    Executes the 3-tier token upgrade:
    1. Swap code for short-lived user token.
    2. Swap short-lived token for 60-day long-lived user token.
    3. Query /me/accounts with long-lived user token to retrieve:
       - Permanent, never-expiring Page Access Token
       - Connected instagram_business_account ID
    """
    # Step 1: Exchange code for short-lived user token
    print("\n[1/3] Exchanging authorization code for short-lived User Token...")
    step1_url = f"{GRAPH_BASE}/{META_GRAPH_VERSION}/oauth/access_token"
    p1 = {
        "client_id": app_id,
        "client_secret": app_secret,
        "redirect_uri": redirect_uri,
        "code": code
    }
    r1 = requests.get(step1_url, params=p1, timeout=30)
    d1 = r1.json()
    if "error" in d1:
        raise RuntimeError(f"Step 1 (Short User Token) failed: {d1['error'].get('message')}")
    short_user_token = d1.get("access_token")

    # Step 2: Exchange for 60-day long-lived user token
    print("[2/3] Exchanging for 60-day Long-Lived User Token (fb_exchange_token)...")
    step2_url = f"{GRAPH_BASE}/{META_GRAPH_VERSION}/oauth/access_token"
    p2 = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_user_token
    }
    r2 = requests.get(step2_url, params=p2, timeout=30)
    d2 = r2.json()
    if "error" in d2:
        raise RuntimeError(f"Step 2 (Long User Token) failed: {d2['error'].get('message')}")
    long_user_token = d2.get("access_token")

    # Step 3: Query /me/accounts for Page Token & Instagram Business Account
    print("[3/3] Querying /me/accounts for permanent Page Token & Instagram Account ID...")
    step3_url = f"{GRAPH_BASE}/{META_GRAPH_VERSION}/me/accounts"
    p3 = {
        "fields": "name,id,access_token,instagram_business_account{id,username,name,profile_picture_url}",
        "access_token": long_user_token
    }
    r3 = requests.get(step3_url, params=p3, timeout=30)
    d3 = r3.json()
    if "error" in d3:
        raise RuntimeError(f"Step 3 (/me/accounts) failed: {d3['error'].get('message')}")

    pages = d3.get("data", [])
    if not pages:
        raise RuntimeError("No Facebook Pages found under this Meta account. Please create or link a Facebook Page to your Instagram account.")

    selected_page = None
    selected_ig = None

    for page in pages:
        ig = page.get("instagram_business_account")
        if ig:
            selected_page = page
            selected_ig = ig
            break

    if not selected_page:
        selected_page = pages[0]
        print(f"\n[!] Notice: Page '{selected_page.get('name')}' found, but no linked Instagram Business account detected yet.")
        print("    Link it in Facebook Page Settings -> Linked Accounts -> Instagram.")

    page_name = selected_page.get("name", "Unknown Page")
    page_id = selected_page.get("id", "")
    page_access_token = selected_page.get("access_token", "")
    ig_account_id = selected_ig.get("id") if selected_ig else ""
    ig_username = selected_ig.get("username", "") if selected_ig else ""

    token_record = {
        "page_name": page_name,
        "page_id": page_id,
        "page_access_token": page_access_token,
        "instagram_account_id": ig_account_id,
        "instagram_username": ig_username,
        "long_lived_user_token": long_user_token,
        "obtained_at": time.time(),
        "token_type": "Permanent Long-Lived Page Access Token (Never Expires)"
    }

    # Save to JSON
    with open("instagram_token.json", "w", encoding="utf-8") as f:
        json.dump(token_record, f, indent=2)

    # Save to .env
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    set_key(env_file, "INSTAGRAM_ACCESS_TOKEN", page_access_token)
    if ig_account_id:
        set_key(env_file, "INSTAGRAM_ACCOUNT_ID", ig_account_id)
    set_key(env_file, "META_APP_ID", app_id)
    set_key(env_file, "META_APP_SECRET", app_secret)

    print("\n" + "=" * 72)
    print(" [SUCCESS] INSTAGRAM & META AUTHORIZATION COMPLETED!")
    print("=" * 72)
    print(f" * Facebook Page    : {page_name} (ID: {page_id})")
    if ig_account_id:
        print(f" * Instagram Account: @{ig_username} (ID: {ig_account_id})")
    else:
        print(f" * Instagram Account: [PENDING LINK IN FACEBOOK PAGE SETTINGS]")
    print(f" * Access Token     : {page_access_token[:20]}... (Permanent Page Token)")
    print(f" * Token Lifetime   : Never expires (valid as long as user remains Page admin)")
    print(f" * Saved in .env    : INSTAGRAM_ACCESS_TOKEN & INSTAGRAM_ACCOUNT_ID")
    print(f" * Token Record     : instagram_token.json")
    print("=" * 72)
    print("[*] Ready for Instagram Reels publishing! Run:")
    print("    python publisher.py --instagram --test\n")

    return token_record


def main():
    import argparse
    parser = argparse.ArgumentParser(description="HORSE HAVOC Instagram Reels OAuth Tool (Audited)")
    parser.add_argument("--app-id", default=META_APP_ID, help="Meta App ID")
    parser.add_argument("--app-secret", default=META_APP_SECRET, help="Meta App Secret")
    parser.add_argument("--redirect-uri", default=REDIRECT_URI, help="OAuth Redirect URI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Local callback port (default: {DEFAULT_PORT})")
    parser.add_argument("--manual", action="store_true", help="Manual code paste only")
    args = parser.parse_args()

    app_id = (args.app_id or "").strip()
    app_secret = (args.app_secret or "").strip()
    port = args.port

    if not app_id or not app_secret:
        print("\n[!] ERROR: META_APP_ID or META_APP_SECRET is not configured.")
        print("    Please set META_APP_ID and META_APP_SECRET in .env or pass --app-id and --app-secret.")
        sys.exit(1)
    redirect_uri = args.redirect_uri

    state = secrets.token_hex(16)
    dialog_url = (
        f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={quote(redirect_uri)}"
        f"&scope={DEFAULT_SCOPES}"
        f"&response_type=code"
        f"&state={state}"
    )

    print("\n" + "=" * 76)
    print(" [META DEVELOPER / INSTAGRAM REELS OAUTH AUTHORIZATION]")
    print("=" * 76)
    print(f" * Meta App ID    : {app_id}")
    print(f" * Redirect URI   : {redirect_uri}")
    print(f" * Scopes         : {DEFAULT_SCOPES}")
    print(f" * Target         : Permanent Long-Lived Page Token + Instagram Business ID")
    print("-" * 76)

    server = None
    if not args.manual:
        server = start_background_server(port)
        if server:
            print(f"[*] Local listener active on http://localhost:{port}/callback/")
        else:
            print(f"[!] Notice: Port {port} is occupied by another service on your system.")
            print("    Dual-capture mode active: simply paste the redirected URL below.")

    print("\nCopy and paste this URL into your browser (or incognito window):\n")
    print(dialog_url)
    print("\n" + "=" * 76)
    print("INSTRUCTIONS:")
    print(f"1. Ensure '{redirect_uri}' is added in Meta Developer Portal -> Facebook Login -> Valid OAuth Redirect URIs.")
    print("2. Open the URL above, log in with Facebook, select your Facebook Page & Instagram account, and approve.")
    print("3. When redirected, your local listener will capture the code automatically.")
    print("   If your browser shows 'Page Not Found', simply copy the FULL URL from your address bar and paste it below.")
    print("=" * 76 + "\n")

    user_input = ""
    while CapturedState.code is None and CapturedState.error is None:
        try:
            user_input = input("Paste redirected URL or authorization code (or press Enter to wait): ").strip()
            if user_input:
                if "code=" in user_input:
                    qs = parse_qs(urlparse(user_input).query)
                    CapturedState.code = qs.get("code", [user_input])[0]
                else:
                    CapturedState.code = user_input
                break
        except (KeyboardInterrupt, EOFError):
            print("\nAuthorization cancelled by user.")
            CapturedState.server_running = False
            sys.exit(1)

    CapturedState.server_running = False

    if CapturedState.error:
        print(f"\n[ERROR] Authorization denied by Meta: {CapturedState.error}")
        sys.exit(1)

    code = CapturedState.code
    if not code:
        print("[ERROR] No authorization code captured.")
        sys.exit(1)

    print(f"\n[+] Authorization code captured: {code[:15]}...")
    try:
        execute_token_upgrade_flow(code, app_id, app_secret, redirect_uri)
    except Exception as e:
        print(f"\n[!] Token upgrade error: {e}")
        sys.exit(1)


def run_instagram_auth_flow(*args, **kwargs):
    return main()


if __name__ == "__main__":
    main()
