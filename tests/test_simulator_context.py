# ai-agents/tests/test_simulator_context.py
"""Tests for simulator context assembly."""

from __future__ import annotations

from pathlib import Path

from agents.simulator_pipeline.context import (
    build_tick_prompt,
    compose_role_profile,
    infer_role,
    load_org_dossier,
    load_role_matrix,
    load_scenarios,
    load_workflow_semantics,
    validate_distribution,
)
from agents.simulator_pipeline.models import SimulatedEvent

_FIXTURES = Path(__file__).resolve().parent.parent
_WORKFLOW_SEMANTICS = _FIXTURES / "docs" / "workflow-semantics.yaml"
_ROLE_MATRIX = _FIXTURES / "config" / "role-matrix.yaml"
_SCENARIOS = _FIXTURES / "config" / "scenarios.yaml"
_ORG_DOSSIER = _FIXTURES / "config" / "org-dossier.yaml"


class TestLoadConfig:
    def test_load_workflow_semantics(self):
        """Loads workflow-semantics.yaml."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        assert "one_on_one" in workflows
        assert "coaching_note" in workflows
        assert workflows["one_on_one"]["subdirectory"] == "meetings/"

    def test_load_role_matrix(self):
        """Loads role-matrix.yaml."""
        roles = load_role_matrix(_ROLE_MATRIX)
        assert "engineering-manager" in roles
        em = roles["engineering-manager"]
        assert "experienced-em" in em["variants"]
        assert "one_on_one" in em["workflows"]

    def test_load_scenarios(self):
        """Loads scenarios.yaml."""
        scenarios = load_scenarios(_SCENARIOS)
        assert "pre-quarterly" in scenarios
        assert scenarios["pre-quarterly"]["probability_overrides"]["okr_update"] == 3.0


class TestComposeRoleProfile:
    def test_compose_experienced_em(self):
        """Compose profile for experienced EM — baseline cadences."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
        )
        assert profile["role"] == "engineering-manager"
        assert profile["variant"] == "experienced-em"
        assert "workflows" in profile
        assert len(profile["workflows"]) == 10

    def test_compose_new_em_applies_modifiers(self):
        """New EM variant applies cadence modifiers."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="new-em",
            roles=roles,
            workflows=workflows,
        )
        assert profile["cadence_modifiers"]["one_on_one"] == 1.5
        assert profile["cadence_modifiers"]["decision"] == 0.3

    def test_compose_with_scenario(self):
        """Scenario overrides are merged into profile."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        scenarios = load_scenarios(_SCENARIOS)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
            scenario=scenarios.get("pre-quarterly"),
        )
        assert profile["scenario_overrides"]["okr_update"] == 3.0


class TestBuildTickPrompt:
    def test_prompt_contains_essentials(self):
        """Tick prompt includes date, role, existing state summary, workflows."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
        )

        prompt = build_tick_prompt(
            profile=profile,
            current_date="2026-03-05",
            existing_state_summary="7 active people, 3 teams, 2 stale 1:1s",
            recent_events=["2026-03-04: 1:1 with Alice", "2026-03-03: coaching note for Bob"],
        )
        assert "2026-03-05" in prompt
        assert "engineering-manager" in prompt
        assert "7 active people" in prompt
        assert "1:1 with Alice" in prompt
        assert "SAFETY" in prompt

    def test_prompt_includes_scenario(self):
        """Tick prompt includes scenario context when present."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        scenarios = load_scenarios(_SCENARIOS)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
            scenario=scenarios["pre-quarterly"],
        )

        prompt = build_tick_prompt(
            profile=profile,
            current_date="2026-03-05",
            existing_state_summary="state",
        )
        assert "quarterly" in prompt.lower()

    def test_prompt_includes_org_context(self):
        """Tick prompt includes org context when present in profile."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
            org=org,
        )

        prompt = build_tick_prompt(
            profile=profile,
            current_date="2026-03-05",
            existing_state_summary="state",
        )
        assert "growth" in prompt.lower()
        assert "SOC2" in prompt

    def test_prompt_uses_effective_weight(self):
        """Tick prompt shows effective_weight, not raw modifiers."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)
        org["company_stage"] = "startup"

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="senior-em",
            roles=roles,
            workflows=workflows,
            org=org,
        )

        prompt = build_tick_prompt(
            profile=profile,
            current_date="2026-03-05",
            existing_state_summary="state",
        )
        decision_line = [l for l in prompt.split("\n") if "decision:" in l.lower()][0]
        assert "1.5x" not in decision_line  # NOT the raw role modifier


class TestLoadOrgDossier:
    def test_load_org_dossier(self):
        """Loads org-dossier.yaml and returns org dict."""
        org = load_org_dossier(_ORG_DOSSIER)
        assert org["company_stage"] == "growth"
        assert "startup" in org["stage_modifiers"]
        assert "enterprise" in org["stage_modifiers"]

    def test_org_dossier_has_strategic_context(self):
        """Org dossier includes strategic context list."""
        org = load_org_dossier(_ORG_DOSSIER)
        assert isinstance(org["strategic_context"], list)
        assert len(org["strategic_context"]) > 0


class TestInferRole:
    def test_explicit_role_overrides_hints(self):
        """Explicit --role always wins."""
        assert infer_role("show me a VP demo", explicit_role="tech-lead") == "tech-lead"

    def test_infers_tech_lead(self):
        """Recognizes tech lead keywords."""
        assert infer_role("demo for a tech lead") == "tech-lead"
        assert infer_role("show me the architect view") == "tech-lead"
        assert infer_role("staff engineer perspective") == "tech-lead"

    def test_infers_vp(self):
        """Recognizes VP/director keywords."""
        assert infer_role("demo for the VP of engineering") == "vp-engineering"
        assert infer_role("show my director") == "vp-engineering"
        assert infer_role("head of engineering review") == "vp-engineering"

    def test_infers_em(self):
        """Recognizes engineering manager keywords."""
        assert infer_role("engineering manager cockpit") == "engineering-manager"

    def test_defaults_to_em(self):
        """Falls back to engineering-manager when no hints match."""
        assert infer_role("show me the system") == "engineering-manager"

    def test_longest_match_wins(self):
        """'engineering director' matches vp-engineering, not engineering-manager."""
        assert infer_role("engineering director overview") == "vp-engineering"

    def test_case_insensitive(self):
        """Matching is case-insensitive."""
        assert infer_role("TECH LEAD demo") == "tech-lead"
        assert infer_role("VP of Engineering") == "vp-engineering"


class TestThreeLayerComposition:
    def test_org_stage_modifiers_applied(self):
        """Org stage modifiers are multiplied into effective weight."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)
        org["company_stage"] = "startup"

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
            org=org,
        )
        decision_wf = next(w for w in profile["workflows"] if w["name"] == "decision")
        assert decision_wf["effective_weight"] == 1.5

    def test_three_layer_multiplication(self):
        """role x scenario x org all multiply together."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        scenarios = load_scenarios(_SCENARIOS)
        org = load_org_dossier(_ORG_DOSSIER)
        org["company_stage"] = "startup"

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="senior-em",
            roles=roles,
            workflows=workflows,
            scenario=scenarios["pre-quarterly"],
            org=org,
        )
        decision_wf = next(w for w in profile["workflows"] if w["name"] == "decision")
        assert abs(decision_wf["effective_weight"] - 2.25) < 0.01

    def test_clamping_at_ceiling(self):
        """Effective weight is clamped at 5.0."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)
        org["company_stage"] = "startup"
        org["stage_modifiers"]["startup"]["status_report"] = 10.0

        profile = compose_role_profile(
            role_name="vp-engineering",
            variant="baseline",
            roles=roles,
            workflows=workflows,
            org=org,
        )
        status_wf = next(w for w in profile["workflows"] if w["name"] == "status_report")
        assert status_wf["effective_weight"] == 5.0

    def test_clamping_at_floor(self):
        """Effective weight is clamped at 0.1."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)
        org["company_stage"] = "startup"
        org["stage_modifiers"]["startup"]["coaching_note"] = 0.01

        profile = compose_role_profile(
            role_name="vp-engineering",
            variant="baseline",
            roles=roles,
            workflows=workflows,
            org=org,
        )
        coaching_wf = next(w for w in profile["workflows"] if w["name"] == "coaching_note")
        assert coaching_wf["effective_weight"] == 0.1

    def test_no_org_uses_baseline(self):
        """When org is None, effective_weight equals role modifier only."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="new-em",
            roles=roles,
            workflows=workflows,
        )
        one_on_one_wf = next(w for w in profile["workflows"] if w["name"] == "one_on_one")
        assert one_on_one_wf["effective_weight"] == 1.5

    def test_org_context_in_profile(self):
        """Org context (stage, headcount, strategic_context) is stored in profile."""
        workflows = load_workflow_semantics(_WORKFLOW_SEMANTICS)
        roles = load_role_matrix(_ROLE_MATRIX)
        org = load_org_dossier(_ORG_DOSSIER)

        profile = compose_role_profile(
            role_name="engineering-manager",
            variant="experienced-em",
            roles=roles,
            workflows=workflows,
            org=org,
        )
        assert profile["org_context"]["company_stage"] == "growth"
        assert "strategic_context" in profile["org_context"]


class TestValidateDistribution:
    def _make_event(self, workflow_type: str) -> SimulatedEvent:
        return SimulatedEvent(
            date="2026-03-01",
            workflow_type=workflow_type,
            subdirectory="test/",
            filename="test.md",
        )

    def test_within_range_no_warnings(self):
        """Events within reference range produce no warnings."""
        events = [self._make_event("decision")] * 5
        reference = {"decision": [3, 8]}
        warnings = validate_distribution(events, reference, window_days=30)
        assert warnings == []

    def test_below_range_produces_warning(self):
        """Too few events of a type produces a warning."""
        events = [self._make_event("decision")] * 1
        reference = {"decision": [3, 8]}
        warnings = validate_distribution(events, reference, window_days=30)
        assert len(warnings) == 1
        assert "decision" in warnings[0]

    def test_above_range_produces_warning(self):
        """Too many events of a type produces a warning."""
        events = [self._make_event("decision")] * 15
        reference = {"decision": [3, 8]}
        warnings = validate_distribution(events, reference, window_days=30)
        assert len(warnings) == 1
        assert "decision" in warnings[0]

    def test_scales_with_window(self):
        """Reference ranges scale proportionally with simulation window."""
        events = [self._make_event("decision")] * 10
        reference = {"decision": [3, 8]}
        warnings = validate_distribution(events, reference, window_days=60)
        assert warnings == []

    def test_missing_type_below_minimum(self):
        """A type with 0 events but minimum > 0 produces a warning."""
        events: list[SimulatedEvent] = []
        reference = {"one_on_one": [6, 16]}
        warnings = validate_distribution(events, reference, window_days=30)
        assert len(warnings) == 1
        assert "one_on_one" in warnings[0]

    def test_missing_type_with_zero_minimum(self):
        """A type with 0 events and minimum 0 produces no warning."""
        events: list[SimulatedEvent] = []
        reference = {"incident": [0, 2]}
        warnings = validate_distribution(events, reference, window_days=30)
        assert warnings == []
