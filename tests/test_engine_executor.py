"""Tests for the phased async executor."""

import asyncio
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

from logos.engine.executor import PhasedExecutor
from logos.engine.models import Action, ActionPlan, ChangeEvent


def _make_event() -> ChangeEvent:
    return ChangeEvent(
        path=Path("/tmp/test.md"),
        subdirectory="people",
        event_type="modified",
        doc_type="person_note",
        timestamp=datetime.now(),
    )


def _make_plan(actions: list[Action]) -> ActionPlan:
    return ActionPlan(
        trigger=_make_event(),
        created_at=datetime.now(),
        actions=actions,
    )


async def test_phase0_actions_execute_and_results_stored():
    handler = AsyncMock(return_value="done")
    plan = _make_plan([Action(name="a", handler=handler, phase=0)])
    executor = PhasedExecutor()
    await executor.execute(plan)
    handler.assert_awaited_once_with()
    assert plan.results["a"] == "done"


async def test_phases_run_in_order():
    order = []

    async def make_handler(label):
        async def h():
            order.append(label)
            return label

        return h

    h0 = await make_handler("phase0")
    h1 = await make_handler("phase1")
    h2 = await make_handler("phase2")

    plan = _make_plan(
        [
            Action(name="a", handler=h0, phase=0),
            Action(name="b", handler=h1, phase=1),
            Action(name="c", handler=h2, phase=2),
        ]
    )
    executor = PhasedExecutor()
    await executor.execute(plan)
    assert order == ["phase0", "phase1", "phase2"]


async def test_actions_within_phase_run_concurrently():
    started = []
    finished = []

    async def slow_handler(label):
        started.append(label)
        await asyncio.sleep(0.05)
        finished.append(label)
        return label

    async def h1():
        return await slow_handler("a")

    async def h2():
        return await slow_handler("b")

    plan = _make_plan(
        [
            Action(name="a", handler=h1, phase=0),
            Action(name="b", handler=h2, phase=0),
        ]
    )
    executor = PhasedExecutor()
    t0 = time.monotonic()
    await executor.execute(plan)
    elapsed = time.monotonic() - t0
    # If sequential, would take ~0.1s. Concurrent should be ~0.05s.
    assert elapsed < 0.09
    assert set(finished) == {"a", "b"}


async def test_failed_action_does_not_abort_plan():
    async def failing():
        raise ValueError("boom")

    ok_handler = AsyncMock(return_value="ok")

    plan = _make_plan(
        [
            Action(name="fail", handler=failing, phase=0),
            Action(name="ok", handler=ok_handler, phase=0),
        ]
    )
    executor = PhasedExecutor()
    await executor.execute(plan)
    assert "fail" in plan.errors
    assert "boom" in plan.errors["fail"]
    assert plan.results["ok"] == "ok"


async def test_dependent_action_skipped_when_dependency_fails():
    async def failing():
        raise ValueError("boom")

    dependent = AsyncMock(return_value="should not run")

    plan = _make_plan(
        [
            Action(name="step1", handler=failing, phase=0),
            Action(name="step2", handler=dependent, phase=1, depends_on=["step1"]),
        ]
    )
    executor = PhasedExecutor()
    await executor.execute(plan)
    assert "step1" in plan.errors
    assert "step2" in plan.skipped
    dependent.assert_not_awaited()


async def test_action_timeout_is_enforced():
    async def slow():
        await asyncio.sleep(10)

    plan = _make_plan([Action(name="slow", handler=slow, phase=0)])
    executor = PhasedExecutor(action_timeout_s=0.1)
    await executor.execute(plan)
    assert "slow" in plan.errors
    assert "timeout" in plan.errors["slow"].lower()


async def test_llm_concurrency_is_bounded():
    """Phase 1 actions respect the semaphore limit."""
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    async def tracked_handler():
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            if current > max_concurrent:
                max_concurrent = current
        await asyncio.sleep(0.05)
        async with lock:
            current -= 1
        return "done"

    actions = [Action(name=f"llm_{i}", handler=tracked_handler, phase=1) for i in range(4)]
    plan = _make_plan(actions)
    executor = PhasedExecutor(llm_concurrency=2)
    await executor.execute(plan)
    assert max_concurrent <= 2
    assert len(plan.results) == 4


async def test_handler_receives_args_as_kwargs():
    handler = AsyncMock(return_value="result")
    plan = _make_plan(
        [
            Action(name="a", handler=handler, args={"x": 1, "y": "hello"}, phase=0),
        ]
    )
    executor = PhasedExecutor()
    await executor.execute(plan)
    handler.assert_awaited_once_with(x=1, y="hello")
    assert plan.results["a"] == "result"


async def test_phase0_unlimited_concurrency():
    """Phase 0 does not use the semaphore, even with llm_concurrency=1."""
    max_concurrent = 0
    current = 0
    lock = asyncio.Lock()

    async def tracked_handler():
        nonlocal max_concurrent, current
        async with lock:
            current += 1
            if current > max_concurrent:
                max_concurrent = current
        await asyncio.sleep(0.05)
        async with lock:
            current -= 1
        return "done"

    actions = [Action(name=f"fast_{i}", handler=tracked_handler, phase=0) for i in range(3)]
    plan = _make_plan(actions)
    executor = PhasedExecutor(llm_concurrency=1)
    await executor.execute(plan)
    # All 3 should run concurrently despite llm_concurrency=1
    assert max_concurrent == 3
    assert len(plan.results) == 3


async def test_dependent_skipped_when_dependency_in_skipped():
    """Action skipped if its dependency was itself skipped."""

    async def failing():
        raise ValueError("boom")

    dep2 = AsyncMock(return_value="nope")
    dep3 = AsyncMock(return_value="nope")

    plan = _make_plan(
        [
            Action(name="step1", handler=failing, phase=0),
            Action(name="step2", handler=dep2, phase=1, depends_on=["step1"]),
            Action(name="step3", handler=dep3, phase=2, depends_on=["step2"]),
        ]
    )
    executor = PhasedExecutor()
    await executor.execute(plan)
    assert "step2" in plan.skipped
    assert "step3" in plan.skipped
    dep2.assert_not_awaited()
    dep3.assert_not_awaited()
