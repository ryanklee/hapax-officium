"""Reactive engine — filesystem-watching event loop for automated cascades."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from logos.engine.delivery import DeliveryQueue
from logos.engine.executor import PhasedExecutor
from logos.engine.models import ChangeEvent, DeliveryItem
from logos.engine.reactive_rules import build_default_rules
from logos.engine.rules import evaluate_rules
from logos.engine.synthesis import SynthesisScheduler
from logos.engine.watcher import DataDirWatcher

if TYPE_CHECKING:
    from pathlib import Path

_log = logging.getLogger(__name__)


class ReactiveEngine:
    """Top-level orchestrator wiring watcher -> rules -> executor -> delivery.

    All constructor params are optional, falling back to environment variables.
    """

    def __init__(
        self,
        *,
        data_dir: Path | None = None,
        enabled: bool | None = None,
        debounce_ms: int | None = None,
        llm_concurrency: int | None = None,
        delivery_interval_s: int | None = None,
        action_timeout_s: float | None = None,
        agent_run_manager: object | None = None,
    ) -> None:
        if data_dir is None:
            from shared.config import config

            data_dir = config.data_dir

        if enabled is None:
            enabled = os.environ.get("ENGINE_ENABLED", "true").lower() in (
                "true",
                "1",
                "yes",
            )
        if debounce_ms is None:
            debounce_ms = int(os.environ.get("ENGINE_DEBOUNCE_MS", "200"))
        if llm_concurrency is None:
            llm_concurrency = int(os.environ.get("ENGINE_LLM_CONCURRENCY", "2"))
        if delivery_interval_s is None:
            delivery_interval_s = int(os.environ.get("ENGINE_DELIVERY_INTERVAL_S", "300"))
        if action_timeout_s is None:
            action_timeout_s = float(os.environ.get("ENGINE_ACTION_TIMEOUT_S", "60"))

        self._enabled = enabled
        self._data_dir = data_dir

        self._watcher = DataDirWatcher(
            data_dir=data_dir,
            on_change=self._handle_change,
            debounce_ms=debounce_ms,
        )
        self._registry = build_default_rules(
            ignore_fn=self._watcher.ignore,
        )
        self._executor = PhasedExecutor(
            llm_concurrency=llm_concurrency,
            action_timeout_s=action_timeout_s,
        )
        self._delivery = DeliveryQueue(flush_interval_s=delivery_interval_s)
        self._scheduler = SynthesisScheduler(
            executor=self._executor,
            delivery=self._delivery,
            agent_run_manager=agent_run_manager,
            ignore_fn=self._watcher.ignore,
        )
        self.running: bool = False
        self.paused: bool = False

    async def start(self) -> None:
        """Start the engine (watcher + delivery flush loop).

        If not enabled, logs a message and returns without starting.
        """
        if not self._enabled:
            _log.info("ReactiveEngine is disabled, not starting")
            return

        if not self._data_dir.is_dir():
            _log.warning("DATA_DIR %s does not exist, creating it", self._data_dir)
            self._data_dir.mkdir(parents=True, exist_ok=True)

        await self._watcher.start()
        await self._delivery.start_flush_loop()
        self.running = True
        await self._scheduler.start()
        _log.info("ReactiveEngine started")

    async def stop(self) -> None:
        """Stop the engine, watcher, and delivery queue."""
        if not self.running:
            return

        await self._watcher.stop()
        await self._delivery.stop()
        await self._scheduler.stop()
        self.running = False
        _log.info("ReactiveEngine stopped")

    async def pause(self) -> None:
        """Pause the engine (stop watcher/scheduler) without full shutdown.

        Used during simulation context switching to prevent the engine
        from reacting to the real DATA_DIR while the API serves simulation data.
        """
        if not self.running:
            return

        await self._watcher.stop()
        await self._scheduler.stop()
        self.running = False
        self.paused = True
        _log.info("ReactiveEngine paused")

    async def resume(self) -> None:
        """Resume the engine after a pause."""
        if not self.paused:
            return

        await self._watcher.start()
        await self._delivery.start_flush_loop()
        await self._scheduler.start()
        self.running = True
        self.paused = False
        _log.info("ReactiveEngine resumed")

    async def _handle_change(self, event: ChangeEvent) -> None:
        """Handle a filesystem change event from the watcher."""
        plan = evaluate_rules(self._registry, event)

        if not plan.actions:
            _log.info("No actions for event %s on %s", event.event_type, event.path)
            return

        _log.info(
            "Event %s on %s -> %d actions",
            event.event_type,
            event.path,
            len(plan.actions),
        )

        await self._executor.execute(plan)

        now = datetime.now(UTC)

        for action_name, result in plan.results.items():
            self._delivery.enqueue(
                DeliveryItem(
                    title=action_name,
                    detail=str(result),
                    priority="medium",
                    category="generated",
                    source_action=action_name,
                    timestamp=now,
                )
            )

        for action_name, error in plan.errors.items():
            self._delivery.enqueue(
                DeliveryItem(
                    title=f"{action_name} failed",
                    detail=error,
                    priority="high",
                    category="error",
                    source_action=action_name,
                    timestamp=now,
                )
            )

        self._scheduler.signal(event.subdirectory)

        from logos.api.cache import cache as _cache
        from logos.engine.synthesis import HOT_PATH, WARM_PATH

        if event.subdirectory in HOT_PATH:
            _cache.record_hot_change()
        elif event.subdirectory in WARM_PATH:
            _cache.record_warm_change()

    def status(self) -> dict:
        """Return engine status summary."""
        return {
            "running": self.running,
            "paused": self.paused,
            "enabled": self._enabled,
            "rules_count": len(self._registry.rules),
            "pending_delivery": len(self._delivery.pending),
            "synthesis": self._scheduler.status(),
        }

    async def force_synthesis(self) -> None:
        """Force immediate synthesis, bypassing quiet window."""
        await self._scheduler.force()

    def recent_items(self) -> list[DeliveryItem]:
        """Return recent delivery items."""
        return list(self._delivery.recent)

    def rule_descriptions(self) -> list[dict]:
        """Return metadata for all registered rules."""
        return [{"name": r.name, "description": r.description} for r in self._registry.rules]
