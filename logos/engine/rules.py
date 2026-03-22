"""Rules engine — Rule dataclass, RuleRegistry, and evaluate_rules.

Rules map ChangeEvents to ActionPlans. Each rule has a trigger_filter
predicate and a produce callable that returns actions when the filter matches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from logos.engine.models import Action, ActionPlan, ChangeEvent

if TYPE_CHECKING:
    from collections.abc import Callable

_log = logging.getLogger(__name__)


@dataclass
class Rule:
    """A single rule mapping a ChangeEvent pattern to actions."""

    name: str
    trigger_filter: Callable[[ChangeEvent], bool]
    produce: Callable[[ChangeEvent], list[Action]]
    description: str = ""


class RuleRegistry:
    """Registry of named rules, keyed by name (last registration wins)."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}

    @property
    def rules(self) -> list[Rule]:
        """Return all registered rules in insertion order."""
        return list(self._rules.values())

    def register(self, rule: Rule) -> None:
        """Add a rule, replacing any existing rule with the same name."""
        self._rules[rule.name] = rule


def evaluate_rules(registry: RuleRegistry, event: ChangeEvent) -> ActionPlan:
    """Evaluate all rules against an event and return a deduplicated ActionPlan.

    - Iterates rules, calls trigger_filter for each
    - Collects actions from matching rules via produce()
    - Deduplicates actions by name (first one wins)
    - Catches and logs exceptions from rule.produce() without aborting
    """
    actions: list[Action] = []
    seen_names: set[str] = set()

    for rule in registry.rules:
        try:
            if not rule.trigger_filter(event):
                continue
        except Exception:
            _log.exception("Rule '%s' trigger_filter() failed for event %s", rule.name, event.path)
            continue
        try:
            produced = rule.produce(event)
        except Exception:
            _log.exception("Rule '%s' produce() failed for event %s", rule.name, event.path)
            continue
        for action in produced:
            if action.name not in seen_names:
                seen_names.add(action.name)
                actions.append(action)

    return ActionPlan(
        trigger=event,
        created_at=datetime.now(UTC),
        actions=actions,
    )
