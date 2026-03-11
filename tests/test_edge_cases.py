"""Edge case tests: HTTP errors, broken data, status transitions."""

from __future__ import annotations

import pytest

from heygen_mcp.api_client import (
    Character,
    VideoGenerateRequest,
    VideoInput,
    Voice,
)


def _make_simple_request() -> VideoGenerateRequest:
    return VideoGenerateRequest(
        video_inputs=[
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Hello", voice_id="voice_001"),
            )
        ],
    )


# ── HTTP Errors ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_401_unauthorized(mock_state, mock_server, api_client):
    """Bad API key → error with '401'."""
    mock_state.force_http_error = 401
    result = await api_client.get_remaining_credits()
    assert result.error is not None
    assert "401" in result.error


@pytest.mark.asyncio
async def test_429_rate_limited(mock_state, mock_server, api_client):
    """Rate limit → error with '429'."""
    mock_state.force_http_error = 429
    result = await api_client.get_voices()
    assert result.error is not None
    assert "429" in result.error


@pytest.mark.asyncio
async def test_500_server_error(mock_state, mock_server, api_client):
    """Server error → error with '500'."""
    mock_state.force_http_error = 500
    result = await api_client.list_avatar_groups()
    assert result.error is not None
    assert "500" in result.error


# ── Broken Voice Previews ────────────────────────────────


@pytest.mark.asyncio
async def test_s3_url_voice(mock_state, mock_server, api_client):
    """s3:// URL preserved as string."""
    mock_state.voices = [{
        "voice_id": "v_s3",
        "name": "S3 Voice",
        "language": "en",
        "gender": "male",
        "preview_audio": "s3://heygen-bucket/audio.mp3",
    }]
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices is not None
    assert result.voices[0].preview_audio == "s3://heygen-bucket/audio.mp3"


@pytest.mark.asyncio
async def test_relative_path_voice(mock_state, mock_server, api_client):
    """Relative path preserved."""
    mock_state.voices = [{
        "voice_id": "v_rel",
        "name": "Rel Voice",
        "language": "en",
        "gender": "female",
        "preview_audio": "audio/preview.mp3",
    }]
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices[0].preview_audio == "audio/preview.mp3"


@pytest.mark.asyncio
async def test_null_preview_voice(mock_state, mock_server, api_client):
    """None preview → no crash."""
    mock_state.voices = [{
        "voice_id": "v_null",
        "name": "Null Voice",
        "language": "en",
        "gender": "male",
        "preview_audio": None,
    }]
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices[0].preview_audio is None


@pytest.mark.asyncio
async def test_empty_string_preview(mock_state, mock_server, api_client):
    """Empty string preview → no crash."""
    mock_state.voices = [{
        "voice_id": "v_empty",
        "name": "Empty Voice",
        "language": "en",
        "gender": "male",
        "preview_audio": "",
    }]
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices[0].preview_audio == ""


# ── Video Edge Cases ─────────────────────────────────────


@pytest.mark.asyncio
async def test_multi_scene_video(mock_state, mock_server, api_client):
    """2 video_inputs → both stored."""
    request = VideoGenerateRequest(
        video_inputs=[
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Scene one", voice_id="voice_001"),
            ),
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Scene two", voice_id="voice_002"),
            ),
        ],
    )
    result = await api_client.generate_avatar_video(request)
    assert result.error is None
    assert result.video_id is not None

    # Verify mock stored both inputs
    job = mock_state.video_jobs[result.video_id]
    assert len(job["request"]["video_inputs"]) == 2


@pytest.mark.asyncio
async def test_status_progression(mock_state, mock_server, api_client):
    """waiting→pending→processing→completed."""
    gen_result = await api_client.generate_avatar_video(_make_simple_request())
    vid = gen_result.video_id

    for status in ["waiting", "pending", "processing", "completed"]:
        mock_state.video_jobs[vid]["status"] = status
        if status == "completed":
            mock_state.video_jobs[vid]["video_url"] = "https://cdn.heygen.com/v.mp4"
            mock_state.video_jobs[vid]["duration"] = 10.0

        result = await api_client.get_video_status(vid)
        assert result.status == status


@pytest.mark.asyncio
async def test_status_failed_with_error(mock_state, mock_server, api_client):
    """Failed job → error details."""
    gen_result = await api_client.generate_avatar_video(_make_simple_request())
    vid = gen_result.video_id

    mock_state.video_jobs[vid]["status"] = "failed"
    mock_state.video_jobs[vid]["error"] = {
        "code": 1001,
        "message": "Rendering failed",
        "detail": "GPU out of memory",
    }

    result = await api_client.get_video_status(vid)
    assert result.status == "failed"
    assert result.error_details is not None
    assert result.error_details["message"] == "Rendering failed"


@pytest.mark.asyncio
async def test_concurrent_video_jobs(mock_state, mock_server, api_client):
    """Multiple jobs don't interfere."""
    r1 = await api_client.generate_avatar_video(_make_simple_request())
    r2 = await api_client.generate_avatar_video(_make_simple_request())

    assert r1.video_id != r2.video_id

    # Complete one, leave other waiting
    mock_state.video_jobs[r1.video_id]["status"] = "completed"
    mock_state.video_jobs[r1.video_id]["video_url"] = "https://cdn.heygen.com/v1.mp4"

    s1 = await api_client.get_video_status(r1.video_id)
    s2 = await api_client.get_video_status(r2.video_id)

    assert s1.status == "completed"
    assert s2.status == "waiting"
