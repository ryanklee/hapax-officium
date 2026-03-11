"""Phased async executor for ActionPlans.

Runs actions grouped by phase with bounded LLM concurrency.
Phase 0 = deterministic/fast (unlimited concurrency).
Phase >= 1 = LLM calls (bounded by semaphore).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cockpit.engine.models import Action, ActionPlan


@dataclass
class PhasedExecutor:
    """Execute an ActionPlan phase-by-phase with concurrency control."""

    llm_concurrency: int = 2
    action_timeout_s: float = 60.0
    _llm_semaphore: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._llm_semaphore = asyncio.Semaphore(self.llm_concurrency)

    async def execute(self, plan: ActionPlan) -> None:
        """Run all actions in the plan, phase by phase."""
        phases = plan.actions_by_phase()
        for phase_num in sorted(phases):
            actions = phases[phase_num]
            async with asyncio.TaskGroup() as tg:
                for action in actions:
                    tg.create_task(self._run_action(action, plan, phase_num))

    async def _run_action(self, action: Action, plan: ActionPlan, phase: int) -> None:
        """Run a single action with dependency checking, timeout, and error handling."""
        # Check dependencies
        if any(dep in plan.errors or dep in plan.skipped for dep in action.depends_on):
            plan.skipped.add(action.name)
            return

        try:
            if phase >= 1:
                async with self._llm_semaphore:
                    result = await asyncio.wait_for(
                        action.handler(**action.args),
                        timeout=self.action_timeout_s,
                    )
            else:
                result = await asyncio.wait_for(
                    action.handler(**action.args),
                    timeout=self.action_timeout_s,
                )
            plan.results[action.name] = result
        except TimeoutError:
            plan.errors[action.name] = "timeout"
        except Exception as exc:
            plan.errors[action.name] = str(exc)
