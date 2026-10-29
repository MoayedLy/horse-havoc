"""
Celebrity Meme Roster & Dynamic Themed Avatar System for HORSE HAVOC
===================================================================
Manages a pool of 100 famous internet & pop culture personalities split across
5 distinct themed categories (20 celebrities per group):
  1. "football"       : Football Legends & Stars (Ronaldo, Messi, Mbappe, Neymar, etc.)
  2. "streamers"      : Content Creators & Internet Stars (MrBeast, Speed, Kai, Pewds, etc.)
  3. "tech_business"  : Tech Titans & Billionaires (Elon Musk, Zuck, Gates, Jobs, etc.)
  4. "world_leaders"  : Global Leaders & Historical Figures (Trump, Biden, Putin, Obama, etc.)
  5. "pop_culture"    : Pop Culture & Meme Icons (The Rock, Drake, Goku, Walter White, etc.)

Features:
- Dynamically loads `assets/celebrities/roster.json` as the central source of truth.
- Themed match selection: select 5 distinct racers belonging to the SAME hilarious group.
- Procedural Caricature Generator: automatically renders stylized circular avatars with
  distinctive features, two-tone gradient, bold initials, and outline if PNG is missing.
- Multi-resolution caching for Jockey Head, HUD Leaderboard, Mini-Map Pin, and Podium.
- Zero network dependency & ultra-lightweight disk footprint (<2MB total).
"""

import os
import io
import json
import math
import random
import pygame

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "celebrities")
ROSTER_PATH = os.path.join(ASSETS_DIR, "roster.json")

# Group metadata definitions
GROUP_DISPLAY_NAMES = {
    "football": "Football Derby",
    "streamers": "Content Creators",
    "tech_business": "Tech Titans",
    "world_leaders": "World Leaders",
    "pop_culture": "Pop Culture Icons",
    "random": "All-Star Mashup"
}

GROUP_THEME_COLORS = {
    "football": (220, 38, 38),       # Striker Crimson Red
    "streamers": (168, 85, 247),     # Creator Neon Purple
    "tech_business": (14, 165, 233), # Tech Cyber Cyan
    "world_leaders": (234, 179, 8),  # Presidential Gold / Amber
    "pop_culture": (236, 72, 153),   # Viral Pop Magenta
    "random": (16, 185, 129)         # All-Star Emerald Green
}

VALID_GROUPS = ["football", "streamers", "tech_business", "world_leaders", "pop_culture"]


def load_roster_data():
    """Loads the 100-celebrity roster from `roster.json` with safety fallback."""
    if os.path.exists(ROSTER_PATH):
        try:
            with open(ROSTER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) >= 5:
                    return data
        except Exception as e:
            print(f"[!] Warning: Error reading {ROSTER_PATH}: {e}")

    # Fallback to minimal built-in roster if file is unexpectedly missing
    return [
        {
            "id": "ronaldo",
            "name": "Cristiano Ronaldo",
            "short_name": "C. Ronaldo",
            "initials": "CR7",
            "group": "football",
            "group_name": "Football Derby",
            "quote": "SIUUU! 🐐",
            "archetype": "Front Runner",
            "color": [220, 38, 38],
            "silk_color": [220, 38, 38],
            "silk_accent": [250, 204, 21],
            "coat_color": [160, 82, 45],
            "photo": "assets/celebrities/ronaldo.png"
        },
        {
            "id": "messi",
            "name": "Lionel Messi",
            "short_name": "Leo Messi",
            "initials": "LM10",
            "group": "football",
            "group_name": "Football Derby",
            "quote": "Ankara Messi 🇦🇷",
            "archetype": "Tactician",
            "color": [56, 189, 248],
            "silk_color": [56, 189, 248],
            "silk_accent": [255, 255, 255],
            "coat_color": [230, 232, 235],
            "photo": "assets/celebrities/messi.png"
        },
        {
            "id": "elon_musk",
            "name": "Elon Musk",
            "short_name": "Elon Musk",
            "initials": "ELON",
            "group": "tech_business",
            "group_name": "Tech Titans",
            "quote": "To The Moon 🚀",
            "archetype": "Late Rusher",
            "color": [15, 23, 42],
            "silk_color": [15, 23, 42],
            "silk_accent": [34, 197, 94],
            "coat_color": [28, 28, 32],
            "photo": "assets/celebrities/elon_musk.png"
        },
        {
            "id": "mrbeast",
            "name": "MrBeast",
            "short_name": "MrBeast",
            "initials": "BEAST",
            "group": "streamers",
            "group_name": "Content Creators",
            "quote": "Gave Away 1M 💸",
            "archetype": "Brawler",
            "color": [6, 182, 212],
            "silk_color": [6, 182, 212],
            "silk_accent": [236, 72, 153],
            "coat_color": [218, 165, 32],
            "photo": "assets/celebrities/mrbeast.png"
        },
        {
            "id": "the_rock",
            "name": "The Rock",
            "short_name": "The Rock",
            "initials": "ROCK",
            "group": "pop_culture",
            "group_name": "Pop Culture Icons",
            "quote": "The Eyebrow 🤨",
            "archetype": "Brawler",
            "color": [71, 85, 105],
            "silk_color": [71, 85, 105],
            "silk_accent": [234, 179, 8],
            "coat_color": [139, 69, 19],
            "photo": "assets/celebrities/the_rock.png"
        }
    ]


# Global Roster Pools
CELEBRITY_ROSTER = load_roster_data()
CELEBRITY_POOL = CELEBRITY_ROSTER  # Alias for backward-compatibility

# Group mapping: {group_key: [celebrities]}
CELEBRITY_GROUPS = {}
for _c in CELEBRITY_ROSTER:
    _grp = _c.get("group", "pop_culture")
    if _grp not in CELEBRITY_GROUPS:
        CELEBRITY_GROUPS[_grp] = []
    CELEBRITY_GROUPS[_grp].append(_c)

# In-memory surface cache: {(celeb_id, size, border_color, border_width): Surface}
_AVATAR_CACHE = {}


def generate_procedural_avatar_file(celeb, output_path=None, canvas_size=128):
    """
    Renders a crisp 128x128 stylized circular meme avatar:
    - Signature jersey/silk color background with 3D gradient highlight.
    - Caricature facial feature / accessory where applicable.
    - Bold, readable 2-4 letter initials rendered in pure white with drop shadow.
    - Thick 3-4px white outline metallic border.
    - Saves PNG to output_path if provided, and returns the Surface.
    """
    # Ensure pygame font module is initialized
    if not pygame.font.get_init():
        try:
            pygame.font.init()
        except Exception:
            pass

    surf = pygame.Surface((canvas_size, canvas_size), pygame.SRCALPHA)
    cx = canvas_size // 2
    cy = canvas_size // 2
    radius = (canvas_size // 2) - 4

    silk = celeb.get("silk_color") or celeb.get("color") or GROUP_THEME_COLORS.get(celeb.get("group", "football"), (59, 130, 246))
    if isinstance(silk, list):
        silk = tuple(silk)
    accent = celeb.get("silk_accent", [255, 255, 255])
    if isinstance(accent, list):
        accent = tuple(accent)

    # 1. Base circular disk with group/silk color
    pygame.draw.circle(surf, silk, (cx, cy), radius)

    # 2. Gradient lighting: top-left highlight disk & bottom-right shading rim
    highlight_col = (
        min(255, int(silk[0] * 1.35 + 20)),
        min(255, int(silk[1] * 1.35 + 20)),
        min(255, int(silk[2] * 1.35 + 20))
    )
    pygame.draw.circle(surf, highlight_col, (cx - int(radius * 0.15), cy - int(radius * 0.15)), int(radius * 0.85))

    shadow_col = (
        max(0, int(silk[0] * 0.65)),
        max(0, int(silk[1] * 0.65)),
        max(0, int(silk[2] * 0.65))
    )
    pygame.draw.arc(surf, shadow_col, (cx - radius + 2, cy - radius + 2, (radius - 2) * 2, (radius - 2) * 2), 1.1 * math.pi, 1.9 * math.pi, 5)

    # 3. Caricature feature accessory (if defined)
    feature = celeb.get("hair_feature", "initials")
    if feature == "fade":  # CR7 fade
        pygame.draw.arc(surf, (30, 20, 15), (cx - 36, cy - 46, 72, 54), 0.2, math.pi - 0.2, 9)
        pygame.draw.polygon(surf, accent, [(cx - 26, cy - 36), (cx + 26, cy - 36), (cx, cy - 50)])
    elif feature == "beard":  # Messi beard
        pygame.draw.arc(surf, (140, 90, 40), (cx - 34, cy - 18, 68, 50), math.pi, 2 * math.pi, 8)
    elif feature == "glasses":  # Elon sunglasses
        pygame.draw.rect(surf, (15, 23, 42), (cx - 38, cy - 24, 32, 16), border_radius=5)
        pygame.draw.rect(surf, (15, 23, 42), (cx + 6, cy - 24, 32, 16), border_radius=5)
        pygame.draw.line(surf, (15, 23, 42), (cx - 6, cy - 16), (cx + 6, cy - 16), 4)
    elif feature == "vr":  # Zuck VR visor
        pygame.draw.rect(surf, (20, 20, 25), (cx - 40, cy - 24, 80, 22), border_radius=7)
        pygame.draw.rect(surf, (56, 189, 248), (cx - 36, cy - 20, 72, 14), width=2, border_radius=5)
    elif feature == "quiff":  # Trump golden hair
        pygame.draw.ellipse(surf, (253, 224, 71), (cx - 42, cy - 54, 84, 34))
    elif feature == "eyebrow":  # The Rock eyebrow
        pygame.draw.arc(surf, (20, 20, 20), (cx - 34, cy - 32, 28, 20), 0.1, math.pi * 0.9, 6)
        pygame.draw.line(surf, (20, 20, 20), (cx + 6, cy - 22), (cx + 34, cy - 22), 5)
    elif feature == "queen_crown" or feature == "crown":  # Golden royal crown
        pts = [(cx - 32, cy - 22), (cx - 20, cy - 44), (cx, cy - 32), (cx + 20, cy - 44), (cx + 32, cy - 22)]
        pygame.draw.polygon(surf, (250, 204, 21), pts)
        pygame.draw.lines(surf, (255, 255, 255), False, pts, 2)
    elif feature == "headphones":  # Pewds headphones
        pygame.draw.arc(surf, (220, 38, 38), (cx - 44, cy - 48, 88, 68), 0.2, math.pi - 0.2, 7)
        pygame.draw.rect(surf, (24, 24, 27), (cx - 48, cy - 24, 12, 26), border_radius=5)
        pygame.draw.rect(surf, (24, 24, 27), (cx + 36, cy - 24, 12, 26), border_radius=5)
    elif feature == "straw_hat":  # Luffy straw hat
        pygame.draw.ellipse(surf, (234, 179, 8), (cx - 46, cy - 46, 92, 30))
        pygame.draw.ellipse(surf, (220, 38, 38), (cx - 28, cy - 42, 56, 16))
    elif feature == "bat_cowl":  # Batman ears
        pygame.draw.polygon(surf, (15, 23, 42), [(cx - 36, cy - 20), (cx - 44, cy - 50), (cx - 20, cy - 35)])
        pygame.draw.polygon(surf, (15, 23, 42), [(cx + 36, cy - 20), (cx + 44, cy - 50), (cx + 20, cy - 35)])

    # 4. Bold Initials Badge
    initials = celeb.get("initials") or celeb.get("short_name", celeb.get("name", "HH"))[:3].upper()
    font_size = 32 if len(initials) <= 3 else (26 if len(initials) <= 4 else 22)
    font = None
    try:
        font = pygame.font.SysFont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], font_size, bold=True)
    except Exception:
        pass
    if font is None:
        font = pygame.font.Font(None, font_size + 4)

    txt_surf = font.render(initials, True, (255, 255, 255))
    shadow_surf = font.render(initials, True, (15, 23, 42))

    text_y_off = 10 if feature != "initials" else 0
    surf.blit(shadow_surf, shadow_surf.get_rect(center=(cx + 2, cy + text_y_off + 2)))
    surf.blit(txt_surf, txt_surf.get_rect(center=(cx, cy + text_y_off)))

    # 5. Crisp Outer Outline Ring (3px solid white border + subtle inner ring)
    pygame.draw.circle(surf, (255, 255, 255), (cx, cy), radius, width=3)
    pygame.draw.circle(surf, accent, (cx, cy), radius - 3, width=1)

    # Save to disk if requested and missing or 0 bytes
    if output_path:
        needs_write = (not os.path.exists(output_path)) or (os.path.getsize(output_path) < 100)
        if needs_write:
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                pygame.image.save(surf, output_path)
            except Exception as e:
                print(f"[!] Warning: Could not save avatar PNG for {celeb.get('id')}: {e}")

    return surf


def make_circular_surface(source_surf, size, border_color=(255, 215, 0), border_width=2):
    """
    Crops any rectangular/square surface into a circle with an anti-aliased border.
    """
    w, h = size
    scaled = pygame.transform.smoothscale(source_surf, (w, h))

    target = pygame.Surface((w, h), pygame.SRCALPHA)
    mask = pygame.Surface((w, h), pygame.SRCALPHA)
    radius = min(w, h) // 2
    pygame.draw.circle(mask, (255, 255, 255, 255), (w // 2, h // 2), radius)

    scaled.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    target.blit(scaled, (0, 0))

    if border_width > 0 and border_color:
        pygame.draw.circle(target, border_color, (w // 2, h // 2), radius, width=border_width)

    return target


def get_celebrity_avatar(celeb_id, size=(36, 36), border_color=None, border_width=2):
    """
    Loads, crops, and caches a circular avatar for a celebrity.
    Prioritizes local image files in `assets/celebrities/{celeb_id}.png`,
    and safely falls back to procedural drawing if file is missing.
    """
    cache_key = (celeb_id, size, border_color, border_width)
    if cache_key in _AVATAR_CACHE:
        return _AVATAR_CACHE[cache_key]

    # Find celebrity profile from global roster
    celeb = next((c for c in CELEBRITY_ROSTER if c["id"] == celeb_id), None)
    if not celeb:
        celeb = {
            "id": celeb_id,
            "name": celeb_id.replace("_", " ").title(),
            "short_name": celeb_id.replace("_", " ").title()[:10],
            "initials": celeb_id[:3].upper(),
            "silk_color": (59, 130, 246),
            "silk_accent": (255, 255, 255)
        }

    if border_color is None:
        accent = celeb.get("silk_accent", (255, 255, 255))
        border_color = tuple(accent) if isinstance(accent, list) else accent

    # Ensure display surface exists for alpha conversions
    if pygame.display.get_surface() is None:
        try:
            pygame.display.set_mode((1, 1))
        except Exception:
            pass

    # Check for local file
    raw_surf = None
    extensions = [".png", ".jpg", ".jpeg", ".PNG", ".JPG"]
    for ext in extensions:
        file_path = os.path.join(ASSETS_DIR, f"{celeb_id}{ext}")
        if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
            try:
                loaded = pygame.image.load(file_path)
                try:
                    raw_surf = loaded.convert_alpha()
                except Exception:
                    raw_surf = loaded
                break
            except Exception:
                pass

    # If missing or corrupted, procedurally generate fallback badge
    if raw_surf is None:
        target_png = os.path.join(ASSETS_DIR, f"{celeb_id}.png")
        raw_surf = generate_procedural_avatar_file(celeb, target_png, canvas_size=128)

    # Crop to circle & add border (default: 3px white outline)
    bw = border_width if border_width is not None else 3
    bc = border_color if border_color is not None else (255, 255, 255)
    try:
        final_surf = make_circular_surface(raw_surf, size, border_color=bc, border_width=bw)
    except Exception:
        # Ultimate fallback
        final_surf = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.circle(final_surf, (59, 130, 246), (size[0] // 2, size[1] // 2), min(size) // 2)
        pygame.draw.circle(final_surf, (255, 255, 255), (size[0] // 2, size[1] // 2), min(size) // 2, width=3)

    _AVATAR_CACHE[cache_key] = final_surf
    return final_surf


def pick_themed_roster(group=None, count=5, seed=None):
    """
    Selects `count` distinct celebrities tailored to a chosen or random group.
    
    Args:
        group (str or None): "auto", "random", or specific group name
                            ("football", "streamers", "tech_business", "world_leaders", "pop_culture").
                            If None or "auto", picks ONE category randomly.
                            If "random", picks 5 across the full 100-celebrity pool.
        count (int): Number of celebrities to select (default: 5).
        seed (int or None): Random seed for reproducibility.

    Returns:
        tuple: (selected_celebs_list, active_group_key, active_group_name)
    """
    ensure_assets_directory()
    rng = random.Random(seed) if seed is not None else random.Random()

    # 1. Normalize group request (strictly enforce single-category match unity)
    chosen_group = group.lower() if isinstance(group, str) else "auto"

    if chosen_group in ("auto", "none", "random") or not chosen_group or chosen_group not in VALID_GROUPS:
        # Strictly pick ONE category from the 5 themes so all 5 horses share the exact same group
        chosen_group = rng.choice(VALID_GROUPS)

    # Filter pool strictly to contestants belonging to that chosen category
    candidates = CELEBRITY_GROUPS.get(chosen_group, [])
    if len(candidates) < count:
        # Fallback to football
        chosen_group = "football"
        candidates = CELEBRITY_GROUPS.get("football", [])

    group_title = GROUP_DISPLAY_NAMES.get(chosen_group, chosen_group.replace("_", " ").title())

    # Sample distinct celebrities strictly from this single category
    num_to_sample = min(count, len(candidates))
    selected = rng.sample(candidates, num_to_sample)

    return selected, chosen_group, group_title


def pick_celebrity_roster(seed=None, count=5, group=None):
    """
    Backward-compatible entry point returning a list of `count` celebrities.
    """
    roster, _, _ = pick_themed_roster(group=group, count=count, seed=seed)
    return roster


def ensure_assets_directory():
    """
    Ensures `assets/celebrities/` exists and all 100 roster personalities
    have an avatar image on disk (generating procedural badges for missing ones).
    """
    os.makedirs(ASSETS_DIR, exist_ok=True)
    for c in CELEBRITY_ROSTER:
        cid = c.get("id")
        png_path = os.path.join(ASSETS_DIR, f"{cid}.png")
        if not os.path.exists(png_path):
            generate_procedural_avatar_file(c, png_path, canvas_size=128)
