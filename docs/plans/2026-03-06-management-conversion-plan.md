# Management Cockpit: Total Conversion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the containerized Hapax system from a personal executive function platform into a purpose-built management support system.

**Architecture:** Remove all non-management agents, collectors, routes, and frontend components. Rename and reground 3 axioms. Transform 4 agents, 2 collectors, and the frontend to serve management purpose exclusively. The safety boundary "LLMs prepare, humans deliver" becomes the product's core constraint.

**Tech Stack:** Python 3.12+ (uv), FastAPI, React/TypeScript (pnpm), Docker Compose v2, Pydantic AI, YAML axiom registry

**Design Document:** `docs/plans/2026-03-06-management-conversion-design.md`

---

## Batch 1: Axiom Amendment

Constitutional changes first — these define what the system IS, so everything downstream depends on them.

### Task 1.1: Rename and reground axioms in registry.yaml

**Files:**
- Modify: `axioms/registry.yaml`

**Step 1: Edit the registry**

Replace the 4 axiom entries with the converted versions:

```yaml
version: 3
axioms:
  - id: single_operator
    text: >
      This system is built for and operated by a single manager.
      All architectural decisions must respect and leverage that constraint.
      No multi-operator features, role management, sharing capabilities,
      or administrative interfaces.
    weight: 100
    type: hardcoded
    created: "2026-03-03"
    status: active
    supersedes: single_user
    scope: constitutional
    domain:

  - id: decision_support
    text: >
      This system supports high-stakes people management decisions.
      The operator's time and attention are the scarcest resources.
      The system must minimize friction, surface actionable items proactively,
      automate routine preparation, and never require the operator to remember,
      check, or manually trigger what can be automated.
    weight: 95
    type: hardcoded
    created: "2026-03-03"
    status: active
    supersedes: executive_function
    scope: constitutional
    domain:

  - id: management_safety
    text: >
      This system aggregates signals and prepares context for the operator's
      relational work with their team. It never substitutes for human judgment
      in people decisions. LLMs prepare, humans deliver. The system surfaces
      patterns and open loops. It never generates feedback language, coaching
      hypotheses, or recommendations about individual team members.
    weight: 95
    type: hardcoded
    created: "2026-03-03"
    status: active
    supersedes: management_governance
    scope: constitutional
    domain:

  - id: corporate_boundary
    text: >
      The Obsidian plugin operates across a corporate network boundary via
      Obsidian Sync. When running on employer-managed devices, all external
      API calls must use employer-sanctioned providers (currently: OpenAI,
      Anthropic). No localhost service dependencies may be assumed. The
      system must degrade gracefully when home-only services are unreachable.
    weight: 90
    type: softcoded
    created: "2026-03-04"
    status: dormant
    supersedes:
    scope: domain
    domain: infrastructure
```

**Step 2: Verify YAML is valid**

Run: `python3 -c "import yaml; yaml.safe_load(open('axioms/registry.yaml'))"`
Expected: No error output

**Step 3: Commit**

```bash
git add axioms/registry.yaml
git commit -m "feat: rename and reground axioms for management conversion

single_user -> single_operator (weight 100, constitutional)
executive_function -> decision_support (weight 95, constitutional)
management_governance -> management_safety (weight 95, constitutional, elevated)
corporate_boundary -> dormant"
```

### Task 1.2: Rename axiom implication files

**Files:**
- Rename: `axioms/implications/single-user.yaml` → `axioms/implications/single-operator.yaml`
- Rename: `axioms/implications/executive-function.yaml` → `axioms/implications/decision-support.yaml`
- Rename: `axioms/implications/management-governance.yaml` → `axioms/implications/management-safety.yaml`
- Modify: each file's `axiom_id` field

**Step 1: Rename files and update axiom_id references**

```bash
cd axioms/implications
mv single-user.yaml single-operator.yaml
mv executive-function.yaml decision-support.yaml
mv management-governance.yaml management-safety.yaml
```

Then edit each file to update the `axiom_id` field at the top:
- `single-operator.yaml`: change `axiom_id: single_user` → `axiom_id: single_operator`
- `decision-support.yaml`: change `axiom_id: executive_function` → `axiom_id: decision_support`
- `management-safety.yaml`: change `axiom_id: management_governance` → `axiom_id: management_safety`

**Step 2: Verify all 3 files parse**

Run: `for f in axioms/implications/*.yaml; do python3 -c "import yaml; yaml.safe_load(open('$f')); print(f'OK: $f')"; done`
Expected: OK for all files (including corporate-boundary.yaml which is unchanged)

**Step 3: Commit**

```bash
git add axioms/implications/
git commit -m "feat: rename axiom implication files to match converted axiom IDs"
```

### Task 1.3: Add conversion precedent

**Files:**
- Create: `axioms/precedents/seed/management-conversion.yaml`

**Step 1: Write the precedent**

```yaml
# Precedent documenting the management total conversion decision
- id: sp-conv-001
  axiom_id: management_safety
  date: "2026-03-06"
  context: >
    System converted from personal executive function platform to
    purpose-built management support system. management_governance
    elevated from domain axiom (weight 85) to constitutional axiom
    management_safety (weight 95). The boundary "LLMs prepare, humans
    deliver" is now the product's core safety specification.
  decision: >
    All non-management agents, collectors, routes, and frontend
    components removed. 4 axioms converted: single_user -> single_operator,
    executive_function -> decision_support, management_governance ->
    management_safety (elevated), corporate_boundary -> dormant.
  implication_ids:
    - mg-boundary-001
    - mg-boundary-002
  status: approved
```

**Step 2: Verify YAML**

Run: `python3 -c "import yaml; yaml.safe_load(open('axioms/precedents/seed/management-conversion.yaml'))"`

**Step 3: Commit**

```bash
git add axioms/precedents/seed/management-conversion.yaml
git commit -m "feat: add conversion precedent documenting management total conversion"
```

### Task 1.4: Update axiom-scan hook with management_safety patterns

**Files:**
- Modify: `hapax-system/hooks/scripts/axiom-scan.sh`

**Step 1: Read the current hook**

Read `hapax-system/hooks/scripts/axiom-scan.sh` to understand the pattern-matching structure.

**Step 2: Add feedback language generation patterns**

Add these patterns to the scan list (alongside existing single_operator patterns):

```bash
# management_safety (mg-boundary-001, mg-boundary-002)
"generate.*feedback"
"draft.*feedback"
"suggest.*to_say"
"FeedbackGenerator"
"CoachingRecommender"
"PerformanceReview"
"write.*evaluation"
"compose.*message.*team"
"recommend.*for.*person"
```

**Step 3: Update any references to old axiom names**

Search for `single_user`, `executive_function`, `management_governance` in all hook scripts and replace with new names.

**Step 4: Test the hook doesn't false-positive on design doc prose**

Run: `bash hapax-system/hooks/scripts/axiom-scan.sh` (dry run if supported)

**Step 5: Commit**

```bash
git add hapax-system/hooks/scripts/
git commit -m "feat: add management_safety scan patterns to axiom hooks"
```

### Task 1.5: Update hapax-system rules

**Files:**
- Modify: `hapax-system/rules/axioms.md` — update axiom names, weights, implications
- Modify: `hapax-system/rules/system-context.md` — strip non-management content
- Create: `hapax-system/rules/management-context.md` — team boundaries, data policies
- Delete (later, in cleanup): music-production rules are in `~/.claude/rules/`, not in hapax-system

**Step 1: Rewrite axioms.md**

Replace the entire axiom governance rule with the converted axiom registry:
- `single_operator` (100) with 5 T0 implications
- `decision_support` (95) with 6 T0 implications
- `management_safety` (95) with 2 T0 implications + 5 T1-T2 implications
- `corporate_boundary` noted as dormant

**Step 2: Rewrite system-context.md**

Strip: Tier 2 agent table (replace with 5 management agents + demo), Tier 3 timer table (replace with management timers only), model aliases (keep but simplify), Qdrant collections (keep claude-memory + profile-facts, remove samples + documents), key paths (management-relevant only).

**Step 3: Create management-context.md**

```markdown
# Management Context

## Safety Boundary
LLMs prepare, humans deliver. The system never generates feedback language,
coaching recommendations, or suggestions for what to say to team members.

## Team Data
- Person notes live in Obsidian vault at `10-work/people/`
- Coaching, feedback, meeting notes are subdirectories per person
- All team state is computed deterministically (zero LLM calls)
- Cognitive load is operator self-reported (1-5 scale)

## Data Policies
- No team member behavioral data is stored outside the vault
- Profile dimensions reflect the OPERATOR's management patterns, never team members
- Staleness thresholds: weekly 1:1 >10d, biweekly >18d, monthly >40d
```

**Step 4: Commit**

```bash
git add hapax-system/rules/
git commit -m "feat: convert hapax-system rules to management context"
```

---

## Batch 2: Agent Deletions

Remove the 9 agents that have no management function. This is pure deletion — no transformation logic needed.

### Task 2.1: Delete non-management agents

**Files:**
- Delete: `agents/scout.py`
- Delete: `agents/digest.py`
- Delete: `agents/knowledge_maint.py`
- Delete: `agents/drift_detector.py`
- Delete: `agents/code_review.py`
- Delete: `agents/research.py`
- Delete: `agents/introspect.py`
- Delete: `agents/ingest.py`
- Delete: `agents/profiler_sources.py`
- Delete: `agents/query.py` (if not imported by kept agents)

**Step 1: Verify no kept agent imports from deleted agents**

Run these greps to confirm no kept agent (management_prep, meeting_lifecycle, briefing, profiler, activity_analyzer, demo, demo_eval, demo_models, health_monitor) imports from the agents being deleted:

```bash
rg "from agents\.(scout|digest|knowledge_maint|drift_detector|code_review|research|introspect|ingest|profiler_sources|query)" agents/management_prep.py agents/meeting_lifecycle.py agents/briefing.py agents/profiler.py agents/activity_analyzer.py agents/demo.py agents/demo_eval.py agents/demo_models.py agents/health_monitor.py
```

Expected: No matches. If `query.py` is imported by anything kept, leave it.

**Step 2: Delete the files**

```bash
cd ai-agents/ agents
rm scout.py digest.py knowledge_maint.py drift_detector.py code_review.py research.py introspect.py ingest.py profiler_sources.py
# Only delete query.py if step 1 confirmed no imports
```

**Step 3: Commit**

```bash
git add -A agents/
git commit -m "feat: remove 9 non-management agents

Removed: scout, digest, knowledge_maint, drift_detector, code_review,
research, introspect, ingest, profiler_sources"
```

### Task 2.2: Delete non-management shared modules

**Files:**
- Delete: `shared/health_analysis.py`
- Delete: `shared/health_history.py`
- Delete: `shared/health_correlator.py`
- Delete: `shared/incidents.py`
- Delete: `shared/alert_state.py`
- Delete: `shared/capacity.py`
- Delete: `shared/service_graph.py`
- Delete: `shared/service_tiers.py`
- Delete: `shared/threshold_tuner.py`
- Delete: `shared/sufficiency_probes.py`
- Delete: `shared/email_utils.py`
- Delete: `shared/llm_export_converter.py` (if not imported by kept code)

**Step 1: Verify no kept code imports these modules**

```bash
rg "from shared\.(health_analysis|health_history|health_correlator|incidents|alert_state|capacity|service_graph|service_tiers|threshold_tuner|sufficiency_probes|email_utils|llm_export_converter)" agents/management_prep.py agents/meeting_lifecycle.py agents/briefing.py agents/profiler.py agents/activity_analyzer.py agents/demo.py agents/health_monitor.py shared/config.py shared/notify.py shared/vault_writer.py shared/vault_utils.py shared/management_bridge.py shared/context_tools.py shared/operator.py shared/profile_store.py cockpit/
```

Expected: No matches from kept code. If any match, leave that module.

**Step 2: Delete the files**

```bash
cd ai-agents/ shared
rm health_analysis.py health_history.py health_correlator.py incidents.py alert_state.py capacity.py service_graph.py service_tiers.py threshold_tuner.py sufficiency_probes.py email_utils.py llm_export_converter.py
```

**Step 3: Check for takeout/ and proton/ directories**

```bash
ls shared/takeout/ shared/proton/ 2>/dev/null
```

If they exist, delete them:
```bash
rm -rf shared/takeout shared/proton
```

**Step 4: Commit**

```bash
git add -A shared/
git commit -m "feat: remove 12+ non-management shared modules

Removed: health_analysis, health_history, health_correlator, incidents,
alert_state, capacity, service_graph, service_tiers, threshold_tuner,
sufficiency_probes, email_utils, llm_export_converter, takeout/, proton/"
```

---

## Batch 3: Agent Transformations

Transform the 4 agents that have management value but need reframing.

### Task 3.1: Transform briefing → management_briefing

**Files:**
- Modify: `agents/briefing.py` (rename to `management_briefing.py`)

**Step 1: Read the current briefing agent**

Read `agents/briefing.py` fully. Identify:
- Data source imports (Langfuse, health, drift, scout, etc.)
- The BriefingStats schema
- The LLM synthesis prompt
- The CLI entrypoint

**Step 2: Rename the file**

```bash
mv agents/briefing.py agents/management_briefing.py
```

**Step 3: Rewrite data sources**

Remove all infrastructure data sources. Replace with:
- `from cockpit.data.management import collect_management_state` — team state
- `from cockpit.data.nudges import collect_nudges` — management nudges only
- `from cockpit.data.goals import collect_goals` — management goals

**Step 4: Rewrite BriefingStats schema**

Replace infrastructure fields with:
```python
class ManagementBriefingStats(BaseModel):
    people_count: int = 0
    stale_1on1_count: int = 0
    overdue_coaching_count: int = 0
    overdue_feedback_count: int = 0
    high_load_count: int = 0
    teams_falling_behind: list[str] = []
    management_goal_count: int = 0
```

**Step 5: Rewrite LLM synthesis prompt**

Replace the system prompt with:
```
You are generating a morning management briefing. Surface patterns and
open loops in the operator's people management work.

CRITICAL: Do not generate feedback language, coaching recommendations,
or suggestions for what to say to anyone. Present facts and patterns only.
```

**Step 6: Update module name in `__main__` block**

If there's `if __name__ == "__main__"`, update the description/name.

**Step 7: Verify it parses**

Run: `cd ai-agents && uv run python -c "import agents.management_briefing"`
Expected: Import succeeds (may warn about missing services, that's OK)

**Step 8: Commit**

```bash
git add agents/
git commit -m "feat: transform briefing -> management_briefing

Strip infrastructure data sources. Add team state, management nudges,
coaching/feedback tracking. Reframe LLM prompt for management context."
```

### Task 3.2: Transform profiler → management_profiler

**Files:**
- Modify: `agents/profiler.py` (rename to `management_profiler.py`)

**Step 1: Read the current profiler agent**

Read `agents/profiler.py`. Identify the PROFILE_DIMENSIONS list and data source collection.

**Step 2: Rename the file**

```bash
mv agents/profiler.py agents/management_profiler.py
```

**Step 3: Replace PROFILE_DIMENSIONS**

Replace the 14-dimension list with 6 management dimensions:

```python
PROFILE_DIMENSIONS = [
    "management_practice",
    "team_leadership",
    "decision_patterns",
    "communication_style",
    "attention_distribution",
    "self_awareness",
]
```

**Step 4: Update data sources**

Remove: shell history, git commits, config file scanning, Claude Code transcripts, platform exports.
Add: 1:1 note patterns, feedback delivery timing, decision logs, coaching experiment history.

**Step 5: Add safety constraint to LLM prompt**

Add to any synthesis prompt:
```
Profile the OPERATOR's management behavior only. Never profile or evaluate
team members. This answers "how do I tend to manage?" — never "how is
Person X performing?"
```

**Step 6: Verify it parses**

Run: `cd ai-agents && uv run python -c "import agents.management_profiler"`

**Step 7: Commit**

```bash
git add agents/
git commit -m "feat: transform profiler -> management_profiler

6 management dimensions (from 14). Data from vault 1:1/coaching/feedback
patterns. Profiles operator's management behavior, never team members."
```

### Task 3.3: Transform activity_analyzer → management_activity

**Files:**
- Modify: `agents/activity_analyzer.py` (rename to `management_activity.py`)

**Step 1: Read the current activity_analyzer**

Read `agents/activity_analyzer.py`. Identify system telemetry sources and goal tracking.

**Step 2: Rename the file**

```bash
mv agents/activity_analyzer.py agents/management_activity.py
```

**Step 3: Remove system telemetry**

Remove all Langfuse call counting, health run tracking, drift item counting, systemd journal analysis.

**Step 4: Add management metrics**

Replace with:
- 1:1 completion rates over rolling windows (7d, 30d)
- Feedback delivery timing (days between observation and delivery)
- Coaching experiment check-in frequency
- Career conversation recency per team member
- Management goal momentum

All computed deterministically from vault data — zero LLM calls for data collection (consistent with mg-deterministic-001).

**Step 5: Verify it parses**

Run: `cd ai-agents && uv run python -c "import agents.management_activity"`

**Step 6: Commit**

```bash
git add agents/
git commit -m "feat: transform activity_analyzer -> management_activity

1:1 completion rates, feedback timing, coaching frequency, career
conversation recency, management goal momentum. Zero LLM for collection."
```

### Task 3.4: Reduce health_monitor → system_check

**Files:**
- Modify: `agents/health_monitor.py` (rename to `system_check.py`)

**Step 1: Read the current health_monitor**

Read `agents/health_monitor.py`. Identify the 15 checks across 9 groups.

**Step 2: Rename the file**

```bash
mv agents/health_monitor.py agents/system_check.py
```

**Step 3: Replace all checks with 4 management system checks**

```python
CHECKS = [
    ("cockpit_api", check_cockpit_api_responding),
    ("vault_access", check_vault_directory_accessible),
    ("qdrant", check_qdrant_reachable),
    ("litellm", check_litellm_reachable),
]
```

Remove: GPU checks, Docker container checks, systemd timer checks, disk usage, budget tracking, capacity planning, endpoint checks, secret rotation checks, axiom compliance checks.

**Step 4: Verify it parses**

Run: `cd ai-agents && uv run python -c "import agents.system_check"`

**Step 5: Commit**

```bash
git add agents/
git commit -m "feat: reduce health_monitor -> system_check

4 checks: logos API, vault access, Qdrant, LiteLLM.
Removed 11 infrastructure-only check groups."
```

---

## Batch 4: Logos API Conversion

Remove personal collectors and routes. Transform the data cache and data endpoints.

### Task 4.1: Remove personal data collectors

**Files:**
- Delete: `logos/data/health.py`
- Delete: `logos/data/gpu.py`
- Delete: `logos/data/infrastructure.py`
- Delete: `logos/data/briefing.py` (replaced by management_briefing agent)
- Delete: `logos/data/scout.py`
- Delete: `logos/data/cost.py`
- Delete: `logos/data/readiness.py`
- Delete: `logos/data/drift.py`
- Delete: `logos/data/momentum.py`
- Delete: `logos/data/emergence.py`
- Delete: `logos/data/knowledge_sufficiency.py`
- Delete: `logos/data/domain_health.py`
- Delete: `logos/data/decisions.py` (verify not used by management)

**Step 1: Verify kept code doesn't import deleted collectors**

```bash
rg "from cockpit\.data\.(health|gpu|infrastructure|briefing|scout|cost|readiness|drift|momentum|emergence|knowledge_sufficiency|domain_health|decisions)" logos/data/management.py logos/data/team_health.py logos/data/nudges.py logos/data/goals.py logos/data/agents.py
```

Expected: nudges.py may import briefing — that import will be removed in Task 4.3.

**Step 2: Delete the files**

```bash
cd cockpit/data
rm health.py gpu.py infrastructure.py briefing.py scout.py cost.py readiness.py drift.py momentum.py emergence.py knowledge_sufficiency.py domain_health.py decisions.py
```

**Step 3: Commit**

```bash
git add -A logos/data/
git commit -m "feat: remove 13 non-management cockpit data collectors"
```

### Task 4.2: Remove personal API routes

**Files:**
- Delete: `logos/api/routes/chat.py`
- Delete: `logos/api/routes/copilot.py`
- Delete: `logos/api/routes/accommodations.py`

**Step 1: Delete the files**

```bash
cd logos/api/routes
rm chat.py copilot.py accommodations.py
```

**Step 2: Commit**

```bash
git add -A logos/api/routes/
git commit -m "feat: remove chat, copilot, and accommodations route files"
```

### Task 4.3: Rewrite logos/api/app.py

**Files:**
- Modify: `logos/api/app.py:44-60`

**Step 1: Remove deleted router imports and registrations**

Remove these lines from `app.py`:
- Line 47: `from cockpit.api.routes.chat import router as chat_router`
- Line 49: `from cockpit.api.routes.accommodations import router as accommodations_router`
- Line 50: `from cockpit.api.routes.copilot import router as copilot_router`
- Line 56: `app.include_router(chat_router)`
- Line 58: `app.include_router(accommodations_router)`
- Line 59: `app.include_router(copilot_router)`

Update app title/description:
- Line 25: `title="management-logos-api"`
- Line 26: `description="Management logos API"`

**Step 2: Verify the app module loads**

Run: `cd ai-agents && uv run python -c "from cockpit.api.app import app; print(app.title)"`
Expected: `management-logos-api`

**Step 3: Commit**

```bash
git add logos/api/app.py
git commit -m "feat: remove personal route registrations from logos API app"
```

### Task 4.4: Rewrite logos/api/cache.py

**Files:**
- Modify: `logos/api/cache.py`

**Step 1: Rewrite DataCache class**

Replace the entire DataCache with management-only fields:

```python
@dataclass
class DataCache:
    """In-memory cache for management data collector results."""

    # Management data (refresh every 5 min)
    management: Any = None
    nudges: list = field(default_factory=list)
    goals: Any = None
    agents: list = field(default_factory=list)
    team_health: Any = None

    # Refresh timestamp
    _refreshed_at: float = 0.0

    def cache_age(self) -> int:
        if self._refreshed_at == 0.0:
            return -1
        return int(time.monotonic() - self._refreshed_at)

    async def refresh(self) -> None:
        await asyncio.to_thread(self._refresh_sync)
        self._refreshed_at = time.monotonic()

    def _refresh_sync(self) -> None:
        from cockpit.data.agents import get_agent_registry
        from cockpit.data.goals import collect_goals
        from cockpit.data.management import collect_management_state
        from cockpit.data.nudges import collect_nudges
        from cockpit.data.team_health import collect_team_health

        for name, fn in [
            ("management", collect_management_state),
            ("goals", collect_goals),
            ("team_health", collect_team_health),
            ("agents", get_agent_registry),
        ]:
            try:
                setattr(self, name, fn())
            except Exception as e:
                log.warning("Refresh %s failed: %s", name, e)

        try:
            self.nudges = collect_nudges()
        except Exception as e:
            log.warning("Nudge collection error: %s", e)
```

**Step 2: Simplify the refresh loop**

Remove the fast/slow distinction. Single 5-minute loop:

```python
REFRESH_INTERVAL = 300  # seconds

async def start_refresh_loop() -> None:
    await cache.refresh()

    async def _loop():
        while True:
            await asyncio.sleep(REFRESH_INTERVAL)
            await cache.refresh()

    task = asyncio.create_task(_loop())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
```

**Step 3: Remove accommodation loading**

Delete lines 121-125 (accommodation import and loading).

**Step 4: Verify**

Run: `cd ai-agents && uv run python -c "from cockpit.api.cache import DataCache; print('OK')"`

**Step 5: Commit**

```bash
git add logos/api/cache.py
git commit -m "feat: rewrite data cache for management-only collectors

Single refresh cadence (5min). Fields: management, nudges, goals,
agents, team_health. Removed health/gpu/containers/timers/fast loop."
```

### Task 4.5: Rewrite logos/api/routes/data.py

**Files:**
- Modify: `logos/api/routes/data.py`

**Step 1: Remove all personal endpoints**

Delete these endpoints (keep the helper functions `_to_dict`, `_dict_factory`):
- `get_health` (line 50-52)
- `get_health_history` (line 55-60)
- `get_gpu` (line 63-65)
- `get_infrastructure` (line 68-73)
- `get_scout` (line 83-85)
- `get_drift` (line 88-90)
- `get_cost` (line 93-95)
- `get_readiness` (line 103-105)
- `get_accommodations` (line 123-125)
- `get_manual` (line 128-145)

**Step 2: Keep/add management endpoints**

Keep: `get_briefing`, `get_management`, `get_nudges`, `get_goals`, `get_agents`

Add:
```python
@router.get("/team/health")
async def get_team_health():
    return _response(_to_dict(cache.team_health))

@router.get("/status")
async def get_status():
    """Minimal system self-check."""
    return _response({"healthy": True})  # Placeholder — system_check agent provides detail
```

**Step 3: Simplify response helper**

Replace `_fast_response` and `_slow_response` with single `_response`:

```python
def _response(data: Any) -> JSONResponse:
    return JSONResponse(content=data, headers={"X-Cache-Age": str(cache.cache_age())})
```

**Step 4: Verify**

Run: `cd ai-agents && uv run python -c "from cockpit.api.routes.data import router; print(len(router.routes))"`

**Step 5: Commit**

```bash
git add logos/api/routes/data.py
git commit -m "feat: reduce data routes to management endpoints only

Keep: briefing, management, nudges, goals, agents.
Add: team/health, status.
Remove: health, gpu, infrastructure, scout, drift, cost, readiness,
accommodations, manual."
```

### Task 4.6: Transform nudges.py collector

**Files:**
- Modify: `logos/data/nudges.py`

**Step 1: Read the current nudges collector**

Read `logos/data/nudges.py`. Identify all nudge categories.

**Step 2: Remove personal nudge categories**

Remove categories: health, briefing-age, readiness, profile, scout, drift, momentum, emergence, sufficiency.

Keep management categories: stale-1on1, overdue-coaching, feedback-followup, high-load, team-state, career-convo-stale, growth-vector-gap.

**Step 3: Remove the `briefing` parameter dependency**

The current `collect_nudges(briefing=...)` parameter passes briefing data for staleness checks. Remove this — management nudges come from management state, not briefing data.

**Step 4: Verify**

Run: `cd ai-agents && uv run python -c "from cockpit.data.nudges import collect_nudges; print('OK')"`

**Step 5: Commit**

```bash
git add logos/data/nudges.py
git commit -m "feat: strip personal nudge categories, keep management nudges only"
```

### Task 4.7: Transform profile routes

**Files:**
- Modify: `logos/api/routes/profile.py`

**Step 1: Read the current profile routes**

Read `logos/api/routes/profile.py`. Identify all endpoints.

**Step 2: Keep only 3 endpoints**

```python
# GET /api/profile — management self-awareness dimensions
# GET /api/profile/{dimension} — facts for one management dimension
# POST /api/profile/correct — correct a management self-awareness fact
```

Remove: `/api/profile/facts/pending`, `/api/profile/facts/flush`, any interview-related endpoints.

**Step 3: Verify**

Run: `cd ai-agents && uv run python -c "from cockpit.api.routes.profile import router; print('OK')"`

**Step 4: Commit**

```bash
git add logos/api/routes/profile.py
git commit -m "feat: reduce profile routes to 3 management self-awareness endpoints"
```

### Task 4.8: Remove cockpit accommodations module

**Files:**
- Delete: `cockpit/accommodations.py` (if exists at cockpit root level)

**Step 1: Check if file exists and delete**

```bash
ls cockpit/accommodations.py 2>/dev/null && rm cockpit/accommodations.py
```

**Step 2: Grep for any remaining imports**

```bash
rg "from cockpit\.accommodations" ai-agents/  --type py
rg "from cockpit\..*accommodations" ai-agents/  --type py
```

Remove any remaining import references.

**Step 3: Commit**

```bash
git add -A cockpit/
git commit -m "feat: remove cockpit accommodations module"
```

---

## Batch 5: Frontend Conversion

Remove personal pages, panels, and components.

### Task 5.1: Remove Chat page and route

**Files:**
- Modify: `hapax-mgmt-web/src/App.tsx:1-19`
- Delete: `hapax-mgmt-web/src/pages/ChatPage.tsx`

**Step 1: Edit App.tsx**

Remove the chat import and route:

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "./components/layout/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { DemosPage } from "./pages/DemosPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="demos" element={<DemosPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
```

**Step 2: Delete ChatPage**

```bash
rm hapax-mgmt-web/src/pages/ChatPage.tsx
```

**Step 3: Check for nav links to /chat**

```bash
rg "chat" hapax-mgmt-web/src/components/layout/ --type tsx
```

Remove any navigation links to `/chat`.

**Step 4: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: remove Chat page and route"
```

### Task 5.2: Remove CopilotBanner from DashboardPage

**Files:**
- Modify: `hapax-mgmt-web/src/pages/DashboardPage.tsx:1-17`
- Delete: `hapax-mgmt-web/src/components/dashboard/CopilotBanner.tsx`

**Step 1: Edit DashboardPage.tsx**

Remove CopilotBanner import and the banner section:

```tsx
import { Sidebar } from "../components/Sidebar";
import { MainPanel } from "../components/MainPanel";

export function DashboardPage() {
  return (
    <>
      <div className="flex flex-1 flex-col overflow-hidden">
        <MainPanel />
      </div>
      <Sidebar />
    </>
  );
}
```

**Step 2: Delete CopilotBanner**

```bash
rm hapax-mgmt-web/src/components/dashboard/CopilotBanner.tsx
```

**Step 3: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: remove CopilotBanner from dashboard"
```

### Task 5.3: Rewrite Sidebar to 4 management panels

**Files:**
- Modify: `hapax-mgmt-web/src/components/Sidebar.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/HealthPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/VramPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/ContainersPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/CostPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/ScoutPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/DriftPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/AccommodationPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/TimersPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/FreshnessPanel.tsx`
- Delete: `hapax-mgmt-web/src/components/sidebar/HealthHistoryChart.tsx` (if exists)

**Step 1: Delete personal panel components**

```bash
cd hapax-mgmt-web/src/components/sidebar
rm HealthPanel.tsx VramPanel.tsx ContainersPanel.tsx CostPanel.tsx ScoutPanel.tsx DriftPanel.tsx AccommodationPanel.tsx TimersPanel.tsx FreshnessPanel.tsx
ls HealthHistoryChart.tsx 2>/dev/null && rm HealthHistoryChart.tsx
```

**Step 2: Rewrite Sidebar.tsx**

Replace the 12-panel array with 4 management panels:

```tsx
import { useState, useMemo, useCallback, type ComponentType } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useManagement, useBriefing, useNudges } from "../api/hooks";
import { ManagementPanel } from "./sidebar/ManagementPanel";
import { BriefingPanel } from "./sidebar/BriefingPanel";
import { GoalsPanel } from "./sidebar/GoalsPanel";
import { SidebarStrip } from "./sidebar/SidebarStrip";

interface PanelEntry {
  id: string;
  component: ComponentType;
  defaultOrder: number;
}

const panels: PanelEntry[] = [
  { id: "team", component: ManagementPanel, defaultOrder: 0 },
  { id: "briefing", component: BriefingPanel, defaultOrder: 1 },
  { id: "goals", component: GoalsPanel, defaultOrder: 2 },
];
```

Simplify `needsAttention` to check management signals only:
```tsx
const needsAttention = useMemo(() => {
  if (mgmt?.people.some((p) => p.stale_1on1)) return true;
  if (nudges?.some((n) => n.priority_label === "critical" || n.priority_label === "high")) return true;
  return false;
}, [mgmt, nudges]);
```

Simplify `statusDots` to management signals only:
```tsx
const statusDots = useMemo(() => {
  const dots: Record<string, "green" | "yellow" | "red" | "zinc"> = {};
  dots.team = mgmt?.people.some((p) => p.stale_1on1) ? "yellow" : mgmt ? "green" : "zinc";
  dots.briefing = (() => {
    if (!briefing?.generated_at) return "zinc" as const;
    const h = (Date.now() - new Date(briefing.generated_at).getTime()) / 3_600_000;
    return h > 24 ? "yellow" as const : "green" as const;
  })();
  return dots;
}, [mgmt, briefing]);
```

Remove imports: `useHealth`, `useGpu`, `useInfrastructure`, `useDrift`.

**Step 3: Verify it builds**

Run: `cd cockpit-web && pnpm tsc --noEmit`

**Step 4: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: reduce sidebar to 4 management panels

Panels: Team (primary), Briefing, Goals. Removed 8 personal/infra panels.
Simplified attention triggers to management signals only."
```

### Task 5.4: Delete chat components directory

**Files:**
- Delete: `hapax-mgmt-web/src/components/chat/` (entire directory)

**Step 1: List and delete**

```bash
rm -rf hapax-mgmt-web/src/components/chat
```

**Step 2: Grep for any remaining imports**

```bash
rg "from.*components/chat" hapax-mgmt-web/src/ --type ts --type tsx
rg "components/chat" hapax-mgmt-web/src/
```

Remove any remaining references.

**Step 3: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: remove all chat components"
```

### Task 5.5: Remove personal API hooks

**Files:**
- Modify: `hapax-mgmt-web/src/api/hooks.ts` (or wherever hooks are defined)

**Step 1: Read the hooks file**

```bash
rg "useHealth|useGpu|useInfrastructure|useDrift|useScout|useCost|useReadiness|useAccommodations" hapax-mgmt-web/src/ --type ts -l
```

**Step 2: Remove unused hooks**

Remove: `useHealth`, `useGpu`, `useInfrastructure`, `useDrift`, `useScout`, `useCost`, `useReadiness`, `useAccommodations`.

Keep: `useManagement`, `useBriefing`, `useNudges`, `useGoals`, `useAgents`.

**Step 3: Remove unused types**

Check `hapax-mgmt-web/src/api/types.ts` for types that only served deleted endpoints and remove them.

**Step 4: Verify it builds**

Run: `cd cockpit-web && pnpm tsc --noEmit`

**Step 5: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: remove personal API hooks and unused types"
```

### Task 5.6: Clean up layout navigation

**Files:**
- Modify: `hapax-mgmt-web/src/components/layout/Layout.tsx` (or wherever nav lives)
- Delete: `hapax-mgmt-web/src/components/layout/ManualDrawer.tsx` (if exists)
- Delete: `hapax-mgmt-web/src/hooks/useInputHistory.ts` (if exists)

**Step 1: Remove chat nav link**

Find and remove any navigation link to `/chat` in the layout header/nav.

**Step 2: Delete ManualDrawer if it exists**

```bash
ls hapax-mgmt-web/src/components/layout/ManualDrawer.tsx 2>/dev/null && rm hapax-mgmt-web/src/components/layout/ManualDrawer.tsx
```

**Step 3: Delete useInputHistory if it exists**

```bash
ls hapax-mgmt-web/src/hooks/useInputHistory.ts 2>/dev/null && rm hapax-mgmt-web/src/hooks/useInputHistory.ts
```

**Step 4: Verify it builds**

Run: `cd cockpit-web && pnpm tsc --noEmit`

**Step 5: Commit**

```bash
git add -A hapax-mgmt-web/src/
git commit -m "feat: clean up layout navigation, remove manual drawer and chat nav"
```

---

## Batch 6: Docker and Configuration

Update Docker images and Claude Code configuration for management purpose.

### Task 6.1: Rename and slim down Dockerfile

**Files:**
- Modify: `Dockerfile` (if exists) or `Dockerfile.api`

**Step 1: Read the existing Dockerfile**

Read whichever Dockerfile exists for the logos API.

**Step 2: Update image metadata**

```dockerfile
# management-cockpit — Management support system
# 5 agents + logos API + demo (HTML/markdown mode)
```

**Step 3: Ensure demo deps are included but heavy deps excluded**

Include: matplotlib, d2 (if available), Marp CLI (via npx)
Exclude: playwright, moviepy, chatterbox, docling

**Step 4: Verify build**

Run: `cd ai-agents && docker build -t management-cockpit -f Dockerfile .`

**Step 5: Commit**

```bash
git add Dockerfile*
git commit -m "feat: rename and slim Dockerfile for management-cockpit image"
```

### Task 6.2: Remove Dockerfile.ingest

**Files:**
- Delete: `Dockerfile.ingest` (if exists)

**Step 1: Delete**

```bash
rm -f Dockerfile.ingest
```

**Step 2: Commit**

```bash
git add -A ai-agents/ 
git commit -m "feat: remove Dockerfile.ingest (no management function)"
```

### Task 6.3: Update docker-compose.yml

**Files:**
- Modify: `llm-stack/docker-compose.yml`

**Step 1: Read the current compose file**

Read `llm-stack/docker-compose.yml` and find the hapax-agents and hapax-ingest service definitions.

**Step 2: Replace with management-cockpit service**

Replace `hapax-agents` with:
```yaml
  management-cockpit:
    build:
      context: ../ai-agents
      dockerfile: Dockerfile
    ports:
      - "127.0.0.1:8051:8050"
    environment:
      - LITELLM_API_BASE=http://litellm:4000
      - LITELLM_API_KEY=${LITELLM_API_KEY}
      - QDRANT_URL=http://qdrant:6333
      - OLLAMA_URL=http://ollama:11434
      - LANGFUSE_HOST=http://langfuse:3000
      - NTFY_BASE_URL=http://ntfy:8090
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - AXIOMS_PATH=/app/axioms
    volumes:
      - management_data:/data
      - ${VAULT_PATH:-/path/to/vault}:/vault
      - ../axioms:/app/axioms:ro
    networks:
      - llm-stack
    profiles:
      - management
    restart: unless-stopped
```

**Step 3: Remove hapax-ingest service entirely**

Delete the `hapax-ingest` service block.

**Step 4: Verify compose is valid**

Run: `cd llm-stack && docker compose config --quiet`

**Step 5: Commit**

```bash
git add llm-stack/docker-compose.yml
git commit -m "feat: replace hapax-agents with management-cockpit in compose

Remove hapax-ingest. Add vault mount (read-write), axioms mount (read-only).
Management profile with VAULT_PATH env var."
```

### Task 6.4: Update Dockerfile.dev for management-dev

**Files:**
- Modify: `Dockerfile.dev`

**Step 1: Read the current Dockerfile.dev**

Already read. Update the image description and environment variables.

**Step 2: Update metadata and env vars**

- Change description comment to: `management-dev — Interactive Claude Code with management-focused configuration`
- Keep all the Claude Code setup, hooks, skills, rules, agents infrastructure
- The content changes (which skills/rules are present) happen via the file deletions in Batch 7

**Step 3: Commit**

```bash
git add Dockerfile.dev
git commit -m "feat: rename Dockerfile.dev for management-dev image"
```

### Task 6.5: Remove personal Claude Code skills

**Files:**
- Delete: `hapax-system/skills/briefing/`
- Delete: `hapax-system/skills/status/`
- Delete: `hapax-system/skills/vram/`
- Delete: `hapax-system/skills/ingest/`
- Delete: `hapax-system/skills/studio/`
- Delete: `hapax-system/skills/deploy-check/`
- Delete: `hapax-system/skills/axiom-sweep/`

**Step 1: Delete skill directories**

```bash
cd hapax-system/skills
rm -rf briefing status vram ingest studio deploy-check axiom-sweep
```

**Step 2: Verify kept skills exist**

```bash
ls hapax-system/skills/*/SKILL.md
```

Expected: axiom-check, axiom-review, weekly-review, demo

**Step 3: Commit**

```bash
git add -A hapax-system/skills/
git commit -m "feat: remove 7 non-management Claude Code skills

Kept: axiom-check, axiom-review, weekly-review, demo"
```

### Task 6.6: Remove personal Claude Code agents and rules

**Files:**
- Delete: `hapax-system/agents/operator-voice/` (if exists)
- Delete: `hapax-system/agents/convention-guard/` (if exists)
- Delete: `hapax-system/agents/infra-check/` (if exists)

**Step 1: Check what agent directories exist**

```bash
ls hapax-system/agents/ 2>/dev/null
```

**Step 2: Delete non-management agents**

```bash
rm -rf hapax-system/agents/operator-voice hapax-system/agents/convention-guard hapax-system/agents/infra-check 2>/dev/null
```

**Step 3: Commit**

```bash
git add -A hapax-system/
git commit -m "feat: remove non-management Claude Code agents"
```

---

## Batch 7: Shared Module Transforms and Cleanup

Transform remaining shared modules and update project configuration.

### Task 7.1: Transform profile_store.py

**Files:**
- Modify: `shared/profile_store.py`

**Step 1: Read the current profile_store**

Read `shared/profile_store.py`. Find the dimension list/validation.

**Step 2: Replace with 6 management dimensions**

Update any dimension constants or validation to only accept:
- `management_practice`
- `team_leadership`
- `decision_patterns`
- `communication_style`
- `attention_distribution`
- `self_awareness`

**Step 3: Verify**

Run: `cd ai-agents && uv run python -c "from shared.profile_store import *; print('OK')"`

**Step 4: Commit**

```bash
git add shared/profile_store.py
git commit -m "feat: reduce profile_store to 6 management dimensions"
```

### Task 7.2: Transform operator.py

**Files:**
- Modify: `shared/operator.py`

**Step 1: Read the current operator module**

Read `shared/operator.py`. Identify goal tracking and metadata.

**Step 2: Filter to management goals**

If goals have a domain/tag field, filter to management-tagged goals only. If not, add a management filter mechanism.

**Step 3: Remove non-management metadata**

Remove any personal metadata fields (neurocognitive profile, etc.) that aren't management-relevant.

**Step 4: Verify**

Run: `cd ai-agents && uv run python -c "from shared.operator import *; print('OK')"`

**Step 5: Commit**

```bash
git add shared/operator.py
git commit -m "feat: filter operator.py to management goals and metadata"
```

### Task 7.3: Transform context_tools.py

**Files:**
- Modify: `shared/context_tools.py`

**Step 1: Read the current context_tools**

Read `shared/context_tools.py`. Identify the 5 tool functions.

**Step 2: Narrow constraint categories**

Update `lookup_constraints` to return management-relevant constraints only.
Update `search_profile` to use management dimensions only.
Keep `lookup_sufficiency_requirements` unchanged.

**Step 3: Verify**

Run: `cd ai-agents && uv run python -c "from shared.context_tools import *; print('OK')"`

**Step 4: Commit**

```bash
git add shared/context_tools.py
git commit -m "feat: narrow context_tools to management-relevant constraints"
```

### Task 7.4: Update agent registry

**Files:**
- Modify: `logos/data/agents.py`

**Step 1: Read the agent registry**

Read `logos/data/agents.py`. Identify how agents are registered.

**Step 2: Update to only list management agents**

Keep: management_prep, meeting_lifecycle, management_briefing, management_profiler, management_activity, demo, system_check.

Remove all other agent entries.

**Step 3: Verify**

Run: `cd ai-agents && uv run python -c "from cockpit.data.agents import get_agent_registry; print(len(get_agent_registry()))"`

**Step 4: Commit**

```bash
git add logos/data/agents.py
git commit -m "feat: update agent registry to management agents only"
```

### Task 7.5: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml`

**Step 1: Read the current pyproject.toml**

Identify all dependencies.

**Step 2: Remove dependencies only used by deleted agents**

Candidates for removal (verify no kept code uses them):
- Any packages only imported by scout, digest, knowledge_maint, drift_detector, code_review, research, introspect, ingest
- docling, watchdog (ingest-only)
- playwright, moviepy, chatterbox (demo video-only, excluded from container)

Keep: pydantic-ai, litellm, fastapi, uvicorn, qdrant-client, langfuse, httpx, pyyaml, matplotlib (demo charts)

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: remove unused dependencies from pyproject.toml"
```

### Task 7.6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (repo root)

**Step 1: Rewrite for management purpose**

Replace the containerization-focused CLAUDE.md with management cockpit context:
- What the system is (management support system)
- Agent roster (5 + demo + system_check)
- API surface (~12 endpoints)
- Axiom registry (3 active, 1 dormant)
- Safety boundary
- Key file locations

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md for management cockpit"
```

### Task 7.7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Rewrite for management agent scope**

Update project description, agent roster, project layout, testing notes.

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md for management cockpit"
```

---

## Batch 8: Test Cleanup and Verification

### Task 8.1: Remove tests for deleted agents

**Files:**
- Delete: test files for removed agents

**Step 1: Find test files for deleted agents**

```bash
find tests -name "*scout*" -o -name "*digest*" -o -name "*knowledge_maint*" -o -name "*drift*" -o -name "*code_review*" -o -name "*research*" -o -name "*introspect*" -o -name "*ingest*" -o -name "*profiler_source*"
```

**Step 2: Delete them**

**Step 3: Find tests for deleted shared modules**

```bash
find tests -name "*health_analysis*" -o -name "*health_history*" -o -name "*health_correlator*" -o -name "*incidents*" -o -name "*alert_state*" -o -name "*capacity*" -o -name "*service_graph*" -o -name "*service_tiers*" -o -name "*threshold_tuner*" -o -name "*sufficiency*" -o -name "*email_utils*"
```

**Step 4: Delete them**

**Step 5: Find tests for deleted cockpit components**

```bash
find tests -name "*chat*" -o -name "*copilot*" -o -name "*accommodation*" -o -name "*interview*"
```

**Step 6: Delete them**

**Step 7: Commit**

```bash
git add -A tests/
git commit -m "feat: remove tests for deleted agents, modules, and routes"
```

### Task 8.2: Run remaining tests

**Step 1: Run the test suite**

```bash
cd ai-agents && uv run pytest tests/ -q --tb=short 2>&1 | head -50
```

**Step 2: Fix any import errors**

Tests may fail due to missing imports from deleted modules. Fix by updating test imports or deleting tests that test deleted functionality.

**Step 3: Iterate until tests pass**

Repeat run/fix until clean.

**Step 4: Commit fixes**

```bash
git add -A ai-agents/ 
git commit -m "fix: resolve test import errors after management conversion"
```

### Task 8.3: Verify frontend builds

**Step 1: Type-check**

```bash
cd cockpit-web && pnpm tsc --noEmit
```

**Step 2: Build**

```bash
cd cockpit-web && pnpm build
```

**Step 3: Fix any errors and commit**

```bash
git add -A hapax-mgmt-web/
git commit -m "fix: resolve frontend build errors after management conversion"
```

### Task 8.4: Verify Docker builds

**Step 1: Build management-cockpit image**

```bash
cd ai-agents && docker build -t management-cockpit -f Dockerfile .
```

**Step 2: Build management-dev image**

```bash
docker build -t management-dev -f Dockerfile.dev .
```

**Step 3: Fix any build errors and commit**

```bash
git add -A
git commit -m "fix: resolve Docker build errors after management conversion"
```

---

## Summary

| Batch | Tasks | Purpose |
|-------|-------|---------|
| 1 | 1.1-1.5 | Axiom amendment — constitutional foundation |
| 2 | 2.1-2.2 | Agent & shared module deletions — remove non-management code |
| 3 | 3.1-3.4 | Agent transformations — reframe for management purpose |
| 4 | 4.1-4.8 | Logos API conversion — routes, cache, collectors |
| 5 | 5.1-5.6 | Frontend conversion — pages, panels, components |
| 6 | 6.1-6.6 | Docker & config — images, compose, Claude Code customizations |
| 7 | 7.1-7.7 | Shared module transforms & cleanup — profile, operator, docs |
| 8 | 8.1-8.4 | Test cleanup & verification — ensure everything builds and passes |

**Total:** 33 tasks across 8 batches. Batches are ordered by dependency: axioms define purpose, deletions clear the field, transformations reshape what remains, API/frontend reflect the new shape, Docker packages it, cleanup verifies.
