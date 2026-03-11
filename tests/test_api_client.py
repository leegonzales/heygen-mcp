"""API client regression tests against mock HeyGen server."""

from __future__ import annotations

import pytest

from heygen_mcp.api_client import (
    Character,
    Dimension,
    HeyGenApiClient,
    VideoGenerateRequest,
    VideoInput,
    Voice,
)
from tests.fixtures import (
    make_large_voice_list,
    make_voices_with_broken_previews,
)

# ── Credits ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_credits_with_plan_credit(mock_state, mock_server, api_client):
    """Current API format: only plan_credit in data."""
    mock_state.plan_credit = 500
    result = await api_client.get_remaining_credits()
    assert result.error is None
    assert result.remaining_credits == 500


@pytest.mark.asyncio
async def test_credits_minimal_response(mock_state, mock_server, api_client):
    """No remaining_quota or details — just plan_credit."""
    mock_state.plan_credit = 42
    result = await api_client.get_remaining_credits()
    assert result.error is None
    assert result.remaining_credits == 42


@pytest.mark.asyncio
async def test_credits_with_legacy_quota(mock_state, mock_server, api_client):
    """Old format with remaining_quota + details.plan_credit."""
    mock_state.plan_credit = None
    mock_state.credits = 300
    result = await api_client.get_remaining_credits()
    assert result.error is None
    assert result.remaining_credits == 300


@pytest.mark.asyncio
async def test_credits_empty_response(mock_server):
    """Empty data: {} — graceful handling."""
    # Override state to produce empty data
    mock_server.state.plan_credit = None
    mock_server.state.credits = 0
    client = HeyGenApiClient("test-key", base_url=mock_server.base_url)
    result = await client.get_remaining_credits()
    # Should not crash; credits should be 0
    assert result.error is None or result.remaining_credits == 0


# ── Voices ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voices_with_broken_previews(mock_state, mock_server, api_client):
    """s3://, relative, null, empty previews — no crash."""
    mock_state.voices = make_voices_with_broken_previews()
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices is not None
    assert len(result.voices) == 5


@pytest.mark.asyncio
async def test_voices_truncation(mock_state, mock_server, api_client):
    """1200 voices → only 100 returned."""
    mock_state.voices = make_large_voice_list(1200)
    result = await api_client.get_voices()
    assert result.error is None
    assert result.voices is not None
    assert len(result.voices) == 100


@pytest.mark.asyncio
async def test_voices_empty(mock_state, mock_server, api_client):
    """No voices available."""
    mock_state.voices = []
    result = await api_client.get_voices()
    assert result.error is None or result.voices == []


# ── Avatar Groups ────────────────────────────────────────


@pytest.mark.asyncio
async def test_private_groups_only(mock_server, api_client):
    """include_public=false filters correctly."""
    result = await api_client.list_avatar_groups(include_public=False)
    assert result.error is None
    assert result.avatar_groups is not None
    group_types = [g.group_type for g in result.avatar_groups]
    assert "public" not in group_types
    assert result.total_count == 1


@pytest.mark.asyncio
async def test_include_public_groups(mock_server, api_client):
    """Both private + public returned."""
    result = await api_client.list_avatar_groups(include_public=True)
    assert result.error is None
    assert result.avatar_groups is not None
    assert result.total_count == 2


# ── Avatars in Group ─────────────────────────────────────


@pytest.mark.asyncio
async def test_avatars_found(mock_server, api_client):
    """Known group → avatars returned."""
    result = await api_client.get_avatars_in_group("grp_private")
    assert result.error is None
    assert result.avatars is not None
    assert len(result.avatars) == 1
    assert result.avatars[0].avatar_name == "Lee Gonzales"


@pytest.mark.asyncio
async def test_avatars_not_found(mock_server, api_client):
    """Unknown group → empty list."""
    result = await api_client.get_avatars_in_group("nonexistent_group")
    assert result.error is None
    assert result.avatars is not None
    assert len(result.avatars) == 0


# ── Video Generation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_video(mock_server, api_client):
    """Happy path → video_id returned."""
    request = VideoGenerateRequest(
        title="Test Video",
        video_inputs=[
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Hello world", voice_id="voice_001"),
            )
        ],
        dimension=Dimension(width=1280, height=720),
    )
    result = await api_client.generate_avatar_video(request)
    assert result.error is None
    assert result.video_id is not None
    assert result.video_id.startswith("vid_")


@pytest.mark.asyncio
async def test_status_waiting(mock_state, mock_server, api_client):
    """Generate then poll → 'waiting'."""
    request = VideoGenerateRequest(
        video_inputs=[
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Test", voice_id="voice_001"),
            )
        ],
    )
    gen_result = await api_client.generate_avatar_video(request)
    assert gen_result.video_id is not None

    status_result = await api_client.get_video_status(gen_result.video_id)
    assert status_result.error is None or status_result.error_details is None
    assert status_result.status == "waiting"


@pytest.mark.asyncio
async def test_status_completed(mock_state, mock_server, api_client):
    """Completed job → video_url + duration."""
    request = VideoGenerateRequest(
        video_inputs=[
            VideoInput(
                character=Character(avatar_id="lee_avatar"),
                voice=Voice(input_text="Test", voice_id="voice_001"),
            )
        ],
    )
    gen_result = await api_client.generate_avatar_video(request)
    video_id = gen_result.video_id

    # Mutate mock state to simulate completion
    mock_state.video_jobs[video_id]["status"] = "completed"
    mock_state.video_jobs[video_id]["video_url"] = "https://cdn.heygen.com/out.mp4"
    mock_state.video_jobs[video_id]["duration"] = 12.5

    status_result = await api_client.get_video_status(video_id)
    assert status_result.status == "completed"
    assert status_result.video_url == "https://cdn.heygen.com/out.mp4"
    assert status_result.duration == 12.5


@pytest.mark.asyncio
async def test_status_not_found(mock_server, api_client):
    """Unknown video_id → failed."""
    result = await api_client.get_video_status("nonexistent_video")
    assert result.status == "failed"
    assert result.error_details is not None
