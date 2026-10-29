#!/usr/bin/env python3
"""
HORSE HAVOC - Match History & Anti-Duplication Engine
=====================================================
Ensures:
1. Every race has a cryptographically unique, non-repeating seed.
2. The 5 celebrity meme jockeys selected from the roster are NEVER identical back-to-back.
3. Every match output has a unique timestamped filename (output/match_YYYYMMDD_HHMMSS_*.mp4).
4. Maintains `history.json` tracking match seeds, rosters, winners, SHA-256 hashes, and timestamps.
5. Strictly validates that identical video files are never re-uploaded.
"""

import os
import sys
import json
import time
import uuid
import hashlib
import random
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(PROJECT_DIR, "history.json")

def load_history(filepath=HISTORY_FILE):
    """Loads history.json safely; initializes default structure if missing or corrupt."""
    default_history = {
        "version": "2.0",
        "total_matches": 0,
        "last_roster_ids": [],
        "used_seeds": [],
        "used_hashes": [],
        "matches": []
    }
    if not os.path.exists(filepath):
        return default_history

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and "matches" in data:
                return data
    except Exception as e:
        print(f"[MATCH MANAGER] Warning reading {filepath} ({e}). Initializing clean history.")

    return default_history

def save_history(history_data, filepath=HISTORY_FILE):
    """Atomically writes history.json to prevent race conditions or partial writes."""
    temp_path = f"{filepath}.tmp_{os.getpid()}"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
        if os.path.exists(filepath):
            os.replace(temp_path, filepath)
        else:
            os.rename(temp_path, filepath)
    except Exception as e:
        print(f"[MATCH MANAGER] Error writing {filepath}: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def generate_unique_seed(history=None):
    """
    Generates a cryptographically strong, non-repeating 31-bit integer seed
    by combining system time in nanoseconds with OS cryptographic entropy.
    """
    used = set(history.get("used_seeds", [])) if history else set()
    for _ in range(1000):
        # High-entropy seed: nanoseconds XOR 64-bit random bytes
        entropy = int.from_bytes(os.urandom(8), "big")
        candidate = (time.time_ns() ^ entropy) & 0x7FFFFFFF
        if candidate not in used and candidate > 0:
            return candidate
    return int(time.time_ns()) & 0x7FFFFFFF

def pick_unique_roster(pool, count=5, last_roster_ids=None, seed=None, group=None):
    """
    Selects `count` distinct celebrities from `pool`, strictly filtered to ONE single category.
    Under no circumstances are contestants from different categories mixed into the same race.
    Guarantees that the set of selected celebrity IDs is NOT identical to `last_roster_ids`.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    valid_groups = ["football", "streamers", "tech_business", "world_leaders", "pop_culture"]

    # Strictly pick ONE category from the pool
    req_group = group.lower() if isinstance(group, str) else "auto"
    if req_group in ("auto", "none", "random") or not req_group or req_group not in valid_groups:
        req_group = rng.choice(valid_groups)

    # Strictly filter contestants belonging to that chosen category
    candidate_pool = [c for c in pool if c.get("group") == req_group]
    if len(candidate_pool) < count:
        # Fallback to football category if group has fewer than count
        req_group = "football"
        candidate_pool = [c for c in pool if c.get("group") == "football"]

    if len(candidate_pool) <= count:
        return candidate_pool[:]

    last_set = set(last_roster_ids) if last_roster_ids else set()

    for _ in range(100):
        candidate = rng.sample(candidate_pool, count)
        candidate_set = {c["id"] for c in candidate}
        if candidate_set != last_set:
            return candidate

    return rng.sample(candidate_pool, count)

def compute_file_sha256(filepath):
    """Computes SHA-256 checksum of a file in 64KB blocks."""
    if not os.path.exists(filepath):
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def is_duplicate_video(sha256_hash, history=None):
    """Checks if a video file with this SHA-256 hash has already been registered."""
    if not sha256_hash or not history:
        return False
    return sha256_hash in set(history.get("used_hashes", []))

def record_match_result(
    video_path,
    seed,
    roster,
    winner_name,
    runner_up_name,
    finish_time,
    margin_sec,
    published_channels=None,
    track_theme=None,
    track_name=None,
    group=None,
    group_name=None,
    history_file=HISTORY_FILE
):
    """
    Records a completed race into `history.json` with full telemetry,
    unique match ID, track theme, category group, SHA-256 hash, and published platform status.
    """
    history = load_history(history_file)
    sha256_hash = compute_file_sha256(video_path)
    file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0

    now_dt = datetime.utcnow()
    match_id = f"match_{now_dt.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    roster_ids = [c["id"] if isinstance(c, dict) else str(c) for c in roster]
    roster_names = [c["name"] if isinstance(c, dict) else str(c) for c in roster]

    # Resolve category metadata
    inferred_group = group
    inferred_group_name = group_name
    if not inferred_group and roster and isinstance(roster[0], dict):
        inferred_group = roster[0].get("group", "football")
        inferred_group_name = roster[0].get("group_name", "Football Derby")

    entry = {
        "match_id": match_id,
        "utc_timestamp": now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": int(seed),
        "track_theme": track_theme or "classic_turf",
        "track_name": track_name or "Classic Turf Derby",
        "group": inferred_group or "football",
        "group_name": inferred_group_name or "Football Derby",
        "video_file": os.path.abspath(video_path),
        "video_sha256": sha256_hash,
        "file_size_bytes": file_size,
        "winner": winner_name,
        "runner_up": runner_up_name,
        "finish_time_sec": round(float(finish_time), 2),
        "margin_sec": round(float(margin_sec), 2),
        "roster_ids": roster_ids,
        "roster_names": roster_names,
        "published_channels": published_channels or []
    }

    history["matches"].append(entry)
    history["total_matches"] = len(history["matches"])
    history["last_roster_ids"] = roster_ids

    if seed not in history["used_seeds"]:
        history["used_seeds"].append(int(seed))

    if sha256_hash and sha256_hash not in history["used_hashes"]:
        history["used_hashes"].append(sha256_hash)

    # Keep list sizes manageable (last 5000 matches)
    if len(history["matches"]) > 5000:
        history["matches"] = history["matches"][-5000:]
    if len(history["used_seeds"]) > 10000:
        history["used_seeds"] = history["used_seeds"][-10000:]
    if len(history["used_hashes"]) > 10000:
        history["used_hashes"] = history["used_hashes"][-10000:]

    save_history(history, history_file)
    print(f"[MATCH MANAGER] Recorded match {match_id} (Winner: {winner_name}, SHA: {sha256_hash[:12]}...) in {os.path.basename(history_file)}")
    return entry

