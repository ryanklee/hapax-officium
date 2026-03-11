"""LLM-driven event generation for the temporal simulator.

Uses pydantic-ai with structured output to generate SimulatedEvent
objects for a single simulation tick. Safety enforcement strips
body_template from restricted types (coaching, feedback).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic_ai import Agent

from agents.simulator_pipeline.models import ContentPolicy, SimulatedEvent
from shared.config import get_model

_log = logging.getLogger(__name__)

_event_agent = Agent(
    get_model("balanced"),
    system_prompt=(
        "You are a temporal simulation engine for a management cockpit system. "
        "You generate plausible management activity events for a single workday. "
        "Each event represents a file that would be created or updated in the "
        "manager's data directory. Output 0-3 events per day.\n\n"
        "VALID WORKFLOW TYPES (use EXACTLY these workflow_type and subdirectory values):\n"
        "  one_on_one → subdirectory: meetings\n"
        "  coaching_note → subdirectory: coaching\n"
        "  feedback → subdirectory: feedback\n"
        "  okr_update → subdirectory: okrs\n"
        "  goal → subdirectory: goals\n"
        "  incident → subdirectory: incidents\n"
        "  postmortem_action → subdirectory: postmortem-actions\n"
        "  review_cycle → subdirectory: review-cycles\n"
        "  status_report → subdirectory: status-reports\n"
        "  decision → subdirectory: decisions\n\n"
        "SAFETY: Never generate evaluative language about team members. "
        "Coaching and feedback events must have body_template=null."
    ),
    output_type=list[SimulatedEvent],
    model_settings={"max_tokens": 4096},
)


async def generate_tick_events(
    *,
    prompt: str,
    valid_workflows: dict[str, Any] | None = None,
) -> list[SimulatedEvent]:
    """Generate events for a single tick via LLM.

    Applies safety enforcement: strips body_template from restricted types.
    If valid_workflows is provided, validates events against workflow-semantics.
    """
    result = await _event_agent.run(prompt)
    events = result.output

    # Safety enforcement: strip body from restricted types
    for event in events:
        if ContentPolicy.is_restricted(event.workflow_type):
            event.body_template = None

    # Validate against workflow-semantics if provided
    if valid_workflows is not None:
        from agents.simulator_pipeline.validation import validate_events

        events = validate_events(events, valid_workflows)

    return events
