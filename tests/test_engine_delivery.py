"""Tests for the batched delivery queue."""

import asyncio
from datetime import datetime
from unittest.mock import patch

from logos.engine.models import DeliveryItem


def _make_item(
    priority: str = "medium",
    title: str = "Test update",
    detail: str = "Some detail",
) -> DeliveryItem:
    return DeliveryItem(
        title=title,
        detail=detail,
        priority=priority,
        category="detected",
        source_action="test_action",
        timestamp=datetime.now(),
    )


@patch("logos.engine.delivery._send_notification")
async def test_enqueue_adds_to_pending(mock_send):
    from logos.engine.delivery import DeliveryQueue

    q = DeliveryQueue()
    item = _make_item()
    q.enqueue(item)
    assert len(q.pending) == 1
    assert q.pending[0] is item


@patch("logos.engine.delivery._send_notification")
async def test_enqueue_adds_to_recent(mock_send):
    from logos.engine.delivery import DeliveryQueue

    q = DeliveryQueue()
    item = _make_item()
    q.enqueue(item)
    assert len(q.recent) == 1
    assert q.recent[0] is item


@patch("logos.engine.delivery._send_notification")
async def test_recent_ring_buffer_respects_max_size(mock_send):
    from logos.engine.delivery import DeliveryQueue

    q = DeliveryQueue(max_recent=3)
    for i in range(5):
        q.enqueue(_make_item(title=f"item-{i}"))
    assert len(q.recent) == 3
    assert q.recent[0].title == "item-2"
    assert q.recent[2].title == "item-4"


@patch("logos.engine.delivery._send_notification")
async def test_flush_sends_consolidated_notification(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(title="Alpha", detail="detail-a"))
    q.enqueue(_make_item(title="Beta", detail="detail-b"))
    await q.flush()
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[1]
    assert "2 updates" in call_kwargs["message"]
    assert "Alpha" in call_kwargs["message"]
    assert "Beta" in call_kwargs["message"]
    assert len(q.pending) == 0


@patch("logos.engine.delivery._send_notification")
async def test_flush_noop_when_empty(mock_send):
    from logos.engine.delivery import DeliveryQueue

    q = DeliveryQueue()
    await q.flush()
    mock_send.assert_not_called()


@patch("logos.engine.delivery._send_notification")
async def test_critical_triggers_immediate_flush(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(priority="critical", title="CRITICAL"))
    # Allow the event loop to process the scheduled callback
    await asyncio.sleep(0.05)
    mock_send.assert_called_once()
    assert len(q.pending) == 0


@patch("logos.engine.delivery._send_notification")
async def test_high_priority_schedules_flush_within_60s(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(priority="high", title="HIGH"))
    # High flush should be scheduled but not yet fired
    assert q._high_flush_scheduled is True
    mock_send.assert_not_called()
    # Clean up
    if q._high_flush_handle is not None:
        q._high_flush_handle.cancel()


@patch("logos.engine.delivery._send_notification")
async def test_high_priority_no_duplicate_scheduling(mock_send):
    from logos.engine.delivery import DeliveryQueue

    q = DeliveryQueue()
    q.enqueue(_make_item(priority="high", title="HIGH-1"))
    q.enqueue(_make_item(priority="high", title="HIGH-2"))
    # Should only schedule once
    assert q._high_flush_scheduled is True
    # Clean up
    if q._high_flush_handle is not None:
        q._high_flush_handle.cancel()


@patch("logos.engine.delivery._send_notification")
async def test_format_batch_single_item(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(title="Only One", detail="the detail"))
    await q.flush()
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["message"] == "Only One\nthe detail"


@patch("logos.engine.delivery._send_notification")
async def test_format_batch_multiple_items(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(title="A"))
    q.enqueue(_make_item(title="B"))
    q.enqueue(_make_item(title="C"))
    await q.flush()
    call_kwargs = mock_send.call_args[1]
    msg = call_kwargs["message"]
    assert msg.startswith("3 updates:")
    assert "• A" in msg
    assert "• B" in msg
    assert "• C" in msg


@patch("logos.engine.delivery._send_notification")
async def test_flush_maps_highest_priority(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(priority="low"))
    q.enqueue(_make_item(priority="high"))
    q.enqueue(_make_item(priority="medium"))
    await q.flush()
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["priority"] == "high"


@patch("logos.engine.delivery._send_notification")
async def test_stop_flushes_remaining(mock_send):
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue()
    q.enqueue(_make_item(title="leftover"))
    await q.stop()
    mock_send.assert_called_once()
    assert len(q.pending) == 0


@patch("logos.engine.delivery._send_notification")
async def test_flush_loop_fires_periodically(mock_send):
    """start_flush_loop flushes pending items on the interval."""
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue(flush_interval_s=0.05)  # 50ms for testing
    q.enqueue(_make_item(title="periodic"))
    await q.start_flush_loop()
    await asyncio.sleep(0.12)
    await q.stop()
    # Flush loop should have fired at least once
    assert mock_send.call_count >= 1
    assert len(q.pending) == 0


@patch("logos.engine.delivery._send_notification")
async def test_stop_cancels_flush_loop_task(mock_send):
    """stop() cancels the background flush task cleanly."""
    from logos.engine.delivery import DeliveryQueue

    mock_send.return_value = True
    q = DeliveryQueue(flush_interval_s=9999)
    await q.start_flush_loop()
    assert q._flush_task is not None
    assert not q._flush_task.done()
    await q.stop()
    assert q._flush_task is None
