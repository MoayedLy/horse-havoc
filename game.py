"""
RaceEngine: Central Game Loop, Physics, Dynamic Camera, and State Machine
Supports both live windowed interactive play and headless frame-by-frame video rendering.
"""

import math
import random
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS,
    TRACK_LEFT, TRACK_RIGHT, TRACK_WIDTH,
    TRACK_LENGTH, START_Y, FINISH_Y, TOTAL_RACE_DISTANCE,
    NUM_HORSES, LANE_WIDTH, HORSE_PROFILES
)
from track import Track
from horse import Horse
from particles import ParticleSystem
from hud import HUD
from sound_effects import (
    SoundManager, AudioTimeline,
    VICTORY_SOUNDS, get_victory_sound_for_winner, CELEBRITY_VICTORY_SIGNATURES
)

class RaceGame:
    def __init__(self, seed=None, headless=False, enable_audio=True, selected_celebs=None, track_theme=None, group=None):
        self.seed = seed
        self.headless = headless
        self.frame_idx = 0
        self.race_time_sec = 0.0

        # State Machine: 'GATE_PREPARE', 'RACING', 'PHOTO_FINISH', 'PODIUM', 'COMPLETED'
        self.state = "GATE_PREPARE"
        self.gate_timer = 45  # frames before gates fling open

        # Track, Particles & HUD
        self.track_theme_req = track_theme
        self.track = Track(seed=self.seed, theme=track_theme)
        self.track_theme = self.track.theme
        self.track_name = self.track.theme_config["name"]
        self.particles = ParticleSystem()
        self.hud = HUD()
        self.hud.track_theme = self.track_theme
        self.hud.track_name = self.track_name

        # Audio
        self.sound_manager = SoundManager(enabled=enable_audio and not headless)
        self.audio_timeline = AudioTimeline(fps=FPS)

        # Dynamic Victory SFX selection
        self.match_default_victory_sfx = random.choice(list(VICTORY_SOUNDS.keys()))
        self.selected_victory_sfx = None

        # Strictly Enforce Single-Category Match Selection
        self.group_req = group
        from celebrities import pick_themed_roster
        if selected_celebs is not None:
            # Validate that all contestants belong to the exact same category
            first_group = selected_celebs[0].get("group", "football") if isinstance(selected_celebs[0], dict) else "football"
            uniform_celebs = [c for c in selected_celebs if isinstance(c, dict) and c.get("group") == first_group]
            if len(uniform_celebs) < NUM_HORSES:
                # If mixed or incomplete, re-sample strictly from that category
                self.selected_celebs, self.active_group, self.active_group_name = pick_themed_roster(
                    group=first_group, count=NUM_HORSES, seed=self.seed
                )
            else:
                self.selected_celebs = uniform_celebs[:NUM_HORSES]
                self.active_group = first_group
                self.active_group_name = self.selected_celebs[0].get("group_name", first_group.replace("_", " ").title())
        else:
            self.selected_celebs, self.active_group, self.active_group_name = pick_themed_roster(
                group=group, count=NUM_HORSES, seed=self.seed
            )

        self.group = self.active_group
        self.group_name = self.active_group_name
        self.hud.group_key = self.active_group
        self.hud.group_name = self.active_group_name
        self.hud.current_ticker = f">> {self.active_group_name.upper()} AT {self.track_name.upper()}! <<"

        # Initialize the 5 Horses at their starting stalls with Celebrity personas
        self.horses = []
        for i, celeb in enumerate(self.selected_celebs):
            base_profile = HORSE_PROFILES[i % len(HORSE_PROFILES)].copy()
            s_col = tuple(celeb["silk_color"]) if isinstance(celeb.get("silk_color"), list) else celeb.get("silk_color", base_profile["silk_color"])
            s_acc = tuple(celeb["silk_accent"]) if isinstance(celeb.get("silk_accent"), list) else celeb.get("silk_accent", (255, 255, 255))
            c_col = tuple(celeb["coat_color"]) if isinstance(celeb.get("coat_color"), list) else celeb.get("coat_color", base_profile["coat_color"])

            merged_profile = {
                **base_profile,
                "id": i,
                "celebrity_id": celeb["id"],
                "name": celeb["name"],
                "short_name": celeb["short_name"],
                "quote": celeb["quote"],
                "number": i + 1,
                "group": celeb.get("group", self.active_group),
                "group_name": celeb.get("group_name", self.active_group_name),
                "silk_color": s_col,
                "silk_accent": s_acc,
                "coat_color": c_col,
                "initials": celeb.get("initials", celeb.get("short_name", celeb.get("name", "HH"))[:3].upper())
            }
            stall_x = TRACK_LEFT + (i + 0.5) * LANE_WIDTH
            stall_y = START_Y + 10
            horse = Horse(merged_profile, stall_x, stall_y)
            self.horses.append(horse)

        # Active in-flight projectiles
        self.projectiles = []

        # Camera
        self.camera_y = START_Y - SCREEN_HEIGHT * 0.65
        self.target_camera_y = self.camera_y
        self.camera_shake = 0.0

        # Race tracking
        self.finish_order = []
        self.current_leader = None
        self.confetti_triggered = False
        self.post_race_timer = 0
        self.debug_mode = False

    def reset(self, new_seed=None, new_roster=None, track_theme=None, group=None):
        """Resets the race with fresh horses, track, and state."""
        if new_seed is not None:
            self.seed = new_seed
        theme_to_use = track_theme if track_theme is not None else getattr(self, "track_theme_req", None)
        group_to_use = group if group is not None else getattr(self, "group_req", None)
        self.__init__(
            seed=self.seed,
            headless=self.headless,
            enable_audio=self.sound_manager.enabled,
            selected_celebs=new_roster if new_roster is not None else self.selected_celebs,
            track_theme=theme_to_use,
            group=group_to_use
        )

    def update(self):
        """Advances one simulation frame."""
        self.frame_idx += 1
        self.race_time_sec = max(0.0, (self.frame_idx - 45) / FPS)
        self.hud.update()
        self.particles.update()
        self.track.update()

        # 1. State: Gate Preparation
        if self.state == "GATE_PREPARE":
            self.gate_timer -= 1
            if self.gate_timer == 1:
                # Bell Chimes! And they're off!
                self.state = "RACING"
                self.hud.push_commentary(f">> RACE AT {self.track_name.upper()}! GATES OPEN! <<")
                if self.sound_manager:
                    self.sound_manager.play("start")
                if self.audio_timeline:
                    self.audio_timeline.schedule(self.frame_idx, "start", volume=0.7)
            return

        # 2. Update Horses AI & Physics
        leader = min(self.horses, key=lambda h: h.y)
        if self.current_leader is not None and leader.id != self.current_leader.id and not leader.is_finished:
            # Lead change event!
            self.hud.push_commentary(f">> {leader.name.upper()} SURGES INTO 1ST! <<")
        self.current_leader = leader

        for horse in self.horses:
            dist_to_finish = horse.y - FINISH_Y
            new_proj = horse.update_ai(
                self.track, self.horses, dist_to_finish,
                self.sound_manager, self.audio_timeline, self.frame_idx, self.particles
            )
            if new_proj:
                self.projectiles.append(new_proj)
                w_name = new_proj.p_type.replace('_', ' ').upper()
                self.hud.push_commentary(f">> {horse.name.upper()} FIRED {w_name}! <<")

            horse.update_physics(self.track, self.particles, self.sound_manager, self.audio_timeline, self.frame_idx)

            # Check Finish Line Crossing
            if horse.y <= FINISH_Y and not horse.is_finished:
                horse.is_finished = True
                horse.finish_time = self.race_time_sec
                horse.finish_rank = len(self.finish_order) + 1
                self.finish_order.append(horse)

                if horse.finish_rank == 1:
                    # Winner crossed! Determine dynamic victory sound
                    celeb_id = getattr(horse, "celebrity_id", None)
                    victory_key = get_victory_sound_for_winner(celeb_id, fallback_random=False)
                    if not victory_key or (victory_key == "royal_fanfare" and celeb_id not in CELEBRITY_VICTORY_SIGNATURES):
                        victory_key = self.match_default_victory_sfx
                    self.selected_victory_sfx = victory_key
                    v_name = VICTORY_SOUNDS.get(victory_key, {}).get("name", victory_key.replace('_', ' ').title())

                    self.hud.push_commentary(f">> {horse.name.upper()} WINS! [{v_name}] <<")
                    if not self.confetti_triggered:
                        self.particles.emit_confetti(SCREEN_WIDTH // 2, FINISH_Y, count=220)
                        self.confetti_triggered = True
                    self.camera_shake = 7.0
                    if self.sound_manager:
                        self.sound_manager.play(victory_key)
                        self.sound_manager.play("cheer")
                    if self.audio_timeline:
                        vol = VICTORY_SOUNDS.get(victory_key, {}).get("volume", 0.90)
                        self.audio_timeline.schedule(self.frame_idx, victory_key, volume=vol)
                        self.audio_timeline.schedule(self.frame_idx, "cheer", volume=0.85)
                    self.post_race_timer = 1  # Trigger post-race celebration timer immediately!

        # 3. Update Projectiles & Direct Hits
        surviving_projs = []
        for proj in self.projectiles:
            hit = proj.update(
                self.horses, self.particles, self.sound_manager, self.audio_timeline, self.frame_idx
            )
            if hit:
                w_name = hit["weapon"].replace('_', ' ').upper()
                self.hud.push_commentary(f">> HIT! {hit['target_name'].upper()} STUNNED BY {w_name}! <<")
                self.camera_shake = 6.0
            if proj.alive:
                surviving_projs.append(proj)
        self.projectiles = surviving_projs

        # 4. Horse-to-Horse Collisions (Side-Bumps)
        num_h = len(self.horses)
        for i in range(num_h):
            for j in range(i + 1, num_h):
                h1 = self.horses[i]
                h2 = self.horses[j]
                if h1.resolve_bump_collision(h2, self.particles, self.sound_manager, self.audio_timeline, self.frame_idx):
                    self.hud.push_commentary(f">> CONTACT! {h1.name} & {h2.name} BUMP! <<")
                    self.camera_shake = 5.0

        # 5. Camera Follow Logic
        active_horses = [h for h in self.horses if not h.is_finished]
        if active_horses:
            top_horses = sorted(active_horses, key=lambda h: h.y)[:2]
            focus_y = sum(h.y for h in top_horses) / len(top_horses)
            self.target_camera_y = focus_y - SCREEN_HEIGHT * 0.65
        else:
            self.target_camera_y = FINISH_Y - SCREEN_HEIGHT * 0.45

        self.camera_y += (self.target_camera_y - self.camera_y) * 0.08

        if self.camera_shake > 0:
            self.camera_shake *= 0.85
            if self.camera_shake < 0.2:
                self.camera_shake = 0.0

        # 6. Check Race Conclusion & 3-Second Celebration
        if len(self.finish_order) >= 1:
            self.post_race_timer += 1

            # Transition to PODIUM screen after 30 frames (0.5s of crossing the line)
            if self.post_race_timer >= 30 and self.state != "PODIUM":
                self.state = "PODIUM"
                self.particles.emit_confetti(SCREEN_WIDTH // 2, self.camera_y + 400, count=160)
                self.particles.emit_confetti(SCREEN_WIDTH // 4, self.camera_y + 350, count=80)
                self.particles.emit_confetti(3 * SCREEN_WIDTH // 4, self.camera_y + 350, count=80)

            # Exactly 3.0 seconds (180 frames) after the first horse crosses, complete the match!
            if self.post_race_timer >= 180:
                self.state = "COMPLETED"

    def render(self, surface):
        """Draws the entire frame (Track -> Horses -> Particles -> Broadcast HUD)."""
        shake_offset = (random.uniform(-self.camera_shake, self.camera_shake), random.uniform(-self.camera_shake, self.camera_shake)) if self.camera_shake > 0 else (0, 0)
        cam_y = self.camera_y + shake_offset[1]

        # 1. Render Track, Rails, Obstacles, Finish Line
        self.track.draw(surface, cam_y)

        # 2. Render Horses (sorted by Y so horses in foreground render over those behind)
        sorted_draw_horses = sorted(self.horses, key=lambda h: h.y)
        for h in sorted_draw_horses:
            h.draw(surface, cam_y, debug=self.debug_mode)

        # 3. Render Active Projectiles (Lasers, Mud Bombs, Rockets)
        for proj in self.projectiles:
            proj.draw(surface, cam_y)

        # 4. Render Particle System (turf, mud, sparks, confetti)
        self.particles.draw(surface, cam_y)

        # 4. Render Broadcast UI & HUD Overlay
        self.hud.draw(surface, self.race_time_sec, self.horses, self.finish_order, self.state)
