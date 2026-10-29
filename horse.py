"""
Horse Simulation, Jockey/Rider Character Visuals, Weapons AI, and Physics
Upgrades:
- Detailed human jockey character riding each horse with matching jersey, helmet visor,
  goggles, arms holding reins, dynamic turning lean, and equipped weapon display.
- Stun & spin-out animation system with dizzy orbiting cartoon stars.
- Weapon pickup detection and AI targeting/firing at horses in front.
"""

import math
import random
import pygame
from config import (
    TRACK_LEFT, TRACK_RIGHT, TRACK_WIDTH, FINISH_Y,
    HORSE_LENGTH, HORSE_WIDTH, COLLISION_RADIUS,
    KNOCKBACK_DAMPING, BUMP_IMPULSE,
    OBSTACLE_MUD, OBSTACLE_HURDLE, OBSTACLE_HAYBALE,
    WEAPON_LASER, WEAPON_MUD_BOMB, WEAPON_ROCKET
)
from track import (
    OBSTACLE_QUICKSAND, OBSTACLE_BOULDER, OBSTACLE_TUMBLEWEED,
    OBSTACLE_PLASMA, OBSTACLE_EMP,
    TRACK_THEME_TURF, TRACK_THEME_DESERT, TRACK_THEME_CYBER
)
from projectiles import Projectile

class Horse:
    def __init__(self, profile, start_x, start_y):
        self.id = profile["id"]
        self.name = profile["name"]
        self.number = profile["number"]
        self.archetype = profile["archetype"]
        self.coat_color = profile["coat_color"]
        self.mane_color = profile["mane_color"]
        self.silk_color = profile["silk_color"]
        self.silk_accent = profile["silk_accent"]
        self.jockey_skin = profile.get("jockey_skin", (230, 190, 160))

        # Celebrity Meme Attributes
        self.celebrity_id = profile.get("celebrity_id", None)
        self.short_name = profile.get("short_name", self.name)
        self.quote = profile.get("quote", "")
        self.group = profile.get("group", "football")
        self.group_name = profile.get("group_name", "Football Derby")

        # Cached Celebrity Meme Avatars at various UI resolutions
        celeb_key = self.celebrity_id or f"racer_{self.id}"
        from celebrities import get_celebrity_avatar
        # Ultra-Prominent Big Head / Bobblehead Mode (88x88 diameter, +47% size) with 4px solid white outline
        self.avatar_head_surf = get_celebrity_avatar(celeb_key, (88, 88), border_color=(255, 255, 255), border_width=4)
        # Enlarged Leaderboard Avatar (46x46, +28% size) for clear readability
        self.avatar_hud_surf = get_celebrity_avatar(celeb_key, (46, 46), border_color=(255, 255, 255), border_width=2)
        self.avatar_pin_surf = get_celebrity_avatar(celeb_key, (24, 24), border_color=(255, 255, 255), border_width=1)
        self.avatar_podium_surf = get_celebrity_avatar(celeb_key, (110, 110), border_color=(255, 215, 0), border_width=4)
        self.avatar_runner_surf = get_celebrity_avatar(celeb_key, (52, 52), border_color=self.silk_color, border_width=2)

        # Base Stats
        self.base_top_speed = profile["top_speed"]
        self.accel_rate = profile["accel"]
        self.max_stamina = profile["stamina"]
        self.stamina = profile["stamina"]
        self.stamina_drain = profile["stamina_drain"]
        self.sprint_threshold = profile["sprint_threshold"]
        self.grit = profile["grit"]
        self.lane_bias = profile["lane_bias"]
        self.steer_speed = profile["steer_speed"]

        # Dynamic Coordinates & Physics
        self.x = float(start_x)
        self.y = float(start_y)
        self.vx = 0.0
        self.vy = 0.0          # Negative is moving forward (upwards)
        self.speed = 0.0
        self.heading = 0.0     # Angle in degrees (0 = straight up)
        self.target_x = float(start_x)

        # Race State
        self.is_finished = False
        self.finish_time = None
        self.finish_rank = None
        self.is_sprinting = False
        self.is_jumping = False
        self.jump_progress = 0.0
        self.jump_duration = 24  # frames
        self.in_mud = False
        self.stumble_timer = 0
        self.boost_timer = 0
        self.drafting = False

        # Weapons & Stun System
        self.held_weapon = None
        self.aim_timer = random.randint(20, 45)
        self.stun_timer = 0
        self.spin_angle = 0.0
        self.last_fired_weapon = None

        # Animation State
        self.stride_phase = random.uniform(0, 2 * math.pi)
        self.stride_rate = 0.35

        # Collision Cooldown
        self.bump_cooldown = 0
        self.last_bump_other_id = -1

    @property
    def bounds(self):
        """Bounding circle for collision physics."""
        return (self.x, self.y, COLLISION_RADIUS)

    def apply_stun(self, duration, weapon_type="hit"):
        """Triggers spin-out stun effect, slowing horse down for ~1.5 - 2.0s."""
        self.stun_timer = duration
        self.speed = max(4.0, self.speed * 0.28)
        self.stumble_timer = duration
        self.is_sprinting = False

    def update_ai(self, track, all_horses, dist_to_finish, sound_manager=None, audio_timeline=None, frame_idx=0, particle_system=None):
        """
        AI Decision Engine:
        1. Checks weapon crate pickups and targets opponents ahead.
        2. Evaluates obstacle feelers ahead (mud, hurdles, haybales).
        3. Manages stamina conservation, drafting bonuses, and sprint bursts.
        """
        if self.is_finished:
            self.target_x = self.x
            self.is_sprinting = False
            return None

        # --- 0. Stun / Spin-Out Logic ---
        if self.stun_timer > 0:
            self.stun_timer -= 1
            self.spin_angle = (self.spin_angle + 26.0) % 360.0
            # During stun, horse slows down and cannot steer effectively
            self.speed = max(3.5, self.speed * 0.94)
            self.vx *= 0.85
            self.x += self.vx
            return None
        else:
            self.spin_angle = 0.0

        # --- 1. Item Box Pickup Detection ---
        if self.held_weapon is None:
            horse_rect = pygame.Rect(int(self.x - 22), int(self.y - 25), 44, 50)
            for box in track.item_boxes:
                if not box.collected and box.rect.colliderect(horse_rect):
                    box.collected = True
                    box.respawn_timer = 400
                    self.held_weapon = box.weapon
                    self.aim_timer = random.randint(22, 50)
                    if particle_system:
                        particle_system.emit_collision_bump(box.x, box.y)
                    if sound_manager:
                        sound_manager.play("pickup")
                    if audio_timeline:
                        pan = ((self.x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                        audio_timeline.schedule(frame_idx, "pickup", volume=0.55, pan=pan)
                    break

        # --- 2. Weapon Aiming & Firing Logic ---
        new_projectile = None
        if self.held_weapon is not None:
            # Look for the nearest horse in front
            nearest_target = None
            min_dy = 99999.0
            for other in all_horses:
                if other.id != self.id and not other.is_finished:
                    dy = self.y - other.y
                    # Horse must be in front within firing range
                    if 80 < dy < 900:
                        if dy < min_dy:
                            min_dy = dy
                            nearest_target = other

            if nearest_target is not None:
                self.aim_timer -= 1
                if self.aim_timer <= 0:
                    # FIRE WEAPON!
                    new_projectile = Projectile(
                        self.held_weapon,
                        self.id,
                        self.name,
                        self.x,
                        self.y - 36,
                        target_horse=nearest_target
                    )
                    # Play launch sound
                    snd_name = "laser" if self.held_weapon == WEAPON_LASER else ("rocket" if self.held_weapon == WEAPON_ROCKET else "mud")
                    if sound_manager:
                        sound_manager.play(snd_name)
                    if audio_timeline:
                        pan = ((self.x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                        audio_timeline.schedule(frame_idx, snd_name, volume=0.6, pan=pan)

                    self.last_fired_weapon = self.held_weapon
                    self.held_weapon = None

        # --- 3. Stamina & Sprint Logic ---
        if dist_to_finish <= self.sprint_threshold and self.stamina > 5.0:
            self.is_sprinting = True
        else:
            self.is_sprinting = False

        # Check slipstream drafting: if directly behind another horse within 190px
        self.drafting = False
        for other in all_horses:
            if other.id != self.id and not other.is_finished:
                dy = self.y - other.y
                dx = abs(self.x - other.x)
                if 45 < dy < 190 and dx < 38:
                    self.drafting = True
                    break

        # Stamina consumption & recovery
        drain = self.stamina_drain
        if self.is_sprinting:
            drain *= 2.4
        if self.drafting:
            drain *= 0.50  # 50% stamina saved drafting!
        if self.in_mud:
            drain *= 1.8

        self.stamina = max(0.0, self.stamina - drain)

        # Calculate desired forward speed
        stamina_factor = 0.58 + 0.42 * (self.stamina / self.max_stamina)
        desired_speed = self.base_top_speed * stamina_factor
        if self.is_sprinting:
            desired_speed *= 1.16
        if self.in_mud:
            desired_speed *= 0.56
        if self.stumble_timer > 0:
            desired_speed *= 0.65
            self.stumble_timer -= 1
        if self.boost_timer > 0:
            desired_speed *= 1.25
            self.boost_timer -= 1

        # Smooth acceleration
        speed_diff = desired_speed - self.speed
        self.speed += speed_diff * (0.04 if speed_diff > 0 else 0.08)

        # --- 4. Sensory Feeler Raycasting (Obstacle Avoidance & Boost Navigation) ---
        steer_impulse = 0.0
        lookahead = 280 + self.speed * 8.0

        nearest_obs = None
        min_obs_dist = 999999.0

        for obs in track.obstacles:
            if self.y - obs.y > 0 and (self.y - obs.y) < lookahead + 80:
                dist = self.y - obs.y
                if dist < min_obs_dist:
                    min_obs_dist = dist
                    nearest_obs = obs

        if nearest_obs:
            dx = self.x - nearest_obs.x
            # Hurdle jump check
            if nearest_obs.type == OBSTACLE_HURDLE and abs(dx) < nearest_obs.width * 0.55:
                if 25 < (self.y - nearest_obs.y) < 130 and not self.is_jumping:
                    self.is_jumping = True
                    self.jump_progress = 0.0

            hazard_types = (
                OBSTACLE_MUD, OBSTACLE_QUICKSAND, OBSTACLE_PLASMA,
                OBSTACLE_HAYBALE, OBSTACLE_BOULDER, OBSTACLE_EMP, OBSTACLE_TUMBLEWEED
            )
            if nearest_obs.type in hazard_types or (not self.is_jumping and nearest_obs.type == OBSTACLE_HURDLE):
                safe_margin = (nearest_obs.width // 2) + 40
                if abs(dx) < safe_margin:
                    direction = 1.0 if dx >= 0 else -1.0
                    if self.x > TRACK_RIGHT - 120:
                        direction = -1.0
                    elif self.x < TRACK_LEFT + 120:
                        direction = 1.0
                    steer_impulse += direction * self.steer_speed * 1.5

        # Speed Pad homing attraction if directly ahead
        for pad in getattr(track, "speed_pads", []):
            if 0 < (self.y - pad.y) < lookahead:
                p_dx = pad.x - self.x
                if abs(p_dx) < 130:
                    steer_impulse += (1.0 if p_dx > 0 else -1.0) * self.steer_speed * 0.45
                break

        # Tactical lane separation
        for other in all_horses:
            if other.id == self.id:
                continue
            h_dx = self.x - other.x
            h_dy = self.y - other.y
            dist = math.hypot(h_dx, h_dy)
            if 0 < dist < 90:
                repel = (90 - dist) / 90.0
                direction = 1.0 if h_dx >= 0 else -1.0
                steer_impulse += direction * repel * 2.2

        # Rail avoidance
        if self.x < TRACK_LEFT + 70:
            steer_impulse += (TRACK_LEFT + 70 - self.x) * 0.12
        elif self.x > TRACK_RIGHT - 70:
            steer_impulse -= (self.x - (TRACK_RIGHT - 70)) * 0.12

        steer_impulse += self.lane_bias * 0.6
        self.vx += steer_impulse * 0.35
        self.vx *= 0.82
        self.x += self.vx

        # Hard rail clamp
        if self.x < TRACK_LEFT + 32:
            self.x = TRACK_LEFT + 32
            self.vx = abs(self.vx) * 0.5 + 1.5
        elif self.x > TRACK_RIGHT - 32:
            self.x = TRACK_RIGHT - 32
            self.vx = -abs(self.vx) * 0.5 - 1.5

        return new_projectile

    def update_physics(self, track, particle_system, sound_manager=None, audio_timeline=None, frame_idx=0):
        """Advances forward movement, gallop stride, obstacle collisions, and particles."""
        self.vy = -self.speed
        self.y += self.vy

        if self.is_jumping:
            self.jump_progress += 1.0 / self.jump_duration
            if self.jump_progress >= 1.0:
                self.is_jumping = False
                self.jump_progress = 0.0

        # --- Speed Pads Collision & Boost Activation ---
        for pad in getattr(track, "speed_pads", []):
            if pad.contains_point(self.x, self.y):
                if self.boost_timer <= 0:
                    self.boost_timer = 45
                    self.speed = min(self.base_top_speed * 1.35, self.speed + 4.2)
                    pad_type = getattr(pad, "pad_type", "turbo_amber")
                    if particle_system:
                        particle_system.emit_turbo_boost(self.x, self.y, pad_type)
                    if sound_manager:
                        sound_manager.play("boost")
                    if audio_timeline:
                        pan = ((self.x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                        audio_timeline.schedule(frame_idx, "boost", volume=0.65, pan=pan)
                break

        # --- Obstacles Collision & Hazards ---
        self.in_mud = False
        if not self.is_jumping:
            for obs in track.obstacles:
                if obs.type in (OBSTACLE_MUD, OBSTACLE_QUICKSAND, OBSTACLE_PLASMA) and obs.contains_point(self.x, self.y):
                    self.in_mud = True
                    if random.random() < 0.35:
                        if obs.type == OBSTACLE_QUICKSAND:
                            particle_system.emit_sand_dust(self.x, self.y + 20, count=4)
                        elif obs.type == OBSTACLE_PLASMA:
                            particle_system.emit_plasma_sparks(self.x, self.y + 20, count=5)
                        else:
                            particle_system.emit_mud_splash(self.x, self.y + 20)
                        if sound_manager and random.random() < 0.2:
                            sound_manager.play("mud")
                    break
                elif obs.type in (OBSTACLE_BOULDER, OBSTACLE_EMP, OBSTACLE_HAYBALE, OBSTACLE_TUMBLEWEED) and obs.contains_point(self.x, self.y):
                    if self.stumble_timer <= 0:
                        self.stumble_timer = 20
                        self.speed = max(4.0, self.speed * 0.65)
                        if particle_system:
                            if obs.type == OBSTACLE_EMP:
                                particle_system.emit_plasma_sparks(self.x, self.y, count=8)
                            else:
                                particle_system.emit_collision_bump(self.x, self.y)
                        if sound_manager:
                            sound_manager.play("bump")
                        if audio_timeline:
                            pan = ((self.x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                            audio_timeline.schedule(frame_idx, "bump", volume=0.5, pan=pan)
                    break

        if self.bump_cooldown > 0:
            self.bump_cooldown -= 1

        # Stride cycle
        self.stride_rate = 0.20 + (self.speed / self.base_top_speed) * 0.22
        prev_phase = self.stride_phase
        self.stride_phase = (self.stride_phase + self.stride_rate) % (2 * math.pi)

        # Footfall sound & track-specific particles
        if prev_phase < math.pi <= self.stride_phase:
            track_theme = getattr(track, "theme", TRACK_THEME_TURF)
            if track_theme == TRACK_THEME_DESERT:
                particle_system.emit_sand_dust(self.x, self.y + 28, self.vx, self.vy, count=4)
            elif track_theme == TRACK_THEME_CYBER:
                particle_system.emit_neon_sparks(self.x, self.y + 28, self.vx, self.vy, count=4)
            else:
                particle_system.emit_turf(self.x, self.y + 28, self.vx, self.vy)
            if sound_manager and random.random() < 0.22:
                sound_manager.play("hoofbeat")
            if audio_timeline and random.random() < 0.14:
                pan = ((self.x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                audio_timeline.schedule(frame_idx, "hoofbeat", volume=0.22, pan=pan)

        if self.is_sprinting and random.random() < 0.4:
            particle_system.emit_sprint_trail(self.x, self.y + 25, self.silk_color)

        self.heading = -self.vx * 3.2

    def resolve_bump_collision(self, other, particle_system, sound_manager=None, audio_timeline=None, frame_idx=0):
        dx = self.x - other.x
        dy = self.y - other.y
        dist = math.hypot(dx, dy)
        min_dist = COLLISION_RADIUS * 2.0

        if 0 < dist < min_dist:
            overlap = min_dist - dist
            nx = dx / dist

            total_grit = self.grit + other.grit
            self_ratio = other.grit / total_grit
            other_ratio = self.grit / total_grit

            self.x += nx * overlap * self_ratio * 0.65
            other.x -= nx * overlap * other_ratio * 0.65

            impulse = BUMP_IMPULSE
            self.vx += nx * impulse * self_ratio
            other.vx -= nx * impulse * other_ratio

            self.stumble_timer = 12
            other.stumble_timer = 12
            self.speed = max(8.0, self.speed - 1.2 * self_ratio)
            other.speed = max(8.0, other.speed - 1.2 * other_ratio)

            if self.bump_cooldown == 0 or other.bump_cooldown == 0:
                mid_x = (self.x + other.x) * 0.5
                mid_y = (self.y + other.y) * 0.5
                particle_system.emit_collision_bump(mid_x, mid_y)

                if sound_manager:
                    sound_manager.play("bump")
                if audio_timeline:
                    pan = ((mid_x - TRACK_LEFT) / TRACK_WIDTH) * 2.0 - 1.0
                    audio_timeline.schedule(frame_idx, "bump", volume=0.55, pan=pan)

                self.bump_cooldown = 18
                other.bump_cooldown = 18
                self.last_bump_other_id = other.id
                other.last_bump_other_id = self.id
                return True

        return False

    def draw(self, surface, camera_y, debug=False):
        """
        Renders the horse and rider with:
        - Human jockey character with jersey silks, helmet visor, goggles, and arms holding reins.
        - Dynamic leaning posture matching steering trajectory.
        - Equipped weapon icon display.
        - Stun spin-out animation & orbiting dizzy stars.
        """
        screen_y = self.y - camera_y
        if screen_y < -130 or screen_y > 2050:
            return

        jump_elevation = 0.0
        if self.is_jumping:
            jump_elevation = math.sin(self.jump_progress * math.pi) * 26.0

        render_y = screen_y - jump_elevation

        # If stunned, create a rotating sub-surface for the complete horse & rider
        is_stunned = self.stun_timer > 0
        if is_stunned:
            canvas_w = 160
            canvas_h = 180
            sub_surf = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            cx = canvas_w // 2
            cy = canvas_h // 2
            self._draw_horse_body(sub_surf, cx, cy, jump_elevation, 0.0)
            self._draw_jockey(sub_surf, cx, cy, jump_elevation, 0.0)

            # Rotate sub-surface
            rot_surf = pygame.transform.rotate(sub_surf, self.spin_angle)
            surface.blit(rot_surf, rot_surf.get_rect(center=(int(self.x), int(render_y))))

            # Orbiting cartoon dizzy stars above enlarged head
            for star_idx in range(3):
                star_angle = (self.spin_angle * 1.5 + star_idx * (360 / 3)) * (math.pi / 180)
                star_x = self.x + math.cos(star_angle) * 44
                star_y = render_y - 52 + math.sin(star_angle) * 14
                self._draw_mini_star(surface, (255, 230, 0), (int(star_x), int(star_y)), 9)
        else:
            # Normal gallop rendering
            lean_offset_x = -self.vx * 1.8
            self._draw_horse_body(surface, self.x, render_y, jump_elevation, lean_offset_x)
            self._draw_jockey(surface, self.x, render_y, jump_elevation, lean_offset_x)

        # Held Weapon Floating Indicator cleanly beside the enlarged head
        if self.held_weapon and not is_stunned:
            self._draw_held_weapon_badge(surface, self.x + 40, render_y - 26)

        # Sprint Aura Glow
        if self.is_sprinting:
            halo_surf = pygame.Surface((HORSE_WIDTH + 32, HORSE_LENGTH + 32), pygame.SRCALPHA)
            pygame.draw.ellipse(halo_surf, (*self.silk_color[:3], 50), halo_surf.get_rect())
            surface.blit(halo_surf, (self.x - halo_surf.get_width() // 2, render_y - halo_surf.get_height() // 2))

        # Debug feelers
        if debug:
            pygame.draw.circle(surface, (255, 0, 0), (int(self.x), int(screen_y)), COLLISION_RADIUS, 1)
            pygame.draw.line(surface, (0, 255, 255), (self.x, screen_y), (self.x, screen_y - 240), 1)

    def _draw_horse_body(self, surface, px, py, jump_elevation, lean_x):
        stride_sin = math.sin(self.stride_phase)
        stride_cos = math.cos(self.stride_phase)

        # 1. Soft Dynamic Drop Shadow
        shadow_w = int(HORSE_WIDTH * (1.0 - jump_elevation * 0.015))
        shadow_h = int(HORSE_LENGTH * (1.0 - jump_elevation * 0.012))
        shadow_surf = pygame.Surface((shadow_w + 20, shadow_h + 20), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow_surf, (20, 40, 25, max(30, int(115 - jump_elevation * 2.5))), shadow_surf.get_rect())
        surface.blit(shadow_surf, (px - shadow_surf.get_width() // 2, py + jump_elevation - shadow_surf.get_height() // 2 + 10))

        # 2. Galloping Legs
        front_left_ext = stride_sin * 18.0
        front_right_ext = -stride_sin * 18.0
        back_left_ext = stride_cos * 16.0
        back_right_ext = -stride_cos * 16.0
        leg_color = self.coat_color
        hoof_color = (35, 35, 35)

        # Back legs
        pygame.draw.line(surface, leg_color, (px - 12, py + 14), (px - 14, py + 30 + back_left_ext), 6)
        pygame.draw.circle(surface, hoof_color, (int(px - 14), int(py + 30 + back_left_ext)), 4)
        pygame.draw.line(surface, leg_color, (px + 12, py + 14), (px + 14, py + 30 + back_right_ext), 6)
        pygame.draw.circle(surface, hoof_color, (int(px + 14), int(py + 30 + back_right_ext)), 4)

        # Front legs
        pygame.draw.line(surface, leg_color, (px - 12, py - 12), (px - 14, py - 32 + front_left_ext), 6)
        pygame.draw.circle(surface, hoof_color, (int(px - 14), int(py - 32 + front_left_ext)), 4)
        pygame.draw.line(surface, leg_color, (px + 12, py - 12), (px + 14, py - 32 + front_right_ext), 6)
        pygame.draw.circle(surface, hoof_color, (int(px + 14), int(py - 32 + front_right_ext)), 4)

        # 3. Horse Torso (Sculpted & widened for realistic horse proportions under bobblehead)
        torso_w = HORSE_WIDTH + 8
        torso_rect = pygame.Rect(int(px - torso_w // 2), int(py - HORSE_LENGTH // 2 + 2), torso_w, HORSE_LENGTH - 6)
        pygame.draw.ellipse(surface, self.coat_color, torso_rect)

        # 4. Swaying Tail
        tail_sway = math.sin(self.stride_phase * 1.5) * 8.0
        pygame.draw.line(surface, self.mane_color, (px, py + HORSE_LENGTH // 2 - 4), (px + tail_sway * 0.6, py + HORSE_LENGTH // 2 + 14), 7)
        pygame.draw.line(surface, self.mane_color, (px + tail_sway * 0.6, py + HORSE_LENGTH // 2 + 14), (px + tail_sway, py + HORSE_LENGTH // 2 + 28), 5)

        # 5. Neck, Head & Muzzle (Extended boldly forward as an unmistakable direction pointer)
        head_bob = stride_sin * 4.0
        front_anchor = py - HORSE_LENGTH // 2 + head_bob

        # Horse Muscular Neck
        neck_rect = pygame.Rect(int(px - 11), int(front_anchor - 22), 22, 30)
        pygame.draw.ellipse(surface, self.coat_color, neck_rect)

        # Horse Forehead
        head_rect = pygame.Rect(int(px - 10), int(front_anchor - 44), 20, 28)
        pygame.draw.ellipse(surface, self.coat_color, head_rect)

        # Horse Muzzle & Snout (Extends past the 88px jockey avatar)
        muzzle_rect = pygame.Rect(int(px - 9), int(front_anchor - 50), 18, 16)
        pygame.draw.ellipse(surface, (50, 38, 30), muzzle_rect)
        # Nostrils
        pygame.draw.circle(surface, (20, 15, 10), (int(px - 4), int(front_anchor - 46)), 2)
        pygame.draw.circle(surface, (20, 15, 10), (int(px + 4), int(front_anchor - 46)), 2)

        # Horse Ears (Pointed forward and outward with inner shadow)
        ear_base_y = front_anchor - 34
        ear_tip_y = front_anchor - 52
        # Left Ear
        pygame.draw.polygon(surface, self.coat_color, [
            (px - 7, ear_base_y),
            (px - 13, ear_tip_y),
            (px - 3, ear_base_y - 6),
        ])
        pygame.draw.line(surface, (60, 45, 35), (px - 8, ear_base_y - 2), (px - 12, ear_tip_y + 4), 2)

        # Right Ear
        pygame.draw.polygon(surface, self.coat_color, [
            (px + 7, ear_base_y),
            (px + 13, ear_tip_y),
            (px + 3, ear_base_y - 6),
        ])
        pygame.draw.line(surface, (60, 45, 35), (px + 8, ear_base_y - 2), (px + 12, ear_tip_y + 4), 2)

        # Flowing Mane
        pygame.draw.line(surface, self.mane_color, (px, front_anchor - 32), (px, front_anchor + 6), 5)

        # 6. Saddle Blanket & Number (Positioned naturally behind rider)
        saddle_rect = pygame.Rect(int(px - 16), int(py + 6), 32, 26)
        pygame.draw.rect(surface, (255, 255, 255), saddle_rect, border_radius=4)
        pygame.draw.rect(surface, self.silk_color, saddle_rect, width=2, border_radius=4)
        num_font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 18, bold=True)
        num_txt = num_font.render(str(self.number), True, (20, 20, 20))
        surface.blit(num_txt, num_txt.get_rect(center=saddle_rect.center))

    def _draw_jockey(self, surface, px, py, jump_elevation, lean_x):
        """Draws human jockey character riding on top of the horse with jersey, helmet, and reins."""
        stride_bob = math.sin(self.stride_phase) * 2.0
        jx = px + lean_x * 0.4
        jy = py - 4 + stride_bob

        # Jockey Shoulders & Jersey Silks (Widened to peek naturally around the 88px head)
        shoulders_rect = pygame.Rect(int(jx - 24), int(jy + 2), 48, 22)
        pygame.draw.rect(surface, self.silk_color, shoulders_rect, border_radius=7)
        # Jersey collar / bib
        pygame.draw.polygon(surface, self.silk_accent, [
            (jx - 10, jy + 2),
            (jx + 10, jy + 2),
            (jx, jy + 14)
        ])
        # Jersey arm sleeves
        pygame.draw.rect(surface, self.silk_accent, (int(jx - 24), int(jy + 4), 6, 16), border_radius=2)
        pygame.draw.rect(surface, self.silk_accent, (int(jx + 18), int(jy + 4), 6, 16), border_radius=2)

        # Jockey Arms & Hands holding reins
        pygame.draw.line(surface, self.silk_color, (jx - 20, jy + 8), (jx - 14, jy - 8), 5)
        pygame.draw.line(surface, self.silk_color, (jx + 20, jy + 8), (jx + 14, jy - 8), 5)
        # Jockey Hands (skin tone)
        pygame.draw.circle(surface, self.jockey_skin, (int(jx - 14), int(jy - 8)), 4)
        pygame.draw.circle(surface, self.jockey_skin, (int(jx + 14), int(jy - 8)), 4)

        # Leather reins connecting hands to horse bridle
        reins_bit_y = py - HORSE_LENGTH // 2 - 28 + math.sin(self.stride_phase) * 4.0
        pygame.draw.line(surface, (50, 35, 25), (jx - 14, jy - 8), (px - 6, reins_bit_y), 2)
        pygame.draw.line(surface, (50, 35, 25), (jx + 14, jy - 8), (px + 6, reins_bit_y), 2)

        # Jockey Head: Prominent Big Head Meme Caricature (88x88 with 4px solid white border stroke)
        if self.avatar_head_surf:
            head_rect = self.avatar_head_surf.get_rect(center=(int(jx), int(jy - 22)))
            surface.blit(self.avatar_head_surf, head_rect)
        else:
            # Procedural circular caricature badge fallback (88x88 with 4px solid white outline)
            fb = pygame.Surface((88, 88), pygame.SRCALPHA)
            pygame.draw.circle(fb, self.silk_color, (44, 44), 42)
            pygame.draw.circle(fb, (255, 255, 255), (44, 44), 42, width=4)
            init_str = getattr(self, "initials", self.name[:2].upper())
            f_font = pygame.font.Font(None, 34)
            t_s = f_font.render(init_str, True, (255, 255, 255))
            fb.blit(t_s, t_s.get_rect(center=(44, 44)))
            surface.blit(fb, fb.get_rect(center=(int(jx), int(jy - 22))))

    def _draw_held_weapon_badge(self, surface, x, y):
        """Draws an equipped weapon floating icon above the jockey's shoulder."""
        badge_rect = pygame.Rect(int(x - 14), int(y - 14), 28, 28)
        pygame.draw.circle(surface, (15, 23, 42), (int(x), int(y)), 14)
        color = (56, 189, 248) if self.held_weapon == WEAPON_LASER else ((239, 68, 68) if self.held_weapon == WEAPON_ROCKET else (180, 115, 40))
        pygame.draw.circle(surface, color, (int(x), int(y)), 12)
        pygame.draw.circle(surface, (255, 255, 255), (int(x), int(y)), 12, width=2)

        font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 13, bold=True)
        label = "L" if self.held_weapon == WEAPON_LASER else ("R" if self.held_weapon == WEAPON_ROCKET else "B")
        txt = font.render(label, True, (255, 255, 255))
        surface.blit(txt, txt.get_rect(center=(int(x), int(y))))

    def _draw_mini_star(self, surface, color, center, radius):
        points = []
        for i in range(10):
            r = radius if i % 2 == 0 else radius * 0.44
            angle = i * math.pi / 5 - math.pi / 2
            points.append((center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)))
        pygame.draw.polygon(surface, color, points)
