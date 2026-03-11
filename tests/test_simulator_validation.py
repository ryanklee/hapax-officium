"""Tests for event validation against workflow-semantics.yaml."""

from __future__ import annotations

from agents.simulator_pipeline.models import SimulatedEvent
from agents.simulator_pipeline.validation import validate_events

# Minimal valid workflows dict matching workflow-semantics.yaml structure
_VALID_WORKFLOWS = {
    "one_on_one": {"subdirectory": "meetings/"},
    "coaching_note": {"subdirectory": "coaching/"},
    "feedback": {"subdirectory": "feedback/"},
    "decision": {"subdirectory": "decisions/"},
    "status_report": {"subdirectory": "status-reports/"},
    "incident": {"subdirectory": "incidents/"},
}


def _event(
    workflow_type: str = "one_on_one",
    subdirectory: str = "meetings",
    filename: str = "2026-03-05-alice.md",
    **kwargs,
) -> SimulatedEvent:
    return SimulatedEvent(
        date="2026-03-05",
        workflow_type=workflow_type,
        subdirectory=subdirectory,
        filename=filename,
        metadata={"type": "meeting"},
        **kwargs,
    )


class TestValidateEvents:
    def test_valid_event_passes(self):
        """Events with known workflow_type and matching subdirectory pass."""
        events = [_event()]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 1

    def test_unknown_workflow_type_rejected(self):
        """Events with unknown workflow_type are filtered out."""
        events = [_event(workflow_type="unknown_type", subdirectory="unknown")]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 0

    def test_wrong_subdirectory_rejected(self):
        """Events with wrong subdirectory for their workflow_type are rejected."""
        events = [_event(workflow_type="one_on_one", subdirectory="wrong-dir")]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 0

    def test_empty_filename_rejected(self):
        """Events with empty filename are rejected."""
        events = [_event(filename="")]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 0

    def test_mixed_valid_and_invalid(self):
        """Only valid events survive filtering."""
        events = [
            _event(),  # valid
            _event(workflow_type="bogus", subdirectory="nope"),  # invalid
            _event(
                workflow_type="decision", subdirectory="decisions", filename="2026-03-05-ci.md"
            ),  # valid
        ]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 2
        assert result[0].workflow_type == "one_on_one"
        assert result[1].workflow_type == "decision"

    def test_subdirectory_trailing_slash_normalized(self):
        """Subdirectory matching handles trailing slash in workflow spec."""
        # workflow-semantics.yaml has "meetings/" with trailing slash
        events = [_event(subdirectory="meetings")]
        result = validate_events(events, _VALID_WORKFLOWS)
        assert len(result) == 1
