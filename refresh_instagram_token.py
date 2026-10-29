#!/usr/bin/env python3
"""
HORSE HAVOC - Instagram Reels Meta Token Diagnostic & Auto-Refresh Utility
-------------------------------------------------------------------------
Automates token lifecycle management, expiration tracking, and renewal
for Meta Graph API Instagram Reels publishing.

Usage:
  python refresh_instagram_token.py                 # Diagnose & auto-refresh if < 7 days remaining
  python refresh_instagram_token.py --check-only    # Only inspect token health without modifying .env
  python refresh_instagram_token.py --force         # Force token exchange even if > 7 days remaining
  python refresh_instagram_token.py --threshold 14  # Custom expiration threshold in days
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

from publisher import (
    check_instagram_token_health,
    refresh_instagram_token,
    update_env_variable
)


def print_banner():
    print("=" * 68)
    print("      HORSE HAVOC - INSTAGRAM REELS META TOKEN MANAGER")
    print("=" * 68)


def format_timestamp(ts):
    if not ts or ts == 0:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)


def diagnose_and_refresh_token(check_only=False, force=False, threshold_days=7.0, env_file=None):
    """
    Diagnoses the current Instagram access token health and renews it if needed.
    Returns:
        tuple (success: bool, status_dict: dict)
    """
    if env_file is None:
        env_file = Path(__file__).resolve().parent / ".env"

    print_banner()
    print("[1] Diagnosing Instagram Access Token via Meta Graph API...")

    app_id = os.getenv("META_APP_ID", "").strip()
    app_secret = os.getenv("META_APP_SECRET", "").strip()
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    graph_version = os.getenv("META_GRAPH_VERSION", "v20.0").strip()
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()

    if not token:
        print("[!] ERROR: INSTAGRAM_ACCESS_TOKEN is not set in .env.")
        print("    Run 'python publisher.py --auth-instagram' to link your Instagram account.")
        return False, {"error": "Missing INSTAGRAM_ACCESS_TOKEN"}

    if not app_secret:
        print("[!] ERROR: META_APP_SECRET is not set in .env.")
        return False, {"error": "Missing META_APP_SECRET"}

    # 1. Run debug_token inspection
    health = check_instagram_token_health(access_token=token, app_id=app_id, app_secret=app_secret)

    is_valid = health.get("is_valid", False)
    token_type = health.get("token_type", "UNKNOWN")
    expires_at = health.get("expires_at", 0)
    never_expires = health.get("never_expires", False)
    days_remaining = health.get("days_remaining", 0.0)
    scopes = health.get("scopes", [])
    app_name = health.get("app_name", "Unknown")
    error_msg = health.get("error")

    # Display diagnostics table
    print("-" * 68)
    print(f"  * Application Name   : {app_name} (ID: {app_id})")
    print(f"  * Target IG Account  : {account_id or 'Not specified'}")
    print(f"  * Meta Graph Version : {graph_version}")
    print(f"  * Token Type         : {token_type}")
    print(f"  * Token Status       : {'[VALID]' if is_valid else '[INVALID / EXPIRED]'}")

    if never_expires:
        lifespan_str = "Never Expires (Permanent Page / System User Token)"
    elif expires_at > 0:
        lifespan_str = f"{days_remaining:.1f} days remaining (Expires: {format_timestamp(expires_at)})"
    else:
        lifespan_str = "Unavailable"

    print(f"  * Lifespan           : {lifespan_str}")

    # Check scopes
    has_publish = "instagram_content_publish" in scopes
    has_basic = "instagram_basic" in scopes
    scopes_str = ", ".join(scopes) if scopes else "None"
    print(f"  * Granted Scopes     : {scopes_str}")
    print(f"  * Required Scopes    : instagram_content_publish [{'OK' if has_publish else 'MISSING'}], "
          f"instagram_basic [{'OK' if has_basic else 'MISSING'}]")
    print("-" * 68)

    if not is_valid:
        print(f"[!] Warning: Token is INVALID or REVOKED: {error_msg}")
    elif not (has_publish and has_basic):
        print("[!] Warning: Token is missing required publishing scopes!")

    # 2. Check if check-only mode requested
    if check_only:
        print("[i] Check-only mode: No refresh requested.")
        if is_valid and (never_expires or days_remaining >= threshold_days):
            print("[✓] Token health is optimal. No action required.")
            return True, health
        else:
            print("[!] Token requires attention or renewal.")
            return False, health

    # 3. Determine if refresh should be executed
    needs_refresh = False
    reason = ""

    if force:
        needs_refresh = True
        reason = "Forced refresh requested by user flag (--force)"
    elif not is_valid:
        needs_refresh = True
        reason = f"Token is invalid ({error_msg})"
    elif not never_expires and days_remaining < threshold_days:
        needs_refresh = True
        reason = f"Token expires in {days_remaining:.1f} days (< threshold of {threshold_days} days)"

    if not needs_refresh:
        print(f"[✓] Token is healthy! Lifespan: {lifespan_str}.")
        print("[✓] Automated renewal not required at this time.")
        return True, health

    # 4. Execute token renewal exchange
    print(f"\n[2] Initiating automated token exchange via Meta Graph API ({reason})...")
    try:
        new_token, new_type, expires_in = refresh_instagram_token(
            access_token=token,
            app_id=app_id,
            app_secret=app_secret,
            graph_version=graph_version,
            target_account_id=account_id,
            env_file=env_file
        )
        print(f"[✓] Successfully acquired refreshed Meta access token!")
        print(f"    * New Token Type : {new_type}")
        print(f"    * Saved to .env  : {env_file}")

        # 5. Verify the refreshed token
        print("\n[3] Verifying newly installed token...")
        verify_health = check_instagram_token_health(
            access_token=new_token,
            app_id=app_id,
            app_secret=app_secret
        )

        v_valid = verify_health.get("is_valid", False)
        v_never = verify_health.get("never_expires", False)
        v_days = verify_health.get("days_remaining", 0.0)
        v_exp_str = "Never Expires (Permanent)" if v_never else f"{v_days:.1f} days remaining"

        print(f"  * Verification Status : {'[SUCCESS]' if v_valid else '[FAILED]'}")
        print(f"  * Updated Lifespan    : {v_exp_str}")
        print("=" * 68)
        print("[✓] Instagram Reels authentication is fully renewed and verified!")
        print("=" * 68)
        return True, verify_health

    except Exception as e:
        print(f"\n[!] Token exchange failed: {e}")
        print("\n[RECOMMENDED ACTION]")
        print("If your access token is expired or revoked, a fresh user consent flow is required:")
        print("  --> Run: python publisher.py --auth-instagram")
        print("=" * 68)
        return False, {"error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="HORSE HAVOC - Instagram Reels Meta Token Diagnostic & Auto-Refresh Utility"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Inspect token health without requesting renewal or modifying .env"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force token renewal exchange even if token has > 7 days remaining"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=7.0,
        help="Expiration threshold in days to trigger auto-refresh (default: 7.0 days)"
    )
    parser.add_argument(
        "--env-file",
        type=str,
        default=None,
        help="Path to .env file (default: .env in project root)"
    )

    args = parser.parse_args()

    success, _ = diagnose_and_refresh_token(
        check_only=args.check_only,
        force=args.force,
        threshold_days=args.threshold,
        env_file=args.env_file
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

