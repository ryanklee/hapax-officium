"""management_activity.py — Management activity tracking.

Computes management practice metrics deterministically: 1:1 completion rates,
feedback delivery timing, coaching experiment check-in frequency, career
conversation recency, and management goal momentum.

Zero LLM calls. All data from logos.data.management.

Usage:
    uv run python -m agents.management_activity                  # Human-readable report
    uv run python -m agents.management_activity --json           # Machine-readable JSON
    uv run python -m agents.management_activity --days 30        # Custom window (default: 30)
"""

from __future__ import annotations

import argparse
import logging
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

log = logging.getLogger("agents.management_activity")


# ── Schemas ──────────────────────────────────────────────────────────────────


class OneOnOneMetrics(BaseModel):
    """1:1 completion rates over rolling windows."""

    total_people: int = 0
    on_track_7d: int = 0
    on_track_30d: int = 0
    stale_count: int = 0
    completion_rate_7d: float = 0.0  # pct of people with recent 1:1
    completion_rate_30d: float = 0.0
    stale_details: list[dict] = Field(default_factory=list)
    # detail: [{name, cadence, days_since, stale}]


class FeedbackTimingMetrics(BaseModel):
    """Feedback delivery timing — days between observation and delivery."""

    total_pending: int = 0
    total_overdue: int = 0
    avg_days_overdue: float = 0.0
    overdue_details: list[dict] = Field(default_factory=list)
    # detail: [{title, person, days_overdue}]


class CoachingMetrics(BaseModel):
    """Coaching experiment check-in frequency."""

    total_active: int = 0
    total_overdue: int = 0
    avg_days_overdue: float = 0.0
    overdue_details: list[dict] = Field(default_factory=list)
    # detail: [{title, person, days_overdue}]


class CareerConversationMetrics(BaseModel):
    """Career conversation recency per team member."""

    total_people: int = 0
    with_career_convo: int = 0
    without_career_convo: int = 0
    coverage_pct: float = 0.0
    details: list[dict] = Field(default_factory=list)
    # detail: [{name, last_career_convo, days_since}]


class GoalMomentum(BaseModel):
    """Management goal momentum tracking."""

    name: str
    status: str = ""
    last_activity_at: str = ""
    days_since_activity: int | None = None
    momentum: str = ""  # active | stalled | dormant | no-tracking


class ManagementActivityReport(BaseModel):
    """Complete management activity report."""

    generated_at: str
    window_days: int
    one_on_ones: OneOnOneMetrics = Field(default_factory=OneOnOneMetrics)
    feedback: FeedbackTimingMetrics = Field(default_factory=FeedbackTimingMetrics)
    coaching: CoachingMetrics = Field(default_factory=CoachingMetrics)
    career_conversations: CareerConversationMetrics = Field(
        default_factory=CareerConversationMetrics
    )
    management_goals: list[GoalMomentum] = Field(default_factory=list)
    team_size: int = 0
    high_load_count: int = 0


# ── Collectors (all deterministic, zero LLM) ────────────────────────────────


def _collect_one_on_ones(people: list, now: datetime, window_days: int) -> OneOnOneMetrics:
    """Compute 1:1 completion rates from person states."""
    metrics = OneOnOneMetrics(total_people=len(people))

    if not people:
        return metrics

    window_7d = now - timedelta(days=7)
    window_30d = now - timedelta(days=window_days)

    for p in people:
        days = p.days_since_1on1
        last_date = p.last_1on1

        detail = {
            "name": p.name,
            "cadence": p.cadence,
            "days_since": days,
            "stale": p.stale_1on1,
        }

        if last_date and days is not None:
            try:
                last_dt = datetime.strptime(last_date, "%Y-%m-%d").replace(tzinfo=UTC)
                if last_dt >= window_7d:
                    metrics.on_track_7d += 1
                if last_dt >= window_30d:
                    metrics.on_track_30d += 1
            except (ValueError, TypeError):
                pass

        if p.stale_1on1:
            metrics.stale_count += 1
            metrics.stale_details.append(detail)

    total = metrics.total_people
    if total > 0:
        metrics.completion_rate_7d = round(100 * metrics.on_track_7d / total, 1)
        metrics.completion_rate_30d = round(100 * metrics.on_track_30d / total, 1)

    return metrics


def _collect_feedback_timing(feedback: list) -> FeedbackTimingMetrics:
    """Compute feedback delivery timing from feedback states."""
    metrics = FeedbackTimingMetrics(total_pending=len(feedback))

    overdue_days: list[int] = []
    for f in feedback:
        if f.overdue:
            metrics.total_overdue += 1
            overdue_days.append(f.days_overdue)
            metrics.overdue_details.append(
                {
                    "title": f.title,
                    "person": f.person,
                    "days_overdue": f.days_overdue,
                }
            )

    if overdue_days:
        metrics.avg_days_overdue = round(sum(overdue_days) / len(overdue_days), 1)

    return metrics


def _collect_coaching_metrics(coaching: list) -> CoachingMetrics:
    """Compute coaching experiment check-in frequency."""
    metrics = CoachingMetrics(total_active=len(coaching))

    overdue_days: list[int] = []
    for c in coaching:
        if c.overdue:
            metrics.total_overdue += 1
            overdue_days.append(c.days_overdue)
            metrics.overdue_details.append(
                {
                    "title": c.title,
                    "person": c.person,
                    "days_overdue": c.days_overdue,
                }
            )

    if overdue_days:
        metrics.avg_days_overdue = round(sum(overdue_days) / len(overdue_days), 1)

    return metrics


def _collect_career_conversations(people: list, now: datetime) -> CareerConversationMetrics:
    """Compute career conversation recency per team member."""
    metrics = CareerConversationMetrics(total_people=len(people))

    for p in people:
        last_convo = p.last_career_convo
        days_since: int | None = None

        if last_convo:
            metrics.with_career_convo += 1
            try:
                convo_dt = datetime.strptime(last_convo, "%Y-%m-%d").replace(tzinfo=UTC)
                days_since = (now - convo_dt).days
            except (ValueError, TypeError):
                pass
        else:
            metrics.without_career_convo += 1

        metrics.details.append(
            {
                "name": p.name,
                "last_career_convo": last_convo or "",
                "days_since": days_since,
            }
        )

    if metrics.total_people > 0:
        metrics.coverage_pct = round(100 * metrics.with_career_convo / metrics.total_people, 1)

    return metrics


def _collect_management_goals(now: datetime) -> list[GoalMomentum]:
    """Collect management goals only, compute momentum."""
    from shared.operator import get_goals

    all_goals = get_goals()
    results: list[GoalMomentum] = []

    for g in all_goals:
        # Filter to management goals only
        tags = g.get("tags", [])
        category = g.get("category", "")
        name = g.get("name", g.get("id", ""))

        is_management = (
            category == "management"
            or "management" in tags
            or "team" in tags
            or "leadership" in tags
            or any(
                kw in name.lower()
                for kw in ("management", "team", "1:1", "coaching", "feedback", "leadership")
            )
        )

        if not is_management:
            continue

        status = g.get("status", "")
        last = g.get("last_activity_at", "")
        days_since: int | None = None
        momentum = "no-tracking"

        if last:
            try:
                last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                days_since = (now - last_dt).days
                if days_since <= 7:
                    momentum = "active"
                elif days_since <= 14:
                    momentum = "stalled"
                else:
                    momentum = "dormant"
            except (ValueError, TypeError):
                pass

        results.append(
            GoalMomentum(
                name=name,
                status=status,
                last_activity_at=last,
                days_since_activity=days_since,
                momentum=momentum,
            )
        )

    return results


# ── Main collector ───────────────────────────────────────────────────────────


def generate_management_report(window_days: int = 30) -> ManagementActivityReport:
    """Collect all management activity metrics.

    Fully deterministic — reads data via logos.data.management,
    computes metrics without any LLM calls.
    """
    from logos.data.management import collect_management_state

    now = datetime.now(UTC)
    snapshot = collect_management_state()

    one_on_ones = _collect_one_on_ones(snapshot.people, now, window_days)
    feedback = _collect_feedback_timing(snapshot.feedback)
    coaching = _collect_coaching_metrics(snapshot.coaching)
    career = _collect_career_conversations(snapshot.people, now)
    goals = _collect_management_goals(now)

    return ManagementActivityReport(
        generated_at=now.isoformat()[:19],
        window_days=window_days,
        one_on_ones=one_on_ones,
        feedback=feedback,
        coaching=coaching,
        career_conversations=career,
        management_goals=goals,
        team_size=snapshot.active_people_count,
        high_load_count=snapshot.high_load_count,
    )


# ── Formatter ────────────────────────────────────────────────────────────────


def format_human(report: ManagementActivityReport) -> str:
    """Format report for human-readable terminal output."""
    lines = [
        f"Management Activity Report ({report.window_days}d window)",
        f"  Generated: {report.generated_at}",
        f"  Team size: {report.team_size} active people"
        + (f" ({report.high_load_count} high cognitive load)" if report.high_load_count else ""),
        "",
    ]

    # 1:1 Completion
    oo = report.one_on_ones
    lines.append("1:1 Completion:")
    lines.append(f"  7d rate:  {oo.completion_rate_7d}% ({oo.on_track_7d}/{oo.total_people})")
    lines.append(
        f"  {report.window_days}d rate: {oo.completion_rate_30d}% ({oo.on_track_30d}/{oo.total_people})"
    )
    if oo.stale_count > 0:
        lines.append(f"  Stale ({oo.stale_count}):")
        for d in sorted(oo.stale_details, key=lambda x: x.get("days_since") or 0, reverse=True):
            days = d.get("days_since")
            days_str = f"{days}d ago" if days is not None else "unknown"
            lines.append(f"    {d['name']} ({d['cadence']}) — last {days_str}")
    else:
        lines.append("  All 1:1s on track")
    lines.append("")

    # Feedback Timing
    fb = report.feedback
    lines.append("Feedback Delivery:")
    lines.append(f"  Pending: {fb.total_pending}  Overdue: {fb.total_overdue}")
    if fb.total_overdue > 0:
        lines.append(f"  Avg overdue: {fb.avg_days_overdue} days")
        for d in sorted(fb.overdue_details, key=lambda x: x["days_overdue"], reverse=True):
            lines.append(f"    {d['person']}: {d['title']} ({d['days_overdue']}d overdue)")
    lines.append("")

    # Coaching Experiments
    co = report.coaching
    lines.append("Coaching Experiments:")
    lines.append(f"  Active: {co.total_active}  Overdue check-ins: {co.total_overdue}")
    if co.total_overdue > 0:
        lines.append(f"  Avg overdue: {co.avg_days_overdue} days")
        for d in sorted(co.overdue_details, key=lambda x: x["days_overdue"], reverse=True):
            lines.append(f"    {d['person']}: {d['title']} ({d['days_overdue']}d overdue)")
    lines.append("")

    # Career Conversations
    cc = report.career_conversations
    lines.append("Career Conversations:")
    lines.append(f"  Coverage: {cc.coverage_pct}% ({cc.with_career_convo}/{cc.total_people})")
    if cc.without_career_convo > 0:
        missing = [d for d in cc.details if not d.get("last_career_convo")]
        if missing:
            lines.append(f"  Missing ({len(missing)}):")
            for d in missing:
                lines.append(f"    {d['name']}")
    lines.append("")

    # Management Goals
    if report.management_goals:
        lines.append("Management Goals:")
        for g in report.management_goals:
            days_str = ""
            if g.days_since_activity is not None:
                days_str = f", {g.days_since_activity}d ago"
            momentum_label = {
                "active": "ACTIVE",
                "stalled": "STALLED",
                "dormant": "DORMANT",
                "no-tracking": "NO TRACKING",
            }.get(g.momentum, g.momentum)
            lines.append(f"  [{momentum_label}{days_str}] {g.name}")
    else:
        lines.append("Management Goals: None found (tag goals with 'management' category)")

    return "\n".join(lines)


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Management activity tracker — management practice metrics",
        prog="python -m agents.management_activity",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--days", type=int, default=30, help="Rolling window in days (default: 30)")
    args = parser.parse_args()

    report = generate_management_report(args.days)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(format_human(report))


if __name__ == "__main__":
    main()
