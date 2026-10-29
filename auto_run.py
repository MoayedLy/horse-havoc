#!/usr/bin/env python3
"""
HORSE HAVOC - Cloud VPS Automated Production & Publishing Runner
================================================================
Designed to run 24/7 on Linux VPS (Ubuntu/Debian) or local machines:
- Automatic Xvfb virtual framebuffer wrapping for headless servers.
- Automatic SDL dummy driver fallback when no display server is available.
- Triggers full 45s race simulation, FFmpeg 1080x1920 capture, audio mixing,
  viral metadata generation, and multi-channel social dispatch (Telegram/APIs).
- Supports one-shot cron execution, instant test mode, and persistent daemon loop.
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
from datetime import datetime

# ------------------------------------------------------------------------------
# 1. HEADLESS LINUX & XVFB AUTO-WRAPPING
# ------------------------------------------------------------------------------
def ensure_virtual_display():
    """
    On headless Linux servers, if no DISPLAY is set and xvfb-run is installed,
    automatically re-executes this script under xvfb-run so Pygame/OpenGL have
    a full 1080x1920 virtual framebuffer display.
    """
    is_linux = sys.platform.startswith("linux")
    has_display = bool(os.environ.get("DISPLAY"))
    already_wrapped = os.environ.get("_HORSE_HAVOC_XVFB_WRAPPED") == "1"

    if is_linux and not has_display and not already_wrapped:
        xvfb_bin = shutil.which("xvfb-run")
        if xvfb_bin:
            os.environ["_HORSE_HAVOC_XVFB_WRAPPED"] = "1"
            cmd = [
                xvfb_bin,
                "-a",                               # Auto-find free display number
                "-s", "-screen 0 1080x1920x24",     # 1080x1920 24-bit color depth
                sys.executable,
                os.path.abspath(__file__)
            ] + sys.argv[1:]
            print(f"[VPS HEADLESS] Auto-launching inside virtual framebuffer: {' '.join(cmd[:4])}...")
            sys.stdout.flush()
            res = subprocess.run(cmd)
            sys.exit(res.returncode)

    # Fallback to pure dummy drivers if Xvfb is not present and no display exists
    if not has_display:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ensure_virtual_display()

# ------------------------------------------------------------------------------
# 2. ENCODING & PATH CONFIGURATION
# ------------------------------------------------------------------------------
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
os.chdir(str(PROJECT_DIR))

# Ensure logs directory exists
LOGS_DIR = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------------------
# 3. ASSET INTEGRITY VERIFICATION
# ------------------------------------------------------------------------------
def verify_asset_prerequisites():
    """Ensures victory sounds and celebrity avatars exist before starting race."""
    victory_dir = PROJECT_DIR / "assets" / "sounds" / "victory"
    if not victory_dir.exists() or len(os.listdir(str(victory_dir))) < 5:
        print("[SETUP] Generating missing procedural victory sound pool...")
        try:
            from create_victory_sounds import save_wav, sounds, out_dir
            for fname, s_samples in sounds.items():
                save_wav(os.path.join(out_dir, fname), s_samples)
        except Exception as e:
            print(f"[SETUP] Warning during sound pool check: {e}")

    celeb_dir = PROJECT_DIR / "assets" / "celebrities"
    if not celeb_dir.exists() or len([f for f in os.listdir(str(celeb_dir)) if f.endswith('.png')]) < 5:
        print("[SETUP] Checking celebrity avatars...")
        try:
            script = str(PROJECT_DIR / "download_avatars.py")
            if os.path.exists(script):
                subprocess.run([sys.executable, script], check=False)
        except Exception as e:
            print(f"[SETUP] Notice on avatar check: {e}")

# ------------------------------------------------------------------------------
# 4. SINGLE PRODUCTION EXECUTION
# ------------------------------------------------------------------------------
def execute_production_run(
    is_test=False,
    no_dispatch=False,
    output_file="final_short.mp4",
    seed=None,
    live_upload=False,
    enable_youtube=True,
    enable_tiktok=True,
    enable_instagram=True,
    youtube_privacy="public",
    track=None,
    group=None
):
    """Executes one complete end-to-end race production and social dispatch run."""
    start_time = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_name = f"auto_run_{datetime.now().strftime('%Y%m%d')}.log"
    daily_log_path = os.path.join(LOGS_DIR, log_name)

    yt_privacy = youtube_privacy or os.getenv("YOUTUBE_PRIVACY_STATUS", "public")

    print("=" * 72)
    print(" [HORSE HAVOC] AUTOMATED CLOUD PRODUCTION RUNNER")
    print("=" * 72)
    print(f" * Timestamp       : {now_str}")
    print(f" * Operating System: {sys.platform} ({os.name})")
    print(f" * Working Dir     : {PROJECT_DIR}")
    print(f" * Display State   : {os.environ.get('DISPLAY', 'Headless Dummy Driver')}")
    print(f" * Video Driver    : {os.environ.get('SDL_VIDEODRIVER', 'auto')}")
    print(f" * Mode            : {'TEST (Fast Verification)' if is_test else 'FULL 45-SECOND PRODUCTION'}")
    print(f" * Track Preset    : {track or 'auto (seed rotation)'}")
    print(f" * Category Preset : {group or 'auto (category rotation)'}")
    print(f" * Live Upload     : {live_upload or not is_test}")
    print(f" * YouTube Shorts  : {'ENABLED (' + yt_privacy.upper() + ')' if enable_youtube else 'DISABLED'}")
    print(f" * TikTok Video    : {'ENABLED' if enable_tiktok else 'DISABLED'}")
    print(f" * Instagram Reels : {'ENABLED' if enable_instagram else 'DISABLED'}")
    print(f" * Output Target   : {output_file}")
    print(f" * Daily Log File  : {daily_log_path}")
    print("-" * 72)
    sys.stdout.flush()

    verify_asset_prerequisites()

    # Import and run master pipeline
    from run_pipeline import run_pipeline

    result = run_pipeline(
        seed=seed,
        is_test=is_test,
        no_dispatch=no_dispatch,
        output_file=output_file,
        crf=23 if not is_test else 23,
        preset="veryfast" if not is_test else "ultrafast",
        live_upload=live_upload,
        enable_youtube=enable_youtube,
        enable_tiktok=enable_tiktok,
        enable_instagram=enable_instagram,
        youtube_privacy=yt_privacy,
        track=track,
        group=group
    )

    elapsed = time.time() - start_time
    print("\n" + "=" * 72)
    print(" AUTOMATED MATCH EXECUTION COMPLETE")
    print("=" * 72)
    print(f" * Status         : {result.get('status', 'unknown').upper()}")
    print(f" * Output Video   : {os.path.abspath(output_file)}")
    print(f" * Total Elapsed  : {elapsed:.1f}s")
    if result.get("dispatch"):
        print(f" * Dispatch Info  : {result.get('dispatch')}")
    print("=" * 72)
    sys.stdout.flush()

    # Defense-in-depth: Run automated disk cleanup (Keep single latest video file on disk, purge >24h old videos)
    try:
        import cleanup_manager
        cleanup_manager.run_retention_policy(max_age_hours=24.0, single_video_mode=True, current_target=output_file)
    except Exception as ce:
        print(f"[CLEANUP NOTICE] Production runner retention notice: {ce}")

    # Write summary to daily log
    with open(daily_log_path, "a", encoding="utf-8") as f:
        f.write(f"[{now_str}] SUCCESS - Video: {output_file} ({elapsed:.1f}s) - Status: {result.get('status')}\n")

    return result

# ------------------------------------------------------------------------------
# 5. PERSISTENT DAEMON SCHEDULER (OPTIONAL ALTERNATIVE TO CRON)
# ------------------------------------------------------------------------------
def run_daemon_scheduler(times_list=None, is_test=False, no_dispatch=False, enable_youtube=True, enable_tiktok=True, enable_instagram=True, youtube_privacy="public", track=None, group=None):
    """Runs a continuous in-process loop triggering every day at target times (Default: 00:00 & 12:00)."""
    import schedule

    target_times = times_list or ["00:00", "12:00"]
    yt_privacy = youtube_privacy or os.getenv("YOUTUBE_PRIVACY_STATUS", "public")

    print("=" * 72)
    print(" [HORSE HAVOC] PERSISTENT DAEMON SCHEDULER ACTIVE (TWICE-DAILY)")
    print("=" * 72)
    print(f" * Scheduled Triggers: {', '.join(target_times)} (Server Time)")
    print(f" * Midnight Run      : 12:00 AM (00:00)")
    print(f" * Noon Run          : 12:00 PM (12:00)")
    print(f" * Track Preset      : {track or 'auto (seed rotation)'}")
    print(f" * Category Preset   : {group or 'auto (category rotation)'}")
    print(f" * Project Directory : {PROJECT_DIR}")
    print(f" * YouTube Shorts    : {'ENABLED (' + yt_privacy.upper() + ')' if enable_youtube else 'DISABLED'}")
    print(f" * TikTok Drafts     : {'ENABLED' if enable_tiktok else 'DISABLED'}")
    print(f" * Instagram Reels   : {'ENABLED' if enable_instagram else 'DISABLED'}")
    print(f" * Press Ctrl+C at any time to stop.")
    print("-" * 72)
    sys.stdout.flush()

    def job():
        try:
            execute_production_run(
                is_test=is_test,
                no_dispatch=no_dispatch,
                enable_youtube=enable_youtube,
                enable_tiktok=enable_tiktok,
                enable_instagram=enable_instagram,
                youtube_privacy=yt_privacy,
                track=track,
                group=group
            )
        except Exception as e:
            print(f"[DAEMON ERROR] Pipeline failed: {e}", file=sys.stderr)

    for t in target_times:
        clean_t = t.strip()
        if clean_t:
            schedule.every().day.at(clean_t).do(job)
            print(f" [+] Registered daily trigger: {clean_t}")

    next_trigger = schedule.next_run()
    if next_trigger:
        print(f"[*] Next scheduled race: {next_trigger.strftime('%Y-%m-%d %H:%M:%S')}")
    sys.stdout.flush()

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Daemon stopped by user.")

# ------------------------------------------------------------------------------
# 6. CLI ENTRY POINT
# ------------------------------------------------------------------------------
if __name__ == "__main__":
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

    parser = argparse.ArgumentParser(description="HORSE HAVOC VPS Autonomous Production Runner")
    parser.add_argument("-o", "--output", default="final_short.mp4", help="Output MP4 video path (default: final_short.mp4)")
    parser.add_argument("--test", action="store_true", help="Run fast dry-run test (10s video) for VPS verification")
    parser.add_argument("--live-upload", action="store_true", help="Perform live upload to YouTube/TikTok/Instagram even in test mode")
    parser.add_argument("--no-dispatch", action="store_true", help="Skip all network social dispatch and notifications")
    parser.add_argument("--seed", type=int, default=None, help="Fixed random seed (default: Dynamic random selection)")
    parser.add_argument("--daemon", action="store_true", help="Run as continuous daemon instead of one-shot execution")
    parser.add_argument("--times", default="00:00,12:00", help="Daily trigger times in 24h format for daemon mode (default: '00:00,12:00')")
    parser.add_argument("--time", default=None, help="Single trigger time alias (e.g. '12:00')")

    # Platform toggles
    parser.add_argument("--all", action="store_true", help="Enable all social platforms (YouTube, TikTok, Instagram)")
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

    # Track Theme Preset
    parser.add_argument("--track", choices=["auto", "classic_turf", "desert_dunes", "cyber_neon", "random"], default="auto", help="Track theme preset (default: auto)")

    # Celebrity Category Preset
    parser.add_argument("--group", "--category", dest="group", choices=["auto", "football", "streamers", "tech_business", "world_leaders", "pop_culture", "random"], default="auto", help="Celebrity category theme (default: auto)")

    args = parser.parse_args()

    enable_yt, enable_tt, enable_ig = resolve_platforms(
        args.all,
        args.youtube, args.no_youtube,
        args.tiktok, args.no_tiktok,
        args.instagram, args.no_instagram
    )

    if args.daemon:
        times = [args.time] if args.time else [t.strip() for t in args.times.split(",") if t.strip()]
        run_daemon_scheduler(
            times_list=times,
            is_test=args.test,
            no_dispatch=args.no_dispatch,
            enable_youtube=enable_yt,
            enable_tiktok=enable_tt,
            enable_instagram=enable_ig,
            youtube_privacy=args.privacy,
            track=args.track,
            group=args.group
        )
    else:
        execute_production_run(
            is_test=args.test,
            no_dispatch=args.no_dispatch,
            output_file=args.output,
            seed=args.seed,
            live_upload=args.live_upload,
            enable_youtube=enable_yt,
            enable_tiktok=enable_tt,
            enable_instagram=enable_ig,
            youtube_privacy=args.privacy,
            track=args.track,
            group=args.group
        )

