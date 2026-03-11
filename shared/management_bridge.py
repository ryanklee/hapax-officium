"""management_bridge.py — Management data source bridge.

Reads from DATA_DIR (people/, coaching/, feedback/, meetings/) and generates
structured ProfileFact-compatible dicts for the management profiler and other
consumers.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from shared.config import PROFILES_DIR, config
from shared.frontmatter import parse_frontmatter as _parse_frontmatter

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("management_bridge")
FACTS_OUTPUT = PROFILES_DIR / "management-structured-facts.json"


# ── Fact construction ────────────────────────────────────────────────────


def _make_fact(text: str, dimension: str, source: str) -> dict:
    """Create a ProfileFact-compatible dict.

    Derives a stable key from the source path and text for deduplication.
    """
    import re as _re

    # Derive a key from source filename + first few words of text
    slug = source.rsplit("/", 1)[-1].replace(".md", "").replace("-", "_")
    words = _re.sub(r"[^a-z0-9 ]", "", text.lower()).split()[:5]
    key = f"{slug}_{'_'.join(words)}"

    return {
        "dimension": dimension,
        "key": key,
        "value": text,
        "confidence": 0.90,
        "source": f"management-bridge:{source}",
        "evidence": text,
    }


# ── Fact generators ──────────────────────────────────────────────────────


def _people_facts() -> list[dict]:
    """Generate facts from people files in DATA_DIR/people/."""
    people_dir = config.data_dir / "people"
    if not people_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(people_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "person":
            continue

        status = str(fm.get("status", "active"))
        if status == "inactive":
            continue

        name = str(fm.get("name", path.stem.replace("-", " ").title()))
        team = str(fm.get("team", "unknown"))
        role = str(fm.get("role", "unknown"))
        cadence = str(fm.get("cadence", ""))

        facts.append(
            _make_fact(
                f"{name} is on {team} team (role: {role})",
                "team_leadership",
                f"people/{path.name}",
            )
        )

        if cadence:
            facts.append(
                _make_fact(
                    f"{cadence} 1:1 cadence with {name}",
                    "management_practice",
                    f"people/{path.name}",
                )
            )

    return facts


def _coaching_facts() -> list[dict]:
    """Generate facts from coaching files in DATA_DIR/coaching/."""
    coaching_dir = config.data_dir / "coaching"
    if not coaching_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(coaching_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "coaching":
            continue

        person = str(fm.get("person", "unknown"))
        title = str(fm.get("title", path.stem.replace("-", " ").title()))
        status = str(fm.get("status", "active"))

        facts.append(
            _make_fact(
                f"Coaching hypothesis for {person}: {title} (status: {status})",
                "management_practice",
                f"coaching/{path.name}",
            )
        )

    return facts


def _feedback_facts() -> list[dict]:
    """Generate facts from feedback files in DATA_DIR/feedback/."""
    feedback_dir = config.data_dir / "feedback"
    if not feedback_dir.is_dir():
        return []

    facts: list[dict] = []
    for path in sorted(feedback_dir.glob("*.md")):
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "feedback":
            continue

        person = str(fm.get("person", "unknown"))
        direction = str(fm.get("direction", "given"))
        category = str(fm.get("category", "growth"))

        facts.append(
            _make_fact(
                f"Feedback record ({direction}) for {person}: {category}",
                "management_practice",
                f"feedback/{path.name}",
            )
        )

    return facts


def _meeting_facts() -> list[dict]:
    """Generate facts from the last 20 meeting files in DATA_DIR/meetings/."""
    meetings_dir = config.data_dir / "meetings"
    if not meetings_dir.is_dir():
        return []

    # Sort by filename descending (dates in filenames), take last 20
    paths = sorted(meetings_dir.glob("*.md"), reverse=True)[:20]

    facts: list[dict] = []
    for path in paths:
        fm, _body = _parse_frontmatter(path)
        if not fm or fm.get("type") != "meeting":
            continue

        title = str(fm.get("title", path.stem.replace("-", " ").title()))
        meeting_date = str(fm.get("date", "unknown"))

        facts.append(
            _make_fact(
                f"Meeting: {title} ({meeting_date})",
                "attention_distribution",
                f"meetings/{path.name}",
            )
        )

    return facts


def _okr_facts() -> list[dict]:
    """Generate facts from OKR files in DATA_DIR/okrs/."""
    okrs_dir = config.data_dir / "okrs"
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
        on_track = sum(
            1
            for kr in (krs if isinstance(krs, list) else [])
            if isinstance(kr, dict) and (kr.get("confidence") or 0) >= 0.5
        )

        scope_label = f"{scope} ({team})" if team else scope
        facts.append(
            _make_fact(
                f"OKR ({scope_label}, {quarter}): {objective} — {on_track}/{kr_count} KRs on track",
                "strategic_alignment",
                f"okrs/{path.name}",
            )
        )

    return facts


def _smart_goal_facts() -> list[dict]:
    """Generate facts from SMART goal files in DATA_DIR/goals/."""
    goals_dir = config.data_dir / "goals"
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

        facts.append(
            _make_fact(
                f"SMART goal for {person}: {specific} ({category}, due {target_date})",
                "management_practice",
                f"goals/{path.name}",
            )
        )

    return facts


def _incident_facts() -> list[dict]:
    """Generate facts from incident files in DATA_DIR/incidents/."""
    incidents_dir = config.data_dir / "incidents"
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

        facts.append(
            _make_fact(
                f"{severity.upper()} incident: {title} ({dur_str}, {status})",
                "attention_distribution",
                f"incidents/{path.name}",
            )
        )

    return facts


def _postmortem_action_facts() -> list[dict]:
    """Generate facts from postmortem action files in DATA_DIR/postmortem-actions/."""
    actions_dir = config.data_dir / "postmortem-actions"
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

        facts.append(
            _make_fact(
                f"Postmortem action ({status}): {title} — owner: {owner}",
                "management_practice",
                f"postmortem-actions/{path.name}",
            )
        )

    return facts


def _review_cycle_facts() -> list[dict]:
    """Generate facts from review cycle files in DATA_DIR/review-cycles/."""
    cycles_dir = config.data_dir / "review-cycles"
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

        facts.append(
            _make_fact(
                f"Review cycle {cycle} for {person}: {status} (due {review_due})",
                "management_practice",
                f"review-cycles/{path.name}",
            )
        )

    return facts


# ── Public API ───────────────────────────────────────────────────────────


def generate_facts(vault_path: Path | None = None) -> list[dict]:
    """Generate ProfileFact dicts from management data in DATA_DIR.

    Args:
        vault_path: Ignored (kept for API compatibility).

    Returns:
        List of fact dicts with text, dimension, source, timestamp fields.
        Returns [] if no data found.
    """
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


def save_facts(facts: list[dict]) -> Path:
    """Save generated facts to the profiles directory."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    FACTS_OUTPUT.write_text(
        json.dumps(facts, indent=2, default=str),
        encoding="utf-8",
    )
    log.info("Saved %d management facts to %s", len(facts), FACTS_OUTPUT.name)
    return FACTS_OUTPUT
