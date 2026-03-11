"""Render SimulatedEvent objects into markdown files with YAML frontmatter.

Coaching and feedback events use structural templates (date, participant,
topics, action items) — never evaluative or prescriptive language.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import yaml

from agents.simulator_pipeline.models import ContentPolicy, SimulatedEvent

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)


def render_event(event: SimulatedEvent, data_dir: Path) -> Path:
    """Render a single event to a markdown file in data_dir.

    Returns the path to the written file.
    """
    target_dir = data_dir / event.subdirectory
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / event.filename

    frontmatter = yaml.dump(event.metadata, default_flow_style=False).strip()
    body = _render_body(event)

    content = f"---\n{frontmatter}\n---\n{body}\n"
    target.write_text(content, encoding="utf-8")

    _log.debug("Rendered %s -> %s", event.workflow_type, target)
    return target


def render_events(events: list[SimulatedEvent], data_dir: Path) -> list[Path]:
    """Render multiple events. Returns list of written file paths."""
    return [render_event(event, data_dir) for event in events]


def _render_body(event: SimulatedEvent) -> str:
    """Generate body content for an event.

    Restricted types (coaching, feedback) get structural-only templates.
    Unrestricted types use body_template if provided, else structural fallback.
    """
    if ContentPolicy.is_restricted(event.workflow_type):
        return _structural_body(event)

    if event.body_template:
        return _expand_template(event)

    return _structural_body(event)


def _structural_body(event: SimulatedEvent) -> str:
    """Generate a structural body from event fields — no evaluative content."""
    lines = []

    if event.participant:
        lines.append(f"Participant: {event.participant}")
    if event.topics:
        lines.append("")
        lines.append("## Topics")
        lines.append("")
        for topic in event.topics:
            lines.append(f"- {topic}")

    return "\n".join(lines)


def _expand_template(event: SimulatedEvent) -> str:
    """Expand body_template with event fields."""
    topics_list = "\n".join(f"- {t}" for t in event.topics)
    template = event.body_template or ""
    return template.replace("{topics_list}", topics_list).replace(
        "{topics}", ", ".join(event.topics)
    )
