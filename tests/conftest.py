"""Pytest fixtures for HeyGen MCP tests."""

from __future__ import annotations

import pytest

from heygen_mcp.api_client import HeyGenApiClient
from tests.mock_server import MockServerRunner, MockState


@pytest.fixture
def mock_state() -> MockState:
    """Default MockState with realistic data."""
    return MockState()


@pytest.fixture
def mock_server(mock_state: MockState):
    """Start and stop mock HeyGen HTTP server."""
    runner = MockServerRunner(mock_state)
    runner.start()
    yield runner
    runner.stop()


@pytest.fixture
def api_client(mock_server: MockServerRunner) -> HeyGenApiClient:
    """HeyGenApiClient pointed at mock server."""
    return HeyGenApiClient(
        api_key="test-api-key",
        base_url=mock_server.base_url,
    )
