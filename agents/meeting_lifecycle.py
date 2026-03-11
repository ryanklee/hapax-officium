"""meeting_lifecycle.py — Meeting lifecycle automation agent.

Automates meeting preparation, post-meeting processing, transcript ingestion,
and weekly review pre-population.

Modes:
    --prepare       Auto-generate 1:1 prep for meetings coming due
    --process FILE  Extract structured data from a meeting note
    --transcript FILE  Ingest a transcript file into a meeting note
    --weekly-review Pre-populate weekly review from vault data

Zero LLM calls for data collection; LLM calls only for synthesis/extraction.

Guiding principle: "LLM Prepares, Human Delivers."

Usage:
    uv run python -m agents.meeting_lifecycle --prepare
    uv run python -m agents.meeting_lifecycle --prepare --dry-run
    uv run python -m agents.meeting_lifecycle --process 10-work/meetings/2026-03-03-alice-1on1.md
    uv run python -m agents.meeting_lifecycle --transcript 10-work/meetings/standup.vtt
    uv run python -m agents.meeting_lifecycle --weekly-review
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import get_model
from shared.operator import get_system_prompt_fragment

# Import Langfuse OTel config (side-effect: configures exporter)
try:
    from shared import langfuse_config  # noqa: F401
except ImportError:
    pass

from agents.management_prep import (
    PrepDocument,
    format_prep_md,
    generate_1on1_prep,
)
from cockpit.data.management import (
    collect_management_state,
)
from shared.vault_utils import parse_frontmatter as _parse_frontmatter
from shared.vault_writer import write_1on1_prep_to_vault, write_to_vault

log = logging.getLogger("meeting_lifecycle")

# ── Prep thresholds ────────────────────────────────────────────────────────

_PREP_THRESHOLDS = {
    "weekly": 5,
    "biweekly": 12,
    "monthly": 30,
}


# ── Schemas ────────────────────────────────────────────────────────────────


class MeetingDue(BaseModel):
    """A meeting that needs preparation."""

    person_name: str
    cadence: str
    days_since_1on1: int | None
    prep_threshold: int


class PrepResult(BaseModel):
    """Result of preparing for one meeting."""

    person_name: str
    prep: PrepDocument
    saved_path: str = ""


class PrepSummary(BaseModel):
    """Summary of all prep generated in one run."""

    meetings_due: int = 0
    preps_generated: int = 0
    preps_failed: int = 0
    results: list[PrepResult] = Field(default_factory=list)


class ActionItemExtracted(BaseModel):
    """An action item extracted from meeting notes."""

    text: str
    assignee: str = ""
    due_date: str = ""


class FeedbackMoment(BaseModel):
    """A feedback moment noted in meeting notes."""

    description: str
    direction: str = "given"  # given | received
    category: str = ""  # growth | recognition | correction


class MeetingExtraction(BaseModel):
    """LLM-extracted structured data from a meeting note."""

    action_items: list[ActionItemExtracted] = Field(default_factory=list)
    coaching_observations: list[str] = Field(default_factory=list)
    feedback_moments: list[FeedbackMoment] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    key_themes: list[str] = Field(default_factory=list)
    summary: str = ""


class WeeklyReviewData(BaseModel):
    """Pre-populated data for weekly review."""

    cognitive_load_table: list[dict] = Field(default_factory=list)
    key_outcomes: list[str] = Field(default_factory=list)
    wins: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    topology_signals: list[str] = Field(default_factory=list)
    recurring_themes: list[str] = Field(default_factory=list)
    meetings_this_week: int = 0
    coaching_activity: list[str] = Field(default_factory=list)
    feedback_activity: list[str] = Field(default_factory=list)


# ── Extraction agent ──────────────────────────────────────────────────────

EXTRACT_SYSTEM_PROMPT = """\
You are a meeting note processor. Extract structured data from meeting notes.

CRITICAL BOUNDARIES:
- Extract what IS in the notes, do not infer or add
- Action items: exact text, assignee if mentioned, due date if mentioned
- Coaching observations: direct observations noted by the operator only
- Feedback: only if explicitly noted as delivered
- Do NOT generate coaching hypotheses or feedback suggestions
- Do NOT suggest what the operator should say or do
"""

extract_agent = Agent(
    get_model("fast"),
    system_prompt=get_system_prompt_fragment("meeting-lifecycle") + "\n\n" + EXTRACT_SYSTEM_PROMPT,
    output_type=MeetingExtraction,
)


# ── Prepare mode ──────────────────────────────────────────────────────────


def discover_due_meetings(person_filter: str | None = None) -> list[MeetingDue]:
    """Find people whose 1:1 is coming due based on cadence thresholds.

    A meeting is "due" when days_since_1on1 >= prep_threshold.
    """
    snapshot = collect_management_state()

    due: list[MeetingDue] = []
    for person in snapshot.people:
        if person_filter and person.name.lower() != person_filter.lower():
            continue

        threshold = _PREP_THRESHOLDS.get(person.cadence)
        if threshold is None:
            continue

        if person.days_since_1on1 is None:
            continue

        if person.days_since_1on1 < threshold:
            continue

        due.append(
            MeetingDue(
                person_name=person.name,
                cadence=person.cadence,
                days_since_1on1=person.days_since_1on1,
                prep_threshold=threshold,
            )
        )

    return due


async def prepare_all(
    person_filter: str | None = None,
    dry_run: bool = False,
    save: bool = True,
) -> PrepSummary:
    """Generate 1:1 prep for all meetings coming due."""
    meetings = discover_due_meetings(person_filter)
    summary = PrepSummary(meetings_due=len(meetings))

    if dry_run:
        for m in meetings:
            print(
                f"  Would prepare: {m.person_name} "
                f"(cadence={m.cadence}, {m.days_since_1on1}d since last 1:1)"
            )
        return summary

    for meeting in meetings:
        try:
            prep = await generate_1on1_prep(meeting.person_name)
            saved_path = ""
            if save:
                md = format_prep_md(meeting.person_name, prep)
                path = write_1on1_prep_to_vault(meeting.person_name, md)
                if path:
                    saved_path = str(path)
                    log.info("Saved prep for %s to %s", meeting.person_name, path)

            summary.results.append(
                PrepResult(
                    person_name=meeting.person_name,
                    prep=prep,
                    saved_path=saved_path,
                )
            )
            summary.preps_generated += 1
        except Exception as exc:
            log.error("Failed to prepare for %s: %s", meeting.person_name, exc)
            summary.preps_failed += 1

    return summary


# ── Process mode ──────────────────────────────────────────────────────────


async def process_meeting(path: Path) -> MeetingExtraction:
    """Extract structured data from a meeting note using LLM."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        log.error("Failed to read meeting note %s: %s", path, exc)
        return MeetingExtraction()

    prompt = f"""Extract structured data from this meeting note.

{content}

Extract action items, coaching observations, feedback moments, decisions,
key themes, and a brief summary."""

    try:
        result = await extract_agent.run(prompt)
        return result.output
    except Exception as exc:
        log.error("LLM extraction failed for %s: %s", path, exc)
        return MeetingExtraction()


def route_extractions(extraction: MeetingExtraction, meeting_path: Path) -> list[Path]:
    """Route extracted data to appropriate vault locations. Returns created paths."""
    from shared.vault_writer import (
        create_coaching_starter,
        create_decision_starter,
        create_fb_record_starter,
    )

    created: list[Path] = []
    meeting_ref = meeting_path.stem

    # Resolve person once for all items
    person = _person_from_meeting_path(meeting_path)
    if not person and (extraction.coaching_observations or extraction.feedback_moments):
        log.warning(
            "Could not resolve person from %s — skipping %d coaching and %d feedback items",
            meeting_path.name,
            len(extraction.coaching_observations),
            len(extraction.feedback_moments),
        )

    # Coaching observations → coaching starter docs
    for obs in extraction.coaching_observations:
        if len(obs.strip()) < 10:
            continue
        if person:
            path = create_coaching_starter(person, obs)
            if path:
                created.append(path)

    # Feedback moments → feedback starter docs
    for fb in extraction.feedback_moments:
        if person:
            path = create_fb_record_starter(person, fb)
            if path:
                created.append(path)

    # Decisions → decision starter docs
    for decision in extraction.decisions:
        path = create_decision_starter(decision, meeting_ref)
        if path:
            created.append(path)

    return created


def _person_from_meeting_path(path: Path) -> str:
    """Try to extract person name from meeting filename or frontmatter."""
    fm = _parse_frontmatter(path)
    attendees = fm.get("attendees", "")
    if isinstance(attendees, list) and attendees:
        # First non-self attendee
        for a in attendees:
            name = str(a).strip("[]")
            if name.lower() not in ("operator", "the operator"):
                return name
    # Try from filename: YYYY-MM-DD-name-1on1.md
    stem = path.stem
    parts = stem.split("-")
    if len(parts) >= 4:
        # Skip date parts (YYYY-MM-DD)
        name_parts = parts[3:]
        # Remove common suffixes
        name_parts = [p for p in name_parts if p not in ("1on1", "standup", "retro", "meeting")]
        if name_parts:
            return " ".join(p.capitalize() for p in name_parts)
    return ""


# ── Transcript mode ───────────────────────────────────────────────────────


async def process_transcript(
    path: Path,
    dry_run: bool = False,
    save: bool = True,
) -> MeetingExtraction:
    """Parse transcript, extract data, create meeting note."""
    from shared.transcript_parser import format_as_text, parse_transcript

    segments = parse_transcript(path)
    if not segments:
        log.warning("No segments parsed from %s", path)
        return MeetingExtraction()

    transcript_text = format_as_text(segments)
    prompt = f"""Extract structured data from this meeting transcript.

{transcript_text[:8000]}

Extract action items, coaching observations, feedback moments, decisions,
key themes, and a brief summary."""

    try:
        result = await extract_agent.run(prompt)
        extraction = result.output
    except Exception as exc:
        log.error("LLM extraction failed for transcript %s: %s", path, exc)
        return MeetingExtraction()

    if save and not dry_run:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        meeting_md = _format_meeting_from_extraction(extraction, transcript_text)
        meeting_path = write_to_vault(
            "10-work/meetings",
            f"{today}-{slug}.md",
            meeting_md,
            frontmatter={
                "type": "meeting",
                "date": today,
                "source": "transcript",
                "transcript-file": path.name,
                "tags": ["meeting", "transcript"],
            },
        )
        if meeting_path:
            log.info("Created meeting note: %s", meeting_path)
            route_extractions(extraction, meeting_path)

    return extraction


def _format_meeting_from_extraction(extraction: MeetingExtraction, transcript: str) -> str:
    """Format a meeting note from extraction results."""
    lines = ["# Meeting Notes", ""]

    if extraction.summary:
        lines.append("## Summary")
        lines.append(extraction.summary)
        lines.append("")

    if extraction.key_themes:
        lines.append("## Key Themes")
        for theme in extraction.key_themes:
            lines.append(f"- {theme}")
        lines.append("")

    if extraction.action_items:
        lines.append("## Action Items")
        for item in extraction.action_items:
            assignee = f" (@{item.assignee})" if item.assignee else ""
            due = f" (due: {item.due_date})" if item.due_date else ""
            lines.append(f"- [ ] {item.text}{assignee}{due}")
        lines.append("")

    if extraction.decisions:
        lines.append("## Decisions")
        for d in extraction.decisions:
            lines.append(f"- {d}")
        lines.append("")

    lines.append("## Transcript")
    lines.append(transcript[:5000])

    return "\n".join(lines)


# ── Weekly review mode ─────────────────────────────────────────────────────


def generate_weekly_review() -> WeeklyReviewData:
    """Deterministic data collection for weekly review pre-population."""
    snapshot = collect_management_state()
    data = WeeklyReviewData()

    # Cognitive load table
    for p in snapshot.people:
        signals = []
        if p.stale_1on1:
            signals.append(f"stale 1:1 ({p.days_since_1on1}d)")
        if p.coaching_active:
            signals.append("coaching active")

        action = ""
        if p.cognitive_load is not None and p.cognitive_load >= 4:
            action = "discuss workload"
        elif p.stale_1on1:
            action = "schedule 1:1"

        data.cognitive_load_table.append(
            {
                "person": p.name,
                "load": p.cognitive_load or "?",
                "signals": ", ".join(signals) if signals else "none",
                "action": action,
            }
        )

    # Meeting count this week — vault excised, no meeting files to scan

    # Risks
    for p in snapshot.people:
        if p.stale_1on1:
            data.risks.append(f"Stale 1:1: {p.name} ({p.days_since_1on1}d)")
        if p.cognitive_load is not None and p.cognitive_load >= 4:
            data.risks.append(f"High load: {p.name} ({p.cognitive_load}/5)")

    # Coaching activity
    for c in snapshot.coaching:
        status = "OVERDUE" if c.overdue else c.status
        data.coaching_activity.append(f"{c.title} ({c.person}, {status})")

    # Feedback activity
    for f in snapshot.feedback:
        status = "OVERDUE" if f.overdue else "pending"
        data.feedback_activity.append(f"{f.title} ({f.person}, {status})")

    return data


def format_weekly_review_md(data: WeeklyReviewData) -> str:
    """Format weekly review as markdown."""
    today = datetime.now(UTC)
    week_num = today.isocalendar()[1]
    year = today.year

    lines = [
        f"# Weekly Review — {year}-W{week_num:02d}",
        "",
        "## Cognitive Load Table",
        "",
        "| Person | Load | Signals | Action |",
        "|--------|------|---------|--------|",
    ]

    for row in data.cognitive_load_table:
        lines.append(f"| {row['person']} | {row['load']}/5 | {row['signals']} | {row['action']} |")
    lines.append("")

    lines.append(f"## Meetings This Week: {data.meetings_this_week}")
    lines.append("")

    if data.risks:
        lines.append("## Risks")
        for r in data.risks:
            lines.append(f"- {r}")
        lines.append("")

    if data.coaching_activity:
        lines.append("## Coaching Activity")
        for c in data.coaching_activity:
            lines.append(f"- {c}")
        lines.append("")

    if data.feedback_activity:
        lines.append("## Feedback Activity")
        for f in data.feedback_activity:
            lines.append(f"- {f}")
        lines.append("")

    # Blank sections for operator judgment
    lines.append("## Wins")
    lines.append("- ")
    lines.append("")
    lines.append("## Key Outcomes")
    lines.append("- ")
    lines.append("")
    lines.append("## Next Week Focus")
    lines.append("- ")
    lines.append("")

    return "\n".join(lines)


def write_weekly_review_to_vault(data: WeeklyReviewData) -> Path | None:
    """Write weekly review to vault."""
    today = datetime.now(UTC)
    week_num = today.isocalendar()[1]
    year = today.year
    md = format_weekly_review_md(data)
    return write_to_vault(
        "30-system/weekly-reviews",
        f"{year}-W{week_num:02d}.md",
        md,
        frontmatter={
            "type": "weekly-review",
            "date": today.strftime("%Y-%m-%d"),
            "week": f"{year}-W{week_num:02d}",
            "source": "agents.meeting_lifecycle",
            "tags": ["weekly-review", "system"],
        },
    )


# ── CLI ────────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Meeting lifecycle automation agent",
        prog="python -m agents.meeting_lifecycle",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true", help="Auto-prep due meetings")
    group.add_argument("--process", type=str, metavar="FILE", help="Process a meeting note")
    group.add_argument("--transcript", type=str, metavar="FILE", help="Ingest a transcript")
    group.add_argument("--weekly-review", action="store_true", help="Pre-populate weekly review")

    parser.add_argument("--person", type=str, help="Filter to one person (with --prepare)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    parser.add_argument("--save", action="store_true", help="Save output to vault")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.prepare:
        print("Discovering due meetings...", file=sys.stderr)
        summary = await prepare_all(
            person_filter=args.person,
            dry_run=args.dry_run,
            save=args.save or not args.dry_run,
        )
        print(
            f"Due: {summary.meetings_due}, "
            f"Generated: {summary.preps_generated}, "
            f"Failed: {summary.preps_failed}",
            file=sys.stderr,
        )
        if args.json:
            print(summary.model_dump_json(indent=2))
        elif not args.dry_run:
            for r in summary.results:
                print(f"\n{'=' * 60}")
                print(format_prep_md(r.person_name, r.prep))

    elif args.process:
        path = Path(args.process).resolve()
        print(f"Processing meeting note: {path}", file=sys.stderr)
        extraction = await process_meeting(path)
        if not args.dry_run:
            created = route_extractions(extraction, path)
            if created:
                print(f"Created {len(created)} starter docs", file=sys.stderr)
        if args.json:
            print(extraction.model_dump_json(indent=2))
        else:
            print(f"Summary: {extraction.summary}")
            print(f"Action items: {len(extraction.action_items)}")
            print(f"Decisions: {len(extraction.decisions)}")
            print(f"Coaching observations: {len(extraction.coaching_observations)}")
            print(f"Feedback moments: {len(extraction.feedback_moments)}")

    elif args.transcript:
        path = Path(args.transcript)
        print(f"Processing transcript: {path}", file=sys.stderr)
        extraction = await process_transcript(
            path,
            dry_run=args.dry_run,
            save=args.save or not args.dry_run,
        )
        if args.json:
            print(extraction.model_dump_json(indent=2))
        else:
            print(f"Summary: {extraction.summary}")
            print(f"Action items: {len(extraction.action_items)}")

    elif args.weekly_review:
        print("Generating weekly review...", file=sys.stderr)
        data = generate_weekly_review()
        if args.save:
            path = write_weekly_review_to_vault(data)
            if path:
                print(f"Saved to {path}", file=sys.stderr)
        if args.json:
            print(data.model_dump_json(indent=2))
        else:
            print(format_weekly_review_md(data))


if __name__ == "__main__":
    asyncio.run(main())
