# Synthesis Scheduler Design

**Date:** 2026-03-10
**Status:** Approved
**Scope:** Auto-trigger LLM synthesis agents when management data changes

## Problem

The reactive engine detects filesystem changes and recomputes deterministic state (cache, nudges, team health) in <500ms. But the most valuable outputs — briefings, team snapshots, management overviews, and operator profiles — require manual CLI or API invocation. The system evaluates but doesn't automatically generate.

The operator must remember to run agents after editing data. Generated artifacts go stale silently with no freshness signal.

## Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Execution model | In-process async | Follows meeting_cascade precedent; shares LLM semaphore |
| Reactive agents | briefing + team snapshot + overview | Hot-path outputs; 3 LLM calls, ~10s total |
| Profiler cadence | Daily (lightweight: facts + synthesis only) | Too heavy for reactive; 1 LLM call, ~5s |
| Quiet window | 180s default, configurable | Batches edit clusters without excessive delay |
| Manual suppression | Suppress all synthesis while any manual agent runs | Simple, conservative, avoids conflicts |
| ActionPlan trigger | Make `trigger` field optional (`None` default) | Synthesis is timer-driven, not event-driven |
| Partial failure | Re-run all 3 reactive handlers on any failure | Intentional simplification; cost negligible |
| Freshness | Per-artifact using dependency map | Global staleness produces false positives |
| Force synthesis | `POST /api/engine/synthesize` endpoint | Operator may not want to wait 180s |
| Restart behavior | Dirty set lost on restart | Acceptable for single-operator; documented trade-off |

## Architecture

### New Component

`logos/engine/synthesis.py` — `SynthesisScheduler` class (~150 lines).

Three responsibilities:
1. **Accumulate** — receive `signal(subdirectory)` calls, maintain dirty set
2. **Timer** — quiet-window timer resets on each signal; fires when edits stop
3. **Submit** — build ActionPlan with Phase 1 actions, hand to executor

### Wiring

```
ReactiveEngine.__init__()
  → creates SynthesisScheduler(executor, delivery, agent_run_manager)

ReactiveEngine._handle_change(event)
  → evaluate_rules → executor.execute (phase 0: cache refresh)
  → self._scheduler.signal(event.subdirectory)

ReactiveEngine.start() / stop()
  → self._scheduler.start() / stop()
```

The scheduler does not modify the rule registry or watcher. It consumes change signals only.

## Data Flow

### Change-to-Synthesis Dependency Map

```
FILE CHANGE                    INVALIDATES
──────────────────────────────────────────────
data/people/*.md            →  briefing, snapshot, overview, profiler
data/coaching/*.md          →  briefing, snapshot, overview, profiler
data/feedback/*.md          →  briefing, snapshot, overview, profiler
data/meetings/*.md          →  profiler only
data/okrs/*.md              →  profiler only
data/goals/*.md             →  profiler only
data/incidents/*.md         →  profiler only
data/postmortem-actions/*.md → profiler only
data/review-cycles/*.md     →  profiler only
data/status-reports/*.md    →  (no synthesis agent reads these)
data/decisions/*.md         →  (no synthesis agent reads these)
```

Two tiers:
- **Hot path** (`people`, `coaching`, `feedback`): triggers reactive synthesis
- **Warm path** (`meetings`, `okrs`, `goals`, `incidents`, `postmortem-actions`, `review-cycles`): marks profiler dirty only

### Excluded Subdirectories

These DATA_DIR subdirectories are output directories and are explicitly excluded from synthesis triggering. `signal()` filters them on arrival — only subdirectories in `SYNTHESIS_RELEVANT` are added to `_dirty`.

- `references/` — generated briefings, snapshots, overviews, digests
- `1on1-prep/` — generated 1:1 prep documents
- `briefings/` — generated briefings (legacy path)
- `status-updates/` — generated status reports
- `review-prep/` — generated review evidence
- `inbox/` — transient; ingest routes files to typed subdirectories which then trigger signals
- `processed/` — archived inbox files

### Reactive Synthesis (Quiet Window)

```
signal("people") → add to _dirty, reset 180s timer
signal("coaching") → add to _dirty, reset 180s timer
...180s of quiet...
_on_quiet_window():
  if _running_synthesis → reschedule 60s, return
  if agent_run_manager.is_running → reschedule 60s, return
  snapshot dirty set, clear _dirty
  if snapshot ∩ HOT_PATH → run briefing + snapshot + overview
  trigger cache refresh
```

### Daily Profiler

```
hourly check (first check at +1h after start(), not immediately):
  if not _profiler_dirty → skip
  if (now - _last_profiler_at) < 24h → skip
  if _running_synthesis → skip
  if agent_run_manager.is_running → skip
  run lightweight profiler (facts + synthesis, no curation)
```

### Inbox Ingest Interaction

When the ingest handler processes an inbox file, it routes the document to a typed subdirectory (e.g., `people/`, `meetings/`). The watcher fires for the destination, the engine calls `_handle_change`, and the scheduler receives a signal for that subdirectory. This is correct behavior — the ingested document should trigger synthesis if appropriate. Transcripts are not suppressed by `ignore_fn` (per existing ingest design), so a transcript ingest triggers both `meeting_cascade` and a scheduler signal for `meetings/`.

## Component Interface

```python
class SynthesisScheduler:
    def __init__(
        self,
        executor: PhasedExecutor,
        delivery: DeliveryQueue,
        agent_run_manager: AgentRunManager,
        ignore_fn: Callable[[Path], None] | None = None,
        quiet_window_s: float | None = None,
        profiler_interval_s: float | None = None,
        enabled: bool | None = None,
    ) -> None: ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def signal(self, subdirectory: str) -> None: ...
    async def force(self) -> None: ...
    def status(self) -> dict: ...
```

### Internal State

- `_dirty: set[str]` — subdirectories changed since last synthesis (only SYNTHESIS_RELEVANT entries)
- `_timer: asyncio.TimerHandle | None` — quiet-window timer
- `_last_synthesis_at: float` — monotonic time of last reactive synthesis
- `_profiler_dirty: bool` — any synthesis-relevant change since last profiler run
- `_last_profiler_at: float` — monotonic time of last profiler run (initialized from profile's `updated_at` on construction)
- `_running_synthesis: bool` — re-entrant guard
- `_profiler_task: asyncio.Task | None` — hourly check loop task

### Constants

```python
HOT_PATH = {"people", "coaching", "feedback"}
WARM_PATH = {"meetings", "okrs", "goals", "incidents",
             "postmortem-actions", "review-cycles"}
SYNTHESIS_RELEVANT = HOT_PATH | WARM_PATH
```

### signal() Behavior

1. If `subdirectory not in SYNTHESIS_RELEVANT` → return immediately
2. Add `subdirectory` to `_dirty`
3. Set `_profiler_dirty = True`
4. If `_timer` exists, cancel it
5. Schedule new timer: `loop.call_later(quiet_window_s, _schedule_synthesis)`

### _on_quiet_window() Behavior

1. If `_running_synthesis` → reschedule timer for 60s, return
2. If `agent_run_manager.is_running` → reschedule timer for 60s, return
3. Set `_running_synthesis = True`
4. Snapshot and clear `_dirty`
5. If snapshot intersects `HOT_PATH`:
   - Build ActionPlan with 3 Phase 1 actions (briefing, snapshot, overview)
   - `trigger` field is `None` (timer-driven, not event-driven)
   - Wrap `executor.execute(plan)` in try/except
   - On any action error → restore `self._dirty |= HOT_PATH`
   - On executor exception (ExceptionGroup) → restore dirty, log error
   - Enqueue delivery items for results and errors
   - Call `cache.refresh()` (from `cockpit.api.cache`) so API serves fresh artifacts
6. Set `_running_synthesis = False`

### force() Behavior

1. Cancel pending `_timer` if exists
2. Call `_on_quiet_window()` directly

Exposed via `ReactiveEngine.force_synthesis()` (public method delegating to `self._scheduler.force()`), called by `POST /api/engine/synthesize`.

### stop() Behavior

1. Cancel `_timer` if pending
2. Cancel `_profiler_task`
3. If `_running_synthesis` is True, await current synthesis completion (max ~10s)
4. Dirty set is NOT persisted — lost on restart (documented trade-off)

## Model Change

### `logos/engine/models.py`

Reorder `ActionPlan` fields so `trigger` (now optional) comes after `created_at` to satisfy Python's dataclass rule that fields with defaults follow fields without:

```python
@dataclass
class ActionPlan:
    created_at: datetime
    trigger: ChangeEvent | None = None  # None for timer-driven plans
    actions: list[Action] = field(default_factory=list)
    ...
```

All existing callers pass `trigger` as a keyword argument or positionally before `created_at`, so update call sites in `rules.py` to use keyword arguments: `ActionPlan(trigger=event, created_at=...)`. This is a small, safe refactor.

## Synthesis Handlers

Three reactive handlers, called as Phase 1 actions (semaphore-bounded to 2 concurrent):

```python
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
```

One daily handler:

```python
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
```

### Output Paths

All writes go to `DATA_DIR/references/` or `PROFILES_DIR/` — neither is watched by any rule, so no cascade risk and no `ignore_fn` calls needed.

| Handler | Writes to | Watched? |
|---------|-----------|----------|
| briefing | `references/briefing-{date}.md` + `profiles/management-briefing.json` | No |
| snapshot | `references/team-snapshot-{date}.md` | No |
| overview | `references/overview-{date}.md` | No |
| profiler | `profiles/management-profile.json` + `.md` | No |

### Cost

| Handler | Model | Calls | Latency |
|---------|-------|-------|---------|
| briefing | fast (haiku) | 1 | ~3s |
| snapshot | balanced (sonnet) | 1 | ~5s |
| overview | fast (haiku) | 1 | ~3s |
| profiler light | balanced (sonnet) | 1 | ~5s |

Reactive total: 3 calls, ~10s wall time (semaphore=2).

## Error Handling

Synthesis handler failures are caught by the executor and enqueued as high-priority delivery items (notification within 60s). On failure, the dirty set is restored for the failed tier so the next quiet window retries:

```python
# After executor.execute(plan):
if any(name in plan.errors for name in reactive_action_names):
    self._dirty |= HOT_PATH  # retry on next window
```

The entire `executor.execute()` call is wrapped in try/except to handle unexpected ExceptionGroup propagation. On any exception, the dirty set is restored and the error is logged.

Profiler failure: `_profiler_dirty` stays True, hourly check retries next cycle.

Successful synthesis produces medium-priority delivery items (existing engine pattern — all action results are enqueued). The operator sees "briefing: Today's focus is..." in their notifications.

## Configuration

New env vars following existing `ENGINE_*` pattern:

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENGINE_SYNTHESIS_ENABLED` | `true` | Kill switch for auto-synthesis |
| `ENGINE_SYNTHESIS_QUIET_S` | `180` | Seconds of quiet before reactive synthesis |
| `ENGINE_PROFILER_INTERVAL_S` | `86400` | Minimum seconds between profiler runs |

## Engine Integration

### Changes to `logos/engine/__init__.py`

1. Import `SynthesisScheduler`
2. Accept `agent_run_manager` parameter in constructor
3. Create `SynthesisScheduler` instance during init
4. Call `self._scheduler.signal(event.subdirectory)` in `_handle_change()`
5. Start/stop scheduler in `start()`/`stop()`
6. Include `synthesis` key in `status()` return

### Changes to `logos/engine/models.py`

Make `trigger` optional: `trigger: ChangeEvent | None = None`.

### Changes to `logos/api/app.py`

Pass `agent_run_manager` to `ReactiveEngine()`.

### Changes to `logos/api/routes/engine.py`

Add `POST /api/engine/synthesize` endpoint that calls `engine.force_synthesis()`.

### Scheduler Status (exposed via GET /api/engine/status)

```json
{
  "synthesis": {
    "enabled": true,
    "dirty": ["people", "coaching"],
    "quiet_window_s": 180,
    "timer_active": true,
    "last_synthesis_at": "2026-03-10T14:32:00Z",
    "last_profiler_at": "2026-03-10T07:00:00Z",
    "profiler_dirty": true
  }
}
```

## Freshness Signaling

### Cache Extension

`logos/api/cache.py` gains two timestamps:
- `_last_hot_change_at: float` — set by engine on HOT_PATH changes
- `_last_warm_change_at: float` — set by engine on WARM_PATH changes

Exposed as `hot_change_age()` and `warm_change_age()`.

The engine sets these in `_handle_change()` based on `event.subdirectory`:
```python
if event.subdirectory in HOT_PATH:
    cache._last_hot_change_at = time.monotonic()
elif event.subdirectory in WARM_PATH:
    cache._last_warm_change_at = time.monotonic()
```

### API Response Enrichment

All four artifact endpoints gain `_freshness` metadata:

```json
{
  "...artifact fields...",
  "_freshness": {
    "generated_at": "2026-03-10T07:00:00Z",
    "data_change_age": 900,
    "synthesis_stale": false
  }
}
```

- Briefing, snapshot, overview: `data_change_age` uses `hot_change_age()`
- Profile: `data_change_age` uses `min(hot_change_age(), warm_change_age())`
- `generated_at` comes from the artifact's own timestamp field (briefing has `generated_at`, profile has `updated_at`)
- `synthesis_stale` is true when the relevant data changed more recently than the artifact was generated

## Testing

One new file: `tests/test_synthesis_scheduler.py`. All in-memory, no LLM, no filesystem.

| Test | Verifies |
|------|----------|
| `test_signal_irrelevant_subdirectory` | `decisions/`, `status-reports/`, `references/`, `1on1-prep/` don't affect dirty set |
| `test_signal_hot_path_sets_dirty` | `people/` adds to dirty set and sets profiler dirty |
| `test_signal_warm_path_sets_profiler_dirty` | `meetings/` sets profiler dirty but not hot-path dirty |
| `test_quiet_window_resets_on_signal` | Second signal cancels and reschedules timer |
| `test_synthesis_fires_after_quiet_window` | Handlers called after timer expires |
| `test_suppressed_when_agent_running` | Reschedules 60s when manual agent active |
| `test_suppressed_when_synthesis_running` | Re-entrant guard prevents concurrent synthesis |
| `test_dirty_preserved_on_failure` | Dirty set restored when handler raises |
| `test_profiler_skipped_within_24h` | Recent profiler timestamp prevents re-run |
| `test_profiler_fires_when_stale_and_dirty` | Old timestamp + dirty flag triggers profiler |
| `test_force_bypasses_quiet_window` | `force()` triggers immediate synthesis |
| `test_stop_cancels_pending_timer` | `stop()` cancels timer and profiler loop |
| `test_status_returns_scheduler_state` | Status dict has correct shape |

Mock strategy: `executor.execute` mocked to capture ActionPlans. `agent_run_manager.is_running` as simple property mock. Handlers patched to return immediately.

## Files Changed

| File | Change |
|------|--------|
| `logos/engine/synthesis.py` | **NEW** — SynthesisScheduler + 4 handlers (~200 lines) |
| `logos/engine/models.py` | Reorder ActionPlan fields, make `trigger` optional |
| `logos/engine/rules.py` | Update ActionPlan construction to use keyword args |
| `logos/engine/__init__.py` | Add scheduler wiring (signal, start/stop, status, force_synthesis) |
| `logos/api/app.py` | Pass agent_run_manager to engine |
| `logos/api/cache.py` | Add `_last_hot_change_at`, `_last_warm_change_at`, accessors |
| `logos/api/routes/data.py` | Add `_freshness` to 4 artifact endpoints |
| `logos/api/routes/engine.py` | Add `POST /api/engine/synthesize` endpoint |
| `tests/test_synthesis_scheduler.py` | **NEW** — 13 tests |
