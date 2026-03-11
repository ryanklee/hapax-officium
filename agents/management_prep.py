"""management_prep.py — Management preparation agent.

Reads management state data and synthesizes preparation material for 1:1s,
team snapshots, and management overviews.

Zero LLM calls for data collection; one LLM call for synthesis.

Guiding principle: "LLM Prepares, Human Delivers."
The agent generates preparation material only. It does NOT draft feedback
language, generate coaching hypotheses, or suggest what the operator should say.

Usage:
    uv run python -m agents.management_prep --person "Alice"
    uv run python -m agents.management_prep --team-snapshot
    uv run python -m agents.management_prep --overview
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime

log = logging.getLogger("management_prep")

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import get_model
from shared.operator import get_system_prompt_fragment

# Import Langfuse OTel config (side-effect: configures exporter)
try:
    from shared import langfuse_config  # noqa: F401
except ImportError:
    pass

from cockpit.data.management import (
    ManagementSnapshot,
    PersonState,
    collect_management_state,
)

# ── Schemas ──────────────────────────────────────────────────────────────────


class PrepDocument(BaseModel):
    """LLM-synthesized 1:1 preparation document."""

    summary: str = Field(description="2-3 sentence context summary for this person")
    rolling_themes: list[str] = Field(
        default_factory=list, description="Patterns across recent meetings"
    )
    open_items: list[str] = Field(default_factory=list, description="Unresolved action items")
    coaching_status: str = Field(default="", description="Status of active coaching experiments")
    suggested_topics: list[str] = Field(default_factory=list, description="Topics worth covering")
    energy_signals: str = Field(default="", description="Observed energy/load signals")


class TeamSnapshot(BaseModel):
    """LLM-synthesized team state snapshot."""

    headline: str = Field(description="One-line team state summary")
    people_summaries: list[str] = Field(default_factory=list, description="One-line per person")
    load_assessment: str = Field(default="", description="Cognitive load distribution narrative")
    active_experiments: list[str] = Field(
        default_factory=list, description="Active coaching/feedback"
    )
    topology_observations: str = Field(default="", description="Team interaction patterns")
    themes: list[str] = Field(default_factory=list, description="Recurring strategic themes")


class ManagementOverview(BaseModel):
    """Condensed management overview for system folder."""

    headline: str = Field(description="One-line management state summary")
    body: str = Field(description="3-5 sentence management overview")
    key_actions: list[str] = Field(default_factory=list, description="Top actions needed")


# ── System prompts ───────────────────────────────────────────────────────────

PREP_SYSTEM_PROMPT = """\
You are a management preparation assistant. Your role is to aggregate signals
and synthesize context for an upcoming 1:1 meeting.

CRITICAL BOUNDARIES:
- Generate preparation material ONLY
- Do NOT draft feedback language
- Do NOT generate coaching hypotheses
- Do NOT suggest what the operator should say
- Focus on signal aggregation and context synthesis
- Surface patterns and open loops, not recommendations for people decisions

The operator is an experienced manager who makes their own judgments about people.
Your value is saving them time on information gathering, not substituting for
their direct observation and relational work.

Call lookup_constraints() for additional operator constraints.
"""

SNAPSHOT_SYSTEM_PROMPT = """\
You are a team state summarizer. Given structured data about team members,
coaching experiments, and feedback records, produce a concise team snapshot.

CRITICAL BOUNDARIES:
- Summarize observed state only
- Do NOT evaluate individual performance
- Do NOT suggest people actions
- Focus on patterns, load distribution, and open experiments
- Be factual and concise

Call lookup_constraints() for additional operator constraints.
"""

OVERVIEW_SYSTEM_PROMPT = """\
You are a management state summarizer. Given a management snapshot, produce
a brief overview suitable for a system dashboard.

Be concise. Surface the most important signals: stale 1:1s, overdue items,
load distribution. The operator will drill into details elsewhere.

Call lookup_constraints() for additional operator constraints.
"""


# ── Agents ───────────────────────────────────────────────────────────────────

_FRAG = get_system_prompt_fragment("management-prep")

prep_agent = Agent(
    get_model("balanced"),
    system_prompt=_FRAG + "\n\n" + PREP_SYSTEM_PROMPT,
    output_type=PrepDocument,
)

snapshot_agent = Agent(
    get_model("balanced"),
    system_prompt=_FRAG + "\n\n" + SNAPSHOT_SYSTEM_PROMPT,
    output_type=TeamSnapshot,
)

overview_agent = Agent(
    get_model("fast"),
    system_prompt=_FRAG + "\n\n" + OVERVIEW_SYSTEM_PROMPT,
    output_type=ManagementOverview,
)

# Register on-demand operator context tools on all LLM agents
from shared.context_tools import get_context_tools

for _tool_fn in get_context_tools():
    prep_agent.tool(_tool_fn)
    snapshot_agent.tool(_tool_fn)
    overview_agent.tool(_tool_fn)

from shared.axiom_tools import get_axiom_tools

for _tool_fn in get_axiom_tools():
    prep_agent.tool(_tool_fn)
    snapshot_agent.tool(_tool_fn)
    overview_agent.tool(_tool_fn)


# ── Data collection ──────────────────────────────────────────────────────────


def _find_person(snapshot: ManagementSnapshot, name: str) -> PersonState | None:
    """Find a person in the snapshot by name (case-insensitive)."""
    name_lower = name.lower()
    for p in snapshot.people:
        if p.name.lower() == name_lower:
            return p
    return None


def _read_recent_meetings(person_name: str, limit: int = 5) -> list[dict]:
    """Read last N 1:1 meeting notes for a person.

    Returns empty list — vault data source excised.
    """
    return []


def _collect_person_context(person: PersonState, snapshot: ManagementSnapshot) -> str:
    """Build a context string for a person's 1:1 prep."""
    lines = [
        f"## Person: {person.name}",
        f"- Role: {person.role}",
        f"- Team: {person.team}",
        f"- Cadence: {person.cadence}",
        f"- Last 1:1: {person.last_1on1 or 'unknown'}",
        f"- Days since 1:1: {person.days_since_1on1 or 'unknown'}",
        f"- Cognitive load: {person.cognitive_load or 'not rated'}/5",
        f"- Growth vector: {person.growth_vector or 'not set'}",
        f"- Coaching active: {person.coaching_active}",
        f"- Career goal (3y): {person.career_goal_3y or 'not set'}",
        f"- Current focus: {person.current_focus or 'not set'}",
        f"- Skill level: {person.skill_level or 'not rated'}",
        f"- Team type: {person.team_type or 'not classified'}",
        "",
    ]

    # Related coaching hypotheses
    related_coaching = [c for c in snapshot.coaching if c.person.lower() == person.name.lower()]
    if related_coaching:
        lines.append("## Active Coaching Experiments")
        for c in related_coaching:
            status = "OVERDUE" if c.overdue else c.status
            lines.append(f"- {c.title} (status: {status}, check-in by: {c.check_in_by})")
        lines.append("")

    # Related feedback
    related_feedback = [f for f in snapshot.feedback if f.person.lower() == person.name.lower()]
    if related_feedback:
        lines.append("## Open Feedback Follow-ups")
        for f in related_feedback:
            status = "OVERDUE" if f.overdue else "pending"
            lines.append(f"- {f.title} ({f.category}, {f.direction}, {status})")
        lines.append("")

    # Recent meetings
    meetings = _read_recent_meetings(person.name)
    if meetings:
        lines.append(f"## Last {len(meetings)} 1:1 Meeting Notes")
        for m in meetings:
            lines.append(f"### {m['date']}")
            lines.append(m["content"])
            lines.append("")

    return "\n".join(lines)


def _collect_team_context(snapshot: ManagementSnapshot) -> str:
    """Build a context string for team snapshot synthesis."""
    lines = ["## Team State Data", ""]

    lines.append("### People")
    for p in snapshot.people:
        lines.append(
            f"- {p.name} | {p.role} | {p.team} | "
            f"load:{p.cognitive_load or '?'}/5 | "
            f"growth:{p.growth_vector or 'unset'} | "
            f"coaching:{p.coaching_active} | "
            f"last 1:1:{p.last_1on1 or 'unknown'} | "
            f"stale:{p.stale_1on1}"
        )
    lines.append("")

    if snapshot.coaching:
        lines.append("### Active Coaching")
        for c in snapshot.coaching:
            status = "OVERDUE" if c.overdue else c.status
            lines.append(f"- {c.title} (person: {c.person}, {status})")
        lines.append("")

    if snapshot.feedback:
        lines.append("### Open Feedback")
        for f in snapshot.feedback:
            status = "OVERDUE" if f.overdue else "pending"
            lines.append(f"- {f.title} (person: {f.person}, {f.category}, {status})")
        lines.append("")

    lines.append("### Summary Counts")
    lines.append(f"- Active people: {snapshot.active_people_count}")
    lines.append(f"- Stale 1:1s: {snapshot.stale_1on1_count}")
    lines.append(f"- Overdue coaching: {snapshot.overdue_coaching_count}")
    lines.append(f"- Overdue feedback: {snapshot.overdue_feedback_count}")
    lines.append(f"- High load (4+): {snapshot.high_load_count}")

    return "\n".join(lines)


# ── Prep generation ──────────────────────────────────────────────────────────


async def generate_1on1_prep(person_name: str) -> PrepDocument:
    """Generate 1:1 preparation for a specific person."""
    snapshot = collect_management_state()
    person = _find_person(snapshot, person_name)

    if person is None:
        return PrepDocument(
            summary=f"No active person record found for '{person_name}'.",
            suggested_topics=["Check that a person record exists in the data source"],
        )

    context = _collect_person_context(person, snapshot)
    prompt = f"""Prepare a 1:1 context summary for the following team member.
Focus on aggregating signals — patterns from recent meetings, open items,
coaching experiment status, and energy/load signals.

{context}

Generate the preparation document now."""

    try:
        result = await prep_agent.run(prompt)
    except Exception as exc:
        log.error("LLM 1:1 prep failed for %s: %s", person_name, exc)
        return PrepDocument(
            summary=f"1:1 prep generation failed: {exc}",
            suggested_topics=[
                "Retry with: uv run python -m agents.management_prep --person " + person_name
            ],
        )
    return result.output


async def generate_team_snapshot() -> TeamSnapshot:
    """Generate a team state snapshot."""
    snapshot = collect_management_state()

    if not snapshot.people:
        return TeamSnapshot(
            headline="No active people found.",
            people_summaries=["Check that person records exist in the data source"],
        )

    context = _collect_team_context(snapshot)
    prompt = f"""Summarize the current team state based on this data.
Focus on cognitive load distribution, active experiments, and open loops.

{context}

Generate the team snapshot now."""

    try:
        result = await snapshot_agent.run(prompt)
    except Exception as exc:
        log.error("LLM team snapshot failed: %s", exc)
        return TeamSnapshot(
            headline=f"Team snapshot generation failed: {exc}",
        )
    return result.output


async def generate_overview() -> ManagementOverview:
    """Generate a condensed management overview."""
    snapshot = collect_management_state()
    context = _collect_team_context(snapshot)
    prompt = f"""Generate a brief management overview for the system dashboard.

{context}

Generate the overview now."""

    try:
        result = await overview_agent.run(prompt)
    except Exception as exc:
        log.error("LLM management overview failed: %s", exc)
        return ManagementOverview(
            headline=f"Management overview generation failed: {exc}",
            body=str(exc),
        )
    return result.output


# ── Formatters ───────────────────────────────────────────────────────────────


def format_prep_md(person_name: str, prep: PrepDocument) -> str:
    """Format 1:1 prep as markdown."""
    lines = [
        f"# 1:1 Prep — {person_name}",
        "",
        "## Context Summary",
        prep.summary,
        "",
    ]

    if prep.rolling_themes:
        lines.append("## Rolling Themes")
        for theme in prep.rolling_themes:
            lines.append(f"- {theme}")
        lines.append("")

    if prep.open_items:
        lines.append("## Open Items")
        for item in prep.open_items:
            lines.append(f"- [ ] {item}")
        lines.append("")

    if prep.coaching_status:
        lines.append("## Coaching Experiment Status")
        lines.append(prep.coaching_status)
        lines.append("")

    if prep.suggested_topics:
        lines.append("## Suggested Topics")
        for topic in prep.suggested_topics:
            lines.append(f"- [ ] {topic}")
        lines.append("")

    if prep.energy_signals:
        lines.append("## Energy/Load Signals")
        lines.append(prep.energy_signals)
        lines.append("")

    return "\n".join(lines)


def format_snapshot_md(snap: TeamSnapshot) -> str:
    """Format team snapshot as markdown."""
    lines = [
        "# Team State Snapshot",
        "",
        f"## {snap.headline}",
        "",
    ]

    if snap.people_summaries:
        lines.append("## People")
        for s in snap.people_summaries:
            lines.append(f"- {s}")
        lines.append("")

    if snap.load_assessment:
        lines.append("## Cognitive Load Assessment")
        lines.append(snap.load_assessment)
        lines.append("")

    if snap.active_experiments:
        lines.append("## Active Experiments")
        for exp in snap.active_experiments:
            lines.append(f"- {exp}")
        lines.append("")

    if snap.topology_observations:
        lines.append("## Topology Observations")
        lines.append(snap.topology_observations)
        lines.append("")

    if snap.themes:
        lines.append("## Strategic Themes")
        for theme in snap.themes:
            lines.append(f"- {theme}")
        lines.append("")

    return "\n".join(lines)


def format_overview_md(overview: ManagementOverview) -> str:
    """Format management overview as markdown."""
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "# Management Overview",
        f"*Updated {now}*",
        "",
        f"## {overview.headline}",
        "",
        overview.body,
        "",
    ]

    if overview.key_actions:
        lines.append("## Key Actions")
        for action in overview.key_actions:
            lines.append(f"- [ ] {action}")
        lines.append("")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Management preparation agent",
        prog="python -m agents.management_prep",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--person", type=str, help="Generate 1:1 prep for a person")
    group.add_argument("--team-snapshot", action="store_true", help="Generate team snapshot")
    group.add_argument("--overview", action="store_true", help="Generate management overview")
    parser.add_argument("--save", action="store_true", help="Save to vault")
    parser.add_argument("--json", action="store_true", help="JSON output")
    args = parser.parse_args()

    if args.person:
        print(f"Preparing 1:1 context for {args.person}...", file=sys.stderr)
        prep = await generate_1on1_prep(args.person)

        if args.save:
            from shared.vault_writer import write_1on1_prep_to_vault

            md = format_prep_md(args.person, prep)
            path = write_1on1_prep_to_vault(args.person, md)
            if path:
                print(f"Saved to {path}", file=sys.stderr)

        if args.json:
            print(prep.model_dump_json(indent=2))
        else:
            print(format_prep_md(args.person, prep))

    elif args.team_snapshot:
        print("Generating team snapshot...", file=sys.stderr)
        snap = await generate_team_snapshot()

        if args.save:
            from shared.vault_writer import write_team_snapshot_to_vault

            md = format_snapshot_md(snap)
            path = write_team_snapshot_to_vault(md)
            if path:
                print(f"Saved to {path}", file=sys.stderr)

        if args.json:
            print(snap.model_dump_json(indent=2))
        else:
            print(format_snapshot_md(snap))

    elif args.overview:
        print("Generating management overview...", file=sys.stderr)
        overview = await generate_overview()

        if args.save:
            from shared.vault_writer import write_management_overview_to_vault

            md = format_overview_md(overview)
            path = write_management_overview_to_vault(md)
            if path:
                print(f"Saved to {path}", file=sys.stderr)

        if args.json:
            print(overview.model_dump_json(indent=2))
        else:
            print(format_overview_md(overview))


if __name__ == "__main__":
    asyncio.run(main())
