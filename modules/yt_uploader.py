"""YouTube uploader — handles OAuth, upload, and token refresh."""

import json
import logging
import os
import pickle
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config.settings import Settings

logger = logging.getLogger(__name__)

YT_API_SERVICE_NAME = "youtube"
YT_API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# YouTube category IDs
CATEGORY_SELF_IMPROVEMENT = "22"  # People & Blogs


class YTUploaderError(Exception):
    """Base exception for YouTube upload failures."""


class YTUploader:
    """Uploads videos to YouTube with Shorts metadata and token management."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._credentials: Optional[Credentials] = None
        self._service = None

    # ------------------------------------------------------------------
    # OAuth / Token management
    # ------------------------------------------------------------------
    def _get_credentials(self) -> Credentials:
        """Build credentials from client secret + refresh token."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        creds = Credentials(
            token=None,
            refresh_token=self.settings.yt_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.yt_client_id,
            client_secret=self.settings.yt_client_secret,
            scopes=SCOPES,
        )

        # Refresh to get a valid access token
        try:
            creds.refresh(Request())
            self._credentials = creds
            logger.info("YouTube token refreshed successfully")
            return creds
        except RefreshError as e:
            raise YTUploaderError(
                f"YouTube token refresh failed: {e}. Re-run yt_oauth_setup.py."
            ) from e

    def _get_service(self):
        """Get or create the YouTube API service object."""
        if self._service is None:
            creds = self._get_credentials()
            self._service = build(YT_API_SERVICE_NAME, YT_API_VERSION, credentials=creds)
        return self._service

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def upload_shorts(
        self,
        video_path: str | Path,
        title: str,
        description: str,
        tags: list[str],
        *,
        privacy: str = "public",
    ) -> Optional[str]:
        """Upload a video as a YouTube Short.

        Args:
            video_path: Path to the processed .mp4.
            title: Video title (should end with #Shorts).
            description: Video description.
            tags: List of hashtag strings.
            privacy: 'unlisted' or 'public'.

        Returns:
            YouTube video ID if successful, None otherwise.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise YTUploaderError(f"Video file not found: {video_path}")

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags[:30],
                "categoryId": CATEGORY_SELF_IMPROVEMENT,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            chunksize=4 * 1024 * 1024,  # 4 MB chunks
            resumable=True,
        )

        try:
            service = self._get_service()
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = request.execute()
            video_id = response.get("id")

            if video_id:
                logger.info(
                    "Uploaded: %s → https://youtu.be/%s (privacy: %s)",
                    title,
                    video_id,
                    privacy,
                )
                return video_id
            else:
                logger.error("Upload succeeded but no video ID returned")
                return None

        except HttpError as e:
            error = json.loads(e.content.decode())
            reason = (
                error.get("error", {}).get("errors", [{}])[0]
                .get("reason", "unknown")
            )
            logger.error("YouTube upload failed: %s — %s", reason, e)

            if reason == "quotaExceeded":
                raise YTUploaderError("YouTube quota exceeded for today") from e
            if reason == "authError":
                # Force re-auth next time
                self._credentials = None
                raise YTUploaderError("YouTube auth error, will retry") from e

            raise YTUploaderError(f"YouTube API error: {reason}") from e

        except Exception as e:
            logger.error("Unexpected upload error: %s", e)
            raise YTUploaderError(str(e)) from e

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def make_public(self, video_id: str) -> bool:
        """Change a video's privacy from unlisted to public."""
        try:
            service = self._get_service()
            service.videos().update(
                part="status",
                body={
                    "id": video_id,
                    "status": {"privacyStatus": "public"},
                },
            ).execute()
            logger.info("Video %s set to public", video_id)
            return True
        except Exception as e:
            logger.error("Failed to set video public: %s", e)
            return False
