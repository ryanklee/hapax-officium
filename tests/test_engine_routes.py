"""Tests for engine API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.api.routes.engine import router


def _make_client():
    """Create a TestClient with just the engine router."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _mock_engine(*, running: bool = True) -> MagicMock:
    engine = MagicMock()
    engine.status.return_value = {
        "running": running,
        "enabled": True,
        "rules_count": 3,
        "pending_delivery": 0,
    }
    engine.recent_items.return_value = []
    engine.rule_descriptions.return_value = [
        {"name": "prep_on_person_change", "description": "Trigger prep on person note change"},
    ]
    return engine


class TestEngineStatus:
    def test_status_returns_200(self):
        mock = _mock_engine()
        with patch("cockpit.api.routes.engine._get_engine", return_value=mock):
            client = _make_client()
            resp = client.get("/api/engine/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True
        assert data["rules_count"] == 3

    def test_status_no_engine(self):
        with patch("cockpit.api.routes.engine._get_engine", return_value=None):
            client = _make_client()
            resp = client.get("/api/engine/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is False


class TestEngineRecent:
    def test_recent_returns_200_empty(self):
        mock = _mock_engine()
        with patch("cockpit.api.routes.engine._get_engine", return_value=mock):
            client = _make_client()
            resp = client.get("/api/engine/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_recent_serializes_items(self):
        mock = _mock_engine()
        from cockpit.engine.models import DeliveryItem

        ts = datetime(2026, 3, 9, 12, 0, 0, tzinfo=UTC)
        item = DeliveryItem(
            title="prep_refresh",
            detail="Refreshed prep for Alice",
            priority="medium",
            category="generated",
            source_action="prep_refresh",
            timestamp=ts,
            artifacts=[Path("/tmp/test.md")],
        )
        mock.recent_items.return_value = [item]
        with patch("cockpit.api.routes.engine._get_engine", return_value=mock):
            client = _make_client()
            resp = client.get("/api/engine/recent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == "prep_refresh"
        assert data[0]["timestamp"] == "2026-03-09T12:00:00+00:00"
        assert data[0]["artifacts"] == ["/tmp/test.md"]


class TestEngineRules:
    def test_rules_returns_200(self):
        mock = _mock_engine()
        with patch("cockpit.api.routes.engine._get_engine", return_value=mock):
            client = _make_client()
            resp = client.get("/api/engine/rules")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "prep_on_person_change"
