# ai-agents/tests/test_engine_pause.py
"""Tests for engine pause/resume during simulation context switching."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from cockpit.engine import ReactiveEngine


class TestEnginePause:
    async def test_pause_stops_watcher(self):
        """pause() stops the watcher but keeps engine instance alive."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine._watcher = MagicMock()
        engine._watcher.stop = AsyncMock()
        engine._scheduler = MagicMock()
        engine._scheduler.stop = AsyncMock()
        engine.running = True

        await engine.pause()

        engine._watcher.stop.assert_called_once()
        engine._scheduler.stop.assert_called_once()
        assert engine.running is False
        assert engine.paused is True

    async def test_resume_restarts_watcher(self):
        """resume() restarts the watcher."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine._watcher = MagicMock()
        engine._watcher.start = AsyncMock()
        engine._scheduler = MagicMock()
        engine._scheduler.start = AsyncMock()
        engine._delivery = MagicMock()
        engine._delivery.start_flush_loop = AsyncMock()
        engine.running = False
        engine.paused = True

        await engine.resume()

        engine._watcher.start.assert_called_once()
        engine._scheduler.start.assert_called_once()
        assert engine.running is True
        assert engine.paused is False

    async def test_pause_noop_when_not_running(self):
        """pause() is a no-op if engine not running."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False

        await engine.pause()
        assert engine.paused is False

    async def test_resume_noop_when_not_paused(self):
        """resume() is a no-op if engine not paused."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False
        engine.paused = False

        await engine.resume()
        assert engine.running is False

    async def test_status_includes_paused(self):
        """status() reports paused state."""
        engine = ReactiveEngine(data_dir=Path("/tmp/fake"), enabled=True)
        engine.running = False
        engine.paused = True

        status = engine.status()
        assert status["paused"] is True
