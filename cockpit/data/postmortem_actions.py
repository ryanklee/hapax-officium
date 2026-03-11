"""Postmortem action collector — reads from DATA_DIR/postmortem-actions/.

Deterministic, no LLM calls. Tracks action items from incident
postmortems with deadline and completion tracking.
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
    actions_dir = config.data_dir / "postmortem-actions"
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
