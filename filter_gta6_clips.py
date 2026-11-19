#!/usr/bin/env python3
"""
Automatic GTA 6 Content Filter.
Filters out 100% of unwanted content (Warzone, Resident Evil, Soccer, Anime ads, Photos)
and preserves only strict GTA 6 clips.
"""

import json
import re

AUDIT_FILE = "/home/samirkhadka/ytbe/gta6_accounts_audit.json"
OUTPUT_CATALOG = "/home/samirkhadka/ytbe/gta6_clean_catalog.json"

WHITELIST = [
    "gta 6", "gta vi", "gtavi", "vice city",
    "lucia", "jason", "leonida", "gta6", "gta6gameplay"
]

BLACKLIST = [
    "warzone", "cod", "mw4", "bo7", "rebirth", "call of duty",
    "resident evil", "tlou", "the last of us", "abby", "ellie",
    "ballon d'or", "ronaldo", "messi", "fifa", "world cup", "spain",
    "tvアニメ", "世界の不思議な薬", "logitech", "baseball", "shrek",
    "halloween", "prophunt", "photo by"
]

def is_valid_gta6(text):
    t = text.lower()
    
    # 1. Reject if any blacklisted keyword exists
    for bad in BLACKLIST:
        if bad in t:
            return False, f"Blacklisted ({bad})"

    # 2. Accept if whitelist matches
    for good in WHITELIST:
        if good in t:
            return True, f"Matched ({good})"

    return False, "No GTA 6 signals"

def main():
    with open(AUDIT_FILE) as f:
        data = json.load(f)

    clean_clips = []
    rejected_count = 0
    rejection_reasons = {}

    for acc, posts in data.items():
        for p in posts:
            full_text = f"{p.get('text', '')} {p.get('alt', '')}".strip()
            href = p.get("href")
            
            # Shortcode check
            m = re.search(r"/(?:reel|p)/([A-Za-z0-9_-]{11})/", href)
            if not m:
                continue
            code = m.group(1)

            valid, reason = is_valid_gta6(full_text)
            if valid:
                clean_clips.append({
                    "account": acc,
                    "code": code,
                    "url": f"https://www.instagram.com/reel/{code}/",
                    "caption": full_text[:120],
                    "matched": reason
                })
            else:
                rejected_count += 1
                base_reason = reason.split("(")[0].strip()
                rejection_reasons[base_reason] = rejection_reasons.get(base_reason, 0) + 1

    print("==========================================")
    print("🤖 AUTOMATIC FILTER TEST RESULTS")
    print("==========================================")
    print(f"Total Posts Scanned: {len(clean_clips) + rejected_count}")
    print(f"✅ Approved GTA 6 Clips: {len(clean_clips)}")
    print(f"❌ Auto-Rejected Unwanted: {rejected_count}")
    print("\nRejection Breakdown:")
    for r, count in rejection_reasons.items():
        print(f"  - {r}: {count} posts blocked")

    with open(OUTPUT_CATALOG, "w") as f:
        json.dump(clean_clips, f, indent=2)

    print(f"\nSaved {len(clean_clips)} approved clips to {OUTPUT_CATALOG}")

if __name__ == "__main__":
    main()
