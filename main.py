"""
Interactive Desktop Preview Runner for 2D Horse Racing Game
Renders native 1080x1920 vertical canvas scaled down gracefully to fit desktop monitors.
Controls:
- SPACE : Pause / Resume
- R     : Restart Race with fresh track & AI conditions
- D     : Toggle AI Debug View (sensor feelers, hitboxes, stats)
- F     : Fast-Forward Speed Toggle (1x, 2x, 4x)
- C     : Quick-Record match to MP4
- ESC/Q : Quit
"""

import sys
import os
import pygame
from config import SCREEN_WIDTH, SCREEN_HEIGHT, FPS
from game import RaceGame

# Set console encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def main():
    try:
        pygame.mixer.pre_init(44100, -16, 2, 2048)
    except Exception:
        pass
    pygame.init()
    pygame.display.set_caption("Horse Havoc - 2D Racing Championship (1080x1920)")

    # Window scale factor for desktop display (540x960 fits comfortably on 1080p and 1440p displays)
    scale = 0.5
    win_w = int(SCREEN_WIDTH * scale)
    win_h = int(SCREEN_HEIGHT * scale)

    screen = pygame.display.set_mode((win_w, win_h))
    native_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    game = RaceGame(seed=None, headless=False, enable_audio=True)

    running = True
    paused = False
    speed_mult = 1

    print("\n" + "=" * 60)
    print(" [HORSE HAVOC] INTERACTIVE PREVIEW")
    print("=" * 60)
    print(" [SPACE] : Pause / Resume")
    print(" [R]     : Restart Race (New Seed)")
    print(" [D]     : Toggle AI Sensory & Collision Debug Overlays")
    print(" [F]     : Toggle Speed (1x -> 2x -> 4x)")
    print(" [C]     : Record Next Match Headlessly to MP4")
    print(" [ESC/Q] : Quit")
    print("=" * 60 + "\n")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_d:
                    game.debug_mode = not game.debug_mode
                elif event.key == pygame.K_f:
                    speed_mult = 2 if speed_mult == 1 else (4 if speed_mult == 2 else 1)
                    print(f"-> Playback Speed: {speed_mult}x")
                elif event.key == pygame.K_c:
                    pygame.quit()
                    print("\n[🎬] Launching headless recorder...")
                    import record_race
                    record_race.record_race("recorded_match.mp4")
                    return

        if not paused:
            for _ in range(speed_mult):
                game.update()

        # Render native high-res canvas
        game.render(native_surface)

        # Scale down to fit desktop window
        scaled_frame = pygame.transform.smoothscale(native_surface, (win_w, win_h))
        screen.blit(scaled_frame, (0, 0))

        # Show pause / speed banner if applicable
        if paused or speed_mult > 1:
            font = pygame.font.SysFont("Arial", 22, bold=True)
            status_str = "⏸ PAUSED" if paused else f"⏩ {speed_mult}X SPEED"
            badge = font.render(status_str, True, (255, 215, 0))
            screen.blit(badge, (15, 15))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
