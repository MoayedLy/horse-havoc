"""
HORSE HAVOC - Master Autonomous Production Pipeline
===================================================
System Architecture:
  Game Simulation -> Video Capture -> Post-Processing/Metadata -> Scheduling & Dispatch

Executes:
1. 2D Headless Game Simulation with randomized Meme Celebrity Riders.
2. FFmpeg pipe recording into 1080x1920 (9:16 Vertical) MP4.
3. Audio post-processing: Crisp in-game sound effects + Driving 130 BPM Arcade Music (no TTS).
4. Viral metadata generation: Gemini 1.5 Flash API with built-in template fallback.
5. Automated Dispatcher: Telegram Bot, Webhooks, and direct Social Media stubs.
"""

import os
import sys
import time
import json
import math
import wave
import struct
import shutil
import random
import uuid
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

# Headless Linux & VPS Environment Configuration
if "DISPLAY" not in os.environ or not os.environ["DISPLAY"]:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
import pygame

from config import FPS, SCREEN_WIDTH, SCREEN_HEIGHT, HORSE_PROFILES, NUM_HORSES
from record_race import resolve_ffmpeg_path, record_race
from hud import HUD
from game import RaceGame
from publisher import dispatch_video
import metadata_engine
import match_manager
import cleanup_manager

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None

class RaceTelemetryHook:
    """Non-invasively hooks into HUD commentary and RaceGame to capture race telemetry."""
    def __init__(self):
        self.events = []
        self.active_game = None
        self._orig_game_init = RaceGame.__init__
        self._orig_push_commentary = HUD.push_commentary

    def __enter__(self):
        hook_self = self
        def hooked_init(game_self, *args, **kwargs):
            hook_self._orig_game_init(game_self, *args, **kwargs)
            hook_self.active_game = game_self

        def hooked_push(hud_self, message):
            hook_self._orig_push_commentary(hud_self, message)
            if hook_self.active_game:
                g = hook_self.active_game
                hook_self.events.append({
                    "frame": g.frame_idx,
                    "time_sec": round(g.race_time_sec, 2),
                    "message": message
                })

        RaceGame.__init__ = hooked_init
        HUD.push_commentary = hooked_push
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        RaceGame.__init__ = self._orig_game_init
        HUD.push_commentary = self._orig_push_commentary

def generate_arcade_music(duration_sec, output_wav_path, sample_rate=44100):
    """Synthesizes a driving 130 BPM arcade electronic music track in pure Python."""
    bpm = 130.0
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0
    total_samples = int(duration_sec * sample_rate)
    left = [0.0] * total_samples
    right = [0.0] * total_samples

    # Kick
    kick_samples = []
    for i in range(int(0.20 * sample_rate)):
        t = i / sample_rate
        freq = 45.0 + 120.0 * math.exp(-32.0 * t)
        v = math.sin(2.0 * math.pi * freq * t)
        env = math.exp(-16.0 * t)
        kick_samples.append(v * env * 0.75)

    # Snare
    snare_samples = []
    for i in range(int(0.18 * sample_rate)):
        t = i / sample_rate
        noise = random.uniform(-1.0, 1.0)
        tone = math.sin(2.0 * math.pi * 190.0 * t)
        env = math.exp(-22.0 * t)
        snare_samples.append((0.7 * noise + 0.3 * tone) * env * 0.45)

    # Hats
    hihat_samples = [random.uniform(-1.0, 1.0) * math.exp(-85.0 * (i / sample_rate)) * 0.22 for i in range(int(0.045 * sample_rate))]
    openhat_samples = [random.uniform(-1.0, 1.0) * math.exp(-30.0 * (i / sample_rate)) * 0.28 for i in range(int(0.12 * sample_rate))]

    bass_chords = [73.42, 87.31, 65.41, 98.00]  # Dm -> F -> C -> G
    arp_notes = [293.66, 349.23, 392.00, 440.00, 523.25, 587.33]

    total_steps = int(duration_sec / step_sec)
    for step in range(total_steps):
        t_start = step * step_sec
        start_idx = int(t_start * sample_rate)
        if start_idx >= total_samples:
            break

        beat_in_bar = (step // 4) % 4
        sub_step = step % 4
        bar_idx = (step // 16)
        chord_root = bass_chords[bar_idx % len(bass_chords)]

        if sub_step == 0:
            for j, s in enumerate(kick_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s
                    right[idx] += s

        if sub_step == 0 and (beat_in_bar == 1 or beat_in_bar == 3):
            for j, s in enumerate(snare_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 0.95
                    right[idx] += s * 0.95

        if sub_step == 2:
            for j, s in enumerate(openhat_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 0.70
                    right[idx] += s * 1.10
        elif sub_step in (0, 1, 3):
            for j, s in enumerate(hihat_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 1.0
                    right[idx] += s * 0.8

        # Rolling 16th Bass
        bass_len = int(step_sec * 0.85 * sample_rate)
        for j in range(bass_len):
            idx = start_idx + j
            if idx < total_samples:
                t = j / sample_rate
                saw = 2.0 * ((t * chord_root) % 1.0) - 1.0
                sub = math.sin(2.0 * math.pi * chord_root * 0.5 * t)
                env = math.exp(-12.0 * t)
                v = (0.55 * saw + 0.45 * sub) * env * 0.32
                left[idx] += v
                right[idx] += v

        # Arp lead
        note_idx = (step * 3) % len(arp_notes)
        arp_freq = arp_notes[note_idx]
        arp_len = int(step_sec * 0.90 * sample_rate)
        pan = 0.5 + 0.35 * math.sin(step * 0.6)
        for j in range(arp_len):
            idx = start_idx + j
            if idx < total_samples:
                t = j / sample_rate
                sq = 1.0 if math.sin(2.0 * math.pi * arp_freq * t) > 0 else -1.0
                env = math.exp(-20.0 * t)
                v = sq * env * 0.14
                left[idx] += v * (1.0 - pan)
                right[idx] += v * pan

    # Fade in & out
    fade_in = int(1.5 * sample_rate)
    fade_out = int(2.5 * sample_rate)
    for i in range(min(fade_in, total_samples)):
        left[i] *= (i / fade_in)
        right[i] *= (i / fade_in)
    for i in range(min(fade_out, total_samples)):
        idx = total_samples - 1 - i
        left[idx] *= (i / fade_out)
        right[idx] *= (i / fade_out)

    peak = max(max(abs(l) for l in left), max(abs(r) for r in right), 0.001)
    gain = 16000.0 / peak
    interleaved = []
    for i in range(total_samples):
        interleaved.append(int(max(-32767, min(32767, left[i] * gain))))
        interleaved.append(int(max(-32767, min(32767, right[i] * gain))))

    with wave.open(output_wav_path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(interleaved)}h", *interleaved))

def generate_metadata_via_gemini(winner_name, winner_number, winner_quote, archetype, finish_time, lead_changes, weapon_hits, api_key):
    """Generates viral social media titles and copy using Gemini 1.5 Flash REST API."""
    if not requests or not api_key:
        return None

    prompt = f"""You are an elite viral gaming social media manager for YouTube Shorts, TikTok, and Instagram Reels.
A chaotic 2D vertical horse racing match of 'Horse Havoc' just completed.
Match Highlights:
- Winning Celebrity Jockey: {winner_name} (Horse #{winner_number})
- Celebrity Signature Quote: "{winner_quote}"
- Archetype: {archetype}
- Winning Time: {finish_time:.2f}s
- In-Game Drama: {lead_changes} Lead Changes, {weapon_hits} Weapon Stuns (Guided Rockets, Lasers, Mud Bombs)

Generate high CTR viral copy in strict JSON format with exactly these keys:
{{
  "primary_title": "Extreme curiosity or hype hook title under 55 characters with emojis",
  "alternative_titles": ["Alternative title 1", "Alternative title 2", "Alternative title 3"],
  "description": "Punchy 3-line description with match outcome and a call to action asking viewers who they backed",
  "hashtags": ["#Shorts", "#HorseHavoc", "#Viral", "#Gaming", "#TikTokGaming", "#{winner_name.replace(' ', '')}"]
}}
Only return raw valid JSON. No markdown backticks."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 400}
    }

    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            data = r.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            # Clean possible markdown fence
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            res = json.loads(raw_text.strip())
            res["source"] = "Gemini 1.5 Flash"
            return res
    except Exception as e:
        print(f"[!] Gemini API fallback triggered: {e}")

    return None

def generate_template_metadata(winner_name, winner_number, winner_quote, archetype, finish_time, lead_changes, weapon_hits, duration_sec):
    """High-performing fallback viral metadata generator tailored dynamically to the winning celebrity."""
    quote_tag = f" ({winner_quote})" if winner_quote else ""

    titles = [
        f"WHO WILL WIN?! 😱 {winner_name} In An INSANE 45s Finish! 🐎🔥",
        f"The ending had me screaming! 😭🚀 {winner_name} pulls off the IMPOSSIBLE! #HorseHavoc",
        f"45 Seconds Of Pure Chaos! Can {winner_name} Survive The Rocket Crossfire?! 💣🐎",
        f"{winner_name} vs Top Celebrities In A Wild 45-Second AI Horse Race! 🏁🤯"
    ]

    description = (
        f"🏁 HORSE HAVOC: CELEBRITY MEME DERBY 🏁\n"
        f"🏆 WINNER: {winner_name} (Horse #{winner_number}){quote_tag}\n"
        f"⏱️ Winning Time: {finish_time:.2f}s  •  Archetype: {archetype}\n"
        f"💥 Match Drama: {lead_changes} Lead Changes | {weapon_hits} Weapon Stuns\n\n"
        f"Which celebrity were you rooting for? Drop your pick in the comments! 👇🐎\n\n"
        f"#HorseHavoc #CelebrityDerby #Gaming #Shorts #TikTokGaming #ViralGaming #AIHorses #{winner_name.replace(' ', '')}"
    )

    hashtags = [
        "#HorseHavoc", "#CelebrityDerby", "#Gaming", "#IndieGame", "#Shorts",
        "#TikTokGaming", "#Viral", "#AIHorses", "#EpicFinish", "#Reels",
        f"#{winner_name.replace(' ', '')}"
    ]

    return {
        "primary_title": titles[0],
        "alternative_titles": titles[1:],
        "description": description,
        "hashtags": hashtags,
        "source": "Celebrity Template Generator"
    }

def run_pipeline(
    seed=None,
    is_test=False,
    no_dispatch=False,
    output_file="final_short.mp4",
    crf=23,
    preset="veryfast",
    live_upload=False,
    enable_youtube=True,
    enable_tiktok=True,
    enable_instagram=True,
    youtube_privacy="public",
    track=None,
    group=None
):
    """
    Executes the complete autonomous production loop:
    Simulation -> Capture -> Audio Post-Processing -> AI Metadata -> Dispatch -> History Archival
    """
    start_time = time.time()
    ffmpeg_exe = resolve_ffmpeg_path()
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)

    # Enforce ultra-tight disk quota (160 MB limit): purge previous videos before rendering
    try:
        cleanup_manager.enforce_single_video_policy(output_dir=output_dir, current_target=None)
    except Exception as ce:
        print(f"[NANO DISK NOTICE] Pre-run video sweep notice: {ce}")

    # Load match history for anti-duplication and unique seed/roster selection
    import match_manager
    from celebrities import CELEBRITY_POOL
    history = match_manager.load_history()

    active_seed = seed if seed is not None else match_manager.generate_unique_seed(history)
    last_roster = history.get("last_roster_ids", [])
    active_roster = match_manager.pick_unique_roster(CELEBRITY_POOL, count=NUM_HORSES, last_roster_ids=last_roster, seed=active_seed, group=group)
    active_group = active_roster[0].get("group", "football") if isinstance(active_roster[0], dict) else "football"
    active_group_name = active_roster[0].get("group_name", "Football Derby") if isinstance(active_roster[0], dict) else "Football Derby"
    roster_names = [c["name"] for c in active_roster]

    now_dt = datetime.now()
    timestamp_str = now_dt.strftime("%Y%m%d_%H%M%S")
    match_uuid = uuid.uuid4().hex[:6]

    temp_clean_mp4 = f"temp_clean_{int(time.time())}_{match_uuid}.mp4"
    temp_music_wav = f"temp_music_{int(time.time())}_{match_uuid}.wav"
    metadata_json_path = "final_short_metadata.json"
    metadata_txt_path = "final_short_metadata.txt"

    max_seconds = 12.0 if is_test else 55.0

    print("=" * 70)
    print(" [HORSE HAVOC] MASTER AUTONOMOUS PRODUCTION RUNNER")
    print("=" * 70)
    print(f" * Timestamp     : {timestamp_str}")
    print(f" * Mode          : {'TEST / FAST DRY-RUN' if is_test else 'FULL 45S MATCH PRODUCTION'}")
    print(f" * Output Target : {output_file}")
    print(f" * Video Quality : 1080x1920 @ 60 FPS (CRF: {crf}, Preset: {preset if not is_test else 'ultrafast'})")
    print(f" * Random Seed   : {active_seed} (Cryptographically Unique)")
    print(f" * Category Theme: {active_group_name} ({active_group})")
    print(f" * Racer Roster  : {', '.join(roster_names)}")
    print(f" * FFmpeg Binary : {ffmpeg_exe}")
    print("-" * 70)

    # -------------------------------------------------------------
    # 1. SIMULATION & VIDEO CAPTURE
    # -------------------------------------------------------------
    print("\n[PHASE 1/4] Simulating race & capturing 1080x1920 60 FPS frames...")
    hook = RaceTelemetryHook()
    with hook:
        record_race(
            output_file=temp_clean_mp4,
            fps=FPS,
            seed=active_seed,
            crf=crf if not is_test else 20,
            preset=preset if not is_test else "ultrafast",
            max_seconds=max_seconds,
            roster=active_roster,
            track=track,
            group=active_group
        )

    events = hook.events
    active_game = hook.active_game
    track_theme = getattr(active_game, "track_theme", "classic_turf")
    track_name = getattr(active_game, "track_name", "Classic Turf Derby")

    order = active_game.finish_order if active_game and active_game.finish_order else (active_game.horses if active_game else [])
    winner = order[0] if len(order) > 0 else None
    runner_up = order[1] if len(order) > 1 else None
    third_place = order[2] if len(order) > 2 else None

    winner_name = winner.name if winner else "Cristiano Ronaldo"
    runner_up_name = runner_up.name if runner_up else "Lionel Messi"
    third_name = third_place.name if third_place else "MrBeast"

    winner_number = winner.number if winner else 1
    winner_quote = getattr(winner, "quote", "")
    winner_arch = getattr(winner, "archetype", "Champion")
    winner_time = winner.finish_time if (winner and winner.finish_time) else 40.37
    runner_up_time = runner_up.finish_time if (runner_up and runner_up.finish_time) else 40.55

    margin_sec = abs(runner_up_time - winner_time)
    if margin_sec <= 0.01:
        margin_sec = 0.12

    total_frames = active_game.frame_idx if active_game else 2645
    race_duration_sec = total_frames / FPS

    lead_changes = sum(1 for e in events if "SURGES INTO 1ST" in e.get("message", ""))
    weapon_hits = sum(1 for e in events if "HIT!" in e.get("message", "") or "STUNNED" in e.get("message", ""))

    print(f"\n[OK] Capture Complete!")
    print(f" * Duration     : {race_duration_sec:.2f}s ({total_frames} frames)")
    print(f" * Winner (1st) : {winner_name} (#{winner_number}) in {winner_time:.2f}s")
    print(f" * Runner-Up    : {runner_up_name} (+{margin_sec:.2f}s)")
    if third_place:
        print(f" * 3rd Place    : {third_name}")
    print(f" * Match Drama  : {len(events)} events ({lead_changes} lead changes, {weapon_hits} weapon stuns)")

    # Write game_events.json containing active_category for title/description generator
    game_events_payload = {
        "active_category": active_group,
        "category_name": active_group_name,
        "track_theme": track_theme,
        "track_name": track_name,
        "winner": winner_name,
        "runner_up": runner_up_name,
        "third_place": third_name,
        "finish_time": round(winner_time, 2),
        "margin_sec": round(margin_sec, 2),
        "lead_changes": lead_changes,
        "weapon_hits": weapon_hits,
        "roster": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "category": c.get("group", active_group)
            } for c in active_roster
        ],
        "events": events
    }
    try:
        with open("game_events.json", "w", encoding="utf-8") as f:
            json.dump(game_events_payload, f, ensure_ascii=False, indent=2)
    except Exception as ge_err:
        print(f"[PIPELINE] Warning writing game_events.json: {ge_err}")

    # -------------------------------------------------------------
    # 2. AUDIO POST-PROCESSING & MUSIC MUXING
    # -------------------------------------------------------------
    print("\n[PHASE 2/4] Synthesizing 130 BPM arcade music & mixing master audio (192k AAC)...")
    generate_arcade_music(race_duration_sec, temp_music_wav)

    # SFX 100% volume + Arcade Music 32% volume
    mix_filter = (
        "[0:a]volume=1.0[sfx]; "
        "[1:a]volume=0.32[bgm]; "
        "[sfx][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    mux_cmd = [
        ffmpeg_exe, "-y",
        "-i", temp_clean_mp4,
        "-i", temp_music_wav,
        "-filter_complex", mix_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        output_file
    ]

    subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Clean intermediate temp files
    for tf in [temp_clean_mp4, temp_music_wav]:
        if os.path.exists(tf):
            try:
                os.remove(tf)
            except Exception:
                pass
    try:
        cleanup_manager.clean_intermediate_artifacts()
    except Exception as ce:
        print(f"[CLEANUP NOTICE] Intermediate artifacts sweep notice: {ce}")

    # Unique archived filename preserving every match history (Metadata JSON archive only; 1-video quota enforced)
    winner_slug = winner_name.lower().replace(' ', '_').replace('.', '')
    archive_video_path = output_file
    archive_meta_path = os.path.join(output_dir, f"match_{timestamp_str}_{winner_slug}_{match_uuid}.json")

    # Verify SHA-256 hash against duplication
    video_hash = match_manager.compute_file_sha256(output_file)
    if match_manager.is_duplicate_video(video_hash, history):
        print(f"[!] Warning: Video SHA-256 ({video_hash[:12]}...) exists in history.json! Proceeding with match archival.")

    # -------------------------------------------------------------
    # 3. AI / DYNAMIC MATCH-TAILORED VIRAL METADATA GENERATION
    # -------------------------------------------------------------
    print("\n[PHASE 3/4] Generating tailored multi-platform metadata (YouTube, Instagram, TikTok)...")
    meta_engine_result = metadata_engine.generate_match_metadata(
        winner_name=winner_name,
        runner_up_name=runner_up_name,
        third_place_name=third_name,
        finish_time=winner_time,
        margin_sec=margin_sec,
        events=events,
        track_name=track_name,
        track_theme=track_theme,
        group_name=active_group_name,
        group_key=active_group,
        roster=active_roster
    )

    meta_full = {
        "timestamp": timestamp_str,
        "active_category": active_group,
        "category_name": active_group_name,
        "track_theme": track_theme,
        "track_name": track_name,
        "group": active_group,
        "group_name": active_group_name,
        "winner": {
            "name": winner_name,
            "number": winner_number,
            "quote": winner_quote,
            "archetype": winner_arch,
            "finish_time": round(winner_time, 2)
        },
        "runner_up": {
            "name": runner_up_name,
            "finish_time": round(runner_up_time, 2),
            "margin_sec": round(margin_sec, 2)
        },
        "video_duration_sec": round(race_duration_sec, 2),
        "primary_title": meta_engine_result["primary_title"],
        "description": meta_engine_result["description"],
        "hashtags": meta_engine_result["hashtags"],
        "tags_string": meta_engine_result["tags_string"],
        "key_clutch_event": meta_engine_result["key_clutch_event"],
        "youtube": meta_engine_result["youtube"],
        "instagram": meta_engine_result["instagram"],
        "tiktok": meta_engine_result["tiktok"],
        "metadata_engine": meta_engine_result["metadata_engine"]
    }

    # Save metadata JSON
    with open(metadata_json_path, "w", encoding="utf-8") as f:
        json.dump(meta_full, f, ensure_ascii=False, indent=2)

    # Save multi-platform ready-to-post TXT
    with open(metadata_txt_path, "w", encoding="utf-8") as f:
        f.write("======================================================================\n")
        f.write(f" HORSE HAVOC - MULTI-PLATFORM COPYWRITING (ENGINE: {meta_full['metadata_engine']})\n")
        f.write(f" MATCH: {winner_name} (1st) vs {runner_up_name} (2nd) | Margin: {margin_sec:.2f}s\n")
        f.write(f" CLUTCH EVENT: {meta_full['key_clutch_event']}\n")
        f.write("======================================================================\n\n")

        f.write("--- [1] YOUTUBE SHORTS ---\n")
        f.write(f"TITLE:\n{meta_full['youtube']['title']}\n\n")
        f.write(f"DESCRIPTION:\n{meta_full['youtube']['description']}\n\n")
        f.write(f"TAGS:\n{', '.join(meta_full['youtube']['tags'])}\n\n")

        f.write("--- [2] INSTAGRAM REELS ---\n")
        f.write(f"CAPTION:\n{meta_full['instagram']['caption']}\n\n")

        f.write("--- [3] TIKTOK ---\n")
        f.write(f"CAPTION:\n{meta_full['tiktok']['caption']}\n\n")

    # Also archive metadata in output/
    try:
        shutil.copy2(metadata_json_path, archive_meta_path)
    except Exception:
        pass

    print(f" * Engine        : {meta_full['metadata_engine']}")
    print(f" * Clutch Event  : {meta_full['key_clutch_event']}")
    print(f" * YouTube Title : {meta_full['youtube']['title']}")
    print(f" * TikTok Hook   : {meta_full['tiktok']['caption']}")
    print(f" * Metadata Logs : {os.path.abspath(metadata_json_path)}")
    print(f"                   {os.path.abspath(metadata_txt_path)}")

    # -------------------------------------------------------------
    # 4. DISPATCH & NOTIFICATION
    # -------------------------------------------------------------
    dispatch_results = {}
    if not no_dispatch:
        print("\n[PHASE 4/4] Triggering automated dispatcher (Telegram / Social Platforms)...")
        dispatch_is_test = False if live_upload else is_test
        try:
            dispatch_results = dispatch_video(
                output_file,
                meta_full,
                is_test=dispatch_is_test,
                enable_youtube=enable_youtube,
                enable_tiktok=enable_tiktok,
                enable_instagram=enable_instagram,
                youtube_privacy=youtube_privacy
            )
        except Exception as e:
            print(f"\n[PHASE 4/4] Notice: Uncaught dispatcher error ({e}). Remaining pipeline continues.")
            dispatch_results = {"status": "failed", "error": str(e)}
    else:
        print("\n[PHASE 4/4] Dispatch skipped (--no-dispatch specified).")

    # Record completed match into history.json for strict anti-duplication tracking
    successful_channels = [ch for ch, res in dispatch_results.items() if res.get("status") in ("success", "test_ok")]
    match_manager.record_match_result(
        video_path=archive_video_path if os.path.exists(archive_video_path) else output_file,
        seed=active_seed,
        roster=active_roster,
        winner_name=winner_name,
        runner_up_name=runner_up_name,
        finish_time=winner_time,
        margin_sec=margin_sec,
        published_channels=successful_channels,
        track_theme=track_theme,
        track_name=track_name,
        group=active_group,
        group_name=active_group_name
    )

    # -------------------------------------------------------------
    # 5. AUTOMATED DISK RETENTION & CLEANUP (24-Hour Retention)
    # -------------------------------------------------------------
    try:
        cleanup_manager.run_retention_policy(max_age_hours=24.0, single_video_mode=True, current_target=output_file)
    except Exception as ce:
        print(f"[CLEANUP NOTICE] Retention policy sweep notice: {ce}")

    elapsed_wall = time.time() - start_time
    print("\n" + "=" * 70)
    print(" PIPELINE EXECUTION FINISHED SUCCESSFULLY")
    print("=" * 70)
    print(f" * Master Output : {os.path.abspath(output_file)}")
    print(f" * Archive Video : {os.path.abspath(archive_video_path)}")
    print(f" * Archive Meta  : {os.path.abspath(archive_meta_path)}")
    print(f" * Video SHA-256 : {video_hash}")
    print(f" * Total Elapsed : {elapsed_wall:.1f} seconds")
    print("=" * 70)

    return {
        "status": "success",
        "video": output_file,
        "metadata": meta_full,
        "dispatch": dispatch_results
    }

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

    parser = argparse.ArgumentParser(description="HORSE HAVOC Master Pipeline Runner")
    parser.add_argument("-o", "--output", default="final_short.mp4", help="Output video path (default: final_short.mp4)")
    parser.add_argument("--test", action="store_true", help="Run in fast dry-run / verification test mode")
    parser.add_argument("--no-dispatch", action="store_true", help="Skip social dispatch and notifications")
    parser.add_argument("--seed", type=int, default=None, help="Fixed random seed (default: Dynamic)")
    parser.add_argument("--crf", type=int, default=18, help="H.264 video CRF quality (default: 18 - visually lossless)")
    parser.add_argument("--preset", default="slow", help="FFmpeg speed preset (default: slow)")
    parser.add_argument("--live-upload", action="store_true", help="Perform live upload to YouTube/TikTok/Instagram even in test mode")

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

    run_pipeline(
        seed=args.seed,
        is_test=args.test,
        no_dispatch=args.no_dispatch,
        output_file=args.output,
        crf=args.crf,
        preset=args.preset,
        live_upload=args.live_upload,
        enable_youtube=enable_yt,
        enable_tiktok=enable_tt,
        enable_instagram=enable_ig,
        youtube_privacy=args.privacy,
        track=args.track,
        group=args.group
    )

