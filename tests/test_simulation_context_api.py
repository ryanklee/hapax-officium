# ai-agents/tests/test_simulation_context_api.py
"""Tests for POST /api/engine/simulation-context endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from cockpit.api.routes.engine import router, set_engine

if TYPE_CHECKING:
    from pathlib import Path


class TestSimulationContextEndpoint:
    def _make_client(self, engine=None):
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        if engine is not None:
            set_engine(engine)
        return TestClient(app)

    def test_activate_simulation_context(self, tmp_path: Path):
        """POST with sim_dir activates simulation context."""
        sim_dir = tmp_path / "sim-test"
        sim_dir.mkdir()
        (sim_dir / ".sim-manifest.yaml").write_text(
            "simulation:\n  id: test\n  role: em\n  window: 7d\n"
            "  start_date: '2026-03-01'\n  end_date: '2026-03-07'\n"
            "  seed: demo-data/\n  status: completed\n"
        )

        engine = MagicMock()
        engine.pause = AsyncMock()
        client = self._make_client(engine)

        with (
            patch("cockpit.api.routes.engine.config"),
            patch("cockpit.api.routes.engine.cache") as mock_cache,
        ):
            mock_cache.refresh = AsyncMock()
            response = client.post(
                "/api/engine/simulation-context",
                json={"sim_dir": str(sim_dir)},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_deactivate_simulation_context(self):
        """POST with null sim_dir deactivates simulation context."""
        engine = MagicMock()
        engine.resume = AsyncMock()
        client = self._make_client(engine)

        with (
            patch("cockpit.api.routes.engine.config"),
            patch("cockpit.api.routes.engine.cache") as mock_cache,
        ):
            mock_cache.refresh = AsyncMock()
            response = client.post(
                "/api/engine/simulation-context",
                json={"sim_dir": None},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_rejects_nonexistent_directory(self):
        """POST with nonexistent sim_dir returns 400."""
        engine = MagicMock()
        client = self._make_client(engine)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": "/nonexistent/path"},
        )
        assert response.status_code == 400

    def test_rejects_non_simulation_directory(self, tmp_path: Path):
        """POST with directory lacking .sim-manifest.yaml returns 400."""
        regular_dir = tmp_path / "not-a-sim"
        regular_dir.mkdir()

        engine = MagicMock()
        client = self._make_client(engine)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": str(regular_dir)},
        )
        assert response.status_code == 400

    def test_engine_not_running_returns_error(self):
        """POST when engine is None returns error."""
        set_engine(None)
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post(
            "/api/engine/simulation-context",
            json={"sim_dir": None},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "error"
