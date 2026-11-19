#!/usr/bin/env python3
"""
Expands manifest.json using the 557 scraped videos in roblox_reels_catalog.json.
Uses round-robin across creators for optimal content diversity.
"""

import os
import json
import re
from datetime import datetime, timedelta, timezone

BASE_DIR = "/home/samirkhadka/ytbe"
MANIFEST_FILE = os.path.join(BASE_DIR, "manifest.json")
CATALOG_FILE = os.path.join(BASE_DIR, "roblox_reels_catalog.json")

HOOK_TITLES_BY_ACCOUNT = {
    "craftee_films": [
        "Trapped in 100 Days of Hardcore Roblox 🚨🔥 #Shorts",
        "The Impossible Maze Escape 🏃‍♂️💨 #Shorts",
        "Don't Look At The Red Light 🔴😱 #Shorts",
        "I Built an Unbreakable Diamond Vault 💎🔒 #Shorts",
        "Surviving 99 Level Floor Is Lava 🌋💀 #Shorts"
    ],
    "stickman.deadzone": [
        "Stickman Physics Gone Wrong 💥🤸 #Shorts",
        "Ragdoll vs Giant Shredder 😱⚙️ #Shorts",
        "1000 IQ Escape Route 🧠⚡ #Shorts",
        "Stickman Parkour Impossible Jump 🏃‍♂️🎯 #Shorts",
        "The Ultimate Stickman Arena ⚔️💀 #Shorts"
    ],
    "coo.gae": [
        "Bro Thought He Was Safe 😭💀 #Shorts",
        "When Your Teammate Sells The Win 🤦‍♂️🎮 #Shorts",
        "Only 1% of Players Can Beat This 🏆🔥 #Shorts",
        "Wait Till The Very End 😱👀 #Shorts",
        "The Funniest Roblox Glitch Ever 😂💥 #Shorts"
    ],
    "robloxstoriesevryday": [
        "The Plastic Bag Secret Protocol 🛍️🔒 #Shorts",
        "Touching The Ground Costs $1,000,000 💸🚨 #Shorts",
        "My Teacher Is An Alien In Disguise 👽🎒 #Shorts",
        "The Forbidden Locker Room Mystery 🚪🔍 #Shorts",
        "I Discovered A Secret World Under School 🏫⚡ #Shorts"
    ],
    "zaylento": [
        "The Voice Inside The Game 🎙️👀 #Shorts",
        "Never Break The Number One Rule 📜⚠️ #Shorts",
        "The Shadow Creature Is Watching 👤👁️ #Shorts",
        "Escape Before The Timer Hits Zero ⏳🏃 #Shorts",
        "The Haunting Of Block City 🏙️👻 #Shorts"
    ],
    "ruletopia": [
        "Follow The Rules Or Disappear 🛑⚠️ #Shorts",
        "Rule Number 7 Will Shock You 📜⚡ #Shorts",
        "The Mystery Player Who Never Speaks 👤🤫 #Shorts",
        "Floor 100 Of The Infinite Tower 🏢🧗 #Shorts",
        "The Red Door Challenge 🚪🔴 #Shorts"
    ],
    "nixuj_playz": [
        "Villain Origin Story Begins 😈🚨 #Shorts",
        "The Golden Key Quest 🔑✨ #Shorts",
        "Nobody Escapes Level 50 🚪🔒 #Shorts",
        "The Mystery In Room 304 🔍😱 #Shorts",
        "The Plastic Bag Vault Finale 🛍️👑 #Shorts"
    ],
    "themiloshoww": [
        "Milo's Funniest Roblox Moment 😂🎮 #Shorts",
        "Bro Got Sent To The Backrooms 🟨😱 #Shorts",
        "When You Accidentally Press Reset 💀💥 #Shorts",
        "The 1v1 That Broke The Game ⚔️🔥 #Shorts"
    ],
    "moodlyvines": [
        "Roblox Vines That Cure Boredom 😂✨ #Shorts",
        "Moodly's Most Viral Skit 🎭🔥 #Shorts",
        "The Ultimate NPC Encounter 🤖💀 #Shorts",
        "When Lag Saves Your Life 📶🙌 #Shorts"
    ]
}

DEFAULT_HOOKS = [
    "The Impossible Challenge 🚨🔥 #Shorts",
    "Nobody Expected This Ending 😱👀 #Shorts",
    "1000 IQ Brainrot Strategy 🧠⚡ #Shorts",
    "Surviving The Most Dangerous Game 💀🎮 #Shorts",
    "The Funniest Roblox Moment 😂✨ #Shorts"
]

def main():
    with open(MANIFEST_FILE) as f:
        manifest = json.load(f)

    with open(CATALOG_FILE) as f:
        catalog = json.load(f)

    existing_urls = {s.get("instagram_url") for s in manifest["schedule"] if s.get("instagram_url")}
    print(f"Current scheduled entries: {len(manifest['schedule'])}")
    print(f"Existing scheduled Instagram URLs: {len(existing_urls)}")

    # Collect unqueued URLs per account
    account_queues = {}
    total_new = 0
    for acc, urls in catalog.items():
        unqueued = [u for u in urls if u not in existing_urls]
        account_queues[acc] = unqueued
        total_new += len(unqueued)
        print(f"  @{acc}: {len(unqueued)} new unqueued URLs")

    print(f"Total new unqueued URLs across all accounts: {total_new}")

    # Interleave / Round-Robin accounts
    interleaved = []
    accounts = list(account_queues.keys())
    max_len = max(len(q) for q in account_queues.values()) if account_queues else 0

    for idx in range(max_len):
        for acc in accounts:
            q = account_queues[acc]
            if idx < len(q):
                interleaved.append((acc, q[idx]))

    print(f"Prepared {len(interleaved)} interleaved items for scheduling.")

    start_day = manifest["total_days"] + 1
    # Base scheduled time from last entry or start
    last_entry = manifest["schedule"][-1]
    last_time_str = last_entry["scheduled_time"]
    try:
        last_dt = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    except Exception:
        last_dt = datetime(2027, 5, 10, 14, 0, tzinfo=timezone.utc)

    for i, (acc, url) in enumerate(interleaved):
        day_num = start_day + i
        sched_dt = last_dt + timedelta(days=i + 1)
        
        # Shortcode from URL
        m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{11})/", url)
        reel_id = m.group(1) if m else f"roblox_{day_num}"

        hooks = HOOK_TITLES_BY_ACCOUNT.get(acc, DEFAULT_HOOKS)
        hook_tmpl = hooks[i % len(hooks)]
        hook_clean = hook_tmpl.replace(" #Shorts", "")
        title = f"{hook_clean} (Ep. {day_num}) #Shorts"

        entry = {
            "day": day_num,
            "type": "instagram_remix",
            "account": acc,
            "reel_id": reel_id,
            "instagram_url": url,
            "part": "single",
            "title": title,
            "description": (
                f"{title}\n\n"
                "Can you survive this Roblox challenge? Drop your score in the comments! 👇\n\n"
                "🔔 Subscribe for daily high-retention Roblox stories, physics glitches, and viral 3D animations!\n\n"
                f"#roblox #shorts #robloxstories #robloxfyp #gaming #viral #trending #{acc.replace('.', '_')}"
            ),
            "tags": [
                "roblox",
                "shorts",
                "robloxstories",
                "robloxfyp",
                "gaming",
                "viral",
                "trending",
                "brainrot",
                acc.replace(".", "_")
            ],
            "scheduled_time": sched_dt.strftime("%Y-%m-%d %H:%M UTC"),
            "status": "queued"
        }
        manifest["schedule"].append(entry)

    manifest["total_days"] = len(manifest["schedule"])

    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"🎉 SUCCESS! Manifest expanded to {manifest['total_days']} total days!")
    print(f"Runway now spans from Day 1 to Day {manifest['total_days']} ({manifest['schedule'][-1]['scheduled_time']})!")

if __name__ == "__main__":
    main()
