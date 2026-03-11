"""HeyGen MCP server module for providing MCP tools for the HeyGen API."""

import argparse
import os
import sys

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from heygen_mcp import workflow_tools
from heygen_mcp.api_client import (
    Character,
    Dimension,
    HeyGenApiClient,
    MCPAvatarGroupResponse,
    MCPAvatarsInGroupResponse,
    MCPGetCreditsResponse,
    MCPVideoGenerateResponse,
    MCPVideoStatusResponse,
    MCPVoicesResponse,
    VideoGenerateRequest,
    VideoInput,
    Voice,
)

# Load environment variables
load_dotenv()

# Create MCP server instance
mcp = FastMCP("HeyGen MCP")
api_client = None


# Function to get or create API client
async def get_api_client() -> HeyGenApiClient:
    """Get the API client, creating it if necessary."""
    global api_client

    # If we already have a client, return it
    if api_client is not None:
        return api_client

    # Otherwise, get the API key and create a new client
    api_key = os.getenv("HEYGEN_API_KEY")

    if not api_key:
        raise ValueError("HEYGEN_API_KEY environment variable not set.")

    # Create and store the client
    base_url = os.getenv("HEYGEN_BASE_URL")
    api_client = HeyGenApiClient(api_key, base_url=base_url)
    return api_client


########################
# MCP Tool Definitions #
########################


@mcp.tool(
    name="get_remaining_credits",
    description="Retrieves the remaining credits in heygen account.",
)
async def get_remaining_credits() -> MCPGetCreditsResponse:
    """Get the remaining quota for the user via HeyGen API."""
    try:
        client = await get_api_client()
        return await client.get_remaining_credits()
    except Exception as e:
        return MCPGetCreditsResponse(error=str(e))


@mcp.tool(
    name="get_voices",
    description=(
        "Retrieves a list of available voices from the HeyGen API. Results truncated "
        "to first 100 voices. Private voices generally will returned 1st."
    ),
)
async def get_voices() -> MCPVoicesResponse:
    """Get the list of available voices via HeyGen API."""
    try:
        client = await get_api_client()
        return await client.get_voices()
    except Exception as e:
        return MCPVoicesResponse(error=str(e))


@mcp.tool(
    name="get_avatar_groups",
    description=(
        "Retrieves a list of HeyGen avatar groups. By default, only private avatar "
        "groups are returned, unless include_public is set to true. Avatar groups "
        "are collections of avatars, avatar group ids cannot be used to generate "
        "videos."
    ),
)
async def get_avatar_groups(include_public: bool = False) -> MCPAvatarGroupResponse:
    """List avatar groups via HeyGen API v2/avatar_group.list endpoint."""
    try:
        client = await get_api_client()
        return await client.list_avatar_groups(include_public)
    except Exception as e:
        return MCPAvatarGroupResponse(error=str(e))


@mcp.tool(
    name="get_avatars_in_avatar_group",
    description="Retrieves a list of avatars in a specific HeyGen avatar group.",
)
async def get_avatars_in_avatar_group(group_id: str) -> MCPAvatarsInGroupResponse:
    """List avatars in a specific HeyGen avatar group via HeyGen API."""
    try:
        client = await get_api_client()
        return await client.get_avatars_in_group(group_id)
    except Exception as e:
        return MCPAvatarsInGroupResponse(error=str(e))


@mcp.tool(
    name="generate_avatar_video",
    description="Generates a new avatar video via the HeyGen API.",
)
async def generate_avatar_video(
    avatar_id: str, input_text: str, voice_id: str, title: str = ""
) -> MCPVideoGenerateResponse:
    """Generate a new avatar video using the HeyGen API."""
    try:
        # Create the request object with default values
        request = VideoGenerateRequest(
            title=title,
            video_inputs=[
                VideoInput(
                    character=Character(avatar_id=avatar_id),
                    voice=Voice(input_text=input_text, voice_id=voice_id),
                )
            ],
            dimension=Dimension(width=1280, height=720),
        )

        client = await get_api_client()
        return await client.generate_avatar_video(request)
    except Exception as e:
        return MCPVideoGenerateResponse(error=str(e))


@mcp.tool(
    name="get_avatar_video_status",
    description=(
        "Retrieves the status of a video generated via the HeyGen API. Video status "
        "make take several minutes to hours depending on length of video and queue "
        "time. If video is not yet complete, status be viewed later by user via "
        "https://app.heygen.com/home"
    ),
)
async def get_avatar_video_status(video_id: str) -> MCPVideoStatusResponse:
    """Retrieve the status of a video generated via the HeyGen API."""
    try:
        client = await get_api_client()
        return await client.get_video_status(video_id)
    except Exception as e:
        return MCPVideoStatusResponse(error=str(e))


############################
# Workflow Tool Definitions #
############################


@mcp.tool(
    name="check_inventory",
    description=(
        "Fetches credits, voices, and avatars in one call. Returns a combined "
        "inventory with capabilities info. Voices with non-HTTPS previews are "
        "flagged with hasPreview: false but not dropped."
    ),
)
async def check_inventory_tool() -> dict:
    """One-shot inventory: credits + voices + avatars."""
    try:
        client = await get_api_client()
        return await workflow_tools.check_inventory(client)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    name="create_video",
    description=(
        "Creates a HeyGen avatar video. Accepts avatar/voice as name or ID "
        "(fuzzy name matching). Returns a job handle to poll with "
        "get_video_status."
    ),
)
async def create_video_tool(
    avatar: str,
    voice: str,
    script: str,
    title: str = "",
    width: int = 1280,
    height: int = 720,
    avatar_style: str = "normal",
    emotion: str = "",
    voice_speed: float = 1.0,
    background_type: str = "color",
    background_value: str = "#000000",
) -> dict:
    """Create a video with smart avatar/voice lookup."""
    try:
        client = await get_api_client()
        return await workflow_tools.create_video(
            client,
            avatar=avatar,
            voice=voice,
            script=script,
            title=title,
            width=width,
            height=height,
            avatar_style=avatar_style,
            emotion=emotion or None,
            voice_speed=voice_speed,
            background_type=background_type,
            background_value=background_value,
        )
    except Exception as e:
        return {"error": str(e)}


@mcp.tool(
    name="get_video_status",
    description=(
        "Polls the status of a video job created with create_video. "
        "Returns status, videoUrl, duration, and any errors."
    ),
)
async def get_video_status_tool(job_id: str) -> dict:
    """Poll video job status."""
    try:
        client = await get_api_client()
        return await workflow_tools.get_video_status(client, job_id)
    except Exception as e:
        return {"error": str(e)}


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="HeyGen MCP Server")
    parser.add_argument(
        "--api-key",
        help=(
            "HeyGen API key. Alternatively, set HEYGEN_API_KEY environment variable."
        ),
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind the server to."
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind the server to."
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development.",
    )
    return parser.parse_args()


def main():
    """Run the MCP server."""
    args = parse_args()

    # Check if API key is provided or in environment
    if args.api_key:
        os.environ["HEYGEN_API_KEY"] = args.api_key

    # Verify API key is set
    if not os.getenv("HEYGEN_API_KEY"):
        print("ERROR: HeyGen API key not provided.")
        print(
            "Please set it using --api-key or the HEYGEN_API_KEY environment variable."
        )
        sys.exit(1)

    mcp.run()


if __name__ == "__main__":
    main()
