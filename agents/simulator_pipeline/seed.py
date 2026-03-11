"""Seed date rebasing for simulation setup.

Scans seed corpus files for ISO date strings in frontmatter and shifts
them by a calculated offset so the seed represents 'existing history'
at the simulation start_date.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)

# ISO date pattern (YYYY-MM-DD)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def find_latest_date(data_dir: Path) -> date | None:
    """Scan all .md files in data_dir for the latest ISO date in frontmatter."""
    latest: date | None = None

    for md_file in data_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        # Only scan frontmatter (between --- markers)
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        frontmatter = parts[1]

        for match in _DATE_RE.finditer(frontmatter):
            try:
                d = date.fromisoformat(match.group(1))
                if latest is None or d > latest:
                    latest = d
            except ValueError:
                continue

    return latest


def rebase_seed_dates(data_dir: Path, sim_start: date) -> None:
    """Rebase all dates in seed corpus files relative to sim_start.

    Finds the latest date in the corpus, calculates the offset to make
    that date fall just before sim_start, then shifts all dates by that offset.
    """
    latest = find_latest_date(data_dir)
    if latest is None:
        _log.info("No dates found in seed corpus, skipping rebase")
        return

    offset = (sim_start - latest) - timedelta(days=1)
    if offset.days == 0:
        _log.info("Seed dates already aligned with sim_start")
        return

    _log.info(
        "Rebasing seed dates by %d days (latest=%s, sim_start=%s)", offset.days, latest, sim_start
    )

    for md_file in data_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8")
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue

        frontmatter = parts[1]
        new_frontmatter = _DATE_RE.sub(lambda m: _shift_date(m.group(1), offset), frontmatter)

        if new_frontmatter != frontmatter:
            md_file.write_text(
                f"---{new_frontmatter}---{parts[2]}",
                encoding="utf-8",
            )


def _shift_date(date_str: str, offset: timedelta) -> str:
    """Shift a single ISO date string by offset."""
    try:
        d = date.fromisoformat(date_str)
        return (d + offset).isoformat()
    except ValueError:
        return date_str
