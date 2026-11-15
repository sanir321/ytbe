#!/usr/bin/env python3
"""
Rumble SEO & Metadata Generator for Financial/Crypto Content
Optimized for high CTR with Rumble's core 35-65 demographic.
"""

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
        "inflation": "[MONETARY TRUTH]",
        "speech": "[UNCUT SPEECH]"
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

def generate_seo_metadata(candidate: Dict[str, Any]) -> Dict[str, Any]:
    raw_title = candidate.get("title", "")
    topic = candidate.get("search_topic", "")
    yid = candidate.get("id", "")

    rumble_title = format_rumble_title(raw_title, topic)

    description = (
        f"{rumble_title}\n\n"
        "Official uncut testimony and historic financial debate investigating sound money, "
        "Federal Reserve currency expansion, public ledgers, and economic sovereignty.\n\n"
        "📌 Key Themes:\n"
        "• The integrity of fiat currency vs sound money\n"
        "• Government oversight, monetary policy, and inflation\n"
        "• Bitcoin, decentralized finance, and the future of value\n\n"
        f"Original archive reference: {yid}\n"
        "US Government proceedings and public debates are published under public domain / fair informative review.\n\n"
        "#bitcoin #crypto #finance #banking #soundmoney #federalreserve #inflation #rumble #gold"
    )

    tags = "bitcoin, crypto, cryptocurrency, finance, banking, sound money, federal reserve, inflation, money, gold, rumble, btc, economics"

    # Extract headline lines for thumbnail
    words = raw_title.split()
    if len(words) <= 4:
        headline = [raw_title.upper()]
    elif len(words) <= 8:
        mid = len(words) // 2
        headline = [" ".join(words[:mid]).upper(), " ".join(words[mid:]).upper()]
    else:
        headline = [
            " ".join(words[:3]).upper(),
            " ".join(words[3:7]).upper(),
            " ".join(words[7:10]).upper() if len(words) > 7 else ""
        ]
    headline = [h for h in headline if h]

    return {
        "title": rumble_title,
        "description": description,
        "tags": tags,
        "badge": "UNCUT TESTIMONY" if "hearing" in raw_title.lower() else "HISTORIC CLASH",
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
