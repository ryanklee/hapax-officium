"""Validate SimulatedEvent objects against workflow-semantics.yaml.

Rejects events with unknown workflow types, mismatched subdirectories,
or empty filenames. Logs warnings for each rejected event.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agents.simulator_pipeline.models import SimulatedEvent

_log = logging.getLogger(__name__)


def validate_events(
    events: list[SimulatedEvent],
    valid_workflows: dict[str, Any],
) -> list[SimulatedEvent]:
    """Filter events, keeping only those matching workflow-semantics.yaml.

    Returns a new list containing only valid events. Logs warnings for
    each rejected event.
    """
    validated = []
    for event in events:
        if not event.filename:
            _log.warning("Rejected event: empty filename (type=%s)", event.workflow_type)
            continue

        if event.workflow_type not in valid_workflows:
            _log.warning("Rejected event: unknown workflow_type=%s", event.workflow_type)
            continue

        spec = valid_workflows[event.workflow_type]
        expected_subdir = spec.get("subdirectory", "").rstrip("/")
        actual_subdir = event.subdirectory.rstrip("/")

        if actual_subdir != expected_subdir:
            _log.warning(
                "Rejected event: subdirectory mismatch for %s (got=%s, expected=%s)",
                event.workflow_type,
                event.subdirectory,
                expected_subdir,
            )
            continue

        validated.append(event)

    if len(validated) < len(events):
        _log.info("Validation: %d/%d events passed", len(validated), len(events))

    return validated
