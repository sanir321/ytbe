#!/usr/bin/env python3
"""
Rumble SEO & Metadata Generator for Financial/Crypto Content
Optimized for high CTR with Rumble's core 35-65 demographic.
"""

import re
from typing import Dict, Any, List

def format_rumble_title(original_title: str, topic_badge: str) -> str:
    cleaned = original_title.strip()
    # Remove generic YouTube suffixes like | Full Video, etc.
    for suffix in ["- Full Video", "| Full Video", "(Full Video)", "| CSPAN", "- CSPAN"]:
        cleaned = cleaned.replace(suffix, "").strip()

    badge_map = {
        "senate": "[SENATE TESTIMONY]",
        "congress": "[CONGRESSIONAL HEARING]",
        "hearing": "[FULL HEARING]",
        "clash": "[HISTORIC CLASH]",
        "grilling": "[HEATED GRILLING]",
        "inflation": "[MONETARY TRUTH]",
        "gold": "[SOUND MONEY]",
        "dollar": "[ECONOMIC WARNING]",
        "collapse": "[ECONOMIC WARNING]",
        "speech": "[UNCUT SPEECH]",
        "uap": "[DECLASSIFIED TESTIMONY]",
        "ufo": "[DECLASSIFIED TESTIMONY]"
    }

    chosen_badge = "[UNCUT TESTIMONY]"
    low_title = cleaned.lower()
    for k, v in badge_map.items():
        if k in low_title or k in topic_badge.lower():
            chosen_badge = v
            break

    # Build compelling title within 90 chars
    title = f"{chosen_badge} {cleaned}"
    if len(title) > 95:
        title = title[:92] + "..."
    return title

def extract_viral_headline(title: str) -> List[str]:
    # 1. Clean dates, timestamps, years, and channel tags
    t = re.sub(r'[-\|:]?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{2,4}', '', title, flags=re.IGNORECASE)
    t = re.sub(r'[-\|:]?\s*\d{1,2}/\d{1,2}/\d{2,4}', '', t)
    t = re.sub(r'[-\|:]?\s*\b(19|20)\d{2}\b', '', t)
    t = re.sub(r'\(.*?\)|\[.*?\]', '', t)
    t = re.sub(r'\|.*$', '', t)
    t = re.sub(r'\s+in\s+\d+\s+minutes.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*-\s*Full Video.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*-\s*CSPAN.*$', '', t, flags=re.IGNORECASE)
    t = t.strip(' -|:,')

    # 2. Check for question pattern (e.g. Is Gold Money?)
    q_match = re.search(r'(is [^?]+|\bwhy [^?]+|\bcan [^?]+|\bwhat [^?]+)\??', t, re.IGNORECASE)
    
    # 3. Check for VS pattern
    vs_match = re.search(r'([A-Za-z\s]+)\s+vs\.?\s+([A-Za-z\s]+)', t, re.IGNORECASE)

    lines = []
    if q_match:
        q_text = q_match.group(1).strip()
        if not q_text.endswith('?'):
            q_text += '?'
        lines.append(q_text.upper())
        if vs_match:
            p1 = vs_match.group(1).strip().split()[-1]
            p2 = vs_match.group(2).strip().split()[-1]
            lines.append(f"{p1} VS {p2}".upper())
        else:
            lines.append('CONGRESSIONAL CLASH')
    elif vs_match:
        p1 = vs_match.group(1).strip().split()[-1]
        p2 = vs_match.group(2).strip().split()[-1]
        lines.append(f"{p1} VS {p2}".upper())
        lines.append('HEATED SHOWDOWN')
    else:
        # Split cleanly by words, max 2 lines, max 18 chars per line
        words = [w for w in t.split() if w.lower() not in ['watch', 'the', 'and', 'at', 'in', 'on', 'of', 'for']]
        if len(words) <= 3:
            lines = [' '.join(words).upper()]
        elif len(words) <= 6:
            mid = len(words) // 2
            lines = [' '.join(words[:mid]).upper(), ' '.join(words[mid:]).upper()]
        else:
            lines = [' '.join(words[:3]).upper(), ' '.join(words[3:6]).upper()]

    # Clean punctuation debris
    clean_lines = [re.sub(r'^[-\s,:]+|[-\s,:]+$', '', l).strip() for l in lines if l.strip()]
    return clean_lines[:2]

def generate_seo_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    raw_title = candidate.get("title", "")
    topic = candidate.get("search_topic", "")
    yid = candidate.get("id", "")

    rumble_title = format_rumble_title(raw_title, topic)

    # Dynamic keyword optimization tailored for high Rumble CTR
    low_title = raw_title.lower()
    tag_set = [
        "bitcoin", "crypto", "breaking news", "finance", "economy",
        "sound money", "inflation", "market crash", "rumble viral", "2026"
    ]
    if "gold" in low_title or "silver" in low_title or "dollar" in low_title:
        tag_set.extend(["gold", "silver", "dollar collapse", "federal reserve", "brics", "precious metals", "wealth protection"])
    elif "senate" in low_title or "congress" in low_title or "hearing" in low_title or "grilling" in low_title:
        tag_set.extend(["senate hearing", "congressional hearing", "cspan", "grilling", "heated debate", "oversight", "government"])
    elif "saylor" in low_title or "microstrategy" in low_title:
        tag_set.extend(["michael saylor", "microstrategy", "msci", "bitcoin bull run", "btc target", "institutional bitcoin"])
    else:
        tag_set.extend(["cryptocurrency", "altcoins", "coinbase", "sec", "monetary policy", "central banks"])

    tags = ", ".join(dict.fromkeys(tag_set))

    # Rich description with SEO keywords
    description = (
        f"{rumble_title}\n\n"
        "🔥 Essential market update, breaking macroeconomic analysis, and critical insights into sound money, "
        "Federal Reserve policy, currency debasement, and the digital financial revolution.\n\n"
        "📌 Key Themes Covered:\n"
        "• Institutional market dynamics & high-volume liquidations\n"
        "• Fiat currency debasement vs Bitcoin & hard assets\n"
        "• Government regulatory shifts, committee hearings & monetary reform\n\n"
        f"Original archive reference: https://www.youtube.com/watch?v={yid}\n"
        "Published for educational commentary, journalistic documentation, and public interest review.\n\n"
        "#bitcoin #crypto #marketcrash #michaelsaylor #gold #inflation #federalreserve #soundmoney #finance #rumble"
    )

    # Extract punchy 2-line viral headline
    headline = extract_viral_headline(raw_title)

    badge = "UNCUT TESTIMONY"
    if "vs" in raw_title.lower() or "clash" in raw_title.lower():
        badge = "HISTORIC CLASH"
    elif "grilling" in raw_title.lower():
        badge = "HEATED GRILLING"
    elif "senate" in raw_title.lower():
        badge = "SENATE HEARING"
    elif "congress" in raw_title.lower():
        badge = "CONGRESSIONAL HEARING"
    elif "gold" in raw_title.lower() or "money" in raw_title.lower():
        badge = "SOUND MONEY"
    elif "dollar" in raw_title.lower() or "collapse" in raw_title.lower():
        badge = "ECONOMIC WARNING"

    return {
        "title": rumble_title,
        "description": description,
        "tags": tags,
        "badge": badge,
        "headline_lines": headline
    }

if __name__ == "__main__":
    sample = {
        "id": "2NJnL10vZ1Y",
        "title": "Ron Paul vs Bernanke: Is Gold Money? - July 13, 2011",
        "search_topic": "ron paul federal reserve hearing is gold money"
    }
    meta = generate_seo_metadata(sample)
    print("Title:", meta["title"])
    print("Badge:", meta["badge"])
    print("Headline:", meta["headline_lines"])
