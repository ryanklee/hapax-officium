"""Integration tests for ReactiveEngine orchestrator."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from cockpit.engine import ReactiveEngine

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory with people/ subdirectory."""
    people = tmp_path / "people"
    people.mkdir()
    return tmp_path


class TestLifecycle:
    """start() and stop() lifecycle tests."""

    async def test_start_sets_running(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        assert engine.running is False
        await engine.start()
        assert engine.running is True
        await engine.stop()

    async def test_stop_clears_running(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()
        assert engine.running is True
        await engine.stop()
        assert engine.running is False

    async def test_stop_when_not_running_is_noop(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        # Should not raise
        await engine.stop()
        assert engine.running is False


class TestDisabledEngine:
    """Engine disabled via enabled=False."""

    async def test_disabled_engine_does_not_start(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=False,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()
        assert engine.running is False
        # stop should still be safe
        await engine.stop()


class TestPersonFileCascade:
    """Person file change triggers refresh_cache (which includes nudges + team health)."""

    @patch(
        "cockpit.engine.reactive_rules._refresh_cache",
        new_callable=AsyncMock,
        return_value="cache refreshed",
    )
    async def test_person_file_triggers_cache_refresh(
        self,
        mock_refresh: AsyncMock,
        data_dir: Path,
    ) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()

        person_file = data_dir / "people" / "alice.md"
        person_file.write_text(
            "---\nname: Alice\ntype: person\n---\n# Alice\n",
            encoding="utf-8",
        )

        await asyncio.sleep(0.2)
        await engine.stop()

        mock_refresh.assert_called()


class TestErrorDelivery:
    """Failed actions produce high-priority error delivery items."""

    @patch(
        "cockpit.engine.reactive_rules._refresh_cache",
        new_callable=AsyncMock,
        side_effect=RuntimeError("cache exploded"),
    )
    async def test_failed_action_produces_error_delivery_item(
        self,
        mock_refresh: AsyncMock,
        data_dir: Path,
    ) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()

        person_file = data_dir / "people" / "alice.md"
        person_file.write_text(
            "---\nname: Alice\ntype: person\n---\n# Alice\n",
            encoding="utf-8",
        )

        await asyncio.sleep(0.2)
        await engine.stop()

        items = engine.recent_items()
        error_items = [i for i in items if i.category == "error"]
        assert len(error_items) >= 1
        err = error_items[0]
        assert err.priority == "high"
        assert "refresh_cache" in err.title
        assert "cache exploded" in err.detail


class TestStatus:
    """status() returns correct dict."""

    async def test_status_before_start(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        status = engine.status()
        assert status["running"] is False
        assert status["enabled"] is True
        assert isinstance(status["rules_count"], int)
        assert status["rules_count"] > 0
        assert status["pending_delivery"] == 0

    async def test_status_after_start(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()
        status = engine.status()
        assert status["running"] is True
        await engine.stop()


class TestRecentItems:
    """recent_items() returns delivery items."""

    async def test_recent_items_initially_empty(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        items = engine.recent_items()
        assert items == []


class TestRuleDescriptions:
    """rule_descriptions() returns rule metadata."""

    async def test_rule_descriptions(self, data_dir: Path) -> None:
        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        descriptions = engine.rule_descriptions()
        assert isinstance(descriptions, list)
        assert len(descriptions) > 0
        for desc in descriptions:
            assert "name" in desc
            assert "description" in desc
