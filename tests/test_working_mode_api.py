"""API tests for the /api/working-mode endpoint and deprecated /api/cycle-mode alias."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mode_file(tmp_path: Path) -> Path:
    """Patch WORKING_MODE_FILE + force the route's script-lookup to return None
    so the direct-file-write fallback executes (instead of running the real
    council hapax-working-mode script which would write to the operator's
    real ~/.cache/hapax/working-mode)."""
    file = tmp_path / "working-mode"
    with (
        patch("shared.working_mode.WORKING_MODE_FILE", file),
        patch("logos.api.routes.working_mode.WORKING_MODE_FILE", file),
        patch("logos.api.routes.working_mode.shutil.which", return_value=None),
        patch("logos.api.routes.working_mode._SCRIPT", Path("/nonexistent/hapax-working-mode")),
    ):
        yield file


@pytest.fixture
def client():
    """A FastAPI TestClient against the officium logos app."""
    from logos.api.app import app

    return TestClient(app)


def test_get_working_mode_defaults_to_rnd(mode_file: Path, client: TestClient):
    response = client.get("/api/working-mode")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "rnd"
    assert body["switched_at"] is None


def test_get_working_mode_reads_existing_file(mode_file: Path, client: TestClient):
    mode_file.write_text("research")
    response = client.get("/api/working-mode")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "research"
    assert body["switched_at"] is not None


def test_put_working_mode_research(mode_file: Path, client: TestClient):
    response = client.put("/api/working-mode", json={"mode": "research"})
    assert response.status_code == 200
    assert response.json()["mode"] == "research"
    assert mode_file.read_text() == "research"


def test_put_working_mode_rnd(mode_file: Path, client: TestClient):
    response = client.put("/api/working-mode", json={"mode": "rnd"})
    assert response.status_code == 200
    assert response.json()["mode"] == "rnd"
    assert mode_file.read_text() == "rnd"


def test_put_working_mode_rejects_invalid_mode(mode_file: Path, client: TestClient):
    response = client.put("/api/working-mode", json={"mode": "dev"})
    assert response.status_code == 422


def test_put_working_mode_rejects_fortress(mode_file: Path, client: TestClient):
    """Officium intentionally omits council's fortress mode."""
    response = client.put("/api/working-mode", json={"mode": "fortress"})
    assert response.status_code == 422


def test_deprecated_cycle_mode_get_alias(mode_file: Path, client: TestClient):
    """The /api/cycle-mode GET still works as a deprecated alias."""
    mode_file.write_text("research")
    response = client.get("/api/cycle-mode")
    assert response.status_code == 200
    assert response.json()["mode"] == "research"


def test_deprecated_cycle_mode_put_alias(mode_file: Path, client: TestClient):
    """The /api/cycle-mode PUT still works as a deprecated alias."""
    response = client.put("/api/cycle-mode", json={"mode": "rnd"})
    assert response.status_code == 200
    assert response.json()["mode"] == "rnd"
    assert mode_file.read_text() == "rnd"
