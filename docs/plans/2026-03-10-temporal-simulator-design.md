# Temporal Simulator — Design Spec

## Goal

A self-exercising temporal simulation engine that discovers system capabilities and generates realistic usage patterns over configurable time windows, producing ephemeral DATA_DIR snapshots that the demo agent or logos API can operate against.

## Requirements

1. **Data isolation** — Demo data and non-demo data are always separate. All artifacts, documents, and state from a simulation live in an ephemeral DATA_DIR instance, never in the working `data/` directory.

2. **Always-demo-ready** — The system is always prepared to produce a demo. The simulator runs on-demand against the current system state.

3. **Self-exercising time-travel** — The system discovers its own capabilities at runtime and exercises them according to likely usage patterns for a given role and time window. No pre-scripted scenarios; the simulator reasons about what a role would plausibly do based on documented workflows and system context.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Standalone agent (peer to demo) | Simulator produces system state; demo produces presentations about it. Different responsibilities. |
| Data isolation | Ephemeral DATA_DIR instances | Perfect isolation, trivially disposable, no agent code changes needed (just point DATA_DIR). |
| Fidelity | Tiered | Deterministic agents every tick, LLM synthesis at weekly checkpoints. Balances authenticity vs cost. |
| Discovery | Existing context pipeline + documented workflow semantics | No separate discovery subsystem. Same context assembly the demo agent uses. |
| Role profiles | Role matrix + operator profile calibration + audience archetype | Three-layer composition: what the role does, calibrated by how the operator does it, in context of who's watching. |
| Temporal granularity | Day-sized ticks | Natural unit for management workflows. Sub-day ordering within a tick. |
| Latency | Not a concern | Demo pipeline already takes 1hr+. On-demand generation is acceptable. |

## Architecture

### Ephemeral DATA_DIR Management

Each simulation run creates an isolated DATA_DIR instance:

```
/tmp/hapax-sim-{uuid}/
├── people/
├── coaching/
├── feedback/
├── meetings/
├── okrs/
├── goals/
├── incidents/
├── postmortem-actions/
├── review-cycles/
├── status-reports/
├── decisions/
├── references/
├── 1on1-prep/          # agent output directories (created on demand)
├── briefings/
├── review-prep/
└── .sim-manifest.yaml
```

Agent output directories (`1on1-prep/`, `briefings/`, `review-prep/`, etc.) are created on demand when checkpoint agents produce output. The simulator does not pre-create them.

**Lifecycle:**
1. Simulator creates the directory, seeds from `demo-data/` (same as bootstrap)
2. Event generation writes new files as simulated time advances
3. Agents run against this DATA_DIR at checkpoint boundaries
4. On completion, the directory is a complete standalone snapshot
5. Demo agent receives the path and operates against it
6. Cleanup is caller's responsibility (or configurable auto-cleanup)

**`.sim-manifest.yaml`** tracks simulation metadata and progress:

```yaml
simulation:
  id: "uuid"
  role: engineering-manager
  variant: experienced-em
  window: 30d
  start_date: "2026-02-08"
  end_date: "2026-03-10"
  scenario: null
  audience: leadership
  seed: demo-data/
  created_at: "2026-03-10T14:30:00Z"
  completed_at: "2026-03-10T15:45:00Z"
  ticks_completed: 22
  ticks_total: 22
  checkpoints_run: 4
  last_completed_tick: "2026-03-10"  # enables resume
  status: completed  # running | completed | failed
```

**Resume semantics:** The manifest is written progressively — `ticks_completed` and `last_completed_tick` update after each tick. On failure, the ephemeral DATA_DIR is preserved. The simulator accepts `--resume /path/to/sim-dir/` to continue from the last completed tick. This is essential for 90-day simulations which may run for hours.

**DATA_DIR context switching:** `DATA_DIR` is currently a module-level constant in `shared/config.py`, imported by name in 14+ consumers. A simple reassignment would not propagate. Sub-project 1 must refactor `DATA_DIR` into a mutable config holder:

```python
# shared/config.py
class _Config:
    def __init__(self):
        self._data_dir = Path(os.environ.get("HAPAX_DATA_DIR", ...))

    @property
    def data_dir(self) -> Path:
        return self._data_dir

    def set_data_dir(self, path: Path) -> None:
        self._data_dir = path

config = _Config()
DATA_DIR = config.data_dir  # backward compat (read at import time)
```

All consumers that need dynamic switching (API routes, collectors) must migrate from `from shared.config import DATA_DIR` to `from shared.config import config` and access `config.data_dir`. Consumers that only run at startup (agents invoked as subprocesses) can continue using the environment variable `HAPAX_DATA_DIR`.

**API integration:** `POST /api/engine/simulation-context` calls `config.set_data_dir()` and triggers a cache refresh. Multiple simulations can exist on disk; only one is active for the API at a time.

### Reactive Engine During Simulation

The reactive engine (inotify watcher) is **not involved** during simulation. The simulator runs its own checkpoint logic directly:

- The simulator invokes agents as library calls with `HAPAX_DATA_DIR` pointed at the ephemeral directory
- The reactive engine continues watching the real `data/` directory undisturbed
- No rule evaluation, no cascade, no synthesis scheduler — the simulator controls what runs and when
- When the API switches to serve a simulation via `POST /api/engine/simulation-context`, the engine is paused (its watcher is stopped) until the context is switched back

This avoids interference between the simulator's controlled tick-by-tick execution and the engine's event-driven reactions.

### Temporal Simulation Engine

The simulator advances through simulated time in discrete day-sized ticks.

**Time model:**
- Simulation defined by: `start_date`, `end_date`, `role_profile`, `seed_corpus`
- Time advances in day-sized ticks (one workday per tick)
- Within a tick, events are generated in natural order (morning context before afternoon notes)
- Weekends/holidays skipped unless role profile indicates otherwise

**Event generation (per tick):**
1. Simulator reads current system context (same pipeline the demo agent uses — docs, data, RAG)
2. LLM receives: role profile, current simulated date, existing DATA_DIR state, workflow documentation
3. LLM decides: "what would this role plausibly do today?" — outputs a list of filesystem events (create/update files with frontmatter + content)
4. Events are written to the ephemeral DATA_DIR

**Tiered fidelity checkpoints:**
- **Every tick:** Deterministic agents run (management_activity, nudge recalculation, system_check)
- **Weekly boundaries:** LLM synthesis agents run (management_briefing, management_profiler, team snapshot)
- **On significant events:** If the tick generated an incident or review cycle, relevant synthesis runs immediately

**Seed date handling:** The seed corpus (`demo-data/`) contains files with hardcoded dates. The simulator rebases these dates relative to `start_date` during the seed copy step. If the seed's latest date is `2026-03-10` and `start_date` is `2026-01-01`, all seed dates shift backward by the same offset. This ensures the seed represents "existing history" at simulation start.

### Workflow Documentation & Discovery

Rather than a separate discovery mechanism, the simulator uses the same context assembly pipeline the demo agent uses. Workflow semantics are documented in a form that pipeline consumes.

**Workflow semantics file:** `docs/workflow-semantics.yaml`

```yaml
workflows:
  one_on_one:
    data_type: meeting
    subdirectory: meetings/
    frontmatter:
      type: meeting
      meeting-type: one-on-one
    triggers:
      - coaching_note
      - feedback
    cadence: per-person, configurable (weekly/biweekly/monthly)

  coaching_note:
    data_type: coaching
    subdirectory: coaching/
    frontmatter:
      type: coaching
    triggered_by: [one_on_one, incident]

  okr_update:
    data_type: okr
    subdirectory: okrs/
    frontmatter:
      type: okr
    cadence: quarterly review, monthly check-in

  incident:
    data_type: incident
    subdirectory: incidents/
    stochastic: true
    triggers: [postmortem_action, coaching_note]

  feedback:
    data_type: feedback
    subdirectory: feedback/
    frontmatter:
      type: feedback
    triggered_by: [one_on_one, review_cycle]
    cadence: monthly or event-driven

  postmortem_action:
    data_type: postmortem-action
    subdirectory: postmortem-actions/
    frontmatter:
      type: postmortem-action
    triggered_by: [incident]

  review_cycle:
    data_type: review-cycle
    subdirectory: review-cycles/
    frontmatter:
      type: review-cycle
    cadence: semi-annual or annual
    triggers: [feedback]

  status_report:
    data_type: status-report
    subdirectory: status-reports/
    frontmatter:
      type: status-report
    cadence: weekly or biweekly

  decision:
    data_type: decision
    subdirectory: decisions/
    frontmatter:
      type: decision
    stochastic: true

  goal:
    data_type: goal
    subdirectory: goals/
    frontmatter:
      type: goal
    cadence: quarterly
```

**Keeping it current:** The drift detector already checks docs vs reality weekly. Adding `workflow-semantics.yaml` to its scope means new DATA_DIR document types that aren't in the schema get flagged automatically. A validation test ensures bidirectional consistency: every document type in `demo-data/` has a workflow-semantics entry, and every workflow-semantics entry has at least one example in `demo-data/`.

### Role Matrix

**Location:** `config/role-matrix.yaml` (checked-in configuration, not in `profiles/` which gitignores YAML)

```yaml
roles:
  engineering-manager:
    description: "IC-to-EM transition through experienced EM"
    variants:
      - new-em
      - experienced-em
      - senior-em
    workflows: [one_on_one, coaching_note, feedback, okr_update,
                incident, postmortem_action, review_cycle,
                status_report, decision, goal]

  # Future roles (schema supports them, not implemented in v1)
  scrum-master:
    description: "Team-level agile facilitation"
    workflows: [meeting, incident, postmortem_action, goal]

  product-owner:
    description: "Backlog and stakeholder management"
    workflows: [okr_update, decision, status_report, goal, meeting]

  release-train-engineer:
    description: "SAFe ART-level coordination"
    workflows: [meeting, incident, okr_update, status_report, decision]
```

**Role profile composition (3 layers):**
1. **Role matrix entry** — what the role does, which workflows it uses
2. **Operator profile calibration** — realistic cadences, attention patterns from management_profiler's 6 dimensions
3. **Audience archetype** — contextual emphasis from `demo-audiences.yaml`

### Simulator Agent Interface

Standard CLI-invocable agent:

```bash
# 1-month simulation for an experienced EM
uv run python -m agents.simulator \
  --role engineering-manager \
  --window 30d \
  --seed demo-data/

# 2 weeks before quarterly planning
uv run python -m agents.simulator \
  --role engineering-manager \
  --scenario pre-quarterly \
  --window 14d

# Custom output, audience calibration, specific variant
uv run python -m agents.simulator \
  --role engineering-manager \
  --variant new-em \
  --window 90d \
  --audience technical-peer \
  --output /path/to/output/

# Resume a failed simulation
uv run python -m agents.simulator \
  --resume /tmp/hapax-sim-abc123/
```

**Parameters:**
- `--role` — key into role matrix (required unless `--resume`)
- `--variant` — role variant: `new-em`, `experienced-em`, `senior-em` (optional, defaults to role's first variant)
- `--window` — simulation duration: `7d`, `30d`, `90d` (required unless `--resume`)
- `--scenario` — named scenario modifier (optional, see Scenarios below)
- `--seed` — seed corpus path (default: `demo-data/`)
- `--audience` — audience archetype for profile calibration (optional)
- `--output` — output directory (default: `/tmp/hapax-sim-{uuid}/`)
- `--resume` — path to an existing simulation directory to continue from last completed tick
- `--checkpoints` — override checkpoint strategy (optional)

**Demo agent integration:**

```bash
uv run python -m agents.demo \
  --topic "system after 1 month" \
  --simulate --window 30d --role engineering-manager \
  --audience leadership
```

Demo agent detects `--simulate`, runs simulator first to produce a DATA_DIR, then generates demo against that state. Without `--simulate`, demo agent works exactly as today.

### Scenarios

A scenario modifier adjusts the event generation probability distribution and may set temporal constraints. Defined in `config/scenarios.yaml`:

```yaml
scenarios:
  pre-quarterly:
    description: "2 weeks before quarterly planning — increased OKR activity"
    window_hint: 14d
    probability_overrides:
      okr_update: 3.0    # 3x normal frequency
      status_report: 2.0  # 2x normal frequency
      goal: 2.0
    inject_events:
      - type: meeting
        meeting-type: planning
        at: end  # appears near end of window

  post-incident:
    description: "Aftermath of a major incident"
    inject_events:
      - type: incident
        severity: high
        at: start  # incident happens at simulation start
    probability_overrides:
      postmortem_action: 5.0
      coaching_note: 2.0

  first-90-days:
    description: "New manager onboarding period"
    window_hint: 90d
    probability_overrides:
      one_on_one: 1.5     # more frequent initial 1:1s
      coaching_note: 0.5  # fewer coaching notes (still learning)
      decision: 0.3       # fewer decisions (observing)
```

Scenarios are additive — they modify the base role profile's probabilities, not replace them. The LLM receives the scenario context as part of its prompt and uses the probability overrides as guidance (not hard constraints).

### Safety Enforcement

Event generation uses structured output (Pydantic models) to enforce the management_safety axiom:

```python
class SimulatedEvent(BaseModel):
    """A single filesystem event generated by the simulator."""
    date: str
    workflow_type: str        # key into workflow-semantics.yaml
    subdirectory: str
    filename: str
    participant: str | None   # for people-related events
    topics: list[str]         # structural content only
    metadata: dict[str, Any]  # frontmatter fields

    # Explicitly NO free-text content field for coaching/feedback types.
    # Content is generated from templates using the structural fields above.
```

For document types that need body content (meetings, decisions, status reports), the event model includes a `body_template` field that the simulator fills with structural content. Coaching and feedback events have their body generated from a constrained template that produces only structural content (date, participant, topics discussed, action items) — never evaluative language.

## Scaling Plan

- **v1:** Engineering manager only (3 variants: new-em, experienced-em, senior-em). Exercises the full existing data model.
- **v2:** Roles that reuse existing document types (scrum-master, product-owner). May require new document types.
- **v3:** SAFe-specific roles (RTE, Solution Architect). May need new workflow semantics.

Each new role requires: (1) role matrix entry, (2) workflow documentation for new workflows, (3) optionally a calibration profile. The LLM-driven event generation handles the rest.

## Sub-Project Decomposition

Three sequential sub-projects, each with its own plan → implementation cycle:

### Sub-project 1: Ephemeral DATA_DIR & Simulation Infrastructure

- DATA_DIR instance lifecycle (create, seed, switch, cleanup)
- `.sim-manifest.yaml` schema and validation
- API context switching (`POST /api/engine/simulation-context`)
- Workflow semantics documentation (`docs/workflow-semantics.yaml`)
- Role matrix schema (`config/role-matrix.yaml`) — EM role only
- Scenario schema (`config/scenarios.yaml`)
- `DATA_DIR` mutable config holder refactor in `shared/config.py`
- Reactive engine pause/resume for simulation context switching
- Tests for isolation guarantees

### Sub-project 2: Temporal Simulation Engine

- `agents/simulator.py` — the agent
- `agents/simulator_pipeline/` — event generation, tick advancement, checkpoint execution
- LLM-driven daily event generation from role profile + workflow semantics + system context
- Tiered fidelity checkpoint runner
- Seed date rebasing during copy step
- Resume support (`--resume` flag)
- CLI interface with `--role`, `--variant`, `--window`, `--scenario`, `--resume` flags
- Structured output models (SimulatedEvent) for safety enforcement
- Tests with mocked LLM calls

### Sub-project 3: Demo Integration & Role Scaling

- Demo agent `--simulate` flag and simulator orchestration
- Scenario modifiers (`pre-quarterly`, `post-incident`, `first-90-days`)
- EM role variants (new-em, experienced-em, senior-em)
- End-to-end validation that simulated DATA_DIR produces valid demos

## Safety Boundary

The management_safety axiom applies fully: the simulator generates plausible management *activity patterns* (1:1 cadences, coaching timing, OKR updates) but never generates feedback language, coaching recommendations, or evaluations of simulated team members. Simulated coaching notes contain structural content (date, participant, topics) without prescriptive language.
