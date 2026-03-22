"""Incident state collector — reads from DATA_DIR/incidents/.

Deterministic, no LLM calls. Tracks incident status, severity,
and whether a postmortem has been completed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from shared.config import config
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

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
    incidents_dir = config.data_dir / "incidents"
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
