"""Team health collector — deterministic team-level aggregation.

Groups people by team, computes aggregate health metrics, and classifies
each team using Larson's four-state model (falling-behind, treading-water,
repaying-debt, innovating).

Fully deterministic, no LLM calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from logos.data.management import ManagementSnapshot, PersonState, collect_management_state

_log = logging.getLogger(__name__)


@dataclass
class TeamState:
    """Aggregated state of a single team."""

    name: str
    members: list[PersonState] = field(default_factory=list)
    avg_cognitive_load: float | None = None
    high_load_count: int = 0
    stale_1on1_count: int = 0
    coaching_active_count: int = 0
    size: int = 0
    larson_state: str = ""  # falling-behind | treading-water | repaying-debt | innovating
    larson_evidence: list[str] = field(default_factory=list)
    team_type: str = ""  # majority team-type from members


@dataclass
class TeamHealthSnapshot:
    """Aggregated team health across all teams."""

    teams: list[TeamState] = field(default_factory=list)
    total_people: int = 0
    teams_falling_behind: int = 0
    teams_treading_water: int = 0


def classify_larson_state(team: TeamState) -> tuple[str, list[str]]:
    """Classify a team using Larson's four-state model from proxy signals.

    States (from An Elegant Puzzle):
    - falling-behind: high load or majority stale 1:1s
    - treading-water: moderate load, no active coaching
    - repaying-debt: coaching active, moderate load
    - innovating: low load, coaching active, no stale 1:1s

    Returns:
        Tuple of (state_string, evidence_list). Empty string if insufficient data.
    """
    if team.size == 0:
        return "", []

    evidence: list[str] = []
    has_load_data = team.avg_cognitive_load is not None

    # falling-behind: avg load >= 4 OR > 50% stale 1:1s
    if has_load_data and team.avg_cognitive_load >= 4:  # type: ignore[operator]
        evidence.append(f"avg cognitive load {team.avg_cognitive_load:.1f} >= 4")
        return "falling-behind", evidence

    stale_pct = team.stale_1on1_count / team.size
    if stale_pct > 0.5:
        evidence.append(f"{team.stale_1on1_count}/{team.size} stale 1:1s (>{50}%)")
        return "falling-behind", evidence

    # innovating: low load AND coaching active AND no stale 1:1s
    if (
        has_load_data
        and team.avg_cognitive_load < 3  # type: ignore[operator]
        and team.coaching_active_count > 0
        and team.stale_1on1_count == 0
    ):
        evidence.append(f"avg load {team.avg_cognitive_load:.1f} < 3")
        evidence.append(f"{team.coaching_active_count} active coaching")
        evidence.append("no stale 1:1s")
        return "innovating", evidence

    # repaying-debt: coaching active AND moderate load
    if team.coaching_active_count > 0:
        evidence.append(f"{team.coaching_active_count} active coaching")
        if has_load_data:
            evidence.append(f"avg load {team.avg_cognitive_load:.1f}")
        return "repaying-debt", evidence

    # treading-water: moderate load, no coaching
    if has_load_data:
        evidence.append(f"avg load {team.avg_cognitive_load:.1f}, no active coaching")
        return "treading-water", evidence

    return "", []


def _compute_majority_team_type(members: list[PersonState]) -> str:
    """Return the most common team_type among members, or empty string."""
    from collections import Counter

    types = [m.team_type for m in members if m.team_type]
    if not types:
        return ""
    counter = Counter(types)
    return counter.most_common(1)[0][0]


def collect_team_health(
    snapshot: ManagementSnapshot | None = None,
) -> TeamHealthSnapshot:
    """Collect team health by grouping people by team and classifying.

    Args:
        snapshot: Pre-computed management snapshot. If None, scans DATA_DIR.
            Pass this when the caller already has a fresh snapshot to avoid
            redundant disk I/O.

    Safe with empty vault — returns empty snapshot.
    """
    if snapshot is None:
        try:
            snapshot = collect_management_state()
        except Exception as exc:
            _log.warning("team_health: failed to collect management state: %s", exc)
            return TeamHealthSnapshot()

    if not snapshot.people:
        return TeamHealthSnapshot()

    # Group people by team
    teams_map: dict[str, list[PersonState]] = {}
    for p in snapshot.people:
        team_name = p.team or "unassigned"
        teams_map.setdefault(team_name, []).append(p)

    teams: list[TeamState] = []
    for name, members in sorted(teams_map.items()):
        load_values = [m.cognitive_load for m in members if m.cognitive_load is not None]
        avg_load = sum(load_values) / len(load_values) if load_values else None

        team = TeamState(
            name=name,
            members=members,
            avg_cognitive_load=avg_load,
            high_load_count=sum(1 for v in load_values if v >= 4),
            stale_1on1_count=sum(1 for m in members if m.stale_1on1),
            coaching_active_count=sum(1 for m in members if m.coaching_active),
            size=len(members),
            team_type=_compute_majority_team_type(members),
        )
        state, evidence = classify_larson_state(team)
        team.larson_state = state
        team.larson_evidence = evidence
        teams.append(team)

    return TeamHealthSnapshot(
        teams=teams,
        total_people=len(snapshot.people),
        teams_falling_behind=sum(1 for t in teams if t.larson_state == "falling-behind"),
        teams_treading_water=sum(1 for t in teams if t.larson_state == "treading-water"),
    )
