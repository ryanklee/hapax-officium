"""status_update.py — Upward-facing status report generator.

Generates weekly (or daily) status reports in the Lara Hogan "Week in Review"
pattern. Consumes the week's meetings, coaching activity, and feedback from
DATA_DIR to produce: headline, themes from 1:1s, risks/blockers, wins, asks.

Zero LLM calls for data collection; one LLM call for synthesis.

Usage:
    uv run python -m agents.status_update              # Weekly (7-day lookback)
    uv run python -m agents.status_update --daily      # Daily (1-day lookback)
    uv run python -m agents.status_update --save       # Save to DATA_DIR/references/
    uv run python -m agents.status_update --json       # Machine-readable JSON
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import config, get_model

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger(__name__)

# ── Frontmatter parsing (same pattern as management_bridge.py) ───────────

_FM_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?(.*)", re.DOTALL)


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter from a markdown file.

    Returns (frontmatter_dict, body_text). On any error returns ({}, "").
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("status_update: cannot read %s: %s", path, exc)
        return {}, ""

    match = _FM_RE.match(text)
    if not match:
        return {}, text

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        log.warning("status_update: bad YAML in %s: %s", path, exc)
        return {}, match.group(2)

    if not isinstance(fm, dict):
        return {}, match.group(2)

    return fm, match.group(2)


# ── Schemas ──────────────────────────────────────────────────────────────


class StatusReport(BaseModel):
    """Upward-facing status report (Lara Hogan Week in Review pattern)."""

    headline: str = Field(description="One-sentence summary of the week/period")
    themes: list[str] = Field(
        default_factory=list,
        description="Key themes from 1:1s and meetings",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="Risks and blockers to surface upward",
    )
    wins: list[str] = Field(
        default_factory=list,
        description="Wins and accomplishments worth highlighting",
    )
    asks: list[str] = Field(
        default_factory=list,
        description="Asks for leadership / things you need help with",
    )


# ── Data gathering ───────────────────────────────────────────────────────


def _file_date(fm: dict, path: Path) -> datetime | None:
    """Extract date from frontmatter or filename. Returns UTC datetime or None."""
    # Try frontmatter date field
    date_val = fm.get("date")
    if date_val:
        if isinstance(date_val, datetime):
            if date_val.tzinfo is None:
                return date_val.replace(tzinfo=UTC)
            return date_val
        try:
            return datetime.strptime(str(date_val), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pass

    # Try ISO format in frontmatter
    for key in ("created", "created_at", "timestamp"):
        val = fm.get(key)
        if val:
            try:
                dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except (ValueError, TypeError):
                pass

    # Try date from filename (YYYY-MM-DD prefix)
    date_match = re.match(r"(\d{4}-\d{2}-\d{2})", path.stem)
    if date_match:
        try:
            return datetime.strptime(date_match.group(1), "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            pass

    return None


def _body_excerpt(body: str, max_chars: int = 500) -> str:
    """Return the first max_chars characters of body text, stripped."""
    text = body.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _gather_week_context(days: int = 7) -> dict[str, list[dict]]:
    """Scan DATA_DIR for recent files within date range.

    Returns dict with keys: meetings, coaching, feedback — each a list of
    dicts with 'filename', 'frontmatter', 'excerpt' fields.
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    context: dict[str, list[dict]] = {
        "meetings": [],
        "coaching": [],
        "feedback": [],
    }

    subdirs = {
        "meetings": config.data_dir / "meetings",
        "coaching": config.data_dir / "coaching",
        "feedback": config.data_dir / "feedback",
    }

    for category, dirpath in subdirs.items():
        if not dirpath.is_dir():
            continue

        for path in sorted(dirpath.glob("*.md")):
            fm, body = _parse_frontmatter(path)
            file_dt = _file_date(fm, path)

            # Include file if date is within range, or if no date could be
            # determined (better to include than miss)
            if file_dt is not None and file_dt < cutoff:
                continue

            context[category].append(
                {
                    "filename": path.name,
                    "frontmatter": fm,
                    "excerpt": _body_excerpt(body),
                }
            )

    return context


# ── LLM synthesis ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are generating an upward-facing status report for an engineering manager.
This follows the Lara Hogan "Week in Review" pattern: headline, themes, risks,
wins, and asks.

CRITICAL SAFETY RULES:
- Never generate feedback language about individual team members.
- Never suggest what to say to anyone.
- Never generate coaching recommendations or performance evaluations.
- Focus on themes and patterns, NOT play-by-play of individual conversations.

GUIDELINES:
- Headline: one sentence capturing the overall period (e.g., "Team alignment \
improving; two open headcount risks need escalation")
- Themes: synthesize patterns from 1:1s and meetings into 3-5 themes. \
Abstract away from individuals.
- Risks: concrete blockers or risks that leadership should know about
- Wins: accomplishments, milestones, or positive signals worth highlighting
- Asks: specific things the manager needs from their leadership
- If data is sparse, say so honestly — don't fabricate content
- Write concisely. Each item should be 1-2 sentences max.
"""

_agent = Agent(
    get_model("balanced"),
    system_prompt=SYSTEM_PROMPT,
    output_type=StatusReport,
)


def _format_context_for_prompt(context: dict[str, list[dict]], days: int) -> str:
    """Format gathered context into a structured prompt."""
    lines: list[str] = []
    period = "day" if days == 1 else f"{days} days"
    lines.append(f"Generate a status report covering the last {period}.")
    lines.append("")

    for category, items in context.items():
        if not items:
            lines.append(f"## {category.title()}\nNo {category} data found.\n")
            continue

        lines.append(f"## {category.title()} ({len(items)} files)")
        for item in items:
            fm = item["frontmatter"]
            title = fm.get("title", item["filename"])
            date = fm.get("date", "unknown date")
            lines.append(f"### {title} ({date})")
            if item["excerpt"]:
                lines.append(item["excerpt"])
            lines.append("")

    total = sum(len(v) for v in context.values())
    if total == 0:
        lines.append(
            "No data files found for this period. Generate a minimal report noting the data gap."
        )

    return "\n".join(lines)


async def generate_status(days: int = 7, save: bool = False) -> StatusReport:
    """Gather context and generate a status report via LLM.

    Args:
        days: Number of days to look back (7 for weekly, 1 for daily).
        save: If True, save the report to DATA_DIR/references/.

    Returns:
        StatusReport with headline, themes, risks, wins, asks.
    """
    context = _gather_week_context(days)
    prompt = _format_context_for_prompt(context, days)

    try:
        result = await _agent.run(prompt)
        report = result.output
    except Exception as e:
        log.error("LLM synthesis failed: %s", e)
        report = StatusReport(
            headline="Status report unavailable -- LLM error",
            themes=[],
            risks=[str(e)],
            wins=[],
            asks=[],
        )

    if save:
        _save_report(report, days)

    return report


def _save_report(report: StatusReport, days: int) -> Path:
    """Save report as markdown to DATA_DIR/references/."""
    refs_dir = config.data_dir / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    period = "daily" if days == 1 else "weekly"
    filename = f"status-{period}-{today}.md"
    path = refs_dir / filename

    lines = [
        "---",
        "type: status-report",
        f"period: {period}",
        f"date: {today}",
        f"days: {days}",
        "---",
        "",
        f"# {report.headline}",
        "",
    ]

    if report.themes:
        lines.append("## Themes")
        for t in report.themes:
            lines.append(f"- {t}")
        lines.append("")

    if report.risks:
        lines.append("## Risks & Blockers")
        for r in report.risks:
            lines.append(f"- {r}")
        lines.append("")

    if report.wins:
        lines.append("## Wins")
        for w in report.wins:
            lines.append(f"- {w}")
        lines.append("")

    if report.asks:
        lines.append("## Asks")
        for a in report.asks:
            lines.append(f"- {a}")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Saved status report to %s", path)
    return path


# ── Formatters ───────────────────────────────────────────────────────────


def format_human(report: StatusReport) -> str:
    """Format report for terminal display."""
    lines = [report.headline, ""]

    if report.themes:
        lines.append("Themes:")
        for t in report.themes:
            lines.append(f"  - {t}")
        lines.append("")

    if report.risks:
        lines.append("Risks & Blockers:")
        for r in report.risks:
            lines.append(f"  - {r}")
        lines.append("")

    if report.wins:
        lines.append("Wins:")
        for w in report.wins:
            lines.append(f"  - {w}")
        lines.append("")

    if report.asks:
        lines.append("Asks:")
        for a in report.asks:
            lines.append(f"  - {a}")
        lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upward-facing status report generator",
        prog="python -m agents.status_update",
    )
    parser.add_argument(
        "--daily",
        action="store_true",
        help="Daily report (1-day lookback instead of 7)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to DATA_DIR/references/",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Machine-readable JSON output",
    )
    args = parser.parse_args()

    days = 1 if args.daily else 7

    print(f"Gathering context ({days}d lookback)...", file=sys.stderr)
    report = await generate_status(days=days, save=args.save)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(format_human(report))


if __name__ == "__main__":
    asyncio.run(main())
