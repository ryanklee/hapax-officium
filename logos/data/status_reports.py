"""Status report collector — reads from DATA_DIR/status-reports/.

Deterministic, no LLM calls. Tracks status report recency and
staleness based on cadence (weekly > 9 days, monthly > 35 days).
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
    reports_dir = config.data_dir / "status-reports"
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
