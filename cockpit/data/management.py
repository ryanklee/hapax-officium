"""Management state collector — reads from DATA_DIR.

Scans DATA_DIR subdirectories (people/, coaching/, feedback/) for markdown
files with YAML frontmatter. Computes staleness, overdue status, and
aggregates into a ManagementSnapshot for the cockpit API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from shared.config import config
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)

# ── Cadence thresholds (days before a 1:1 is considered stale) ────────────

_CADENCE_THRESHOLDS: dict[str, int] = {
    "weekly": 10,
    "biweekly": 17,
    "monthly": 35,
}
_DEFAULT_THRESHOLD: int = 14

# ── Cognitive load string→numeric mapping ────────────────────────────────

_LOAD_MAP: dict[str, int] = {
    "low": 1,
    "moderate": 2,
    "medium": 3,
    "high": 4,
    "critical": 5,
}

# ── Dataclasses (API contracts — do not change field names/types) ────────


@dataclass
class PersonState:
    """State of a single team member."""

    name: str
    team: str = ""
    role: str = ""
    cadence: str = ""
    status: str = "active"
    cognitive_load: int | None = None
    growth_vector: str = ""
    feedback_style: str = ""
    last_1on1: str = ""
    coaching_active: bool = False
    stale_1on1: bool = False
    days_since_1on1: int | None = None
    file_path: Path | None = None
    career_goal_3y: str = ""
    current_gaps: str = ""
    current_focus: str = ""
    last_career_convo: str = ""
    team_type: str = ""
    interaction_mode: str = ""
    skill_level: str = ""
    will_signal: str = ""
    domains: list[str] = field(default_factory=lambda: ["management"])
    relationship: str = ""


@dataclass
class CoachingState:
    """State of a coaching hypothesis."""

    title: str
    person: str = ""
    status: str = "active"
    check_in_by: str = ""
    overdue: bool = False
    days_overdue: int = 0
    file_path: Path | None = None


@dataclass
class FeedbackState:
    """State of a feedback record."""

    title: str
    person: str = ""
    direction: str = "given"
    category: str = "growth"
    follow_up_by: str = ""
    followed_up: bool = False
    overdue: bool = False
    days_overdue: int = 0
    file_path: Path | None = None


@dataclass
class ManagementSnapshot:
    """Aggregated management state."""

    people: list[PersonState] = field(default_factory=list)
    coaching: list[CoachingState] = field(default_factory=list)
    feedback: list[FeedbackState] = field(default_factory=list)
    stale_1on1_count: int = 0
    overdue_coaching_count: int = 0
    overdue_feedback_count: int = 0
    high_load_count: int = 0
    active_people_count: int = 0


# ── Helpers ──────────────────────────────────────────────────────────────


def _date_str(value: str | date | datetime | None) -> str:
    """Normalise a date value to ISO string."""
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _days_since(date_str: str) -> int | None:
    """Return days between date_str (ISO format) and today, or None."""
    if not date_str:
        return None
    try:
        d = date.fromisoformat(str(date_str))
        return (date.today() - d).days
    except (ValueError, TypeError):
        return None


# ── Collectors ───────────────────────────────────────────────────────────


def _collect_people() -> list[PersonState]:
    """Scan DATA_DIR/people for person markdown files."""
    people_dir = config.data_dir / "people"
    if not people_dir.is_dir():
        _log.debug("management: no people dir at %s", people_dir)
        return []

    people: list[PersonState] = []
    for path in sorted(people_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "person":
            continue

        status = str(fm.get("status", "active"))
        if status == "inactive":
            continue

        last_1on1_raw = _date_str(fm.get("last-1on1"))
        cadence = str(fm.get("cadence", ""))
        days = _days_since(last_1on1_raw)

        # Staleness check
        threshold = _CADENCE_THRESHOLDS.get(cadence, _DEFAULT_THRESHOLD)
        stale = days is not None and days > threshold

        # Domains — ensure list
        domains_raw = fm.get("domains")
        if isinstance(domains_raw, list):
            domains = [str(d) for d in domains_raw]
        elif isinstance(domains_raw, str):
            domains = [domains_raw]
        else:
            domains = ["management"]

        person = PersonState(
            name=str(fm.get("name", path.stem.replace("-", " ").title())),
            team=str(fm.get("team", "")),
            role=str(fm.get("role", "")),
            cadence=cadence,
            status=status,
            cognitive_load=_LOAD_MAP.get(str(fm.get("cognitive-load", "")).lower()),
            growth_vector=str(fm.get("growth-vector", "")),
            feedback_style=str(fm.get("feedback-style", "")),
            last_1on1=last_1on1_raw,
            coaching_active=bool(fm.get("coaching-active", False)),
            stale_1on1=stale,
            days_since_1on1=days,
            file_path=path,
            career_goal_3y=str(fm.get("career-goal-3y", "")),
            current_gaps=str(fm.get("current-gaps", "")),
            current_focus=str(fm.get("current-focus", "")),
            last_career_convo=_date_str(fm.get("last-career-convo")),
            team_type=str(fm.get("team-type", "")),
            interaction_mode=str(fm.get("interaction-mode", "")),
            skill_level=str(fm.get("skill-level", "")),
            will_signal=str(fm.get("will-signal", "")),
            domains=domains,
            relationship=str(fm.get("relationship", "")),
        )
        people.append(person)

    return people


def _collect_coaching() -> list[CoachingState]:
    """Scan DATA_DIR/coaching for coaching markdown files."""
    coaching_dir = config.data_dir / "coaching"
    if not coaching_dir.is_dir():
        _log.debug("management: no coaching dir at %s", coaching_dir)
        return []

    items: list[CoachingState] = []
    for path in sorted(coaching_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "coaching":
            continue

        check_in_by_raw = _date_str(fm.get("check-in-by"))
        days = _days_since(check_in_by_raw)
        overdue = days is not None and days > 0

        item = CoachingState(
            title=str(fm.get("title", path.stem.replace("-", " ").title())),
            person=str(fm.get("person", "")),
            status=str(fm.get("status", "active")),
            check_in_by=check_in_by_raw,
            overdue=overdue,
            days_overdue=max(days, 0) if days is not None else 0,
            file_path=path,
        )
        items.append(item)

    return items


def _collect_feedback() -> list[FeedbackState]:
    """Scan DATA_DIR/feedback for feedback markdown files."""
    feedback_dir = config.data_dir / "feedback"
    if not feedback_dir.is_dir():
        _log.debug("management: no feedback dir at %s", feedback_dir)
        return []

    items: list[FeedbackState] = []
    for path in sorted(feedback_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "feedback":
            continue

        followed_up = bool(fm.get("followed-up", False))
        follow_up_by_raw = _date_str(fm.get("follow-up-by"))

        overdue = False
        days_overdue = 0
        if not followed_up and follow_up_by_raw:
            days = _days_since(follow_up_by_raw)
            if days is not None and days > 0:
                overdue = True
                days_overdue = days

        item = FeedbackState(
            title=str(fm.get("title", path.stem.replace("-", " ").title())),
            person=str(fm.get("person", "")),
            direction=str(fm.get("direction", "given")),
            category=str(fm.get("category", "growth")),
            follow_up_by=follow_up_by_raw,
            followed_up=followed_up,
            overdue=overdue,
            days_overdue=days_overdue,
            file_path=path,
        )
        items.append(item)

    return items


# ── Main entry point ─────────────────────────────────────────────────────


def collect_management_state() -> ManagementSnapshot:
    """Collect management state from DATA_DIR.

    Scans people/, coaching/, and feedback/ subdirectories for markdown
    files with YAML frontmatter. Returns aggregated ManagementSnapshot.
    """
    people = _collect_people()
    coaching = _collect_coaching()
    feedback = _collect_feedback()

    active_people = [p for p in people if p.status == "active"]

    return ManagementSnapshot(
        people=people,
        coaching=coaching,
        feedback=feedback,
        stale_1on1_count=sum(1 for p in active_people if p.stale_1on1),
        overdue_coaching_count=sum(1 for c in coaching if c.overdue),
        overdue_feedback_count=sum(1 for f in feedback if f.overdue),
        high_load_count=sum(
            1 for p in active_people if p.cognitive_load is not None and p.cognitive_load >= 4
        ),
        active_people_count=len(active_people),
    )
