"""Filesystem watcher for DATA_DIR with debounce and self-trigger prevention.

Uses watchdog (inotify on Linux) to detect file changes recursively.
Emits ChangeEvent instances via an async callback after debouncing
rapid writes and filtering out dotfiles/processed/ paths.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from logos.engine.models import ChangeEvent
from shared.frontmatter import parse_frontmatter_text

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from watchdog.observers.api import BaseObserver

_log = logging.getLogger(__name__)

_MD_SUFFIXES = {".md", ".markdown"}

_EVENT_TYPE_MAP = {
    FileCreatedEvent: "created",
    FileModifiedEvent: "modified",
    FileDeletedEvent: "deleted",
}


def _is_filtered(path: Path, data_dir: Path) -> bool:
    """Return True if the path should be filtered out (dotfiles, processed/)."""
    try:
        rel = path.relative_to(data_dir)
    except ValueError:
        return True

    for part in rel.parts:
        if part.startswith("."):
            return True

    # Filter processed/ subdirectory
    return bool(rel.parts and rel.parts[0] == "processed")


def _extract_subdirectory(path: Path, data_dir: Path) -> str:
    """Extract first-level subdirectory name relative to data_dir."""
    try:
        rel = path.relative_to(data_dir)
    except ValueError:
        return ""
    if rel.parts:
        return rel.parts[0]
    return ""


def _extract_doc_type(path: Path) -> str | None:
    """Extract type: from YAML frontmatter of markdown files."""
    if path.suffix.lower() not in _MD_SUFFIXES:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm, _body = parse_frontmatter_text(text)
    return fm.get("type") if fm else None


class _Handler(FileSystemEventHandler):
    """Watchdog handler that bridges filesystem events to the async loop."""

    def __init__(
        self,
        data_dir: Path,
        loop: asyncio.AbstractEventLoop,
        schedule_debounce: Callable[[Path, str], None],
    ) -> None:
        super().__init__()
        self._data_dir = data_dir
        self._loop = loop
        self._schedule_debounce = schedule_debounce

    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        path = Path(str(event.src_path))
        event_type = _EVENT_TYPE_MAP.get(type(event))
        if event_type is None:
            return

        if _is_filtered(path, self._data_dir):
            return

        # Bridge from watchdog thread to asyncio event loop
        self._loop.call_soon_threadsafe(self._schedule_debounce, path, event_type)


class DataDirWatcher:
    """Watches DATA_DIR for file changes, debounces, and emits ChangeEvents.

    Args:
        data_dir: Directory to watch recursively.
        on_change: Async callback receiving ChangeEvent instances.
        debounce_ms: Debounce window in milliseconds (default 200).
    """

    def __init__(
        self,
        data_dir: Path,
        on_change: Callable[[ChangeEvent], Awaitable[None]],
        debounce_ms: int = 200,
    ) -> None:
        self._data_dir = data_dir
        self._on_change = on_change
        self._debounce_s = debounce_ms / 1000.0
        self._observer: BaseObserver | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._timers: dict[Path, asyncio.TimerHandle] = {}
        self._pending_event_types: dict[Path, str] = {}
        self._ignore_set: set[Path] = set()

    def ignore(self, path: Path) -> None:
        """Register a path to skip on the next event (one-shot)."""
        self._ignore_set.add(path.resolve())

    async def start(self) -> None:
        """Start watching DATA_DIR."""
        self._loop = asyncio.get_running_loop()
        handler = _Handler(
            data_dir=self._data_dir,
            loop=self._loop,
            schedule_debounce=self._schedule_debounce,
        )
        observer = Observer()
        observer.schedule(handler, str(self._data_dir), recursive=True)
        observer.start()
        self._observer = observer
        _log.info("DataDirWatcher started on %s", self._data_dir)

    async def stop(self) -> None:
        """Stop watching and cancel pending timers."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2.0)
            self._observer = None

        # Cancel any pending debounce timers
        for handle in self._timers.values():
            handle.cancel()
        self._timers.clear()
        _log.info("DataDirWatcher stopped")

    def _schedule_debounce(self, path: Path, event_type: str) -> None:
        """Schedule or reschedule a debounced event emission.

        Called from the asyncio event loop thread (via call_soon_threadsafe).
        """
        resolved = path.resolve()

        # Check self-trigger ignore set — keep ignoring for the full
        # debounce window so that all inotify events from one write
        # (created + modified) are suppressed, then remove.
        if resolved in self._ignore_set:
            # Cancel any pending removal timer and schedule a new one
            existing_timer = self._timers.pop(resolved, None)
            if existing_timer is not None:
                existing_timer.cancel()
            if self._loop is None:
                return
            handle = self._loop.call_later(
                self._debounce_s,
                lambda r=resolved: self._ignore_set.discard(r),
            )
            self._timers[resolved] = handle
            _log.debug("Ignored self-triggered event for %s", path)
            return

        # Cancel existing timer for this path (reschedule debounce)
        existing = self._timers.pop(resolved, None)
        if existing is not None:
            existing.cancel()
        else:
            # First event for this path in debounce window — record the type
            self._pending_event_types[resolved] = event_type

        # Schedule new timer (always uses the *first* event_type seen)
        if self._loop is None:
            return
        handle = self._loop.call_later(
            self._debounce_s,
            self._fire_event,
            resolved,
            self._pending_event_types.get(resolved, event_type),
        )
        self._timers[resolved] = handle

    def _fire_event(self, path: Path, event_type: str) -> None:
        """Fire the debounced event — runs on the asyncio event loop."""
        self._timers.pop(path, None)
        self._pending_event_types.pop(path, None)

        doc_type = _extract_doc_type(path) if event_type != "deleted" else None
        subdirectory = _extract_subdirectory(path, self._data_dir)

        event = ChangeEvent(
            path=path,
            subdirectory=subdirectory,
            event_type=event_type,
            doc_type=doc_type,
            timestamp=datetime.now(UTC),
        )

        if self._loop is None:
            return
        coro = self._on_change(event)
        self._loop.create_task(coro)  # type: ignore[arg-type]  # Awaitable from async callback
