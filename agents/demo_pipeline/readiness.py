"""System readiness gate — ensures system is presentable before demo generation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

log = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine, handling both fresh and existing event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing event loop — create a new thread to run it
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


@dataclass
class ReadinessResult:
    """Result of the system readiness check."""

    ready: bool
    health_score: str = ""  # e.g., "74/75"
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    health_report: object | None = None  # HealthReport if available
    briefing_summary: str = ""


def check_readiness(
    require_tts: bool = False,
    auto_fix: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> ReadinessResult:
    """Run system readiness checks. Returns ReadinessResult.

    Checks:
    1. System check (run_checks)
    2. Cockpit API (:8050) reachable
    3. Cockpit web (:5173) reachable
    4. TTS service (:4123) if require_tts=True
    5. Voice sample exists if require_tts=True
    """

    def progress(msg: str) -> None:
        if on_progress:
            on_progress(msg)
        else:
            log.info(msg)

    issues: list[str] = []
    warnings: list[str] = []
    health_score = ""
    health_report = None

    # 1. System check — run_checks() is async, returns list[CheckResult]
    try:
        from agents.system_check import run_checks

        progress("Running health checks...")
        results = _run_async(run_checks())
        health_report = results
        ok_count = sum(1 for r in results if r.ok)
        total = len(results)
        failed_count = total - ok_count
        health_score = f"{ok_count}/{total}"
        progress(f"Health: {health_score}")

        if failed_count > 0:
            if auto_fix:
                log.warning("auto_fix requested but system_check has no auto-fix capability")
            # Health failures are warnings, not blockers — the demo only
            # needs LiteLLM, Qdrant, cockpit, and TTS (checked separately)
            failed_names = [r.name for r in results if not r.ok]
            warnings.append(
                f"System check: {failed_count} failed checks: {', '.join(failed_names)} (non-blocking)"
            )
    except Exception as e:
        warnings.append(f"System check unavailable: {e}")

    # 2. Cockpit API
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:8060/api/status", timeout=5)
        progress("Cockpit API: OK")
    except Exception:
        issues.append(
            "Cockpit API (:8060) not reachable — start with: "
            "cd ~/projects/hapax-officium/ai-agents && uv run python -m cockpit.api --port 8060"
        )

    # 3. Cockpit web
    try:
        import urllib.request

        urllib.request.urlopen("http://localhost:5173", timeout=5)
        progress("Cockpit web: OK")
    except Exception:
        issues.append(
            "Cockpit web (:5173) not reachable — start with: "
            "cd ~/projects/hapax-officium/officium-web && pnpm dev"
        )

    # 4 & 5. TTS (only if required)
    if require_tts:
        try:
            import urllib.request

            urllib.request.urlopen("http://localhost:4123/docs", timeout=5)
            progress("TTS service: OK")
        except Exception:
            issues.append(
                "Chatterbox TTS (:4123) not running — start with: "
                "cd ~/projects/hapax-officium/llm-stack && docker compose --profile tts up -d chatterbox"
            )

        # Voice sample
        from shared.config import PROFILES_DIR

        voice_sample = PROFILES_DIR / "voice-sample.wav"
        if not voice_sample.exists():
            issues.append(f"Voice sample not found at {voice_sample}")
        else:
            progress("Voice sample: OK")

    ready = len(issues) == 0
    return ReadinessResult(
        ready=ready,
        health_score=health_score,
        issues=issues,
        warnings=warnings,
        health_report=health_report,
    )
