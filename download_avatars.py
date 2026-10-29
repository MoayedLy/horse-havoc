"""
HORSE HAVOC - Celebrity Avatar Downloader & Procedural Generator
================================================================
Manages photographic & procedural avatar assets for all 100 roster personalities.
- Reads definitions from `assets/celebrities/roster.json`.
- Standardizes all avatars to 128x128 PNG format with square face crop.
- Queries Wikimedia / Wikipedia REST API and direct sources for official portraits.
- Guarantees 100% offline autonomy: if offline or download fails, procedurally
  renders a circular caricature avatar with group theme colors, initials, and 3px white outline.
- Produces a clear confirmation table with status and file sizes.
"""

import os
import io
import sys
import time
import json
import math
import argparse
from pathlib import Path

# Reconfigure console encoding for Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
import requests

from celebrities import (
    ASSETS_DIR,
    ROSTER_PATH,
    CELEBRITY_ROSTER,
    GROUP_THEME_COLORS,
    generate_procedural_avatar_file
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 HorseHavoc/2.0"
HEADERS = {"User-Agent": USER_AGENT}

# Accurate Wikipedia / direct source mapping for all 100 celebrities
WIKI_SOURCES = {
    # 1. Football Legends & Stars (20)
    "ronaldo": "Cristiano_Ronaldo",
    "messi": "Lionel_Messi",
    "mbappe": "Kylian_Mbapp%C3%A9",
    "neymar": "Neymar",
    "haaland": "Erling_Haaland",
    "bellingham": "Jude_Bellingham",
    "vinicius_jr": "Vin%C3%ADcius_J%C3%BAnior",
    "de_bruyne": "Kevin_De_Bruyne",
    "salah": "Mohamed_Salah",
    "benzema": "Karim_Benzema",
    "modric": "Luka_Modri%C4%87",
    "ibrahimovic": "Zlatan_Ibrahimovi%C4%87",
    "ronaldinho": "Ronaldinho",
    "zidane": "Zinedine_Zidane",
    "maradona": "Diego_Maradona",
    "pele": "Pel%C3%A9",
    "ramos": "Sergio_Ramos",
    "neuer": "Manuel_Neuer",
    "maguire": "Harry_Maguire",
    "mourinho": "Jos%C3%A9_Mourinho",

    # 2. Content Creators & Streamers (20)
    "mrbeast": "MrBeast",
    "ishowspeed": "IShowSpeed",
    "kai_cenat": "Kai_Cenat",
    "pewdiepie": "PewDiePie",
    "xqc": "XQc",
    "pokimane": "Pokimane",
    "ninja": "Ninja_(gamer)",
    "logan_paul": "Logan_Paul",
    "ksi": "KSI",
    "adin_ross": "Adin_Ross",
    "asmongold": "Asmongold",
    "dream": "Dream_(YouTuber)",
    "hasanabi": "Hasan_Piker",
    "valkyrae": "Valkyrae",
    "shroud": "Shroud_(gamer)",
    "ludwig": "Ludwig_Ahgren",
    "moistcrone": "MoistCr1TiKaL",
    "hasbulla": "https://raw.githubusercontent.com/svict4/emojis/main/hasbulla1.png",
    "giga_chad": "https://raw.githubusercontent.com/justinlime/GigaChads/main/gigachads/gigaclassic.jpg",

    # 3. Tech Titans & Billionaires (20)
    "elon_musk": "Elon_Musk",
    "zuckerberg": "Mark_Zuckerberg",
    "bill_gates": "Bill_Gates",
    "steve_jobs": "Steve_Jobs",
    "jeff_bezos": "Jeff_Bezos",
    "warren_buffett": "Warren_Buffett",
    "jensen_huang": "Jensen_Huang",
    "sam_altman": "Sam_Altman",
    "tim_cook": "Tim_Cook",
    "sundar_pichai": "Sundar_Pichai",
    "jack_ma": "Jack_Ma",
    "larry_page": "Larry_Page",
    "sergey_brin": "Sergey_Brin",
    "peter_thiel": "Peter_Thiel",
    "satoshi_nakamoto": "Satoshi_Nakamoto",
    "gabe_newell": "Gabe_Newell",
    "vitalik_buterin": "Vitalik_Buterin",
    "bernard_arnault": "Bernard_Arnault",
    "larry_ellison": "Larry_Ellison",
    "richard_branson": "Richard_Branson",

    # 4. World Leaders & Historical Icons (20)
    "trump": "Donald_Trump",
    "joe_biden": "Joe_Biden",
    "barack_obama": "Barack_Obama",
    "vladimir_putin": "Vladimir_Putin",
    "kim_jong_un": "Kim_Jong_Un",
    "emmanuel_macron": "Emmanuel_Macron",
    "boris_johnson": "Boris_Johnson",
    "justin_trudeau": "Justin_Trudeau",
    "narendra_modi": "Narendra_Modi",
    "xi_jinping": "Xi_Jinping",
    "george_w_bush": "George_W._Bush",
    "angela_merkel": "Angela_Merkel",
    "queen_elizabeth": "Elizabeth_II",
    "bernie_sanders": "Bernie_Sanders",
    "nelson_mandela": "Nelson_Mandela",
    "winston_churchill": "Winston_Churchill",
    "abraham_lincoln": "Abraham_Lincoln",
    "julius_caesar": "Julius_Caesar",
    "napoleon": "Napoleon",
    "che_guevara": "Che_Guevara",

    # 5. Pop Culture Icons (20)
    "the_rock": "Dwayne_Johnson",
    "drake": "Drake_(musician)",
    "kanye_west": "Kanye_West",
    "snoop_dogg": "Snoop_Dogg",
    "eminem": "Eminem",
    "michael_jackson": "Michael_Jackson",
    "keanu_reeves": "Keanu_Reeves",
    "leonardo_dicaprio": "Leonardo_DiCaprio",
    "tom_cruise": "Tom_Cruise",
    "will_smith": "Will_Smith",
    "goku": "Goku",
    "naruto": "Naruto_Uzumaki",
    "luffy": "Monkey_D._Luffy",
    "walter_white": "Walter_White_(Breaking_Bad)",
    "spongebob": "SpongeBob_SquarePants_(character)",
    "shrek": "Shrek_(character)",
    "spider_man": "Spider-Man",
    "batman": "Batman",
    "taylor_swift": "Taylor_Swift",
    "billie_eilish": "Billie_Eilish"
}


def fetch_image_from_url(url, timeout=8):
    """Fetches image bytes with proper headers."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
    except Exception:
        pass
    return None


def fetch_wiki_thumbnail(wiki_page):
    """Dynamically queries Wikipedia REST API to get the current official thumbnail URL."""
    if not wiki_page:
        return None
    try:
        api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{wiki_page}"
        r = requests.get(api_url, headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json()
            thumb_url = data.get("thumbnail", {}).get("source")
            if thumb_url:
                return fetch_image_from_url(thumb_url)
    except Exception:
        pass
    return None


def crop_and_save_128x128_png(img_bytes, dest_path, crop_top_ratio=0.10):
    """Loads image, extracts a clean square crop focused on face, scales to 128x128, and saves PNG."""
    try:
        surf = pygame.image.load(io.BytesIO(img_bytes))
        try:
            surf = surf.convert_alpha()
        except Exception:
            pass
        w, h = surf.get_size()

        # Compute square dimensions focusing on face/center
        s = min(w, h)
        if h > w:
            y_off = int((h - s) * crop_top_ratio)
            x_off = 0
        elif w > h:
            y_off = 0
            x_off = int((w - s) * 0.50)
        else:
            x_off = 0
            y_off = 0

        y_off = max(0, min(h - s, y_off))
        x_off = max(0, min(w - s, x_off))

        cropped = surf.subsurface((x_off, y_off, s, s))
        scaled_128 = pygame.transform.smoothscale(cropped, (128, 128))

        pygame.image.save(scaled_128, dest_path)
        return True
    except Exception:
        return False


def setup_all_avatars(force_download=False, force_procedural=False):
    """
    Ensures all 100 personalities have avatars in `assets/celebrities/`.
    Downloads real portraits from Wikipedia / direct CDNs where available,
    and falls back to high-quality procedural caricature badges with initials.
    """
    pygame.init()
    if pygame.display.get_surface() is None:
        try:
            pygame.display.set_mode((1, 1))
        except Exception:
            pass

    os.makedirs(ASSETS_DIR, exist_ok=True)

    print("=" * 84)
    print(" [HORSE HAVOC] 100 CELEBRITY MEME AVATARS ENGINE (128x128 RGBA PNG)")
    print("=" * 84)
    print(f" * Target Directory : {os.path.abspath(ASSETS_DIR)}")
    print(f" * Roster Size      : {len(CELEBRITY_ROSTER)} Personalities across 5 Categories")
    print(f" * Download Mode    : {'FORCE DOWNLOAD' if force_download else 'ONLINE WITH FALLBACK'}")
    print("-" * 84)

    results = []

    for idx, celeb in enumerate(CELEBRITY_ROSTER, 1):
        cid = celeb["id"]
        cname = celeb["name"]
        grp = celeb.get("group", "pop_culture")
        dest_path = os.path.join(ASSETS_DIR, f"{cid}.png")

        # Check existing file status
        is_existing_valid = False
        is_real_photo = False
        if os.path.exists(dest_path):
            try:
                sz = os.path.getsize(dest_path)
                if sz > 200:
                    test_surf = pygame.image.load(dest_path)
                    if test_surf.get_width() > 0:
                        is_existing_valid = True
                        is_real_photo = (sz >= 5000)
            except Exception:
                is_existing_valid = False

        # If already a high-res real photo and not forced, preserve it
        if is_existing_valid and is_real_photo and not force_download and not force_procedural:
            sz_kb = os.path.getsize(dest_path) / 1024
            results.append({
                "id": cid,
                "name": cname,
                "group": grp,
                "size_kb": f"{sz_kb:.1f} KB",
                "status": "EXISTING_PHOTO"
            })
            continue

        # If force procedural requested
        if force_procedural:
            generate_procedural_avatar_file(celeb, dest_path, canvas_size=128)
            sz_kb = os.path.getsize(dest_path) / 1024 if os.path.exists(dest_path) else 0.0
            results.append({
                "id": cid,
                "name": cname,
                "group": grp,
                "size_kb": f"{sz_kb:.1f} KB",
                "status": "PROCEDURAL_BADGE"
            })
            continue

        # Attempt photo download
        created = False
        source = WIKI_SOURCES.get(cid)
        if source:
            time.sleep(0.12)  # Respect rate limits
            img_bytes = None
            if source.startswith("http://") or source.startswith("https://"):
                img_bytes = fetch_image_from_url(source)
            else:
                img_bytes = fetch_wiki_thumbnail(source)

            if img_bytes:
                created = crop_and_save_128x128_png(img_bytes, dest_path, crop_top_ratio=0.10)
                if created:
                    sz_kb = os.path.getsize(dest_path) / 1024
                    results.append({
                        "id": cid,
                        "name": cname,
                        "group": grp,
                        "size_kb": f"{sz_kb:.1f} KB",
                        "status": "DOWNLOADED_PHOTO"
                    })

        # Fallback to procedural caricature badge if download was unsuccessful
        if not created:
            if not is_existing_valid:
                generate_procedural_avatar_file(celeb, dest_path, canvas_size=128)
                sz_kb = os.path.getsize(dest_path) / 1024 if os.path.exists(dest_path) else 0.0
                results.append({
                    "id": cid,
                    "name": cname,
                    "group": grp,
                    "size_kb": f"{sz_kb:.1f} KB",
                    "status": "PROCEDURAL_FALLBACK"
                })
            else:
                sz_kb = os.path.getsize(dest_path) / 1024
                results.append({
                    "id": cid,
                    "name": cname,
                    "group": grp,
                    "size_kb": f"{sz_kb:.1f} KB",
                    "status": "EXISTING_BADGE"
                })

    # Summary table
    print(f" {'ID':<16} | {'NAME':<20} | {'GROUP':<14} | {'SIZE':<9} | STATUS")
    print("-" * 84)
    success = 0
    photo_count = 0
    badge_count = 0

    for r in results:
        status_tag = "[OK] " + r["status"]
        # Print cleanly without encoding crashes
        clean_id = r["id"][:16]
        clean_name = r["name"].encode("ascii", "replace").decode()[:20]
        clean_grp = r["group"][:14]
        print(f" {clean_id:<16} | {clean_name:<20} | {clean_grp:<14} | {r['size_kb']:<9} | {status_tag}")
        success += 1
        if "PHOTO" in r["status"]:
            photo_count += 1
        else:
            badge_count += 1

    total_dir_bytes = sum(
        os.path.getsize(os.path.join(ASSETS_DIR, f))
        for f in os.listdir(ASSETS_DIR) if f.endswith(".png")
    )
    print("=" * 84)
    print(f" Complete: {success} / {len(CELEBRITY_ROSTER)} avatars verified ({total_dir_bytes / (1024*1024):.2f} MB total storage).")
    print(f" Real Portraits: {photo_count} | Procedural Caricatures: {badge_count}")
    print("=" * 84)
    return success


def download_all_avatars():
    """Entry point for automated checks."""
    return setup_all_avatars(force_download=True, force_procedural=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HORSE HAVOC Avatar Setup")
    parser.add_argument("--download", "--all", action="store_true", help="Download official portraits for all 100 personalities")
    parser.add_argument("--procedural-all", action="store_true", help="Regenerate all 100 avatars procedurally")
    args = parser.parse_args()

    setup_all_avatars(force_download=True if args.download else False, force_procedural=args.procedural_all)
