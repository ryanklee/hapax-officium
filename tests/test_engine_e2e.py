"""End-to-end tests verifying the full reactive engine cascade.

Write a file -> watcher detects -> rules evaluate -> actions execute -> delivery items queued.
All downstream agent/collector functions are mocked — we test engine orchestration only.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from logos.engine import ReactiveEngine

if TYPE_CHECKING:
    from pathlib import Path


def _write_md(path: Path, frontmatter: str, body: str = "") -> None:
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


class TestPersonFileFullCascade:
    """Person file write triggers refresh_cache (includes nudges + team health)."""

    @patch(
        "logos.engine.reactive_rules._refresh_cache",
        new_callable=AsyncMock,
        return_value="cache refreshed",
    )
    async def test_person_file_full_cascade(
        self,
        mock_refresh: AsyncMock,
        tmp_path: Path,
    ) -> None:
        data_dir = tmp_path
        (data_dir / "people").mkdir()

        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()

        _write_md(
            data_dir / "people" / "alice.md",
            "type: person\nname: Alice\nteam: platform\ncognitive-load: high\n",
            "# Alice\nPlatform team lead.\n",
        )

        await asyncio.sleep(0.2)
        await engine.stop()

        mock_refresh.assert_awaited()

        items = engine.recent_items()
        assert len(items) >= 1
        titles = [item.title for item in items]
        assert any("refresh_cache" in t for t in titles)


class TestCoachingFileRefreshesCache:
    """Coaching file write triggers refresh_cache (includes nudges)."""

    @patch(
        "logos.engine.reactive_rules._refresh_cache",
        new_callable=AsyncMock,
        return_value="cache refreshed",
    )
    async def test_coaching_file_triggers_cache_refresh(
        self,
        mock_refresh: AsyncMock,
        tmp_path: Path,
    ) -> None:
        data_dir = tmp_path
        (data_dir / "coaching").mkdir()

        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()

        _write_md(
            data_dir / "coaching" / "alice-coaching.md",
            "type: coaching\nname: Alice\n",
            "# Coaching notes\nGrowth area: delegation.\n",
        )

        await asyncio.sleep(0.2)
        await engine.stop()

        mock_refresh.assert_awaited()


class TestInboxFileTriggersIngest:
    """Inbox file write triggers ingest_document and refresh_cache."""

    @patch(
        "logos.engine.reactive_rules._refresh_cache",
        new_callable=AsyncMock,
        return_value="cache refreshed",
    )
    @patch(
        "logos.engine.reactive_rules._ingest_document",
        new_callable=AsyncMock,
        return_value="ingested as note",
    )
    async def test_inbox_file_triggers_ingest(
        self,
        mock_ingest: AsyncMock,
        mock_refresh: AsyncMock,
        tmp_path: Path,
    ) -> None:
        data_dir = tmp_path
        (data_dir / "inbox").mkdir()

        engine = ReactiveEngine(
            data_dir=data_dir,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,
        )
        await engine.start()

        inbox_file = data_dir / "inbox" / "new-doc.md"
        _write_md(
            inbox_file,
            "type: note\n",
            "Some content to ingest.\n",
        )

        await asyncio.sleep(0.2)
        await engine.stop()

        mock_ingest.assert_awaited()
        # Verify the path argument was passed correctly
        call_kwargs = mock_ingest.call_args
        called_path = call_kwargs.kwargs.get("path") or call_kwargs.args[0]
        assert called_path == inbox_file.resolve() or called_path == inbox_file
