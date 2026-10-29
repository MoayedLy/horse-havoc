#!/usr/bin/env python3
"""
HORSE HAVOC - Twice-Daily Automated Production Scheduler
=========================================================
Triggers automated match generation and social dispatch twice every day:
- Midnight Run : 12:00 AM (00:00)
- Noon Run     : 12:00 PM (12:00)

Features:
- Powered by Python's `schedule` library.
- Supports custom trigger times via `--times "00:00,12:00"`.
- Runs `auto_run.py` which auto-wraps under Xvfb virtual framebuffer on headless Linux servers.
- Automatically publishes to YouTube Shorts (Public), TikTok, and Instagram Reels.
- Graceful error recovery: failures are recorded without stopping the standing daemon.
"""

import os
import sys
import time
import argparse
import subprocess
from datetime import datetime

# Set console encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import schedule

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTO_RUN_SCRIPT = os.path.join(PROJECT_DIR, "auto_run.py")

def trigger_production_job(is_test=False, youtube=True, tiktok=True, instagram=True, privacy="public"):
    """Executes auto_run.py as an isolated child process."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n" + "=" * 72)
    print(f" [TWICE-DAILY SCHEDULER TRIGGER] {now_str}")
    print("=" * 72)
    print(f" * Target Script  : {AUTO_RUN_SCRIPT}")
    print(f" * Mode           : {'TEST' if is_test else 'FULL 45S MATCH PRODUCTION'}")
    print(f" * YouTube Privacy: {privacy.upper()}")
    print("-" * 72)
    sys.stdout.flush()

    cmd = [sys.executable, AUTO_RUN_SCRIPT, f"--privacy={privacy}"]
    if is_test:
        cmd.append("--test")
    if youtube and tiktok and instagram:
        cmd.append("--all")
    else:
        if youtube:
            cmd.append("--youtube")
        else:
            cmd.append("--no-youtube")
        if tiktok:
            cmd.append("--tiktok")
        else:
            cmd.append("--no-tiktok")
        if instagram:
            cmd.append("--instagram")
        else:
            cmd.append("--no-instagram")

    try:
        res = subprocess.run(cmd, cwd=PROJECT_DIR)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Job execution completed (Return code: {res.returncode}).")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [!] Job execution error: {e}", file=sys.stderr)

    # Log next scheduled trigger
    next_run = schedule.next_run()
    if next_run:
        print(f"[*] Next scheduled publishing run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72 + "\n")
    sys.stdout.flush()

def start_scheduler(times_list=None, run_now=False, is_test=False, privacy="public", youtube=True, tiktok=True, instagram=True):
    target_times = times_list or ["00:00", "12:00"]

    print("=" * 72)
    print(" [HORSE HAVOC] TWICE-DAILY AUTONOMOUS PUBLISHING SCHEDULER")
    print("=" * 72)
    print(f" * Schedule Times : {', '.join(target_times)} (Server Time)")
    print(f" * Midnight Run   : 12:00 AM (00:00)")
    print(f" * Noon Run       : 12:00 PM (12:00)")
    print(f" * Python Binary  : {sys.executable}")
    print(f" * YouTube Shorts : {'ENABLED (' + privacy.upper() + ')' if youtube else 'DISABLED'}")
    print(f" * TikTok Drafts  : {'ENABLED' if tiktok else 'DISABLED'}")
    print(f" * Instagram Reels: {'ENABLED' if instagram else 'DISABLED'}")
    print(f" * Mode           : {'TEST (Fast Dry-Run)' if is_test else 'LIVE PRODUCTION'}")
    print("-" * 72)
    sys.stdout.flush()

    # Register each scheduled time
    for t_str in target_times:
        clean_t = t_str.strip()
        if clean_t:
            schedule.every().day.at(clean_t).do(
                trigger_production_job,
                is_test=is_test,
                youtube=youtube,
                tiktok=tiktok,
                instagram=instagram,
                privacy=privacy
            )
            print(f" [+] Registered daily trigger: {clean_t}")

    if run_now:
        print("[+] Immediate execution requested (--run-now). Launching initial match now...")
        trigger_production_job(
            is_test=is_test,
            youtube=youtube,
            tiktok=tiktok,
            instagram=instagram,
            privacy=privacy
        )

    next_run = schedule.next_run()
    if next_run:
        print(f"\n[*] Standing by. Next scheduled trigger: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
    print("    (Running in foreground. Press Ctrl+C at any time to exit)\n")
    sys.stdout.flush()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Scheduler terminated by user.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HORSE HAVOC Twice-Daily (00:00 & 12:00) Production Scheduler")
    parser.add_argument("--times", default="00:00,12:00", help="Comma-separated trigger times in 24h format (default: '00:00,12:00')")
    parser.add_argument("--run-now", action="store_true", help="Execute one match immediately before entering the schedule loop")
    parser.add_argument("--test", action="store_true", help="Run in fast dry-run test mode")
    parser.add_argument("--privacy", choices=["public", "unlisted", "private"], default="public", help="YouTube upload privacy (default: public)")

    parser.add_argument("--all", action="store_true", default=True, help="Enable all social platforms")
    parser.add_argument("--youtube", action="store_true", default=True, help="Enable YouTube Shorts")
    parser.add_argument("--no-youtube", action="store_false", dest="youtube", help="Disable YouTube Shorts")
    parser.add_argument("--tiktok", action="store_true", default=True, help="Enable TikTok")
    parser.add_argument("--no-tiktok", action="store_false", dest="tiktok", help="Disable TikTok")
    parser.add_argument("--instagram", action="store_true", default=True, help="Enable Instagram Reels")
    parser.add_argument("--no-instagram", action="store_false", dest="instagram", help="Disable Instagram Reels")

    args = parser.parse_args()
    times = [t.strip() for t in args.times.split(",") if t.strip()]

    start_scheduler(
        times_list=times,
        run_now=args.run_now,
        is_test=args.test,
        privacy=args.privacy,
        youtube=args.youtube,
        tiktok=args.tiktok,
        instagram=args.instagram
    )
