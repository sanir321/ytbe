#!/usr/bin/env python3
"""Tests for modules/yt_uploader.py - YouTube OAuth, upload, and token refresh."""
import json
import pytest
from pathlib import Path
from modules.yt_uploader import YTUploader
from config.settings import PipelineError


@pytest.fixture
def settings(mocker):
    s = mocker.Mock()
    s.yt_refresh_token = "test_refresh_token"
    s.yt_client_id = "test_client_id"
    s.yt_client_secret = "test_client_secret"
    return s


@pytest.fixture
def mock_credentials(mocker):
    """Mock google.oauth2.credentials.Credentials."""
    return mocker.patch("modules.yt_uploader.Credentials")


@pytest.fixture
def mock_request(mocker):
    """Mock google.auth.transport.requests.Request."""
    return mocker.patch("modules.yt_uploader.Request")


@pytest.fixture
def mock_build(mocker):
    """Mock googleapiclient.discovery.build."""
    return mocker.patch("modules.yt_uploader.build")


class TestCredentials:
    def test_refresh_token_success(self, settings, mock_credentials, mock_request):
        """Successful token refresh should set valid credentials."""
        creds_instance = mock_credentials.return_value
        creds_instance.valid = False
        creds_instance.refresh.return_value = None

        uploader = YTUploader(settings)
        result = uploader._get_credentials()

        assert result is creds_instance
        creds_instance.refresh.assert_called_once()
        assert uploader._credentials is creds_instance

    def test_uses_cached_credentials(self, settings, mock_credentials):
        """Valid cached credentials should skip refresh."""
        creds_instance = mock_credentials.return_value
        creds_instance.valid = True

        uploader = YTUploader(settings)
        uploader._credentials = creds_instance
        result = uploader._get_credentials()

        assert result is creds_instance
        # refresh should not be called again
        assert creds_instance.refresh.call_count == 0

    def test_refresh_failure_raises(self, settings, mock_credentials, mock_request):
        """Failed token refresh should raise PipelineError."""
        from google.auth.exceptions import RefreshError
        creds_instance = mock_credentials.return_value
        creds_instance.valid = False
        creds_instance.refresh.side_effect = RefreshError("token expired")

        uploader = YTUploader(settings)
        with pytest.raises(PipelineError, match="YouTube token refresh failed"):
            uploader._get_credentials()

    def test_credentials_constructed_correctly(self, settings, mock_credentials, mock_request):
        """Verify Credentials() is called with the right args."""
        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        uploader._get_credentials()

        mock_credentials.assert_called_once_with(
            token=None,
            refresh_token="test_refresh_token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )


class TestUploadShorts:
    def test_upload_success(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Successful upload returns a video ID."""
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")

        mock_service = mocker.Mock()
        mock_build = mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_request_obj = mocker.Mock()
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.return_value = (None, {"id": "fake_video_id_123"})

        mock_service.videos.return_value = mock_request_obj
        mock_request_obj.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        video_id = uploader.upload_shorts(
            video_path=video_path,
            title="Test Title #Shorts",
            description="Test description\n\n#Shorts  #motivation",
            tags=["#Shorts", "#motivation"],
            privacy="public",
        )

        assert video_id == "fake_video_id_123"
        mock_build.assert_called_once()
        mock_insert.next_chunk.assert_called_once()

    def test_upload_builds_correct_body(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Verify the request body has correct structure."""
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake video content")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid1"})
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        uploader.upload_shorts(
            video_path=video_path,
            title="My Title #Shorts",
            description="My description\n\n#Shorts  #motivation",
            tags=["#Shorts", "#motivation"],
            privacy="public",
        )

        call_body = mock_service.videos.return_value.insert.call_args[1]
        assert call_body["part"] == "snippet,status"
        assert call_body["body"]["snippet"]["title"] == "My Title #Shorts"
        assert call_body["body"]["snippet"]["categoryId"] == "22"
        assert call_body["body"]["status"]["privacyStatus"] == "public"
        assert call_body["body"]["status"]["selfDeclaredMadeForKids"] is False
        assert call_body["body"]["snippet"]["tags"] == ["#Shorts", "#motivation"]

    def test_upload_file_not_found(self, settings, mock_credentials):
        """Missing video file should raise immediately."""
        uploader = YTUploader(settings)
        with pytest.raises(PipelineError, match="Video file not found"):
            uploader.upload_shorts(
                video_path=Path("/nonexistent/video.mp4"),
                title="Test #Shorts",
                description="Desc",
                tags=["#Shorts"],
            )

    def test_upload_truncates_long_fields(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Title > 100 chars and description > 5000 chars should be truncated."""
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid1"})
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        uploader.upload_shorts(
            video_path=video_path,
            title="X" * 200 + " #Shorts",
            description="Y" * 10000,
            tags=["#Shorts"],
        )

        call_body = mock_service.videos.return_value.insert.call_args[1]
        assert len(call_body["body"]["snippet"]["title"]) <= 100
        assert len(call_body["body"]["snippet"]["description"]) <= 5000

    def test_upload_quota_exceeded(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Quota exceeded should raise with specific message."""
        from googleapiclient.errors import HttpError
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.side_effect = HttpError(
            resp=mocker.Mock(status=403),
            content=json.dumps({
                "error": {"errors": [{"reason": "quotaExceeded"}]}
            }).encode(),
        )
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        with pytest.raises(PipelineError, match="YouTube quota exceeded"):
            uploader.upload_shorts(
                video_path=video_path,
                title="Test #Shorts",
                description="Desc",
                tags=["#Shorts"],
            )

    def test_upload_auth_error(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Auth error should clear cached credentials and raise."""
        from googleapiclient.errors import HttpError
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.side_effect = HttpError(
            resp=mocker.Mock(status=401),
            content=json.dumps({
                "error": {"errors": [{"reason": "authError"}]}
            }).encode(),
        )
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        uploader._credentials = creds_instance

        with pytest.raises(PipelineError, match="YouTube auth error"):
            uploader.upload_shorts(
                video_path=video_path,
                title="Test #Shorts",
                description="Desc",
                tags=["#Shorts"],
            )

        assert uploader._credentials is None

    def test_upload_no_video_id_in_response(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Response without 'id' should return None."""
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.return_value = (None, {})  # No 'id' key
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        result = uploader.upload_shorts(
            video_path=video_path,
            title="Test #Shorts",
            description="Desc",
            tags=["#Shorts"],
        )
        assert result is None

    def test_upload_http_error_unknown_reason(self, settings, mocker, tmp_path, mock_credentials, mock_request):
        """Unknown HTTP error reason should not match specific handlers."""
        from googleapiclient.errors import HttpError
        video_path = tmp_path / "test_video.mp4"
        video_path.write_bytes(b"fake")

        mock_service = mocker.Mock()
        mocker.patch("modules.yt_uploader.build", return_value=mock_service)
        mock_insert = mocker.Mock()
        mock_insert.next_chunk.side_effect = HttpError(
            resp=mocker.Mock(status=400),
            content=json.dumps({
                "error": {"errors": [{"reason": "videoTooLarge"}]}
            }).encode(),
        )
        mock_service.videos.return_value.insert.return_value = mock_insert

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        with pytest.raises(PipelineError, match="YouTube API error: videoTooLarge"):
            uploader.upload_shorts(
                video_path=video_path,
                title="Test #Shorts",
                description="Desc",
                tags=["#Shorts"],
            )


class TestGetService:
    def test_service_is_cached(self, settings, mocker, mock_credentials, mock_request):
        """Multiple calls should reuse the same service object."""
        mock_service = mocker.Mock()
        mock_build = mocker.patch("modules.yt_uploader.build", return_value=mock_service)

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        svc1 = uploader._get_service()
        svc2 = uploader._get_service()

        assert svc1 is svc2
        assert mock_build.call_count == 1

    def test_service_rebuilt_after_auth_failure(self, settings, mocker, mock_credentials, mock_request):
        """After credentials are cleared, service should be rebuilt."""
        mock_service = mocker.Mock()
        mock_build = mocker.patch("modules.yt_uploader.build", return_value=mock_service)

        creds_instance = mock_credentials.return_value
        creds_instance.valid = False

        uploader = YTUploader(settings)
        svc1 = uploader._get_service()
        assert svc1 is mock_service

        # Simulate auth failure clearing credentials
        uploader._credentials = None
        uploader._service = None

        svc2 = uploader._get_service()
        assert svc2 is mock_service
        assert mock_build.call_count == 2
