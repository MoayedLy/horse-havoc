"""
Automated Celebrity Meme Face Image Downloader for HORSE HAVOC
==============================================================
Downloads real funny meme / portrait headshots for celebrities and saves
them directly as centered, standardized 256x256 images in `assets/celebrities/`.

Features:
- Connects to Wikipedia / Wikimedia Commons API with descriptive User-Agent.
- Automatically crops portraits into face-centered squares.
- Saves high-quality PNGs ready for circular masking in the game engine.
- Safe execution: continues even if any single image fails or if offline.
"""

import os
import io
import time
import requests

# Reconfigure console encoding
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "celebrities")
HEADERS = {
    "User-Agent": "HorseHavocCelebrityDownloader/1.0 (contact: admin@horsehavoc.io; gaming meme project)"
}

CELEBRITY_SOURCES = [
    {
        "id": "ronaldo",
        "wiki_title": "Cristiano_Ronaldo",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/8/8c/Cristiano_Ronaldo_2018.jpg",
        "crop_ratio": 0.12
    },
    {
        "id": "messi",
        "wiki_title": "Lionel_Messi",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/b/b4/Lionel-Messi-Argentina-2022-FIFA-World-Cup_%28cropped%29.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "mbappe",
        "wiki_title": "Kylian_Mbapp%C3%A9",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/5/57/2019-07-17_SG_Dynamo_Dresden_vs._Paris_Saint-Germain_by_Sandro_Halank%E2%80%93129_%28cropped%29.jpg",
        "crop_ratio": 0.15
    },
    {
        "id": "elon_musk",
        "wiki_title": "Elon_Musk",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/3/34/Elon_Musk_Royal_Society_%28crop2%29.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "mrbeast",
        "wiki_title": "MrBeast",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/c/ce/MrBeast_2023_%28cropped%29.jpg",
        "crop_ratio": 0.12
    },
    {
        "id": "ishowspeed",
        "wiki_title": "IShowSpeed",
        "direct_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/e/ea/IShowSpeed_at_Chinatown_%28Portrait%29_04.jpg/500px-IShowSpeed_at_Chinatown_%28Portrait%29_04.jpg",
        "crop_ratio": 0.15
    },
    {
        "id": "the_rock",
        "wiki_title": "Dwayne_Johnson",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/1/1f/Dwayne_Johnson_2014_%28cropped%29.jpg",
        "crop_ratio": 0.08
    },
    {
        "id": "zuckerberg",
        "wiki_title": "Mark_Zuckerberg",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/1/12/P20260929DT-1655_%2855561811540%29_%28cropped_2%29.jpg",
        "crop_ratio": 0.12
    },
    {
        "id": "bill_gates",
        "wiki_title": "Bill_Gates",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/a/a8/Bill_Gates_2017_%28cropped%29.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "pewdiepie",
        "wiki_title": "PewDiePie",
        "direct_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/5/53/Pewdiepie_head_shot.jpg/500px-Pewdiepie_head_shot.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "haaland",
        "wiki_title": "Erling_Haaland",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/0/07/Erling_Haaland_2023_%28cropped%29.jpg",
        "crop_ratio": 0.12
    },
    {
        "id": "neymar",
        "wiki_title": "Neymar",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/8/83/Bra-Cos_%281%29_%28cropped%29.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "lebron",
        "wiki_title": "LeBron_James",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/7/7a/LeBron_James_%2851959977144%29_%28cropped2%29.jpg",
        "crop_ratio": 0.12
    },
    {
        "id": "trump",
        "wiki_title": "Donald_Trump",
        "direct_url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/1/16/Official_Presidential_Portrait_of_President_Donald_J._Trump_%282025%29.jpg/500px-Official_Presidential_Portrait_of_President_Donald_J._Trump_%282025%29.jpg",
        "crop_ratio": 0.10
    },
    {
        "id": "hasbulla",
        "wiki_title": "Khabib_Nurmagomedov",
        "direct_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Khabib_Nurmagomedov_in_2018.jpg/440px-Khabib_Nurmagomedov_in_2018.jpg",
        "crop_ratio": 0.12
    }
]

def resolve_image_url(celeb):
    """Fetches high-resolution thumbnail URL via Wikipedia API or falls back to direct URL."""
    wiki_title = celeb.get("wiki_title")
    if wiki_title:
        try:
            api_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={wiki_title}&prop=pageimages&format=json&pithumbsize=500"
            r = requests.get(api_url, headers=HEADERS, timeout=6)
            if r.status_code == 200:
                pages = r.json().get("query", {}).get("pages", {})
                for pid, pdata in pages.items():
                    thumb = pdata.get("thumbnail", {}).get("source")
                    if thumb:
                        return thumb
        except Exception:
            pass

    return celeb.get("direct_url")

def download_and_crop_avatar(celeb, output_dir=ASSETS_DIR):
    """
    Downloads, face-crops, and saves a 256x256 PNG headshot for the celebrity.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"{celeb['id']}.png")

    img_url = resolve_image_url(celeb)
    if not img_url:
        print(f" [!] No URL found for {celeb['id']}")
        return False

    try:
        r = requests.get(img_url, headers=HEADERS, timeout=12)
        if r.status_code != 200 or len(r.content) < 2000:
            # Try direct URL fallback if different
            if img_url != celeb.get("direct_url") and celeb.get("direct_url"):
                r = requests.get(celeb["direct_url"], headers=HEADERS, timeout=12)

        if r.status_code == 200 and len(r.content) >= 2000:
            surf = pygame.image.load(io.BytesIO(r.content))
            w, h = surf.get_size()

            # Center square crop focusing on head
            s = min(w, h)
            crop_ratio = celeb.get("crop_ratio", 0.12)
            y_off = int((h - s) * crop_ratio) if h > w else 0
            x_off = int((w - s) * 0.50) if w > h else 0

            # Safety clamp
            y_off = max(0, min(h - s, y_off))
            x_off = max(0, min(w - s, x_off))

            cropped = surf.subsurface((x_off, y_off, s, s))
            scaled = pygame.transform.smoothscale(cropped, (256, 256))
            pygame.image.save(scaled, out_path)
            print(f" [OK] Downloaded & Cropped: {celeb['id']:<12} -> {out_path} ({w}x{h} -> 256x256)")
            return True
        else:
            print(f" [!] HTTP {r.status_code} for {celeb['id']}")
            return False
    except Exception as e:
        print(f" [!] Error downloading {celeb['id']}: {e}")
        return False

def download_all_celebrities():
    """Batch downloads all 15 celebrity avatars with respectful delay."""
    pygame.init()
    print("=" * 70)
    print(" [HORSE HAVOC] CELEBRITY MEME FACE DOWNLOADER")
    print("=" * 70)
    print(f" * Target Directory : {ASSETS_DIR}")
    print(f" * Total Celebrities: {len(CELEBRITY_SOURCES)}")
    print("-" * 70)

    success_count = 0
    for idx, c in enumerate(CELEBRITY_SOURCES, 1):
        print(f"[{idx:2d}/{len(CELEBRITY_SOURCES)}] Processing {c['id']}...")
        if download_and_crop_avatar(c):
            success_count += 1
        time.sleep(0.35)  # Respectful delay between requests

    print("=" * 70)
    print(f" COMPLETE: Successfully downloaded {success_count}/{len(CELEBRITY_SOURCES)} real celebrity photos!")
    print(f" Location: {ASSETS_DIR}")
    print("=" * 70)
    return success_count

if __name__ == "__main__":
    download_all_celebrities()

