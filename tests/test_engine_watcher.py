"""Tests for cockpit.engine.watcher — DataDirWatcher.

Self-contained, no conftest. Uses tmp_path for isolated test directories.
asyncio_mode = "auto" in pytest config — async tests work without decorator.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from cockpit.engine.watcher import DataDirWatcher

if TYPE_CHECKING:
    from pathlib import Path

    from cockpit.engine.models import ChangeEvent


async def test_file_creation_detected(tmp_path: Path):
    """File creation emits a ChangeEvent with correct subdirectory and event_type."""
    people_dir = tmp_path / "people"
    people_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        (people_dir / "alice.md").write_text("---\ntype: person\n---\n# Alice\n")
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 1
    evt = events[0]
    assert evt.path == people_dir / "alice.md"
    assert evt.subdirectory == "people"
    assert evt.event_type == "created"


async def test_dotfiles_ignored(tmp_path: Path):
    """Files/dirs starting with '.' are ignored."""
    hidden_dir = tmp_path / ".hidden"
    hidden_dir.mkdir()
    normal_dir = tmp_path / "inbox"
    normal_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        (hidden_dir / "secret.md").write_text("hidden")
        (normal_dir / ".dotfile").write_text("dotfile")
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 0


async def test_processed_directory_ignored(tmp_path: Path):
    """Files in processed/ subdirectory are ignored."""
    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        (processed_dir / "done.md").write_text("processed")
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 0


async def test_self_trigger_prevention(tmp_path: Path):
    """ignore() prevents one event then re-enables detection."""
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    target = inbox_dir / "generated.md"

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        # Pre-register the path to ignore
        watcher.ignore(target)
        target.write_text("first write — should be ignored")
        await asyncio.sleep(0.15)
        assert len(events) == 0

        # Second write should be detected (ignore consumed)
        target.write_text("second write — should be detected")
        await asyncio.sleep(0.15)
        assert len(events) == 1
        assert events[0].event_type == "modified"
    finally:
        await watcher.stop()


async def test_debounce_coalesces_rapid_writes(tmp_path: Path):
    """Multiple rapid writes to the same file produce a single event."""
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=100)
    await watcher.start()
    try:
        target = inbox_dir / "rapid.txt"
        for i in range(5):
            target.write_text(f"write {i}")
            await asyncio.sleep(0.02)
        # Wait for debounce to fire (debounce_ms=100 + buffer)
        await asyncio.sleep(0.2)
    finally:
        await watcher.stop()

    assert len(events) == 1


async def test_frontmatter_type_enrichment(tmp_path: Path):
    """Markdown files with type: in frontmatter get doc_type populated."""
    people_dir = tmp_path / "people"
    people_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        (people_dir / "bob.md").write_text("---\ntype: person\nname: Bob\n---\n# Bob\n")
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 1
    assert events[0].doc_type == "person"


async def test_file_deletion_detected(tmp_path: Path):
    """File deletion emits a ChangeEvent with event_type='deleted' and doc_type=None."""
    people_dir = tmp_path / "people"
    people_dir.mkdir()
    target = people_dir / "departing.md"
    target.write_text("---\ntype: person\n---\n# Departing\n")

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        # Wait for watcher to settle after initial creation
        await asyncio.sleep(0.15)
        events.clear()

        target.unlink()
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 1
    assert events[0].event_type == "deleted"
    assert events[0].doc_type is None
    assert events[0].subdirectory == "people"


async def test_non_md_files_have_no_doc_type(tmp_path: Path):
    """Non-markdown files have doc_type=None."""
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()

    events: list[ChangeEvent] = []
    callback = AsyncMock(side_effect=lambda e: events.append(e))

    watcher = DataDirWatcher(data_dir=tmp_path, on_change=callback, debounce_ms=50)
    await watcher.start()
    try:
        (inbox_dir / "data.json").write_text('{"key": "value"}')
        await asyncio.sleep(0.15)
    finally:
        await watcher.stop()

    assert len(events) == 1
    assert events[0].doc_type is None
