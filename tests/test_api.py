"""Tests for cockpit API — management-focused endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from cockpit.api.cache import cache


@pytest.fixture
async def client():
    from cockpit.api.app import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Mock data classes ────────────────────────────────────────────────────────


@dataclass
class MockManagement:
    people_count: int = 5
    stale_1on1s: int = 1


@dataclass
class MockNudge:
    priority: int = 10
    source: str = "management"
    message: str = "Stale 1:1 with Alice"


@dataclass
class MockGoal:
    name: str = "Agent coverage"
    status: str = "active"
    description: str = "Full agent coverage for management workflows"


@dataclass
class MockAgent:
    name: str = "management_prep"
    status: str = "healthy"
    last_run: str = "2026-03-01T07:00:00Z"


@dataclass
class MockTeamHealth:
    healthy: int = 5
    at_risk: int = 0
    stale: int = 1


# ── App skeleton tests ───────────────────────────────────────────────────────


class TestAppSkeleton:
    async def test_root_returns_info(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "cockpit-api"
        assert "version" in data

    async def test_cors_headers_present(self, client):
        resp = await client.options(
            "/",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


# ── Management data endpoints ────────────────────────────────────────────────


class TestManagementEndpoint:
    async def test_management_returns_data(self, client):
        cache.management = MockManagement()
        resp = await client.get("/api/management")
        assert resp.status_code == 200
        data = resp.json()
        assert data["people_count"] == 5

    async def test_management_returns_null_when_empty(self, client):
        cache.management = None
        resp = await client.get("/api/management")
        assert resp.status_code == 200
        assert resp.json() is None


class TestBriefingEndpoint:
    async def test_briefing_returns_briefing_data(self, client):
        """Briefing endpoint returns the cached briefing JSON."""
        cache.briefing = {
            "headline": "2 stale 1:1s",
            "generated_at": "2026-03-09T07:00:00Z",
            "body": "Test briefing body.",
            "action_items": [{"priority": "high", "action": "Schedule 1:1", "reason": "Overdue"}],
        }
        resp = await client.get("/api/briefing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["headline"] == "2 stale 1:1s"
        assert len(data["action_items"]) == 1

    async def test_briefing_returns_null_when_empty(self, client):
        cache.briefing = None
        resp = await client.get("/api/briefing")
        assert resp.status_code == 200
        assert resp.json() is None


class TestNudgesEndpoint:
    async def test_nudges_returns_list(self, client):
        cache.nudges = [MockNudge()]
        resp = await client.get("/api/nudges")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["priority"] == 10

    async def test_nudges_empty_list(self, client):
        cache.nudges = []
        resp = await client.get("/api/nudges")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


class TestGoalsEndpoint:
    async def test_goals_returns_data(self, client):
        cache.goals = [MockGoal()]
        resp = await client.get("/api/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Agent coverage"

    async def test_goals_returns_null_when_empty(self, client):
        cache.goals = None
        resp = await client.get("/api/goals")
        assert resp.status_code == 200
        assert resp.json() is None


class TestAgentsEndpoint:
    async def test_agents_returns_list(self, client):
        cache.agents = [MockAgent()]
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "management_prep"


class TestTeamHealthEndpoint:
    async def test_team_health_returns_data(self, client):
        cache.team_health = MockTeamHealth()
        resp = await client.get("/api/team/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] == 5

    async def test_team_health_returns_null_when_empty(self, client):
        cache.team_health = None
        resp = await client.get("/api/team/health")
        assert resp.status_code == 200
        assert resp.json() is None


class TestStatusEndpoint:
    async def test_status_returns_healthy(self, client):
        resp = await client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["healthy"] is True


# ── Cache age headers ────────────────────────────────────────────────────────


class TestCacheAgeHeaders:
    """All data endpoints should include X-Cache-Age header."""

    async def test_management_has_cache_header(self, client):
        cache.management = MockManagement()
        resp = await client.get("/api/management")
        assert "x-cache-age" in resp.headers

    async def test_nudges_has_cache_header(self, client):
        cache.nudges = [MockNudge()]
        resp = await client.get("/api/nudges")
        assert "x-cache-age" in resp.headers

    async def test_cache_age_is_numeric(self, client):
        cache.management = MockManagement()
        resp = await client.get("/api/management")
        age = resp.headers["x-cache-age"]
        assert age.lstrip("-").isdigit()


# ── Path serialization ──────────────────────────────────────────────────────


class TestPathSerialization:
    """Verify Path objects don't cause TypeError."""

    async def test_path_in_dataclass_serialized(self, client):
        @dataclass
        class DataWithPath:
            name: str = "test"
            file_path: Path = Path("/tmp/test.md")

        cache.management = DataWithPath()
        resp = await client.get("/api/management")
        assert resp.status_code == 200
        data = resp.json()
        assert data["file_path"] == "/tmp/test.md"
