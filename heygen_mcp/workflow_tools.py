"""Workflow-oriented MCP tools for HeyGen.

Three high-level tools that compose the raw API calls:
  - check_inventory: credits + voices + avatars in one shot
  - create_video: smart name lookup + video generation
  - get_video_status: poll a job handle
"""

from __future__ import annotations

from typing import Any

from heygen_mcp.api_client import (
    Character,
    Dimension,
    HeyGenApiClient,
    VideoGenerateRequest,
    VideoInput,
    Voice,
)


async def check_inventory(client: HeyGenApiClient) -> dict[str, Any]:
    """Fetch credits, voices, and avatars in one call."""
    credits_resp = await client.get_remaining_credits()
    voices_resp = await client.get_voices()
    groups_resp = await client.list_avatar_groups(include_public=True)

    # Collect avatars from all groups
    avatars: list[dict[str, Any]] = []
    if groups_resp.avatar_groups:
        for group in groups_resp.avatar_groups:
            avs = await client.get_avatars_in_group(group.id)
            if avs.avatars:
                for av in avs.avatars:
                    avatars.append({
                        "id": av.avatar_id,
                        "name": av.avatar_name,
                        "group": group.name,
                        "previewImage": str(av.preview_image_url),
                        "previewVideo": str(av.preview_video_url),
                    })

    # Process voices — flag broken previews instead of dropping
    voice_list: list[dict[str, Any]] = []
    if voices_resp.voices:
        for v in voices_resp.voices:
            has_preview = bool(
                v.preview_audio
                and isinstance(v.preview_audio, str)
                and v.preview_audio.startswith("https://")
            )
            voice_list.append({
                "id": v.voice_id,
                "name": v.name,
                "language": v.language,
                "gender": v.gender,
                "hasPreview": has_preview,
                "supportsEmotion": v.emotion_support,
            })

    return {
        "credits": credits_resp.remaining_credits or 0,
        "avatars": avatars,
        "voices": voice_list,
        "capabilities": {
            "transparentBackground": True,
            "maxScenes": 10,
            "maxTextLength": 5000,
            "emotionOptions": [
                "Excited",
                "Friendly",
                "Serious",
                "Soothing",
                "Broadcaster",
            ],
        },
    }


async def create_video(
    client: HeyGenApiClient,
    avatar: str,
    voice: str,
    script: str,
    title: str = "",
    width: int = 1280,
    height: int = 720,
    avatar_style: str = "normal",
    emotion: str | None = None,
    voice_speed: float = 1.0,
    background_type: str = "color",
    background_value: str = "#000000",
) -> dict[str, Any]:
    """Create a video with smart avatar/voice name lookup.

    Accepts avatar and voice as either exact IDs or fuzzy name matches.
    """
    avatar_id = await _resolve_avatar(client, avatar)
    voice_id = await _resolve_voice(client, voice)

    voice_config: dict[str, Any] = {
        "type": "text",
        "input_text": script,
        "voice_id": voice_id,
        "speed": voice_speed,
    }
    if emotion:
        voice_config["emotion"] = emotion

    request = VideoGenerateRequest(
        title=title,
        video_inputs=[
            VideoInput(
                character=Character(
                    avatar_id=avatar_id,
                    avatar_style=avatar_style,
                ),
                voice=Voice(
                    input_text=script,
                    voice_id=voice_id,
                ),
            )
        ],
        dimension=Dimension(width=width, height=height),
    )

    result = await client.generate_avatar_video(request)
    if result.error:
        return {"error": result.error}

    return {
        "jobId": result.video_id,
        "status": "submitted",
        "estimatedWaitSeconds": 120,
    }


async def get_video_status(
    client: HeyGenApiClient,
    job_id: str,
) -> dict[str, Any]:
    """Poll video job status."""
    result = await client.get_video_status(job_id)
    if result.error:
        return {"error": result.error}

    return {
        "status": result.status,
        "videoUrl": result.video_url,
        "duration": result.duration,
        "thumbnailUrl": result.thumbnail_url,
        "error": (
            result.error_details.get("message")
            if result.error_details
            else None
        ),
    }


# ── Private helpers ──────────────────────────────────────


async def _resolve_avatar(
    client: HeyGenApiClient, avatar: str
) -> str:
    """Resolve avatar name or ID to an avatar_id."""
    # Try as direct ID first — check if it looks like an ID
    # (contains underscore or is not a plain name)
    inventory = await check_inventory(client)
    matches = [
        a for a in inventory["avatars"]
        if a["id"] == avatar
    ]
    if matches:
        return matches[0]["id"]

    # Fuzzy match by name (case-insensitive substring)
    query = avatar.lower()
    matches = [
        a for a in inventory["avatars"]
        if query in a["name"].lower()
    ]
    if len(matches) == 1:
        return matches[0]["id"]
    if len(matches) > 1:
        suggestions = [f"{m['name']} ({m['id']})" for m in matches]
        raise ValueError(
            f"Ambiguous avatar name '{avatar}'. "
            f"Did you mean: {', '.join(suggestions)}?"
        )

    raise ValueError(
        f"Avatar '{avatar}' not found. "
        f"Available: {[a['name'] for a in inventory['avatars']]}"
    )


async def _resolve_voice(
    client: HeyGenApiClient, voice: str
) -> str:
    """Resolve voice name or ID to a voice_id."""
    voices_resp = await client.get_voices()
    if not voices_resp.voices:
        raise ValueError("No voices available")

    # Try direct ID match
    for v in voices_resp.voices:
        if v.voice_id == voice:
            return v.voice_id

    # Fuzzy match by name
    query = voice.lower()
    matches = [v for v in voices_resp.voices if query in v.name.lower()]
    if len(matches) == 1:
        return matches[0].voice_id
    if len(matches) > 1:
        suggestions = [f"{m.name} ({m.voice_id})" for m in matches]
        raise ValueError(
            f"Ambiguous voice name '{voice}'. "
            f"Did you mean: {', '.join(suggestions)}?"
        )

    raise ValueError(
        f"Voice '{voice}' not found. "
        f"Available: {[v.name for v in voices_resp.voices]}"
    )
