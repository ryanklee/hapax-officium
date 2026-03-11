"""Tests for the operator profile integration layer.

Uses mock operator data injected into the cache so tests don't depend
on the gitignored profiles/operator.json file.
"""

import copy
import json

import pytest

from shared.operator import (
    get_agent_context,
    get_axioms,
    get_constraints,
    get_goals,
    get_operator,
    get_patterns,
    get_system_prompt_fragment,
    reload_operator,
)

# ── Mock operator data ──────────────────────────────────────────────────────

MOCK_OPERATOR = {
    "version": 1,
    "operator": {
        "name": "Operator",
        "role": "Engineering Manager",
        "context": "Manages a team of engineers building infrastructure services.",
    },
    "axioms": {
        "single_operator": "This system serves a single operator: Operator.",
        "decision_support": "Reduce friction and decision load in all management workflows.",
        "management_safety": "LLMs prepare, humans deliver. Never generate feedback language.",
    },
    "constraints": {
        "python": [
            "Always use uv for package management",
            "Type hints are mandatory on all function signatures",
            "Use Pydantic models for structured data",
            "Never use pip directly",
        ],
        "docker": [
            "Use Docker Compose v2",
            "Always set resource limits",
            "Bind ports to 127.0.0.1",
        ],
        "git": [
            "Use conventional commits",
            "Feature branches from main",
        ],
        "music": [
            "DAWless workflow — no traditional DAW",
            "44.1kHz / 16-bit WAV for SP-404MKII compatibility",
            "ALSA MIDI for routing",
        ],
        "llm": [
            "Route through LiteLLM proxy",
            "All traces to Langfuse",
        ],
        "secrets": [
            "Never hardcode secrets",
            "Use pass + direnv",
        ],
        "communication": [
            "Precise, efficient communication",
            "State epistemic confidence",
        ],
        "agents": [
            "Stateless per-invocation",
            "Persistent state in Qdrant or profiles/",
        ],
    },
    "patterns": {
        "decision_making": [
            "Prefers data-driven decisions",
            "Evaluates tradeoffs explicitly",
            "Uses pipeline approach for complex workflows",
        ],
        "workflow": [
            "Morning focus blocks for deep work",
            "Batch similar tasks together",
            "Pipeline-oriented development",
        ],
        "development": [
            "Iterative pipeline approach",
            "Test-driven for critical paths",
            "Prefers composition over inheritance",
        ],
        "communication": [
            "Direct and concise",
            "Asks clarifying questions early",
            "Documents decisions inline",
        ],
    },
    "goals": {
        "primary": [
            {
                "id": "llm-first-environment",
                "description": "LLM-first development environment",
                "domain": "management",
            },
            {
                "id": "agent-coverage",
                "description": "Full agent coverage for management workflows",
                "domain": "management",
            },
            {
                "id": "decision-quality",
                "description": "Improve decision quality through data",
                "domain": "management",
            },
        ],
        "secondary": [
            {
                "id": "music-production",
                "description": "DAWless music production workflow",
                "domain": "personal",
            },
        ],
    },
    "agent_context_map": {
        "research": {
            "inject": ["patterns.communication", "patterns.decision_making"],
            "domain_knowledge": "Knowledge base access via Qdrant vector search.",
        },
        "code-review": {
            "inject": ["constraints.python", "constraints.docker", "constraints.git"],
            "domain_knowledge": "Pydantic AI for agent framework. LiteLLM for model routing.",
        },
    },
    "neurocognitive": {},
}


@pytest.fixture(autouse=True)
def _inject_mock_operator(monkeypatch):
    """Inject mock operator data into the cache for all tests in this module."""
    import shared.operator as op_mod

    monkeypatch.setattr(op_mod, "_operator_cache", copy.deepcopy(MOCK_OPERATOR))
    yield
    monkeypatch.setattr(op_mod, "_operator_cache", None)


# ── Basic loading ───────────────────────────────────────────────────────────


def test_operator_loads():
    data = get_operator()
    assert data.get("version") == 1
    assert data["operator"]["name"] == "Operator"


def test_constraints_all():
    rules = get_constraints()
    assert len(rules) >= 20  # Across all categories


def test_constraints_by_category():
    python_rules = get_constraints("python")
    assert any("uv" in r for r in python_rules)
    assert any("type hints" in r.lower() for r in python_rules)


def test_constraints_music():
    rules = get_constraints("music")
    assert any("DAW" in r for r in rules)
    assert any("44.1kHz" in r for r in rules)


def test_patterns_all():
    patterns = get_patterns()
    assert len(patterns) > 10


def test_patterns_by_category():
    dev = get_patterns("development")
    assert any("pipeline" in p.lower() for p in dev)


def test_goals():
    goals = get_goals()
    assert len(goals) >= 3
    ids = [g["id"] for g in goals]
    assert "llm-first-environment" in ids
    assert "agent-coverage" in ids


def test_agent_context_research():
    ctx = get_agent_context("research")
    assert "inject" in ctx
    assert "domain_knowledge" in ctx
    assert "knowledge base" in ctx["domain_knowledge"].lower()


def test_agent_context_code_review():
    ctx = get_agent_context("code-review")
    assert "constraints.python" in ctx["inject"]


def test_agent_context_missing():
    ctx = get_agent_context("nonexistent-agent")
    assert ctx == {}


def test_axioms():
    axioms = get_axioms()
    assert "single_operator" in axioms
    assert "decision_support" in axioms
    assert "management_safety" in axioms
    assert "Operator" in axioms["single_operator"]


# ── System prompt fragment tests ────────────────────────────────────────────


def test_system_prompt_fragment_includes_single_operator_axiom():
    fragment = get_system_prompt_fragment("research")
    # Registry axioms take precedence if available; otherwise fall back to operator.json axioms
    assert "single" in fragment.lower()
    assert "Operator" in fragment


def test_system_prompt_fragment_research():
    """Research agent gets identity + axioms but NOT constraints/patterns via old injection."""
    fragment = get_system_prompt_fragment("research")
    assert "Operator" in fragment
    assert "Rules:" not in fragment
    assert len(fragment) > 100


def test_system_prompt_fragment_code_review():
    """Code review agent gets identity but constraints come from context map, not old injection."""
    fragment = get_system_prompt_fragment("code-review")
    assert "Operator" in fragment
    assert "Rules:" not in fragment


def test_system_prompt_fragment_missing():
    """Unknown agent still gets system context and operator identity."""
    fragment = get_system_prompt_fragment("nonexistent")
    assert "Operator" in fragment


def test_system_prompt_fragment_no_constraints_for_unmapped_agent():
    """Agents WITHOUT agent_context_map entries get no constraints injected."""
    fragment = get_system_prompt_fragment("nonexistent-agent-xyz")
    assert "Relevant constraints:" not in fragment
    assert "Relevant behavioral patterns:" not in fragment


def test_neurocognitive_profile_empty():
    from shared.operator import get_neurocognitive_profile

    result = get_neurocognitive_profile()
    assert isinstance(result, dict)


def test_system_prompt_fragment_no_neurocognitive_when_empty(monkeypatch):
    """Empty neurocognitive dict means no 'Neurocognitive patterns' in fragment."""
    fragment = get_system_prompt_fragment("research")
    assert "Neurocognitive patterns" not in fragment


def test_system_prompt_fragment_ignores_neurocognitive_in_management_mode(monkeypatch):
    """Neurocognitive data is deprecated in management mode — not rendered in prompts.

    Neurocognitive accommodations are now baked into the decision_support axiom
    rather than profiled separately.
    """
    import shared.operator as op_mod

    patched = copy.deepcopy(MOCK_OPERATOR)
    patched["neurocognitive"] = {
        "task_initiation": ["Body doubling effective", "Timers help start"],
        "energy_cycles": ["Morning focus peak"],
    }
    monkeypatch.setattr(op_mod, "_operator_cache", patched)
    fragment = get_system_prompt_fragment("research")
    # Neurocognitive section is no longer rendered — it's deprecated
    assert "Neurocognitive patterns" not in fragment


# ── Agent context map injection tests ────────────────────────────────────────


def test_system_prompt_includes_constraints_for_mapped_agent():
    """Agents with agent_context_map entries get their mapped constraints."""
    fragment = get_system_prompt_fragment("code-review")
    assert "Relevant constraints:" in fragment
    assert "uv" in fragment.lower()


def test_system_prompt_includes_patterns_for_mapped_agent():
    """Agents with agent_context_map entries get their mapped patterns."""
    fragment = get_system_prompt_fragment("research")
    assert "Relevant behavioral patterns:" in fragment


def test_system_prompt_includes_domain_knowledge():
    """Agents with domain_knowledge in their context map get it injected."""
    fragment = get_system_prompt_fragment("code-review")
    assert "Domain context:" in fragment
    assert "Pydantic AI" in fragment


def test_system_prompt_no_context_map_for_unknown():
    """Unknown agents don't get constraints/patterns but still get base context."""
    fragment = get_system_prompt_fragment("nonexistent-agent")
    assert "Relevant constraints:" not in fragment
    assert "Relevant behavioral patterns:" not in fragment
    assert "Domain context:" not in fragment
    assert "Operator" in fragment


def test_system_prompt_has_constraints_without_neurocognitive(monkeypatch):
    """Mapped agent gets constraints; neurocognitive is deprecated and not rendered."""
    import shared.operator as op_mod

    patched = copy.deepcopy(MOCK_OPERATOR)
    patched["neurocognitive"] = {"attention": ["Focus windows 90 min"]}
    monkeypatch.setattr(op_mod, "_operator_cache", patched)
    fragment = get_system_prompt_fragment("code-review")
    assert "Relevant constraints:" in fragment
    # Neurocognitive is deprecated — not rendered
    assert "Neurocognitive patterns" not in fragment


# ── Schema validation tests ─────────────────────────────────────────────────


def test_operator_schema_valid():
    from shared.operator import OperatorSchema

    data = {"version": 1, "operator": {"name": "Test"}}
    schema = OperatorSchema.model_validate(data)
    assert schema.version == 1


def test_operator_schema_extra_fields_allowed():
    from shared.operator import OperatorSchema

    data = {"version": 1, "operator": {}, "custom_field": "allowed"}
    schema = OperatorSchema.model_validate(data)
    assert schema.version == 1


def test_operator_schema_wrong_type_rejects():
    from pydantic import ValidationError

    from shared.operator import OperatorSchema

    with pytest.raises(ValidationError):
        OperatorSchema.model_validate({"operator": "not-a-dict"})


def test_load_operator_corrupt_json(tmp_path, monkeypatch):
    import shared.operator as op_mod

    monkeypatch.setattr(op_mod, "_operator_cache", None)
    corrupt = tmp_path / "operator.json"
    corrupt.write_text("{invalid json!")
    monkeypatch.setattr(op_mod, "PROFILES_DIR", tmp_path)
    result = op_mod._load_operator()
    assert result == {}
    monkeypatch.setattr(op_mod, "_operator_cache", None)


def test_load_operator_invalid_schema(tmp_path, monkeypatch):
    import shared.operator as op_mod

    monkeypatch.setattr(op_mod, "_operator_cache", None)
    bad = tmp_path / "operator.json"
    bad.write_text(json.dumps({"operator": "not-a-dict"}))
    monkeypatch.setattr(op_mod, "PROFILES_DIR", tmp_path)
    result = op_mod._load_operator()
    assert result == {}
    monkeypatch.setattr(op_mod, "_operator_cache", None)


def test_reload_operator_clears_cache(tmp_path, monkeypatch):
    """reload_operator() clears cache so next access re-reads from disk."""
    import shared.operator as op_mod

    # Write mock operator.json to tmp_path so reload can re-read it
    operator_file = tmp_path / "operator.json"
    operator_file.write_text(json.dumps(MOCK_OPERATOR))
    monkeypatch.setattr(op_mod, "PROFILES_DIR", tmp_path)

    # Load once to populate cache
    get_operator()
    assert op_mod._operator_cache is not None
    # Inject fake data into cache
    monkeypatch.setattr(op_mod, "_operator_cache", {"fake": True})
    assert get_operator() == {"fake": True}
    # Reload clears cache
    reload_operator()
    assert op_mod._operator_cache is None
    # Next access re-reads from disk
    data = get_operator()
    assert data.get("version") == 1
    assert "fake" not in data
