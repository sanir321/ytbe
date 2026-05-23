"""Telegram notification — sends pipeline status messages via bot."""

import logging
from typing import Optional

import requests

from config.settings import Settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, settings: Settings) -> None:
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.enabled = bool(self.token and self.chat_id)

    def send(self, message: str) -> None:
        if not self.enabled:
            logger.debug("Telegram not configured — skipping notification")
            return
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            logger.info("Telegram notification sent")
        except Exception as e:
            logger.warning("Telegram notification failed: %s", e)

    def on_upload(self, title: str, video_id: str) -> None:
        self.send(
            f"<b>✅ Uploaded</b>\n"
            f"{title}\n"
            f"<a href='https://youtu.be/{video_id}'>https://youtu.be/{video_id}</a>"
        )

    def on_error(self, stage: str, shortcode: str, error: str) -> None:
        self.send(
            f"<b>❌ Pipeline Error</b>\n"
            f"Stage: {stage}\n"
            f"Reel: {shortcode}\n"
            f"Error: {error[:500]}"
        )

    def on_skip(self, reason: str) -> None:
        self.send(f"<b>⏭️ Skipped</b>\n{reason}")
