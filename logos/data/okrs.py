"""OKR state collector — reads from DATA_DIR/okrs/.

Deterministic, no LLM calls. Parses OKR markdown files with nested
key-results in YAML frontmatter. Computes at-risk and stale KR counts.
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

        results.append(
            KeyResultState(
                id=str(item.get("id", "")),
                description=str(item.get("description", "")),
                target=float(item.get("target", 0)),
                current=float(item.get("current", 0)),
                unit=str(item.get("unit", "")),
                direction=str(item.get("direction", "increase")),
                confidence=confidence,
                last_updated=last_updated,
                stale=stale,
            )
        )
    return results


def collect_okr_state() -> OKRSnapshot:
    """Collect OKR state from DATA_DIR/okrs/."""
    okrs_dir = config.data_dir / "okrs"
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
