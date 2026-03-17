"""shared/vault_writer.py — Write management data to DATA_DIR as markdown with YAML frontmatter."""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import TYPE_CHECKING

import yaml

from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9_-]")


def _write_md(
    path: Path,
    content: str,
    frontmatter: dict | None = None,
) -> Path:
    """Write a markdown file with optional YAML frontmatter. Creates parent dirs.

    Validates that the resolved path stays under DATA_DIR to prevent path traversal.
    """
    resolved = path.resolve()
    data_root = config.data_dir.resolve()
    if not resolved.is_relative_to(data_root):
        raise ValueError(f"Path escapes DATA_DIR: {resolved}")

    resolved.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    if frontmatter:
        parts.append("---")
        parts.append(yaml.dump(frontmatter, default_flow_style=False).rstrip())
        parts.append("---")
        parts.append("")
    parts.append(content)
    resolved.write_text("\n".join(parts))
    return resolved


def _today() -> str:
    return date.today().isoformat()


def _person_slug(name: str) -> str:
    """Sanitise a person name into a filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"Empty slug from person name: {name!r}")
    return slug


def _decision_slug(text: str) -> str:
    """Sanitise decision text into a filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", text[:40].lower()).strip("-")
    if not slug:
        raise ValueError(f"Empty slug from decision text: {text!r}")
    return slug


def write_to_vault(
    folder: str,
    filename: str,
    content: str,
    frontmatter: dict | None = None,
) -> Path | None:
    try:
        return _write_md(config.data_dir / folder / filename, content, frontmatter)
    except Exception:
        _log.exception("Failed to write %s/%s", folder, filename)
        return None


def write_briefing_to_vault(briefing_md: str) -> Path | None:
    try:
        path = config.data_dir / "references" / f"briefing-{_today()}.md"
        return _write_md(path, briefing_md, {"type": "briefing", "date": _today()})
    except Exception:
        _log.exception("Failed to write briefing")
        return None


def write_digest_to_vault(digest_md: str) -> Path | None:
    try:
        path = config.data_dir / "references" / f"digest-{_today()}.md"
        return _write_md(path, digest_md, {"type": "digest", "date": _today()})
    except Exception:
        _log.exception("Failed to write digest")
        return None


def write_nudges_to_vault(nudges: list[dict]) -> Path | None:
    try:
        path = config.data_dir / "references" / "nudges.md"
        lines: list[str] = []
        for n in nudges:
            label = n.get("label", n.get("text", str(n)))
            lines.append(f"- [ ] {label}")
        return _write_md(path, "\n".join(lines), {"type": "nudges", "date": _today()})
    except Exception:
        _log.exception("Failed to write nudges")
        return None


def write_goals_to_vault(goals: list[dict]) -> Path | None:
    try:
        path = config.data_dir / "references" / "goals.md"
        lines: list[str] = []
        for g in goals:
            label = g.get("label", g.get("text", str(g)))
            lines.append(f"- {label}")
        return _write_md(path, "\n".join(lines), {"type": "goals", "date": _today()})
    except Exception:
        _log.exception("Failed to write goals")
        return None


def write_1on1_prep_to_vault(person_name: str, prep_md: str) -> Path | None:
    try:
        slug = _person_slug(person_name)
        path = config.data_dir / "1on1-prep" / f"prep-{slug}-{_today()}.md"
        fm = {"type": "prep", "person": person_name, "date": _today()}
        return _write_md(path, prep_md, fm)
    except Exception:
        _log.exception("Failed to write 1:1 prep for %s", person_name)
        return None


def write_team_snapshot_to_vault(snapshot_md: str) -> Path | None:
    try:
        path = config.data_dir / "references" / f"team-snapshot-{_today()}.md"
        return _write_md(path, snapshot_md, {"type": "team-snapshot", "date": _today()})
    except Exception:
        _log.exception("Failed to write team snapshot")
        return None


def write_management_overview_to_vault(overview_md: str) -> Path | None:
    try:
        path = config.data_dir / "references" / f"overview-{_today()}.md"
        return _write_md(path, overview_md, {"type": "overview", "date": _today()})
    except Exception:
        _log.exception("Failed to write management overview")
        return None


def create_coaching_starter(person: str, observation: str) -> Path | None:
    try:
        slug = _person_slug(person)
        path = config.data_dir / "coaching" / f"{slug}-{_today()}.md"
        fm = {"type": "coaching", "person": person, "date": _today()}
        return _write_md(path, observation, fm)
    except Exception:
        _log.exception("Failed to create coaching starter for %s", person)
        return None


def create_fb_record_starter(person: str, fb_moment) -> Path | None:
    try:
        slug = _person_slug(person)
        path = config.data_dir / "feedback" / f"{slug}-{_today()}.md"
        fm = {"type": "feedback", "person": person, "date": _today()}
        content = str(fb_moment)
        return _write_md(path, content, fm)
    except Exception:
        _log.exception("Failed to create feedback record for %s", person)
        return None


def create_decision_starter(decision_text: str, meeting_ref: str) -> Path | None:
    try:
        slug = _decision_slug(decision_text)
        path = config.data_dir / "decisions" / f"{slug}-{_today()}.md"
        fm: dict = {"type": "decision", "date": _today()}
        if meeting_ref:
            fm["meeting_ref"] = meeting_ref
        return _write_md(path, decision_text, fm)
    except Exception:
        _log.exception("Failed to create decision starter")
        return None


def write_bridge_prompt_to_vault(prompt_name: str, prompt_md: str) -> Path | None:
    try:
        path = config.data_dir / "references" / f"prompt-{prompt_name}.md"
        return _write_md(path, prompt_md, {"type": "prompt", "name": prompt_name})
    except Exception:
        _log.exception("Failed to write bridge prompt %s", prompt_name)
        return None
