# Synthesis Scheduler Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-trigger LLM synthesis agents (briefing, snapshot, overview, profiler) when management data changes, using quiet-window batching.

**Architecture:** SynthesisScheduler is a peer component to the reactive engine. It receives `signal(subdirectory)` calls from the engine's change handler, accumulates a dirty set, waits for a configurable quiet window (180s), then submits Phase 1 ActionPlans to the existing PhasedExecutor. Manual agent runs suppress all synthesis.

**Tech Stack:** Python 3.12+, asyncio, dataclasses, FastAPI, PhasedExecutor, existing agent functions.

**Spec:** `docs/plans/2026-03-10-synthesis-scheduler-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `logos/engine/models.py` | Make `ActionPlan.trigger` optional (field reorder) |
| `logos/engine/rules.py` | Update `evaluate_rules` to use keyword args for ActionPlan |
| `logos/engine/synthesis.py` | **NEW** — SynthesisScheduler class + 4 synthesis handlers |
| `logos/engine/__init__.py` | Wire scheduler into ReactiveEngine lifecycle |
| `logos/api/app.py` | Pass `agent_run_manager` to engine constructor |
| `logos/api/cache.py` | Add hot/warm change timestamps + accessors |
| `logos/api/routes/engine.py` | Add `POST /api/engine/synthesize` endpoint |
| `logos/api/routes/data.py` | Add `_freshness` metadata to 4 artifact endpoints |
| `tests/test_synthesis_scheduler.py` | **NEW** — 14 tests for scheduler behavior |

---

## Chunk 1: ActionPlan Model Refactor

Safe, behavior-preserving refactor. Makes `trigger` optional so synthesis can create timer-driven plans.

### Task 1: Make ActionPlan.trigger optional

**Files:**
- Modify: `logos/engine/models.py:38-47`
- Modify: `logos/engine/rules.py:72-76`
- Test: existing tests (no new test needed — behavior unchanged)

- [ ] **Step 1: Write a test that ActionPlan works with trigger=None**

Add to `tests/test_engine_models.py` (create if needed — check first):

```python
"""Tests for logos/engine/models.py."""
from __future__ import annotations

from datetime import datetime, timezone

from cockpit.engine.models import ActionPlan


class TestActionPlanTriggerOptional:
    def test_action_plan_without_trigger(self):
        plan = ActionPlan(created_at=datetime.now(timezone.utc))
        assert plan.trigger is None
        assert plan.actions == []

    def test_action_plan_with_trigger(self):
        from cockpit.engine.models import ChangeEvent
        from pathlib import Path

        event = ChangeEvent(
            path=Path("/tmp/test.md"),
            subdirectory="people",
            event_type="modified",
            doc_type="person",
            timestamp=datetime.now(timezone.utc),
        )
        plan = ActionPlan(created_at=datetime.now(timezone.utc), trigger=event)
        assert plan.trigger is event
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py -v`
Expected: FAIL — `trigger` is a required positional arg (no default).

- [ ] **Step 3: Reorder ActionPlan fields**

In `logos/engine/models.py`, change the `ActionPlan` class:

```python
@dataclass
class ActionPlan:
    """Ordered set of actions produced by rule evaluation."""

    created_at: datetime
    trigger: ChangeEvent | None = None  # None for timer-driven plans
    actions: list[Action] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)
```

- [ ] **Step 4: Update evaluate_rules to use keyword args**

In `logos/engine/rules.py` line 72-76, change to:

```python
    return ActionPlan(
        trigger=event,
        created_at=datetime.now(UTC),
        actions=actions,
    )
```

(This is already using keyword args — verify it still works.)

- [ ] **Step 5: Run all engine tests to verify no regression**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py tests/test_engine_rules.py tests/test_engine_executor.py tests/test_engine_reactive_rules.py tests/test_engine_integration.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add logos/engine/models.py logos/engine/rules.py tests/test_engine_models.py
git commit -m "refactor: make ActionPlan.trigger optional for timer-driven plans"
```

---

## Chunk 2: SynthesisScheduler Core + Tests

The main implementation. TDD: write tests first, then implement to make them pass.

### Task 2: Write core scheduler tests (signal, timer, dirty set)

**Files:**
- Create: `tests/test_synthesis_scheduler.py`

- [ ] **Step 1: Write the test file with 7 core tests**

```python
"""Tests for logos/engine/synthesis.py — SynthesisScheduler."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cockpit.engine.synthesis import (
    HOT_PATH,
    WARM_PATH,
    SYNTHESIS_RELEVANT,
    SynthesisScheduler,
)


def _make_scheduler(
    *,
    agent_running: bool = False,
    quiet_window_s: float = 0.05,
    profiler_interval_s: float = 86400,
    enabled: bool = True,
) -> tuple[SynthesisScheduler, AsyncMock]:
    """Create a scheduler with mocked dependencies."""
    executor = AsyncMock()
    delivery = MagicMock()
    delivery.enqueue = MagicMock()
    arm = MagicMock()
    arm.is_running = agent_running

    scheduler = SynthesisScheduler(
        executor=executor,
        delivery=delivery,
        agent_run_manager=arm,
        quiet_window_s=quiet_window_s,
        profiler_interval_s=profiler_interval_s,
        enabled=enabled,
    )
    return scheduler, executor


class TestSignal:
    def test_irrelevant_subdirectory(self):
        """decisions/, status-reports/, references/, 1on1-prep/ don't affect dirty set."""
        scheduler, _ = _make_scheduler()
        for subdir in ("decisions", "status-reports", "references", "1on1-prep", "inbox", "processed"):
            scheduler.signal(subdir)
        assert len(scheduler._dirty) == 0
        assert scheduler._profiler_dirty is False

    def test_hot_path_sets_dirty(self):
        """people/ adds to dirty set and sets profiler dirty."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("people")
        assert "people" in scheduler._dirty
        assert scheduler._profiler_dirty is True

    def test_warm_path_sets_profiler_dirty(self):
        """meetings/ sets profiler dirty but doesn't add to hot-path-triggering dirty."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("meetings")
        assert "meetings" in scheduler._dirty
        assert scheduler._profiler_dirty is True


class TestQuietWindow:
    async def test_timer_resets_on_signal(self):
        """Second signal cancels and reschedules timer."""
        scheduler, _ = _make_scheduler(quiet_window_s=10.0)

        scheduler.signal("people")
        first_timer = scheduler._timer
        assert first_timer is not None

        scheduler.signal("coaching")
        second_timer = scheduler._timer
        assert second_timer is not first_timer
        assert {"people", "coaching"} <= scheduler._dirty

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()

    async def test_synthesis_fires_after_quiet_window(self):
        """Handlers called after timer expires."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)

        with patch("cockpit.engine.synthesis._synthesize_briefing", new_callable=AsyncMock) as mock_brief, \
             patch("cockpit.engine.synthesis._synthesize_snapshot", new_callable=AsyncMock) as mock_snap, \
             patch("cockpit.engine.synthesis._synthesize_overview", new_callable=AsyncMock) as mock_over, \
             patch("cockpit.engine.synthesis.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()

            scheduler.signal("people")
            # Wait for quiet window + execution
            await asyncio.sleep(0.2)

            assert executor.execute.called
            plan = executor.execute.call_args[0][0]
            action_names = {a.name for a in plan.actions}
            assert "synthesize_briefing" in action_names
            assert "synthesize_snapshot" in action_names
            assert "synthesize_overview" in action_names
            assert plan.trigger is None


class TestSuppression:
    async def test_suppressed_when_agent_running(self):
        """Reschedules 60s when manual agent active."""
        scheduler, executor = _make_scheduler(
            agent_running=True, quiet_window_s=0.05
        )

        scheduler.signal("people")
        await asyncio.sleep(0.2)

        # Should not have fired — agent is running
        assert not executor.execute.called
        # Timer should have been rescheduled
        assert scheduler._timer is not None

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()

    async def test_suppressed_when_synthesis_running(self):
        """Re-entrant guard prevents concurrent synthesis."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        scheduler._running_synthesis = True

        scheduler.signal("people")
        await asyncio.sleep(0.2)

        assert not executor.execute.called

        # Cleanup
        scheduler._running_synthesis = False
        if scheduler._timer:
            scheduler._timer.cancel()


class TestFailure:
    async def test_dirty_preserved_on_failure(self):
        """Dirty set restored when executor raises."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        executor.execute = AsyncMock(side_effect=Exception("LLM down"))

        with patch("cockpit.engine.synthesis.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            scheduler.signal("people")
            await asyncio.sleep(0.2)

        # Dirty should be restored after failure
        assert scheduler._dirty & HOT_PATH


class TestForce:
    async def test_force_bypasses_quiet_window(self):
        """force() triggers immediate synthesis."""
        scheduler, executor = _make_scheduler(quiet_window_s=999)

        with patch("cockpit.engine.synthesis.cache") as mock_cache:
            mock_cache.refresh = AsyncMock()
            scheduler.signal("people")
            await scheduler.force()

        assert executor.execute.called
        assert scheduler._timer is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_synthesis_scheduler.py -v`
Expected: FAIL — `cockpit.engine.synthesis` doesn't exist yet.

### Task 3: Implement SynthesisScheduler core

**Files:**
- Create: `logos/engine/synthesis.py`

- [ ] **Step 3: Create the synthesis module**

```python
"""Synthesis scheduler — auto-triggers LLM synthesis after management data changes.

Accumulates filesystem change signals, waits for a quiet window,
then submits synthesis ActionPlans to the executor.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from cockpit.engine.delivery import DeliveryQueue
from cockpit.engine.executor import PhasedExecutor
from cockpit.engine.models import Action, ActionPlan, DeliveryItem

_log = logging.getLogger(__name__)

# ── Path classification ──────────────────────────────────────────────

HOT_PATH = frozenset({"people", "coaching", "feedback"})
WARM_PATH = frozenset({"meetings", "okrs", "goals", "incidents",
                        "postmortem-actions", "review-cycles"})
SYNTHESIS_RELEVANT = HOT_PATH | WARM_PATH

# Reschedule delay when suppressed (seconds)
_SUPPRESSION_DELAY = 60.0


# ── Synthesis handlers ───────────────────────────────────────────────

async def _synthesize_briefing() -> str:
    from agents.management_briefing import generate_briefing, format_briefing_md
    from shared.vault_writer import write_briefing_to_vault
    from shared.config import PROFILES_DIR

    briefing = await generate_briefing()
    md = format_briefing_md(briefing)
    write_briefing_to_vault(md)
    (PROFILES_DIR / "management-briefing.json").write_text(
        briefing.model_dump_json(indent=2)
    )
    return f"briefing: {briefing.headline}"


async def _synthesize_snapshot() -> str:
    from agents.management_prep import generate_team_snapshot, format_snapshot_md
    from shared.vault_writer import write_team_snapshot_to_vault

    snapshot = await generate_team_snapshot()
    write_team_snapshot_to_vault(format_snapshot_md(snapshot))
    return f"snapshot: {snapshot.headline}"


async def _synthesize_overview() -> str:
    from agents.management_prep import generate_overview, format_overview_md
    from shared.vault_writer import write_management_overview_to_vault

    overview = await generate_overview()
    write_management_overview_to_vault(format_overview_md(overview))
    return f"overview: {overview.headline}"


async def _synthesize_profile_light() -> str:
    from agents.management_profiler import (
        generate_and_load_management_facts, synthesize_profile,
        build_profile, save_profile, load_profile,
    )

    facts = generate_and_load_management_facts()
    existing = load_profile()
    synthesis = await synthesize_profile(facts)
    profile = build_profile(facts, synthesis, existing)
    save_profile(profile)
    return f"profile v{profile.version}: {len(facts)} facts"


# ── Scheduler ────────────────────────────────────────────────────────

class SynthesisScheduler:
    """Accumulate change signals, wait for quiet, trigger LLM synthesis."""

    def __init__(
        self,
        executor: PhasedExecutor,
        delivery: DeliveryQueue,
        agent_run_manager: object,
        ignore_fn: Callable[[Path], None] | None = None,
        quiet_window_s: float | None = None,
        profiler_interval_s: float | None = None,
        enabled: bool | None = None,
    ) -> None:
        self._executor = executor
        self._delivery = delivery
        self._arm = agent_run_manager
        self._ignore_fn = ignore_fn

        if quiet_window_s is None:
            quiet_window_s = float(
                os.environ.get("ENGINE_SYNTHESIS_QUIET_S", "180")
            )
        if profiler_interval_s is None:
            profiler_interval_s = float(
                os.environ.get("ENGINE_PROFILER_INTERVAL_S", "86400")
            )
        if enabled is None:
            enabled = os.environ.get(
                "ENGINE_SYNTHESIS_ENABLED", "true"
            ).lower() in ("true", "1", "yes")

        self._quiet_window_s = quiet_window_s
        self._profiler_interval_s = profiler_interval_s
        self._enabled = enabled

        # Mutable state
        self._dirty: set[str] = set()
        self._timer: asyncio.TimerHandle | None = None
        self._last_synthesis_at: float = 0.0
        self._profiler_dirty: bool = False
        self._last_profiler_at: float = 0.0
        self._running_synthesis: bool = False
        self._profiler_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the profiler check loop."""
        if not self._enabled:
            _log.info("SynthesisScheduler disabled")
            return

        # Initialize profiler timestamp from existing profile if available
        self._last_profiler_at = self._load_profiler_timestamp()

        self._profiler_task = asyncio.create_task(self._profiler_loop())
        _log.info("SynthesisScheduler started (quiet=%ss)", self._quiet_window_s)

    async def stop(self) -> None:
        """Stop the scheduler, cancelling pending work."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._profiler_task is not None:
            self._profiler_task.cancel()
            try:
                await self._profiler_task
            except asyncio.CancelledError:
                pass
            self._profiler_task = None
        _log.info("SynthesisScheduler stopped (dirty lost: %s)", self._dirty)

    def signal(self, subdirectory: str) -> None:
        """Receive a change signal from the engine."""
        if not self._enabled:
            return
        if subdirectory not in SYNTHESIS_RELEVANT:
            return

        self._dirty.add(subdirectory)
        self._profiler_dirty = True

        # Reset quiet-window timer
        if self._timer is not None:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(
            self._quiet_window_s, self._schedule_synthesis
        )

    async def force(self) -> None:
        """Force immediate synthesis, bypassing quiet window."""
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        await self._on_quiet_window()

    def status(self) -> dict:
        """Return scheduler status for API consumption."""
        return {
            "enabled": self._enabled,
            "dirty": sorted(self._dirty),
            "quiet_window_s": self._quiet_window_s,
            "timer_active": self._timer is not None,
            "last_synthesis_at": (
                datetime.fromtimestamp(
                    self._last_synthesis_at, tz=timezone.utc
                ).isoformat()
                if self._last_synthesis_at > 0
                else None
            ),
            "last_profiler_at": (
                datetime.fromtimestamp(
                    self._last_profiler_at, tz=timezone.utc
                ).isoformat()
                if self._last_profiler_at > 0
                else None
            ),
            "profiler_dirty": self._profiler_dirty,
        }

    # ── Internal ─────────────────────────────────────────────────────

    def _schedule_synthesis(self) -> None:
        """Called by the event loop when the quiet window expires."""
        self._timer = None
        asyncio.ensure_future(self._on_quiet_window())

    async def _on_quiet_window(self) -> None:
        """Execute reactive synthesis if conditions are met."""
        if self._running_synthesis:
            _log.info("Synthesis already running, rescheduling")
            self._reschedule(_SUPPRESSION_DELAY)
            return

        if getattr(self._arm, "is_running", False):
            _log.info("Manual agent running, rescheduling synthesis")
            self._reschedule(_SUPPRESSION_DELAY)
            return

        self._running_synthesis = True
        try:
            snapshot = frozenset(self._dirty)
            self._dirty.clear()

            if snapshot & HOT_PATH:
                await self._run_reactive_synthesis(snapshot)
        finally:
            self._running_synthesis = False

    async def _run_reactive_synthesis(self, snapshot: frozenset[str]) -> None:
        """Build and execute the reactive synthesis plan."""
        plan = ActionPlan(
            created_at=datetime.now(timezone.utc),
            trigger=None,
            actions=[
                Action(
                    name="synthesize_briefing",
                    handler=_synthesize_briefing,
                    phase=1,
                    priority=0,
                ),
                Action(
                    name="synthesize_snapshot",
                    handler=_synthesize_snapshot,
                    phase=1,
                    priority=1,
                ),
                Action(
                    name="synthesize_overview",
                    handler=_synthesize_overview,
                    phase=1,
                    priority=2,
                ),
            ],
        )

        try:
            await self._executor.execute(plan)
        except Exception:
            _log.exception("Synthesis executor failed")
            self._dirty |= HOT_PATH
            return

        # Check for individual action failures
        reactive_names = {"synthesize_briefing", "synthesize_snapshot", "synthesize_overview"}
        if any(name in plan.errors for name in reactive_names):
            _log.warning("Synthesis partial failure: %s", plan.errors)
            self._dirty |= HOT_PATH

        # Enqueue delivery items
        now = datetime.now(timezone.utc)
        for name, result in plan.results.items():
            self._delivery.enqueue(DeliveryItem(
                title=name,
                detail=str(result),
                priority="medium",
                category="generated",
                source_action=name,
                timestamp=now,
            ))
        for name, error in plan.errors.items():
            self._delivery.enqueue(DeliveryItem(
                title=f"{name} failed",
                detail=error,
                priority="high",
                category="error",
                source_action=name,
                timestamp=now,
            ))

        # Refresh cache so API serves fresh artifacts
        try:
            from cockpit.api.cache import cache
            await cache.refresh()
        except Exception:
            _log.exception("Post-synthesis cache refresh failed")

        self._last_synthesis_at = time.monotonic()
        _log.info("Reactive synthesis complete: %s", list(plan.results.keys()))

    def _reschedule(self, delay: float) -> None:
        """Reschedule the quiet-window timer."""
        if self._timer is not None:
            self._timer.cancel()
        loop = asyncio.get_running_loop()
        self._timer = loop.call_later(delay, self._schedule_synthesis)

    async def _profiler_loop(self) -> None:
        """Hourly check for profiler synthesis trigger."""
        # Wait 1 hour before first check (not immediately on startup)
        await asyncio.sleep(3600)

        while True:
            try:
                await self._check_profiler()
            except asyncio.CancelledError:
                raise
            except Exception:
                _log.exception("Profiler check failed")
            await asyncio.sleep(3600)

    async def _check_profiler(self) -> None:
        """Run profiler if dirty and interval elapsed."""
        if not self._profiler_dirty:
            return
        if (time.monotonic() - self._last_profiler_at) < self._profiler_interval_s:
            return
        if self._running_synthesis:
            return
        if getattr(self._arm, "is_running", False):
            return

        self._running_synthesis = True
        try:
            plan = ActionPlan(
                created_at=datetime.now(timezone.utc),
                trigger=None,
                actions=[
                    Action(
                        name="synthesize_profile",
                        handler=_synthesize_profile_light,
                        phase=1,
                        priority=0,
                    ),
                ],
            )
            await self._executor.execute(plan)

            if "synthesize_profile" not in plan.errors:
                self._profiler_dirty = False
                self._last_profiler_at = time.monotonic()

            now = datetime.now(timezone.utc)
            for name, result in plan.results.items():
                self._delivery.enqueue(DeliveryItem(
                    title=name,
                    detail=str(result),
                    priority="medium",
                    category="generated",
                    source_action=name,
                    timestamp=now,
                ))
        except Exception:
            _log.exception("Profiler synthesis failed")
        finally:
            self._running_synthesis = False

    def _load_profiler_timestamp(self) -> float:
        """Load last profiler run time from existing profile file."""
        try:
            from shared.config import PROFILES_DIR
            import json

            profile_path = PROFILES_DIR / "management-profile.json"
            if profile_path.is_file():
                data = json.loads(profile_path.read_text())
                updated = data.get("updated_at")
                if updated:
                    dt = datetime.fromisoformat(updated)
                    # Convert to monotonic-compatible offset
                    age = (datetime.now(timezone.utc) - dt).total_seconds()
                    return max(0.0, time.monotonic() - age)
        except Exception:
            _log.debug("Could not load profiler timestamp, starting fresh")
        return 0.0
```

- [ ] **Step 4: Run the core tests**

Run: `cd ai-agents && uv run pytest tests/test_synthesis_scheduler.py -v`
Expected: PASS for all 7 core tests.

- [ ] **Step 5: Commit**

```bash
git add logos/engine/synthesis.py tests/test_synthesis_scheduler.py
git commit -m "feat: add SynthesisScheduler with quiet-window batching and 4 handlers"
```

### Task 4: Add profiler and status tests

**Files:**
- Modify: `tests/test_synthesis_scheduler.py`

- [ ] **Step 6: Add remaining 7 tests**

Append to `tests/test_synthesis_scheduler.py`:

```python
class TestDisabled:
    def test_signal_noop_when_disabled(self):
        """signal() is a no-op when scheduler is disabled."""
        scheduler, _ = _make_scheduler(enabled=False)
        scheduler.signal("people")
        assert len(scheduler._dirty) == 0
        assert scheduler._timer is None


class TestProfiler:
    async def test_profiler_skipped_within_24h(self):
        """Recent profiler timestamp prevents re-run."""
        scheduler, executor = _make_scheduler(quiet_window_s=0.05)
        scheduler._profiler_dirty = True
        scheduler._last_profiler_at = time.monotonic()  # just ran

        await scheduler._check_profiler()
        assert not executor.execute.called

    async def test_profiler_fires_when_stale_and_dirty(self):
        """Old timestamp + dirty flag triggers profiler."""
        scheduler, executor = _make_scheduler(
            quiet_window_s=0.05,
            profiler_interval_s=0,  # no minimum interval
        )
        scheduler._profiler_dirty = True
        scheduler._last_profiler_at = 0.0  # never ran

        await scheduler._check_profiler()
        assert executor.execute.called
        plan = executor.execute.call_args[0][0]
        assert any(a.name == "synthesize_profile" for a in plan.actions)


class TestStop:
    async def test_stop_cancels_pending_timer(self):
        """stop() cancels timer and profiler loop."""
        scheduler, _ = _make_scheduler(quiet_window_s=999)
        scheduler.signal("people")
        assert scheduler._timer is not None

        # Simulate profiler task
        scheduler._profiler_task = asyncio.create_task(asyncio.sleep(999))

        await scheduler.stop()
        assert scheduler._timer is None
        assert scheduler._profiler_task is None


class TestStatus:
    def test_status_returns_scheduler_state(self):
        """Status dict has correct shape."""
        scheduler, _ = _make_scheduler()
        scheduler.signal("people")

        status = scheduler.status()
        assert "enabled" in status
        assert "dirty" in status
        assert "people" in status["dirty"]
        assert "quiet_window_s" in status
        assert "timer_active" in status
        assert "profiler_dirty" in status
        assert status["profiler_dirty"] is True

        # Cleanup
        if scheduler._timer:
            scheduler._timer.cancel()
```

(Also add `import time` to the test file imports.)

- [ ] **Step 7: Run all scheduler tests**

Run: `cd ai-agents && uv run pytest tests/test_synthesis_scheduler.py -v`
Expected: ALL 14 PASS

- [ ] **Step 8: Run full test suite to verify no regressions**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py tests/test_engine_rules.py tests/test_engine_executor.py tests/test_engine_reactive_rules.py tests/test_engine_integration.py tests/test_synthesis_scheduler.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add tests/test_synthesis_scheduler.py
git commit -m "test: add profiler, stop, and status tests for SynthesisScheduler"
```

---

## Chunk 3: Engine + API Integration

Wire the scheduler into the reactive engine and expose via API.

### Task 5: Wire SynthesisScheduler into ReactiveEngine

**Files:**
- Modify: `logos/engine/__init__.py`
- Modify: `logos/api/app.py:21`

- [ ] **Step 1: Update ReactiveEngine to accept agent_run_manager and create scheduler**

In `logos/engine/__init__.py`, make these changes:

1. Add import at top:

```python
from cockpit.engine.synthesis import SynthesisScheduler
```

2. Add `agent_run_manager` parameter to `__init__`:

```python
    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        enabled: bool | None = None,
        debounce_ms: int | None = None,
        llm_concurrency: int | None = None,
        delivery_interval_s: int | None = None,
        action_timeout_s: float | None = None,
        agent_run_manager: object | None = None,
    ) -> None:
```

3. After `self._delivery = ...` line, add:

```python
        self._scheduler = SynthesisScheduler(
            executor=self._executor,
            delivery=self._delivery,
            agent_run_manager=agent_run_manager,
            ignore_fn=self._watcher.ignore,
        )
```

4. In `_handle_change`, after `await self._executor.execute(plan)`, add:

```python
        self._scheduler.signal(event.subdirectory)
```

5. In `start()`, after `self.running = True`, add:

```python
        await self._scheduler.start()
```

6. In `stop()`, after `await self._delivery.stop()`, add:

```python
        await self._scheduler.stop()
```

7. In `status()`, add to the returned dict:

```python
            "synthesis": self._scheduler.status(),
```

8. Add a `force_synthesis` public method:

```python
    async def force_synthesis(self) -> None:
        """Force immediate synthesis, bypassing quiet window."""
        await self._scheduler.force()
```

- [ ] **Step 2: Update app.py to pass agent_run_manager**

In `logos/api/app.py` line 21, change:

```python
    engine = ReactiveEngine()
```

to:

```python
    engine = ReactiveEngine(agent_run_manager=agent_run_manager)
```

- [ ] **Step 3: Run engine tests to verify integration**

Run: `cd ai-agents && uv run pytest tests/test_engine_integration.py -v`
Expected: PASS (agent_run_manager defaults to None, scheduler is created but dormant)

- [ ] **Step 4: Commit**

```bash
git add logos/engine/__init__.py logos/api/app.py
git commit -m "feat: wire SynthesisScheduler into ReactiveEngine lifecycle"
```

### Task 6: Add cache freshness timestamps

**Files:**
- Modify: `logos/api/cache.py:17-34`

- [ ] **Step 5: Add timestamp fields and accessors to DataCache**

In `logos/api/cache.py`, add two new fields to `DataCache` and two accessor methods.

After `_refreshed_at: float = 0.0` (line 33), add:

```python
    _last_hot_change_at: float = 0.0
    _last_warm_change_at: float = 0.0
```

After `cache_age()` method, add:

```python
    def record_hot_change(self) -> None:
        """Record that a hot-path data change occurred now."""
        self._last_hot_change_at = time.monotonic()

    def record_warm_change(self) -> None:
        """Record that a warm-path data change occurred now."""
        self._last_warm_change_at = time.monotonic()

    def hot_change_age(self) -> int:
        """Seconds since last hot-path change, or -1 if none."""
        if self._last_hot_change_at == 0.0:
            return -1
        return int(time.monotonic() - self._last_hot_change_at)

    def warm_change_age(self) -> int:
        """Seconds since last warm-path change, or -1 if none."""
        if self._last_warm_change_at == 0.0:
            return -1
        return int(time.monotonic() - self._last_warm_change_at)
```

- [ ] **Step 6: Set timestamps from engine _handle_change**

In `logos/engine/__init__.py`, in `_handle_change()`, after the `self._scheduler.signal(...)` call, add:

```python
        from cockpit.engine.synthesis import HOT_PATH, WARM_PATH
        from cockpit.api.cache import cache as _cache

        if event.subdirectory in HOT_PATH:
            _cache.record_hot_change()
        elif event.subdirectory in WARM_PATH:
            _cache.record_warm_change()
```

- [ ] **Step 7: Run tests**

Run: `cd ai-agents && uv run pytest tests/test_engine_integration.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add logos/api/cache.py logos/engine/__init__.py
git commit -m "feat: add hot/warm change timestamps to cache for freshness signaling"
```

### Task 7: Add API endpoints

**Files:**
- Modify: `logos/api/routes/engine.py`
- Modify: `logos/api/routes/data.py`

- [ ] **Step 9: Add POST /api/engine/synthesize endpoint**

In `logos/api/routes/engine.py`, add after the `engine_rules` endpoint:

```python
@router.post("/synthesize")
async def engine_synthesize() -> dict:
    """Force immediate synthesis, bypassing quiet window."""
    engine = _get_engine()
    if engine is None:
        return {"status": "error", "message": "Engine not running"}
    await engine.force_synthesis()
    return {"status": "ok", "message": "Synthesis triggered"}
```

- [ ] **Step 10: Add _freshness metadata to artifact endpoints**

In `logos/api/routes/data.py`, add a helper and modify 4 endpoints.

Add helper after `_response()`:

```python
def _freshness_response(data: Any, *, hot: bool = True) -> JSONResponse:
    """Return JSON response with _freshness metadata for synthesis artifacts."""
    from cockpit.api.cache import cache as _cache

    if hot:
        change_age = _cache.hot_change_age()
    else:
        hot_age = _cache.hot_change_age()
        warm_age = _cache.warm_change_age()
        if hot_age >= 0 and warm_age >= 0:
            change_age = min(hot_age, warm_age)
        elif hot_age >= 0:
            change_age = hot_age
        elif warm_age >= 0:
            change_age = warm_age
        else:
            change_age = -1

    freshness = {
        "data_change_age": change_age,
    }

    if isinstance(data, dict) and data is not None:
        data = {**data, "_freshness": freshness}
    elif data is not None:
        data = {"data": data, "_freshness": freshness}

    return JSONResponse(
        content=data,
        headers={"X-Cache-Age": str(_cache.cache_age())},
    )
```

Modify the briefing endpoint:

```python
@router.get("/briefing")
async def get_briefing():
    return _freshness_response(cache.briefing, hot=True)
```

The management, nudges, goals, agents, team health, and other existing endpoints stay as-is (they are deterministic, not synthesis artifacts).

Note: The snapshot and overview data is not currently cached separately (they write to `DATA_DIR/references/`). The briefing is the primary synthesis artifact served via API. The profile is served from the `/api/profile` route (different router). Adding `_freshness` to the briefing endpoint demonstrates the pattern; snapshot/overview can be added when those endpoints exist.

- [ ] **Step 11: Run the full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q --timeout=30 -x`
Expected: ALL PASS

- [ ] **Step 12: Commit**

```bash
git add logos/api/routes/engine.py logos/api/routes/data.py
git commit -m "feat: add POST /api/engine/synthesize and briefing freshness metadata"
```

---

## Chunk 4: Final Verification

### Task 8: Run full test suite and verify

**Files:** None (verification only)

- [ ] **Step 1: Run all engine + scheduler tests**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py tests/test_engine_rules.py tests/test_engine_executor.py tests/test_engine_reactive_rules.py tests/test_engine_integration.py tests/test_synthesis_scheduler.py -v`
Expected: ALL PASS

- [ ] **Step 2: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: ALL PASS, no import errors

- [ ] **Step 3: Verify synthesis module imports cleanly**

Run: `cd ai-agents && uv run python -c "from cockpit.engine.synthesis import SynthesisScheduler, HOT_PATH, WARM_PATH; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify API app starts without errors**

Run: `cd ai-agents && timeout 3 uv run python -c "from cockpit.api.app import app; print('App created:', app.title)" 2>&1 || true`
Expected: `App created: management-logos-api`
