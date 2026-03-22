# Tier 1 Document Type Expansion — Design

**Date:** 2026-03-09
**Status:** Approved
**Approach:** Layered (Layer 1: data models + collectors, Layer 2: nudges + engine, Layer 3: demo data + frontend)

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| OKR key results | Nested YAML list in frontmatter | Usability — managing 4 files for 1 OKR is painful |
| Nudge system | Category-slotted (people:3, goals:2, operational:2) | Prevents any domain from dominating the 7-item cap |
| Incidents | Two types: `incident` + `postmortem-action` | Actions need independent deadlines and staleness tracking |
| Review cycles | Process tracking only, no content | Management safety axiom — track deadlines, not evaluations |
| Status reports | Generated draft + editable, tracked for staleness | Both input and output document |
| Goal frameworks | Both SMART and OKR available | Different scopes: OKR=team/quarterly, SMART=individual/project |
| Demo timeline | ~1 quarter (Q1 2026, Jan–Mar) | Natural OKR/review lifecycle cadence |
| SMART goals module | `smart_goals.py` (not `goals.py`) | Existing `goals.py` serves operator system goals from operator.json |

## New Document Types

### 1. OKR (`data/okrs/`)

```yaml
---
type: okr
scope: team                # team | individual | org
team: Platform             # team name (if scope=team)
person: ""                 # person name (if scope=individual)
quarter: 2026-Q1
status: active             # active | scored | archived
objective: Improve platform reliability to support 10x traffic growth
key-results:
  - id: kr1
    description: Reduce P99 latency from 450ms to under 200ms
    target: 200
    current: 310
    unit: ms
    direction: decrease    # increase | decrease
    confidence: 0.6        # 0.0-1.0
    last-updated: "2026-02-28"
  - id: kr2
    description: Achieve 99.95% uptime
    target: 99.95
    current: 99.91
    unit: percent
    direction: increase
    confidence: 0.7
    last-updated: "2026-02-28"
score: null                # 0.0-1.0 final (null until scored)
scored-at: ""
---
Context, alignment notes, links to parent OKR.
```

**Dataclass:**

```python
@dataclass
class KeyResultState:
    id: str
    description: str
    target: float
    current: float
    unit: str = ""
    direction: str = "increase"
    confidence: float | None = None
    last_updated: str = ""
    stale: bool = False          # computed: last_updated > 14 days

@dataclass
class OKRState:
    objective: str
    scope: str = "team"
    team: str = ""
    person: str = ""
    quarter: str = ""
    status: str = "active"
    key_results: list[KeyResultState] = field(default_factory=list)
    score: float | None = None
    scored_at: str = ""
    file_path: Path | None = None
    at_risk_count: int = 0       # KRs with confidence < 0.5
    stale_kr_count: int = 0      # KRs with last_updated > 14d

@dataclass
class OKRSnapshot:
    okrs: list[OKRState] = field(default_factory=list)
    active_count: int = 0
    at_risk_count: int = 0
    stale_kr_count: int = 0
```

### 2. SMART Goal (`data/goals/`)

```yaml
---
type: goal
framework: smart
person: Sarah Chen
status: active             # active | completed | deferred | abandoned
category: career-development  # career-development | skill-building | project | stretch
created: "2026-01-15"
target-date: "2026-06-30"
last-reviewed: "2026-02-10"
review-cadence: quarterly  # monthly | quarterly
linked-okr: ""             # filename of related OKR (optional)
specific: Lead a cross-team architecture review for the database migration
measurable: Architecture proposal approved by 3+ team leads
achievable: Has led single-team reviews; cross-team is the stretch
relevant: Aligns with principal engineer promotion criteria
time-bound: Complete by end of Q2 2026
progress-notes:
  - date: "2026-02-10"
    note: Identified 3 candidate reviews. Scheduled first for March.
---
Extended context and notes.
```

**Dataclass:**

```python
@dataclass
class SmartGoalState:
    person: str
    specific: str
    status: str = "active"
    framework: str = "smart"
    category: str = ""
    created: str = ""
    target_date: str = ""
    last_reviewed: str = ""
    review_cadence: str = "quarterly"
    linked_okr: str = ""
    measurable: str = ""
    achievable: str = ""
    relevant: str = ""
    time_bound: str = ""
    file_path: Path | None = None
    days_until_due: int | None = None
    overdue: bool = False
    review_overdue: bool = False
    days_since_review: int | None = None

@dataclass
class SmartGoalSnapshot:
    goals: list[SmartGoalState] = field(default_factory=list)
    active_count: int = 0
    overdue_count: int = 0
    review_overdue_count: int = 0
```

### 3. Incident (`data/incidents/`)

```yaml
---
type: incident
title: API gateway outage — connection pool exhaustion
severity: sev1             # sev1 | sev2 | sev3
status: postmortem-complete  # detected | mitigated | investigating | postmortem-complete | closed
detected: "2026-02-15T14:30:00"
mitigated: "2026-02-15T15:45:00"
duration-minutes: 75
impact: 503 errors for 40% of API traffic
root-cause: Connection pool leak under sustained load
owner: Marcus Johnson
teams-affected:
  - Platform
  - Product
---
Timeline and postmortem narrative.
```

**Dataclass:**

```python
@dataclass
class IncidentState:
    title: str
    severity: str = "sev3"
    status: str = "detected"
    detected: str = ""
    mitigated: str = ""
    duration_minutes: int | None = None
    impact: str = ""
    root_cause: str = ""
    owner: str = ""
    teams_affected: list[str] = field(default_factory=list)
    file_path: Path | None = None
    open: bool = False
    has_postmortem: bool = False

@dataclass
class IncidentSnapshot:
    incidents: list[IncidentState] = field(default_factory=list)
    open_count: int = 0
    missing_postmortem_count: int = 0
```

### 4. Postmortem Action (`data/postmortem-actions/`)

```yaml
---
type: postmortem-action
incident-ref: 2026-02-15-api-gateway-outage
title: Add connection pool exhaustion alerting
owner: Marcus Johnson
status: open               # open | in-progress | completed | wont-fix
priority: high             # critical | high | medium | low
due-date: "2026-03-01"
completed-date: ""
---
Add Prometheus alerting for connection pool utilization > 80%.
```

**Dataclass:**

```python
@dataclass
class PostmortemActionState:
    title: str
    incident_ref: str = ""
    owner: str = ""
    status: str = "open"
    priority: str = "medium"
    due_date: str = ""
    completed_date: str = ""
    file_path: Path | None = None
    overdue: bool = False
    days_overdue: int = 0

@dataclass
class PostmortemActionSnapshot:
    actions: list[PostmortemActionState] = field(default_factory=list)
    open_count: int = 0
    overdue_count: int = 0
```

### 5. Review Cycle (`data/review-cycles/`)

```yaml
---
type: review-cycle
cycle: 2026-H1
person: Sarah Chen
status: self-assessment-due  # not-started | self-assessment-due | writing | calibration | delivered
self-assessment-due: "2026-04-15"
self-assessment-received: false
peer-feedback-requested: 3
peer-feedback-received: 1
review-due: "2026-05-01"
calibration-date: "2026-05-10"
delivered: false
---
Process notes (no content about the person's performance).
```

**Dataclass:**

```python
@dataclass
class ReviewCycleState:
    person: str
    cycle: str = ""
    status: str = "not-started"
    self_assessment_due: str = ""
    self_assessment_received: bool = False
    peer_feedback_requested: int = 0
    peer_feedback_received: int = 0
    review_due: str = ""
    calibration_date: str = ""
    delivered: bool = False
    file_path: Path | None = None
    days_until_review_due: int | None = None
    peer_feedback_gap: int = 0
    overdue: bool = False

@dataclass
class ReviewCycleSnapshot:
    cycles: list[ReviewCycleState] = field(default_factory=list)
    active_count: int = 0
    overdue_count: int = 0
    peer_feedback_gap_total: int = 0
```

### 6. Status Report (`data/status-reports/`)

```yaml
---
type: status-report
date: "2026-03-07"
cadence: weekly            # weekly | monthly | pi
direction: upward          # upward | lateral
generated: true
edited: false
---
## Highlights
- Platform reliability OKR on track (2/3 KRs green)

## Risks
- Jordan Kim at cognitive load 5/5

## Next Week
- Sarah Chen architecture review
```

**Dataclass:**

```python
@dataclass
class StatusReportState:
    date: str
    cadence: str = "weekly"
    direction: str = "upward"
    generated: bool = False
    edited: bool = False
    file_path: Path | None = None
    days_since: int | None = None
    stale: bool = False          # weekly: >9d, monthly: >35d

@dataclass
class StatusReportSnapshot:
    reports: list[StatusReportState] = field(default_factory=list)
    latest_date: str = ""
    stale: bool = False
```

## Nudge Category System

### Slot Allocation

| Category | Slots | Covers |
|----------|-------|--------|
| `people` | 3 | Stale 1:1s, overdue coaching/feedback, high load, career staleness, team health, review cycles |
| `goals` | 2 | OKR at-risk KRs, stale KR updates, unscored OKRs, overdue SMART goals, stale goal reviews |
| `operational` | 2 | Overdue postmortem actions, open incidents without postmortem, stale status reports |

Total cap: 7 (unchanged). Unused slots redistribute to highest-priority overflow.

### Priority Scores

**People category (existing + new):**

| Condition | Score | Source |
|-----------|-------|--------|
| Team falling behind | 75 | team_health |
| Stale 1:1 | 70 | management |
| Overdue feedback follow-up | 65 | management |
| Review cycle overdue | 65 | review_cycles |
| Peer feedback gap ≥ 2 | 60 | review_cycles |
| High cognitive load | 60 | management |
| Treading water, no coaching | 55 | team_health |
| Overdue coaching check-in | 55 | management |
| Career convo stale (>180d) | 50 | career |
| No growth vector | 40 | career |

**Goals category (all new):**

| Condition | Score | Source |
|-----------|-------|--------|
| Unscored OKR (quarter ended) | 70 | okrs |
| At-risk KR (confidence < 0.5 at mid-quarter+) | 65 | okrs |
| SMART goal overdue (past target-date) | 65 | smart_goals |
| SMART goal deadline approaching (<30d) | 55 | smart_goals |
| Stale KR update (>14 days) | 50 | okrs |
| SMART goal review overdue | 45 | smart_goals |
| No active goals for person (>90d) | 35 | smart_goals |

**Operational category (all new):**

| Condition | Score | Source |
|-----------|-------|--------|
| Open incident without postmortem (>7d) | 70 | incidents |
| Overdue postmortem action | 65 | postmortem_actions |
| Status report stale | 50 | status_reports |

### Redistribution Logic

```python
CATEGORY_SLOTS = {"people": 3, "goals": 2, "operational": 2}

# 1. Group nudges by category, sort each by priority
# 2. Fill guaranteed slots per category
# 3. Unused slots go to highest-priority overflow across all categories
# 4. Final sort by priority_score descending
```

## Collectors, Bridge, Engine, API

### New Collector Modules

| Module | Scans | Returns |
|--------|-------|---------|
| `logos/data/okrs.py` | `data/okrs/*.md` | `OKRSnapshot` |
| `logos/data/smart_goals.py` | `data/goals/*.md` | `SmartGoalSnapshot` |
| `logos/data/incidents.py` | `data/incidents/*.md` | `IncidentSnapshot` |
| `logos/data/postmortem_actions.py` | `data/postmortem-actions/*.md` | `PostmortemActionSnapshot` |
| `logos/data/review_cycles.py` | `data/review-cycles/*.md` | `ReviewCycleSnapshot` |
| `logos/data/status_reports.py` | `data/status-reports/*.md` | `StatusReportSnapshot` |

Existing `logos/data/goals.py` (operator system goals from operator.json) is unchanged.

### Management Bridge Facts

| Function | Dimension | Example |
|----------|-----------|---------|
| `_okr_facts()` | `strategic_alignment` | "Team OKR: Improve platform reliability (Q1, 2/3 KRs on track)" |
| `_smart_goal_facts()` | `management_practice` | "SMART goal for Sarah Chen: Lead cross-team architecture review" |
| `_incident_facts()` | `attention_distribution` | "Sev1 incident: API gateway outage (75min, postmortem complete)" |
| `_postmortem_action_facts()` | `management_practice` | "Postmortem action (open): Add connection pool alerting" |
| `_review_cycle_facts()` | `management_practice` | "Review cycle 2026-H1 for Sarah Chen: self-assessment-due" |

Status reports don't generate bridge facts.

### Engine Rules

Six new rules, all phase 0 `refresh_cache`:

| Rule | Trigger Directory |
|------|-------------------|
| `okr_changed` | `okrs/` |
| `smart_goal_changed` | `goals/` |
| `incident_changed` | `incidents/` |
| `postmortem_action_changed` | `postmortem-actions/` |
| `review_cycle_changed` | `review-cycles/` |
| `status_report_changed` | `status-reports/` |

### Cache Additions

Six new fields on `DataCache`, populated in `_refresh_sync()`.

### API Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/okrs` | `OKRSnapshot` |
| `GET /api/smart-goals` | `SmartGoalSnapshot` |
| `GET /api/incidents` | `IncidentSnapshot` |
| `GET /api/postmortem-actions` | `PostmortemActionSnapshot` |
| `GET /api/review-cycles` | `ReviewCycleSnapshot` |
| `GET /api/status-reports` | `StatusReportSnapshot` |

## Frontend

### New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `OKRPanel` | Sidebar | KR confidence summary, at-risk indicators |
| `ReviewCyclePanel` | Sidebar | Deadline countdown, peer feedback progress |
| `IncidentBanner` | MainPanel (above NudgeList) | Open incident alert, only visible when incidents are open |

Postmortem actions and status reports surface **only through nudges**.

Existing `GoalsPanel` extended to show SMART goals alongside operator goals.

### Sidebar Order (auto-sorted by urgency)

1. ManagementPanel (people)
2. OKRPanel (goals)
3. ReviewCyclePanel (people)
4. BriefingPanel (context)
5. GoalsPanel (goals — operator + SMART)

### NudgeList Change

Category badge per nudge: `people` (blue), `goals` (amber), `operational` (red).

## Demo Data — Q1 2026 Quarter

### OKRs (3 files)

| File | Team | State |
|------|------|-------|
| `2026-q1-platform-reliability.md` | Platform | 1 KR at-risk (0.4), 1 KR stale (21d) |
| `2026-q1-product-activation.md` | Product | All KRs on track |
| `2026-q1-data-pipeline-quality.md` | Data | 2/3 KRs at-risk |

### SMART Goals (4 files)

| File | Person | State |
|------|--------|-------|
| `sarah-chen-principal-readiness.md` | Sarah Chen | Active, review on schedule |
| `alex-rivera-incident-response.md` | Alex Rivera | Active, approaching deadline (30d) |
| `marcus-johnson-tech-lead.md` | Marcus Johnson | Active, review overdue (45d) |
| `jordan-kim-data-modeling.md` | Jordan Kim | Active, past target-date |

### Incidents (2 files)

| File | Severity | State |
|------|----------|-------|
| `2026-02-15-api-gateway-outage.md` | sev1 | postmortem-complete |
| `2026-03-05-data-pipeline-stall.md` | sev2 | mitigated (no postmortem, >4d) |

### Postmortem Actions (3 files)

| File | State |
|------|-------|
| `api-gateway-connection-pool-monitor.md` | completed |
| `api-gateway-load-test-runbook.md` | open, overdue (due 2026-03-01) |
| `api-gateway-capacity-planning.md` | in-progress |

### Review Cycles (3 files)

| File | Person | State |
|------|--------|-------|
| `2026-h1-sarah-chen.md` | Sarah Chen | self-assessment-due, 1/3 peer feedback |
| `2026-h1-marcus-johnson.md` | Marcus Johnson | not-started, 5d until self-assessment due |
| `2026-h1-alex-rivera.md` | Alex Rivera | writing, ahead of schedule |

### Status Reports (2 files)

| File | State |
|------|-------|
| `2026-03-07-weekly.md` | Current, generated + edited |
| `2026-02-28-weekly.md` | History |

### Expected Nudge Output

**People (3 slots):**
- Team Data falling behind (75)
- Stale 1:1 with Jordan Kim or Marcus Johnson (70)
- Review cycle behind: Marcus Johnson (65)

**Goals (2 slots):**
- At-risk KR: Data pipeline quality (65)
- SMART goal overdue: Jordan Kim data modeling (65)

**Operational (2 slots):**
- Incident without postmortem: Data pipeline stall (70)
- Overdue postmortem action: Load test runbook (65)

## Implementation Layers

### Layer 1 — Data Models + Collectors
- Frontmatter schemas (this document)
- 6 collector modules with dataclasses
- 5 management bridge fact generators
- Unit tests for all collectors
- No nudges, no UI

### Layer 2 — Nudges + Engine Rules
- Category-slotted nudge system (refactor `collect_nudges`)
- 6 new nudge sub-collectors
- 6 engine rules
- Cache additions + API endpoints
- Tests for nudge allocation and redistribution

### Layer 3 — Demo Data + Frontend
- 17 demo seed files spanning Q1 2026
- Frontend types, hooks, components (OKRPanel, ReviewCyclePanel, IncidentBanner)
- GoalsPanel extension for SMART goals
- NudgeList category badges
- Update bootstrap script and CLAUDE.md
