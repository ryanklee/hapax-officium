# Tier 1 Document Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 5 new document types (OKR, SMART goal, incident, postmortem action, review cycle) plus status reports to the management cockpit, with category-slotted nudges, reactive engine rules, API endpoints, demo data, and frontend components.

**Architecture:** Filesystem-as-bus — markdown files with YAML frontmatter in DATA_DIR subdirectories. Collectors parse frontmatter into dataclasses. Nudges are deterministic. Reactive engine watches for changes and refreshes cache. Frontend polls API at 5-minute intervals.

**Tech Stack:** Python 3.12+ (uv, dataclasses, pytest), FastAPI, React + TypeScript + React Query, Tailwind CSS

**Design doc:** `docs/plans/2026-03-09-tier1-document-expansion-design.md`

**Existing patterns to follow:**
- Collector: `logos/data/management.py` (dataclasses + `_collect_*` functions + public `collect_*_state()`)
- Nudges: `logos/data/nudges.py` (sub-collectors appending to shared list)
- Bridge: `shared/management_bridge.py` (`_*_facts()` → `_make_fact()` → `generate_facts()`)
- Engine: `logos/engine/reactive_rules.py` (Rule + `build_default_rules()`)
- Cache: `logos/api/cache.py` (DataCache fields + `_refresh_sync()`)
- API: `logos/api/routes/data.py` (`@router.get` + `_response(_to_dict(...))`)
- Frontend types: `hapax-mgmt-web/src/api/types.ts`
- Frontend hooks: `hapax-mgmt-web/src/api/hooks.ts` (`useQuery` with `refetchInterval: SLOW`)
- Frontend client: `hapax-mgmt-web/src/api/client.ts` (api object with `get<T>` calls)
- Tests: `tests/test_management.py` pattern (tmp_path, patch DATA_DIR, `_write_md` helper)

---

## Layer 1 — Data Models + Collectors + Bridge + Tests

### Task 1: OKR Collector

**Files:**
- Create: `logos/data/okrs.py`
- Test: `tests/test_okrs.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/okrs.py — OKR state collection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectOKRs:
    def test_active_okr_with_key_results(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "2026-q1-platform.md", {
            "type": "okr",
            "scope": "team",
            "team": "Platform",
            "quarter": "2026-Q1",
            "status": "active",
            "objective": "Improve reliability",
            "key-results": [
                {"id": "kr1", "description": "Reduce P99", "target": 200, "current": 310,
                 "unit": "ms", "direction": "decrease", "confidence": 0.6, "last-updated": "2026-02-28"},
                {"id": "kr2", "description": "Uptime", "target": 99.95, "current": 99.91,
                 "unit": "percent", "direction": "increase", "confidence": 0.8, "last-updated": "2026-03-05"},
            ],
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.active_count == 1
        assert len(snap.okrs) == 1
        okr = snap.okrs[0]
        assert okr.objective == "Improve reliability"
        assert okr.team == "Platform"
        assert len(okr.key_results) == 2
        assert okr.key_results[0].confidence == 0.6

    def test_scored_okr_excluded_from_active(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "2025-q4-done.md", {
            "type": "okr", "status": "scored", "objective": "Old OKR",
            "quarter": "2025-Q4", "score": 0.7, "scored-at": "2026-01-05",
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.active_count == 0
        assert len(snap.okrs) == 1

    def test_at_risk_kr_counted(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "2026-q1-risk.md", {
            "type": "okr", "status": "active", "objective": "Risky",
            "quarter": "2026-Q1",
            "key-results": [
                {"id": "kr1", "description": "Bad", "target": 100, "current": 10,
                 "confidence": 0.3, "last-updated": "2026-03-01"},
                {"id": "kr2", "description": "Ok", "target": 100, "current": 80,
                 "confidence": 0.9, "last-updated": "2026-03-01"},
            ],
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.at_risk_count == 1
        assert snap.okrs[0].at_risk_count == 1

    def test_stale_kr_detected(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "2026-q1-stale.md", {
            "type": "okr", "status": "active", "objective": "Stale",
            "quarter": "2026-Q1",
            "key-results": [
                {"id": "kr1", "description": "Old", "target": 100, "current": 50,
                 "confidence": 0.7, "last-updated": "2026-01-01"},
            ],
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.stale_kr_count == 1
        assert snap.okrs[0].key_results[0].stale is True

    def test_missing_dir_returns_empty(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.okrs == []
        assert snap.active_count == 0

    def test_no_key_results_field(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "2026-q1-bare.md", {
            "type": "okr", "status": "active", "objective": "Bare OKR",
            "quarter": "2026-Q1",
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert len(snap.okrs) == 1
        assert snap.okrs[0].key_results == []

    def test_wrong_type_skipped(self, tmp_path: Path):
        from cockpit.data.okrs import collect_okr_state

        _write_md(tmp_path / "okrs" / "not-okr.md", {
            "type": "person", "name": "Alice",
        })

        with patch("cockpit.data.okrs.DATA_DIR", tmp_path):
            snap = collect_okr_state()

        assert snap.okrs == []
```

**Step 2: Run tests to verify they fail**

Run: `cd ai-agents && uv run pytest tests/test_okrs.py -v`
Expected: ImportError — `cockpit.data.okrs` does not exist

**Step 3: Write the collector**

Create `logos/data/okrs.py`:

```python
"""OKR state collector — reads from DATA_DIR/okrs/.

Deterministic, no LLM calls. Parses OKR markdown files with nested
key-results in YAML frontmatter. Computes at-risk and stale KR counts.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)

_KR_STALE_DAYS = 14


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
    stale: bool = False


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
    at_risk_count: int = 0
    stale_kr_count: int = 0


@dataclass
class OKRSnapshot:
    okrs: list[OKRState] = field(default_factory=list)
    active_count: int = 0
    at_risk_count: int = 0
    stale_kr_count: int = 0


def _parse_key_results(raw: list | None) -> list[KeyResultState]:
    if not raw or not isinstance(raw, list):
        return []

    today = date.today()
    results: list[KeyResultState] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        last_updated = str(item.get("last-updated", ""))
        stale = False
        if last_updated:
            try:
                d = date.fromisoformat(last_updated)
                stale = (today - d).days > _KR_STALE_DAYS
            except (ValueError, TypeError):
                pass

        conf_raw = item.get("confidence")
        confidence = float(conf_raw) if conf_raw is not None else None

        results.append(KeyResultState(
            id=str(item.get("id", "")),
            description=str(item.get("description", "")),
            target=float(item.get("target", 0)),
            current=float(item.get("current", 0)),
            unit=str(item.get("unit", "")),
            direction=str(item.get("direction", "increase")),
            confidence=confidence,
            last_updated=last_updated,
            stale=stale,
        ))
    return results


def collect_okr_state() -> OKRSnapshot:
    """Collect OKR state from DATA_DIR/okrs/."""
    okrs_dir = DATA_DIR / "okrs"
    if not okrs_dir.is_dir():
        return OKRSnapshot()

    okrs: list[OKRState] = []
    for path in sorted(okrs_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "okr":
            continue

        krs = _parse_key_results(fm.get("key-results"))
        at_risk = sum(1 for kr in krs if kr.confidence is not None and kr.confidence < 0.5)
        stale = sum(1 for kr in krs if kr.stale)

        score_raw = fm.get("score")
        score = float(score_raw) if score_raw is not None else None

        okr = OKRState(
            objective=str(fm.get("objective", "")),
            scope=str(fm.get("scope", "team")),
            team=str(fm.get("team", "")),
            person=str(fm.get("person", "")),
            quarter=str(fm.get("quarter", "")),
            status=str(fm.get("status", "active")),
            key_results=krs,
            score=score,
            scored_at=str(fm.get("scored-at", "")),
            file_path=path,
            at_risk_count=at_risk,
            stale_kr_count=stale,
        )
        okrs.append(okr)

    active = [o for o in okrs if o.status == "active"]
    return OKRSnapshot(
        okrs=okrs,
        active_count=len(active),
        at_risk_count=sum(o.at_risk_count for o in active),
        stale_kr_count=sum(o.stale_kr_count for o in active),
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd ai-agents && uv run pytest tests/test_okrs.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add logos/data/okrs.py tests/test_okrs.py
git commit -m "feat: add OKR collector with nested key-result parsing"
```

---

### Task 2: SMART Goal Collector

**Files:**
- Create: `logos/data/smart_goals.py`
- Test: `tests/test_smart_goals.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/smart_goals.py — SMART goal collection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectSmartGoals:
    def test_active_goal(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        _write_md(tmp_path / "goals" / "sarah-principal.md", {
            "type": "goal", "framework": "smart", "person": "Sarah Chen",
            "status": "active", "category": "career-development",
            "created": "2026-01-15", "target-date": "2026-06-30",
            "last-reviewed": "2026-03-01", "review-cadence": "quarterly",
            "specific": "Lead cross-team review",
            "measurable": "Approved by 3+ leads",
            "achievable": "Has led single-team reviews",
            "relevant": "Aligns with promo criteria",
            "time-bound": "Q2 2026",
        })

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.active_count == 1
        assert snap.goals[0].person == "Sarah Chen"
        assert snap.goals[0].specific == "Lead cross-team review"

    def test_overdue_goal(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        _write_md(tmp_path / "goals" / "jordan-overdue.md", {
            "type": "goal", "framework": "smart", "person": "Jordan Kim",
            "status": "active", "target-date": "2026-01-15",
            "specific": "Past due goal",
        })

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.overdue_count == 1
        assert snap.goals[0].overdue is True

    def test_review_overdue(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        _write_md(tmp_path / "goals" / "marcus-stale.md", {
            "type": "goal", "framework": "smart", "person": "Marcus",
            "status": "active", "last-reviewed": "2025-10-01",
            "review-cadence": "quarterly", "specific": "Stale review",
        })

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.review_overdue_count == 1
        assert snap.goals[0].review_overdue is True

    def test_completed_excluded_from_active(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        _write_md(tmp_path / "goals" / "done.md", {
            "type": "goal", "framework": "smart", "person": "Alice",
            "status": "completed", "specific": "Done goal",
        })

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.active_count == 0
        assert len(snap.goals) == 1

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.goals == []

    def test_wrong_type_skipped(self, tmp_path: Path):
        from cockpit.data.smart_goals import collect_smart_goal_state

        _write_md(tmp_path / "goals" / "not-goal.md", {
            "type": "person", "name": "Alice",
        })

        with patch("cockpit.data.smart_goals.DATA_DIR", tmp_path):
            snap = collect_smart_goal_state()

        assert snap.goals == []
```

**Step 2: Run tests — expect ImportError**

**Step 3: Write the collector**

Create `logos/data/smart_goals.py`:

```python
"""SMART goal collector — reads from DATA_DIR/goals/.

Deterministic, no LLM calls. Tracks individual development goals
with SMART framework fields, deadline tracking, and review cadence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)

_REVIEW_CADENCE_DAYS: dict[str, int] = {
    "monthly": 35,
    "quarterly": 100,
}


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


def _days_until(date_str: str) -> int | None:
    if not date_str:
        return None
    try:
        d = date.fromisoformat(str(date_str))
        return (d - date.today()).days
    except (ValueError, TypeError):
        return None


def _days_since(date_str: str) -> int | None:
    if not date_str:
        return None
    try:
        d = date.fromisoformat(str(date_str))
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


def collect_smart_goal_state() -> SmartGoalSnapshot:
    """Collect SMART goal state from DATA_DIR/goals/."""
    goals_dir = DATA_DIR / "goals"
    if not goals_dir.is_dir():
        return SmartGoalSnapshot()

    goals: list[SmartGoalState] = []
    for path in sorted(goals_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "goal":
            continue

        status = str(fm.get("status", "active"))
        target_date = str(fm.get("target-date", ""))
        last_reviewed = str(fm.get("last-reviewed", ""))
        review_cadence = str(fm.get("review-cadence", "quarterly"))

        days_until_due = _days_until(target_date)
        overdue = status == "active" and days_until_due is not None and days_until_due < 0

        days_since_review = _days_since(last_reviewed)
        review_threshold = _REVIEW_CADENCE_DAYS.get(review_cadence, 100)
        review_overdue = (
            status == "active"
            and days_since_review is not None
            and days_since_review > review_threshold
        )

        goal = SmartGoalState(
            person=str(fm.get("person", "")),
            specific=str(fm.get("specific", "")),
            status=status,
            framework=str(fm.get("framework", "smart")),
            category=str(fm.get("category", "")),
            created=str(fm.get("created", "")),
            target_date=target_date,
            last_reviewed=last_reviewed,
            review_cadence=review_cadence,
            linked_okr=str(fm.get("linked-okr", "")),
            measurable=str(fm.get("measurable", "")),
            achievable=str(fm.get("achievable", "")),
            relevant=str(fm.get("relevant", "")),
            time_bound=str(fm.get("time-bound", "")),
            file_path=path,
            days_until_due=days_until_due,
            overdue=overdue,
            review_overdue=review_overdue,
            days_since_review=days_since_review,
        )
        goals.append(goal)

    active = [g for g in goals if g.status == "active"]
    return SmartGoalSnapshot(
        goals=goals,
        active_count=len(active),
        overdue_count=sum(1 for g in active if g.overdue),
        review_overdue_count=sum(1 for g in active if g.review_overdue),
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add logos/data/smart_goals.py tests/test_smart_goals.py
git commit -m "feat: add SMART goal collector with deadline and review tracking"
```

---

### Task 3: Incident Collector

**Files:**
- Create: `logos/data/incidents.py`
- Test: `tests/test_incidents.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/incidents.py — incident state collection."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectIncidents:
    def test_open_incident(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        _write_md(tmp_path / "incidents" / "2026-03-05-outage.md", {
            "type": "incident", "title": "API outage",
            "severity": "sev1", "status": "mitigated",
            "detected": "2026-03-05T14:00:00",
            "owner": "Marcus Johnson",
            "teams-affected": ["Platform"],
        })

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.open_count == 1
        assert snap.incidents[0].open is True
        assert snap.incidents[0].severity == "sev1"

    def test_closed_incident_not_open(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        _write_md(tmp_path / "incidents" / "2026-02-15-resolved.md", {
            "type": "incident", "title": "Resolved",
            "severity": "sev2", "status": "closed",
        })

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.open_count == 0
        assert snap.incidents[0].open is False

    def test_missing_postmortem_counted(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        _write_md(tmp_path / "incidents" / "2026-03-01-no-pm.md", {
            "type": "incident", "title": "No postmortem",
            "severity": "sev2", "status": "mitigated",
        })

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.missing_postmortem_count == 1
        assert snap.incidents[0].has_postmortem is False

    def test_postmortem_complete_has_postmortem(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        _write_md(tmp_path / "incidents" / "2026-02-15-done.md", {
            "type": "incident", "title": "Done",
            "severity": "sev1", "status": "postmortem-complete",
        })

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.incidents[0].has_postmortem is True

    def test_teams_affected_parsed(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        _write_md(tmp_path / "incidents" / "2026-03-05-multi.md", {
            "type": "incident", "title": "Multi-team",
            "severity": "sev1", "status": "mitigated",
            "teams-affected": ["Platform", "Product", "Data"],
        })

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.incidents[0].teams_affected == ["Platform", "Product", "Data"]

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.incidents import collect_incident_state

        with patch("cockpit.data.incidents.DATA_DIR", tmp_path):
            snap = collect_incident_state()

        assert snap.incidents == []
```

**Step 2: Run tests — expect ImportError**

**Step 3: Write the collector**

Create `logos/data/incidents.py`:

```python
"""Incident state collector — reads from DATA_DIR/incidents/.

Deterministic, no LLM calls. Tracks incident status, severity,
and whether a postmortem has been completed.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)

_CLOSED_STATUSES = frozenset({"postmortem-complete", "closed"})
_POSTMORTEM_STATUSES = frozenset({"postmortem-complete", "closed"})


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


def collect_incident_state() -> IncidentSnapshot:
    """Collect incident state from DATA_DIR/incidents/."""
    incidents_dir = DATA_DIR / "incidents"
    if not incidents_dir.is_dir():
        return IncidentSnapshot()

    incidents: list[IncidentState] = []
    for path in sorted(incidents_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "incident":
            continue

        status = str(fm.get("status", "detected"))
        is_open = status not in _CLOSED_STATUSES
        has_pm = status in _POSTMORTEM_STATUSES

        teams_raw = fm.get("teams-affected")
        teams = [str(t) for t in teams_raw] if isinstance(teams_raw, list) else []

        dur_raw = fm.get("duration-minutes")
        duration = int(dur_raw) if dur_raw is not None else None

        incident = IncidentState(
            title=str(fm.get("title", path.stem)),
            severity=str(fm.get("severity", "sev3")),
            status=status,
            detected=str(fm.get("detected", "")),
            mitigated=str(fm.get("mitigated", "")),
            duration_minutes=duration,
            impact=str(fm.get("impact", "")),
            root_cause=str(fm.get("root-cause", "")),
            owner=str(fm.get("owner", "")),
            teams_affected=teams,
            file_path=path,
            open=is_open,
            has_postmortem=has_pm,
        )
        incidents.append(incident)

    return IncidentSnapshot(
        incidents=incidents,
        open_count=sum(1 for i in incidents if i.open),
        missing_postmortem_count=sum(
            1 for i in incidents if not i.has_postmortem and i.severity in ("sev1", "sev2")
        ),
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add logos/data/incidents.py tests/test_incidents.py
git commit -m "feat: add incident collector with postmortem tracking"
```

---

### Task 4: Postmortem Action Collector

**Files:**
- Create: `logos/data/postmortem_actions.py`
- Test: `tests/test_postmortem_actions.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/postmortem_actions.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectPostmortemActions:
    def test_open_action(self, tmp_path: Path):
        from cockpit.data.postmortem_actions import collect_postmortem_action_state

        _write_md(tmp_path / "postmortem-actions" / "add-alerting.md", {
            "type": "postmortem-action",
            "incident-ref": "2026-02-15-api-gateway-outage",
            "title": "Add alerting",
            "owner": "Marcus",
            "status": "open",
            "priority": "high",
            "due-date": "2026-03-01",
        })

        with patch("cockpit.data.postmortem_actions.DATA_DIR", tmp_path):
            snap = collect_postmortem_action_state()

        assert snap.open_count == 1
        assert snap.actions[0].title == "Add alerting"

    def test_overdue_action(self, tmp_path: Path):
        from cockpit.data.postmortem_actions import collect_postmortem_action_state

        _write_md(tmp_path / "postmortem-actions" / "overdue.md", {
            "type": "postmortem-action", "title": "Overdue task",
            "status": "open", "due-date": "2026-01-01",
        })

        with patch("cockpit.data.postmortem_actions.DATA_DIR", tmp_path):
            snap = collect_postmortem_action_state()

        assert snap.overdue_count == 1
        assert snap.actions[0].overdue is True
        assert snap.actions[0].days_overdue > 0

    def test_completed_not_open(self, tmp_path: Path):
        from cockpit.data.postmortem_actions import collect_postmortem_action_state

        _write_md(tmp_path / "postmortem-actions" / "done.md", {
            "type": "postmortem-action", "title": "Done",
            "status": "completed", "completed-date": "2026-02-20",
        })

        with patch("cockpit.data.postmortem_actions.DATA_DIR", tmp_path):
            snap = collect_postmortem_action_state()

        assert snap.open_count == 0

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.postmortem_actions import collect_postmortem_action_state

        with patch("cockpit.data.postmortem_actions.DATA_DIR", tmp_path):
            snap = collect_postmortem_action_state()

        assert snap.actions == []
```

**Step 2: Run tests — expect ImportError**

**Step 3: Write the collector**

Create `logos/data/postmortem_actions.py`:

```python
"""Postmortem action collector — reads from DATA_DIR/postmortem-actions/.

Deterministic, no LLM calls. Tracks action items from incident
postmortems with deadline and completion tracking.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)

_OPEN_STATUSES = frozenset({"open", "in-progress"})


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


def collect_postmortem_action_state() -> PostmortemActionSnapshot:
    """Collect postmortem action state from DATA_DIR/postmortem-actions/."""
    actions_dir = DATA_DIR / "postmortem-actions"
    if not actions_dir.is_dir():
        return PostmortemActionSnapshot()

    actions: list[PostmortemActionState] = []
    today = date.today()

    for path in sorted(actions_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "postmortem-action":
            continue

        status = str(fm.get("status", "open"))
        due_date = str(fm.get("due-date", ""))
        is_open = status in _OPEN_STATUSES

        overdue = False
        days_overdue = 0
        if is_open and due_date:
            try:
                d = date.fromisoformat(due_date)
                days = (today - d).days
                if days > 0:
                    overdue = True
                    days_overdue = days
            except (ValueError, TypeError):
                pass

        action = PostmortemActionState(
            title=str(fm.get("title", path.stem)),
            incident_ref=str(fm.get("incident-ref", "")),
            owner=str(fm.get("owner", "")),
            status=status,
            priority=str(fm.get("priority", "medium")),
            due_date=due_date,
            completed_date=str(fm.get("completed-date", "")),
            file_path=path,
            overdue=overdue,
            days_overdue=days_overdue,
        )
        actions.append(action)

    return PostmortemActionSnapshot(
        actions=actions,
        open_count=sum(1 for a in actions if a.status in _OPEN_STATUSES),
        overdue_count=sum(1 for a in actions if a.overdue),
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add logos/data/postmortem_actions.py tests/test_postmortem_actions.py
git commit -m "feat: add postmortem action collector with deadline tracking"
```

---

### Task 5: Review Cycle Collector

**Files:**
- Create: `logos/data/review_cycles.py`
- Test: `tests/test_review_cycles.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/review_cycles.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectReviewCycles:
    def test_active_cycle(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(tmp_path / "review-cycles" / "2026-h1-sarah.md", {
            "type": "review-cycle", "cycle": "2026-H1", "person": "Sarah Chen",
            "status": "self-assessment-due",
            "self-assessment-due": "2026-04-15",
            "self-assessment-received": False,
            "peer-feedback-requested": 3,
            "peer-feedback-received": 1,
            "review-due": "2026-05-01",
            "calibration-date": "2026-05-10",
            "delivered": False,
        })

        with patch("cockpit.data.review_cycles.DATA_DIR", tmp_path):
            snap = collect_review_cycle_state()

        assert snap.active_count == 1
        assert snap.cycles[0].person == "Sarah Chen"
        assert snap.cycles[0].peer_feedback_gap == 2

    def test_overdue_cycle(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(tmp_path / "review-cycles" / "2025-h2-late.md", {
            "type": "review-cycle", "cycle": "2025-H2", "person": "Bob",
            "status": "writing", "review-due": "2026-01-01", "delivered": False,
        })

        with patch("cockpit.data.review_cycles.DATA_DIR", tmp_path):
            snap = collect_review_cycle_state()

        assert snap.overdue_count == 1
        assert snap.cycles[0].overdue is True

    def test_delivered_excluded_from_active(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(tmp_path / "review-cycles" / "2025-h2-done.md", {
            "type": "review-cycle", "cycle": "2025-H2", "person": "Alice",
            "status": "delivered", "delivered": True,
        })

        with patch("cockpit.data.review_cycles.DATA_DIR", tmp_path):
            snap = collect_review_cycle_state()

        assert snap.active_count == 0

    def test_peer_feedback_gap_total(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        _write_md(tmp_path / "review-cycles" / "2026-h1-a.md", {
            "type": "review-cycle", "person": "A", "status": "writing",
            "peer-feedback-requested": 3, "peer-feedback-received": 1,
        })
        _write_md(tmp_path / "review-cycles" / "2026-h1-b.md", {
            "type": "review-cycle", "person": "B", "status": "writing",
            "peer-feedback-requested": 4, "peer-feedback-received": 2,
        })

        with patch("cockpit.data.review_cycles.DATA_DIR", tmp_path):
            snap = collect_review_cycle_state()

        assert snap.peer_feedback_gap_total == 4  # (3-1) + (4-2)

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.review_cycles import collect_review_cycle_state

        with patch("cockpit.data.review_cycles.DATA_DIR", tmp_path):
            snap = collect_review_cycle_state()

        assert snap.cycles == []
```

**Step 2: Run tests — expect ImportError**

**Step 3: Write the collector**

Create `logos/data/review_cycles.py`:

```python
"""Review cycle collector — reads from DATA_DIR/review-cycles/.

Deterministic, no LLM calls. Tracks performance review process
state: deadlines, self-assessments, peer feedback progress.
Does NOT track review content (management safety axiom).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)


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


def collect_review_cycle_state() -> ReviewCycleSnapshot:
    """Collect review cycle state from DATA_DIR/review-cycles/."""
    cycles_dir = DATA_DIR / "review-cycles"
    if not cycles_dir.is_dir():
        return ReviewCycleSnapshot()

    cycles: list[ReviewCycleState] = []
    today = date.today()

    for path in sorted(cycles_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "review-cycle":
            continue

        delivered = bool(fm.get("delivered", False))
        review_due = str(fm.get("review-due", ""))
        requested = int(fm.get("peer-feedback-requested", 0))
        received = int(fm.get("peer-feedback-received", 0))

        days_until = None
        overdue = False
        if review_due and not delivered:
            try:
                d = date.fromisoformat(review_due)
                days_until = (d - today).days
                overdue = days_until < 0
            except (ValueError, TypeError):
                pass

        cycle = ReviewCycleState(
            person=str(fm.get("person", "")),
            cycle=str(fm.get("cycle", "")),
            status=str(fm.get("status", "not-started")),
            self_assessment_due=str(fm.get("self-assessment-due", "")),
            self_assessment_received=bool(fm.get("self-assessment-received", False)),
            peer_feedback_requested=requested,
            peer_feedback_received=received,
            review_due=review_due,
            calibration_date=str(fm.get("calibration-date", "")),
            delivered=delivered,
            file_path=path,
            days_until_review_due=days_until,
            peer_feedback_gap=max(requested - received, 0),
            overdue=overdue,
        )
        cycles.append(cycle)

    active = [c for c in cycles if not c.delivered]
    return ReviewCycleSnapshot(
        cycles=cycles,
        active_count=len(active),
        overdue_count=sum(1 for c in active if c.overdue),
        peer_feedback_gap_total=sum(c.peer_feedback_gap for c in active),
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add logos/data/review_cycles.py tests/test_review_cycles.py
git commit -m "feat: add review cycle collector with process deadline tracking"
```

---

### Task 6: Status Report Collector

**Files:**
- Create: `logos/data/status_reports.py`
- Test: `tests/test_status_reports.py`

**Step 1: Write tests**

```python
"""Tests for logos/data/status_reports.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml


def _write_md(path: Path, frontmatter: dict, body: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_text = yaml.dump(frontmatter, default_flow_style=False)
    path.write_text(f"---\n{fm_text}---\n{body}", encoding="utf-8")


class TestCollectStatusReports:
    def test_current_report(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state
        from datetime import date

        today = date.today().isoformat()
        _write_md(tmp_path / "status-reports" / f"{today}-weekly.md", {
            "type": "status-report", "date": today,
            "cadence": "weekly", "direction": "upward",
            "generated": True, "edited": True,
        })

        with patch("cockpit.data.status_reports.DATA_DIR", tmp_path):
            snap = collect_status_report_state()

        assert len(snap.reports) == 1
        assert snap.latest_date == today
        assert snap.stale is False

    def test_stale_weekly(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        _write_md(tmp_path / "status-reports" / "2026-01-01-weekly.md", {
            "type": "status-report", "date": "2026-01-01",
            "cadence": "weekly", "direction": "upward",
        })

        with patch("cockpit.data.status_reports.DATA_DIR", tmp_path):
            snap = collect_status_report_state()

        assert snap.stale is True
        assert snap.reports[0].stale is True

    def test_missing_dir(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        with patch("cockpit.data.status_reports.DATA_DIR", tmp_path):
            snap = collect_status_report_state()

        assert snap.reports == []
        assert snap.stale is False

    def test_latest_date_is_most_recent(self, tmp_path: Path):
        from cockpit.data.status_reports import collect_status_report_state

        _write_md(tmp_path / "status-reports" / "2026-02-01-weekly.md", {
            "type": "status-report", "date": "2026-02-01", "cadence": "weekly",
        })
        _write_md(tmp_path / "status-reports" / "2026-03-01-weekly.md", {
            "type": "status-report", "date": "2026-03-01", "cadence": "weekly",
        })

        with patch("cockpit.data.status_reports.DATA_DIR", tmp_path):
            snap = collect_status_report_state()

        assert snap.latest_date == "2026-03-01"
```

**Step 2: Run tests — expect ImportError**

**Step 3: Write the collector**

Create `logos/data/status_reports.py`:

```python
"""Status report collector — reads from DATA_DIR/status-reports/.

Deterministic, no LLM calls. Tracks status report recency and
staleness based on cadence (weekly > 9 days, monthly > 35 days).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from shared.config import DATA_DIR
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

_log = logging.getLogger(__name__)

_STALE_DAYS: dict[str, int] = {
    "weekly": 9,
    "monthly": 35,
    "pi": 80,
}


@dataclass
class StatusReportState:
    date: str
    cadence: str = "weekly"
    direction: str = "upward"
    generated: bool = False
    edited: bool = False
    file_path: Path | None = None
    days_since: int | None = None
    stale: bool = False


@dataclass
class StatusReportSnapshot:
    reports: list[StatusReportState] = field(default_factory=list)
    latest_date: str = ""
    stale: bool = False


def collect_status_report_state() -> StatusReportSnapshot:
    """Collect status report state from DATA_DIR/status-reports/."""
    reports_dir = DATA_DIR / "status-reports"
    if not reports_dir.is_dir():
        return StatusReportSnapshot()

    reports: list[StatusReportState] = []
    today = date.today()

    for path in sorted(reports_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "status-report":
            continue

        report_date = str(fm.get("date", ""))
        cadence = str(fm.get("cadence", "weekly"))

        days_since = None
        stale = False
        if report_date:
            try:
                d = date.fromisoformat(report_date)
                days_since = (today - d).days
                threshold = _STALE_DAYS.get(cadence, 9)
                stale = days_since > threshold
            except (ValueError, TypeError):
                pass

        report = StatusReportState(
            date=report_date,
            cadence=cadence,
            direction=str(fm.get("direction", "upward")),
            generated=bool(fm.get("generated", False)),
            edited=bool(fm.get("edited", False)),
            file_path=path,
            days_since=days_since,
            stale=stale,
        )
        reports.append(report)

    # Find latest date
    dates = [r.date for r in reports if r.date]
    latest = max(dates) if dates else ""

    # Overall staleness based on most recent report matching its cadence
    overall_stale = False
    if reports:
        most_recent = max(reports, key=lambda r: r.date or "")
        overall_stale = most_recent.stale

    return StatusReportSnapshot(
        reports=reports,
        latest_date=latest,
        stale=overall_stale,
    )
```

**Step 4: Run tests — expect PASS**

**Step 5: Commit**

```bash
git add logos/data/status_reports.py tests/test_status_reports.py
git commit -m "feat: add status report collector with cadence-based staleness"
```

---

### Task 7: Management Bridge Facts for All 5 New Types

**Files:**
- Modify: `shared/management_bridge.py` (add 5 new `_*_facts()` functions, register in `generate_facts()`)
- Test: `tests/test_management_bridge.py` (add tests for new fact generators)

**Step 1: Write tests**

Add these test classes to `tests/test_management_bridge.py` (after existing classes):

```python
class TestOKRFacts:
    def test_okr_generates_fact(self, tmp_path: Path):
        _write_md(tmp_path / "okrs" / "2026-q1-platform.md", {
            "type": "okr", "status": "active", "objective": "Improve reliability",
            "scope": "team", "team": "Platform", "quarter": "2026-Q1",
            "key-results": [
                {"id": "kr1", "description": "P99", "target": 200, "current": 310,
                 "confidence": 0.6, "last-updated": "2026-03-01"},
            ],
        })

        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()

        okr_facts = [f for f in facts if "OKR" in f["value"]]
        assert len(okr_facts) >= 1
        assert any("Improve reliability" in f["value"] for f in okr_facts)
        assert any(f["dimension"] == "strategic_alignment" for f in okr_facts)


class TestIncidentFacts:
    def test_incident_generates_fact(self, tmp_path: Path):
        _write_md(tmp_path / "incidents" / "2026-02-15-outage.md", {
            "type": "incident", "title": "API outage", "severity": "sev1",
            "status": "postmortem-complete", "duration-minutes": 75,
        })

        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()

        incident_facts = [f for f in facts if "incident" in f["value"].lower() or "outage" in f["value"].lower()]
        assert len(incident_facts) >= 1
        assert any(f["dimension"] == "attention_distribution" for f in incident_facts)


class TestReviewCycleFacts:
    def test_review_cycle_generates_fact(self, tmp_path: Path):
        _write_md(tmp_path / "review-cycles" / "2026-h1-sarah.md", {
            "type": "review-cycle", "cycle": "2026-H1", "person": "Sarah Chen",
            "status": "self-assessment-due", "review-due": "2026-05-01",
        })

        with patch("shared.management_bridge.DATA_DIR", tmp_path):
            facts = generate_facts()

        rc_facts = [f for f in facts if "Review cycle" in f["value"] or "review" in f["value"].lower()]
        assert len(rc_facts) >= 1
        assert any(f["dimension"] == "management_practice" for f in rc_facts)
```

**Step 2: Run tests — expect failure (functions don't exist)**

**Step 3: Add 5 fact generators to `shared/management_bridge.py`**

Add these functions before `generate_facts()` (after existing `_meeting_facts`):

```python
def _okr_facts() -> list[dict]:
    """Generate facts from OKR files in DATA_DIR/okrs/."""
    okrs_dir = DATA_DIR / "okrs"
    if not okrs_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(okrs_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "okr":
            continue

        status = str(fm.get("status", "active"))
        if status == "archived":
            continue

        objective = str(fm.get("objective", ""))
        scope = str(fm.get("scope", "team"))
        team = str(fm.get("team", ""))
        quarter = str(fm.get("quarter", ""))
        krs = fm.get("key-results", [])
        kr_count = len(krs) if isinstance(krs, list) else 0
        on_track = sum(1 for kr in (krs if isinstance(krs, list) else [])
                       if isinstance(kr, dict) and (kr.get("confidence") or 0) >= 0.5)

        scope_label = f"{scope} ({team})" if team else scope
        facts.append(_make_fact(
            f"OKR ({scope_label}, {quarter}): {objective} — {on_track}/{kr_count} KRs on track",
            "strategic_alignment",
            f"okrs/{path.name}",
        ))

    return facts


def _smart_goal_facts() -> list[dict]:
    """Generate facts from SMART goal files in DATA_DIR/goals/."""
    goals_dir = DATA_DIR / "goals"
    if not goals_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(goals_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "goal":
            continue

        status = str(fm.get("status", "active"))
        if status in ("completed", "abandoned"):
            continue

        person = str(fm.get("person", ""))
        specific = str(fm.get("specific", ""))
        category = str(fm.get("category", ""))
        target_date = str(fm.get("target-date", ""))

        facts.append(_make_fact(
            f"SMART goal for {person}: {specific} ({category}, due {target_date})",
            "management_practice",
            f"goals/{path.name}",
        ))

    return facts


def _incident_facts() -> list[dict]:
    """Generate facts from incident files in DATA_DIR/incidents/."""
    incidents_dir = DATA_DIR / "incidents"
    if not incidents_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(incidents_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "incident":
            continue

        title = str(fm.get("title", path.stem))
        severity = str(fm.get("severity", "sev3"))
        status = str(fm.get("status", "detected"))
        duration = fm.get("duration-minutes")
        dur_str = f"{duration}min" if duration else "unknown duration"

        facts.append(_make_fact(
            f"{severity.upper()} incident: {title} ({dur_str}, {status})",
            "attention_distribution",
            f"incidents/{path.name}",
        ))

    return facts


def _postmortem_action_facts() -> list[dict]:
    """Generate facts from postmortem action files in DATA_DIR/postmortem-actions/."""
    actions_dir = DATA_DIR / "postmortem-actions"
    if not actions_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(actions_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "postmortem-action":
            continue

        status = str(fm.get("status", "open"))
        if status in ("completed", "wont-fix"):
            continue

        title = str(fm.get("title", path.stem))
        owner = str(fm.get("owner", ""))

        facts.append(_make_fact(
            f"Postmortem action ({status}): {title} — owner: {owner}",
            "management_practice",
            f"postmortem-actions/{path.name}",
        ))

    return facts


def _review_cycle_facts() -> list[dict]:
    """Generate facts from review cycle files in DATA_DIR/review-cycles/."""
    cycles_dir = DATA_DIR / "review-cycles"
    if not cycles_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(cycles_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "review-cycle":
            continue

        if bool(fm.get("delivered", False)):
            continue

        person = str(fm.get("person", ""))
        cycle = str(fm.get("cycle", ""))
        status = str(fm.get("status", "not-started"))
        review_due = str(fm.get("review-due", ""))

        facts.append(_make_fact(
            f"Review cycle {cycle} for {person}: {status} (due {review_due})",
            "management_practice",
            f"review-cycles/{path.name}",
        ))

    return facts
```

Then update `generate_facts()` to call them:

```python
def generate_facts(vault_path: Path | None = None) -> list[dict]:
    facts: list[dict] = []
    facts.extend(_people_facts())
    facts.extend(_coaching_facts())
    facts.extend(_feedback_facts())
    facts.extend(_meeting_facts())
    facts.extend(_okr_facts())
    facts.extend(_smart_goal_facts())
    facts.extend(_incident_facts())
    facts.extend(_postmortem_action_facts())
    facts.extend(_review_cycle_facts())

    log.info("management_bridge: generated %d facts from DATA_DIR", len(facts))
    return facts
```

**Step 4: Run all tests**

Run: `cd ai-agents && uv run pytest tests/test_management_bridge.py -v`
Expected: All tests PASS (existing + new)

**Step 5: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add shared/management_bridge.py tests/test_management_bridge.py
git commit -m "feat: add bridge facts for OKRs, goals, incidents, postmortem actions, review cycles"
```

---

### Task 8: Layer 1 Checkpoint — Run Full Suite

**Step 1: Run full test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All tests PASS (existing 1082 + ~30 new = ~1112 total)

**Step 2: Verify no regressions**

Run: `cd ai-agents && uv run pytest tests/test_management_bridge.py tests/test_integration_data_flow.py tests/test_team_health.py -v`
Expected: All existing tests still PASS

---

## Layer 2 — Nudges + Engine + Cache + API

### Task 9: Category-Slotted Nudge System

**Files:**
- Modify: `logos/data/nudges.py` (refactor `collect_nudges`, change category field on existing nudges, add 6 new sub-collectors)
- Modify: `tests/test_nudges.py` (add tests for category allocation)
- Test: `tests/test_nudge_categories.py` (new, focused on slot redistribution)

**Step 1: Write category allocation tests**

Create `tests/test_nudge_categories.py`:

```python
"""Tests for nudge category slot allocation and redistribution."""
from __future__ import annotations

from cockpit.data.nudges import Nudge, _allocate_by_category, CATEGORY_SLOTS


class TestCategoryAllocation:
    def test_each_category_gets_slots(self):
        nudges = [
            Nudge(category="people", priority_score=70, priority_label="high",
                  title="P1", detail="", suggested_action=""),
            Nudge(category="people", priority_score=65, priority_label="high",
                  title="P2", detail="", suggested_action=""),
            Nudge(category="people", priority_score=60, priority_label="medium",
                  title="P3", detail="", suggested_action=""),
            Nudge(category="people", priority_score=55, priority_label="medium",
                  title="P4", detail="", suggested_action=""),
            Nudge(category="goals", priority_score=70, priority_label="high",
                  title="G1", detail="", suggested_action=""),
            Nudge(category="goals", priority_score=65, priority_label="high",
                  title="G2", detail="", suggested_action=""),
            Nudge(category="goals", priority_score=60, priority_label="medium",
                  title="G3", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=70, priority_label="high",
                  title="O1", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=65, priority_label="high",
                  title="O2", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=60, priority_label="medium",
                  title="O3", detail="", suggested_action=""),
        ]

        result = _allocate_by_category(nudges)

        cats = [n.category for n in result]
        assert cats.count("people") == CATEGORY_SLOTS["people"]  # 3
        assert cats.count("goals") == CATEGORY_SLOTS["goals"]    # 2
        assert cats.count("operational") == CATEGORY_SLOTS["operational"]  # 2
        assert len(result) == 7

    def test_unused_slots_redistribute(self):
        nudges = [
            Nudge(category="people", priority_score=70, priority_label="high",
                  title="P1", detail="", suggested_action=""),
            Nudge(category="people", priority_score=65, priority_label="high",
                  title="P2", detail="", suggested_action=""),
            Nudge(category="people", priority_score=60, priority_label="medium",
                  title="P3", detail="", suggested_action=""),
            Nudge(category="people", priority_score=55, priority_label="medium",
                  title="P4", detail="", suggested_action=""),
            # goals has only 1 item (budget=2), so 1 slot redistributes
            Nudge(category="goals", priority_score=70, priority_label="high",
                  title="G1", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=65, priority_label="high",
                  title="O1", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=60, priority_label="medium",
                  title="O2", detail="", suggested_action=""),
        ]

        result = _allocate_by_category(nudges)

        # 3 people (budget) + 1 goals + 2 operational + 1 overflow (P4 at 55)
        assert len(result) == 7
        cats = [n.category for n in result]
        assert cats.count("people") == 4  # got the extra slot
        assert cats.count("goals") == 1
        assert cats.count("operational") == 2

    def test_empty_nudges(self):
        result = _allocate_by_category([])
        assert result == []

    def test_single_category_only(self):
        nudges = [
            Nudge(category="people", priority_score=70, priority_label="high",
                  title=f"P{i}", detail="", suggested_action="")
            for i in range(10)
        ]

        result = _allocate_by_category(nudges)

        # All 7 slots go to people (only category with items)
        assert len(result) == 7
        assert all(n.category == "people" for n in result)

    def test_result_sorted_by_priority(self):
        nudges = [
            Nudge(category="people", priority_score=40, priority_label="low",
                  title="P-low", detail="", suggested_action=""),
            Nudge(category="goals", priority_score=70, priority_label="high",
                  title="G-high", detail="", suggested_action=""),
            Nudge(category="operational", priority_score=55, priority_label="medium",
                  title="O-med", detail="", suggested_action=""),
        ]

        result = _allocate_by_category(nudges)

        scores = [n.priority_score for n in result]
        assert scores == sorted(scores, reverse=True)
```

**Step 2: Run tests — expect ImportError (\_allocate\_by\_category doesn't exist)**

**Step 3: Refactor nudges.py**

Key changes to `logos/data/nudges.py`:

1. Add `CATEGORY_SLOTS` constant
2. Change existing nudge `category` values from `"management"` to `"people"`
3. Add `_allocate_by_category()` function
4. Add 6 new sub-collectors: `_collect_okr_nudges`, `_collect_smart_goal_nudges`, `_collect_incident_nudges`, `_collect_postmortem_action_nudges`, `_collect_review_cycle_nudges`, `_collect_status_report_nudges`
5. Refactor `collect_nudges()` to call all collectors and use `_allocate_by_category`

The existing nudges in `_collect_management_nudges`, `_collect_team_health_nudges`, and `_collect_career_staleness_nudges` change `category="management"` to `category="people"`.

New sub-collectors follow this pattern (use lazy imports inside each function):

```python
def _collect_okr_nudges(nudges: list[Nudge]) -> None:
    try:
        from cockpit.data.okrs import collect_okr_state
        snap = collect_okr_state()
        # ... check conditions, append nudges with category="goals" ...
    except Exception:
        log.warning("Failed to collect OKR nudges", exc_info=True)
```

Update `collect_nudges()`:
```python
def collect_nudges(*, max_nudges: int = 7, snapshot: ManagementSnapshot | None = None) -> list[Nudge]:
    nudges: list[Nudge] = []
    _collect_management_nudges(nudges, snap=snapshot)
    _collect_team_health_nudges(nudges, snap=snapshot)
    _collect_career_staleness_nudges(nudges, snap=snapshot)
    _collect_okr_nudges(nudges)
    _collect_smart_goal_nudges(nudges)
    _collect_incident_nudges(nudges)
    _collect_postmortem_action_nudges(nudges)
    _collect_review_cycle_nudges(nudges)
    _collect_status_report_nudges(nudges)

    result = _allocate_by_category(nudges)

    if len(result) > max_nudges:
        overflow = len(result) - max_nudges
        visible = result[:max_nudges]
        visible.append(Nudge(
            category="meta", priority_score=0, priority_label="low",
            title=f"+ {overflow} more items",
            detail=f"{overflow} lower-priority items not shown",
            suggested_action="", source_id="meta:overflow",
        ))
        return visible

    return result
```

**Step 4: Run tests**

Run: `cd ai-agents && uv run pytest tests/test_nudge_categories.py tests/test_nudges.py -v`
Expected: All PASS

**Step 5: Run full suite to check regressions**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All PASS. Note: existing tests that check `category == "management"` need updating to `category == "people"`.

**Step 6: Commit**

```bash
git add logos/data/nudges.py tests/test_nudge_categories.py tests/test_nudges.py
git commit -m "feat: category-slotted nudge system with 6 new collectors"
```

---

### Task 10: Engine Rules for New Types

**Files:**
- Modify: `logos/engine/reactive_rules.py` (add 6 rules, update `build_default_rules`)

**Step 1: Add 6 new rules**

Add after `_rule_decision_logged()` (line 223), before the registry builder section:

```python
def _rule_okr_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in okrs/."""
    return Rule(
        name="okr_changed",
        description="Refresh cache on OKR changes",
        trigger_filter=lambda e: e.subdirectory == "okrs" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )


def _rule_smart_goal_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in goals/."""
    return Rule(
        name="smart_goal_changed",
        description="Refresh cache on SMART goal changes",
        trigger_filter=lambda e: e.subdirectory == "goals" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )


def _rule_incident_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in incidents/."""
    return Rule(
        name="incident_changed",
        description="Refresh cache on incident changes",
        trigger_filter=lambda e: e.subdirectory == "incidents" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )


def _rule_postmortem_action_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in postmortem-actions/."""
    return Rule(
        name="postmortem_action_changed",
        description="Refresh cache on postmortem action changes",
        trigger_filter=lambda e: e.subdirectory == "postmortem-actions" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )


def _rule_review_cycle_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in review-cycles/."""
    return Rule(
        name="review_cycle_changed",
        description="Refresh cache on review cycle changes",
        trigger_filter=lambda e: e.subdirectory == "review-cycles" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )


def _rule_status_report_changed() -> Rule:
    """Trigger on file CREATED or MODIFIED in status-reports/."""
    return Rule(
        name="status_report_changed",
        description="Refresh cache on status report changes",
        trigger_filter=lambda e: e.subdirectory == "status-reports" and e.event_type in ("created", "modified"),
        produce=lambda e: [Action(name="refresh_cache", handler=_refresh_cache, phase=0, priority=0)],
    )
```

Update `build_default_rules()` to register all 12 rules:

```python
def build_default_rules(ignore_fn: IgnoreFn = None) -> RuleRegistry:
    """Create a RuleRegistry with all 12 default reactive rules."""
    registry = RuleRegistry()
    registry.register(_rule_inbox_ingest(ignore_fn))
    registry.register(_rule_meeting_cascade(ignore_fn))
    registry.register(_rule_person_changed())
    registry.register(_rule_coaching_changed())
    registry.register(_rule_feedback_changed())
    registry.register(_rule_decision_logged())
    registry.register(_rule_okr_changed())
    registry.register(_rule_smart_goal_changed())
    registry.register(_rule_incident_changed())
    registry.register(_rule_postmortem_action_changed())
    registry.register(_rule_review_cycle_changed())
    registry.register(_rule_status_report_changed())
    return registry
```

**Step 2: Run existing engine tests**

Run: `cd ai-agents && uv run pytest tests/ -k "engine or reactive" -v`
Expected: PASS

**Step 3: Commit**

```bash
git add logos/engine/reactive_rules.py
git commit -m "feat: add 6 reactive engine rules for new document types"
```

---

### Task 11: Cache + API Endpoints

**Files:**
- Modify: `logos/api/cache.py` (add 6 fields, update `_refresh_sync`)
- Modify: `logos/api/routes/data.py` (add 6 endpoints)

**Step 1: Update cache.py**

Add fields to `DataCache` (after `team_health: Any = None`, line 25):

```python
    okrs: Any = None
    smart_goals: Any = None
    incidents: Any = None
    postmortem_actions: Any = None
    review_cycles: Any = None
    status_reports: Any = None
```

Add collector calls to `_refresh_sync()` (after the team_health try block, before nudges):

```python
        # New Tier 1 collectors
        for name, import_path, fn_name in [
            ("okrs", "cockpit.data.okrs", "collect_okr_state"),
            ("smart_goals", "cockpit.data.smart_goals", "collect_smart_goal_state"),
            ("incidents", "cockpit.data.incidents", "collect_incident_state"),
            ("postmortem_actions", "cockpit.data.postmortem_actions", "collect_postmortem_action_state"),
            ("review_cycles", "cockpit.data.review_cycles", "collect_review_cycle_state"),
            ("status_reports", "cockpit.data.status_reports", "collect_status_report_state"),
        ]:
            try:
                import importlib
                mod = importlib.import_module(import_path)
                setattr(self, name, getattr(mod, fn_name)())
            except Exception as e:
                log.warning("Refresh %s failed: %s", name, e)
```

**Step 2: Update data.py**

Add after `get_team_health()` endpoint (line 72):

```python
# ── Tier 1 expansion ──────────────────────────────────────────────────

@router.get("/okrs")
async def get_okrs():
    return _response(_to_dict(cache.okrs))


@router.get("/smart-goals")
async def get_smart_goals():
    return _response(_to_dict(cache.smart_goals))


@router.get("/incidents")
async def get_incidents():
    return _response(_to_dict(cache.incidents))


@router.get("/postmortem-actions")
async def get_postmortem_actions():
    return _response(_to_dict(cache.postmortem_actions))


@router.get("/review-cycles")
async def get_review_cycles():
    return _response(_to_dict(cache.review_cycles))


@router.get("/status-reports")
async def get_status_reports():
    return _response(_to_dict(cache.status_reports))
```

**Step 3: Run API tests**

Run: `cd ai-agents && uv run pytest tests/test_api.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add logos/api/cache.py logos/api/routes/data.py
git commit -m "feat: add cache fields and API endpoints for 6 new document types"
```

---

### Task 12: Layer 2 Checkpoint

**Step 1: Run full suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All PASS

---

## Layer 3 — Demo Data + Frontend + Docs

### Task 13: Demo Data — OKRs, SMART Goals, Incidents

**Files:**
- Create: `demo-data/okrs/` (3 files)
- Create: `demo-data/goals/` (4 files)
- Create: `demo-data/incidents/` (2 files)
- Create: `demo-data/postmortem-actions/` (3 files)
- Create: `demo-data/review-cycles/` (3 files)
- Create: `demo-data/status-reports/` (2 files)

Write all 17 demo data files per the design doc. Use the exact frontmatter schemas from the design, with dates backdated across Q1 2026. Ensure cross-references between files (e.g., postmortem actions reference incident filenames, SMART goals reference team members from existing people/ files).

**Step 1: Create all 17 files**

Follow the exact specifications from the design doc "Demo Data — Q1 2026 Quarter" section.

**Step 2: Validate demo data loads**

Run: `cd ai-agents && uv run python -c "
from unittest.mock import patch
from pathlib import Path
demo = Path('demo-data')
from cockpit.data.okrs import collect_okr_state
from cockpit.data.smart_goals import collect_smart_goal_state
from cockpit.data.incidents import collect_incident_state
from cockpit.data.postmortem_actions import collect_postmortem_action_state
from cockpit.data.review_cycles import collect_review_cycle_state
from cockpit.data.status_reports import collect_status_report_state

for name, mod, fn in [
    ('okrs', 'cockpit.data.okrs', collect_okr_state),
    ('smart_goals', 'cockpit.data.smart_goals', collect_smart_goal_state),
    ('incidents', 'cockpit.data.incidents', collect_incident_state),
    ('postmortem_actions', 'cockpit.data.postmortem_actions', collect_postmortem_action_state),
    ('review_cycles', 'cockpit.data.review_cycles', collect_review_cycle_state),
    ('status_reports', 'cockpit.data.status_reports', collect_status_report_state),
]:
    with patch(f'{mod}.DATA_DIR', demo):
        snap = fn()
    print(f'{name}: {snap}')
"`
Expected: All snapshots print with non-empty data

**Step 3: Commit**

```bash
git add demo-data/okrs/ demo-data/goals/ demo-data/incidents/ demo-data/postmortem-actions/ demo-data/review-cycles/ demo-data/status-reports/
git commit -m "feat: add quarter-spanning demo data for 6 new document types"
```

---

### Task 14: Frontend Types + Hooks + Client

**Files:**
- Modify: `hapax-mgmt-web/src/api/types.ts` (add 6 new interfaces)
- Modify: `hapax-mgmt-web/src/api/hooks.ts` (add 6 new hooks)
- Modify: `hapax-mgmt-web/src/api/client.ts` (add 6 new API calls)

**Step 1: Add types**

Append to `hapax-mgmt-web/src/api/types.ts`:

```typescript
// --- Tier 1 Expansion ---

export interface KeyResultState {
  id: string;
  description: string;
  target: number;
  current: number;
  unit: string;
  direction: string;
  confidence: number | null;
  last_updated: string;
  stale: boolean;
}

export interface OKRState {
  objective: string;
  scope: string;
  team: string;
  person: string;
  quarter: string;
  status: string;
  key_results: KeyResultState[];
  score: number | null;
  scored_at: string;
  at_risk_count: number;
  stale_kr_count: number;
}

export interface OKRSnapshot {
  okrs: OKRState[];
  active_count: number;
  at_risk_count: number;
  stale_kr_count: number;
}

export interface SmartGoalState {
  person: string;
  specific: string;
  status: string;
  framework: string;
  category: string;
  created: string;
  target_date: string;
  last_reviewed: string;
  review_cadence: string;
  linked_okr: string;
  measurable: string;
  achievable: string;
  relevant: string;
  time_bound: string;
  days_until_due: number | null;
  overdue: boolean;
  review_overdue: boolean;
  days_since_review: number | null;
}

export interface SmartGoalSnapshot {
  goals: SmartGoalState[];
  active_count: number;
  overdue_count: number;
  review_overdue_count: number;
}

export interface IncidentState {
  title: string;
  severity: string;
  status: string;
  detected: string;
  mitigated: string;
  duration_minutes: number | null;
  impact: string;
  root_cause: string;
  owner: string;
  teams_affected: string[];
  open: boolean;
  has_postmortem: boolean;
}

export interface IncidentSnapshot {
  incidents: IncidentState[];
  open_count: number;
  missing_postmortem_count: number;
}

export interface PostmortemActionState {
  title: string;
  incident_ref: string;
  owner: string;
  status: string;
  priority: string;
  due_date: string;
  completed_date: string;
  overdue: boolean;
  days_overdue: number;
}

export interface PostmortemActionSnapshot {
  actions: PostmortemActionState[];
  open_count: number;
  overdue_count: number;
}

export interface ReviewCycleState {
  person: string;
  cycle: string;
  status: string;
  self_assessment_due: string;
  self_assessment_received: boolean;
  peer_feedback_requested: number;
  peer_feedback_received: number;
  review_due: string;
  calibration_date: string;
  delivered: boolean;
  days_until_review_due: number | null;
  peer_feedback_gap: number;
  overdue: boolean;
}

export interface ReviewCycleSnapshot {
  cycles: ReviewCycleState[];
  active_count: number;
  overdue_count: number;
  peer_feedback_gap_total: number;
}

export interface StatusReportState {
  date: string;
  cadence: string;
  direction: string;
  generated: boolean;
  edited: boolean;
  days_since: number | null;
  stale: boolean;
}

export interface StatusReportSnapshot {
  reports: StatusReportState[];
  latest_date: string;
  stale: boolean;
}
```

**Step 2: Add API client calls**

Add to `api` object in `hapax-mgmt-web/src/api/client.ts`:

```typescript
  okrs: () => get<import("./types").OKRSnapshot>("/okrs"),
  smartGoals: () => get<import("./types").SmartGoalSnapshot>("/smart-goals"),
  incidents: () => get<import("./types").IncidentSnapshot>("/incidents"),
  postmortemActions: () => get<import("./types").PostmortemActionSnapshot>("/postmortem-actions"),
  reviewCycles: () => get<import("./types").ReviewCycleSnapshot>("/review-cycles"),
  statusReports: () => get<import("./types").StatusReportSnapshot>("/status-reports"),
```

**Step 3: Add hooks**

Add to `hapax-mgmt-web/src/api/hooks.ts`:

```typescript
export const useOKRs = () =>
  useQuery({ queryKey: ["okrs"], queryFn: api.okrs, refetchInterval: SLOW });

export const useSmartGoals = () =>
  useQuery({ queryKey: ["smartGoals"], queryFn: api.smartGoals, refetchInterval: SLOW });

export const useIncidents = () =>
  useQuery({ queryKey: ["incidents"], queryFn: api.incidents, refetchInterval: SLOW });

export const usePostmortemActions = () =>
  useQuery({ queryKey: ["postmortemActions"], queryFn: api.postmortemActions, refetchInterval: SLOW });

export const useReviewCycles = () =>
  useQuery({ queryKey: ["reviewCycles"], queryFn: api.reviewCycles, refetchInterval: SLOW });

export const useStatusReports = () =>
  useQuery({ queryKey: ["statusReports"], queryFn: api.statusReports, refetchInterval: SLOW });
```

**Step 4: Commit**

```bash
git add hapax-mgmt-web/src/api/types.ts hapax-mgmt-web/src/api/client.ts hapax-mgmt-web/src/api/hooks.ts
git commit -m "feat: add frontend types, hooks, and client calls for 6 new document types"
```

---

### Task 15: Frontend Components — OKRPanel, ReviewCyclePanel, IncidentBanner

**Files:**
- Create: `hapax-mgmt-web/src/components/sidebar/OKRPanel.tsx`
- Create: `hapax-mgmt-web/src/components/sidebar/ReviewCyclePanel.tsx`
- Create: `hapax-mgmt-web/src/components/dashboard/IncidentBanner.tsx`
- Modify: `hapax-mgmt-web/src/components/Sidebar.tsx` (add panels, update sorting/alerting)
- Modify: `hapax-mgmt-web/src/components/MainPanel.tsx` (add IncidentBanner above NudgeList)
- Modify: `hapax-mgmt-web/src/components/dashboard/NudgeList.tsx` (add category badges)

**Step 1: Create OKRPanel**

Create `hapax-mgmt-web/src/components/sidebar/OKRPanel.tsx` following the pattern of `ManagementPanel.tsx`. Use `useOKRs()` hook. Show: objective, quarter, KR count, at-risk count with amber/red badges.

**Step 2: Create ReviewCyclePanel**

Create `hapax-mgmt-web/src/components/sidebar/ReviewCyclePanel.tsx`. Use `useReviewCycles()` hook. Show: person, status, days until due, peer feedback progress bar.

**Step 3: Create IncidentBanner**

Create `hapax-mgmt-web/src/components/dashboard/IncidentBanner.tsx`. Use `useIncidents()` hook. Only render when `snap.open_count > 0`. Red banner with severity badge, title, and "missing postmortem" warning.

**Step 4: Update Sidebar.tsx**

Add imports and panel entries:
```typescript
import { OKRPanel } from "./sidebar/OKRPanel";
import { ReviewCyclePanel } from "./sidebar/ReviewCyclePanel";

const panels: PanelEntry[] = [
  { id: "team", component: ManagementPanel, defaultOrder: 0 },
  { id: "okrs", component: OKRPanel, defaultOrder: 1 },
  { id: "reviews", component: ReviewCyclePanel, defaultOrder: 2 },
  { id: "briefing", component: BriefingPanel, defaultOrder: 3 },
  { id: "goals", component: GoalsPanel, defaultOrder: 4 },
];
```

Add OKR/review data to `needsAttention` memo and `statusDots`.

**Step 5: Update MainPanel.tsx**

Add IncidentBanner above NudgeList:
```typescript
import { IncidentBanner } from "./dashboard/IncidentBanner";
// In JSX:
<IncidentBanner />
<NudgeList />
```

**Step 6: Update NudgeList.tsx**

Add small category badge to each nudge item. Color by category: people=blue, goals=amber, operational=red.

**Step 7: Build frontend**

Run: `cd cockpit-web && pnpm build`
Expected: Build succeeds with no TypeScript errors

**Step 8: Commit**

```bash
git add hapax-mgmt-web/src/components/
git commit -m "feat: add OKRPanel, ReviewCyclePanel, IncidentBanner, and nudge category badges"
```

---

### Task 16: Update Docs

**Files:**
- Modify: `CLAUDE.md` (update agent count, add new data directories to layout)
- Modify: `CLAUDE.md` (update data directory listing, add new document types)
- Modify: `operations-manual.md` (if it references data types or nudge categories)

**Step 1: Update CLAUDE.md files**

Update the data directory listing in both CLAUDE.md files to include:
```
├── okrs/             OKR tracking (quarterly objectives + key results)
├── goals/            SMART goals (individual development goals)
├── incidents/        Incident records
├── postmortem-actions/  Postmortem action items
├── review-cycles/    Performance review process tracking
├── status-reports/   Status reports (weekly/monthly)
```

Update nudge documentation to mention 3 categories (people, goals, operational).

Update reactive engine rule count from 6 to 12.

Update API endpoint count.

**Step 2: Commit**

```bash
git add CLAUDE.md CLAUDE.md operations-manual.md
git commit -m "docs: update CLAUDE.md and operations manual for Tier 1 expansion"
```

---

### Task 17: Final Validation

**Step 1: Run full backend test suite**

Run: `cd ai-agents && uv run pytest tests/ -q`
Expected: All PASS (~1130+ tests)

**Step 2: Build frontend**

Run: `cd cockpit-web && pnpm build`
Expected: Build succeeds

**Step 3: Verify demo data loads through collectors**

Run: `cd ai-agents && uv run python -c "
from unittest.mock import patch
from pathlib import Path
demo = Path('demo-data')
from cockpit.data.nudges import collect_nudges
from cockpit.data.management import collect_management_state
with patch('cockpit.data.management.DATA_DIR', demo), \
     patch('cockpit.data.okrs.DATA_DIR', demo), \
     patch('cockpit.data.smart_goals.DATA_DIR', demo), \
     patch('cockpit.data.incidents.DATA_DIR', demo), \
     patch('cockpit.data.postmortem_actions.DATA_DIR', demo), \
     patch('cockpit.data.review_cycles.DATA_DIR', demo), \
     patch('cockpit.data.status_reports.DATA_DIR', demo):
    snap = collect_management_state()
    nudges = collect_nudges(snapshot=snap)
    for n in nudges:
        print(f'[{n.category:12s}] {n.priority_score} {n.title}')
"`
Expected: 7 nudges across 3 categories (people, goals, operational)

**Step 4: Update memory**

Update `~/.claude/projects/-home-user-projects-hapax-containerization/memory/MEMORY.md` with new document types and nudge categories.
