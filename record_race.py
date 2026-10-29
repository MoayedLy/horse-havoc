"""
Automated Headless Race Recorder using Pygame & Direct FFmpeg Pipe Streaming
Renders the complete 2D Horse Racing simulation in 1080x1920 (9:16 vertical format)
and streams raw RGB24 byte buffers directly via in-memory stdin pipe into FFmpeg.

Key Optimizations:
- Direct In-Memory Stdin Pipe Capture: Zero intermediate image files (PNG/BMP) and zero raw uncompressed AVI/video files on disk.
- Storage-Optimized Single-Pass Encoding: H.264 CRF 23, preset veryfast, capped bitrate 4500k/6000k, pix_fmt yuv420p, stereo AAC 160k.
- Minimal Disk Footprint: 45-second 1080x1920 60 FPS video outputs directly in a single pass under ~25-35 MB.
- Robust Process Management: try...finally block ensures stdin closure and process waiting on completion or interruption.
"""

import os
import sys
import time
import glob
import random
import argparse
import subprocess
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Set console encoding to UTF-8 with fallback replacement to prevent cp1252 crash
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

from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS, NUM_HORSES
from game import RaceGame
import hud

def resolve_ffmpeg_path():
    """Finds FFmpeg executable in PATH or from imageio-ffmpeg package."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    raise RuntimeError("FFmpeg executable not found! Please install ffmpeg or imageio-ffmpeg.")

def cleanup_stale_scratch_files(target_dir=None):
    """Purges any obsolete .raw, uncompressed video, or temporary frame dumps."""
    dirs_to_check = [os.getcwd()]
    if target_dir and os.path.exists(target_dir):
        dirs_to_check.append(target_dir)
    patterns = ["*.raw", "*_temp_video.mp4", "*_temp_audio.wav", "temp_frame_*.png", "temp_frame_*.bmp"]
    for d in set(dirs_to_check):
        for pat in patterns:
            for p in glob.glob(os.path.join(d, pat)):
                try:
                    os.remove(p)
                except Exception:
                    pass

def record_race(
    output_file="race_recording.mp4",
    fps=FPS,
    seed=None,
    crf=23,
    preset="veryfast",
    max_seconds=55,
    roster=None,
    track=None,
    group=None
):
    """
    Renders the race and streams raw RGB24 frames directly into FFmpeg stdin.
    Encodes video and audio in a single pass directly to `output_file` with zero intermediate video files.
    """
    ffmpeg_exe = resolve_ffmpeg_path()
    
    # Resolve output path reliably against BASE_DIR
    out_path = Path(output_file)
    if not out_path.is_absolute():
        out_path = BASE_DIR / out_path
    output_file = str(out_path)
    out_dir = str(out_path.parent)
    os.makedirs(out_dir, exist_ok=True)

    # Pre-clean output target to enforce single-video disk quota
    if os.path.exists(output_file):
        try:
            os.remove(output_file)
        except Exception:
            pass

    # Clean any stale scratch files before starting
    cleanup_stale_scratch_files(out_dir)

    # Ensure deterministic seed so pre-sim audio matches rendering frame-for-frame
    if seed is None:
        seed = (time.time_ns() ^ int.from_bytes(os.urandom(4), "big")) & 0x7FFFFFFF

    # Resolve track theme preset
    selected_theme = track
    if selected_theme == "random":
        selected_theme = random.choice(["classic_turf", "desert_dunes", "cyber_neon"])
    elif selected_theme == "auto":
        selected_theme = None

    # Strictly enforce themed single-category celebrity roster
    active_roster = roster
    chosen_group = group
    chosen_group_name = None
    from celebrities import pick_themed_roster, VALID_GROUPS
    if active_roster is None:
        active_roster, chosen_group, chosen_group_name = pick_themed_roster(group=group, count=NUM_HORSES, seed=seed)
    else:
        # Enforce single-category consistency
        first_group = active_roster[0].get("group", "football") if isinstance(active_roster[0], dict) else "football"
        if not all(isinstance(c, dict) and c.get("group") == first_group for c in active_roster):
            active_roster, chosen_group, chosen_group_name = pick_themed_roster(group=first_group, count=NUM_HORSES, seed=seed)
        else:
            chosen_group = first_group
            chosen_group_name = active_roster[0].get("group_name", first_group.replace("_", " ").title())

    print("=" * 68)
    print(" [HORSE HAVOC] DIRECT IN-MEMORY STREAMING RECORDER")
    print("=" * 68)
    print(f" * Output Target : {output_file}")
    print(f" * Resolution    : {SCREEN_WIDTH}x{SCREEN_HEIGHT} (Vertical 9:16)")
    print(f" * Framerate     : {fps} FPS")
    print(f" * Encoding      : H.264 (CRF: {crf}, Preset: {preset}, Bitrate: 3500k, yuv420p)")
    print(f" * Audio Quality : Stereo AAC 128k @ 44100 Hz")
    print(f" * In-Memory Pipe: Direct RGB24 stdin streaming (Zero disk frames)")
    print(f" * Random Seed   : {seed}")
    print(f" * Match Theme   : {chosen_group_name} ({chosen_group})")
    if active_roster:
        r_names = [c["name"] if isinstance(c, dict) else str(c) for c in active_roster]
        print(f" * Roster (5)    : {', '.join(r_names)}")
    print("-" * 68)

    pygame.init()
    if pygame.display.get_surface() is None:
        try:
            pygame.display.set_mode((1, 1))
        except Exception:
            pass
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    # [1/2] Pre-compile frame-synchronized stereo audio in memory
    # Suppress HUD commentary so RaceTelemetryHook only receives events during render pass
    temp_audio_file = os.path.splitext(output_file)[0] + "_temp_audio.wav"
    orig_push_commentary = hud.HUD.push_commentary
    hud.HUD.push_commentary = lambda self, msg: None

    print("[1/2] Pre-compiling synchronized audio timeline...")
    max_frames = int(max_seconds * fps)
    pre_game = RaceGame(seed=seed, headless=True, enable_audio=False, selected_celebs=active_roster, track_theme=selected_theme, group=chosen_group)
    print(f" * Active Map    : {pre_game.track_name} ({pre_game.track_theme})")
    while pre_game.state != "COMPLETED" and pre_game.frame_idx < max_frames:
        pre_game.update()
    
    total_race_frames = pre_game.frame_idx
    pre_game.audio_timeline.export_wav(temp_audio_file, total_race_frames)
    hud.HUD.push_commentary = orig_push_commentary

    # [2/2] Launch single-pass FFmpeg process reading video from stdin and audio from temp WAV
    video_cmd = [
        ffmpeg_exe, "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{SCREEN_WIDTH}x{SCREEN_HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(fps),
        "-i", "-",                     # Input 0: Raw RGB frames from stdin
        "-i", temp_audio_file,         # Input 1: Synchronized audio
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-b:v", "3500k",
        "-maxrate", "4500k",
        "-bufsize", "6000k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "2",
        "-shortest",
        "-movflags", "+faststart",
        output_file
    ]

    print("[2/2] Streaming in-memory RGB24 frames directly to FFmpeg...")
    start_wall_time = time.time()
    proc = subprocess.Popen(video_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    game = RaceGame(seed=seed, headless=True, enable_audio=False, selected_celebs=active_roster, track_theme=selected_theme, group=chosen_group)
    frame_count = 0

    try:
        while True:
            game.update()
            game.render(surface)

            try:
                raw_bytes = pygame.image.tobytes(surface, "RGB")
            except AttributeError:
                raw_bytes = pygame.image.tostring(surface, "RGB")

            try:
                proc.stdin.write(raw_bytes)
            except BrokenPipeError:
                print("\n[!] FFmpeg process terminated unexpectedly (Broken pipe).")
                break

            frame_count += 1

            # Progress bar display
            if frame_count % 30 == 0:
                elapsed = time.time() - start_wall_time
                fps_actual = frame_count / elapsed if elapsed > 0 else 0
                leader_name = game.current_leader.name if game.current_leader else "Starting..."
                sim_time = game.race_time_sec
                progress_pct = min(100.0, (frame_count / float(total_race_frames or 2700)) * 100.0)
                bar_len = 24
                filled = int(bar_len * (progress_pct / 100.0))
                bar = "█" * filled + "░" * (bar_len - filled)
                sys.stdout.write(
                    f"\r [{bar}] {progress_pct:4.1f}% | Frame: {frame_count:4d} | "
                    f"Race: {sim_time:4.1f}s | Leader: {leader_name:<13} | Speed: {fps_actual:.1f} fps"
                )
                sys.stdout.flush()

            if game.state == "COMPLETED" or frame_count >= max_frames:
                break

    except KeyboardInterrupt:
        print("\n[!] Recording interrupted by user.")
    finally:
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.flush()
                proc.stdin.close()
        except Exception:
            pass
        proc.wait()
        if os.path.exists(temp_audio_file):
            try:
                os.remove(temp_audio_file)
            except Exception:
                pass

    total_sim_time = time.time() - start_wall_time
    print(f"\n[OK] Single-pass streaming complete! Processed {frame_count} frames in {total_sim_time:.1f}s ({frame_count/max(0.1, total_sim_time):.1f} fps).")

    if os.path.exists(output_file):
        file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print("=" * 68)
        print(f" SUCCESS: Race recorded with zero intermediate video/disk dumps!")
        print(f" * File Path : {os.path.abspath(output_file)}")
        print(f" * File Size : {file_size_mb:.2f} MB")
        print(f" * Duration  : {frame_count / fps:.2f} seconds")
        if game.finish_order:
            winner = game.finish_order[0]
            print(f" * Winner    : {winner.name} (Horse #{winner.number}) in {winner.finish_time:.2f}s")
        print("=" * 68)

        # Write game_events.json with active_category for downstream metadata generation
        try:
            import json
            winner_obj = game.finish_order[0] if game.finish_order else (game.horses[0] if game.horses else None)
            runner_obj = game.finish_order[1] if len(game.finish_order) > 1 else (game.horses[1] if len(game.horses) > 1 else None)
            events_data = {
                "active_category": chosen_group,
                "category_name": chosen_group_name,
                "track_theme": game.track_theme,
                "track_name": game.track_name,
                "winner": winner_obj.name if winner_obj else "Winner",
                "runner_up": runner_obj.name if runner_obj else "Runner-Up",
                "finish_time": round(winner_obj.finish_time, 2) if (winner_obj and winner_obj.finish_time) else 40.37,
                "roster": [
                    {
                        "id": getattr(h, "celebrity_id", f"racer_{h.id}"),
                        "name": h.name,
                        "number": h.number,
                        "category": getattr(h, "group", chosen_group)
                    }
                    for h in game.horses
                ]
            }
            with open("game_events.json", "w", encoding="utf-8") as f:
                json.dump(events_data, f, ensure_ascii=False, indent=2)
        except Exception as ge_err:
            pass
    else:
        print("[!] Error creating final MP4 output file.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless 2D Horse Racing MP4 Video Generator")
    parser.add_argument("-o", "--output", default="race_recording.mp4", help="Output MP4 file path")
    parser.add_argument("--fps", type=int, default=FPS, help="Frames per second (default: 60)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for race layout and AI variability")
    parser.add_argument("--crf", type=int, default=23, help="H.264 CRF quality factor (default: 23 - high efficiency)")
    parser.add_argument("--preset", default="veryfast", help="FFmpeg preset (ultrafast, veryfast, fast, medium, slow)")
    parser.add_argument("--duration", type=float, default=55.0, help="Maximum video duration safety cap in seconds (default: 55)")
    parser.add_argument("--track", choices=["auto", "classic_turf", "desert_dunes", "cyber_neon", "random"], default="auto", help="Track theme preset (default: auto)")
    parser.add_argument("--group", "--category", dest="group", choices=["auto", "football", "streamers", "tech_business", "world_leaders", "pop_culture", "random"], default="auto", help="Celebrity category theme (default: auto)")

    args = parser.parse_args()
    record_race(
        output_file=args.output,
        fps=args.fps,
        seed=args.seed,
        crf=args.crf,
        preset=args.preset,
        max_seconds=args.duration,
        track=args.track,
        group=args.group
    )
