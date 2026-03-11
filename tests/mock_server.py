"""FastAPI mock HeyGen HTTP server for testing."""

from __future__ import annotations

import socket
import threading
import time
import uuid
from dataclasses import dataclass, field

import uvicorn
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse

from tests.fixtures import (
    make_avatar,
    make_avatar_group,
    make_voice,
)


@dataclass
class MockState:
    """Mutable state shared between mock routes and test code."""

    credits: int = 200
    plan_credit: int | None = None
    voices: list[dict] = field(default_factory=lambda: [
        make_voice(voice_id="voice_001", name="Sarah", emotion_support=True),
        make_voice(voice_id="voice_002", name="Mark", gender="male"),
    ])
    avatar_groups: list[dict] = field(default_factory=lambda: [
        make_avatar_group(id="grp_private", name="My Avatars", group_type="private"),
        make_avatar_group(id="grp_public", name="Public Avatars", group_type="public"),
    ])
    avatars_by_group: dict[str, list[dict]] = field(default_factory=lambda: {
        "grp_private": [
            make_avatar(avatar_id="lee_avatar", avatar_name="Lee Gonzales"),
        ],
        "grp_public": [
            make_avatar(avatar_id="pub_avatar", avatar_name="Public Avatar"),
        ],
    })
    video_jobs: dict[str, dict] = field(default_factory=dict)
    force_http_error: int | None = None


def create_app(state: MockState) -> FastAPI:
    """Create FastAPI app wired to the given mutable state."""
    app = FastAPI()

    @app.middleware("http")
    async def error_middleware(request: Request, call_next):
        if state.force_http_error:
            code = state.force_http_error
            return JSONResponse(
                status_code=code,
                content={"error": f"Simulated {code} error"},
            )
        return await call_next(request)

    # ── v2 routes ──────────────────────────────────────────

    @app.get("/v2/user/remaining_quota")
    async def get_remaining_quota():
        data: dict = {}
        if state.plan_credit is not None:
            data["plan_credit"] = state.plan_credit
        else:
            data["remaining_quota"] = state.credits
            data["details"] = {"plan_credit": state.credits}
        return {"code": 100, "data": data, "message": "success"}

    @app.get("/v2/voices")
    async def get_voices():
        return {
            "code": 100,
            "data": {"voices": state.voices},
            "message": "success",
        }

    @app.get("/v2/avatar_group.list")
    async def list_avatar_groups(include_public: str = Query("false")):
        if include_public.lower() == "true":
            groups = state.avatar_groups
        else:
            groups = [
                g for g in state.avatar_groups
                if g.get("group_type") != "public"
            ]
        return {
            "code": 100,
            "data": {
                "total_count": len(groups),
                "avatar_group_list": groups,
            },
            "message": "success",
        }

    @app.get("/v2/avatar_group/{group_id}/avatars")
    async def get_avatars_in_group(group_id: str):
        avatars = state.avatars_by_group.get(group_id, [])
        return {
            "code": 100,
            "data": {"avatar_list": avatars},
            "message": "success",
        }

    @app.post("/v2/video/generate")
    async def generate_video(request: Request):
        body = await request.json()
        video_id = f"vid_{uuid.uuid4().hex[:12]}"
        state.video_jobs[video_id] = {
            "id": video_id,
            "status": "waiting",
            "video_url": None,
            "duration": None,
            "thumbnail_url": None,
            "gif_url": None,
            "caption_url": None,
            "created_at": int(time.time()),
            "error": None,
            "request": body,
        }
        return {
            "code": 100,
            "data": {"video_id": video_id},
            "message": "success",
        }

    @app.post("/v2/video/translate")
    async def translate_video(request: Request):
        return {"code": 100, "data": {}, "message": "success"}

    @app.post("/v2/avatar/create")
    async def create_avatar(request: Request):
        return {"code": 100, "data": {}, "message": "success"}

    # ── v1 routes ──────────────────────────────────────────

    @app.get("/v1/video_status.get")
    async def get_video_status(video_id: str = Query(...)):
        job = state.video_jobs.get(video_id)
        if not job:
            return {
                "code": 100,
                "data": {
                    "id": video_id,
                    "status": "failed",
                    "error": {
                        "code": 404,
                        "message": "Video not found",
                        "detail": f"No job with id {video_id}",
                    },
                },
                "message": "success",
            }
        return {
            "code": 100,
            "data": {
                "id": job["id"],
                "status": job["status"],
                "video_url": job["video_url"],
                "duration": job["duration"],
                "thumbnail_url": job["thumbnail_url"],
                "gif_url": job["gif_url"],
                "caption_url": job["caption_url"],
                "created_at": job["created_at"],
                "error": job["error"],
            },
            "message": "success",
        }

    return app


def find_free_port() -> int:
    """Find an available TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class MockServerRunner:
    """Manages lifecycle of the mock server in a background thread."""

    def __init__(self, state: MockState):
        self.state = state
        self.port = find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}/v2"
        self._app = create_app(state)
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        config = uvicorn.Config(
            self._app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        # Wait for server to be ready
        self._wait_for_ready()

    def _wait_for_ready(self, timeout: float = 5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(
                    ("127.0.0.1", self.port), timeout=0.1
                ):
                    return
            except OSError:
                time.sleep(0.05)
        raise TimeoutError(
            f"Mock server did not start within {timeout}s"
        )

    def stop(self):
        if self._server:
            self._server.should_exit = True
        if self._thread:
            self._thread.join(timeout=3.0)
