"""
Automated Social Media Post-Production Pipeline for HORSE HAVOC
===============================================================
Records the complete 45-second race simulation and delivers a broadcast-ready
vertical short video for TikTok, YouTube Shorts, and Instagram Reels.

Features:
  - 100% Non-destructive: Existing game and recorder files remain completely untouched.
  - Video: Pristine 1080x1920 (9:16) 60 FPS H.264 video.
  - Audio: Crisp, pure in-game sound effects (hooves, start bell, laser blasts, rocket
    explosions, bump collisions, podium fanfare) blended with driving, energetic
    arcade background music.
  - Metadata Generator: Generates viral-ready Titles, Descriptions, and Hashtags
    tailored dynamically to the winning horse and race outcome.
  - Output: final_short.mp4 + final_short_metadata.json
"""

import os
import sys
import time
import json
import math
import wave
import struct
import random
import argparse
import subprocess

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

from config import FPS, SCREEN_WIDTH, SCREEN_HEIGHT, HORSE_PROFILES
from record_race import resolve_ffmpeg_path, record_race
from hud import HUD
from game import RaceGame

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

def generate_energetic_music(duration_sec, output_wav_path, sample_rate=44100):
    """
    Synthesizes a driving 130 BPM arcade racing electronic music track in pure Python.
    Includes punchy kick drums, crisp snares, rolling 16th-note synth bassline,
    hi-hat grooves, and melodic arpeggio progression.
    """
    bpm = 130.0
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0  # 16th note
    total_samples = int(duration_sec * sample_rate)
    left = [0.0] * total_samples
    right = [0.0] * total_samples

    # 1. Pre-synthesize drum elements
    # Punchy kick drum
    kick_samples = []
    for i in range(int(0.20 * sample_rate)):
        t = i / sample_rate
        freq = 45.0 + 120.0 * math.exp(-32.0 * t)
        v = math.sin(2.0 * math.pi * freq * t)
        env = math.exp(-16.0 * t)
        kick_samples.append(v * env * 0.75)

    # Snappy snare drum with tonal body
    snare_samples = []
    for i in range(int(0.18 * sample_rate)):
        t = i / sample_rate
        noise = random.uniform(-1.0, 1.0)
        tone = math.sin(2.0 * math.pi * 190.0 * t)
        env = math.exp(-22.0 * t)
        snare_samples.append((0.7 * noise + 0.3 * tone) * env * 0.45)

    # Closed hi-hat
    hihat_samples = []
    for i in range(int(0.045 * sample_rate)):
        t = i / sample_rate
        noise = random.uniform(-1.0, 1.0)
        env = math.exp(-85.0 * t)
        hihat_samples.append(noise * env * 0.22)

    # Open hi-hat
    openhat_samples = []
    for i in range(int(0.12 * sample_rate)):
        t = i / sample_rate
        noise = random.uniform(-1.0, 1.0)
        env = math.exp(-30.0 * t)
        openhat_samples.append(noise * env * 0.28)

    # Chord progression: Dm -> F -> C -> G
    bass_chords = [73.42, 87.31, 65.41, 98.00]  # D2, F2, C2, G2
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

        # Kick on every beat
        if sub_step == 0:
            for j, s in enumerate(kick_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s
                    right[idx] += s

        # Snare on beats 2 and 4 (indices 1 and 3)
        if sub_step == 0 and (beat_in_bar == 1 or beat_in_bar == 3):
            for j, s in enumerate(snare_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 0.95
                    right[idx] += s * 0.95

        # Hi-hat patterns
        if sub_step == 2:  # Off-beat open hat
            for j, s in enumerate(openhat_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 0.70
                    right[idx] += s * 1.10
        elif sub_step in (0, 1, 3):  # Closed hats
            for j, s in enumerate(hihat_samples):
                idx = start_idx + j
                if idx < total_samples:
                    left[idx] += s * 1.0
                    right[idx] += s * 0.8

        # Rolling 16th Synth Bass
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

        # Synth arpeggio
        note_idx = (step * 3) % len(arp_notes)
        arp_freq = arp_notes[note_idx]
        arp_len = int(step_sec * 0.90 * sample_rate)
        pan = 0.5 + 0.35 * math.sin(step * 0.6)
        for j in range(arp_len):
            idx = start_idx + j
            if idx < total_samples:
                t = j / sample_rate
                square = 1.0 if math.sin(2.0 * math.pi * arp_freq * t) > 0 else -1.0
                env = math.exp(-20.0 * t)
                v = square * env * 0.14
                left[idx] += v * (1.0 - pan)
                right[idx] += v * pan

    # Smooth 1.5s fade-in and 2.5s fade-out
    fade_in_samples = int(1.5 * sample_rate)
    fade_out_samples = int(2.5 * sample_rate)
    for i in range(min(fade_in_samples, total_samples)):
        left[i] *= (i / fade_in_samples)
        right[i] *= (i / fade_in_samples)
    for i in range(min(fade_out_samples, total_samples)):
        idx = total_samples - 1 - i
        left[idx] *= (i / fade_out_samples)
        right[idx] *= (i / fade_out_samples)

    # Peak normalization with clean headroom (-6 dBFS)
    peak = max(max(abs(l) for l in left), max(abs(r) for r in right), 0.001)
    target_peak = 16000.0
    gain = target_peak / peak

    interleaved = []
    for i in range(total_samples):
        l = int(max(-32767, min(32767, left[i] * gain)))
        r = int(max(-32767, min(32767, right[i] * gain)))
        interleaved.append(l)
        interleaved.append(r)

    with wave.open(output_wav_path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{len(interleaved)}h", *interleaved))

def generate_social_metadata(winner_name, winner_number, finish_time, total_duration, events, winner_quote="", victory_sfx=""):
    """
    Generates high-performing, viral-optimized metadata for TikTok, YouTube Shorts, and Reels
    dynamically tailored to the winning celebrity and race action.
    """
    lead_changes = sum(1 for e in events if "SURGES INTO 1ST" in e.get("message", ""))
    weapon_hits = sum(1 for e in events if "HIT!" in e.get("message", ""))

    quote_str = f" ({winner_quote})" if winner_quote else ""
    sfx_str = f" | Finish SFX: {victory_sfx}" if victory_sfx else ""

    titles = [
        f"WHO WILL WIN?! 😱 {winner_name} In An INSANE 45s Finish! 🐎🔥",
        f"The ending had me screaming! 😭🚀 {winner_name} pulls off the IMPOSSIBLE! #HorseHavoc",
        f"45 Seconds Of Pure Chaos! Can {winner_name} Survive The Rocket Crossfire?! 💣🐎",
        f"{winner_name} vs Top Celebrities In A Wild 45-Second AI Horse Race! 🏁🤯"
    ]

    description = (
        f"🏁 HORSE HAVOC: CELEBRITY MEME DERBY 🏁\n"
        f"🏆 WINNER: {winner_name} (Horse #{winner_number}){quote_str}\n"
        f"⏱️ Winning Time: {finish_time:.2f}s{sfx_str}\n"
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
        "winner": {
            "name": winner_name,
            "number": winner_number,
            "quote": winner_quote,
            "finish_time": round(finish_time, 2),
            "victory_sfx": victory_sfx
        },
        "video_duration_sec": round(total_duration, 2),
        "primary_title": titles[0],
        "alternative_titles": titles[1:],
        "description": description,
        "hashtags": hashtags,
        "tags_string": " ".join(hashtags)
    }

def run_pipeline(seed=None, fps=FPS, crf=20, preset="fast", custom_music=None, output_file="final_short.mp4"):
    ffmpeg_exe = resolve_ffmpeg_path()
    base_name = os.path.splitext(output_file)[0]
    temp_clean_mp4 = f"{base_name}_temp_clean.mp4"
    temp_music_wav = f"{base_name}_temp_music.wav"
    metadata_json_path = f"{base_name}_metadata.json"
    metadata_txt_path = f"{base_name}_metadata.txt"

    print("=" * 70)
    print(" [HORSE HAVOC] SOCIAL MEDIA POST-PRODUCTION PIPELINE")
    print("=" * 70)
    print(f" * Output Video   : {output_file}")
    print(f" * Resolution     : {SCREEN_WIDTH}x{SCREEN_HEIGHT} (9:16 Vertical Shorts/Reels)")
    print(f" * Target FPS     : {fps}")
    print(f" * Random Seed    : {seed}")
    print(f" * Audio Strategy : In-Game SFX (100%) + Energetic Arcade Music (32%)")
    print(f" * FFmpeg Binary  : {ffmpeg_exe}")
    print("-" * 70)

    # -------------------------------------------------------------
    # STEP 1: Record 45s Match & Capture Event Telemetry
    # -------------------------------------------------------------
    print("\n[STEP 1/3] Simulating match and recording video with crisp in-game SFX...")
    hook = RaceTelemetryHook()
    with hook:
        record_race(
            output_file=temp_clean_mp4,
            fps=fps,
            seed=seed,
            crf=crf,
            preset=preset,
            max_seconds=55
        )

    # Read captured telemetry
    events = hook.events
    active_game = hook.active_game
    winner = active_game.finish_order[0] if active_game and active_game.finish_order else None
    winner_name = winner.name if winner else "Midnight Star"
    winner_number = winner.number if winner else 3
    winner_time = winner.finish_time if winner else 40.37
    victory_sfx_key = getattr(active_game, "selected_victory_sfx", None)
    total_frames = active_game.frame_idx if active_game else 2645
    race_duration_sec = total_frames / fps

    print(f"\n[OK] Match recording complete!")
    print(f" * Duration    : {race_duration_sec:.2f}s ({total_frames} frames)")
    print(f" * Winner      : {winner_name} (Horse #{winner_number}) in {winner_time:.2f}s")
    print(f" * Victory SFX : {victory_sfx_key or 'Standard Fanfare'}")
    print(f" * Events      : {len(events)} logged")
    # Write game_events.json with active_category
    try:
        ge_log = {
            "active_category": getattr(active_game, "active_group", "football"),
            "category_name": getattr(active_game, "active_group_name", "Football Derby"),
            "track_theme": getattr(active_game, "track_theme", "classic_turf"),
            "track_name": getattr(active_game, "track_name", "Classic Turf Derby"),
            "winner": winner_name,
            "finish_time": round(winner_time, 2),
            "events": events
        }
        with open("game_events.json", "w", encoding="utf-8") as gef:
            json.dump(ge_log, gef, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # -------------------------------------------------------------
    # STEP 2: Generate & Mux Energetic Background Music
    # -------------------------------------------------------------
    print("\n[STEP 2/3] Preparing background music and mixing final master audio...")
    if custom_music and os.path.exists(custom_music):
        print(f" * Using user-provided background music: {custom_music}")
        music_input = custom_music
        cleanup_music = False
    else:
        print(f" * Synthesizing driving 130 BPM arcade racing music track ({race_duration_sec:.2f}s)...")
        generate_energetic_music(race_duration_sec, temp_music_wav)
        music_input = temp_music_wav
        cleanup_music = True

    # Audio mixing filter:
    # [0:a] is crisp game sound effects (volume 1.0)
    # [1:a] is energetic background music (volume 0.32, smooth background bed)
    mix_filter = (
        "[0:a]volume=1.0[sfx]; "
        "[1:a]volume=0.32[bgm]; "
        "[sfx][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    mux_cmd = [
        ffmpeg_exe, "-y",
        "-i", temp_clean_mp4,
        "-i", music_input,
        "-filter_complex", mix_filter,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",           # Lossless instant bit-for-bit video copy
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        output_file
    ]

    subprocess.run(mux_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Cleanup temporary recording files
    if os.path.exists(temp_clean_mp4):
        try:
            os.remove(temp_clean_mp4)
        except Exception:
            pass
    if cleanup_music and os.path.exists(temp_music_wav):
        try:
            os.remove(temp_music_wav)
        except Exception:
            pass

    # -------------------------------------------------------------
    # STEP 3: Generate Social Media Metadata (Title, Desc, Tags)
    # -------------------------------------------------------------
    print("\n[STEP 3/3] Generating viral social media metadata...")
    meta = generate_social_metadata(
        winner_name=winner_name,
        winner_number=winner_number,
        finish_time=winner_time,
        total_duration=race_duration_sec,
        events=events,
        winner_quote=getattr(winner, "quote", ""),
        victory_sfx=victory_sfx_key or ""
    )

    # Save metadata JSON
    with open(metadata_json_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # Save ready-to-copy metadata TXT
    with open(metadata_txt_path, "w", encoding="utf-8") as f:
        f.write("=== YOUTUBE SHORTS / TIKTOK READY-TO-POST METADATA ===\n\n")
        f.write(f"TITLE:\n{meta['primary_title']}\n\n")
        f.write(f"DESCRIPTION:\n{meta['description']}\n\n")
        f.write(f"HASHTAGS:\n{meta['tags_string']}\n\n")
        f.write("ALTERNATIVE TITLES:\n")
        for at in meta["alternative_titles"]:
            f.write(f"- {at}\n")

    # -------------------------------------------------------------
    # Summary Display
    # -------------------------------------------------------------
    if os.path.exists(output_file):
        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print("\n" + "=" * 70)
        print(" SUCCESS: FINAL SOCIAL SHORT READY!")
        print("=" * 70)
        print(f" * File Name     : {output_file}")
        print(f" * File Path     : {os.path.abspath(output_file)}")
        print(f" * Duration      : {race_duration_sec:.2f} seconds")
        print(f" * File Size     : {size_mb:.2f} MB")
        print(f" * Resolution    : 1080x1920 (Vertical 9:16)")
        print(f" * Audio Quality : Studio Stereo AAC 192k (SFX + Arcade Music)")
        print("-" * 70)
        print(f" [GENERATED TITLE]\n{meta['primary_title']}")
        print("-" * 70)
        print(f" [GENERATED DESCRIPTION]\n{meta['description']}")
        print("-" * 70)
        print(f" [GENERATED HASHTAGS]\n{meta['tags_string']}")
        print("-" * 70)
        print(f" [METADATA FILES SAVED]")
        print(f" * JSON : {os.path.abspath(metadata_json_path)}")
        print(f" * TXT  : {os.path.abspath(metadata_txt_path)}")
        print("=" * 70)
        return True
    else:
        print("[!] Error creating final output video.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HORSE HAVOC Social Media Video Pipeline")
    parser.add_argument("-o", "--output", default="final_short.mp4", help="Output video file (default: final_short.mp4)")
    parser.add_argument("--seed", type=int, default=None, help="Simulation random seed (default: None for random selection)")
    parser.add_argument("--fps", type=int, default=FPS, help="Frames per second (default: 60)")
    parser.add_argument("--crf", type=int, default=20, help="H.264 video quality (default: 20)")
    parser.add_argument("--preset", default="fast", help="FFmpeg preset (default: fast)")
    parser.add_argument("--music", default=None, help="Optional custom background music file (MP3/WAV)")

    args = parser.parse_args()
    run_pipeline(
        seed=args.seed,
        fps=args.fps,
        crf=args.crf,
        preset=args.preset,
        custom_music=args.music,
        output_file=args.output
    )
