"""
Horse Racing Game Configuration & Constants
Resolution: 1080x1920 (Vertical 9:16 - YouTube Shorts / Reels format)
Paced for Strict 45-Second Match Duration (Lead horse crosses at ~42s + 3s podium celebration)
"""

import math

# Screen & Render Dimensions
SCREEN_WIDTH = 1080
SCREEN_HEIGHT = 1920
FPS = 60

# Track Geometry (Tuned for Strict ~45-Second Total Duration)
TRACK_WIDTH = 740                               # Usable width of the race track
TRACK_LEFT = (SCREEN_WIDTH - TRACK_WIDTH) // 2  # 170
TRACK_RIGHT = TRACK_LEFT + TRACK_WIDTH          # 910
TRACK_LENGTH = 42000                            # Total track length
START_Y = 41000                                 # Start line
FINISH_Y = 1000                                 # Finish line
TOTAL_RACE_DISTANCE = START_Y - FINISH_Y        # 40,000 pixels

# Celebration delay after winner crosses finish line (exactly 3.0 seconds at 60 FPS)
CELEBRATION_DURATION = 180                      # 180 frames = 3.0 seconds
PODIUM_APPEAR_DELAY = 45                        # 45 frames = 0.75s after crossing line

# Lane setup for 5 horses
NUM_HORSES = 5
LANE_WIDTH = TRACK_WIDTH / NUM_HORSES

# Color Palette (Rich RGB)
COLOR_TURF_LIGHT = (46, 139, 87)       # Lush Sea Green
COLOR_TURF_DARK = (40, 125, 78)        # Darker grass stripe
COLOR_TURF_OUTSIDE = (30, 95, 58)      # Deep fairway border
COLOR_DIRT_BORDER = (139, 90, 43)      # Earthy brown rail border
COLOR_RAIL_WHITE = (245, 245, 245)     # Bright white fence rail
COLOR_RAIL_SHADOW = (180, 180, 180)    # Fence shadow
COLOR_FINISH_WHITE = (255, 255, 255)
COLOR_FINISH_BLACK = (20, 20, 20)

# UI & HUD Colors
COLOR_HUD_BG = (15, 23, 42, 220)       # Slate dark semi-transparent
COLOR_GOLD = (255, 215, 0)
COLOR_SILVER = (200, 210, 220)
COLOR_BRONZE = (205, 127, 50)
COLOR_WHITE = (255, 255, 255)
COLOR_ACCENT = (255, 99, 71)

# Physics & Horse Dynamics
HORSE_LENGTH = 72                      # Horse body length
HORSE_WIDTH = 34                       # Horse body width
COLLISION_RADIUS = 26                  # Circular radius for body bump physics
BASE_ACCEL = 4.2
BASE_FRICTION = 0.94
KNOCKBACK_DAMPING = 0.88
BUMP_IMPULSE = 6.5                     # Lateral bounce force on collision

# Weapon & Item Constants
WEAPON_LASER = "laser"
WEAPON_MUD_BOMB = "mud_bomb"
WEAPON_ROCKET = "rocket"
ALL_WEAPONS = [WEAPON_LASER, WEAPON_MUD_BOMB, WEAPON_ROCKET]

ITEM_BOX_WIDTH = 46
ITEM_BOX_HEIGHT = 46
STUN_DURATION = 95                     # ~1.6 seconds stun at 60 FPS

# Horse Profiles with unique AI personalities, colors, and racing stats
# Paced for ~42s sprint to the finish line
HORSE_PROFILES = [
    {
        "id": 0,
        "name": "Thunderbolt",
        "number": 1,
        "archetype": "Front Runner",
        "coat_color": (160, 82, 45),       # Rich Sienna / Chestnut
        "mane_color": (70, 30, 15),
        "silk_color": (220, 38, 38),       # Crimson Red
        "silk_accent": (255, 255, 255),
        "jockey_skin": (235, 195, 165),
        "top_speed": 17.6,
        "accel": 4.8,
        "stamina": 100.0,
        "stamina_drain": 0.0135,
        "sprint_threshold": 5600,
        "grit": 1.15,
        "lane_bias": -0.15,
        "steer_speed": 4.6,
    },
    {
        "id": 1,
        "name": "Shadowfax",
        "number": 2,
        "archetype": "Tactician",
        "coat_color": (230, 232, 235),     # Silver White / Dapple Grey
        "mane_color": (190, 195, 200),
        "silk_color": (37, 99, 235),       # Sapphire Blue
        "silk_accent": (255, 255, 255),
        "jockey_skin": (225, 185, 155),
        "top_speed": 17.3,
        "accel": 4.4,
        "stamina": 100.0,
        "stamina_drain": 0.0110,
        "sprint_threshold": 4800,
        "grit": 1.0,
        "lane_bias": 0.0,
        "steer_speed": 5.2,
    },
    {
        "id": 2,
        "name": "Midnight Star",
        "number": 3,
        "archetype": "Late Rusher",
        "coat_color": (28, 28, 32),        # Jet Black
        "mane_color": (15, 15, 18),
        "silk_color": (147, 51, 234),      # Royal Purple
        "silk_accent": (250, 204, 21),
        "jockey_skin": (240, 200, 170),
        "top_speed": 18.2,                 # Blistering top end speed
        "accel": 4.1,
        "stamina": 100.0,
        "stamina_drain": 0.0105,
        "sprint_threshold": 4200,
        "grit": 0.95,
        "lane_bias": 0.2,
        "steer_speed": 4.8,
    },
    {
        "id": 3,
        "name": "Solar Flare",
        "number": 4,
        "archetype": "Brawler",
        "coat_color": (218, 165, 32),      # Golden Palomino
        "mane_color": (255, 239, 180),
        "silk_color": (234, 88, 12),       # Vivid Orange
        "silk_accent": (254, 240, 138),
        "jockey_skin": (210, 170, 140),
        "top_speed": 17.1,
        "accel": 4.3,
        "stamina": 100.0,
        "stamina_drain": 0.0115,
        "sprint_threshold": 5000,
        "grit": 1.50,                      # Heavy tank
        "lane_bias": -0.05,
        "steer_speed": 4.2,
    },
    {
        "id": 4,
        "name": "Zephyr Wind",
        "number": 5,
        "archetype": "Nimble Weaver",
        "coat_color": (115, 60, 30),       # Mahogany Bay
        "mane_color": (20, 20, 20),
        "silk_color": (13, 148, 136),      # Emerald Teal
        "silk_accent": (255, 255, 255),
        "jockey_skin": (230, 190, 160),
        "top_speed": 17.5,
        "accel": 4.6,
        "stamina": 100.0,
        "stamina_drain": 0.0112,
        "sprint_threshold": 4600,
        "grit": 0.85,
        "lane_bias": 0.1,
        "steer_speed": 6.2,
    }
]

# Obstacle Definitions
OBSTACLE_MUD = "mud"
OBSTACLE_HURDLE = "hurdle"
OBSTACLE_HAYBALE = "haybale"
