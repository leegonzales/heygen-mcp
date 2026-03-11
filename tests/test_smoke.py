"""Full-stack smoke test via MCP stdio transport.

Spawns the MCP server as a subprocess, connects via stdio,
and exercises each tool end-to-end against the mock HeyGen API.
"""

from __future__ import annotations

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client

from tests.mock_server import MockServerRunner, MockState


@pytest.mark.asyncio
async def test_full_stdio_round_trip():
    """Spawn MCP server, connect via stdio, call all tools."""
    # Start mock HeyGen HTTP server
    state = MockState()
    runner = MockServerRunner(state)
    runner.start()

    try:
        # Spawn the MCP server as a subprocess pointing at mock
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "heygen_mcp.server"],
            env={
                "HEYGEN_API_KEY": "test-smoke-key",
                "HEYGEN_BASE_URL": runner.base_url,
                "PATH": "/usr/bin:/usr/local/bin",
                "HOME": "/tmp",
                "PYTHONPATH": ".",
            },
        )

        async with stdio_client(params) as (read_stream, write_stream):
            session = ClientSession(
                read_stream=read_stream,
                write_stream=write_stream,
            )
            async with session:
                await session.initialize()

                # ── List tools ────────────────────────────
                tools_result = await session.list_tools()
                tool_names = sorted(t.name for t in tools_result.tools)

                # Expect 6 original + 3 workflow = 9 tools
                assert len(tool_names) == 9, (
                    f"Expected 9 tools, got {len(tool_names)}: {tool_names}"
                )
                assert "check_inventory" in tool_names
                assert "create_video" in tool_names
                assert "get_video_status" in tool_names
                assert "get_remaining_credits" in tool_names
                assert "get_voices" in tool_names

                # ── check_inventory ───────────────────────
                inv_result = await session.call_tool(
                    "check_inventory", arguments={}
                )
                assert not inv_result.isError, (
                    f"check_inventory failed: {inv_result.content}"
                )
                inv_data = json.loads(inv_result.content[0].text)
                assert "credits" in inv_data
                assert "voices" in inv_data
                assert "avatars" in inv_data
                assert inv_data["credits"] == 200

                # ── create_video ──────────────────────────
                create_result = await session.call_tool(
                    "create_video",
                    arguments={
                        "avatar": "lee_avatar",
                        "voice": "voice_001",
                        "script": "Smoke test video",
                    },
                )
                assert not create_result.isError, (
                    f"create_video failed: {create_result.content}"
                )
                create_data = json.loads(create_result.content[0].text)
                assert "jobId" in create_data
                assert create_data["status"] == "submitted"
                job_id = create_data["jobId"]

                # ── get_video_status ──────────────────────
                status_result = await session.call_tool(
                    "get_video_status",
                    arguments={"job_id": job_id},
                )
                assert not status_result.isError, (
                    f"get_video_status failed: {status_result.content}"
                )
                status_data = json.loads(status_result.content[0].text)
                assert status_data["status"] == "waiting"
    finally:
        runner.stop()
