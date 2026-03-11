"""Test data factories for HeyGen API mock responses."""

from __future__ import annotations


def make_voice(
    voice_id: str = "voice_001",
    name: str = "Test Voice",
    language: str = "en-US",
    gender: str = "female",
    preview_audio: str | None = "https://cdn.heygen.com/preview.mp3",
    support_pause: bool = False,
    emotion_support: bool = False,
    support_interactive_avatar: bool = False,
) -> dict:
    return {
        "voice_id": voice_id,
        "name": name,
        "language": language,
        "gender": gender,
        "preview_audio": preview_audio,
        "support_pause": support_pause,
        "emotion_support": emotion_support,
        "support_interactive_avatar": support_interactive_avatar,
    }


def make_avatar_group(
    id: str = "group_001",
    name: str = "My Avatars",
    group_type: str = "private",
    created_at: int = 1700000000,
    num_looks: int = 2,
    preview_image: str = "https://cdn.heygen.com/group.png",
    train_status: str | None = None,
) -> dict:
    return {
        "id": id,
        "name": name,
        "group_type": group_type,
        "created_at": created_at,
        "num_looks": num_looks,
        "preview_image": preview_image,
        "train_status": train_status,
    }


def make_avatar(
    avatar_id: str = "avatar_001",
    avatar_name: str = "Lee Gonzales",
    gender: str = "male",
    preview_image_url: str = "https://cdn.heygen.com/avatar.png",
    preview_video_url: str = "https://cdn.heygen.com/avatar.mp4",
    premium: bool = False,
    type: str | None = "custom",
    tags: list[str] | None = None,
    default_voice_id: str | None = "voice_001",
) -> dict:
    return {
        "avatar_id": avatar_id,
        "avatar_name": avatar_name,
        "gender": gender,
        "preview_image_url": preview_image_url,
        "preview_video_url": preview_video_url,
        "premium": premium,
        "type": type,
        "tags": tags or [],
        "default_voice_id": default_voice_id,
    }


def make_voices_with_broken_previews() -> list[dict]:
    """5 voices: valid HTTPS, s3://, relative path, None, empty string."""
    return [
        make_voice(
            voice_id="v_https",
            name="HTTPS Voice",
            preview_audio="https://cdn.heygen.com/ok.mp3",
        ),
        make_voice(
            voice_id="v_s3",
            name="S3 Voice",
            preview_audio="s3://heygen-bucket/audio.mp3",
        ),
        make_voice(
            voice_id="v_relative",
            name="Relative Voice",
            preview_audio="audio/preview.mp3",
        ),
        make_voice(
            voice_id="v_none",
            name="None Voice",
            preview_audio=None,
        ),
        make_voice(
            voice_id="v_empty",
            name="Empty Voice",
            preview_audio="",
        ),
    ]


def make_large_voice_list(n: int = 1200) -> list[dict]:
    """Generate a large list of voices for truncation testing."""
    return [
        make_voice(voice_id=f"voice_{i:04d}", name=f"Voice {i}")
        for i in range(n)
    ]
