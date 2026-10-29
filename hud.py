"""
Broadcast Graphics, Live Leaderboard, Minimap Progress, and Victory Podium
Designed specifically for vertical 1080x1920 mobile display (Shorts/Reels/TikTok).
"""

import os
import math
import pygame
from config import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TRACK_LEFT, TRACK_RIGHT,
    START_Y, FINISH_Y, TOTAL_RACE_DISTANCE,
    COLOR_HUD_BG, COLOR_GOLD, COLOR_SILVER, COLOR_BRONZE, COLOR_WHITE
)

def safe_sysfont(names, size, bold=False):
    """
    Safely resolves font from priority list (e.g. ['impact', 'dejavusans', 'liberationsans', 'arial', 'freesansbold'])
    with graceful fallback to standard Linux fonts without throwing warnings.
    """
    if isinstance(names, str):
        names = [names]
    standard_fallbacks = ["dejavusans", "liberationsans", "arial", "freesansbold", "sans-serif"]
    font_candidates = []
    for n in names:
        nl = n.lower()
        if nl not in font_candidates:
            font_candidates.append(nl)
    for fb in standard_fallbacks:
        if fb not in font_candidates:
            font_candidates.append(fb)

    try:
        return pygame.font.SysFont(font_candidates, size, bold=bold)
    except Exception:
        try:
            return pygame.font.Font(None, size)
        except Exception:
            return pygame.font.SysFont(None, size)

def draw_star(surface, color, center, radius):
    """Draws a crisp 5-pointed geometric star on any surface without font dependencies."""
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.44
        angle = i * math.pi / 5 - math.pi / 2
        points.append((center[0] + r * math.cos(angle), center[1] + r * math.sin(angle)))
    pygame.draw.polygon(surface, color, points)

# Dynamic Category Header Mappings
CATEGORY_HEADERS = {
    "football": ("HORSE HAVOC: FOOTBALL DERBY", "⚽"),
    "streamers": ("HORSE HAVOC: STREAMER ROYALE", "🎮"),
    "tech_business": ("HORSE HAVOC: TECH TITANS", "💻"),
    "world_leaders": ("HORSE HAVOC: WORLD LEADERS", "🌍"),
    "pop_culture": ("HORSE HAVOC: POP ICONS", "🌟")
}

CATEGORY_SUBTITLES = {
    "football": "FOOTBALL DERBY SHOWDOWN",
    "streamers": "STREAMER ROYALE FINISH",
    "tech_business": "TECH TITANS SHOWDOWN",
    "world_leaders": "WORLD LEADERS SUMMIT FINISH",
    "pop_culture": "POP ICONS ALL-STAR FINISH"
}

class HUD:
    def __init__(self):
        # High quality font hierarchy with safe cross-platform fallbacks
        self.font_title = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 38, bold=True)
        self.font_timer = safe_sysfont(["couriernew", "dejavusansmono", "liberationmono", "monospace"], 32, bold=True)
        self.font_board_rank = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 28, bold=True)
        self.font_board_name = safe_sysfont(["arial", "dejavusans", "liberationsans", "freesansbold"], 24, bold=True)
        self.font_board_stats = safe_sysfont(["arial", "dejavusans", "liberationsans"], 20)
        self.font_ticker = safe_sysfont(["arial", "dejavusans", "liberationsans", "freesansbold"], 28, bold=True)
        self.font_podium_title = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 60, bold=True)
        self.font_podium_name = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 44, bold=True)
        self.font_podium_time = safe_sysfont(["arial", "dejavusans", "liberationsans", "freesansbold"], 30, bold=True)

        # Cross-platform emoji font resolution (Windows Segoe UI Emoji or Linux Noto/Symbola)
        self.emoji_font = None
        emoji_path = pygame.font.match_font("segoeuiemoji")
        if not emoji_path:
            for p in [
                "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
                "/usr/share/fonts/opentype/noto/NotoColorEmoji.otf",
                "/usr/share/fonts/truetype/ancient-scripts/Symbola.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            ]:
                if os.path.exists(p):
                    emoji_path = p
                    break
        if emoji_path:
            try:
                self.emoji_font = pygame.font.Font(emoji_path, 34)
            except Exception:
                self.emoji_font = None

        # Track Theme State
        self.track_theme = "classic_turf"
        self.track_name = "Classic Turf Derby"

        # Match Group Category State
        self._group_key = "football"
        self.group_name = "Football Derby"
        self.header_title_str = "HORSE HAVOC: FOOTBALL DERBY ⚽"

    @property
    def group_key(self):
        return self._group_key

    @group_key.setter
    def group_key(self, val):
        self._group_key = val
        h_tuple = CATEGORY_HEADERS.get(val, (f"HORSE HAVOC: {getattr(self, 'group_name', 'DERBY').upper()}", "🌟"))
        self.header_title_str = f"{h_tuple[0]} {h_tuple[1]}".strip()

        # Event Commentary Ticker
        self.current_ticker = "HORSE HAVOC: GATES OPEN!"
        self.ticker_timer = 180  # frames
        self.ticker_alpha = 255

    def push_commentary(self, message):
        """Sets a dramatic event headline in the commentary banner."""
        self.current_ticker = message
        self.ticker_timer = 150
        self.ticker_alpha = 255

    def update(self):
        if self.ticker_timer > 0:
            self.ticker_timer -= 1
            if self.ticker_timer < 30:
                self.ticker_alpha = int((self.ticker_timer / 30.0) * 255)

    def draw(self, surface, race_time_sec, horses, finish_order, race_state):
        """Renders header, leaderboard, progress bar, announcements, and podium."""
        self.draw_top_bar(surface, race_time_sec, horses)
        self.draw_leaderboard(surface, horses, race_state)
        self.draw_commentary_ticker(surface)

        if race_state in ("FINISHED", "PODIUM"):
            self.draw_podium(surface, finish_order, race_time_sec)

    def draw_top_bar(self, surface, race_time_sec, horses):
        """Top broadcast scoreboard showing title, race clock, and horizontal progress track."""
        top_bar_height = 200
        bar_surf = pygame.Surface((SCREEN_WIDTH, top_bar_height), pygame.SRCALPHA)
        bar_surf.fill(COLOR_HUD_BG)
        surface.blit(bar_surf, (0, 0))

        # Bottom accent trim tailored per track theme
        if self.track_theme == "cyber_neon":
            pygame.draw.line(surface, (0, 240, 255), (0, top_bar_height - 2), (SCREEN_WIDTH, top_bar_height - 2), 3)
            pygame.draw.line(surface, (255, 20, 147), (0, top_bar_height + 1), (SCREEN_WIDTH, top_bar_height + 1), 2)
        elif self.track_theme == "desert_dunes":
            pygame.draw.line(surface, (245, 158, 11), (0, top_bar_height), (SCREEN_WIDTH, top_bar_height), 4)
        else:
            pygame.draw.line(surface, COLOR_GOLD, (0, top_bar_height), (SCREEN_WIDTH, top_bar_height), 4)

        # Title with Match Category & Themed Emoji
        cat_key = getattr(self, "group_key", "football")
        header_text, emoji_char = CATEGORY_HEADERS.get(
            cat_key,
            (f"HORSE HAVOC: {getattr(self, 'group_name', 'DERBY').upper()}", "🌟")
        )
        self.header_title_str = f"{header_text} {emoji_char}".strip()
        title_col = COLOR_GOLD if self.track_theme != "cyber_neon" else (0, 240, 255)
        title_txt = self.font_title.render(header_text, True, title_col)
        surface.blit(title_txt, (50, 22))

        # Render Trailing Themed Emoji
        if self.emoji_font and emoji_char:
            try:
                emoji_txt = self.emoji_font.render(emoji_char, True, (255, 255, 255))
                surface.blit(emoji_txt, (50 + title_txt.get_width() + 8, 20))
            except Exception:
                pass

        # Track Map Subtitle
        map_col = (0, 240, 255) if self.track_theme == "cyber_neon" else ((254, 240, 138) if self.track_theme == "desert_dunes" else (167, 243, 208))
        map_txt = self.font_board_stats.render(f"TRACK: {self.track_name.upper()}", True, map_col)
        surface.blit(map_txt, (52, 68))

        # Race Timer (formatted MM:SS.ms)
        mins = int(race_time_sec // 60)
        secs = int(race_time_sec % 60)
        ms = int((race_time_sec * 100) % 100)
        time_str = f"TIME: {mins:02d}:{secs:02d}.{ms:02d}"
        time_txt = self.font_timer.render(time_str, True, COLOR_WHITE)
        surface.blit(time_txt, (SCREEN_WIDTH - time_txt.get_width() - 50, 28))

        # Distance to leader
        leader = min(horses, key=lambda h: h.y)
        dist_rem = max(0, int(leader.y - FINISH_Y))
        dist_meters = int((dist_rem / TOTAL_RACE_DISTANCE) * 1000)
        dist_str = f"TO FINISH: {dist_meters}m"
        dist_txt = self.font_board_name.render(dist_str, True, (200, 225, 255))
        surface.blit(dist_txt, (SCREEN_WIDTH - dist_txt.get_width() - 50, 75))

        # --- Mini-Map Progress Track Bar ---
        bar_x = 50
        bar_y = 135
        bar_w = SCREEN_WIDTH - 100
        bar_h = 24

        # Track background bar
        pygame.draw.rect(surface, (30, 41, 59), (bar_x, bar_y, bar_w, bar_h), border_radius=12)
        pygame.draw.rect(surface, (100, 116, 139), (bar_x, bar_y, bar_w, bar_h), width=2, border_radius=12)

        # Start line pin & Finish line checkered pin
        pygame.draw.line(surface, (200, 200, 200), (bar_x + 8, bar_y + 2), (bar_x + 8, bar_y + bar_h - 2), 3)
        pygame.draw.line(surface, (255, 215, 0), (bar_x + bar_w - 8, bar_y + 2), (bar_x + bar_w - 8, bar_y + bar_h - 2), 4)

        # Plot 5 horse pins along the progress bar (Mini circular celebrity avatars)
        for h in horses:
            progress = (START_Y - h.y) / TOTAL_RACE_DISTANCE
            progress = max(0.0, min(1.0, progress))
            pin_x = int(bar_x + 12 + progress * (bar_w - 24))
            pin_y = bar_y + bar_h // 2

            if getattr(h, "avatar_pin_surf", None):
                pin_rect = h.avatar_pin_surf.get_rect(center=(pin_x, pin_y))
                surface.blit(h.avatar_pin_surf, pin_rect)
            else:
                # Fallback Pin dot
                pygame.draw.circle(surface, (20, 20, 20), (pin_x, pin_y), 11)
                pygame.draw.circle(surface, h.silk_color, (pin_x, pin_y), 9)
                p_font = safe_sysfont(["arial", "dejavusans", "liberationsans"], 12, bold=True)
                p_txt = p_font.render(str(h.number), True, (255, 255, 255))
                surface.blit(p_txt, p_txt.get_rect(center=(pin_x, pin_y)))

    def draw_leaderboard(self, surface, horses, race_state):
        """Displays real-time rankings (1st to 5th) with celebrity avatars, silks, speeds, and stamina."""
        # Sort horses by track progress (lowest Y is closest to finish)
        sorted_horses = sorted(horses, key=lambda h: (h.finish_rank or 99, h.y))

        panel_w = 480
        panel_h = 325
        panel_x = 40
        panel_y = SCREEN_HEIGHT - panel_h - 40

        bg_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg_surf.fill((15, 23, 42, 225))
        surface.blit(bg_surf, (panel_x, panel_y))

        # Dynamic themed border & header
        if self.track_theme == "cyber_neon":
            border_col = (0, 240, 255)
            hdr_title = "CYBER STANDINGS"
            hdr_col = (0, 240, 255)
        elif self.track_theme == "desert_dunes":
            border_col = (217, 119, 6)
            hdr_title = "CANYON STANDINGS"
            hdr_col = (254, 240, 138)
        else:
            border_col = (71, 85, 105)
            hdr_title = "LIVE STANDINGS"
            hdr_col = COLOR_GOLD

        pygame.draw.rect(surface, border_col, (panel_x, panel_y, panel_w, panel_h), width=2, border_radius=10)

        # Leaderboard Header
        hdr_rect = pygame.Rect(panel_x, panel_y, panel_w, 42)
        pygame.draw.rect(surface, (30, 41, 59), hdr_rect, border_top_left_radius=10, border_top_right_radius=10)
        hdr_txt = self.font_board_name.render(hdr_title, True, hdr_col)
        surface.blit(hdr_txt, (panel_x + 20, panel_y + 8))

        # Cyber neon corner accent brackets
        if self.track_theme == "cyber_neon":
            c_len = 16
            m_col = (255, 20, 147)
            pygame.draw.line(surface, m_col, (panel_x, panel_y), (panel_x + c_len, panel_y), 3)
            pygame.draw.line(surface, m_col, (panel_x, panel_y), (panel_x, panel_y + c_len), 3)
            pygame.draw.line(surface, m_col, (panel_x + panel_w - c_len, panel_y), (panel_x + panel_w, panel_y), 3)
            pygame.draw.line(surface, m_col, (panel_x + panel_w, panel_y), (panel_x + panel_w, panel_y + c_len), 3)

        row_h = 52
        for idx, h in enumerate(sorted_horses):
            ry = panel_y + 48 + idx * row_h

            # Rank indicator badge
            rank_str = f"{idx + 1}"
            rank_bg_color = (71, 85, 105)
            if idx == 0:
                rank_bg_color = COLOR_GOLD
            elif idx == 1:
                rank_bg_color = COLOR_SILVER
            elif idx == 2:
                rank_bg_color = COLOR_BRONZE

            badge_rect = pygame.Rect(panel_x + 10, ry + 6, 28, 34)
            pygame.draw.rect(surface, rank_bg_color, badge_rect, border_radius=6)
            r_txt = self.font_board_rank.render(rank_str, True, (15, 23, 42) if idx == 0 else (255, 255, 255))
            surface.blit(r_txt, r_txt.get_rect(center=badge_rect.center))

            # Celebrity Circular Avatar Photo (+25% enlarged to 46x46 with white outline)
            if getattr(h, "avatar_hud_surf", None):
                surface.blit(h.avatar_hud_surf, (panel_x + 44, ry + 3))
            else:
                # Procedural caricature badge fallback (46x46 circular with initials and 3px white outline)
                cx, cy = panel_x + 67, ry + 26
                pygame.draw.circle(surface, h.silk_color, (cx, cy), 22)
                pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 22, width=3)
                init_str = getattr(h, "initials", h.name[:2].upper())
                in_txt = self.font_board_stats.render(init_str[:3], True, (255, 255, 255))
                surface.blit(in_txt, in_txt.get_rect(center=(cx, cy)))

            # Celebrity Famous Name (Short name for clean UI fit)
            display_name = getattr(h, "short_name", h.name)
            name_txt = self.font_board_name.render(display_name[:14], True, COLOR_WHITE)
            surface.blit(name_txt, (panel_x + 98, ry + 2))

            # Horse Number & Current Speed
            speed_kmh = h.speed * 3.6
            spd_txt = self.font_board_stats.render(f"#{h.number} • {speed_kmh:.0f} km/h", True, (148, 163, 184))
            surface.blit(spd_txt, (panel_x + 98, ry + 26))

            # Stamina miniature bar
            stamina_pct = max(0.0, min(1.0, h.stamina / h.max_stamina))
            s_bar_w = 70
            s_bar_x = panel_x + panel_w - s_bar_w - 14
            pygame.draw.rect(surface, (51, 65, 85), (s_bar_x, ry + 28, s_bar_w, 7), border_radius=4)
            stamina_col = (34, 197, 94) if stamina_pct > 0.3 else (239, 68, 68)
            pygame.draw.rect(surface, stamina_col, (s_bar_x, ry + 28, int(s_bar_w * stamina_pct), 7), border_radius=4)

            # Weapon or Stun Status Badge
            if h.stun_timer > 0:
                st_txt = self.font_board_stats.render("* STUNNED! *", True, (250, 204, 21))
                surface.blit(st_txt, (panel_x + panel_w - 118, ry + 4))
            elif h.held_weapon:
                w_label = "LASER" if h.held_weapon == "laser" else ("ROCKET" if h.held_weapon == "rocket" else "BOMB")
                w_color = (56, 189, 248) if h.held_weapon == "laser" else ((239, 68, 68) if h.held_weapon == "rocket" else (245, 158, 11))
                w_txt = self.font_board_stats.render(f"[{w_label}]", True, w_color)
                surface.blit(w_txt, (panel_x + panel_w - 110, ry + 4))
            elif h.is_sprinting:
                sp_txt = self.font_board_stats.render(">> SPRINT", True, (255, 120, 30))
                surface.blit(sp_txt, (panel_x + panel_w - 110, ry + 4))

    def draw_commentary_ticker(self, surface):
        """Draws event banner notifications (e.g. overtakes, collisions, hurdles)."""
        if self.ticker_timer <= 0 or self.ticker_alpha <= 0:
            return

        ticker_w = 760
        ticker_h = 58
        ticker_x = (SCREEN_WIDTH - ticker_w) // 2
        ticker_y = 220

        bg_surf = pygame.Surface((ticker_w, ticker_h), pygame.SRCALPHA)
        bg_surf.fill((15, 23, 42, min(230, self.ticker_alpha)))
        surface.blit(bg_surf, (ticker_x, ticker_y))

        ticker_col = (0, 240, 255) if self.track_theme == "cyber_neon" else ((245, 158, 11) if self.track_theme == "desert_dunes" else COLOR_GOLD)
        border_surf = pygame.Surface((ticker_w, ticker_h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (*ticker_col[:3], self.ticker_alpha), (0, 0, ticker_w, ticker_h), width=2, border_radius=12)
        surface.blit(border_surf, (ticker_x, ticker_y))

        txt = self.font_ticker.render(self.current_ticker, True, (*ticker_col[:3], self.ticker_alpha))
        txt.set_alpha(self.ticker_alpha)
        surface.blit(txt, txt.get_rect(center=(SCREEN_WIDTH // 2, ticker_y + ticker_h // 2)))

    def draw_podium(self, surface, finish_order, final_time):
        """Displays triumphant post-race podium ceremony for the winner & top finishers."""
        # Darkened overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 15, 30, 215))
        surface.blit(overlay, (0, 0))

        # Title Card
        title_txt = self.font_podium_title.render("OFFICIAL RESULTS", True, COLOR_GOLD)
        title_rect = title_txt.get_rect(center=(SCREEN_WIDTH // 2, 280))
        surface.blit(title_txt, title_rect)

        # Procedural Gold Stars flanking title
        draw_star(surface, COLOR_GOLD, (title_rect.left - 45, title_rect.centery), 22)
        draw_star(surface, COLOR_GOLD, (title_rect.right + 45, title_rect.centery), 22)

        # Subtitle with Category Finish
        sub_title = CATEGORY_SUBTITLES.get(getattr(self, "group_key", "football"), f"{self.group_name.upper()} DERBY FINISH")
        sub_txt = self.font_podium_time.render(sub_title, True, (220, 220, 220))
        surface.blit(sub_txt, sub_txt.get_rect(center=(SCREEN_WIDTH // 2, 350)))

        # Winner Showcase Card
        if finish_order:
            winner = finish_order[0]
            card_w = 900
            card_h = 330
            card_x = (SCREEN_WIDTH - card_w) // 2
            card_y = 420

            card_surf = pygame.Surface((card_w, card_h), pygame.SRCALPHA)
            card_surf.fill((30, 41, 59, 245))
            surface.blit(card_surf, (card_x, card_y))
            pygame.draw.rect(surface, COLOR_GOLD, (card_x, card_y, card_w, card_h), width=4, border_radius=16)

            # Winner Celebrity Avatar or Fallback Caricature Badge
            if getattr(winner, "avatar_podium_surf", None):
                surface.blit(winner.avatar_podium_surf, (card_x + 35, card_y + 40))
                # 1st Gold Star Badge below avatar
                badge_w = 110
                pygame.draw.rect(surface, COLOR_GOLD, (card_x + 35, card_y + 160, badge_w, 34), border_radius=6)
                tr_font = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 22, bold=True)
                tr_txt = tr_font.render("1st PLACE", True, (20, 20, 20))
                surface.blit(tr_txt, tr_txt.get_rect(center=(card_x + 35 + badge_w // 2, card_y + 177)))
            else:
                # Procedural circular caricature badge (110x110)
                cx, cy = card_x + 90, card_y + 95
                pygame.draw.circle(surface, winner.silk_color, (cx, cy), 52)
                pygame.draw.circle(surface, COLOR_GOLD, (cx, cy), 52, width=4)
                w_init = getattr(winner, "initials", winner.name[:2].upper())
                tr_font = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 36, bold=True)
                tr_txt = tr_font.render(w_init[:4], True, (255, 255, 255))
                surface.blit(tr_txt, tr_txt.get_rect(center=(cx, cy)))
                badge_w = 110
                pygame.draw.rect(surface, COLOR_GOLD, (card_x + 35, card_y + 160, badge_w, 34), border_radius=6)
                pl_font = safe_sysfont(["impact", "dejavusans", "liberationsans", "arial", "freesansbold"], 22, bold=True)
                pl_txt = pl_font.render("1st PLACE", True, (20, 20, 20))
                surface.blit(pl_txt, pl_txt.get_rect(center=(card_x + 35 + badge_w // 2, card_y + 177)))

            # Winner Name & Details
            w_name = self.font_podium_name.render(winner.name.upper(), True, COLOR_GOLD)
            surface.blit(w_name, (card_x + 175, card_y + 35))

            # Celebrity Meme Quote Tagline
            celeb_quote = getattr(winner, "quote", "")
            if celeb_quote:
                quote_txt = self.font_board_name.render(f'"{celeb_quote}"', True, (254, 240, 138))
                surface.blit(quote_txt, (card_x + 175, card_y + 90))

            arch_txt = self.font_board_stats.render(f"Archetype: {winner.archetype}", True, (200, 200, 220))
            surface.blit(arch_txt, (card_x + 175, card_y + 130))

            w_time_str = f"Winning Time: {winner.finish_time:.2f}s"
            w_time_txt = self.font_podium_time.render(w_time_str, True, (255, 255, 255))
            surface.blit(w_time_txt, (card_x + 175, card_y + 168))

            # Winner Jockey Silk Color Bar
            silk_bar = pygame.Rect(card_x + 175, card_y + 230, 500, 42)
            pygame.draw.rect(surface, winner.silk_color, silk_bar, border_radius=8)
            pygame.draw.rect(surface, (255, 255, 255), silk_bar, width=2, border_radius=8)
            num_t = self.font_board_name.render(f"HORSE #{winner.number} • {winner.name.upper()}", True, (255, 255, 255))
            surface.blit(num_t, num_t.get_rect(center=silk_bar.center))

        # Runners Up (2nd through 5th Place Table with Avatars)
        start_y = 800
        table_w = 900
        table_x = (SCREEN_WIDTH - table_w) // 2

        for i, h in enumerate(finish_order[1:], start=2):
            row_y = start_y + (i - 2) * 115
            row_rect = pygame.Rect(table_x, row_y, table_w, 95)
            pygame.draw.rect(surface, (20, 29, 47, 230), row_rect, border_radius=12)
            pygame.draw.rect(surface, (71, 85, 105), row_rect, width=2, border_radius=12)

            # Position badge
            badge_color = COLOR_SILVER if i == 2 else (COLOR_BRONZE if i == 3 else (100, 116, 139))
            b_rect = pygame.Rect(table_x + 20, row_y + 20, 55, 55)
            pygame.draw.rect(surface, badge_color, b_rect, border_radius=8)
            b_txt = self.font_board_rank.render(f"{i}", True, (15, 23, 42) if i <= 3 else (255, 255, 255))
            surface.blit(b_txt, b_txt.get_rect(center=b_rect.center))

            # Celebrity Avatar Photo
            if getattr(h, "avatar_runner_surf", None):
                surface.blit(h.avatar_runner_surf, (table_x + 88, row_y + 21))
            else:
                # Procedural circular caricature badge (52x52)
                cx, cy = table_x + 114, row_y + 47
                pygame.draw.circle(surface, h.silk_color, (cx, cy), 24)
                pygame.draw.circle(surface, (255, 255, 255), (cx, cy), 24, width=3)
                r_init = getattr(h, "initials", h.name[:2].upper())
                r_txt = self.font_board_stats.render(r_init[:3], True, (255, 255, 255))
                surface.blit(r_txt, r_txt.get_rect(center=(cx, cy)))

            # Celebrity Name & Details
            h_name = self.font_board_name.render(h.name, True, (255, 255, 255))
            surface.blit(h_name, (table_x + 155, row_y + 18))

            quote_sub = f" • \"{h.quote}\"" if getattr(h, "quote", "") else ""
            h_arch = self.font_board_stats.render(f"#{h.number} • {h.archetype}{quote_sub}", True, (148, 163, 184))
            surface.blit(h_arch, (table_x + 155, row_y + 54))

            # Time / Gap
            if h.finish_time and finish_order[0].finish_time:
                gap = h.finish_time - finish_order[0].finish_time
                time_str = f"+{gap:.2f}s  ({h.finish_time:.2f}s)"
            else:
                time_str = "DNF"

            gap_txt = self.font_podium_time.render(time_str, True, COLOR_GOLD if i <= 3 else (200, 200, 200))
            surface.blit(gap_txt, (table_x + table_w - gap_txt.get_width() - 35, row_y + 30))
