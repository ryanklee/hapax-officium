"""Context assembly for the temporal simulator.

Loads workflow semantics, role matrix, and scenarios; composes them into
a role profile and builds per-tick prompts for LLM event generation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)


def load_workflow_semantics(path: Path) -> dict[str, Any]:
    """Load workflow-semantics.yaml. Returns the workflows dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["workflows"]


def load_role_matrix(path: Path) -> dict[str, Any]:
    """Load role-matrix.yaml. Returns the roles dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["roles"]


def load_scenarios(path: Path) -> dict[str, Any]:
    """Load scenarios.yaml. Returns the scenarios dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["scenarios"]


def load_org_dossier(path: Path) -> dict[str, Any]:
    """Load org-dossier.yaml. Returns the org dict."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data["org"]


ROLE_HINTS: dict[str, str] = {
    "tech lead": "tech-lead",
    "technical lead": "tech-lead",
    "architect": "tech-lead",
    "principal": "tech-lead",
    "staff engineer": "tech-lead",
    "vice president": "vp-engineering",
    "head of engineering": "vp-engineering",
    "engineering director": "vp-engineering",
    "director": "vp-engineering",
    "vp": "vp-engineering",
    "engineering manager": "engineering-manager",
    "manager": "engineering-manager",
}


def infer_role(request: str, explicit_role: str | None = None) -> str:
    """Infer role from natural language request, or use explicit override."""
    if explicit_role:
        return explicit_role
    request_lower = request.lower()
    for hint in sorted(ROLE_HINTS, key=len, reverse=True):
        if hint in request_lower:
            return ROLE_HINTS[hint]
    return "engineering-manager"


MODIFIER_FLOOR = 0.1
MODIFIER_CEILING = 5.0


def compose_role_profile(
    *,
    role_name: str,
    variant: str,
    roles: dict[str, Any],
    workflows: dict[str, Any],
    scenario: dict[str, Any] | None = None,
    org: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose a role profile from role matrix + variant + scenario + org dossier.

    Three-layer modifier composition:
      effective = role_variant x scenario x org_stage
    Clamped to [MODIFIER_FLOOR, MODIFIER_CEILING].
    """
    if role_name not in roles:
        valid = ", ".join(sorted(roles.keys()))
        raise ValueError(f"Unknown role '{role_name}'. Valid roles: {valid}")
    role = roles[role_name]
    variant_def = role["variants"].get(variant, {})
    cadence_modifiers = variant_def.get("cadence_modifiers", {})
    scenario_overrides: dict[str, float] = {}

    if scenario:
        scenario_overrides = scenario.get("probability_overrides", {})

    org_stage_modifiers: dict[str, float] = {}
    if org:
        stage = org.get("company_stage", "growth")
        all_stage_mods = org.get("stage_modifiers", {})
        org_stage_modifiers = all_stage_mods.get(stage, {}) or {}

    workflow_details = []
    for wf_name in role["workflows"]:
        if wf_name in workflows:
            wf_entry = {"name": wf_name, **workflows[wf_name]}

            role_mod = cadence_modifiers.get(wf_name, 1.0)
            scenario_mod = scenario_overrides.get(wf_name, 1.0)
            org_mod = org_stage_modifiers.get(wf_name, 1.0)

            raw = role_mod * scenario_mod * org_mod
            effective = max(MODIFIER_FLOOR, min(MODIFIER_CEILING, raw))

            if effective != raw:
                _log.warning(
                    "Clamped %s modifier: %.2f -> %.2f (role=%.1f, scenario=%.1f, org=%.1f)",
                    wf_name,
                    raw,
                    effective,
                    role_mod,
                    scenario_mod,
                    org_mod,
                )

            wf_entry["effective_weight"] = effective
            workflow_details.append(wf_entry)

    profile: dict[str, Any] = {
        "role": role_name,
        "variant": variant,
        "description": role.get("description", ""),
        "variant_description": variant_def.get("description", ""),
        "workflows": workflow_details,
        "cadence_modifiers": cadence_modifiers,
        "scenario_overrides": scenario_overrides,
    }

    if scenario:
        profile["scenario_description"] = scenario.get("description", "")

    if org:
        profile["org_context"] = {
            "company_stage": org.get("company_stage", "growth"),
            "headcount_band": org.get("headcount_band"),
            "team_count": org.get("team_count"),
            "industry": org.get("industry"),
            "strategic_context": org.get("strategic_context", []),
        }

    return profile


def build_tick_prompt(
    *,
    profile: dict[str, Any],
    current_date: str,
    existing_state_summary: str,
    recent_events: list[str] | None = None,
) -> str:
    """Build the per-tick prompt for LLM event generation.

    Includes: role context, current date, existing DATA_DIR state,
    recent events for continuity, and workflow semantics.
    """
    lines = [
        f"You are simulating a {profile['role']} ({profile['variant']}).",
        f"Variant: {profile['variant_description']}",
        "",
        f"Today's date: {current_date}",
        "",
        "Current state of the management data:",
        existing_state_summary,
        "",
    ]

    if recent_events:
        lines.append("Recent events (for continuity):")
        for event in recent_events[-5:]:
            lines.append(f"  - {event}")
        lines.append("")

    lines.append("Available workflows and their semantics:")
    for wf in profile["workflows"]:
        effective = wf.get("effective_weight", 1.0)
        cadence = wf.get("cadence", "event-driven")
        lines.append(
            f"  - {wf['name']}: {wf.get('description', '')} "
            f"(cadence: {cadence}, weight: {effective:.1f}x)"
        )
    lines.append("")

    if profile.get("scenario_description"):
        lines.append(f"Scenario context: {profile['scenario_description']}")
        lines.append("")

    if profile.get("org_context"):
        org_ctx = profile["org_context"]
        lines.append(
            f"Organization: {org_ctx.get('company_stage', 'growth')} stage, "
            f"{org_ctx.get('headcount_band', 'unknown')} employees, "
            f"{org_ctx.get('industry', 'technology')}"
        )
        for priority in org_ctx.get("strategic_context", []):
            lines.append(f"  Strategic priority: {priority}")
        lines.append("")

    lines.extend(
        [
            "Generate 0-3 plausible events for today. Consider:",
            "- What would this role naturally do on this day?",
            "- Respect cadences (don't do daily what should be weekly)",
            "- Some days have no events — that's normal",
            "- Incidents and decisions are stochastic (rare, random)",
            "- Follow trigger chains (incident -> postmortem_action)",
            "",
            "SAFETY: Never generate evaluative language about team members.",
            "Coaching and feedback events must contain ONLY structural content:",
            "date, participant, topics discussed, and action items.",
        ]
    )

    return "\n".join(lines)


def validate_distribution(
    events: list[Any],
    reference: dict[str, list[int]],
    window_days: int,
) -> list[str]:
    """Compare actual event counts against reference ranges.

    Reference ranges are per 30 days and scale proportionally with window_days.
    Returns a list of warning strings for out-of-range workflow types.
    """
    scale = window_days / 30.0
    counts: dict[str, int] = {}
    for e in events:
        counts[e.workflow_type] = counts.get(e.workflow_type, 0) + 1

    warnings: list[str] = []
    for wf_type, (lo, hi) in reference.items():
        actual = counts.get(wf_type, 0)
        scaled_lo = int(lo * scale)
        scaled_hi = int(hi * scale + 0.5)
        if actual < scaled_lo or actual > scaled_hi:
            warnings.append(
                f"{wf_type}: {actual} events in {window_days}d (expected {scaled_lo}-{scaled_hi})"
            )
    return warnings
