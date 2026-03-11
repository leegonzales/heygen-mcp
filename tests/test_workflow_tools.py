"""Workflow MCP tool integration tests."""

from __future__ import annotations

import pytest

from heygen_mcp.workflow_tools import (
    check_inventory,
    create_video,
    get_video_status,
)
from tests.fixtures import make_avatar, make_voice

# ── check_inventory ──────────────────────────────────────


@pytest.mark.asyncio
async def test_inventory_joins_all(mock_state, mock_server, api_client):
    """Credits + voices + avatars in one response."""
    result = await check_inventory(api_client)
    assert result["credits"] == 200
    assert len(result["voices"]) == 2
    assert len(result["avatars"]) >= 1
    assert "capabilities" in result


@pytest.mark.asyncio
async def test_inventory_filters_broken_previews(
    mock_state, mock_server, api_client
):
    """Broken voices get hasPreview: false."""
    mock_state.voices = [
        make_voice(
            voice_id="v_ok",
            name="OK",
            preview_audio="https://cdn.heygen.com/ok.mp3",
        ),
        make_voice(
            voice_id="v_bad",
            name="Bad",
            preview_audio="s3://bucket/bad.mp3",
        ),
        make_voice(
            voice_id="v_none",
            name="None",
            preview_audio=None,
        ),
    ]
    result = await check_inventory(api_client)
    voice_map = {v["id"]: v for v in result["voices"]}
    assert voice_map["v_ok"]["hasPreview"] is True
    assert voice_map["v_bad"]["hasPreview"] is False
    assert voice_map["v_none"]["hasPreview"] is False


@pytest.mark.asyncio
async def test_inventory_empty(mock_state, mock_server, api_client):
    """Empty everything → zeros, empty lists."""
    mock_state.credits = 0
    mock_state.voices = []
    mock_state.avatar_groups = []
    mock_state.avatars_by_group = {}
    result = await check_inventory(api_client)
    assert result["credits"] == 0
    assert result["voices"] == []
    assert result["avatars"] == []


# ── create_video ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_by_exact_id(mock_state, mock_server, api_client):
    """avatar_id + voice_id → job handle."""
    result = await create_video(
        api_client,
        avatar="lee_avatar",
        voice="voice_001",
        script="Hello world!",
    )
    assert "error" not in result
    assert result["jobId"].startswith("vid_")
    assert result["status"] == "submitted"


@pytest.mark.asyncio
async def test_create_by_fuzzy_name(mock_state, mock_server, api_client):
    """"Lee" → resolves to "Lee Gonzales"."""
    result = await create_video(
        api_client,
        avatar="Lee",
        voice="Sarah",
        script="Testing fuzzy match",
    )
    assert "error" not in result
    assert result["jobId"].startswith("vid_")


@pytest.mark.asyncio
async def test_ambiguous_name_suggestions(
    mock_state, mock_server, api_client
):
    """2 "Lee" matches → error with suggestions."""
    mock_state.avatars_by_group["grp_private"] = [
        make_avatar(avatar_id="lee_1", avatar_name="Lee Gonzales"),
        make_avatar(avatar_id="lee_2", avatar_name="Lee Smith"),
    ]
    with pytest.raises(ValueError, match="Ambiguous"):
        await create_video(
            api_client,
            avatar="Lee",
            voice="voice_001",
            script="Ambiguous test",
        )


@pytest.mark.asyncio
async def test_create_with_full_config(mock_state, mock_server, api_client):
    """All optional params forwarded correctly."""
    result = await create_video(
        api_client,
        avatar="lee_avatar",
        voice="voice_001",
        script="Full config test",
        title="My Video",
        width=1920,
        height=1080,
        avatar_style="closeUp",
        emotion="Excited",
        voice_speed=1.2,
    )
    assert "error" not in result
    assert result["status"] == "submitted"


@pytest.mark.asyncio
async def test_create_transparent_bg(mock_state, mock_server, api_client):
    """background_type: 'transparent' handled."""
    result = await create_video(
        api_client,
        avatar="lee_avatar",
        voice="voice_001",
        script="Transparent background test",
        background_type="transparent",
    )
    assert "error" not in result


# ── get_video_status ─────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_processing(mock_state, mock_server, api_client):
    """Job in progress → status returned."""
    gen = await create_video(
        api_client,
        avatar="lee_avatar",
        voice="voice_001",
        script="Processing test",
    )
    vid = gen["jobId"]
    mock_state.video_jobs[vid]["status"] = "processing"

    result = await get_video_status(api_client, vid)
    assert result["status"] == "processing"
    assert result["videoUrl"] is None


@pytest.mark.asyncio
async def test_poll_completed(mock_state, mock_server, api_client):
    """Done job → video_url + duration."""
    gen = await create_video(
        api_client,
        avatar="lee_avatar",
        voice="voice_001",
        script="Completion test",
    )
    vid = gen["jobId"]
    mock_state.video_jobs[vid]["status"] = "completed"
    mock_state.video_jobs[vid]["video_url"] = "https://cdn.heygen.com/out.mp4"
    mock_state.video_jobs[vid]["duration"] = 15.0

    result = await get_video_status(api_client, vid)
    assert result["status"] == "completed"
    assert result["videoUrl"] == "https://cdn.heygen.com/out.mp4"
    assert result["duration"] == 15.0
