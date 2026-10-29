#!/usr/bin/env python3
"""
HORSE HAVOC - Instagram Reels & Meta Graph API Diagnostic Tool
==============================================================
Diagnostics performed:
1. Token & Environment Configuration check (.env and instagram_token.json).
2. App Token & debug_token inspection (validity, app_id, scopes, expiry).
3. /me & /me/permissions inspection.
4. /{instagram_account_id} reachability and account details.
5. Minimal container creation test with verbose headers & raw response inspection.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def run_diagnostics():
    load_dotenv()

    app_id = os.getenv("META_APP_ID", "").strip()
    app_secret = os.getenv("META_APP_SECRET", "").strip()
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    graph_ver = os.getenv("META_GRAPH_VERSION", "v20.0").strip()

    # Fallback to instagram_token.json if empty
    token_json_path = "instagram_token.json"
    if os.path.exists(token_json_path):
        try:
            with open(token_json_path, "r", encoding="utf-8") as f:
                tdata = json.load(f)
                access_token = access_token or tdata.get("page_access_token", "").strip()
                account_id = account_id or tdata.get("instagram_account_id", "").strip()
        except Exception as e:
            print(f"[WARN] Error reading instagram_token.json: {e}")

    base_url = f"https://graph.facebook.com/{graph_ver}"

    print("=" * 75)
    print(" [INSTAGRAM REELS DIAGNOSTIC TOOL] Meta Graph API Inspector")
    print("=" * 75)
    print(f" * Meta Graph Version : {graph_ver}")
    print(f" * Meta App ID        : {app_id if app_id else 'NOT SET'}")
    print(f" * Meta App Secret    : {'*' * 8 + app_secret[-4:] if len(app_secret) >= 4 else 'NOT SET'}")
    print(f" * Instagram Account ID: {account_id if account_id else 'NOT SET'}")
    print(f" * Access Token (len) : {len(access_token)} chars {'(Prefix: ' + access_token[:15] + '...)' if access_token else 'NOT SET'}")
    print("=" * 75)

    if not access_token or not account_id:
        print("\n[ERROR] Missing INSTAGRAM_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID in .env.")
        return

    # -------------------------------------------------------------------------
    # TEST 1: Inspect /me and Permissions
    # -------------------------------------------------------------------------
    print("\n--- [TEST 1] Querying /me and Granted Permissions ---")
    url_me = f"{base_url}/me"
    params_me = {
        "fields": "id,name,permissions",
        "access_token": access_token
    }
    try:
        r_me = requests.get(url_me, params=params_me, timeout=20)
        print(f" * GET {url_me}?fields=id,name,permissions")
        print(f" * Response Code : {r_me.status_code}")
        try:
            data_me = r_me.json()
            print(" * Response Body :")
            print(json.dumps(data_me, indent=2))
        except Exception:
            print(f" * Raw Response  : {r_me.text}")
    except Exception as e:
        print(f" * Network Exception: {e}")

    # Also query /me/permissions directly
    url_perms = f"{base_url}/me/permissions"
    try:
        r_perms = requests.get(url_perms, params={"access_token": access_token}, timeout=20)
        if r_perms.status_code == 200:
            print(" * Granted Permissions List:")
            perms_data = r_perms.json().get("data", [])
            for p in perms_data:
                print(f"   - {p.get('permission')}: {p.get('status')}")
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # TEST 2: Inspect /{instagram_account_id}
    # -------------------------------------------------------------------------
    print(f"\n--- [TEST 2] Querying /{account_id} (Instagram Profile Details) ---")
    url_acc = f"{base_url}/{account_id}"
    params_acc = {
        "fields": "id,username,name,biography,followers_count,follows_count,media_count",
        "access_token": access_token
    }
    try:
        r_acc = requests.get(url_acc, params=params_acc, timeout=20)
        print(f" * GET {url_acc}?fields=id,username,name,...")
        print(f" * Response Code : {r_acc.status_code}")
        try:
            data_acc = r_acc.json()
            print(" * Response Body :")
            print(json.dumps(data_acc, indent=2))
        except Exception:
            print(f" * Raw Response  : {r_acc.text}")
    except Exception as e:
        print(f" * Network Exception: {e}")

    # -------------------------------------------------------------------------
    # TEST 3: Inspect Token via /debug_token (App Token)
    # -------------------------------------------------------------------------
    if app_id and app_secret:
        print(f"\n--- [TEST 3] Inspecting Token via /debug_token ---")
        url_debug = f"{base_url}/debug_token"
        app_token = f"{app_id}|{app_secret}"
        params_debug = {
            "input_token": access_token,
            "access_token": app_token
        }
        try:
            r_debug = requests.get(url_debug, params=params_debug, timeout=20)
            print(f" * GET {url_debug}")
            print(f" * Response Code : {r_debug.status_code}")
            try:
                data_debug = r_debug.json()
                print(" * Response Body :")
                print(json.dumps(data_debug, indent=2))
            except Exception:
                print(f" * Raw Response  : {r_debug.text}")
        except Exception as e:
            print(f" * Network Exception: {e}")

    # -------------------------------------------------------------------------
    # TEST 4: Minimal Container Creation Attempt (Verbose)
    # -------------------------------------------------------------------------
    print(f"\n--- [TEST 4] Test Reel Container Creation (POST /{account_id}/media) ---")
    url_media = f"{base_url}/{account_id}/media"
    # A standard public test mp4
    test_video_url = "https://files.catbox.moe/k3h4u7.mp4"
    test_caption = "Horse Havoc Test Diagnostic Reel 🐎 #HorseHavoc #Test"

    payload = {
        "media_type": "REELS",
        "video_url": test_video_url,
        "caption": test_caption,
        "share_to_feed": "false",
        "access_token": access_token
    }

    print(f" * POST {url_media}")
    print(f" * Payload: {{'media_type': 'REELS', 'video_url': '{test_video_url}', 'caption': '...', 'share_to_feed': 'false'}}")
    try:
        r_media = requests.post(url_media, data=payload, timeout=30)
        print(f" * Response Status Code : {r_media.status_code}")
        print(" * Response Headers:")
        for hk in ("WWW-Authenticate", "Facebook-API-Version", "x-fb-trace-id", "x-business-use-case-usage"):
            if hk in r_media.headers:
                print(f"   - {hk}: {r_media.headers[hk]}")

        print(" * Raw Response Body:")
        try:
            res_json = r_media.json()
            print(json.dumps(res_json, indent=2))
            if "error" in res_json:
                err = res_json["error"]
                print("\n[DIAGNOSTIC ANALYSIS]")
                print(f" * Error Code     : {err.get('code')}")
                print(f" * Error Subcode  : {err.get('error_subcode')}")
                print(f" * Error Type     : {err.get('type')}")
                print(f" * Error Message  : {err.get('message')}")
                print(f" * Trace ID       : {err.get('fbtrace_id')}")
                if "error_user_title" in err:
                    print(f" * User Title     : {err.get('error_user_title')}")
                if "error_user_msg" in err:
                    print(f" * User Message   : {err.get('error_user_msg')}")
            elif "id" in res_json:
                print(f"\n[SUCCESS] Container creation succeeded! Container ID: {res_json.get('id')}")
        except Exception:
            print(r_media.text)
    except Exception as e:
        print(f" * Network Exception: {e}")

    print("\n" + "=" * 75)
    print(" DIAGNOSTIC SCAN COMPLETE")
    print("=" * 75)

if __name__ == "__main__":
    run_diagnostics()

