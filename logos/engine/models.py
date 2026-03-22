"""Core data models for the reactive engine.

Four dataclasses representing the event-driven pipeline:
ChangeEvent -> Action/ActionPlan -> DeliveryItem.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path


@dataclass
class ChangeEvent:
    """Detected filesystem change in DATA_DIR."""

    path: Path
    subdirectory: str
    event_type: str  # "created" | "modified" | "deleted"
    doc_type: str | None
    timestamp: datetime


@dataclass
class Action:
    """Unit of work to be executed by the engine."""

    name: str
    handler: Callable  # async callable
    args: dict = field(default_factory=dict)
    priority: int = 0
    phase: int = 0
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ActionPlan:
    """Ordered set of actions produced by rule evaluation."""

    created_at: datetime
    trigger: ChangeEvent | None = None  # None for timer-driven plans
    actions: list[Action] = field(default_factory=list)
    results: dict[str, Any] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)
    skipped: set[str] = field(default_factory=set)

    def actions_by_phase(self) -> dict[int, list[Action]]:
        """Group actions by phase, sorted by phase number.

        Actions within each phase are sorted by priority (ascending).
        """
        if not self.actions:
            return {}
        grouped: dict[int, list[Action]] = defaultdict(list)
        for action in self.actions:
            grouped[action.phase].append(action)
        return {
            phase: sorted(actions, key=lambda a: a.priority)
            for phase, actions in sorted(grouped.items())
        }


@dataclass
class DeliveryItem:
    """Notification queued for batched delivery."""

    title: str
    detail: str
    priority: str  # "critical" | "high" | "medium" | "low"
    category: str  # "generated" | "detected" | "warning" | "error"
    source_action: str
    timestamp: datetime
    artifacts: list[Path] = field(default_factory=list)
