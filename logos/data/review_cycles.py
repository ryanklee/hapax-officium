"""Review cycle collector — reads from DATA_DIR/review-cycles/.

Deterministic, no LLM calls. Tracks performance review process
state: deadlines, self-assessments, peer feedback progress.
Does NOT track review content (management safety axiom).
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
    cycles_dir = config.data_dir / "review-cycles"
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
