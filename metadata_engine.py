#!/usr/bin/env python3
"""
HORSE HAVOC - Dynamic AI & Procedural Multi-Platform Metadata Engine
====================================================================
Generates unique, match-specific, high-CTR copywriting for:
  - YouTube Shorts (Title, Description with channel callouts, Tags array, Hashtags)
  - Instagram Reels (Engaging event-driven caption, follow line, hashtags)
  - TikTok (Punchy, viral hook, character-compliant, FYP hashtags)

Supports:
  1. Google Gemini 1.5 Flash REST API (if GEMINI_API_KEY is configured)
  2. Dynamic Procedural Randomizer (inspects game events, runner-up, clutch stuns, and margins)
"""

import os
import re
import json
import random
import requests
from dotenv import load_dotenv

load_dotenv()


def clean_tag(name):
    """Converts a name to a valid hashtag string (e.g. 'Cristiano Ronaldo' -> 'CristianoRonaldo')."""
    return re.sub(r"[^A-Za-z0-9]", "", name)


def analyze_race_events(events, winner_name, runner_up_name):
    """
    Analyzes telemetry events to find the key dramatic moment of the race.
    Returns:
      - key_event_desc: human-readable phrase of the climax
      - primary_weapon: weapon involved in climax (rocket, mud bomb, laser)
      - victim_name: horse that suffered the critical stun
    """
    rocket_hits = []
    laser_hits = []
    mud_hits = []
    bumps = []
    lead_changes = []

    for ev in events:
        msg = ev.get("message", "")
        t = ev.get("time_sec", 0.0)

        if "STUNNED BY ROCKET" in msg:
            rocket_hits.append((t, msg))
        elif "STUNNED BY LASER" in msg:
            laser_hits.append((t, msg))
        elif "MUD" in msg or "SLIPPED" in msg:
            mud_hits.append((t, msg))
        elif "BUMP" in msg or "CONTACT" in msg:
            bumps.append((t, msg))
        elif "SURGES INTO 1ST" in msg:
            lead_changes.append((t, msg))

    # Priority 1: Did runner_up get hit by a weapon in the second half of the race?
    late_hits = [h for h in (rocket_hits + laser_hits + mud_hits) if h[0] > 15.0]
    if late_hits and runner_up_name:
        for t, msg in reversed(late_hits):
            if runner_up_name.upper() in msg.upper():
                if "ROCKET" in msg:
                    return f"{runner_up_name} getting blasted by a homing rocket", "that rocket", runner_up_name
                elif "LASER" in msg:
                    return f"{runner_up_name} getting sniped by a laser beam", "the laser beam", runner_up_name
                elif "MUD" in msg:
                    return f"{runner_up_name} sliding out in a mud trap", "that mud bomb", runner_up_name

    # Priority 2: Any late rocket sabotage?
    if rocket_hits:
        last_rocket = rocket_hits[-1]
        victim = "a rival"
        for candidate in [runner_up_name, "the leader"]:
            if candidate and candidate.upper() in last_rocket[1].upper():
                victim = candidate
                break
        return f"{victim} getting vaporized by a rocket", "a rocket sabotage", victim

    # Priority 3: Frequent lead changes / photo-finish
    if len(lead_changes) >= 3:
        return f"an insane {len(lead_changes)}-way lead swap before the line", "a photo-finish battle", runner_up_name

    # Default fallback
    return f"a chaotic photo-finish sprint", "pure chaos", runner_up_name or "the pack"


def generate_metadata_via_gemini(winner_name, runner_up_name, finish_time, margin_sec, key_event_desc, lead_changes, weapon_hits, api_key):
    """Calls Google Gemini 1.5 Flash to generate tailored, non-repeating copy."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

    prompt = f"""You are an elite viral gaming social media copywriter for the 2D comedy derby game 'Horse Havoc'.
A race just finished with these exact match highlights:
- Winner: {winner_name} (Finish Time: {finish_time:.2f}s)
- Runner-Up (2nd Place): {runner_up_name}
- Victory Margin: {margin_sec:.2f} seconds
- Key Clutch Event: {key_event_desc}
- Total Lead Changes: {lead_changes}
- Total Weapon Hits: {weapon_hits}

Generate high-CTR, exciting, non-repeating viral copy in strict JSON format matching this schema:
{{
  "youtube": {{
    "title": "Short high-CTR hook title under 65 chars with emojis (e.g. '{winner_name} STOLE THE DERBY IN THE LAST SECOND?! 🏆😱 #Shorts')",
    "description": "2-3 engaging sentences summarizing how {winner_name} won and {runner_up_name} got sabotaged. Do not include fixed channel callouts or hashtags here.",
    "tags": ["Horse Havoc", "Shorts", "Gaming", "Meme Derby", "{winner_name}", "{runner_up_name}", "Funny Gaming", "AI Racing"]
  }},
  "instagram": {{
    "caption_story": "1-2 engaging interactive sentences highlighting {winner_name}'s clutch win and {runner_up_name}'s fate, asking viewers who they picked."
  }},
  "tiktok": {{
    "caption": "Punchy 1-sentence viral hook with emojis (e.g. '{winner_name} really pulled this off with {margin_sec:.1f}s left 💀🏆 #HorseHavoc #Gaming #FYP #MemeRace #{clean_tag(winner_name)}')"
  }}
}}
Return ONLY valid raw JSON without markdown code fences."""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": 600}
    }

    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            data = json.loads(raw_text.strip())
            return data
    except Exception as e:
        print(f"[METADATA] Gemini 1.5 Flash fallback: {e}")

    return None


def generate_dynamic_procedural_metadata(
    winner_name,
    runner_up_name,
    third_place_name,
    finish_time,
    margin_sec,
    key_event_desc,
    primary_weapon,
    lead_changes,
    weapon_hits,
    track_name=None,
    track_theme=None,
    group_name=None,
    group_key=None,
    roster=None
):
    """
    Algorithmic generator guaranteeing unique, non-repeating, match-specific copywriting
    across YouTube Shorts, Instagram Reels, and TikTok without external API dependencies.
    """
    winner_tag = clean_tag(winner_name)
    runner_up_tag = clean_tag(runner_up_name) if runner_up_name else "MemeDerby"
    track_str = track_name or "Classic Turf Derby"
    track_tag = clean_tag(track_str)
    margin_str = f"{margin_sec:.2f}s" if margin_sec < 1.0 else f"{margin_sec:.1f}s"
    grp_name = group_name or "Derby"
    grp_key = (group_key or "general").lower()
    group_tag = clean_tag(grp_name)

    # -------------------------------------------------------------
    # 1. YOUTUBE SHORTS (Category-tailored high-CTR viral hooks)
    # -------------------------------------------------------------
    if grp_key == "football":
        category_titles = [
            f"⚽ {winner_name} vs {runner_up_name} in FOOTBALL DERBY! Who wins?! 🏆😱 #Shorts",
            f"The Football Legends Derby Was Pure Chaos! ⚽🔥 #Shorts",
            f"HOW DID {winner_name.upper()} BEAT THE GOATS AT {track_str.upper()}?! ⚽🔥 #Shorts",
            f"{winner_name} vs {runner_up_name}: INSANE 0.1s FOOTBALL DERBY FINISH! ⚽🏆 #Shorts",
            f"THE CRAZIEST FOOTBALL DERBY IN HORSE HAVOC HISTORY! ⚽💥 #Shorts"
        ]
    elif grp_key == "tech_business":
        category_titles = [
            f"💻 {winner_name} vs {runner_up_name} BILLIONAIRE SHOWDOWN! 🚀🤯 #Shorts",
            f"The Tech Titans Derby Was Pure Chaos! 💻🔥 #Shorts",
            f"{winner_name.upper()} JUST OUTSMARTED THE TECH TITANS! 🤖💥 #Shorts",
            f"TECH DERBY CHAOS: {winner_name} vs {runner_up_name} AT {track_str.upper()}! 💻🏆 #Shorts",
            f"WHO WINS THE BILLIONAIRE HORSE DERBY?! 🚀🏁 #Shorts"
        ]
    elif grp_key == "streamers":
        category_titles = [
            f"🎮 {winner_name} vs {runner_up_name}! INSANE STREAMER DERBY FINISH! 🔥😱 #Shorts",
            f"The Streamer Royale Derby Was Pure Chaos! 🎮🔥 #Shorts",
            f"BRO CAUGHT A ROCKET IN THE CREATORS DERBY?! 😭🎮 #Shorts",
            f"{winner_name.upper()} CLUTCHED 1st AGAINST THE TOP STREAMERS! 💥🏆 #Shorts",
            f"MRBEAST vs SPEED vs {winner_name.upper()}! PURE CHAOS! 🎮🔥 #Shorts"
        ]
    elif grp_key == "world_leaders":
        category_titles = [
            f"🌍 {winner_name} vs {runner_up_name} in the PRESIDENTIAL DERBY! 🏛️🦅 #Shorts",
            f"The World Leaders Derby Was Pure Chaos! 🌍🔥 #Shorts",
            f"WHO WINS THE WORLD LEADERS HORSE RACE?! 🏛️🏁 #Shorts",
            f"{winner_name.upper()} TOOK OVER THE DERBY AT {track_str.upper()}! 👑💥 #Shorts",
            f"PRESIDENTIAL PHOTO FINISH: {winner_name} vs {runner_up_name}! 🏛️🏆 #Shorts"
        ]
    elif grp_key == "pop_culture":
        category_titles = [
            f"🌟 {winner_name} vs {runner_up_name}! CRAZIEST POP DERBY EVER! 🍿🏆 #Shorts",
            f"The Pop Icons Derby Was Pure Chaos! 🌟🔥 #Shorts",
            f"HOW DID {winner_name.upper()} SURVIVE THIS POP SHOWDOWN?! 🍿💥 #Shorts",
            f"{winner_name.upper()} JUST CLUTCHED THE ALL-STAR POP RACE! 🌟🐎 #Shorts",
            f"THE ULTIMATE POP CULTURE SHOWDOWN AT {track_str.upper()}! 🍿🏁 #Shorts"
        ]
    else:
        category_titles = [
            f"{winner_name.upper()} STOLE THE DERBY IN THE LAST SECOND?! 🏆😱 #Shorts",
            f"HOW DID {winner_name.upper()} SURVIVE {track_str.upper()}?! 🚀🤯 #Shorts",
            f"{winner_name} vs {runner_up_name}: INSANE PHOTO FINISH! 🏁🐎 #Shorts",
            f"{winner_name} JUST CLUTCHED AT {track_str.upper()}! 🏆💥 #Shorts"
        ]

    yt_title = random.choice(category_titles)

    yt_story_templates = [
        (
            f"{winner_name} just pulled off one of the craziest finishes in Horse Havoc history during the {grp_name} on {track_str}! "
            f"{runner_up_name} held the lead until {key_event_desc}, triggering a frantic sprint to the line. "
            f"With {weapon_hits} weapon blasts and {lead_changes} lead changes, this match was absolute pandemonium!"
        ),
        (
            f"You won't believe how the {grp_name} at {track_str} ended! "
            f"{runner_up_name} was cruising toward the podium before getting rocked by {primary_weapon}. "
            f"{winner_name} capitalized in the final meters to take the trophy by just {margin_str}!"
        ),
        (
            f"Pure 2D racing combat at its finest in the {grp_name} at {track_str}! "
            f"{winner_name} and {runner_up_name} went head-to-head through rockets, mud bombs, and rail bumps. "
            f"In the end, {winner_name} crossed first in {finish_time:.2f}s to claim victory!"
        )
    ]
    yt_summary = random.choice(yt_story_templates)

    yt_callouts = (
        "\n\n"
        f"🏆 Championship: {grp_name}\n"
        f"🐎 Map: {track_str}\n"
        "🎮 Game: Horse Havoc\n"
        "⏰ 2 Daily Races: 12:00 AM & 12:00 PM!\n"
        "👉 Subscribe to @HorseHavoc for daily derby action!\n\n"
        f"#Shorts #HorseHavoc #{group_tag} #Gaming #MemeRace #{winner_tag} #{runner_up_tag} #{track_tag} #FunnyMoments"
    )
    yt_full_description = yt_summary + yt_callouts

    yt_tags = [
        "Horse Havoc",
        "Shorts",
        "Gaming",
        "Meme Derby",
        grp_name,
        track_str,
        winner_name,
        runner_up_name if runner_up_name else "Meme Race",
        "Funny Gaming",
        "AI Racing",
        "Horse Racing",
        "Photo Finish",
        "Viral Moments"
    ]

    # -------------------------------------------------------------
    # 2. INSTAGRAM REELS
    # -------------------------------------------------------------
    ig_story_templates = [
        f"{winner_name} took home the {grp_name} trophy today, but {runner_up_name} got absolutely obliterated by {primary_weapon}! 🚀😂 Who was your pick?",
        f"{winner_name} really clutched 1st place in the final {margin_str} of the {grp_name} while {runner_up_name} fought through {weapon_hits} weapon blasts! 💥🐎 Who had your vote?",
        f"0.1s margin of victory! {winner_name} edged out {runner_up_name} in the {grp_name} after {key_event_desc}! 🏆🔥 Drop your favorite in the comments!"
    ]
    ig_story = random.choice(ig_story_templates)

    ig_caption = (
        f"{ig_story}\n\n"
        f"🏆 Match: {grp_name} @ {track_str}\n"
        "🐎 Follow @horse.havoc for daily 2D combat races! ⏰ Daily drops at 12 AM & 12 PM.\n\n"
        f"#HorseHavoc #{group_tag} #Reels #GamingMemes #DerbyRace #{winner_tag} #{runner_up_tag} #ViralGaming"
    )

    # -------------------------------------------------------------
    # 3. TIKTOK
    # -------------------------------------------------------------
    tt_templates = [
        f"{winner_name} really won the {grp_name} by {margin_str} 💀🏆 #HorseHavoc #{group_tag} #Gaming #FYP #{winner_tag}",
        f"{winner_name} clutched the {grp_name} after {runner_up_name} caught that rocket 😭🚀 #HorseHavoc #{group_tag} #Gaming #FYP #{winner_tag}",
        f"The {grp_name} was pure chaos from start to finish 🐎🔥 #HorseHavoc #{group_tag} #Gaming #FYP #{winner_tag}",
        f"Bro really thought he won the {grp_name} until {winner_name} hit the turbo 💀🏁 #HorseHavoc #{group_tag} #Gaming #FYP #{winner_tag}"
    ]
    tt_caption = random.choice(tt_templates)

    return {
        "youtube": {
            "title": yt_title,
            "description": yt_full_description,
            "summary": yt_summary,
            "tags": yt_tags,
            "hashtags": [f"#{winner_tag}", f"#{runner_up_tag}", f"#{group_tag}", "#Shorts", "#HorseHavoc", "#Gaming"]
        },
        "instagram": {
            "caption": ig_caption,
            "hashtags": [f"#{winner_tag}", f"#{runner_up_tag}", f"#{group_tag}", "#HorseHavoc", "#Reels", "#GamingMemes"]
        },
        "tiktok": {
            "caption": tt_caption,
            "hashtags": [f"#{winner_tag}", f"#{group_tag}", "#HorseHavoc", "#Gaming", "#FYP", "#MemeRace"]
        },
        "group": grp_key,
        "group_name": grp_name,
        "engine": "Dynamic Procedural Randomizer"
    }


def generate_match_metadata(
    winner_name,
    runner_up_name,
    third_place_name,
    finish_time,
    margin_sec,
    events,
    track_name=None,
    track_theme=None,
    group_name=None,
    group_key=None,
    roster=None
):
    """
    Master entrypoint: Attempts Gemini 1.5 Flash first, then seamlessly
    falls back to the match-specific procedural generator.
    """
    lead_changes = sum(1 for e in events if "SURGES INTO 1ST" in e.get("message", ""))
    weapon_hits = sum(1 for e in events if "HIT!" in e.get("message", "") or "STUNNED" in e.get("message", ""))
    key_event_desc, primary_weapon, victim_name = analyze_race_events(events, winner_name, runner_up_name)

    # Incur category from game_events.json or roster if not directly provided
    if not group_key:
        if os.path.exists("game_events.json"):
            try:
                with open("game_events.json", "r", encoding="utf-8") as gef:
                    ge_d = json.load(gef)
                    group_key = ge_d.get("active_category")
                    group_name = ge_d.get("category_name")
            except Exception:
                pass
        if not group_key and roster and isinstance(roster[0], dict):
            group_key = roster[0].get("group", "football")
            group_name = roster[0].get("group_name", "Football Derby")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_data = None
    if api_key:
        print("[METADATA] Requesting match-specific copywriting from Gemini 1.5 Flash...")
        gemini_data = generate_metadata_via_gemini(
            winner_name=winner_name,
            runner_up_name=runner_up_name,
            finish_time=finish_time,
            margin_sec=margin_sec,
            key_event_desc=key_event_desc,
            lead_changes=lead_changes,
            weapon_hits=weapon_hits,
            api_key=api_key
        )

    # Procedural fallback or baseline
    proc = generate_dynamic_procedural_metadata(
        winner_name=winner_name,
        runner_up_name=runner_up_name,
        third_place_name=third_place_name,
        finish_time=finish_time,
        margin_sec=margin_sec,
        key_event_desc=key_event_desc,
        primary_weapon=primary_weapon,
        lead_changes=lead_changes,
        weapon_hits=weapon_hits,
        track_name=track_name,
        track_theme=track_theme,
        group_name=group_name,
        group_key=group_key,
        roster=roster
    )

    if gemini_data:
        winner_tag = clean_tag(winner_name)
        runner_up_tag = clean_tag(runner_up_name) if runner_up_name else "MemeDerby"
        yt_summary = gemini_data.get("youtube", {}).get("description", proc["youtube"]["summary"])
        yt_callouts = (
            "\n\n"
            "🐎 Game: Horse Havoc\n"
            "⏰ 2 Daily Races: 12:00 AM & 12:00 PM!\n"
            "👉 Subscribe to @HorseHavoc for daily derby action!\n\n"
            f"#Shorts #HorseHavoc #Gaming #MemeRace #{winner_tag} #{runner_up_tag} #FunnyMoments"
        )

        ig_story = gemini_data.get("instagram", {}).get("caption_story", "")
        ig_caption = (
            f"{ig_story}\n\n"
            "🐎 Follow @horse.havoc for daily 2D combat races! ⏰ Daily drops at 12 AM & 12 PM.\n\n"
            f"#HorseHavoc #Reels #GamingMemes #DerbyRace #{winner_tag} #{runner_up_tag} #ViralGaming"
        ) if ig_story else proc["instagram"]["caption"]

        return {
            "primary_title": gemini_data.get("youtube", {}).get("title", proc["youtube"]["title"]),
            "description": yt_summary + yt_callouts,
            "tags_string": f"#Shorts #HorseHavoc #Gaming #MemeRace #{winner_tag}",
            "hashtags": proc["youtube"]["hashtags"],
            "youtube": {
                "title": gemini_data.get("youtube", {}).get("title", proc["youtube"]["title"]),
                "description": yt_summary + yt_callouts,
                "tags": gemini_data.get("youtube", {}).get("tags", proc["youtube"]["tags"]),
                "hashtags": proc["youtube"]["hashtags"]
            },
            "instagram": {
                "caption": ig_caption
            },
            "tiktok": {
                "caption": gemini_data.get("tiktok", {}).get("caption", proc["tiktok"]["caption"])
            },
            "key_clutch_event": key_event_desc,
            "metadata_engine": "Gemini 1.5 Flash (AI Tailored)"
        }

    # Return Procedural
    return {
        "primary_title": proc["youtube"]["title"],
        "description": proc["youtube"]["description"],
        "tags_string": " ".join(proc["youtube"]["hashtags"]),
        "hashtags": proc["youtube"]["hashtags"],
        "youtube": proc["youtube"],
        "instagram": proc["instagram"],
        "tiktok": proc["tiktok"],
        "key_clutch_event": key_event_desc,
        "metadata_engine": "Dynamic Procedural Randomizer"
    }

