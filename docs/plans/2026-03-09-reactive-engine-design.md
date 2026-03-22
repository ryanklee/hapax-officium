# Reactive Engine Design

**Date:** 2026-03-09
**Status:** Approved
**Scope:** Reactive event loop inside logos API — Phase 1 (filesystem-triggered cascades)

## Problem

The data loop is fragmented. Inputs require manual chaining of 3-5 agent invocations to produce downstream outputs. Nothing connects "a file changed" to "all affected outputs regenerated and operator notified." The operator is the glue between components.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Where the brain lives | Inside logos API process | Already always-on, has cache loop, single-operator axiom means no scaling concern |
| Proactive detection cadence | 60s tick (future), batched delivery | Fast detection, consolidated delivery respects attention budget |
| Autonomous action boundary | Write + notify + internal chaining | Single-operator axiom = safe. Management safety axiom = no people-facing actions |
| Implementation priority | Reactive path first | Most visibly broken today — manual chaining should cascade automatically |
| Execution model | Async task queue with phased execution | Concurrent LLM calls for responsiveness, dependencies for correctness |

## Architecture

### Module Layout

```
cockpit/
├── api/                    # existing — FastAPI routes, cache, SSE
├── data/                   # existing — collectors (management, nudges, team_health)
└── engine/                 # new — reactive loop
    ├── __init__.py         # exports ReactiveEngine
    ├── watcher.py          # ChangeEvent, filesystem watcher, debounce, ignore set
    ├── rules.py            # Rule dataclass, rule registry, initial rule set
    ├── executor.py         # Action, ActionPlan, phased async executor
    └── delivery.py         # DeliveryItem, batch queue, ntfy integration
```

Dependency direction: `engine` imports from `data` and `agents`. Nothing imports from `engine` except the API lifespan.

### Core Data Model

```python
@dataclass
class ChangeEvent:
    path: Path                    # absolute path to changed file
    subdirectory: str             # "people", "coaching", "meetings", "inbox", etc.
    event_type: str               # "created" | "modified" | "deleted"
    doc_type: str | None          # from frontmatter "type:" field, if parseable
    timestamp: datetime

@dataclass
class Action:
    name: str                     # e.g. "extract_meeting", "refresh_cache"
    handler: Callable             # async callable
    args: dict                    # kwargs for the handler
    priority: int                 # lower = runs first within same phase
    phase: int                    # 0=deterministic, 1=LLM synthesis, 2=delivery
    depends_on: list[str]         # action names that must complete first

@dataclass
class ActionPlan:
    trigger: ChangeEvent
    actions: list[Action]
    created_at: datetime
    _results: dict[str, Any]      # filled as actions complete

@dataclass
class DeliveryItem:
    title: str
    detail: str
    priority: str                 # "critical" | "high" | "medium" | "low"
    category: str                 # "generated", "detected", "warning", "error"
    source_action: str
    timestamp: datetime
    artifacts: list[Path]         # files created/updated
```

### Phase Model

- **Phase 0** — Deterministic, fast: cache refresh, file routing, starter creation. Bounded concurrency: 5. Timeout: 10s.
- **Phase 1** — LLM synthesis: meeting extraction, prep regeneration. Bounded concurrency: 2. Timeout: 60s.
- **Phase 2** — Delivery: items queued, flushed on batch interval.

### Filesystem Watcher

- Uses `watchdog` library (inotify on Linux) on all `DATA_DIR` subdirectories
- 200ms debounce per file path to coalesce rapid write events
- Self-trigger prevention via `_ignore_set: set[Path]` — executor registers paths before writing, watcher skips and clears after debounce window
- Enriches events by reading frontmatter to populate `doc_type`
- Excludes `DATA_DIR/processed/` and dotfiles/temp files

### Rules Engine

A rule is a pure function: `ChangeEvent -> list[Action] | None`.

```python
@dataclass
class Rule:
    name: str
    trigger_filter: Callable[[ChangeEvent], bool]
    produce: Callable[[ChangeEvent], list[Action]]
```

Initial rule set:

| Rule | Triggers on | Actions |
|------|------------|---------|
| `inbox_ingest` | file created in `inbox/` | P0: classify + route. P1: if transcript, extract meeting data. P0 (chained): create starters from extraction. |
| `meeting_cascade` | file created/modified in `meetings/` | P0: refresh cache. P1: regenerate 1:1 prep for person (if identifiable). P1: update profiler facts. |
| `person_changed` | file created/modified in `people/` | P0: refresh cache, recalc nudges, recalc team health. P1: if 1:1 due, regenerate prep. |
| `coaching_changed` | file created/modified in `coaching/` | P0: refresh cache, recalc nudges. |
| `feedback_changed` | file created/modified in `feedback/` | P0: refresh cache, recalc nudges. |
| `decision_logged` | file created in `decisions/` | P0: refresh cache. |

Rules call Python functions directly (e.g., `meeting_lifecycle.extract_meeting()`), not subprocess invocations. CLI entry points remain for manual use.

Rule evaluation: all rules whose `trigger_filter` matches are collected, actions deduplicated by name, assembled into ActionPlan.

### Executor

- Multiple ActionPlans can execute concurrently (e.g., two inbox files at once)
- Each plan gets its own TaskGroup
- Global semaphore limits total LLM calls across all plans to 3
- Action failure does NOT abort the plan — failed actions logged, dependents skipped, delivery phase always runs
- Every action logged: name, phase, duration_ms, success/failure, output summary

### Delivery Queue

| Priority | Timing |
|----------|--------|
| critical | Immediate push via ntfy (urgent) |
| high | Next batch window or 60s, whichever first |
| medium | Next batch window (default 5 min) |
| low | Suppressed unless requested via API |

Batch flush consolidates items into a single notification. Max 1 notification per interval. Items also written to in-memory ring buffer (last 50) for API consumption.

### API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/engine/status` | Running/stopped, watcher active, pending actions |
| `GET /api/engine/recent` | Last 50 delivery items |
| `GET /api/engine/rules` | Registered rules and descriptions |

### Integration

```python
# logos/api/app.py lifespan
async def lifespan(app):
    cache.start_refresh_loop()      # existing — kept as safety net
    engine = ReactiveEngine()
    await engine.start()            # starts watcher + delivery queue
    yield
    await engine.stop()
```

### Configuration

```bash
ENGINE_ENABLED=true                # kill switch
ENGINE_DEBOUNCE_MS=200             # watcher debounce
ENGINE_LLM_CONCURRENCY=2           # max simultaneous LLM calls
ENGINE_DELIVERY_INTERVAL_S=300     # batch flush interval
ENGINE_ACTION_TIMEOUT_S=60         # per-action LLM timeout
```

## Explicitly Deferred

1. **Proactive tick loop** — 60s timer evaluating time-dependent rules (staleness, approaching meetings). Rules engine designed to accept future `TickEvent` triggers.
2. **External action autonomy** — Profiler chaining, calendar-aware timing. Executor supports it, just needs more rules.
3. **Dashboard activity feed UI** — API endpoint exists, frontend component deferred.
4. **LLM-enriched notifications** — Initial delivery uses plain text consolidation.
5. **Rule hot-reload** — Rules registered in code at startup, no dynamic configuration.

## Testing Strategy

- Rules: pure functions, unit tested with synthetic ChangeEvents
- Executor: tested with mock handlers
- Watcher: tested with tmp_path + real file writes
- Integration: write file to inbox/, assert cascade produces expected files + delivery items

## In-Scope Deliverables

- Watcher on DATA_DIR with debounce + self-trigger prevention
- 6 reactive rules (inbox, meeting, person, coaching, feedback, decision)
- Phased async executor with bounded LLM concurrency
- Batched delivery queue with critical override
- 3 new API endpoints
- Engine integration into logos API lifespan
- Tests for all new components
