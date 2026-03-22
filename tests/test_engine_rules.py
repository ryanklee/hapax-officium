"""Tests for logos.engine.rules — Rule, RuleRegistry, evaluate_rules."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

from logos.engine.models import Action, ActionPlan, ChangeEvent
from logos.engine.rules import Rule, RuleRegistry, evaluate_rules


def _make_event(
    subdirectory: str = "people",
    event_type: str = "modified",
    doc_type: str | None = "person",
) -> ChangeEvent:
    return ChangeEvent(
        path=Path("data/people/alice.md"),
        subdirectory=subdirectory,
        event_type=event_type,
        doc_type=doc_type,
        timestamp=datetime(2026, 3, 9, 12, 0),
    )


def _make_action(name: str = "refresh_prep", priority: int = 0) -> Action:
    return Action(name=name, handler=AsyncMock(), priority=priority)


# --- Rule dataclass ---


def test_rule_trigger_filter_match():
    rule = Rule(
        name="people_rule",
        trigger_filter=lambda e: e.subdirectory == "people",
        produce=lambda e: [_make_action()],
    )
    assert rule.trigger_filter(_make_event(subdirectory="people")) is True


def test_rule_trigger_filter_no_match():
    rule = Rule(
        name="meetings_rule",
        trigger_filter=lambda e: e.subdirectory == "meetings",
        produce=lambda e: [_make_action()],
    )
    assert rule.trigger_filter(_make_event(subdirectory="people")) is False


def test_rule_default_description():
    rule = Rule(
        name="r",
        trigger_filter=lambda e: True,
        produce=lambda e: [],
    )
    assert rule.description == ""


def test_rule_custom_description():
    rule = Rule(
        name="r",
        trigger_filter=lambda e: True,
        produce=lambda e: [],
        description="A custom rule",
    )
    assert rule.description == "A custom rule"


# --- RuleRegistry ---


def test_registry_register_and_list():
    reg = RuleRegistry()
    r1 = Rule(name="a", trigger_filter=lambda e: True, produce=lambda e: [])
    r2 = Rule(name="b", trigger_filter=lambda e: True, produce=lambda e: [])
    reg.register(r1)
    reg.register(r2)
    assert len(reg.rules) == 2
    assert reg.rules[0].name == "a"
    assert reg.rules[1].name == "b"


def test_registry_replace_duplicate_name():
    reg = RuleRegistry()
    r1 = Rule(
        name="dup",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("first")],
        description="first",
    )
    r2 = Rule(
        name="dup",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("second")],
        description="second",
    )
    reg.register(r1)
    reg.register(r2)
    assert len(reg.rules) == 1
    assert reg.rules[0].description == "second"


def test_registry_empty():
    reg = RuleRegistry()
    assert reg.rules == []


# --- evaluate_rules ---


def test_evaluate_rules_collects_matching_only():
    event = _make_event(subdirectory="people")
    match_rule = Rule(
        name="match",
        trigger_filter=lambda e: e.subdirectory == "people",
        produce=lambda e: [_make_action("action_a")],
    )
    no_match_rule = Rule(
        name="no_match",
        trigger_filter=lambda e: e.subdirectory == "meetings",
        produce=lambda e: [_make_action("action_b")],
    )
    reg = RuleRegistry()
    reg.register(match_rule)
    reg.register(no_match_rule)

    plan = evaluate_rules(reg, event)
    assert isinstance(plan, ActionPlan)
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "action_a"


def test_evaluate_rules_deduplicates_by_name():
    event = _make_event()
    r1 = Rule(
        name="rule1",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("shared_action", priority=10)],
    )
    r2 = Rule(
        name="rule2",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("shared_action", priority=99)],
    )
    reg = RuleRegistry()
    reg.register(r1)
    reg.register(r2)

    plan = evaluate_rules(reg, event)
    assert len(plan.actions) == 1
    # First one wins
    assert plan.actions[0].priority == 10


def test_evaluate_rules_empty_when_no_match():
    event = _make_event(subdirectory="people")
    rule = Rule(
        name="meetings_only",
        trigger_filter=lambda e: e.subdirectory == "meetings",
        produce=lambda e: [_make_action()],
    )
    reg = RuleRegistry()
    reg.register(rule)

    plan = evaluate_rules(reg, event)
    assert plan.actions == []
    assert plan.trigger is event


def test_evaluate_rules_empty_registry():
    event = _make_event()
    reg = RuleRegistry()
    plan = evaluate_rules(reg, event)
    assert plan.actions == []


def test_evaluate_rules_catches_produce_exception(caplog):
    event = _make_event()

    def bad_produce(e: ChangeEvent) -> list[Action]:
        raise ValueError("boom")

    rule = Rule(name="bad", trigger_filter=lambda e: True, produce=bad_produce)
    good_rule = Rule(
        name="good",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("good_action")],
    )
    reg = RuleRegistry()
    reg.register(rule)
    reg.register(good_rule)

    plan = evaluate_rules(reg, event)
    # Good rule's action still collected
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "good_action"
    # Error was logged
    assert "bad" in caplog.text
    assert "boom" in caplog.text


def test_evaluate_rules_catches_trigger_filter_exception(caplog):
    """A broken trigger_filter should not prevent other rules from evaluating."""
    event = _make_event()

    def bad_filter(e: ChangeEvent) -> bool:
        raise RuntimeError("filter exploded")

    bad_rule = Rule(
        name="bad_filter",
        trigger_filter=bad_filter,
        produce=lambda e: [_make_action("should_not_appear")],
    )
    good_rule = Rule(
        name="good",
        trigger_filter=lambda e: True,
        produce=lambda e: [_make_action("good_action")],
    )
    reg = RuleRegistry()
    reg.register(bad_rule)
    reg.register(good_rule)

    plan = evaluate_rules(reg, event)
    assert len(plan.actions) == 1
    assert plan.actions[0].name == "good_action"
    assert "bad_filter" in caplog.text
    assert "filter exploded" in caplog.text
