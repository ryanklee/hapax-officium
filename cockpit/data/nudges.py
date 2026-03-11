"""Nudge collector — surfaces prioritized management open loops for the chat UI.

Fully deterministic, no LLM calls. Aggregates data from management state
collectors and returns a ranked list of suggested actions.

Nudges are allocated across three category slots (people, goals, operational)
to ensure diversity. Unused slots redistribute to categories with overflow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from cockpit.data.management import ManagementSnapshot

MAX_VISIBLE_NUDGES = 7  # attention budget cap — cognitive overload prevention

CATEGORY_SLOTS: dict[str, int] = {"people": 3, "goals": 2, "operational": 2}


@dataclass
class Nudge:
    """A single actionable nudge for the operator."""

    category: str  # "people" | "goals" | "operational" | "meta"
    priority_score: int  # numeric, higher = more urgent
    priority_label: str  # "critical" | "high" | "medium" | "low"
    title: str  # short line, e.g. "Stale 1:1 with Alice"
    detail: str  # elaboration
    suggested_action: str
    command_hint: str = ""
    source_id: str = ""  # identity tracking for decision capture


# ── Per-source collectors ────────────────────────────────────────────────────


def _collect_management_nudges(
    nudges: list[Nudge],
    snap: ManagementSnapshot | None = None,
) -> None:
    """Check management state for stale 1:1s, overdue coaching/feedback, high load."""
    try:
        if snap is None:
            from cockpit.data.management import collect_management_state

            snap = collect_management_state()

        # Stale 1:1s (priority 70)
        for p in snap.people:
            if p.stale_1on1:
                days = p.days_since_1on1
                detail = f"Last 1:1 was {days} days ago" if days else "No recorded 1:1"
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=70,
                        priority_label="high",
                        title=f"Stale 1:1 with {p.name}",
                        detail=f"{detail} (cadence: {p.cadence})",
                        suggested_action=f"Schedule 1:1 with {p.name}",
                        source_id=f"management:1on1:{p.name}",
                    )
                )

        # Overdue coaching check-ins (priority 55)
        for c in snap.coaching:
            if c.overdue:
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=55,
                        priority_label="medium",
                        title=f"Coaching check-in overdue: {c.title}",
                        detail=f"{c.days_overdue} days overdue for {c.person or 'unknown'}",
                        suggested_action=f"Review coaching hypothesis: {c.title}",
                        source_id=f"management:coaching:{c.title}",
                    )
                )

        # Overdue feedback follow-ups (priority 65)
        for f in snap.feedback:
            if f.overdue:
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=65,
                        priority_label="high",
                        title=f"Feedback follow-up overdue: {f.person or f.title}",
                        detail=f"{f.days_overdue} days overdue ({f.category} feedback)",
                        suggested_action=f"Follow up on feedback with {f.person or f.title}",
                        source_id=f"management:feedback:{f.title}",
                    )
                )

        # High cognitive load (priority 60)
        for p in snap.people:
            if p.cognitive_load is not None and p.cognitive_load >= 4:
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=60,
                        priority_label="medium",
                        title=f"High cognitive load: {p.name} ({p.cognitive_load}/5)",
                        detail=f"Team: {p.team}, Role: {p.role}",
                        suggested_action=f"Discuss workload with {p.name}",
                        source_id=f"management:load:{p.name}",
                    )
                )
    except Exception:
        log.warning("Failed to collect management nudges", exc_info=True)


def _collect_team_health_nudges(
    nudges: list[Nudge],
    snap: ManagementSnapshot | None = None,
) -> None:
    """Check team health for falling-behind or treading-water teams."""
    try:
        from cockpit.data.team_health import collect_team_health

        health = collect_team_health(snapshot=snap)
        for team in health.teams:
            if team.larson_state == "falling-behind":
                evidence = (
                    "; ".join(team.larson_evidence) if team.larson_evidence else "multiple signals"
                )
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=75,
                        priority_label="high",
                        title=f"Team {team.name} is falling behind",
                        detail=f"Larson state: falling-behind ({evidence})",
                        suggested_action=f"Review team {team.name} workload and staffing",
                        source_id=f"management:team-health:{team.name}",
                    )
                )
            elif team.larson_state == "treading-water" and team.coaching_active_count == 0:
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=55,
                        priority_label="medium",
                        title=f"Team {team.name} treading water, no coaching",
                        detail="Larson state: treading-water, 0 active coaching experiments",
                        suggested_action=f"Consider coaching experiments for team {team.name}",
                        source_id=f"management:team-health:{team.name}",
                    )
                )
    except Exception:
        log.warning("Failed to collect team health nudges", exc_info=True)


def _collect_career_staleness_nudges(
    nudges: list[Nudge],
    snap: ManagementSnapshot | None = None,
) -> None:
    """Check for stale career conversations and missing growth vectors."""
    try:
        if snap is None:
            from cockpit.data.management import collect_management_state

            snap = collect_management_state()

        now = datetime.now(UTC)
        for p in snap.people:
            # Career conversation stale: > 180 days (priority 50)
            if p.last_career_convo:
                try:
                    last_dt = datetime.strptime(p.last_career_convo, "%Y-%m-%d").replace(tzinfo=UTC)
                    days = (now - last_dt).days
                    if days >= 180:
                        nudges.append(
                            Nudge(
                                category="people",
                                priority_score=50,
                                priority_label="medium",
                                title=f"Career convo stale: {p.name} ({days}d ago)",
                                detail=f"Last career conversation was {days} days ago",
                                suggested_action=f"Schedule career conversation with {p.name}",
                                source_id=f"management:career:{p.name}",
                            )
                        )
                except (ValueError, TypeError):
                    pass

            # No growth vector set (priority 40)
            if not p.growth_vector and p.days_since_1on1 is not None and p.days_since_1on1 > 0:
                nudges.append(
                    Nudge(
                        category="people",
                        priority_score=40,
                        priority_label="medium",
                        title=f"No growth vector: {p.name}",
                        detail="Growth vector not set in person note",
                        suggested_action=f"Discuss and set growth vector for {p.name}",
                        source_id=f"management:growth:{p.name}",
                    )
                )
    except Exception:
        log.warning("Failed to collect career staleness nudges", exc_info=True)


def _collect_okr_nudges(nudges: list[Nudge]) -> None:
    """Add nudges for at-risk and stale OKR key results."""
    try:
        from cockpit.data.okrs import collect_okr_state

        snap = collect_okr_state()
    except Exception:
        log.warning("Failed to collect OKR nudges", exc_info=True)
        return

    for okr in snap.okrs:
        if okr.status != "active":
            continue
        if okr.at_risk_count > 0:
            nudges.append(
                Nudge(
                    category="goals",
                    priority_score=75,
                    priority_label="high",
                    title=f"At-risk KRs: {okr.objective}",
                    detail=f"{okr.at_risk_count} key result(s) with confidence < 0.5",
                    suggested_action="Review progress and adjust approach",
                    source_id=f"okr:{okr.file_path.name}" if okr.file_path else "",
                )
            )
        if okr.stale_kr_count > 0:
            nudges.append(
                Nudge(
                    category="goals",
                    priority_score=50,
                    priority_label="medium",
                    title=f"Stale KRs: {okr.objective}",
                    detail=f"{okr.stale_kr_count} key result(s) not updated in 14+ days",
                    suggested_action="Update progress on key results",
                    source_id=f"okr:{okr.file_path.name}" if okr.file_path else "",
                )
            )


def _collect_smart_goal_nudges(nudges: list[Nudge]) -> None:
    """Add nudges for overdue SMART goals and stale reviews."""
    try:
        from cockpit.data.smart_goals import collect_smart_goal_state

        snap = collect_smart_goal_state()
    except Exception:
        log.warning("Failed to collect SMART goal nudges", exc_info=True)
        return

    for goal in snap.goals:
        if goal.status != "active":
            continue
        if goal.overdue:
            nudges.append(
                Nudge(
                    category="goals",
                    priority_score=70,
                    priority_label="high",
                    title=f"Overdue goal: {goal.person}",
                    detail=f"'{goal.specific}' was due {goal.target_date}",
                    suggested_action="Check in on goal progress",
                    source_id=f"goal:{goal.file_path.name}" if goal.file_path else "",
                )
            )
        if goal.review_overdue:
            nudges.append(
                Nudge(
                    category="goals",
                    priority_score=45,
                    priority_label="medium",
                    title=f"Goal review overdue: {goal.person}",
                    detail=f"'{goal.specific}' — {goal.days_since_review}d since last review",
                    suggested_action=f"Schedule {goal.review_cadence} goal review",
                    source_id=f"goal:{goal.file_path.name}" if goal.file_path else "",
                )
            )


def _collect_incident_nudges(nudges: list[Nudge]) -> None:
    """Add nudges for open incidents and missing postmortems."""
    try:
        from cockpit.data.incidents import collect_incident_state

        snap = collect_incident_state()
    except Exception:
        log.warning("Failed to collect incident nudges", exc_info=True)
        return

    for inc in snap.incidents:
        if inc.open:
            score = 90 if inc.severity == "sev1" else 80
            nudges.append(
                Nudge(
                    category="operational",
                    priority_score=score,
                    priority_label="critical" if inc.severity == "sev1" else "high",
                    title=f"Open incident: {inc.title}",
                    detail=f"{inc.severity.upper()} — status: {inc.status}",
                    suggested_action="Check incident status and next steps",
                    source_id=f"incident:{inc.file_path.name}" if inc.file_path else "",
                )
            )
        elif not inc.has_postmortem and inc.severity in ("sev1", "sev2"):
            nudges.append(
                Nudge(
                    category="operational",
                    priority_score=65,
                    priority_label="high",
                    title=f"Missing postmortem: {inc.title}",
                    detail=f"{inc.severity.upper()} incident without completed postmortem",
                    suggested_action="Schedule postmortem",
                    source_id=f"incident:{inc.file_path.name}" if inc.file_path else "",
                )
            )


def _collect_postmortem_action_nudges(nudges: list[Nudge]) -> None:
    """Add nudges for overdue postmortem actions."""
    try:
        from cockpit.data.postmortem_actions import collect_postmortem_action_state

        snap = collect_postmortem_action_state()
    except Exception:
        log.warning("Failed to collect postmortem action nudges", exc_info=True)
        return

    for action in snap.actions:
        if action.overdue:
            nudges.append(
                Nudge(
                    category="operational",
                    priority_score=70,
                    priority_label="high",
                    title=f"Overdue postmortem action: {action.title}",
                    detail=f"{action.days_overdue}d overdue — owner: {action.owner}",
                    suggested_action="Follow up on action item",
                    source_id=f"pm-action:{action.file_path.name}" if action.file_path else "",
                )
            )


def _collect_review_cycle_nudges(nudges: list[Nudge]) -> None:
    """Add nudges for overdue review cycles and peer feedback gaps."""
    try:
        from cockpit.data.review_cycles import collect_review_cycle_state

        snap = collect_review_cycle_state()
    except Exception:
        log.warning("Failed to collect review cycle nudges", exc_info=True)
        return

    for cycle in snap.cycles:
        if cycle.delivered:
            continue
        if cycle.overdue:
            nudges.append(
                Nudge(
                    category="people",
                    priority_score=75,
                    priority_label="high",
                    title=f"Review overdue: {cycle.person}",
                    detail=f"Cycle {cycle.cycle} review was due {cycle.review_due}",
                    suggested_action="Complete and deliver review",
                    source_id=f"review:{cycle.file_path.name}" if cycle.file_path else "",
                )
            )
        if cycle.peer_feedback_gap > 0:
            nudges.append(
                Nudge(
                    category="people",
                    priority_score=55,
                    priority_label="medium",
                    title=f"Peer feedback needed: {cycle.person}",
                    detail=f"{cycle.peer_feedback_gap} peer feedback response(s) outstanding",
                    suggested_action="Follow up on peer feedback requests",
                    source_id=f"review:{cycle.file_path.name}" if cycle.file_path else "",
                )
            )


def _collect_status_report_nudges(nudges: list[Nudge]) -> None:
    """Add nudge if status report is stale."""
    try:
        from cockpit.data.status_reports import collect_status_report_state

        snap = collect_status_report_state()
    except Exception:
        log.warning("Failed to collect status report nudges", exc_info=True)
        return

    if snap.stale:
        nudges.append(
            Nudge(
                category="operational",
                priority_score=55,
                priority_label="medium",
                title="Status report overdue",
                detail=f"Last report: {snap.latest_date or 'never'}",
                suggested_action="Generate or write status report",
                source_id="status-report:stale",
            )
        )


# ── Category allocation ──────────────────────────────────────────────────────


def _allocate_by_category(nudges: list[Nudge]) -> list[Nudge]:
    """Allocate nudges into category slots with redistribution of unused slots."""
    if not nudges:
        return []

    total_budget = sum(CATEGORY_SLOTS.values())  # 7

    # Group by category, sorted by priority within each
    by_cat: dict[str, list[Nudge]] = {}
    for n in sorted(nudges, key=lambda x: x.priority_score, reverse=True):
        by_cat.setdefault(n.category, []).append(n)

    # First pass: fill each category up to its budget
    selected: list[Nudge] = []
    overflow: list[Nudge] = []
    remaining_budget = 0

    for cat, budget in CATEGORY_SLOTS.items():
        cat_nudges = by_cat.pop(cat, [])
        take = cat_nudges[:budget]
        selected.extend(take)
        overflow.extend(cat_nudges[budget:])
        remaining_budget += budget - len(take)

    # Any nudges in unknown categories go to overflow
    for cat_nudges in by_cat.values():
        overflow.extend(cat_nudges)

    # Second pass: fill remaining budget from overflow by priority
    overflow.sort(key=lambda x: x.priority_score, reverse=True)
    selected.extend(overflow[:remaining_budget])

    # Cap at total budget and sort by priority
    selected = selected[:total_budget]
    selected.sort(key=lambda x: x.priority_score, reverse=True)

    return selected


# ── Main entry point ─────────────────────────────────────────────────────────


def collect_nudges(
    *,
    max_nudges: int = 7,
    snapshot: ManagementSnapshot | None = None,
) -> list[Nudge]:
    """Collect and rank management nudges using category-slotted allocation.

    Fully synchronous. Allocates nudges across category slots (people, goals,
    operational) then caps at max_nudges.

    Args:
        max_nudges: Maximum nudges to return.
        snapshot: Pre-computed management snapshot. If None, each sub-collector
            scans DATA_DIR independently. Pass this to avoid redundant I/O.
    """
    nudges: list[Nudge] = []
    _collect_management_nudges(nudges, snap=snapshot)
    _collect_team_health_nudges(nudges, snap=snapshot)
    _collect_career_staleness_nudges(nudges, snap=snapshot)
    _collect_okr_nudges(nudges)
    _collect_smart_goal_nudges(nudges)
    _collect_incident_nudges(nudges)
    _collect_postmortem_action_nudges(nudges)
    _collect_review_cycle_nudges(nudges)
    _collect_status_report_nudges(nudges)

    result = _allocate_by_category(nudges)

    if len(result) > max_nudges:
        overflow = len(result) - max_nudges
        visible = result[:max_nudges]
        visible.append(
            Nudge(
                category="meta",
                priority_score=0,
                priority_label="low",
                title=f"+ {overflow} more items",
                detail=f"{overflow} lower-priority items not shown",
                suggested_action="",
                source_id="meta:overflow",
            )
        )
        return visible

    return result
