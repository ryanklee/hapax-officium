"""Batched delivery queue with priority-aware flush scheduling.

Batches notifications to prevent alert fatigue. Items arrive from the
executor after actions complete. The queue respects attention budget:
at most one notification per flush interval, with critical items
triggering immediate delivery and high-priority items flushing early.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cockpit.engine.models import DeliveryItem

_log = logging.getLogger(__name__)

# Priority ordering for determining batch notification level
_PRIORITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}

# Map DeliveryItem priority to shared.notify priority strings
_NOTIFY_PRIORITY_MAP = {
    "critical": "urgent",
    "high": "high",
    "medium": "default",
    "low": "low",
}


def _send_notification(*, title: str, message: str, priority: str) -> bool:
    """Send a notification, wrapping shared.notify.send_notification.

    Maps delivery priority to ntfy priority and catches all exceptions.

    Returns:
        True if notification was delivered, False on failure.
    """
    try:
        from shared.notify import send_notification

        return send_notification(title, message, priority=priority)
    except Exception as exc:
        _log.error("Notification send failed: %s", exc)
        return False


@dataclass
class DeliveryQueue:
    """Batched notification delivery with priority-aware scheduling.

    Items are queued via enqueue() and flushed periodically or on
    priority escalation. Critical items flush immediately (next tick),
    high-priority items schedule a 60s flush window.
    """

    flush_interval_s: int = 300
    max_recent: int = 50

    pending: list[DeliveryItem] = field(default_factory=list)
    recent: deque[DeliveryItem] = field(init=False)
    _flush_task: asyncio.Task | None = field(default=None, init=False, repr=False)
    _high_flush_handle: asyncio.TimerHandle | None = field(default=None, init=False, repr=False)
    _high_flush_scheduled: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        self.recent = deque(maxlen=self.max_recent)

    def enqueue(self, item: DeliveryItem) -> None:
        """Add item to pending queue and recent ring buffer.

        Schedules priority-aware flush:
        - critical: immediate flush on next event loop tick
        - high: flush in 60s (if not already scheduled)
        """
        self.pending.append(item)
        self.recent.append(item)

        if item.priority == "critical":
            loop = asyncio.get_running_loop()
            loop.call_soon(lambda: asyncio.ensure_future(self.flush()))
        elif item.priority == "high" and not self._high_flush_scheduled:
            self._high_flush_scheduled = True
            loop = asyncio.get_running_loop()
            self._high_flush_handle = loop.call_later(
                60, lambda: asyncio.ensure_future(self._high_flush())
            )

    async def _high_flush(self) -> None:
        """Execute a high-priority flush and reset scheduling flag."""
        self._high_flush_scheduled = False
        self._high_flush_handle = None
        await self.flush()

    async def flush(self) -> None:
        """Flush all pending items as a single batched notification."""
        if not self.pending:
            return

        items = list(self.pending)
        self.pending.clear()

        # Determine highest priority in batch
        highest = max(items, key=lambda i: _PRIORITY_RANK.get(i.priority, 0))
        notify_priority = _NOTIFY_PRIORITY_MAP.get(highest.priority, "default")

        message = self._format_batch(items)
        title = "Cockpit"

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: _send_notification(title=title, message=message, priority=notify_priority),
        )
        _log.info("Flushed %d delivery items (priority=%s)", len(items), notify_priority)

    @staticmethod
    def _format_batch(items: list[DeliveryItem]) -> str:
        """Format items into a notification message.

        Single item: "{title}\\n{detail}"
        Multiple items: "{count} updates:\\n• {title}\\n• {title}\\n..."
        """
        if len(items) == 1:
            return f"{items[0].title}\n{items[0].detail}"
        lines = [f"{len(items)} updates:"]
        for item in items:
            lines.append(f"• {item.title}")
        return "\n".join(lines)

    async def start_flush_loop(self) -> None:
        """Start background task that flushes every flush_interval_s."""
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def _flush_loop(self) -> None:
        """Periodic flush loop."""
        while True:
            await asyncio.sleep(self.flush_interval_s)
            await self.flush()

    async def stop(self) -> None:
        """Cancel background tasks and flush remaining items."""
        if self._flush_task is not None:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
            self._flush_task = None

        if self._high_flush_handle is not None:
            self._high_flush_handle.cancel()
            self._high_flush_handle = None
            self._high_flush_scheduled = False

        await self.flush()
