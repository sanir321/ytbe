"""AI caption generator using Kilo Gateway (OpenAI-compatible → Gemini 2.0 Flash)."""

import json
import logging
from typing import Optional

from openai import OpenAI, APIError, APITimeoutError

from config.settings import Settings

logger = logging.getLogger(__name__)

GENERATION_MODEL = "openrouter/free"
MAX_TOKENS = 2000

SYSTEM_PROMPT = (
    "You are a YouTube Shorts growth expert for men's self-improvement content. "
    "Always respond in valid JSON only. No markdown, no code fences. "
    "Just raw JSON with keys: title, description, hashtags."
)

USER_PROMPT_TEMPLATE = """Given this Instagram caption: "{caption}"

Generate YouTube metadata for a men's motivation/self-improvement Short.

Return ONLY valid JSON (no markdown, no code fences) with exactly these keys:
{{
  "title": "max 58 chars, punchy, 1 emoji, ends with #Shorts",
  "description": "150-200 words, value-first, masculine tone, CTA at end like 'Follow for more'. Append all hashtags at the bottom.",
  "hashtags": ["#Shorts", "#motivation", ... 30 total]
}}"""


class CaptionGeneratorError(Exception):
    """Base exception for caption generation failures."""


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
                )

                raw = resp.choices[0].message.content
                # Reasoning models sometimes put content in reasoning field instead
                if not raw:
                    reasoning = getattr(resp.choices[0].message, "reasoning", None)
                    if reasoning:
                        logger.info("Reasoning model used content=None, skipping (%d reasoning chars)", len(reasoning))
                        # Don't try to parse reasoning — it's chain-of-thought, not output
                    continue

                # Fix common LLM JSON issues
                raw = raw.strip()

                # Strip markdown code fences (```json ... ```)
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1] if "\n" in raw else raw
                if raw.endswith("```"):
                    idx = raw.rfind("```")
                    raw = raw[:idx]
                raw = raw.strip()

                # Try parsing; if it fails, apply progressive fixes
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    # Fix trailing commas in objects and arrays
                    raw = raw.replace(",\n}", "\n}").replace(",}", "}")
                    raw = raw.replace(",\n]", "\n]").replace(",]", "]")
                    # Remove newlines inside strings (common issue)
                    # Try single quotes → double quotes
                    raw = raw.replace("'", '"')
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        # Last resort: manually extract fields
                        data = self._extract_json_fallback(raw)
                # Normalize hashtags: handle list, comma-separated, or space-separated string
                if isinstance(data.get("hashtags"), str):
                    # Try comma first, fall back to spaces
                    if "," in data["hashtags"]:
                        data["hashtags"] = [
                            h.strip() for h in data["hashtags"].split(",") if h.strip()
                        ]
                    else:
                        data["hashtags"] = [
                            h.strip() for h in data["hashtags"].split() if h.strip()
                        ]
                # Ensure all hashtags start with #
                data["hashtags"] = [
                    f"#{h.lstrip('#')}" if not h.startswith("#") else h
                    for h in data.get("hashtags", [])
                ]

                # Validate structure
                if not all(k in data for k in ("title", "description", "hashtags")):
                    logger.warning(
                        "Missing keys in response (attempt %d): %s",
                        attempt + 1,
                        list(data.keys()),
                    )
                    continue

                # Ensure #Shorts is in the hashtags
                if "#Shorts" not in data["hashtags"]:
                    data["hashtags"].insert(0, "#Shorts")

                title = data["title"]
                if not title.endswith("#Shorts"):
                    title = title.rstrip() + " #Shorts"
                data["title"] = title[:100]

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
    def _extract_json_fallback(raw: str) -> dict:
        """Last-resort: extract title/description/hashtags via regex."""
        import re
        result = {"title": "", "description": "", "hashtags": []}

        # Extract title
        m = re.search(r'"title"\s*:\s*"([^"]+)"', raw)
        if m:
            result["title"] = m.group(1)

        # Extract description
        m = re.search(r'"description"\s*:\s*"([^"]+)"', raw)
        if m:
            result["description"] = m.group(1)

        # Extract hashtags as JSON array
        m = re.search(r'"hashtags"\s*:\s*(\[[^\]]+\])', raw)
        if m:
            array_str = m.group(1)
            try:
                result["hashtags"] = json.loads(array_str)
            except json.JSONDecodeError:
                # Try replacing single quotes with double quotes
                try:
                    result["hashtags"] = json.loads(array_str.replace("'", '"'))
                except json.JSONDecodeError:
                    # Extract individual quoted strings (handle both ' and ")
                    tags = re.findall(r'"([^"]+)"', array_str)
                    if not tags:
                        tags = re.findall(r"'([^']+)'", array_str)
                    result["hashtags"] = tags

        logger.info("Extracted via regex fallback: title=%s", bool(result["title"]))
        return result

    @staticmethod
    def fallback_metadata() -> dict:
        """Return hardcoded metadata when AI generation fails."""
        return {
            "title": "Mindset Shift That Changed Everything #Shorts",
            "description": (
                "Sometimes all it takes is a shift in perspective. "
                "This one mindset change can transform how you approach every "
                "challenge in your life.\n\n"
                "Focus on progress, not perfection. Every small step counts. "
                "Success is built on daily habits, not overnight transformations.\n\n"
                "Follow for more daily motivation and self-improvement content."
            ),
            "hashtags": [
                "#Shorts", "#motivation", "#mindset", "#selfimprovement",
                "#success", "#discipline", "#growth", "#mindsetmatters",
                "#dailyroutine", "#habits", "#focus", "#goals",
                "#inspiration", "#grind", "#successmindset",
            ],
        }
