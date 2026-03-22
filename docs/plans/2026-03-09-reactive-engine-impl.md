# Reactive Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a filesystem-watching reactive engine inside the logos API that auto-cascades downstream outputs when data files change.

**Architecture:** Watchdog-based inotify watcher on DATA_DIR emits ChangeEvents. A rules engine evaluates events against 6 rules, producing ActionPlans. A phased async executor runs deterministic actions (phase 0), then LLM synthesis (phase 1), then queues delivery (phase 2). A batched delivery queue consolidates notifications respecting attention budget.

**Tech Stack:** Python 3.12, asyncio, watchdog (inotify), FastAPI, pydantic-ai (existing LLM agents), ntfy (existing notifications)

**Design doc:** `docs/plans/2026-03-09-reactive-engine-design.md`

---

### Task 1: Add watchdog dependency

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add watchdog to dependencies**

In `pyproject.toml`, add `watchdog` to the `dependencies` list:

```toml
dependencies = [
    "fastapi>=0.115.0",
    "jinja2>=3.1",
    "langfuse>=3.14.5",
    "matplotlib>=3.9",
    "ollama>=0.6.1",
    "pillow>=11.0.0",
    "pydantic>=2.12.5",
    "pydantic-ai[litellm]>=1.63.0",
    "pyyaml>=6.0",
    "qdrant-client>=1.17.0",
    "sse-starlette>=2.0.0",
    "uvicorn>=0.34.0",
    "watchdog>=4.0.0",
]
```

**Step 2: Sync dependencies**

Run: `cd ai-agents && uv sync`
Expected: resolves watchdog, installs successfully

**Step 3: Verify import**

Run: `cd ai-agents && uv run python -c "import watchdog; print(watchdog.__version__)"`
Expected: prints version >= 4.0.0

**Step 4: Commit**

```
feat: add watchdog dependency for reactive engine
```

---

### Task 2: Core data model — ChangeEvent, Action, ActionPlan, DeliveryItem

**Files:**
- Create: `logos/engine/__init__.py`
- Create: `logos/engine/models.py`
- Create: `tests/test_engine_models.py`

**Step 1: Create engine package**

Create `logos/engine/__init__.py`:

```python
"""Reactive engine — filesystem-watching event loop for automated cascades."""
```

**Step 2: Write the failing tests**

Create `tests/test_engine_models.py`:

```python
"""Tests for cockpit.engine.models — core data types."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from cockpit.engine.models import Action, ActionPlan, ChangeEvent, DeliveryItem


class TestChangeEvent:
    def test_construction(self):
        evt = ChangeEvent(
            path=Path("/data/people/alice.md"),
            subdirectory="people",
            event_type="created",
            doc_type="person",
            timestamp=datetime.now(timezone.utc),
        )
        assert evt.subdirectory == "people"
        assert evt.doc_type == "person"

    def test_doc_type_none_when_unknown(self):
        evt = ChangeEvent(
            path=Path("/data/inbox/random.txt"),
            subdirectory="inbox",
            event_type="created",
            doc_type=None,
            timestamp=datetime.now(timezone.utc),
        )
        assert evt.doc_type is None


class TestAction:
    def test_construction(self):
        handler = AsyncMock()
        action = Action(
            name="refresh_cache",
            handler=handler,
            args={},
            priority=0,
            phase=0,
            depends_on=[],
        )
        assert action.name == "refresh_cache"
        assert action.phase == 0

    def test_depends_on_default_empty(self):
        action = Action(
            name="test",
            handler=AsyncMock(),
            args={},
            priority=0,
            phase=0,
        )
        assert action.depends_on == []


class TestActionPlan:
    def test_construction(self):
        evt = ChangeEvent(
            path=Path("/data/inbox/doc.md"),
            subdirectory="inbox",
            event_type="created",
            doc_type=None,
            timestamp=datetime.now(timezone.utc),
        )
        plan = ActionPlan(trigger=evt, actions=[])
        assert plan.actions == []
        assert plan.results == {}

    def test_actions_by_phase(self):
        evt = ChangeEvent(
            path=Path("/data/inbox/doc.md"),
            subdirectory="inbox",
            event_type="created",
            doc_type=None,
            timestamp=datetime.now(timezone.utc),
        )
        a0 = Action(name="a", handler=AsyncMock(), args={}, priority=0, phase=0)
        a1 = Action(name="b", handler=AsyncMock(), args={}, priority=0, phase=1)
        a2 = Action(name="c", handler=AsyncMock(), args={}, priority=0, phase=2)
        plan = ActionPlan(trigger=evt, actions=[a1, a0, a2])
        by_phase = plan.actions_by_phase()
        assert list(by_phase.keys()) == [0, 1, 2]
        assert by_phase[0] == [a0]
        assert by_phase[1] == [a1]
        assert by_phase[2] == [a2]


class TestDeliveryItem:
    def test_construction(self):
        item = DeliveryItem(
            title="Prep generated for Alice",
            detail="1:1 prep based on updated person note",
            priority="medium",
            category="generated",
            source_action="generate_prep",
            timestamp=datetime.now(timezone.utc),
            artifacts=[Path("/data/meetings/prep-alice-2026-03-09.md")],
        )
        assert item.priority == "medium"
        assert len(item.artifacts) == 1
```

**Step 3: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cockpit.engine'`

**Step 4: Implement models**

Create `logos/engine/models.py`:

```python
"""Core data types for the reactive engine."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


@dataclass
class ChangeEvent:
    """A detected filesystem change in DATA_DIR."""

    path: Path
    subdirectory: str  # "people", "coaching", "meetings", "inbox", etc.
    event_type: str  # "created" | "modified" | "deleted"
    doc_type: str | None  # from frontmatter type: field, if parseable
    timestamp: datetime


@dataclass
class Action:
    """A single unit of work to execute."""

    name: str
    handler: Callable  # async callable
    args: dict = field(default_factory=dict)
    priority: int = 0  # lower = runs first within same phase
    phase: int = 0  # 0=deterministic, 1=LLM synthesis, 2=delivery
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ActionPlan:
    """Ordered set of actions produced by rule evaluation."""

    trigger: ChangeEvent
    actions: list[Action] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())
    results: dict[str, Any] = field(default_factory=dict)

    def actions_by_phase(self) -> dict[int, list[Action]]:
        """Group actions by phase, sorted by phase number."""
        grouped: dict[int, list[Action]] = defaultdict(list)
        for action in self.actions:
            grouped[action.phase].append(action)
        # Sort actions within each phase by priority
        for phase in grouped:
            grouped[phase].sort(key=lambda a: a.priority)
        return dict(sorted(grouped.items()))


@dataclass
class DeliveryItem:
    """A notification/output item queued for batched delivery."""

    title: str
    detail: str
    priority: str  # "critical" | "high" | "medium" | "low"
    category: str  # "generated" | "detected" | "warning" | "error"
    source_action: str
    timestamp: datetime
    artifacts: list[Path] = field(default_factory=list)
```

**Step 5: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_models.py -v`
Expected: all PASS

**Step 6: Commit**

```
feat: add reactive engine core data models
```

---

### Task 3: Filesystem watcher with debounce and ignore set

**Files:**
- Create: `logos/engine/watcher.py`
- Create: `tests/test_engine_watcher.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_watcher.py`:

```python
"""Tests for cockpit.engine.watcher — filesystem watcher with debounce."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from cockpit.engine.watcher import DataDirWatcher


def _write_md(path: Path, frontmatter: str, body: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


class TestDataDirWatcher:
    async def test_detects_file_creation(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "people").mkdir()
        await watcher.start()
        try:
            _write_md(tmp_path / "people" / "alice.md", "type: person\nname: Alice\n")
            await asyncio.sleep(0.2)  # wait for debounce
        finally:
            await watcher.stop()

        assert callback.call_count == 1
        evt = callback.call_args[0][0]
        assert evt.subdirectory == "people"
        assert evt.event_type == "created"
        assert evt.doc_type == "person"

    async def test_ignores_dotfiles(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "people").mkdir()
        await watcher.start()
        try:
            (tmp_path / "people" / ".hidden").write_text("secret")
            await asyncio.sleep(0.2)
        finally:
            await watcher.stop()

        callback.assert_not_called()

    async def test_ignores_processed_dir(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "processed").mkdir()
        await watcher.start()
        try:
            (tmp_path / "processed" / "old.md").write_text("archived")
            await asyncio.sleep(0.2)
        finally:
            await watcher.stop()

        callback.assert_not_called()

    async def test_self_trigger_prevention(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "coaching").mkdir()
        target = tmp_path / "coaching" / "starter.md"
        watcher.ignore(target)
        await watcher.start()
        try:
            _write_md(target, "type: coaching\n")
            await asyncio.sleep(0.2)
        finally:
            await watcher.stop()

        callback.assert_not_called()

    async def test_debounce_coalesces_events(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=100,
        )
        (tmp_path / "people").mkdir()
        await watcher.start()
        try:
            f = tmp_path / "people" / "alice.md"
            _write_md(f, "type: person\nname: Alice\n")
            await asyncio.sleep(0.02)
            # Modify same file quickly
            _write_md(f, "type: person\nname: Alice\ncognitive-load: high\n")
            await asyncio.sleep(0.3)  # wait past debounce
        finally:
            await watcher.stop()

        # Should coalesce into single event
        assert callback.call_count == 1

    async def test_enriches_frontmatter_type(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "coaching").mkdir()
        await watcher.start()
        try:
            _write_md(
                tmp_path / "coaching" / "delegation.md",
                "type: coaching\nperson: Alice\n",
            )
            await asyncio.sleep(0.2)
        finally:
            await watcher.stop()

        evt = callback.call_args[0][0]
        assert evt.doc_type == "coaching"

    async def test_non_md_file_has_no_doc_type(self, tmp_path: Path):
        callback = AsyncMock()
        watcher = DataDirWatcher(
            data_dir=tmp_path,
            on_change=callback,
            debounce_ms=50,
        )
        (tmp_path / "inbox").mkdir()
        await watcher.start()
        try:
            (tmp_path / "inbox" / "notes.txt").write_text("hello")
            await asyncio.sleep(0.2)
        finally:
            await watcher.stop()

        evt = callback.call_args[0][0]
        assert evt.doc_type is None
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_watcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cockpit.engine.watcher'`

**Step 3: Implement watcher**

Create `logos/engine/watcher.py`:

```python
"""Filesystem watcher with debounce and self-trigger prevention."""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import yaml
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from cockpit.engine.models import ChangeEvent

_log = logging.getLogger("cockpit.engine.watcher")

_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?", re.DOTALL)

_IGNORED_SUBDIRS = {"processed"}


def _parse_doc_type(path: Path) -> str | None:
    """Read frontmatter type: field from a markdown file."""
    if path.suffix not in (".md", ".markdown"):
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = _FM_RE.match(text)
    if not match:
        return None
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if isinstance(fm, dict):
        return fm.get("type")
    return None


def _subdirectory(data_dir: Path, path: Path) -> str:
    """Extract the first-level subdirectory name relative to data_dir."""
    try:
        rel = path.relative_to(data_dir)
    except ValueError:
        return ""
    parts = rel.parts
    return parts[0] if parts else ""


class DataDirWatcher:
    """Watch DATA_DIR for file changes with debounce and ignore set."""

    def __init__(
        self,
        data_dir: Path,
        on_change: callable,
        debounce_ms: int = 200,
    ):
        self._data_dir = data_dir
        self._on_change = on_change
        self._debounce_s = debounce_ms / 1000.0
        self._observer: Observer | None = None
        self._ignore_set: set[Path] = set()
        self._pending: dict[Path, asyncio.TimerHandle] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def ignore(self, path: Path) -> None:
        """Register a path to ignore (for self-trigger prevention)."""
        self._ignore_set.add(path.resolve())

    def unignore(self, path: Path) -> None:
        """Remove a path from the ignore set."""
        self._ignore_set.discard(path.resolve())

    async def start(self) -> None:
        """Start the filesystem observer."""
        self._loop = asyncio.get_running_loop()
        self._observer = Observer()
        handler = _Handler(self)
        self._observer.schedule(handler, str(self._data_dir), recursive=True)
        self._observer.start()
        _log.info("Watcher started on %s", self._data_dir)

    async def stop(self) -> None:
        """Stop the filesystem observer."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        # Cancel pending debounce timers
        for handle in self._pending.values():
            handle.cancel()
        self._pending.clear()
        _log.info("Watcher stopped")

    def _on_fs_event(self, path: Path, is_created: bool) -> None:
        """Called from watchdog thread — schedules debounced processing."""
        resolved = path.resolve()

        # Skip dotfiles
        if any(part.startswith(".") for part in path.parts):
            return

        # Skip ignored subdirectories
        subdir = _subdirectory(self._data_dir, resolved)
        if subdir in _IGNORED_SUBDIRS:
            return

        # Skip self-triggered files
        if resolved in self._ignore_set:
            self._ignore_set.discard(resolved)
            return

        # Debounce: cancel pending timer for this path, schedule new one
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(
                self._schedule_debounce, resolved, is_created
            )

    def _schedule_debounce(self, path: Path, is_created: bool) -> None:
        """Schedule debounced event emission (runs on asyncio loop)."""
        if path in self._pending:
            self._pending[path].cancel()

        handle = self._loop.call_later(
            self._debounce_s,
            lambda: asyncio.ensure_future(self._emit(path, is_created)),
        )
        self._pending[path] = handle

    async def _emit(self, path: Path, is_created: bool) -> None:
        """Emit a ChangeEvent after debounce window."""
        self._pending.pop(path, None)

        if not path.exists():
            return

        subdir = _subdirectory(self._data_dir, path)
        doc_type = _parse_doc_type(path)

        evt = ChangeEvent(
            path=path,
            subdirectory=subdir,
            event_type="created" if is_created else "modified",
            doc_type=doc_type,
            timestamp=datetime.now(timezone.utc),
        )
        _log.debug("Emitting: %s %s/%s", evt.event_type, subdir, path.name)
        try:
            await self._on_change(evt)
        except Exception:
            _log.exception("Error in change handler for %s", path)


class _Handler(FileSystemEventHandler):
    """Watchdog event handler — bridges to async DataDirWatcher."""

    def __init__(self, watcher: DataDirWatcher):
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._on_fs_event(Path(event.src_path), is_created=True)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._on_fs_event(Path(event.src_path), is_created=False)
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_watcher.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add filesystem watcher with debounce and ignore set
```

---

### Task 4: Rules engine — Rule dataclass and rule registry

**Files:**
- Create: `logos/engine/rules.py`
- Create: `tests/test_engine_rules.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_rules.py`:

```python
"""Tests for cockpit.engine.rules — rule evaluation and registry."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from cockpit.engine.models import ChangeEvent
from cockpit.engine.rules import Rule, RuleRegistry, evaluate_rules


def _event(subdir: str, name: str = "test.md", event_type: str = "created",
           doc_type: str | None = None) -> ChangeEvent:
    return ChangeEvent(
        path=Path(f"/data/{subdir}/{name}"),
        subdirectory=subdir,
        event_type=event_type,
        doc_type=doc_type,
        timestamp=datetime.now(timezone.utc),
    )


class TestRule:
    def test_matches_when_filter_true(self):
        rule = Rule(
            name="test_rule",
            trigger_filter=lambda evt: evt.subdirectory == "people",
            produce=lambda evt: [],
        )
        assert rule.trigger_filter(_event("people")) is True
        assert rule.trigger_filter(_event("coaching")) is False


class TestRuleRegistry:
    def test_register_and_list(self):
        registry = RuleRegistry()
        rule = Rule(
            name="test_rule",
            trigger_filter=lambda evt: True,
            produce=lambda evt: [],
        )
        registry.register(rule)
        assert len(registry.rules) == 1
        assert registry.rules[0].name == "test_rule"

    def test_no_duplicate_names(self):
        registry = RuleRegistry()
        rule1 = Rule(name="r", trigger_filter=lambda e: True, produce=lambda e: [])
        rule2 = Rule(name="r", trigger_filter=lambda e: True, produce=lambda e: [])
        registry.register(rule1)
        registry.register(rule2)
        assert len(registry.rules) == 1  # second registration replaces first


class TestEvaluateRules:
    def test_collects_actions_from_matching_rules(self):
        from cockpit.engine.models import Action
        handler = AsyncMock()
        rule_a = Rule(
            name="rule_a",
            trigger_filter=lambda evt: evt.subdirectory == "people",
            produce=lambda evt: [
                Action(name="refresh_cache", handler=handler, phase=0),
            ],
        )
        rule_b = Rule(
            name="rule_b",
            trigger_filter=lambda evt: evt.subdirectory == "people",
            produce=lambda evt: [
                Action(name="recalc_nudges", handler=handler, phase=0),
            ],
        )
        rule_c = Rule(
            name="rule_c",
            trigger_filter=lambda evt: evt.subdirectory == "inbox",
            produce=lambda evt: [
                Action(name="ingest", handler=handler, phase=0),
            ],
        )
        registry = RuleRegistry()
        registry.register(rule_a)
        registry.register(rule_b)
        registry.register(rule_c)

        plan = evaluate_rules(registry, _event("people"))
        names = [a.name for a in plan.actions]
        assert "refresh_cache" in names
        assert "recalc_nudges" in names
        assert "ingest" not in names

    def test_deduplicates_actions_by_name(self):
        from cockpit.engine.models import Action
        handler = AsyncMock()
        rule_a = Rule(
            name="rule_a",
            trigger_filter=lambda evt: True,
            produce=lambda evt: [
                Action(name="refresh_cache", handler=handler, phase=0),
            ],
        )
        rule_b = Rule(
            name="rule_b",
            trigger_filter=lambda evt: True,
            produce=lambda evt: [
                Action(name="refresh_cache", handler=handler, phase=0),
            ],
        )
        registry = RuleRegistry()
        registry.register(rule_a)
        registry.register(rule_b)

        plan = evaluate_rules(registry, _event("people"))
        names = [a.name for a in plan.actions]
        assert names.count("refresh_cache") == 1

    def test_returns_empty_plan_when_no_rules_match(self):
        registry = RuleRegistry()
        rule = Rule(
            name="inbox_only",
            trigger_filter=lambda evt: evt.subdirectory == "inbox",
            produce=lambda evt: [],
        )
        registry.register(rule)
        plan = evaluate_rules(registry, _event("people"))
        assert plan.actions == []
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_rules.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement rules engine**

Create `logos/engine/rules.py`:

```python
"""Rules engine — evaluates filesystem events against registered rules."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from cockpit.engine.models import Action, ActionPlan, ChangeEvent

_log = logging.getLogger("cockpit.engine.rules")


@dataclass
class Rule:
    """A reactive rule: filter + action producer."""

    name: str
    trigger_filter: Callable[[ChangeEvent], bool]
    produce: Callable[[ChangeEvent], list[Action]]
    description: str = ""


class RuleRegistry:
    """Registry of reactive rules."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules.values())

    def register(self, rule: Rule) -> None:
        """Register a rule (replaces existing with same name)."""
        self._rules[rule.name] = rule


def evaluate_rules(registry: RuleRegistry, event: ChangeEvent) -> ActionPlan:
    """Evaluate all rules against an event, return deduplicated ActionPlan."""
    actions: dict[str, Action] = {}  # deduplicate by name

    for rule in registry.rules:
        if rule.trigger_filter(event):
            _log.debug("Rule %s matched for %s", rule.name, event.path.name)
            try:
                produced = rule.produce(event)
                for action in produced:
                    if action.name not in actions:
                        actions[action.name] = action
            except Exception:
                _log.exception("Rule %s failed to produce actions", rule.name)

    return ActionPlan(trigger=event, actions=list(actions.values()))
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_rules.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add rules engine with registry and deduplication
```

---

### Task 5: Phased async executor

**Files:**
- Create: `logos/engine/executor.py`
- Create: `tests/test_engine_executor.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_executor.py`:

```python
"""Tests for cockpit.engine.executor — phased async action execution."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

from cockpit.engine.executor import PhasedExecutor
from cockpit.engine.models import Action, ActionPlan, ChangeEvent


def _event() -> ChangeEvent:
    return ChangeEvent(
        path=Path("/data/people/alice.md"),
        subdirectory="people",
        event_type="created",
        doc_type="person",
        timestamp=datetime.now(timezone.utc),
    )


class TestPhasedExecutor:
    async def test_executes_phase_0_actions(self):
        handler = AsyncMock(return_value="ok")
        plan = ActionPlan(
            trigger=_event(),
            actions=[Action(name="a", handler=handler, phase=0)],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        handler.assert_awaited_once()
        assert plan.results["a"] == "ok"

    async def test_phases_run_in_order(self):
        order = []

        async def phase0():
            order.append(0)

        async def phase1():
            order.append(1)

        async def phase2():
            order.append(2)

        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name="p2", handler=phase2, phase=2),
                Action(name="p0", handler=phase0, phase=0),
                Action(name="p1", handler=phase1, phase=1),
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        assert order == [0, 1, 2]

    async def test_actions_within_phase_run_concurrently(self):
        started = []
        finished = []

        async def slow_a():
            started.append("a")
            await asyncio.sleep(0.05)
            finished.append("a")

        async def slow_b():
            started.append("b")
            await asyncio.sleep(0.05)
            finished.append("b")

        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name="a", handler=slow_a, phase=0),
                Action(name="b", handler=slow_b, phase=0),
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        # Both should start before either finishes (concurrent)
        assert len(started) == 2
        assert len(finished) == 2

    async def test_failed_action_does_not_abort_plan(self):
        async def failing():
            raise RuntimeError("boom")

        success = AsyncMock(return_value="ok")
        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name="fail", handler=failing, phase=0),
                Action(name="ok", handler=success, phase=0),
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        success.assert_awaited_once()
        assert plan.results["ok"] == "ok"
        assert "fail" in plan.errors

    async def test_dependent_action_skipped_when_dependency_fails(self):
        async def failing():
            raise RuntimeError("boom")

        dependent = AsyncMock(return_value="should not run")
        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name="fail", handler=failing, phase=0),
                Action(name="dep", handler=dependent, phase=0, depends_on=["fail"]),
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        dependent.assert_not_awaited()
        assert "dep" in plan.skipped

    async def test_action_timeout(self):
        async def hanging():
            await asyncio.sleep(10)

        plan = ActionPlan(
            trigger=_event(),
            actions=[Action(name="hang", handler=hanging, phase=0)],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=0.1)
        await executor.execute(plan)

        assert "hang" in plan.errors

    async def test_llm_concurrency_bounded(self):
        """Phase 1 actions respect LLM concurrency limit."""
        concurrent = []
        max_concurrent = []

        async def llm_call():
            concurrent.append(1)
            max_concurrent.append(len(concurrent))
            await asyncio.sleep(0.05)
            concurrent.pop()

        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name=f"llm_{i}", handler=llm_call, phase=1)
                for i in range(4)
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        assert max(max_concurrent) <= 2

    async def test_handler_receives_args(self):
        handler = AsyncMock(return_value="ok")
        plan = ActionPlan(
            trigger=_event(),
            actions=[
                Action(name="a", handler=handler, args={"person": "Alice"}, phase=0),
            ],
        )
        executor = PhasedExecutor(llm_concurrency=2, action_timeout_s=10)
        await executor.execute(plan)

        handler.assert_awaited_once_with(person="Alice")
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_executor.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement executor**

Create `logos/engine/executor.py`:

```python
"""Phased async executor — runs ActionPlans with bounded concurrency."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from cockpit.engine.models import Action, ActionPlan

_log = logging.getLogger("cockpit.engine.executor")


@dataclass
class PhasedExecutor:
    """Execute ActionPlans in phase order with bounded LLM concurrency."""

    llm_concurrency: int = 2
    action_timeout_s: float = 60.0
    _llm_semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._llm_semaphore = asyncio.Semaphore(self.llm_concurrency)

    async def execute(self, plan: ActionPlan) -> None:
        """Execute all actions in phase order."""
        plan.errors = getattr(plan, "errors", {})
        plan.skipped = getattr(plan, "skipped", set())

        by_phase = plan.actions_by_phase()
        for phase_num in sorted(by_phase.keys()):
            actions = by_phase[phase_num]
            await self._run_phase(plan, actions, phase_num)

    async def _run_phase(
        self, plan: ActionPlan, actions: list[Action], phase: int
    ) -> None:
        """Run all actions in a phase concurrently (respecting dependencies)."""
        tasks: dict[str, asyncio.Task] = {}
        pending = list(actions)

        async def _run_action(action: Action) -> None:
            # Check dependencies
            for dep in action.depends_on:
                if dep in plan.errors or dep in plan.skipped:
                    plan.skipped.add(action.name)
                    _log.info("Skipping %s (dependency %s failed)", action.name, dep)
                    return

            sem = self._llm_semaphore if phase >= 1 else asyncio.Semaphore(999)
            async with sem:
                try:
                    result = await asyncio.wait_for(
                        action.handler(**action.args),
                        timeout=self.action_timeout_s,
                    )
                    plan.results[action.name] = result
                    _log.info("Action %s completed (phase %d)", action.name, phase)
                except asyncio.TimeoutError:
                    plan.errors[action.name] = "timeout"
                    _log.warning("Action %s timed out", action.name)
                except Exception as exc:
                    plan.errors[action.name] = str(exc)
                    _log.warning("Action %s failed: %s", action.name, exc)

        async with asyncio.TaskGroup() as tg:
            for action in pending:
                tg.create_task(_run_action(action))
```

Note: `ActionPlan` needs `errors` and `skipped` fields. Update `logos/engine/models.py` to add:

```python
@dataclass
class ActionPlan:
    trigger: ChangeEvent
    actions: list[Action] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)
    # ... rest unchanged
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_executor.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add phased async executor with bounded LLM concurrency
```

---

### Task 6: Delivery queue with batching

**Files:**
- Create: `logos/engine/delivery.py`
- Create: `tests/test_engine_delivery.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_delivery.py`:

```python
"""Tests for cockpit.engine.delivery — batched notification queue."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from cockpit.engine.delivery import DeliveryQueue
from cockpit.engine.models import DeliveryItem


def _item(title: str = "Test", priority: str = "medium") -> DeliveryItem:
    return DeliveryItem(
        title=title,
        detail="detail",
        priority=priority,
        category="generated",
        source_action="test",
        timestamp=datetime.now(timezone.utc),
    )


class TestDeliveryQueue:
    def test_enqueue_adds_item(self):
        q = DeliveryQueue(flush_interval_s=300)
        q.enqueue(_item())
        assert len(q.pending) == 1

    def test_recent_ring_buffer(self):
        q = DeliveryQueue(flush_interval_s=300, max_recent=3)
        for i in range(5):
            q.enqueue(_item(title=f"item-{i}"))
        # Pending has all 5
        assert len(q.pending) == 5
        # Recent ring buffer capped at 3
        assert len(q.recent) == 3
        assert q.recent[0].title == "item-2"

    @patch("cockpit.engine.delivery._send_notification")
    async def test_flush_sends_consolidated(self, mock_send: MagicMock):
        q = DeliveryQueue(flush_interval_s=300)
        q.enqueue(_item(title="A"))
        q.enqueue(_item(title="B"))
        await q.flush()

        mock_send.assert_called_once()
        msg = mock_send.call_args[1]["message"]
        assert "A" in msg
        assert "B" in msg
        assert len(q.pending) == 0

    @patch("cockpit.engine.delivery._send_notification")
    async def test_critical_triggers_immediate_send(self, mock_send: MagicMock):
        q = DeliveryQueue(flush_interval_s=300)
        q.enqueue(_item(title="Urgent", priority="critical"))

        # Critical items should be flushed immediately
        # (enqueue calls _maybe_flush_critical internally)
        await asyncio.sleep(0.05)
        mock_send.assert_called_once()
        msg = mock_send.call_args[1]["message"]
        assert "Urgent" in msg

    @patch("cockpit.engine.delivery._send_notification")
    async def test_flush_noop_when_empty(self, mock_send: MagicMock):
        q = DeliveryQueue(flush_interval_s=300)
        await q.flush()
        mock_send.assert_not_called()

    @patch("cockpit.engine.delivery._send_notification")
    async def test_high_priority_flushes_within_60s(self, mock_send: MagicMock):
        q = DeliveryQueue(flush_interval_s=300)
        q.enqueue(_item(title="High", priority="high"))
        # High items should schedule a flush within 60s
        assert q._high_flush_scheduled is True

    def test_format_batch_message(self):
        q = DeliveryQueue(flush_interval_s=300)
        items = [_item(title="A"), _item(title="B"), _item(title="C")]
        msg = q._format_batch(items)
        assert "3 updates" in msg
        assert "A" in msg
        assert "B" in msg
        assert "C" in msg

    def test_format_single_item(self):
        q = DeliveryQueue(flush_interval_s=300)
        items = [_item(title="Solo")]
        msg = q._format_batch(items)
        assert "Solo" in msg
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_delivery.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement delivery queue**

Create `logos/engine/delivery.py`:

```python
"""Batched delivery queue — consolidates notifications respecting attention budget."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from cockpit.engine.models import DeliveryItem

_log = logging.getLogger("cockpit.engine.delivery")

HIGH_FLUSH_DELAY_S = 60  # high priority items flush within this window


def _send_notification(*, title: str, message: str, priority: str = "default") -> bool:
    """Send via ntfy (wraps shared.notify)."""
    try:
        from shared.notify import send_notification
        return send_notification(title, message, priority=priority)
    except Exception:
        _log.exception("Notification send failed")
        return False


@dataclass
class DeliveryQueue:
    """Queue that batches delivery items and flushes on interval."""

    flush_interval_s: int = 300
    max_recent: int = 50

    pending: list[DeliveryItem] = field(default_factory=list)
    recent: deque[DeliveryItem] = field(default_factory=lambda: deque(maxlen=50))
    _flush_task: asyncio.Task | None = field(default=None, repr=False)
    _high_flush_handle: asyncio.TimerHandle | None = field(default=None, repr=False)
    _high_flush_scheduled: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        self.recent = deque(maxlen=self.max_recent)

    def enqueue(self, item: DeliveryItem) -> None:
        """Add item to pending queue and recent ring buffer."""
        self.pending.append(item)
        self.recent.append(item)
        _log.debug("Queued: %s [%s]", item.title, item.priority)

        if item.priority == "critical":
            self._schedule_critical_flush()
        elif item.priority == "high" and not self._high_flush_scheduled:
            self._schedule_high_flush()

    def _schedule_critical_flush(self) -> None:
        """Flush critical items immediately (next event loop tick)."""
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon(lambda: asyncio.ensure_future(self.flush()))
        except RuntimeError:
            pass  # no running loop (testing without async)

    def _schedule_high_flush(self) -> None:
        """Schedule flush within HIGH_FLUSH_DELAY_S for high-priority items."""
        self._high_flush_scheduled = True
        try:
            loop = asyncio.get_running_loop()
            self._high_flush_handle = loop.call_later(
                HIGH_FLUSH_DELAY_S,
                lambda: asyncio.ensure_future(self._high_flush()),
            )
        except RuntimeError:
            pass

    async def _high_flush(self) -> None:
        self._high_flush_scheduled = False
        await self.flush()

    async def flush(self) -> None:
        """Flush pending items as a consolidated notification."""
        if not self.pending:
            return

        items = list(self.pending)
        self.pending.clear()

        # Determine notification priority from highest-priority item
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ntfy_priority = min(items, key=lambda i: priority_order.get(i.priority, 3)).priority
        ntfy_map = {"critical": "urgent", "high": "high", "medium": "default", "low": "low"}

        message = self._format_batch(items)
        title = f"Cockpit — {len(items)} update{'s' if len(items) != 1 else ''}"
        if len(items) == 1:
            title = f"Cockpit — {items[0].title}"

        await asyncio.to_thread(
            _send_notification,
            title=title,
            message=message,
            priority=ntfy_map.get(ntfy_priority, "default"),
        )
        _log.info("Flushed %d delivery items", len(items))

    def _format_batch(self, items: list[DeliveryItem]) -> str:
        """Format items into a consolidated notification message."""
        if len(items) == 1:
            item = items[0]
            return f"{item.title}\n{item.detail}"

        lines = [f"{len(items)} updates:"]
        for item in items:
            lines.append(f"• {item.title}")
        return "\n".join(lines)

    async def start_flush_loop(self) -> None:
        """Start periodic flush loop."""
        async def _loop():
            while True:
                await asyncio.sleep(self.flush_interval_s)
                await self.flush()

        self._flush_task = asyncio.create_task(_loop())

    async def stop(self) -> None:
        """Stop flush loop and send remaining items."""
        if self._flush_task:
            self._flush_task.cancel()
            self._flush_task = None
        if self._high_flush_handle:
            self._high_flush_handle.cancel()
        await self.flush()
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_delivery.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add batched delivery queue with critical/high priority overrides
```

---

### Task 7: Concrete reactive rules (the 6 rules)

**Files:**
- Create: `logos/engine/reactive_rules.py`
- Create: `tests/test_engine_reactive_rules.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_reactive_rules.py`. Key tests per rule — each test verifies: trigger_filter matches the right events, produce returns the expected action names, and action handlers are wired to the correct functions.

```python
"""Tests for cockpit.engine.reactive_rules — the 6 concrete reactive rules."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from cockpit.engine.models import ChangeEvent
from cockpit.engine.reactive_rules import build_default_rules


def _event(subdir: str, name: str = "test.md", event_type: str = "created",
           doc_type: str | None = None) -> ChangeEvent:
    return ChangeEvent(
        path=Path(f"/data/{subdir}/{name}"),
        subdirectory=subdir,
        event_type=event_type,
        doc_type=doc_type,
        timestamp=datetime.now(timezone.utc),
    )


class TestInboxIngestRule:
    def test_matches_inbox_created(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "inbox_ingest")
        assert rule.trigger_filter(_event("inbox", event_type="created"))
        assert not rule.trigger_filter(_event("people", event_type="created"))

    def test_produces_ingest_action(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "inbox_ingest")
        actions = rule.produce(_event("inbox", "transcript.md"))
        names = [a.name for a in actions]
        assert "ingest_document" in names

    def test_does_not_match_modified(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "inbox_ingest")
        assert not rule.trigger_filter(_event("inbox", event_type="modified"))


class TestMeetingCascadeRule:
    def test_matches_meetings_created_or_modified(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "meeting_cascade")
        assert rule.trigger_filter(_event("meetings", event_type="created"))
        assert rule.trigger_filter(_event("meetings", event_type="modified"))
        assert not rule.trigger_filter(_event("people"))

    def test_produces_refresh_and_optional_prep(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "meeting_cascade")
        actions = rule.produce(_event("meetings", "standup-2026-03-09.md",
                                      doc_type="meeting"))
        names = [a.name for a in actions]
        assert "refresh_cache" in names


class TestPersonChangedRule:
    def test_matches_people_dir(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "person_changed")
        assert rule.trigger_filter(_event("people", event_type="created"))
        assert rule.trigger_filter(_event("people", event_type="modified"))

    def test_produces_refresh_nudges_health(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "person_changed")
        actions = rule.produce(_event("people", "alice.md", doc_type="person"))
        names = [a.name for a in actions]
        assert "refresh_cache" in names
        assert "recalc_nudges" in names
        assert "recalc_team_health" in names


class TestCoachingChangedRule:
    def test_matches_coaching_dir(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "coaching_changed")
        assert rule.trigger_filter(_event("coaching"))
        assert not rule.trigger_filter(_event("feedback"))

    def test_produces_refresh_and_nudges(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "coaching_changed")
        actions = rule.produce(_event("coaching"))
        names = [a.name for a in actions]
        assert "refresh_cache" in names
        assert "recalc_nudges" in names


class TestFeedbackChangedRule:
    def test_matches_feedback_dir(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "feedback_changed")
        assert rule.trigger_filter(_event("feedback"))
        assert not rule.trigger_filter(_event("coaching"))

    def test_produces_refresh_and_nudges(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "feedback_changed")
        actions = rule.produce(_event("feedback"))
        names = [a.name for a in actions]
        assert "refresh_cache" in names
        assert "recalc_nudges" in names


class TestDecisionLoggedRule:
    def test_matches_decisions_created_only(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "decision_logged")
        assert rule.trigger_filter(_event("decisions", event_type="created"))
        assert not rule.trigger_filter(_event("decisions", event_type="modified"))

    def test_produces_refresh(self):
        registry = build_default_rules()
        rule = next(r for r in registry.rules if r.name == "decision_logged")
        actions = rule.produce(_event("decisions"))
        names = [a.name for a in actions]
        assert "refresh_cache" in names


class TestAllRulesRegistered:
    def test_six_rules(self):
        registry = build_default_rules()
        assert len(registry.rules) == 6
        names = {r.name for r in registry.rules}
        assert names == {
            "inbox_ingest", "meeting_cascade", "person_changed",
            "coaching_changed", "feedback_changed", "decision_logged",
        }
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_reactive_rules.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implement the 6 rules**

Create `logos/engine/reactive_rules.py`:

```python
"""Concrete reactive rules for the management cockpit.

Each rule maps a filesystem trigger to a list of actions that call
existing agent/collector functions directly (no subprocess spawning).
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from cockpit.engine.models import Action, ChangeEvent
from cockpit.engine.rules import Rule, RuleRegistry

_log = logging.getLogger("cockpit.engine.rules")


# ── Action handlers (thin async wrappers around existing functions) ──────


async def _refresh_cache() -> str:
    """Refresh the cockpit data cache."""
    from cockpit.api.cache import cache
    await cache.refresh()
    return "cache refreshed"


async def _recalc_nudges() -> str:
    """Recalculate nudges (runs after cache refresh)."""
    from cockpit.data.nudges import collect_nudges
    result = await asyncio.to_thread(collect_nudges)
    from cockpit.api.cache import cache
    cache.nudges = result
    return f"{len(result)} nudges"


async def _recalc_team_health() -> str:
    """Recalculate team health (runs after cache refresh)."""
    from cockpit.data.team_health import collect_team_health
    result = await asyncio.to_thread(collect_team_health)
    from cockpit.api.cache import cache
    cache.team_health = result
    return f"{len(result.teams)} teams"


async def _ingest_document(path: Path) -> str:
    """Classify and route an inbox document."""
    from agents.ingest import classify_document, process_document
    doc_type = classify_document(path)
    result = await process_document(path, doc_type)
    return f"ingested as {result.doc_type.value}"


async def _extract_meeting(path: Path) -> str:
    """Extract structured data from a meeting file via LLM."""
    from agents.meeting_lifecycle import process_meeting, route_extractions
    extraction = await process_meeting(path)
    created = route_extractions(extraction, path)
    return f"extracted {len(created)} items"


async def _generate_prep(person_name: str) -> str:
    """Generate 1:1 prep for a person."""
    from agents.management_prep import generate_1on1_prep
    from shared.vault_writer import write_1on1_prep_to_vault
    prep = await generate_1on1_prep(person_name)
    # Format and save
    from agents.management_prep import format_prep_md
    md = format_prep_md(prep, person_name)
    write_1on1_prep_to_vault(person_name, md)
    return f"prep for {person_name}"


# ── Rule definitions ─────────────────────────────────────────────────────


def _rule_inbox_ingest() -> Rule:
    """New file in inbox/ → classify, route, and extract if transcript."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "inbox" and evt.event_type == "created"

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="ingest_document",
                handler=_ingest_document,
                args={"path": evt.path},
                phase=0,
                priority=0,
            ),
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=10,
                depends_on=["ingest_document"],
            ),
        ]

    return Rule(
        name="inbox_ingest",
        trigger_filter=trigger,
        produce=produce,
        description="Classify and route new inbox files",
    )


def _rule_meeting_cascade() -> Rule:
    """Meeting file created/modified → refresh cache, optionally regenerate prep."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "meetings" and evt.event_type in ("created", "modified")

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ]

    return Rule(
        name="meeting_cascade",
        trigger_filter=trigger,
        produce=produce,
        description="Refresh state when meeting files change",
    )


def _rule_person_changed() -> Rule:
    """Person file created/modified → refresh cache, recalc nudges + team health."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "people" and evt.event_type in ("created", "modified")

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
            Action(
                name="recalc_nudges",
                handler=_recalc_nudges,
                phase=0,
                priority=10,
                depends_on=["refresh_cache"],
            ),
            Action(
                name="recalc_team_health",
                handler=_recalc_team_health,
                phase=0,
                priority=10,
                depends_on=["refresh_cache"],
            ),
        ]

    return Rule(
        name="person_changed",
        trigger_filter=trigger,
        produce=produce,
        description="Refresh state and recalculate nudges/health on person changes",
    )


def _rule_coaching_changed() -> Rule:
    """Coaching file created/modified → refresh cache, recalc nudges."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "coaching" and evt.event_type in ("created", "modified")

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
            Action(
                name="recalc_nudges",
                handler=_recalc_nudges,
                phase=0,
                priority=10,
                depends_on=["refresh_cache"],
            ),
        ]

    return Rule(
        name="coaching_changed",
        trigger_filter=trigger,
        produce=produce,
        description="Refresh state and recalculate nudges on coaching changes",
    )


def _rule_feedback_changed() -> Rule:
    """Feedback file created/modified → refresh cache, recalc nudges."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "feedback" and evt.event_type in ("created", "modified")

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
            Action(
                name="recalc_nudges",
                handler=_recalc_nudges,
                phase=0,
                priority=10,
                depends_on=["refresh_cache"],
            ),
        ]

    return Rule(
        name="feedback_changed",
        trigger_filter=trigger,
        produce=produce,
        description="Refresh state and recalculate nudges on feedback changes",
    )


def _rule_decision_logged() -> Rule:
    """Decision file created → refresh cache."""
    def trigger(evt: ChangeEvent) -> bool:
        return evt.subdirectory == "decisions" and evt.event_type == "created"

    def produce(evt: ChangeEvent) -> list[Action]:
        return [
            Action(
                name="refresh_cache",
                handler=_refresh_cache,
                phase=0,
                priority=0,
            ),
        ]

    return Rule(
        name="decision_logged",
        trigger_filter=trigger,
        produce=produce,
        description="Refresh state when decisions are logged",
    )


def build_default_rules() -> RuleRegistry:
    """Build the default rule registry with all 6 reactive rules."""
    registry = RuleRegistry()
    registry.register(_rule_inbox_ingest())
    registry.register(_rule_meeting_cascade())
    registry.register(_rule_person_changed())
    registry.register(_rule_coaching_changed())
    registry.register(_rule_feedback_changed())
    registry.register(_rule_decision_logged())
    return registry
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_reactive_rules.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add 6 concrete reactive rules for data cascades
```

---

### Task 8: ReactiveEngine — top-level orchestrator

**Files:**
- Modify: `logos/engine/__init__.py`
- Create: `tests/test_engine_integration.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_integration.py`:

```python
"""Integration tests for the ReactiveEngine — watcher → rules → executor → delivery."""
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from cockpit.engine import ReactiveEngine


def _write_md(path: Path, frontmatter: str, body: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


class TestReactiveEngine:
    async def test_start_and_stop(self, tmp_path: Path):
        engine = ReactiveEngine(data_dir=tmp_path, enabled=True, debounce_ms=50)
        await engine.start()
        assert engine.running
        await engine.stop()
        assert not engine.running

    async def test_disabled_engine_does_nothing(self, tmp_path: Path):
        engine = ReactiveEngine(data_dir=tmp_path, enabled=False)
        await engine.start()
        assert not engine.running

    @patch("cockpit.engine.reactive_rules._refresh_cache", new_callable=AsyncMock)
    @patch("cockpit.engine.reactive_rules._recalc_nudges", new_callable=AsyncMock)
    @patch("cockpit.engine.reactive_rules._recalc_team_health", new_callable=AsyncMock)
    async def test_person_file_triggers_cascade(
        self, mock_health, mock_nudges, mock_refresh, tmp_path: Path
    ):
        mock_refresh.return_value = "ok"
        mock_nudges.return_value = "ok"
        mock_health.return_value = "ok"

        (tmp_path / "people").mkdir()
        engine = ReactiveEngine(data_dir=tmp_path, enabled=True, debounce_ms=50)
        await engine.start()
        try:
            _write_md(tmp_path / "people" / "alice.md", "type: person\nname: Alice\n")
            await asyncio.sleep(0.5)  # wait for debounce + execution
        finally:
            await engine.stop()

        mock_refresh.assert_awaited()

    async def test_engine_status(self, tmp_path: Path):
        engine = ReactiveEngine(data_dir=tmp_path, enabled=True, debounce_ms=50)
        status = engine.status()
        assert status["running"] is False
        await engine.start()
        status = engine.status()
        assert status["running"] is True
        await engine.stop()

    async def test_recent_items_accessible(self, tmp_path: Path):
        engine = ReactiveEngine(data_dir=tmp_path, enabled=True, debounce_ms=50)
        assert list(engine.recent_items()) == []
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_integration.py -v`
Expected: FAIL

**Step 3: Implement ReactiveEngine**

Update `logos/engine/__init__.py`:

```python
"""Reactive engine — filesystem-watching event loop for automated cascades."""
from __future__ import annotations

import asyncio
import logging
import os
from collections import deque
from pathlib import Path

from shared.config import DATA_DIR

from cockpit.engine.delivery import DeliveryQueue
from cockpit.engine.executor import PhasedExecutor
from cockpit.engine.models import ChangeEvent, DeliveryItem
from cockpit.engine.reactive_rules import build_default_rules
from cockpit.engine.rules import evaluate_rules
from cockpit.engine.watcher import DataDirWatcher

_log = logging.getLogger("cockpit.engine")


class ReactiveEngine:
    """Top-level orchestrator: watcher → rules → executor → delivery."""

    def __init__(
        self,
        data_dir: Path | None = None,
        enabled: bool | None = None,
        debounce_ms: int | None = None,
        llm_concurrency: int | None = None,
        delivery_interval_s: int | None = None,
        action_timeout_s: float | None = None,
    ):
        self._data_dir = data_dir or DATA_DIR
        self._enabled = enabled if enabled is not None else (
            os.environ.get("ENGINE_ENABLED", "true").lower() == "true"
        )
        _debounce = debounce_ms or int(os.environ.get("ENGINE_DEBOUNCE_MS", "200"))
        _llm = llm_concurrency or int(os.environ.get("ENGINE_LLM_CONCURRENCY", "2"))
        _delivery = delivery_interval_s or int(
            os.environ.get("ENGINE_DELIVERY_INTERVAL_S", "300")
        )
        _timeout = action_timeout_s or float(
            os.environ.get("ENGINE_ACTION_TIMEOUT_S", "60")
        )

        self._registry = build_default_rules()
        self._executor = PhasedExecutor(llm_concurrency=_llm, action_timeout_s=_timeout)
        self._delivery = DeliveryQueue(flush_interval_s=_delivery)
        self._watcher = DataDirWatcher(
            data_dir=self._data_dir,
            on_change=self._handle_change,
            debounce_ms=_debounce,
        )
        self.running = False

    async def start(self) -> None:
        """Start the reactive engine."""
        if not self._enabled:
            _log.info("Reactive engine disabled (ENGINE_ENABLED=false)")
            return
        await self._watcher.start()
        await self._delivery.start_flush_loop()
        self.running = True
        _log.info("Reactive engine started (watching %s)", self._data_dir)

    async def stop(self) -> None:
        """Stop the reactive engine."""
        if not self.running:
            return
        await self._watcher.stop()
        await self._delivery.stop()
        self.running = False
        _log.info("Reactive engine stopped")

    async def _handle_change(self, event: ChangeEvent) -> None:
        """Process a filesystem change event through the rules engine."""
        plan = evaluate_rules(self._registry, event)
        if not plan.actions:
            _log.debug("No rules matched for %s", event.path.name)
            return

        _log.info(
            "Event %s/%s → %d actions",
            event.subdirectory,
            event.path.name,
            len(plan.actions),
        )

        # Register output paths in ignore set before execution
        # (actions that create files should call watcher.ignore())
        await self._executor.execute(plan)

        # Queue delivery items for completed actions
        for name, result in plan.results.items():
            self._delivery.enqueue(DeliveryItem(
                title=f"{name}: {result}" if isinstance(result, str) else name,
                detail=f"Triggered by {event.event_type} in {event.subdirectory}/",
                priority="medium",
                category="generated",
                source_action=name,
                timestamp=event.timestamp,
            ))

        # Errors get warning-level delivery items
        for name, error in getattr(plan, "errors", {}).items():
            self._delivery.enqueue(DeliveryItem(
                title=f"FAILED: {name}",
                detail=f"Error: {error}",
                priority="high",
                category="error",
                source_action=name,
                timestamp=event.timestamp,
            ))

    def status(self) -> dict:
        """Return engine status for API."""
        return {
            "running": self.running,
            "enabled": self._enabled,
            "rules_count": len(self._registry.rules),
            "pending_delivery": len(self._delivery.pending),
        }

    def recent_items(self) -> list[DeliveryItem]:
        """Return recent delivery items for API."""
        return list(self._delivery.recent)

    def rule_descriptions(self) -> list[dict]:
        """Return rule names and descriptions for API."""
        return [
            {"name": r.name, "description": r.description}
            for r in self._registry.rules
        ]
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_integration.py -v`
Expected: all PASS

**Step 5: Commit**

```
feat: add ReactiveEngine orchestrator
```

---

### Task 9: API endpoints for engine status

**Files:**
- Create: `logos/api/routes/engine.py`
- Modify: `logos/api/app.py`
- Create: `tests/test_engine_routes.py`

**Step 1: Write the failing tests**

Create `tests/test_engine_routes.py`:

```python
"""Tests for cockpit.api.routes.engine — engine status endpoints."""
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestEngineRoutes:
    def _client(self):
        from cockpit.api.app import app
        return TestClient(app, raise_server_errors=False)

    @patch("cockpit.api.routes.engine._get_engine")
    def test_engine_status(self, mock_engine):
        mock_engine.return_value = MagicMock(
            status=lambda: {"running": True, "enabled": True, "rules_count": 6, "pending_delivery": 0}
        )
        resp = self._client().get("/api/engine/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["running"] is True

    @patch("cockpit.api.routes.engine._get_engine")
    def test_engine_recent(self, mock_engine):
        mock_engine.return_value = MagicMock(recent_items=lambda: [])
        resp = self._client().get("/api/engine/recent")
        assert resp.status_code == 200
        assert resp.json() == []

    @patch("cockpit.api.routes.engine._get_engine")
    def test_engine_rules(self, mock_engine):
        mock_engine.return_value = MagicMock(
            rule_descriptions=lambda: [{"name": "inbox_ingest", "description": "test"}]
        )
        resp = self._client().get("/api/engine/rules")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_engine_routes.py -v`
Expected: FAIL

**Step 3: Implement engine routes**

Create `logos/api/routes/engine.py`:

```python
"""Engine status API routes."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/engine", tags=["engine"])

# Engine instance is set by app lifespan
_engine_instance = None


def set_engine(engine) -> None:
    """Called by app lifespan to register the engine instance."""
    global _engine_instance
    _engine_instance = engine


def _get_engine():
    return _engine_instance


@router.get("/status")
async def engine_status():
    engine = _get_engine()
    if engine is None:
        return {"running": False, "enabled": False, "rules_count": 0, "pending_delivery": 0}
    return engine.status()


@router.get("/recent")
async def engine_recent():
    engine = _get_engine()
    if engine is None:
        return []
    items = engine.recent_items()
    return [
        {
            "title": item.title,
            "detail": item.detail,
            "priority": item.priority,
            "category": item.category,
            "source_action": item.source_action,
            "timestamp": item.timestamp.isoformat(),
            "artifacts": [str(p) for p in item.artifacts],
        }
        for item in items
    ]


@router.get("/rules")
async def engine_rules():
    engine = _get_engine()
    if engine is None:
        return []
    return engine.rule_descriptions()
```

**Step 4: Wire into app.py**

Modify `logos/api/app.py` — add engine router and lifespan integration:

```python
# Add import
from cockpit.api.routes.engine import router as engine_router, set_engine

# Add router
app.include_router(engine_router)

# Update lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_refresh_loop()
    from cockpit.engine import ReactiveEngine
    engine = ReactiveEngine()
    set_engine(engine)
    await engine.start()
    yield
    await engine.stop()
    await agent_run_manager.shutdown()
```

**Step 5: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_engine_routes.py -v`
Expected: all PASS

**Step 6: Commit**

```
feat: add engine status API endpoints and lifespan integration
```

---

### Task 10: End-to-end integration test

**Files:**
- Create: `tests/test_engine_e2e.py`

**Step 1: Write the e2e test**

This test verifies the full cascade: write a person file → engine detects → cache refreshes → nudges recalculated → delivery item queued.

```python
"""End-to-end test: file write → engine cascade → delivery item queued."""
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock

from cockpit.engine import ReactiveEngine
from cockpit.engine.models import DeliveryItem


def _write_md(path: Path, frontmatter: str, body: str = ""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}", encoding="utf-8")


class TestE2ECascade:
    @patch("cockpit.engine.reactive_rules._refresh_cache", new_callable=AsyncMock)
    @patch("cockpit.engine.reactive_rules._recalc_nudges", new_callable=AsyncMock)
    @patch("cockpit.engine.reactive_rules._recalc_team_health", new_callable=AsyncMock)
    async def test_person_file_full_cascade(
        self, mock_health, mock_nudges, mock_refresh, tmp_path: Path
    ):
        """Write person file → 3 actions fire → 3 delivery items queued."""
        mock_refresh.return_value = "cache refreshed"
        mock_nudges.return_value = "3 nudges"
        mock_health.return_value = "2 teams"

        (tmp_path / "people").mkdir()
        engine = ReactiveEngine(
            data_dir=tmp_path,
            enabled=True,
            debounce_ms=50,
            delivery_interval_s=9999,  # don't auto-flush
        )
        await engine.start()
        try:
            _write_md(
                tmp_path / "people" / "alice.md",
                "type: person\nname: Alice\nteam: platform\ncognitive-load: high\n",
            )
            # Wait for debounce + execution
            await asyncio.sleep(1.0)
        finally:
            await engine.stop()

        # All 3 handlers should have been called
        mock_refresh.assert_awaited()
        mock_nudges.assert_awaited()
        mock_health.assert_awaited()

        # Delivery items should be queued
        recent = engine.recent_items()
        assert len(recent) >= 3
        titles = [item.title for item in recent]
        assert any("refresh_cache" in t for t in titles)

    @patch("cockpit.engine.reactive_rules._refresh_cache", new_callable=AsyncMock)
    async def test_coaching_file_triggers_nudge_recalc(
        self, mock_refresh, tmp_path: Path
    ):
        mock_refresh.return_value = "ok"

        (tmp_path / "coaching").mkdir()
        engine = ReactiveEngine(
            data_dir=tmp_path, enabled=True, debounce_ms=50,
            delivery_interval_s=9999,
        )

        with patch(
            "cockpit.engine.reactive_rules._recalc_nudges",
            new_callable=AsyncMock, return_value="ok",
        ) as mock_nudges:
            await engine.start()
            try:
                _write_md(
                    tmp_path / "coaching" / "delegation.md",
                    "type: coaching\nperson: Alice\n",
                )
                await asyncio.sleep(1.0)
            finally:
                await engine.stop()

            mock_nudges.assert_awaited()
```

**Step 2: Run e2e tests**

Run: `cd ai-agents && uv run pytest tests/test_engine_e2e.py -v`
Expected: all PASS

**Step 3: Commit**

```
test: add end-to-end reactive engine cascade tests
```

---

### Task 11: Run full test suite and verify

**Step 1: Run all existing tests to verify no regressions**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: all tests pass (982+ existing + ~40 new engine tests)

**Step 2: Run engine tests specifically**

Run: `cd ai-agents && uv run pytest tests/test_engine_*.py -v`
Expected: all new engine tests pass

**Step 3: If any failures, fix and re-run**

**Step 4: Commit any test fixes**

---

### Task 12: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `CLAUDE.md` (root)
- Modify: `agent-architecture.md`

**Step 1: Update CLAUDE.md**

Add to Project Layout after `data/`:

```
cockpit/
  engine/             Reactive engine (watcher, rules, executor, delivery)
```

Add new section after Data Directory:

```markdown
## Reactive Engine

The `logos/engine/` package provides a filesystem-watching reactive loop. When files change in `DATA_DIR`, the engine evaluates rules, executes cascading actions (cache refresh, nudge recalculation, LLM synthesis), and delivers batched notifications.

Configuration (env vars, all optional):

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENGINE_ENABLED` | `true` | Kill switch |
| `ENGINE_DEBOUNCE_MS` | `200` | Watcher debounce window |
| `ENGINE_LLM_CONCURRENCY` | `2` | Max simultaneous LLM calls |
| `ENGINE_DELIVERY_INTERVAL_S` | `300` | Batch notification interval |
| `ENGINE_ACTION_TIMEOUT_S` | `60` | Per-action LLM timeout |
```

**Step 2: Update root CLAUDE.md**

Add `logos/engine/` to the repository layout under `cockpit/`.

Add to API section: "3 engine endpoints (status, recent, rules) on /api/engine/."

**Step 3: Update agent-architecture.md**

Add a "Reactive Engine" section describing the watcher → rules → executor → delivery loop.

**Step 4: Commit**

```
docs: add reactive engine to project documentation
```

---

### Task Summary

| Task | Description | Tests | Estimated complexity |
|------|------------|-------|---------------------|
| 1 | Add watchdog dependency | 0 | Trivial |
| 2 | Core data models (ChangeEvent, Action, ActionPlan, DeliveryItem) | ~10 | Low |
| 3 | Filesystem watcher with debounce + ignore set | ~7 | Medium |
| 4 | Rules engine (Rule, RuleRegistry, evaluate_rules) | ~6 | Low |
| 5 | Phased async executor | ~8 | Medium |
| 6 | Delivery queue with batching | ~7 | Medium |
| 7 | 6 concrete reactive rules | ~12 | Medium |
| 8 | ReactiveEngine orchestrator | ~5 | Low |
| 9 | API endpoints + app.py integration | ~3 | Low |
| 10 | End-to-end integration tests | ~2 | Low |
| 11 | Full test suite verification | 0 | Trivial |
| 12 | Documentation updates | 0 | Trivial |
