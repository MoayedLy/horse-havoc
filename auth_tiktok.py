#!/usr/bin/env python3
"""
HORSE HAVOC - TikTok OAuth 2.0 PKCE Authentication Tool
Conforming to official TikTok Desktop Login Kit specifications:
- code_verifier: 64 characters from [A-Za-z0-9-._~]
- code_challenge: SHA-256 hash strictly formatted as lowercase hexadecimal
- code_challenge_method: S256
- scope: user.info.basic,video.upload
- Dual-Capture listener on port 8080 with manual URL paste fallback
"""

import os
import sys
import json
import time
import secrets
import hashlib
from urllib.parse import urlparse, parse_qs, quote
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8080/callback/").strip()
DEFAULT_PORT = 8080

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"


def generate_pkce_pair():
    """
    Generates high-entropy RFC 7636 code_verifier (64 chars from [A-Za-z0-9-._~])
    and computes the code_challenge strictly as a lowercase HEXADECIMAL SHA-256 string.
    """
    charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    code_verifier = "".join(secrets.choice(charset) for _ in range(64))
    code_challenge = hashlib.sha256(code_verifier.encode("utf-8")).hexdigest()
    return code_verifier, code_challenge


class CapturedState:
    code = None
    error = None
    server_running = False


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # Handles both /callback and /callback/ or root redirects
        if "code" in qs:
            CapturedState.code = qs["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"><title>TikTok Authorized</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { background: #1e293b; border-radius: 16px; padding: 40px; max-width: 480px; text-align: center; border: 1px solid #334155; }
    h1 { color: #22c55e; font-size: 24px; margin-bottom: 12px; }
    p { color: #94a3b8; font-size: 15px; line-height: 1.5; }
  </style>
</head>
<body>
  <div class="card">
    <h1>TikTok Authorization Successful!</h1>
    <p>Your authorization code has been captured. You can close this browser window and return to your terminal.</p>
  </div>
</body>
</html>"""
            self.wfile.write(html.encode("utf-8"))
        elif "error" in qs:
            CapturedState.error = qs.get("error_description", qs["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>Authorization Error: {CapturedState.error}</h1>".encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Waiting for TikTok Authorization Callback...</h1>")


def start_background_server(port):
    """Starts local listener on port 8080. Returns server instance or None if port in use."""
    try:
        class ReusableServer(HTTPServer):
            allow_reuse_address = True

        server = ReusableServer(("", port), OAuthCallbackHandler)
        server.timeout = 1.0

        def serve():
            CapturedState.server_running = True
            while CapturedState.code is None and CapturedState.error is None and CapturedState.server_running:
                server.handle_request()
            try:
                server.server_close()
            except Exception:
                pass

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        return server
    except OSError:
        return None


def exchange_token(code, client_key, client_secret, redirect_uri, code_verifier):
    """Exchanges captured authorization code for access token via TikTok OAuth API."""
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier
    }

    print("[*] Exchanging code for access token via TikTok OAuth API...")
    resp = requests.post(TOKEN_URL, headers=headers, data=payload, timeout=30)
    data = resp.json()

    if "error" in data:
        err = data["error"]
        if isinstance(err, str) and err != "ok":
            desc = data.get("error_description", "")
            raise RuntimeError(f"TikTok token exchange failed: {err} - {desc}")
        elif isinstance(err, dict) and err.get("code") not in ("ok", None, 0):
            raise RuntimeError(f"TikTok token exchange failed [{err.get('code')}]: {err.get('message')}")

    tok_data = data.get("data") if isinstance(data.get("data"), dict) else data
    access_token = tok_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"No access_token found in response: {data}")

    # Query user display name
    display_name = ""
    try:
        u_resp = requests.get(
            USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"fields": "open_id,display_name,avatar_url"},
            timeout=15
        )
        if u_resp.status_code == 200:
            display_name = u_resp.json().get("data", {}).get("user", {}).get("display_name", "")
    except Exception:
        pass

    tok_data["display_name"] = display_name
    tok_data["obtained_at"] = time.time()

    # Save to JSON
    with open("tiktok_token.json", "w", encoding="utf-8") as f:
        json.dump(tok_data, f, indent=2)

    # Save to .env
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    set_key(env_file, "TIKTOK_ACCESS_TOKEN", access_token)
    set_key(env_file, "TIKTOK_POST_MODE", "MEDIA_UPLOAD")

    print("\n" + "=" * 76)
    print(" [SUCCESS] TIKTOK ACCOUNT AUTHORIZED SUCCESSFULLY!")
    print("=" * 76)
    if display_name:
        print(f" * Creator Name    : {display_name}")
    print(f" * Open ID         : {tok_data.get('open_id')}")
    print(f" * Access Token    : {access_token[:20]}... (Saved to .env & tiktok_token.json)")
    print(f" * Token Life      : {tok_data.get('expires_in', 86400) // 3600} hours (Refresh token cached)")
    print(f" * Publishing Mode : MEDIA_UPLOAD (Direct upload to TikTok Studio / Drafts)")
    print("=" * 76)
    print("[*] Ready for production publishing! Run:")
    print("    python auto_run.py --test\n")

    return tok_data


def main():
    import argparse
    parser = argparse.ArgumentParser(description="HORSE HAVOC TikTok OAuth Tool (Official PKCE Specs)")
    parser.add_argument("--client-key", default=CLIENT_KEY, help="TikTok Client Key")
    parser.add_argument("--client-secret", default=CLIENT_SECRET, help="TikTok Client Secret")
    parser.add_argument("--redirect-uri", default=REDIRECT_URI, help="Redirect URI")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default: 8080)")
    parser.add_argument("--no-trailing-slash", action="store_true", help="Use http://localhost:8080/callback without trailing slash")
    parser.add_argument("--manual", action="store_true", help="Manual code paste only")
    args = parser.parse_args()

    client_key = (args.client_key or "").strip()
    client_secret = (args.client_secret or "").strip()
    if not client_key or not client_secret:
        print("\n[!] ERROR: TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET is not configured.")
        print("    Please set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET in .env or pass --client-key and --client-secret.")
        sys.exit(1)
    redirect_uri = "http://localhost:8080/callback" if args.no_trailing_slash else args.redirect_uri.strip()

    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_hex(16)
    scope = "user.info.basic,video.upload"

    # Persist code_verifier to file so any script/command can reference it
    try:
        with open("tiktok_code_verifier.txt", "w", encoding="utf-8") as f:
            f.write(code_verifier)
    except Exception:
        pass

    auth_url = (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={client_key}"
        f"&scope={quote(scope, safe=',')}"
        f"&response_type=code"
        f"&redirect_uri={quote(redirect_uri, safe='')}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    print("\n" + "=" * 76)
    print(" [TIKTOK DEVELOPER OAUTH 2.0 PKCE AUTHORIZATION]")
    print("=" * 76)
    print(f" * Client Key           : {client_key}")
    print(f" * Redirect URI         : {redirect_uri}")
    print(f" * Scopes               : {scope}")
    print(f" * PKCE Method          : S256")
    print(f" * Code Verifier Length : {len(code_verifier)} chars")
    print(f" * Code Challenge (Hex) : {code_challenge}")
    print("-" * 76)

    # Try starting local server on port 8080
    server = None
    if not args.manual:
        server = start_background_server(args.port)
        if server:
            print(f"[*] Local listener active on http://localhost:{args.port}/callback/ and /callback")
        else:
            print(f"[!] Notice: Port {args.port} is in use by another service on your system.")
            print("    Dual-capture mode active: simply paste the redirected URL below.")

    print("\n" + "=" * 76)
    print("COPY AND PASTE THIS EXACT URL INTO YOUR BROWSER (OR INCOGNITO WINDOW):")
    print("=" * 76)
    print(auth_url)
    print("=" * 76)
    print("\nINSTRUCTIONS:")
    print("1. Open the URL above in your browser.")
    print("2. Log in with your TikTok account and click 'Authorize'.")
    print("3. When redirected, your local listener will capture the code automatically.")
    print("   If your browser displays 'Page Not Found' (due to port 8080 conflict),")
    print("   simply COPY THE FULL URL from your browser address bar and paste it below.")
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
        print(f"\n[ERROR] Authorization denied by TikTok: {CapturedState.error}")
        print("Review your TikTok Developer app settings.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    code = CapturedState.code
    if not code:
        print("\n[ERROR] No authorization code captured.")
        input("\nPress Enter to exit...")
        sys.exit(1)

    print(f"\n[+] Authorization code captured: {code[:15]}...")
    try:
        exchange_token(code, client_key, client_secret, redirect_uri, code_verifier)
    except Exception as e:
        print(f"\n[!] Token exchange error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)


def run_oauth_flow(*args, **kwargs):
    return main()


if __name__ == "__main__":
    main()
