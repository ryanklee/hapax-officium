"""management_briefing.py — Morning management briefing generator.

Consumes management state (team members, 1:1 staleness, coaching check-ins,
feedback follow-ups, cognitive load) plus management goals, then synthesizes
into a concise actionable briefing for people management work.

Zero LLM calls for data collection; one fast LLM call for synthesis.

Usage:
    uv run python -m agents.management_briefing                  # Generate and display
    uv run python -m agents.management_briefing --save           # Also save to profiles/
    uv run python -m agents.management_briefing --json           # Machine-readable JSON
    uv run python -m agents.management_briefing --notify         # Send notification
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime

log = logging.getLogger(__name__)

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from shared.config import PROFILES_DIR, get_model
from shared.operator import get_system_prompt_fragment

# Import Langfuse OTel config (side-effect: configures exporter)
try:
    from shared import langfuse_config  # noqa: F401
except ImportError:
    pass

from logos.data.goals import GoalSnapshot, collect_goals
from logos.data.management import ManagementSnapshot, collect_management_state

# ── Schemas ──────────────────────────────────────────────────────────────────


class ManagementBriefingStats(BaseModel):
    """Key numbers for the management briefing."""

    people_count: int = 0
    stale_1on1_count: int = 0
    overdue_coaching_count: int = 0
    overdue_feedback_count: int = 0
    high_load_count: int = 0
    teams_falling_behind: list[str] = []
    management_goal_count: int = 0


class ActionItem(BaseModel):
    """A specific recommended action for the operator."""

    priority: str = Field(description="high, medium, or low")
    action: str = Field(description="What to do, in imperative form")
    reason: str = Field(description="Why this matters, one sentence")


class ManagementBriefing(BaseModel):
    """The synthesized management briefing."""

    generated_at: str = Field(description="ISO timestamp")
    headline: str = Field(description="One-line management status summary")
    body: str = Field(description="3-5 sentence narrative briefing")
    action_items: list[ActionItem] = Field(default_factory=list)
    stats: ManagementBriefingStats = Field(default_factory=ManagementBriefingStats)


# ── Synthesis ────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are generating a morning management briefing for an engineering manager.
Surface patterns and open loops in the operator's people management work.

CRITICAL: Do not generate feedback language, coaching recommendations,
or suggestions for what to say to anyone. Present facts and patterns only.
The operator makes all people decisions — this briefing surfaces data, never advice.

The operator is technical and wants precision, not filler. Write like a concise
status report: headline, situation, notable items, recommended actions.

GUIDELINES:
- Headline: one sentence, overall management state (e.g., "2 stale 1:1s, 1 overdue coaching check-in")
- Body: 3-5 sentences covering what needs attention in people management
- Action items: only include things that NEED doing — stale 1:1s to schedule,
  overdue coaching check-ins, feedback follow-ups past due, high cognitive load signals
- If everything is current, say so briefly — don't pad
- Priority levels: high = needs attention today, medium = this week, low = when convenient
- For management goals, note which saw progress and which are stalled.
  Frame stalled goals as observation, not failure.
- Never suggest what to say to a team member or draft feedback language
- Never generate coaching hypotheses or performance evaluations
"""

management_briefing_agent = Agent(
    get_model("fast"),
    system_prompt=get_system_prompt_fragment("management-briefing") + "\n\n" + SYSTEM_PROMPT,
    output_type=ManagementBriefing,
)

# Register on-demand operator context tools
from shared.context_tools import get_context_tools

for _tool_fn in get_context_tools():
    management_briefing_agent.tool(_tool_fn)

from shared.axiom_tools import get_axiom_tools

for _tool_fn in get_axiom_tools():
    management_briefing_agent.tool(_tool_fn)


def _format_management_state(mgmt: ManagementSnapshot) -> str:
    """Format management snapshot as structured text for LLM prompt."""
    lines: list[str] = []

    lines.append(f"Active team members: {mgmt.active_people_count}")
    lines.append(f"Stale 1:1s: {mgmt.stale_1on1_count}")
    lines.append(f"Overdue coaching check-ins: {mgmt.overdue_coaching_count}")
    lines.append(f"Overdue feedback follow-ups: {mgmt.overdue_feedback_count}")
    lines.append(f"High cognitive load (>=4): {mgmt.high_load_count}")

    # Detail stale 1:1s
    stale = [p for p in mgmt.people if p.stale_1on1]
    if stale:
        lines.append("")
        lines.append("### Stale 1:1s")
        for p in stale:
            days = f"{p.days_since_1on1}d" if p.days_since_1on1 is not None else "unknown"
            lines.append(f"- {p.name} ({p.team}): {p.cadence} cadence, last {days} ago")

    # Detail overdue coaching
    overdue_coaching = [c for c in mgmt.coaching if c.overdue]
    if overdue_coaching:
        lines.append("")
        lines.append("### Overdue Coaching Check-ins")
        for c in overdue_coaching:
            lines.append(f"- {c.title} (person: {c.person}): {c.days_overdue}d overdue")

    # Detail overdue feedback
    overdue_feedback = [f for f in mgmt.feedback if f.overdue]
    if overdue_feedback:
        lines.append("")
        lines.append("### Overdue Feedback Follow-ups")
        for f in overdue_feedback:
            lines.append(
                f"- {f.title} (person: {f.person}): {f.days_overdue}d overdue, {f.direction}/{f.category}"
            )

    # Detail high cognitive load
    high_load = [p for p in mgmt.people if p.cognitive_load is not None and p.cognitive_load >= 4]
    if high_load:
        lines.append("")
        lines.append("### High Cognitive Load")
        for p in high_load:
            lines.append(f"- {p.name} ({p.team}): load {p.cognitive_load}/5")

    return "\n".join(lines)


def _format_goals(goals_snap: GoalSnapshot) -> str:
    """Format management goals as structured text for LLM prompt."""
    if not goals_snap.goals:
        return "No management goals configured."

    lines: list[str] = []
    lines.append(f"Active goals: {goals_snap.active_count}, Stale: {goals_snap.stale_count}")

    for g in goals_snap.goals:
        stale_tag = " [STALE]" if g.stale else ""
        activity = (
            f"{g.last_activity_h:.0f}h ago" if g.last_activity_h is not None else "no activity"
        )
        lines.append(
            f"- [{g.category}/{g.status}]{stale_tag} {g.name}: {g.description} ({activity})"
        )
        if g.progress_summary:
            lines.append(f"  Progress: {g.progress_summary}")

    if goals_snap.primary_stale:
        lines.append(f"\nPrimary goals stale: {', '.join(goals_snap.primary_stale)}")

    return "\n".join(lines)


def _identify_teams_falling_behind(mgmt: ManagementSnapshot) -> list[str]:
    """Identify teams with multiple issues (stale 1:1s + high load)."""
    team_issues: dict[str, int] = {}
    for p in mgmt.people:
        if not p.team:
            continue
        issues = 0
        if p.stale_1on1:
            issues += 1
        if p.cognitive_load is not None and p.cognitive_load >= 4:
            issues += 1
        if issues > 0:
            team_issues[p.team] = team_issues.get(p.team, 0) + issues

    # Teams with 2+ accumulated issues
    return [team for team, count in team_issues.items() if count >= 2]


async def generate_briefing() -> ManagementBriefing:
    """Collect management state and goals, synthesize briefing."""
    # Collect management state (no LLM calls)
    mgmt = collect_management_state()

    # Collect management goals
    goals_snap = collect_goals()

    # Identify teams falling behind
    teams_behind = _identify_teams_falling_behind(mgmt)

    # Build stats
    stats = ManagementBriefingStats(
        people_count=mgmt.active_people_count,
        stale_1on1_count=mgmt.stale_1on1_count,
        overdue_coaching_count=mgmt.overdue_coaching_count,
        overdue_feedback_count=mgmt.overdue_feedback_count,
        high_load_count=mgmt.high_load_count,
        teams_falling_behind=teams_behind,
        management_goal_count=goals_snap.active_count,
    )

    # Build prompt sections
    mgmt_text = _format_management_state(mgmt)
    goals_text = _format_goals(goals_snap)

    prompt = f"""## Management State

{mgmt_text}

## Management Goals

{goals_text}

Generate a management briefing. The timestamp is {datetime.now(UTC).isoformat()[:19]}Z."""

    try:
        result = await management_briefing_agent.run(prompt)
        briefing = result.output
    except Exception as e:
        log.error("LLM synthesis failed: %s", e)
        briefing = ManagementBriefing(
            generated_at=datetime.now(UTC).isoformat()[:19] + "Z",
            headline="Briefing unavailable -- LLM error",
            body=str(e),
            action_items=[],
        )
    briefing.generated_at = datetime.now(UTC).isoformat()[:19] + "Z"
    briefing.stats = stats

    return briefing


# ── Formatters ───────────────────────────────────────────────────────────────


def format_briefing_md(briefing: ManagementBriefing) -> str:
    """Format briefing as markdown for file storage."""
    lines = [
        "# Management Briefing",
        f"*Generated {briefing.generated_at}*",
        "",
        f"## {briefing.headline}",
        "",
        briefing.body,
        "",
    ]

    # Stats
    s = briefing.stats
    lines.append("## Stats")
    lines.append(f"- Team members: {s.people_count}")
    if s.stale_1on1_count:
        lines.append(f"- Stale 1:1s: {s.stale_1on1_count}")
    if s.overdue_coaching_count:
        lines.append(f"- Overdue coaching: {s.overdue_coaching_count}")
    if s.overdue_feedback_count:
        lines.append(f"- Overdue feedback: {s.overdue_feedback_count}")
    if s.high_load_count:
        lines.append(f"- High cognitive load: {s.high_load_count}")
    if s.teams_falling_behind:
        lines.append(f"- Teams needing attention: {', '.join(s.teams_falling_behind)}")
    lines.append(f"- Management goals: {s.management_goal_count}")
    lines.append("")

    # Action items
    if briefing.action_items:
        date_str = briefing.generated_at[:10]
        lines.append("## Action Items")
        for item in sorted(
            briefing.action_items,
            key=lambda a: {"high": 0, "medium": 1, "low": 2}.get(a.priority, 3),
        ):
            pri_emoji = {"high": " !!!", "medium": " !!", "low": " !"}.get(item.priority, "")
            lines.append(f"- [ ] {item.action}{pri_emoji} [{date_str}]")
            lines.append(f"  - {item.reason}")
        lines.append("")

    return "\n".join(lines)


def format_briefing_human(briefing: ManagementBriefing) -> str:
    """Format briefing for terminal display."""
    lines = [
        f"Management Briefing -- {briefing.generated_at}",
        "",
        briefing.headline,
        "",
        briefing.body,
        "",
    ]

    s = briefing.stats
    parts = [f"{s.people_count} people"]
    if s.stale_1on1_count:
        parts.append(f"{s.stale_1on1_count} stale 1:1s")
    if s.overdue_coaching_count:
        parts.append(f"{s.overdue_coaching_count} overdue coaching")
    if s.overdue_feedback_count:
        parts.append(f"{s.overdue_feedback_count} overdue feedback")
    if s.high_load_count:
        parts.append(f"{s.high_load_count} high load")
    lines.append("Stats: " + " | ".join(parts))

    if briefing.action_items:
        lines.append("")
        lines.append("Action Items:")
        for item in sorted(
            briefing.action_items,
            key=lambda a: {"high": 0, "medium": 1, "low": 2}.get(a.priority, 3),
        ):
            icon = {"high": "!!", "medium": "! ", "low": ".."}
            lines.append(f"  [{icon.get(item.priority, '??')}] {item.action}")

    return "\n".join(lines)


# ── Notification ─────────────────────────────────────────────────────────────


def send_notification(briefing: ManagementBriefing) -> None:
    """Send briefing notification via ntfy (shared.notify)."""
    from shared.notify import send_notification as _notify

    summary = briefing.headline
    body_parts = [summary]
    if briefing.action_items:
        high = [a for a in briefing.action_items if a.priority == "high"]
        if high:
            body_parts.append(f"{len(high)} high-priority action(s)")

    priority = "high" if any(a.priority == "high" for a in briefing.action_items) else "default"
    tags = ["clipboard"] if priority == "default" else ["clipboard", "warning"]

    _notify(
        "Management Briefing",
        "\n".join(body_parts),
        priority=priority,
        tags=tags,
    )


# ── CLI ──────────────────────────────────────────────────────────────────────

BRIEFING_FILE = PROFILES_DIR / "management-briefing.md"
BRIEFING_JSON = PROFILES_DIR / "management-briefing.json"


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Morning management briefing generator",
        prog="python -m agents.management_briefing",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument(
        "--save", action="store_true", help="Save to profiles/management-briefing.md"
    )
    parser.add_argument("--notify", action="store_true", help="Send notification")
    args = parser.parse_args()

    print("Collecting management state...", file=sys.stderr)
    briefing = await generate_briefing()

    if args.save:
        briefing_md = format_briefing_md(briefing)
        BRIEFING_FILE.write_text(briefing_md)
        BRIEFING_JSON.write_text(briefing.model_dump_json(indent=2))
        print(f"Saved to {BRIEFING_FILE}", file=sys.stderr)

        # Also write to Obsidian vault for Sync
        from shared.vault_writer import write_briefing_to_vault

        vault_path = write_briefing_to_vault(briefing_md)
        if vault_path:
            print(f"Vault: {vault_path}", file=sys.stderr)
        else:
            log.warning("Failed to write briefing to vault")

    if args.notify:
        send_notification(briefing)

    if args.json:
        print(briefing.model_dump_json(indent=2))
    else:
        print(format_briefing_human(briefing))


if __name__ == "__main__":
    asyncio.run(main())
