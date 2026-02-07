"""
Integration tests for WebhookServer using aiohttp test client.

Source: app/webhooks/server.py
"""

import pytest
from unittest.mock import AsyncMock, patch
from aiohttp.test_utils import TestClient, TestServer

from app.webhooks.server import WebhookServer


@pytest.fixture
async def webhook_client():
    """Create a test client for the webhook server."""
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    server = WebhookServer(bot)
    async with TestClient(TestServer(server.app)) as client:
        yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, webhook_client):
        resp = await webhook_client.get("/health")
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_health_returns_json(self, webhook_client):
        resp = await webhook_client.get("/health")
        data = await resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["service"] == "telegram-bot-webhooks"


class TestRootEndpoint:
    """Tests for / root endpoint."""

    @pytest.mark.asyncio
    async def test_root_returns_200(self, webhook_client):
        resp = await webhook_client.get("/")
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_root_lists_endpoints(self, webhook_client):
        resp = await webhook_client.get("/")
        data = await resp.json()
        assert "endpoints" in data
        assert data["service"] == "Telegram Bot Webhooks"


class TestAITaskResultWebhook:
    """Tests for /webhooks/ai/task-result endpoint."""

    @pytest.mark.asyncio
    async def test_missing_detection_returns_error(self, webhook_client):
        resp = await webhook_client.post(
            "/webhooks/ai/task-result",
            json={"no_detection": True},
        )
        data = await resp.json()
        # Server should handle gracefully (either error or ignored)
        assert resp.status == 200 or resp.status == 400

    @pytest.mark.asyncio
    async def test_non_task_detection_ignored(self, webhook_client):
        resp = await webhook_client.post(
            "/webhooks/ai/task-result",
            json={
                "detection": {"is_task": False},
                "action_taken": "ignored",
            },
        )
        data = await resp.json()
        assert resp.status == 200


class TestPlaneDirectWebhook:
    """Tests for /webhooks/plane-direct endpoint."""

    @pytest.mark.asyncio
    async def test_non_issue_event_handled(self, webhook_client):
        resp = await webhook_client.post(
            "/webhooks/plane-direct",
            json={
                "event": "project",
                "action": "created",
                "data": {},
            },
        )
        assert resp.status == 200

    @pytest.mark.asyncio
    async def test_empty_payload(self, webhook_client):
        resp = await webhook_client.post(
            "/webhooks/plane-direct",
            json={},
        )
        # Should handle empty payload gracefully
        assert resp.status in (200, 400)
