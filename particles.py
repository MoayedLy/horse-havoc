"""
Visual Particle Effects Engine
Handles turf clods, mud splatters, collision shockwaves, sprint streaks, and finish confetti.
"""

import math
import random
import pygame

class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "p_type", "alpha")

    def __init__(self, x, y, vx, vy, life, color, size, p_type="normal"):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.p_type = p_type
        self.alpha = 255

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        progress = self.life / self.max_life

        if self.p_type == "turf":
            self.vy *= 0.94
            self.vx *= 0.92
            self.size = max(1.0, self.size * 0.97)
        elif self.p_type == "mud":
            self.vy += 0.2  # Gravity
            self.vx *= 0.93
        elif self.p_type == "shockwave":
            self.size += 3.5  # Expanding ring
        elif self.p_type == "streak":
            self.alpha = int(255 * progress)
        elif self.p_type == "confetti":
            self.vy += 0.08  # Slow flutter
            self.vx += math.sin(self.life * 0.3) * 0.2
            self.size = max(2.0, self.size)

        return self.life > 0


class ParticleSystem:
    def __init__(self):
        self.particles = []

    def emit_turf(self, x, y, vx_horse, vy_horse):
        """Kicks up green turf clods and dirt specks from hooves."""
        for _ in range(random.randint(2, 4)):
            vx = random.uniform(-1.5, 1.5) - vx_horse * 0.1
            vy = random.uniform(3.0, 7.0)   # Flies backward
            life = random.randint(18, 32)
            c = random.choice([
                (76, 175, 80),   # Light grass
                (46, 125, 50),   # Dark grass
                (139, 90, 43),   # Dirt
                (101, 67, 33),   # Dark soil
            ])
            size = random.uniform(2.5, 4.5)
            self.particles.append(Particle(x, y, vx, vy, life, c, size, "turf"))

    def emit_mud_splash(self, x, y):
        """Violent splash of brown mud when galloping through puddles."""
        for _ in range(random.randint(6, 10)):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(2.5, 6.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd + 2.0
            life = random.randint(20, 38)
            c = random.choice([
                (92, 64, 51),
                (120, 85, 55),
                (70, 45, 30),
            ])
            size = random.uniform(3.5, 6.0)
            self.particles.append(Particle(x, y, vx, vy, life, c, size, "mud"))

    def emit_collision_bump(self, x, y):
        """Shockwave ring and bright dust burst on horse collision."""
        # Expanding shockwave ring
        self.particles.append(Particle(x, y, 0, 0, 16, (255, 235, 160), 6.0, "shockwave"))
        # Sparks / dust
        for _ in range(12):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(3.0, 8.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = random.randint(15, 26)
            c = random.choice([
                (255, 255, 200),
                (255, 180, 50),
                (240, 240, 240),
            ])
            self.particles.append(Particle(x, y, vx, vy, life, c, random.uniform(2.5, 4.5), "normal"))

    def emit_sprint_trail(self, x, y, color):
        """Streamers of energy trailing behind a sprinting horse."""
        vx = random.uniform(-0.8, 0.8)
        vy = random.uniform(2.5, 5.0)
        life = 14
        self.particles.append(Particle(x, y, vx, vy, life, color, random.uniform(2.5, 4.0), "streak"))

    def emit_sand_dust(self, x, y, vx_horse=0.0, vy_horse=0.0, count=4):
        """Kicks up golden sand dust and desert pebbles from hooves."""
        for _ in range(count or random.randint(2, 4)):
            vx = random.uniform(-1.8, 1.8) - vx_horse * 0.1
            vy = random.uniform(2.5, 6.0)
            life = random.randint(16, 28)
            c = random.choice([
                (226, 184, 120),  # Golden sand
                (205, 155, 95),   # Deep sandstone
                (245, 215, 160),  # Light sunlit dune dust
                (140, 90, 50),    # Desert pebble
            ])
            self.particles.append(Particle(x, y, vx, vy, life, c, random.uniform(2.5, 5.0), "turf"))

    def emit_neon_sparks(self, x, y, vx_horse=0.0, vy_horse=0.0, count=3):
        """Kicks up digital synthwave photon sparks on cyber asphalt."""
        for _ in range(count or random.randint(2, 3)):
            vx = random.uniform(-2.0, 2.0) - vx_horse * 0.08
            vy = random.uniform(2.0, 5.5)
            life = random.randint(12, 22)
            c = random.choice([
                (0, 240, 255),    # Neon cyan
                (255, 20, 147),   # Electric magenta
                (180, 80, 255),   # Synthwave purple
                (255, 255, 255),  # Pure photon white
            ])
            self.particles.append(Particle(x, y, vx, vy, life, c, random.uniform(2.0, 4.0), "streak"))

    def emit_turbo_boost(self, x, y, pad_type="turbo_amber"):
        """High-velocity particle burst when crossing a speed boost pad."""
        if pad_type == "turbo_amber":
            colors = [(255, 200, 30), (255, 120, 10), (255, 240, 120), (245, 158, 11)]
        else:
            colors = [(0, 245, 255), (255, 20, 147), (140, 80, 255), (255, 255, 255)]

        for _ in range(16):
            ang = random.uniform(0.2 * math.pi, 0.8 * math.pi)  # Spays downward/backward
            spd = random.uniform(4.0, 10.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = random.randint(18, 30)
            c = random.choice(colors)
            self.particles.append(Particle(x, y, vx, vy, life, c, random.uniform(3.0, 6.0), "streak"))

    def emit_plasma_sparks(self, x, y, count=8):
        """Electric shock arc burst when hitting cyber plasma puddle."""
        for _ in range(count):
            ang = random.uniform(0, 2 * math.pi)
            spd = random.uniform(3.0, 7.0)
            vx = math.cos(ang) * spd
            vy = math.sin(ang) * spd
            life = random.randint(14, 24)
            c = random.choice([(0, 240, 255), (255, 0, 180), (180, 100, 255), (255, 255, 255)])
            self.particles.append(Particle(x, y, vx, vy, life, c, random.uniform(2.5, 5.0), "streak"))

    def emit_confetti(self, x_center, y_center, count=80):
        """Festive confetti explosion at the finish line."""
        colors = [
            (255, 50, 50), (50, 150, 255), (255, 215, 0),
            (50, 220, 100), (230, 50, 230), (255, 140, 0)
        ]
        for _ in range(count):
            x = x_center + random.uniform(-350, 350)
            y = y_center + random.uniform(-100, 100)
            vx = random.uniform(-3.5, 3.5)
            vy = random.uniform(-6.0, -1.0)
            life = random.randint(90, 180)
            c = random.choice(colors)
            size = random.uniform(4.0, 8.0)
            self.particles.append(Particle(x, y, vx, vy, life, c, size, "confetti"))

    def update(self):
        surviving = []
        for p in self.particles:
            if p.update():
                surviving.append(p)
        self.particles = surviving

    def draw(self, surface, camera_y):
        """Draw all particles relative to vertical camera scroll."""
        for p in self.particles:
            screen_y = p.y - camera_y
            # Culling if off screen
            if screen_y < -50 or screen_y > 1970:
                continue

            if p.p_type == "shockwave":
                # Draw circular shockwave ring
                progress = p.life / p.max_life
                alpha = int(255 * progress)
                ring_surf = pygame.Surface((int(p.size * 2 + 4), int(p.size * 2 + 4)), pygame.SRCALPHA)
                pygame.draw.circle(
                    ring_surf,
                    (*p.color[:3], alpha),
                    (int(p.size + 2), int(p.size + 2)),
                    int(p.size),
                    width=max(2, int(4 * progress))
                )
                surface.blit(ring_surf, (p.x - p.size - 2, screen_y - p.size - 2))

            elif p.p_type == "streak":
                progress = p.life / p.max_life
                alpha = int(180 * progress)
                s_surf = pygame.Surface((int(p.size * 2), int(p.size * 2)), pygame.SRCALPHA)
                pygame.draw.circle(s_surf, (*p.color[:3], alpha), (int(p.size), int(p.size)), int(p.size))
                surface.blit(s_surf, (p.x - p.size, screen_y - p.size))

            elif p.p_type == "confetti":
                # Little rotating rectangles
                rect_surf = pygame.Surface((int(p.size), int(p.size * 1.6)), pygame.SRCALPHA)
                rect_surf.fill(p.color)
                rot_surf = pygame.transform.rotate(rect_surf, p.life * 12)
                surface.blit(rot_surf, (p.x, screen_y))

            else:
                pygame.draw.circle(surface, p.color, (int(p.x), int(screen_y)), int(p.size))

