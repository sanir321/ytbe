"""AI caption generator using Kilo Gateway (OpenAI-compatible -> Gemini 2.0 Flash)."""

import json
import logging
from typing import Optional

from openai import OpenAI, APIError, APITimeoutError

from config.settings import Settings

logger = logging.getLogger(__name__)

GENERATION_MODEL = "kilo-auto/free"
MAX_TOKENS = 2500

SYSTEM_PROMPT = (
    "You are a YouTube Shorts growth expert. You generate viral-optimized metadata "
    "for men's self-improvement content. Your responses must be in valid JSON only — "
    "no markdown, no code fences, no commentary. "
    "Always return raw JSON with exactly these keys: title, description, hashtags."
)

USER_PROMPT_TEMPLATE = """Given this Instagram caption: "{caption}"

Generate YouTube Shorts metadata optimized for growth, retention, and search discovery for a men's motivation / self-improvement channel.

## Title Rules
- Max 58 characters
- MUST be catchy, curiosity-driven, or emotion-triggering (e.g. "Stop Being the Nice Guy" not "Nice Guy Tips")
- Include exactly 1 relevant emoji at the end
- NO hashtags in the title
- Use power words: brutal, truth, secret, stopped, changed, never, real, raw, why

## Description Rules
- 180-250 words
- Structure:
  1. Hook sentence (bold claim or question)
  2. 2-3 value paragraphs expanding the idea
  3. CTA: "Follow for more" or "Subscribe for daily motivation"
- Keep masculine, direct, no fluff
- Append ALL hashtags at the bottom (space-separated, NOT comma-separated)
- Add 2-3 blank lines before hashtags section

## Hashtags Rules (CRITICAL)
- EXACTLY 30 hashtags in a JSON array
- #Shorts MUST be the FIRST element
- Mix of:
  - Broad categories: #motivation #mindset #selfimprovement
  - Niche specific: based on the caption topic
  - Growth tags: #viral #fyp #foryou #explore
  - Channel tags: #mensgrowth #stoicism #discipline
- No spaces inside tags, all lowercase except proper nouns
- Example: ["#Shorts", "#motivation", "#mindset", "#stoicism", "#masculinity", "#discipline", "#growth", "#success", "#grind", "#hustle", "#confidence", "#selfimprovement", "#mentality", "#wisdom", "#habits", "#fyp", "#viral", "#explore", "#foryou", "#sigma", "#sigmaMindset", "#mensGrowth", "#darkPsychology", "#psychology", "#stoic", "#ironMind", "#mindsetMatters", "#goals", "#focus", "#nomo"]

Return ONLY valid JSON (no markdown, no code fences) with exactly these keys:
{{
  "title": "catchy, curiosity-driven title with 1 emoji — no hashtags",
  "description": "full description with all hashtags appended at bottom",
  "hashtags": ["#Shorts", "(29 more specific hashtags)"]
}}"""


class CaptionGenerator:
    """Generates YouTube titles, descriptions, and hashtags via Kilo Gateway."""

    def __init__(self, settings: Settings) -> None:
        self.client = OpenAI(
            api_key=settings.kilo_api_key,
            base_url=settings.kilo_base_url,
        )

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
    def generate(self, ig_caption: str) -> Optional[dict]:
        """Generate YouTube metadata from an Instagram caption.

        Args:
            ig_caption: The original caption from Instagram.

        Returns:
            Dict with keys: title, description, hashtags (list).
            Returns None if all retries fail.
        """
        prompt = USER_PROMPT_TEMPLATE.format(caption=ig_caption[:1000])

        for attempt in range(3):
            try:
                resp = self.client.chat.completions.create(
                    model=GENERATION_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=MAX_TOKENS,
                    response_format={"type": "json_object"},
                )

                raw = resp.choices[0].message.content
                if not raw:
                    continue

                data = json.loads(raw.strip())
                # Ensure all hashtags start with #
                data["hashtags"] = [
                    f"#{h.lstrip('#')}" if not h.startswith("#") else h
                    for h in data.get("hashtags", [])
                ]

                # Validate structure and non-empty values
                if not all(k in data for k in ("title", "description", "hashtags")):
                    logger.warning(
                        "Missing keys in response (attempt %d): %s",
                        attempt + 1,
                        list(data.keys()),
                    )
                    continue
                if not data["title"] or not data["description"]:
                    logger.warning(
                        "Empty title or description (attempt %d)", attempt + 1
                    )
                    continue

                # Ensure #Shorts is in the hashtags
                if "#Shorts" not in data["hashtags"]:
                    data["hashtags"].insert(0, "#Shorts")

                # Append hashtags to description
                desc = data["description"]
                tag_str = "  ".join(data["hashtags"])
                if tag_str not in desc:
                    desc = desc.rstrip() + "\n\n" + tag_str
                data["description"] = desc[:5000]

                logger.info("Caption generated successfully")
                return data

            except json.JSONDecodeError as e:
                logger.warning(
                    "JSON parse error (attempt %d): %s", attempt + 1, e
                )
            except APITimeoutError:
                logger.warning(
                    "Kilo timeout (attempt %d), retrying...", attempt + 1
                )
            except APIError as e:
                logger.warning(
                    "Kilo API error (attempt %d): %s", attempt + 1, e
                )

        logger.error("All 3 attempts to generate caption failed")
        return None

    # ------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------
    @staticmethod
    def fallback_metadata() -> dict:
        return {
            "title": "Motivation \U0001f3af",
            "description": "Daily motivation. Follow for more.\n\n#Shorts  #motivation  #mindset",
            "hashtags": ["#Shorts", "#motivation", "#mindset"],
        }
