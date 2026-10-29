"""
Weapons & Projectiles Physics Engine
Handles Laser Darts, Mud Bombs, and Homing Rockets fired by horses during the race.
"""

import math
import random
import pygame
from config import (
    SCREEN_HEIGHT, COLLISION_RADIUS, STUN_DURATION,
    WEAPON_LASER, WEAPON_MUD_BOMB, WEAPON_ROCKET
)

class Projectile:
    def __init__(self, p_type, shooter_id, shooter_name, x, y, target_horse=None):
        self.p_type = p_type
        self.shooter_id = shooter_id
        self.shooter_name = shooter_name
        self.x = float(x)
        self.y = float(y)
        self.target_horse = target_horse
        self.alive = True
        self.life = 120  # frames before expiring

        if self.p_type == WEAPON_LASER:
            self.speed = 32.0
            self.vx = 0.0
            self.vy = -self.speed
            self.radius = 8.0
        elif self.p_type == WEAPON_MUD_BOMB:
            self.speed = 22.0
            self.vx = random.uniform(-1.0, 1.0)
            self.vy = -self.speed
            self.radius = 16.0
            self.arc_height = 0.0
            self.arc_time = 0
        elif self.p_type == WEAPON_ROCKET:
            self.speed = 26.0
            self.vx = 0.0
            self.vy = -self.speed
            self.radius = 12.0

    def update(self, all_horses, particle_system, sound_manager=None, audio_timeline=None, frame_idx=0):
        if not self.alive:
            return None

        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return None

        # Movement logic
        if self.p_type == WEAPON_LASER:
            self.y += self.vy
            # Laser trail particles
            if random.random() < 0.6:
                particle_system.emit_sprint_trail(self.x, self.y + 10, (56, 189, 248))

        elif self.p_type == WEAPON_MUD_BOMB:
            self.x += self.vx
            self.y += self.vy
            self.arc_time += 1
            # Parabolic hop
            self.arc_height = math.sin(min(math.pi, self.arc_time * 0.07)) * 25.0
            if random.random() < 0.4:
                particle_system.emit_mud_splash(self.x, self.y)

        elif self.p_type == WEAPON_ROCKET:
            # Homing steering toward target horse if alive
            if self.target_horse and not self.target_horse.is_finished:
                tx = self.target_horse.x
                ty = self.target_horse.y
                dx = tx - self.x
                dy = ty - self.y
                dist = math.hypot(dx, dy)
                if dist > 5.0:
                    desired_vx = (dx / dist) * self.speed
                    desired_vy = (dy / dist) * self.speed
                    self.vx += (desired_vx - self.vx) * 0.22
                    self.vy += (desired_vy - self.vy) * 0.22

            self.x += self.vx
            self.y += self.vy

            # Rocket smoke & fire trail
            if random.random() < 0.8:
                particle_system.emit_turf(self.x, self.y + 12, -self.vx * 0.2, 5.0)

        # Check collision with other horses ahead
        hit_event = None
        for horse in all_horses:
            if horse.id == self.shooter_id or horse.is_finished:
                continue

            dist = math.hypot(self.x - horse.x, self.y - horse.y)
            if dist < (COLLISION_RADIUS + self.radius):
                # DIRECT HIT!
                self.alive = False
                horse.apply_stun(STUN_DURATION, self.p_type)

                # Sound & Visual Effects
                if self.p_type == WEAPON_LASER:
                    particle_system.emit_collision_bump(self.x, self.y)
                    if sound_manager:
                        sound_manager.play("stun")
                    if audio_timeline:
                        audio_timeline.schedule(frame_idx, "stun", volume=0.55)

                elif self.p_type == WEAPON_MUD_BOMB:
                    for _ in range(3):
                        particle_system.emit_mud_splash(self.x, self.y)
                    if sound_manager:
                        sound_manager.play("mud")
                        sound_manager.play("stun")
                    if audio_timeline:
                        audio_timeline.schedule(frame_idx, "mud", volume=0.6)
                        audio_timeline.schedule(frame_idx, "stun", volume=0.5)

                elif self.p_type == WEAPON_ROCKET:
                    particle_system.emit_collision_bump(self.x, self.y)
                    if sound_manager:
                        sound_manager.play("explosion")
                        sound_manager.play("stun")
                    if audio_timeline:
                        audio_timeline.schedule(frame_idx, "explosion", volume=0.7)
                        audio_timeline.schedule(frame_idx, "stun", volume=0.55)

                hit_event = {
                    "shooter_name": self.shooter_name,
                    "target_name": horse.name,
                    "weapon": self.p_type
                }
                break

        return hit_event

    def draw(self, surface, camera_y):
        if not self.alive:
            return

        screen_y = self.y - camera_y
        if screen_y < -50 or screen_y > SCREEN_HEIGHT + 50:
            return

        if self.p_type == WEAPON_LASER:
            # High-intensity glowing energy bolt
            glow_surf = pygame.Surface((28, 48), pygame.SRCALPHA)
            pygame.draw.ellipse(glow_surf, (56, 189, 248, 90), glow_surf.get_rect())
            surface.blit(glow_surf, (self.x - 14, screen_y - 24))
            # Core beam
            pygame.draw.line(surface, (255, 255, 255), (self.x, screen_y - 18), (self.x, screen_y + 18), 5)
            pygame.draw.line(surface, (14, 165, 233), (self.x, screen_y - 14), (self.x, screen_y + 14), 8)

        elif self.p_type == WEAPON_MUD_BOMB:
            render_y = screen_y - self.arc_height
            # Shadow below
            shadow_rect = pygame.Rect(self.x - 10, screen_y - 5, 20, 10)
            pygame.draw.ellipse(surface, (20, 35, 20), shadow_rect)
            # Round mud bomb
            pygame.draw.circle(surface, (80, 50, 30), (int(self.x), int(render_y)), 12)
            pygame.draw.circle(surface, (120, 80, 45), (int(self.x - 3), int(render_y - 3)), 6)
            # Fuse spark
            pygame.draw.circle(surface, (255, 200, 50), (int(self.x), int(render_y - 12)), 3)

        elif self.p_type == WEAPON_ROCKET:
            # Red/Orange rocket projectile
            angle = math.atan2(self.vy, self.vx) + math.pi / 2
            rocket_surf = pygame.Surface((22, 36), pygame.SRCALPHA)
            # Body
            pygame.draw.polygon(rocket_surf, (239, 68, 68), [(11, 0), (20, 24), (2, 24)])
            # Fins
            pygame.draw.polygon(rocket_surf, (249, 115, 22), [(2, 24), (0, 32), (6, 28)])
            pygame.draw.polygon(rocket_surf, (249, 115, 22), [(20, 24), (22, 32), (16, 28)])
            # Flame exhaust
            pygame.draw.polygon(rocket_surf, (255, 240, 100), [(7, 26), (11, 35), (15, 26)])

            rot_surf = pygame.transform.rotate(rocket_surf, -math.degrees(angle))
            surface.blit(rot_surf, rot_surf.get_rect(center=(self.x, screen_y)))

