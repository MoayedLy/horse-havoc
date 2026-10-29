#!/usr/bin/env python3
"""
HORSE HAVOC - Automated Retention Policy & Disk Cleanup Engine
==============================================================
Manages server disk space for 24/7 autonomous VPS deployments:
1. Deletes video files older than 24 hours (1 day / 86,400s) in `output/` and root capture dirs.
2. Immediately cleans intermediate/temporary render artifacts (audio stems, raw clips).
3. Strictly protects critical assets, credentials, source code, and `history.json`.
"""

import os
import sys
import time
import glob
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "output"

DEFAULT_RETENTION_HOURS = float(os.getenv("RETENTION_MAX_AGE_HOURS", "24.0"))

# Critical files that must NEVER be deleted
STRICT_PROTECTED_FILES = {
    "history.json",
    ".env",
    ".env.example",
    "token.json",
    "tiktok_token.json",
    "instagram_token.json",
    "client_secrets.json",
    "tiktok_code_verifier.txt",
    "README.md",
    "PROJECT_STATUS_AND_HANDOVER.md",
    "TIKTOK_SETUP.md",
    "requirements.txt"
}
STRICT_PROTECTED_FILES_LOWER = {f.lower() for f in STRICT_PROTECTED_FILES}

# Directories that must NEVER be scanned or pruned
STRICT_PROTECTED_DIRS = {
    "assets",
    "venv",
    ".git",
    "brain",
    ".gemini",
    "logs"
}

# Temporary intermediate file patterns to sweep up immediately
INTERMEDIATE_PATTERNS = [
    "temp_clean_*.mp4",
    "temp_music_*.wav",
    "*_temp_audio.wav",
    "*_temp_video.mp4",
    "temp_*.mp4",
    "temp_*.wav",
    "*.tmp_*",
    "*.tmp"
]

def clean_intermediate_artifacts(project_dir=PROJECT_DIR, dry_run=False):
    """
    Deletes temporary audio files, captured raw clips, and intermediate muxing artifacts.
    Runs immediately after video assembly and dispatch.
    """
    project_dir = str(project_dir)
    removed_files = []
    reclaimed_bytes = 0

    scan_dirs = [project_dir, os.path.join(project_dir, "output")]

    for s_dir in scan_dirs:
        if not os.path.exists(s_dir):
            continue
        for pattern in INTERMEDIATE_PATTERNS:
            match_path = os.path.join(s_dir, pattern)
            for fpath in glob.glob(match_path):
                fname = os.path.basename(fpath)
                if fname in STRICT_PROTECTED_FILES or fname.lower() in STRICT_PROTECTED_FILES_LOWER:
                    continue
                try:
                    fsize = os.path.getsize(fpath)
                    if not dry_run:
                        os.remove(fpath)
                    removed_files.append(fname)
                    reclaimed_bytes += fsize
                    prefix = "[CLEANUP DRY-RUN]" if dry_run else "[CLEANUP]"
                    print(f"{prefix} Removed intermediate artifact: {fname} ({fsize / (1024*1024):.2f} MB)")
                except Exception as e:
                    print(f"[CLEANUP ERROR] Could not remove {fname}: {e}")

    return {
        "removed_files": removed_files,
        "count": len(removed_files),
        "reclaimed_bytes": reclaimed_bytes,
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2)
    }

def clean_old_videos(max_age_hours=DEFAULT_RETENTION_HOURS, output_dir=OUTPUT_DIR, project_dir=PROJECT_DIR, dry_run=False):
    """
    Scans video directories and permanently deletes MP4 files older than `max_age_hours` (default: 24.0h).
    Strictly safeguards critical assets, configurations, and credentials.
    """
    project_dir = str(project_dir)
    output_dir = str(output_dir)
    now = time.time()
    max_age_seconds = max_age_hours * 3600.0

    removed_files = []
    reclaimed_bytes = 0

    # 1. Scan output/ directory for archived match videos
    target_video_paths = []
    if os.path.exists(output_dir):
        target_video_paths.extend(glob.glob(os.path.join(output_dir, "*.mp4")))

    # 2. Also scan root project directory for legacy test / capture videos
    for root_mp4 in glob.glob(os.path.join(project_dir, "*.mp4")):
        base_name = os.path.basename(root_mp4)
        if base_name in STRICT_PROTECTED_FILES:
            continue
        target_video_paths.append(root_mp4)

    print("=" * 70)
    print(" [CLEANUP] RUNNING AUTOMATED VIDEO RETENTION & PRUNING POLICY")
    print("=" * 70)
    print(f" * Retention Window   : {max_age_hours:.1f} hours ({max_age_hours / 24:.1f} days)")
    print(f" * Target Directory   : {output_dir}")
    print(f" * Mode               : {'DRY RUN (Scan Only)' if dry_run else 'ACTIVE PURGE'}")
    print(f" * Protected Files    : {len(STRICT_PROTECTED_FILES)} core files safeguards active")
    print("-" * 70)

    for vid_path in target_video_paths:
        fname = os.path.basename(vid_path)

        # Defense-in-depth: Never delete protected files
        if fname in STRICT_PROTECTED_FILES or fname.lower() in STRICT_PROTECTED_FILES_LOWER:
            continue

        try:
            mtime = os.path.getmtime(vid_path)
            age_seconds = now - mtime
            age_hours = age_seconds / 3600.0

            if age_seconds > max_age_seconds:
                fsize = os.path.getsize(vid_path)
                fsize_mb = fsize / (1024 * 1024)

                prefix = "[CLEANUP DRY-RUN]" if dry_run else "[CLEANUP]"
                if not dry_run:
                    os.remove(vid_path)

                print(f"{prefix} Deleted old video to save disk space: {fname} ({age_hours:.1f}h old, {fsize_mb:.2f} MB freed)")
                removed_files.append({
                    "filename": fname,
                    "path": vid_path,
                    "age_hours": round(age_hours, 1),
                    "size_mb": round(fsize_mb, 2)
                })
                reclaimed_bytes += fsize

                # Prune matching archived metadata in output/ if it exists
                meta_candidate = os.path.splitext(vid_path)[0] + ".json"
                if os.path.exists(meta_candidate):
                    meta_base = os.path.basename(meta_candidate)
                    if meta_base not in STRICT_PROTECTED_FILES and meta_base.lower() not in STRICT_PROTECTED_FILES_LOWER:
                        try:
                            meta_size = os.path.getsize(meta_candidate)
                            if not dry_run:
                                os.remove(meta_candidate)
                            reclaimed_bytes += meta_size
                            print(f"{prefix} Deleted accompanying metadata: {meta_base}")
                        except Exception as me:
                            print(f"[CLEANUP ERROR] Could not remove accompanying metadata {meta_base}: {me}")
        except Exception as e:
            print(f"[CLEANUP ERROR] Failed processing {fname}: {e}")

    total_mb = reclaimed_bytes / (1024 * 1024)
    print("-" * 70)
    print(f"[CLEANUP SUMMARY] Pruned {len(removed_files)} old video(s) | Reclaimed: {total_mb:.2f} MB disk space")
    print("=" * 70)

    return {
        "status": "success",
        "dry_run": dry_run,
        "max_age_hours": max_age_hours,
        "removed_videos": removed_files,
        "count": len(removed_files),
        "reclaimed_bytes": reclaimed_bytes,
        "reclaimed_mb": round(total_mb, 2)
    }

def enforce_single_video_policy(project_dir=PROJECT_DIR, output_dir=OUTPUT_DIR, current_target=None):
    """
    Ultra-tight disk quota enforcement (160 MB server limit):
    Ensures strictly at most ONE video file exists on disk (the current/latest video).
    Deletes any previously rendered .mp4 files and orphan metadata archives.
    """
    project_dir = str(project_dir)
    output_dir = str(output_dir)
    reclaimed_bytes = 0
    removed = []

    candidates = []
    if os.path.exists(output_dir):
        for f in glob.glob(os.path.join(output_dir, "*.mp4")):
            candidates.append(f)
    for f in glob.glob(os.path.join(project_dir, "*.mp4")):
        candidates.append(f)

    # Sort newest first
    candidates.sort(key=lambda x: os.path.getmtime(x) if os.path.exists(x) else 0, reverse=True)

    keep_abs = os.path.abspath(current_target) if current_target else (os.path.abspath(candidates[0]) if candidates else None)

    for vid in candidates:
        abs_v = os.path.abspath(vid)
        if keep_abs and abs_v == keep_abs:
            continue
        try:
            sz = os.path.getsize(vid)
            os.remove(vid)
            reclaimed_bytes += sz
            removed.append(os.path.basename(vid))
            print(f"[NANO DISK] Deleted previous video: {os.path.basename(vid)} ({sz / (1024*1024):.2f} MB freed)")

            json_cand = os.path.splitext(vid)[0] + ".json"
            if os.path.exists(json_cand) and os.path.basename(json_cand) not in STRICT_PROTECTED_FILES:
                try:
                    os.remove(json_cand)
                except Exception:
                    pass
        except Exception as e:
            print(f"[NANO DISK ERROR] Could not remove {vid}: {e}")

    return {
        "status": "success",
        "removed": removed,
        "reclaimed_mb": round(reclaimed_bytes / (1024 * 1024), 2)
    }

def run_retention_policy(max_age_hours=DEFAULT_RETENTION_HOURS, dry_run=False, single_video_mode=True, current_target=None):
    """
    Master cleanup entry point:
    1. Sweeps up all intermediate and temporary audio/video clips.
    2. Enforces single-video policy (if single_video_mode is True).
    3. Enforces 24-hour video retention policy.
    """
    inter_res = clean_intermediate_artifacts(dry_run=dry_run)
    single_res = {"reclaimed_mb": 0.0}
    if single_video_mode and not dry_run:
        single_res = enforce_single_video_policy(current_target=current_target)
    video_res = clean_old_videos(max_age_hours=max_age_hours, dry_run=dry_run)

    return {
        "intermediate": inter_res,
        "single_video": single_res,
        "videos": video_res,
        "total_reclaimed_mb": round(inter_res["reclaimed_mb"] + single_res.get("reclaimed_mb", 0.0) + video_res["reclaimed_mb"], 2)
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="HORSE HAVOC Server File Retention & Disk Cleanup")
    parser.add_argument("--hours", type=float, default=24.0, help="Retention period threshold in hours (default: 24.0)")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report candidates without deleting files")
    args = parser.parse_args()

    run_retention_policy(max_age_hours=args.hours, dry_run=args.dry_run)
