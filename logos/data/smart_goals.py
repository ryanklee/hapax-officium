"""SMART goal collector — reads from DATA_DIR/goals/.

Deterministic, no LLM calls. Tracks individual development goals
with SMART framework fields, deadline tracking, and review cadence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from shared.config import config
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

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
    goals_dir = config.data_dir / "goals"
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
