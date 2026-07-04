"""YouTube uploader - handles OAuth, upload, and token refresh."""

import json
import logging
from pathlib import Path
from typing import Optional

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from config.settings import Settings, PipelineError

logger = logging.getLogger(__name__)

YT_API_SERVICE_NAME = "youtube"
YT_API_VERSION = "v3"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

CATEGORY_SELF_IMPROVEMENT = "22"


class YTUploader:
    """Uploads videos to YouTube with Shorts metadata and token management."""

    def __init__(self, settings: Settings, channel: int = 1) -> None:
        self.settings = settings
        self.channel = channel
        self._credentials: Optional[Credentials] = None
        self._service = None

    # ------------------------------------------------------------------
    # OAuth / Token management
    # ------------------------------------------------------------------
    def _get_credentials(self) -> Credentials:
        """Build credentials from client secret + refresh token."""
        if self._credentials and self._credentials.valid:
            return self._credentials

        if self.channel == 2:
            if not self.settings.yt2_refresh_token:
                raise PipelineError("Channel 2 is not configured (missing YT2_* env vars)")
            client_id = self.settings.yt2_client_id
            client_secret = self.settings.yt2_client_secret
            refresh_token = self.settings.yt2_refresh_token
        else:
            client_id = self.settings.yt_client_id
            client_secret = self.settings.yt_client_secret
            refresh_token = self.settings.yt_refresh_token

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )

        # Refresh to get a valid access token
        try:
            creds.refresh(Request())
            self._credentials = creds
            logger.info("YouTube token refreshed successfully")
            return creds
        except RefreshError as e:
            raise PipelineError(
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
        progress_callback=None,
    ) -> Optional[str]:
        """Upload a video as a YouTube Short.

        Args:
            video_path: Path to the processed .mp4.
            title: Video title (should end with #Shorts).
            description: Video description.
            tags: List of hashtag strings.
            privacy: 'unlisted' or 'public'.
            progress_callback: Optional fn(bytes_sent, total_bytes).

        Returns:
            YouTube video ID if successful, None otherwise.
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise PipelineError(f"Video file not found: {video_path}")

        total_bytes = video_path.stat().st_size

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
            chunksize=4 * 1024 * 1024,
            resumable=True,
        )

        try:
            service = self._get_service()
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            logger.info("Starting upload: title=%r, file_size=%d", title, total_bytes)
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status and progress_callback:
                    progress_callback(status.resumable_progress, total_bytes)

            video_id = response.get("id")
            upload_status = response.get("status", {}).get("uploadStatus", "unknown")
            privacy_status = response.get("status", {}).get("privacyStatus", "unknown")

            if video_id:
                logger.info(
                    "Uploaded: title=%r -> https://youtu.be/%s "
                    "(uploadStatus=%s, privacy=%s)",
                    title,
                    video_id,
                    upload_status,
                    privacy_status,
                )
                if upload_status not in ("uploaded", "processed"):
                    logger.warning("Upload status unexpected: %s", upload_status)
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
            logger.error("YouTube upload failed: %s - %s", reason, e)

            if reason == "quotaExceeded":
                raise PipelineError("YouTube quota exceeded for today") from e
            if reason == "authError":
                self._credentials = None
                raise PipelineError("YouTube auth error, will retry") from e

            raise PipelineError(f"YouTube API error: {reason}") from e

        except Exception as e:
            logger.error("Unexpected upload error: %s", e)
            raise PipelineError(str(e)) from e


