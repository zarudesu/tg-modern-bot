"""
Integration tests for Plane API client with mocked HTTP responses.

Source: app/integrations/plane/client.py, app/integrations/plane/tasks.py
"""

import pytest
import aiohttp
from aioresponses import aioresponses

from app.integrations.plane.client import PlaneAPIClient
from app.integrations.plane.exceptions import (
    PlaneAuthError,
    PlaneNotFoundError,
    PlaneRateLimitError,
    PlaneAPIError,
)


API_URL = "https://plane.test.local"
TOKEN = "test_token"
WORKSPACE = "test-workspace"


@pytest.fixture
def client():
    return PlaneAPIClient(API_URL, TOKEN, WORKSPACE)


class TestPlaneAPIClientGet:
    """Tests for PlaneAPIClient.get() method."""

    @pytest.mark.asyncio
    async def test_get_success(self, client):
        with aioresponses() as mocked:
            mocked.get(
                f"{API_URL}/api/test",
                payload={"results": [{"id": "1", "name": "Test"}]},
            )
            async with aiohttp.ClientSession() as session:
                result = await client.get(session, "/api/test")

            assert result == {"results": [{"id": "1", "name": "Test"}]}

    @pytest.mark.asyncio
    async def test_get_with_params(self, client):
        with aioresponses() as mocked:
            mocked.get(
                f"{API_URL}/api/issues?expand=assignees",
                payload={"results": []},
            )
            async with aiohttp.ClientSession() as session:
                result = await client.get(
                    session, "/api/issues", params={"expand": "assignees"}
                )

            assert result == {"results": []}

    @pytest.mark.asyncio
    async def test_get_auth_error(self, client):
        with aioresponses() as mocked:
            mocked.get(f"{API_URL}/api/test", status=401)
            async with aiohttp.ClientSession() as session:
                with pytest.raises(PlaneAuthError):
                    await client.get(session, "/api/test")

    @pytest.mark.asyncio
    async def test_get_not_found(self, client):
        with aioresponses() as mocked:
            mocked.get(f"{API_URL}/api/nonexistent", status=404)
            async with aiohttp.ClientSession() as session:
                with pytest.raises(PlaneNotFoundError):
                    await client.get(session, "/api/nonexistent")

    @pytest.mark.asyncio
    async def test_get_server_error(self, client):
        with aioresponses() as mocked:
            mocked.get(f"{API_URL}/api/test", status=500, body="Internal Server Error")
            async with aiohttp.ClientSession() as session:
                with pytest.raises(PlaneAPIError, match="HTTP 500"):
                    await client.get(session, "/api/test")


class TestPlaneAPIClientPost:
    """Tests for PlaneAPIClient.post() method."""

    @pytest.mark.asyncio
    async def test_post_create_issue(self, client):
        issue_data = {"name": "New task", "priority": "high"}
        with aioresponses() as mocked:
            mocked.post(
                f"{API_URL}/api/issues",
                payload={"id": "new-uuid", "name": "New task"},
            )
            async with aiohttp.ClientSession() as session:
                result = await client.post(session, "/api/issues", json_data=issue_data)

            assert result["id"] == "new-uuid"


class TestPlaneAPIClientRateLimit:
    """Tests for rate limit handling with exponential backoff."""

    @pytest.mark.asyncio
    async def test_rate_limit_retry_success(self, client):
        """429 → 429 → 200 should succeed after retries."""
        with aioresponses() as mocked:
            url = f"{API_URL}/api/test"
            mocked.get(url, status=429)
            mocked.get(url, status=429)
            mocked.get(url, payload={"ok": True})

            async with aiohttp.ClientSession() as session:
                result = await client._request(session, "GET", "/api/test", max_retries=3)

            assert result == {"ok": True}

    @pytest.mark.asyncio
    async def test_rate_limit_exhausted(self, client):
        """All retries return 429 → should raise PlaneRateLimitError."""
        with aioresponses() as mocked:
            url = f"{API_URL}/api/test"
            mocked.get(url, status=429)
            mocked.get(url, status=429)
            mocked.get(url, status=429)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(PlaneRateLimitError):
                    await client._request(session, "GET", "/api/test", max_retries=3)


class TestPlaneAPIClientHeaders:
    """Tests for correct header construction."""

    def test_headers_contain_api_key(self, client):
        assert client.headers["x-api-key"] == TOKEN

    def test_headers_content_type(self, client):
        assert client.headers["Content-Type"] == "application/json"

    def test_url_construction(self, client):
        assert client.api_url == API_URL

    def test_workspace_slug(self, client):
        assert client.workspace_slug == WORKSPACE
