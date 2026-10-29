"""
Race Track Generation, Geometry, Obstacles, Item Boxes, Speed Pads, and Multi-Map Rendering
==========================================================================================
Supports 3 full distinct track presets:
  1. Map 1: Classic Turf Derby (Traditional mowed lawn, white fence rails, mud & hurdles)
  2. Map 2: Desert Dunes Canyon (Warm golden sandstone, rock canyon barriers, quicksand & boulders, golden speed pads)
  3. Map 3: Cyber Neon Stadium (Dark carbon floor, glowing neon blue/magenta laser forcefields, EMP glitch zones & plasma traps, cyan acceleration grids)
"""

import math
import random
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TRACK_LEFT, TRACK_RIGHT, TRACK_WIDTH,
    TRACK_LENGTH, START_Y, FINISH_Y, NUM_HORSES,
    COLOR_TURF_LIGHT, COLOR_TURF_DARK, COLOR_TURF_OUTSIDE,
    COLOR_RAIL_WHITE, COLOR_RAIL_SHADOW, COLOR_FINISH_WHITE, COLOR_FINISH_BLACK,
    OBSTACLE_MUD, OBSTACLE_HURDLE, OBSTACLE_HAYBALE,
    WEAPON_LASER, WEAPON_MUD_BOMB, WEAPON_ROCKET, ALL_WEAPONS,
    ITEM_BOX_WIDTH, ITEM_BOX_HEIGHT
)

# Obstacle Type Identifiers
OBSTACLE_QUICKSAND = "quicksand"
OBSTACLE_BOULDER = "boulder"
OBSTACLE_TUMBLEWEED = "tumbleweed"
OBSTACLE_PLASMA = "plasma_trap"
OBSTACLE_EMP = "emp_glitch"

# Track Theme Identifiers
TRACK_THEME_TURF = "classic_turf"
TRACK_THEME_DESERT = "desert_dunes"
TRACK_THEME_CYBER = "cyber_neon"

ALL_TRACK_THEMES = [TRACK_THEME_TURF, TRACK_THEME_DESERT, TRACK_THEME_CYBER]

THEME_CONFIGS = {
    TRACK_THEME_TURF: {
        "id": TRACK_THEME_TURF,
        "name": "Classic Turf Derby",
        "subtitle": "TRADITIONAL TURF & HURDLES",
        "bg_outside": (30, 95, 58),
        "track_light": (46, 139, 87),
        "track_dark": (40, 125, 78),
        "lane_line": (55, 145, 95),
        "rail_main": (245, 245, 245),
        "rail_shadow": (180, 180, 180),
        "has_speed_pads": False,
        "pad_type": None,
        "banner_bg": (15, 23, 42),
        "banner_border": (255, 215, 0),
        "banner_text": "FINISH LINE",
        "banner_text_color": (255, 215, 0),
        "stall_bg": (30, 41, 59),
        "stall_accent": (255, 215, 0),
    },
    TRACK_THEME_DESERT: {
        "id": TRACK_THEME_DESERT,
        "name": "Desert Dunes Canyon",
        "subtitle": "SUN-BAKED SAND & BOULDERS",
        "bg_outside": (175, 105, 55),
        "track_light": (226, 184, 120),
        "track_dark": (210, 168, 102),
        "lane_line": (235, 215, 175),
        "rail_main": (118, 70, 40),
        "rail_shadow": (75, 42, 22),
        "has_speed_pads": True,
        "pad_type": "turbo_amber",
        "banner_bg": (58, 30, 15),
        "banner_border": (245, 158, 11),
        "banner_text": "CANYON FINISH",
        "banner_text_color": (254, 215, 118),
        "stall_bg": (70, 42, 24),
        "stall_accent": (245, 158, 11),
    },
    TRACK_THEME_CYBER: {
        "id": TRACK_THEME_CYBER,
        "name": "Cyber Neon Stadium",
        "subtitle": "MIDNIGHT SYNTHWAVE ARENA",
        "bg_outside": (10, 12, 24),
        "track_light": (20, 24, 38),
        "track_dark": (14, 17, 28),
        "lane_line": (0, 210, 255),
        "rail_main": (0, 225, 255),
        "rail_shadow": (180, 0, 160),
        "has_speed_pads": True,
        "pad_type": "cyber_cyan",
        "banner_bg": (8, 10, 22),
        "banner_border": (0, 240, 255),
        "banner_text": "CYBER FINISH",
        "banner_text_color": (0, 240, 255),
        "stall_bg": (12, 16, 32),
        "stall_accent": (0, 240, 255),
    }
}


class Obstacle:
    def __init__(self, obs_type, x, y, width, height, data=None):
        self.type = obs_type
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.data = data or {}
        self.rect = pygame.Rect(int(x - width // 2), int(y - height // 2), int(width), int(height))
        self.anim_phase = random.uniform(0, math.pi * 2)

    def contains_point(self, px, py):
        return self.rect.collidepoint(px, py)

    def update(self):
        self.anim_phase = (self.anim_phase + 0.08) % (math.pi * 2)


class SpeedPad:
    """Acceleration boost pad on track that gives horses an instant forward surge."""
    def __init__(self, x, y, width=130, height=75, pad_type="turbo_amber"):
        self.x = float(x)
        self.y = float(y)
        self.width = width
        self.height = height
        self.pad_type = pad_type
        self.rect = pygame.Rect(int(x - width // 2), int(y - height // 2), int(width), int(height))
        self.anim_phase = random.uniform(0, math.pi * 2)

    def contains_point(self, px, py):
        return self.rect.collidepoint(px, py)

    def update(self):
        self.anim_phase = (self.anim_phase + 0.14) % (math.pi * 2)

    def draw(self, surface, camera_y):
        sy = self.y - camera_y
        if sy < -100 or sy > SCREEN_HEIGHT + 100:
            return

        cx = int(self.x)
        cy = int(sy)
        w = int(self.width)
        h = int(self.height)
        rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
        pulse = 0.5 + 0.5 * math.sin(self.anim_phase)

        if self.pad_type == "turbo_amber":
            # Golden amber desert turbo boost chevrons
            glow_surf = pygame.Surface((w + 12, h + 12), pygame.SRCALPHA)
            alpha_glow = int(35 + pulse * 45)
            pygame.draw.rect(glow_surf, (245, 158, 11, alpha_glow), glow_surf.get_rect(), border_radius=12)
            surface.blit(glow_surf, (cx - (w + 12) // 2, cy - (h + 12) // 2))

            pygame.draw.rect(surface, (45, 28, 14), rect, border_radius=10)
            pygame.draw.rect(surface, (245, 158, 11), rect, width=2, border_radius=10)

            # Three animated chevron arrows pointing forward (up)
            arrow_c = (255, int(190 + pulse * 60), 20)
            for i, offset_y in enumerate([-18, 0, 18]):
                ay = cy + offset_y
                points = [
                    (cx - 38, ay + 10),
                    (cx, ay - 10),
                    (cx + 38, ay + 10),
                    (cx + 26, ay + 10),
                    (cx, ay - 2),
                    (cx - 26, ay + 10)
                ]
                pygame.draw.polygon(surface, arrow_c, points)

        else:
            # Cyberpunk glowing cyan & electric magenta acceleration grid
            glow_surf = pygame.Surface((w + 16, h + 16), pygame.SRCALPHA)
            alpha_glow = int(45 + pulse * 55)
            pygame.draw.rect(glow_surf, (0, 225, 255, alpha_glow), glow_surf.get_rect(), border_radius=14)
            surface.blit(glow_surf, (cx - (w + 16) // 2, cy - (h + 16) // 2))

            pygame.draw.rect(surface, (12, 16, 32), rect, border_radius=10)
            pygame.draw.rect(surface, (0, 240, 255), rect, width=2, border_radius=10)

            # Pulsing digital chevrons
            arrow_c = (0, 240, 255) if int(pulse * 6) % 2 == 0 else (255, 20, 147)
            for i, offset_y in enumerate([-18, 0, 18]):
                ay = cy + offset_y
                col = (0, 240, 255) if i % 2 == 0 else (255, 20, 147)
                points = [
                    (cx - 38, ay + 10),
                    (cx, ay - 10),
                    (cx + 38, ay + 10),
                    (cx + 26, ay + 10),
                    (cx, ay - 2),
                    (cx - 26, ay + 10)
                ]
                pygame.draw.polygon(surface, col, points)


class ItemBox:
    """Collectible mystery weapon crate along the track."""
    def __init__(self, x, y, weapon=None, theme=TRACK_THEME_TURF):
        self.x = float(x)
        self.y = float(y)
        self.width = ITEM_BOX_WIDTH
        self.height = ITEM_BOX_HEIGHT
        self.weapon = weapon or random.choice(ALL_WEAPONS)
        self.collected = False
        self.respawn_timer = 0
        self.rotation = random.uniform(0, 360)
        self.theme = theme

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.width // 2), int(self.y - self.height // 2), self.width, self.height)

    def update(self):
        self.rotation = (self.rotation + 3.0) % 360
        if self.collected:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                self.collected = False
                self.weapon = random.choice(ALL_WEAPONS)

    def draw(self, surface, camera_y):
        if self.collected:
            return

        screen_y = self.y - camera_y
        if screen_y < -60 or screen_y > SCREEN_HEIGHT + 60:
            return

        # Bobbing float effect
        bob = math.sin(self.rotation * 0.06) * 4.0
        render_y = screen_y + bob

        # Soft drop shadow
        shadow_rect = pygame.Rect(int(self.x - 18), int(screen_y + 16), 36, 14)
        shadow_color = (15, 30, 20) if self.theme == TRACK_THEME_TURF else ((45, 25, 15) if self.theme == TRACK_THEME_DESERT else (8, 10, 20))
        pygame.draw.ellipse(surface, shadow_color, shadow_rect)

        # Pulsing glow
        pulse = 0.5 + 0.5 * math.sin(self.rotation * 0.08)
        glow_size = int(self.width + 12 + pulse * 6)
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)

        if self.theme == TRACK_THEME_CYBER:
            glow_c = (0, 240, 255, int(50 + pulse * 50))
            crate_bg = (15, 23, 42)
            crate_border = (0, 240, 255)
            q_color = (0, 240, 255)
        elif self.theme == TRACK_THEME_DESERT:
            glow_c = (245, 158, 11, int(50 + pulse * 50))
            crate_bg = (180, 83, 9)
            crate_border = (254, 240, 138)
            q_color = (255, 255, 255)
        else:
            glow_c = (250, 204, 21, int(45 + pulse * 45))
            crate_bg = (245, 158, 11)
            crate_border = (254, 240, 138)
            q_color = (255, 255, 255)

        pygame.draw.rect(glow_surf, glow_c, glow_surf.get_rect(), border_radius=10)
        surface.blit(glow_surf, (self.x - glow_size // 2, render_y - glow_size // 2))

        # Crate body
        crate_rect = pygame.Rect(int(self.x - self.width // 2), int(render_y - self.height // 2), self.width, self.height)
        pygame.draw.rect(surface, crate_bg, crate_rect, border_radius=8)
        pygame.draw.rect(surface, crate_border, crate_rect, width=3, border_radius=8)

        # Question mark icon
        font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 28, bold=True)
        q_txt = font.render("?", True, q_color)
        surface.blit(q_txt, q_txt.get_rect(center=(int(self.x), int(render_y))))


class Track:
    def __init__(self, seed=None, theme=None):
        self.seed = seed

        # Resolve track theme preset
        if theme in ALL_TRACK_THEMES:
            self.theme = theme
        elif isinstance(theme, str) and theme.lower() in ("desert", "canyon", "dunes"):
            self.theme = TRACK_THEME_DESERT
        elif isinstance(theme, str) and theme.lower() in ("cyber", "neon", "stadium", "midnight"):
            self.theme = TRACK_THEME_CYBER
        elif isinstance(theme, str) and theme.lower() in ("turf", "classic", "derby"):
            self.theme = TRACK_THEME_TURF
        elif seed is not None:
            # Deterministic, seeded rotation: seed % 3 selects map
            self.theme = ALL_TRACK_THEMES[abs(int(seed)) % len(ALL_TRACK_THEMES)]
        else:
            self.theme = random.choice(ALL_TRACK_THEMES)

        self.theme_config = THEME_CONFIGS[self.theme]
        self.obstacles = []
        self.speed_pads = []
        self.item_boxes = []
        self.distance_markers = []

        self._generate_layout()
        self._setup_markers()

    def _generate_layout(self):
        """Generates realistic obstacles, speed pads, and weapon boxes along the track."""
        if self.seed is not None:
            random.seed(self.seed)

        self.obstacles.clear()
        self.speed_pads.clear()
        self.item_boxes.clear()

        cur_y = START_Y - 900
        min_y = FINISH_Y + 1000
        lane_w = TRACK_WIDTH / NUM_HORSES

        # Obstacle pools tailored per map theme
        if self.theme == TRACK_THEME_DESERT:
            obs_choices = [OBSTACLE_QUICKSAND, OBSTACLE_BOULDER, OBSTACLE_HURDLE, OBSTACLE_TUMBLEWEED]
        elif self.theme == TRACK_THEME_CYBER:
            obs_choices = [OBSTACLE_PLASMA, OBSTACLE_EMP, OBSTACLE_HURDLE]
        else:
            obs_choices = [OBSTACLE_MUD, OBSTACLE_HURDLE, OBSTACLE_HAYBALE]

        # Obstacles every 380 - 580 pixels
        while cur_y > min_y:
            zone_type = random.choice(obs_choices)
            lane_idx = random.randint(0, NUM_HORSES - 1)
            lane_center_x = TRACK_LEFT + (lane_idx + 0.5) * lane_w
            offset_x = random.uniform(-25, 25)
            obs_x = max(TRACK_LEFT + 65, min(TRACK_RIGHT - 65, lane_center_x + offset_x))

            if zone_type in (OBSTACLE_MUD, OBSTACLE_QUICKSAND, OBSTACLE_PLASMA):
                w = random.randint(125, 175)
                h = random.randint(85, 130)
                self.obstacles.append(Obstacle(zone_type, obs_x, cur_y, w, h))

            elif zone_type == OBSTACLE_HURDLE:
                w = random.randint(110, 150)
                h = 28
                self.obstacles.append(Obstacle(OBSTACLE_HURDLE, obs_x, cur_y, w, h))

            elif zone_type == OBSTACLE_BOULDER:
                w = random.randint(70, 95)
                h = random.randint(55, 75)
                self.obstacles.append(Obstacle(OBSTACLE_BOULDER, obs_x, cur_y, w, h))

            elif zone_type == OBSTACLE_EMP:
                w = random.randint(115, 160)
                h = random.randint(50, 75)
                self.obstacles.append(Obstacle(OBSTACLE_EMP, obs_x, cur_y, w, h))

            elif zone_type in (OBSTACLE_HAYBALE, OBSTACLE_TUMBLEWEED):
                w = random.randint(55, 75)
                h = random.randint(45, 60)
                self.obstacles.append(Obstacle(zone_type, obs_x, cur_y, w, h))

            cur_y -= random.randint(420, 600)

        # Speed Pads for Desert Canyon and Cyber Neon Stadium
        if self.theme_config.get("has_speed_pads"):
            pad_type = self.theme_config.get("pad_type", "turbo_amber")
            pad_y = START_Y - 2200
            while pad_y > min_y:
                # Place 1 or 2 speed pads across lanes
                num_pads = random.choice([1, 2])
                chosen_lanes = random.sample(range(NUM_HORSES), num_pads)
                for l_idx in chosen_lanes:
                    px = TRACK_LEFT + (l_idx + 0.5) * lane_w
                    self.speed_pads.append(SpeedPad(px, pad_y, width=130, height=75, pad_type=pad_type))

                pad_y -= random.randint(2400, 3600)

        # Item Boxes: placed every ~1800 to 2400 pixels in sets of 2 or 3
        box_y = START_Y - 1400
        while box_y > min_y:
            num_boxes_in_row = random.choice([2, 3])
            chosen_lanes = random.sample(range(NUM_HORSES), num_boxes_in_row)
            for l_idx in chosen_lanes:
                cx = TRACK_LEFT + (l_idx + 0.5) * lane_w + random.uniform(-15, 15)
                self.item_boxes.append(ItemBox(cx, box_y, theme=self.theme))

            box_y -= random.randint(1800, 2500)

    def _setup_markers(self):
        """Sets up milestone distance signs along the rails."""
        total_dist = START_Y - FINISH_Y
        fractions = [
            (0.20, "800m"),
            (0.40, "600m"),
            (0.60, "400m"),
            (0.80, "200m"),
            (0.90, "100m"),
            (0.95, "50m"),
            (1.00, "FINISH"),
        ]
        self.distance_markers = [(START_Y - total_dist * frac, label) for frac, label in fractions]

    def update(self):
        for box in self.item_boxes:
            box.update()
        for pad in self.speed_pads:
            pad.update()
        for obs in self.obstacles:
            obs.update()

    def draw(self, surface, camera_y):
        """Renders theme-specific track surface, boundary rails, obstacles, speed pads, item boxes, and finish line."""
        cfg = self.theme_config

        # 1. Outer Backgrounds (Off-Track)
        bg_color = cfg["bg_outside"]
        pygame.draw.rect(surface, bg_color, (0, 0, TRACK_LEFT, SCREEN_HEIGHT))
        pygame.draw.rect(surface, bg_color, (TRACK_RIGHT, 0, SCREEN_WIDTH - TRACK_RIGHT, SCREEN_HEIGHT))

        # Theme-Specific Off-Track Scenery
        if self.theme == TRACK_THEME_DESERT:
            # Sandstone canyon cliffs & cacti along the outside borders
            canyon_stripe = 160
            start_c = int(camera_y // canyon_stripe) - 1
            for c_idx in range(start_c, start_c + int(SCREEN_HEIGHT // canyon_stripe) + 3):
                cy_pos = c_idx * canyon_stripe - camera_y
                # Left mesa ridges
                pygame.draw.ellipse(surface, (155, 90, 45), (-60, cy_pos, 180, 80))
                # Right mesa ridges
                pygame.draw.ellipse(surface, (155, 90, 45), (SCREEN_WIDTH - 120, cy_pos + 40, 180, 80))
                # Occasional desert saguaro cactus silhouette
                if c_idx % 2 == 0:
                    cactus_y = cy_pos + 60
                    pygame.draw.rect(surface, (55, 105, 50), (45, cactus_y - 30, 8, 35), border_radius=4)
                    pygame.draw.rect(surface, (55, 105, 50), (32, cactus_y - 20, 34, 6), border_radius=3)
                    pygame.draw.rect(surface, (55, 105, 50), (SCREEN_WIDTH - 55, cactus_y - 30, 8, 35), border_radius=4)
                    pygame.draw.rect(surface, (55, 105, 50), (SCREEN_WIDTH - 68, cactus_y - 20, 34, 6), border_radius=3)

        elif self.theme == TRACK_THEME_CYBER:
            # Synthwave perspective grid lines in the outer void
            grid_spacing = 90
            start_g = int(camera_y // grid_spacing) - 1
            for g_idx in range(start_g, start_g + int(SCREEN_HEIGHT // grid_spacing) + 3):
                gy = g_idx * grid_spacing - camera_y
                pygame.draw.line(surface, (70, 20, 110), (0, gy), (TRACK_LEFT, gy), 1)
                pygame.draw.line(surface, (70, 20, 110), (TRACK_RIGHT, gy), (SCREEN_WIDTH, gy), 1)
                # Outer holographic pillars
                if g_idx % 3 == 0:
                    pygame.draw.rect(surface, (255, 20, 147), (TRACK_LEFT - 40, gy - 20, 8, 40), border_radius=4)
                    pygame.draw.rect(surface, (0, 240, 255), (TRACK_RIGHT + 32, gy - 20, 8, 40), border_radius=4)

        # 2. Main Racing Surface (Stripes / Sand Dunes / Carbon Grid)
        stripe_height = 140
        start_stripe_idx = int(camera_y // stripe_height) - 1
        num_stripes = int(SCREEN_HEIGHT // stripe_height) + 3

        for i in range(start_stripe_idx, start_stripe_idx + num_stripes):
            stripe_y = i * stripe_height - camera_y
            color = cfg["track_light"] if i % 2 == 0 else cfg["track_dark"]
            pygame.draw.rect(surface, color, (TRACK_LEFT, stripe_y, TRACK_WIDTH, stripe_height))

            # Extra visual detailing per theme
            if self.theme == TRACK_THEME_CYBER:
                # Synthwave horizontal grid lines on track
                pygame.draw.line(surface, (35, 45, 70), (TRACK_LEFT, stripe_y), (TRACK_RIGHT, stripe_y), 2)
            elif self.theme == TRACK_THEME_DESERT:
                # Dune sand ripple highlight
                pygame.draw.line(surface, (240, 205, 145), (TRACK_LEFT + 20, stripe_y + 40), (TRACK_RIGHT - 20, stripe_y + 45), 1)

        # Subtle Lane Guide Lines
        lane_w = TRACK_WIDTH / NUM_HORSES
        lane_col = cfg["lane_line"]
        for l in range(1, NUM_HORSES):
            lx = int(TRACK_LEFT + l * lane_w)
            if self.theme == TRACK_THEME_CYBER:
                # Glowing neon laser lane line
                col = (0, 225, 255) if l % 2 == 1 else (255, 20, 147)
                pygame.draw.line(surface, col, (lx, 0), (lx, SCREEN_HEIGHT), 2)
            else:
                pygame.draw.line(surface, lane_col, (lx, 0), (lx, SCREEN_HEIGHT), 2)

        # 3. Starting Gate / Stalls
        start_screen_y = int(START_Y - camera_y)
        if -200 < start_screen_y < SCREEN_HEIGHT + 200:
            stall_bg = cfg["stall_bg"]
            stall_accent = cfg["stall_accent"]
            pygame.draw.rect(surface, (230, 230, 230), (TRACK_LEFT, start_screen_y, TRACK_WIDTH, 14))
            pygame.draw.rect(surface, (180, 40, 40), (TRACK_LEFT, start_screen_y + 14, TRACK_WIDTH, 4))
            font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 28, bold=True)
            for l in range(NUM_HORSES):
                stall_cx = int(TRACK_LEFT + (l + 0.5) * lane_w)
                box_rect = pygame.Rect(stall_cx - 30, start_screen_y + 24, 60, 45)
                pygame.draw.rect(surface, stall_bg, box_rect, border_radius=6)
                pygame.draw.rect(surface, stall_accent, box_rect, width=2, border_radius=6)
                txt = font.render(str(l + 1), True, (255, 255, 255))
                surface.blit(txt, txt.get_rect(center=box_rect.center))

        # 4. Speed Pads (Desert Turbo Arrows & Cyber Acceleration Grids)
        for pad in self.speed_pads:
            pad.draw(surface, camera_y)

        # 5. Obstacles
        self.draw_obstacles(surface, camera_y)

        # 6. Item Boxes (Collectible Weapon Crates)
        for box in self.item_boxes:
            box.draw(surface, camera_y)

        # 7. Distance Markers (Boards on outer fences)
        marker_font = pygame.font.SysFont(["arial", "dejavusans", "liberationsans"], 22, bold=True)
        for my, label in self.distance_markers:
            sy = int(my - camera_y)
            if -60 < sy < SCREEN_HEIGHT + 60:
                l_rect = pygame.Rect(TRACK_LEFT - 125, sy - 18, 95, 36)
                r_rect = pygame.Rect(TRACK_RIGHT + 30, sy - 18, 95, 36)

                if self.theme == TRACK_THEME_CYBER:
                    # Neon LED digital display board
                    for rct in (l_rect, r_rect):
                        pygame.draw.rect(surface, (10, 15, 30), rct, border_radius=6)
                        pygame.draw.rect(surface, (0, 240, 255), rct, width=2, border_radius=6)
                        txt = marker_font.render(label, True, (0, 240, 255))
                        surface.blit(txt, txt.get_rect(center=rct.center))
                elif self.theme == TRACK_THEME_DESERT:
                    # Sandstone rock tablet
                    for rct in (l_rect, r_rect):
                        pygame.draw.rect(surface, (168, 120, 75), rct, border_radius=6)
                        pygame.draw.rect(surface, (245, 180, 50), rct, width=2, border_radius=6)
                        txt = marker_font.render(label, True, (255, 245, 220))
                        surface.blit(txt, txt.get_rect(center=rct.center))
                else:
                    # Traditional white wood boards
                    for rct in (l_rect, r_rect):
                        pygame.draw.rect(surface, (240, 240, 240), rct, border_radius=6)
                        pygame.draw.rect(surface, (20, 20, 20), rct, width=2, border_radius=6)
                        txt = marker_font.render(label, True, (20, 20, 20))
                        surface.blit(txt, txt.get_rect(center=rct.center))

        # 8. Finish Line Checkered Pattern & Overhead Banner
        finish_screen_y = int(FINISH_Y - camera_y)
        if -300 < finish_screen_y < SCREEN_HEIGHT + 300:
            sq_size = 20
            num_cols = int(TRACK_WIDTH // sq_size)
            for row in range(2):
                for col in range(num_cols):
                    if self.theme == TRACK_THEME_CYBER:
                        color = (0, 240, 255) if (row + col) % 2 == 0 else (255, 20, 147)
                    elif self.theme == TRACK_THEME_DESERT:
                        color = (255, 240, 200) if (row + col) % 2 == 0 else (60, 35, 18)
                    else:
                        color = COLOR_FINISH_WHITE if (row + col) % 2 == 0 else COLOR_FINISH_BLACK

                    pygame.draw.rect(
                        surface, color,
                        (TRACK_LEFT + col * sq_size, finish_screen_y + row * sq_size, sq_size, sq_size)
                    )

            line_color = (0, 240, 255) if self.theme == TRACK_THEME_CYBER else (255, 30, 30)
            pygame.draw.line(surface, line_color, (TRACK_LEFT, finish_screen_y), (TRACK_RIGHT, finish_screen_y), 3)

            # Overhead Banner
            banner_rect = pygame.Rect(TRACK_LEFT - 20, finish_screen_y - 75, TRACK_WIDTH + 40, 52)
            pygame.draw.rect(surface, cfg["banner_bg"], banner_rect, border_radius=8)
            pygame.draw.rect(surface, cfg["banner_border"], banner_rect, width=3, border_radius=8)

            banner_font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 36, bold=True)
            b_txt = banner_font.render(cfg["banner_text"], True, cfg["banner_text_color"])
            surface.blit(b_txt, b_txt.get_rect(center=banner_rect.center))

            post_col = (0, 240, 255) if self.theme == TRACK_THEME_CYBER else ((160, 90, 45) if self.theme == TRACK_THEME_DESERT else (200, 30, 30))
            pygame.draw.rect(surface, post_col, (TRACK_LEFT - 40, finish_screen_y - 90, 28, 120), border_radius=4)
            pygame.draw.rect(surface, post_col, (TRACK_RIGHT + 12, finish_screen_y - 90, 28, 120), border_radius=4)

        # 9. Left and Right Safety Rails
        self.draw_rails(surface, camera_y)

    def draw_obstacles(self, surface, camera_y):
        for obs in self.obstacles:
            sy = obs.y - camera_y
            if sy < -100 or sy > SCREEN_HEIGHT + 100:
                continue

            cx = int(obs.x)
            cy = int(sy)
            w = int(obs.width)
            h = int(obs.height)

            # --- MAP 1: Turf Derby Obstacles ---
            if obs.type == OBSTACLE_MUD:
                outer_rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
                pygame.draw.ellipse(surface, (60, 42, 28), outer_rect)
                inner_rect = pygame.Rect(cx - w // 2 + 6, cy - h // 2 + 5, w - 12, h - 10)
                pygame.draw.ellipse(surface, (90, 62, 38), inner_rect)
                highlight_rect = pygame.Rect(cx - w // 4, cy - h // 3, w // 2, h // 4)
                pygame.draw.ellipse(surface, (115, 80, 52), highlight_rect)

            elif obs.type == OBSTACLE_HURDLE:
                # Steeplechase Jumpable Hurdle
                shadow_rect = pygame.Rect(cx - w // 2, cy + 6, w, 14)
                shadow_c = (25, 75, 45) if self.theme == TRACK_THEME_TURF else ((120, 70, 35) if self.theme == TRACK_THEME_DESERT else (10, 15, 30))
                pygame.draw.rect(surface, shadow_c, shadow_rect, border_radius=4)

                post_c = (80, 50, 25) if self.theme != TRACK_THEME_CYBER else (0, 240, 255)
                pygame.draw.rect(surface, post_c, (cx - w // 2, cy - 14, 10, 28))
                pygame.draw.rect(surface, post_c, (cx + w // 2 - 10, cy - 14, 10, 28))

                bar_rect = pygame.Rect(cx - w // 2, cy - 10, w, 16)
                pygame.draw.rect(surface, (245, 245, 245), bar_rect, border_radius=3)
                pygame.draw.rect(surface, (50, 50, 50), bar_rect, width=1, border_radius=3)

                stripe_w = 18
                start_x = cx - w // 2
                end_x = cx + w // 2
                stripe_col = (220, 38, 38) if self.theme != TRACK_THEME_CYBER else (255, 20, 147)
                for sx in range(start_x, end_x, stripe_w * 2):
                    clip_w = min(stripe_w, end_x - sx)
                    if clip_w > 0:
                        pygame.draw.rect(surface, stripe_col, (sx, cy - 10, clip_w, 16))

            elif obs.type == OBSTACLE_HAYBALE:
                pygame.draw.ellipse(surface, (25, 75, 45), (cx - w // 2 + 4, cy - h // 2 + 8, w, h))
                bale_rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
                pygame.draw.rect(surface, (218, 165, 32), bale_rect, border_radius=10)
                pygame.draw.rect(surface, (184, 134, 11), bale_rect, width=2, border_radius=10)
                pygame.draw.line(surface, (139, 90, 43), (bale_rect.left, cy - 8), (bale_rect.right, cy - 8), 2)
                pygame.draw.line(surface, (139, 90, 43), (bale_rect.left, cy + 8), (bale_rect.right, cy + 8), 2)

            # --- MAP 2: Desert Dunes Canyon Obstacles ---
            elif obs.type == OBSTACLE_QUICKSAND:
                # Swirling golden-brown quicksand sinkhole
                pulse = 0.5 + 0.5 * math.sin(obs.anim_phase)
                pygame.draw.ellipse(surface, (110, 75, 38), (cx - w // 2, cy - h // 2, w, h))
                pygame.draw.ellipse(surface, (155, 108, 55), (cx - w // 2 + 10, cy - h // 2 + 8, w - 20, h - 16))
                pygame.draw.ellipse(surface, (75, 48, 24), (cx - w // 4, cy - h // 4, w // 2, h // 2))
                # Swirl rings
                ring_rad = int(w * 0.35 + pulse * 6)
                pygame.draw.arc(surface, (235, 185, 120), (cx - ring_rad, cy - ring_rad // 2, ring_rad * 2, ring_rad), 0, math.pi * 1.5, 2)

            elif obs.type == OBSTACLE_BOULDER:
                # Heavy canyon granite rock boulder (causes stun knockback)
                pygame.draw.ellipse(surface, (85, 48, 22), (cx - w // 2 + 6, cy - h // 2 + 10, w, h))
                b_rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
                pygame.draw.rect(surface, (145, 95, 55), b_rect, border_radius=16)
                pygame.draw.rect(surface, (185, 135, 85), b_rect, width=3, border_radius=16)
                # Rock facet cracks
                pygame.draw.line(surface, (100, 60, 30), (cx - 15, cy - 10), (cx + 10, cy + 5), 2)
                pygame.draw.line(surface, (100, 60, 30), (cx + 10, cy + 5), (cx + 25, cy - 8), 2)

            elif obs.type == OBSTACLE_TUMBLEWEED:
                # Prickly desert tumbleweed
                pygame.draw.ellipse(surface, (95, 55, 25), (cx - w // 2 + 3, cy + 4, w - 6, 12))
                tw_surf = pygame.Surface((w, h), pygame.SRCALPHA)
                # Multi-cross thorny twigs
                for ang in [0, 45, 90, 135]:
                    rad = math.radians(ang + obs.anim_phase * 40)
                    dx = math.cos(rad) * (w * 0.45)
                    dy = math.sin(rad) * (h * 0.45)
                    pygame.draw.line(tw_surf, (168, 120, 60), (w // 2 - dx, h // 2 - dy), (w // 2 + dx, h // 2 + dy), 3)
                surface.blit(tw_surf, (cx - w // 2, cy - h // 2))

            # --- MAP 3: Cyber Neon Stadium Obstacles ---
            elif obs.type == OBSTACLE_PLASMA:
                # Electric cyan/violet glowing plasma hazard trap (slows & shocks)
                pulse = 0.5 + 0.5 * math.sin(obs.anim_phase * 2)
                glow_s = pygame.Surface((w + 20, h + 20), pygame.SRCALPHA)
                pygame.draw.ellipse(glow_s, (0, 225, 255, int(40 + pulse * 40)), glow_s.get_rect())
                surface.blit(glow_s, (cx - (w + 20) // 2, cy - (h + 20) // 2))

                pygame.draw.ellipse(surface, (120, 20, 180), (cx - w // 2, cy - h // 2, w, h))
                pygame.draw.ellipse(surface, (0, 240, 255), (cx - w // 2 + 6, cy - h // 2 + 4, w - 12, h - 8), width=2)
                pygame.draw.ellipse(surface, (255, 255, 255), (cx - w // 4, cy - h // 4, w // 2, h // 2))

            elif obs.type == OBSTACLE_EMP:
                # Holographic EMP glitch zone (causes electric stumble)
                pulse = 0.5 + 0.5 * math.sin(obs.anim_phase * 3)
                emp_rect = pygame.Rect(cx - w // 2, cy - h // 2, w, h)
                emp_s = pygame.Surface((w, h), pygame.SRCALPHA)
                emp_s.fill((255, 20, 147, int(35 + pulse * 45)))
                surface.blit(emp_s, (cx - w // 2, cy - h // 2))
                pygame.draw.rect(surface, (255, 20, 147), emp_rect, width=2, border_radius=8)

                # Scanlines
                for scan_y in range(0, h, 8):
                    pygame.draw.line(surface, (0, 240, 255), (cx - w // 2 + 4, cy - h // 2 + scan_y), (cx + w // 2 - 4, cy - h // 2 + scan_y), 1)

    def draw_rails(self, surface, camera_y):
        rail_thickness = 10
        post_spacing = 90

        if self.theme == TRACK_THEME_CYBER:
            # Cyberpunk Glowing Neon Laser Forcefield
            pulse = 0.5 + 0.5 * math.sin(camera_y * 0.02)
            laser_alpha = int(120 + pulse * 60)

            # Left Forcefield Aura
            l_surf = pygame.Surface((20, SCREEN_HEIGHT), pygame.SRCALPHA)
            l_surf.fill((0, 225, 255, laser_alpha))
            surface.blit(l_surf, (TRACK_LEFT - 15, 0))

            # Right Forcefield Aura
            r_surf = pygame.Surface((20, SCREEN_HEIGHT), pygame.SRCALPHA)
            r_surf.fill((255, 20, 147, laser_alpha))
            surface.blit(r_surf, (TRACK_RIGHT - 5, 0))

            # Core Laser Beams
            pygame.draw.line(surface, (220, 255, 255), (TRACK_LEFT - 5, 0), (TRACK_LEFT - 5, SCREEN_HEIGHT), 3)
            pygame.draw.line(surface, (255, 240, 255), (TRACK_RIGHT + 5, 0), (TRACK_RIGHT + 5, SCREEN_HEIGHT), 3)

            # Emitter Pylons
            start_p = int(camera_y // post_spacing) - 1
            for i in range(start_p, start_p + int(SCREEN_HEIGHT // post_spacing) + 3):
                py = i * post_spacing - camera_y
                pygame.draw.circle(surface, (0, 240, 255), (TRACK_LEFT - 5, int(py)), 8)
                pygame.draw.circle(surface, (255, 255, 255), (TRACK_LEFT - 5, int(py)), 4)
                pygame.draw.circle(surface, (255, 20, 147), (TRACK_RIGHT + 5, int(py)), 8)
                pygame.draw.circle(surface, (255, 255, 255), (TRACK_RIGHT + 5, int(py)), 4)

        elif self.theme == TRACK_THEME_DESERT:
            # Canyon Rock Wall & Heavy Weathered Timber Rails
            cfg = self.theme_config
            pygame.draw.rect(surface, cfg["rail_shadow"], (TRACK_LEFT - 8, 0, rail_thickness + 2, SCREEN_HEIGHT))
            pygame.draw.rect(surface, cfg["rail_main"], (TRACK_LEFT - 10, 0, rail_thickness, SCREEN_HEIGHT))
            pygame.draw.rect(surface, cfg["rail_shadow"], (TRACK_RIGHT + 2, 0, rail_thickness + 2, SCREEN_HEIGHT))
            pygame.draw.rect(surface, cfg["rail_main"], (TRACK_RIGHT, 0, rail_thickness, SCREEN_HEIGHT))

            # Natural Canyon Stone Boulder Posts
            start_p = int(camera_y // post_spacing) - 1
            for i in range(start_p, start_p + int(SCREEN_HEIGHT // post_spacing) + 3):
                py = i * post_spacing - camera_y
                pygame.draw.ellipse(surface, (140, 85, 45), (TRACK_LEFT - 14, int(py - 6), 16, 14))
                pygame.draw.ellipse(surface, (185, 135, 80), (TRACK_LEFT - 13, int(py - 5), 14, 12))
                pygame.draw.ellipse(surface, (140, 85, 45), (TRACK_RIGHT - 2, int(py - 6), 16, 14))
                pygame.draw.ellipse(surface, (185, 135, 80), (TRACK_RIGHT - 1, int(py - 5), 14, 12))

        else:
            # Traditional Turf Derby White Safety Rails
            pygame.draw.rect(surface, COLOR_RAIL_SHADOW, (TRACK_LEFT - 8, 0, rail_thickness + 2, SCREEN_HEIGHT))
            pygame.draw.rect(surface, COLOR_RAIL_WHITE, (TRACK_LEFT - 10, 0, rail_thickness, SCREEN_HEIGHT))
            pygame.draw.rect(surface, COLOR_RAIL_SHADOW, (TRACK_RIGHT + 2, 0, rail_thickness + 2, SCREEN_HEIGHT))
            pygame.draw.rect(surface, COLOR_RAIL_WHITE, (TRACK_RIGHT, 0, rail_thickness, SCREEN_HEIGHT))

            start_post_idx = int(camera_y // post_spacing) - 1
            num_posts = int(SCREEN_HEIGHT // post_spacing) + 3
            for i in range(start_post_idx, start_post_idx + num_posts):
                post_y = i * post_spacing - camera_y
                pygame.draw.circle(surface, COLOR_RAIL_SHADOW, (TRACK_LEFT - 5, int(post_y + 2)), 8)
                pygame.draw.circle(surface, COLOR_RAIL_WHITE, (TRACK_LEFT - 6, int(post_y)), 7)
                pygame.draw.circle(surface, COLOR_RAIL_SHADOW, (TRACK_RIGHT + 5, int(post_y + 2)), 8)
                pygame.draw.circle(surface, COLOR_RAIL_WHITE, (TRACK_RIGHT + 5, int(post_y)), 7)
