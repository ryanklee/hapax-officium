"""system_check.py — Minimal management system health checks.

Zero LLM calls. Checks the 3 services needed for the management system:
logos API, Qdrant, and LiteLLM.

Usage:
    uv run python -m agents.system_check              # Human output
    uv run python -m agents.system_check --json        # Machine-readable JSON
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import socket
import sys
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("agents.system_check")


# -- Schemas ------------------------------------------------------------------


class CheckResult:
    __slots__ = ("name", "ok", "message")

    def __init__(self, name: str, ok: bool, message: str) -> None:
        self.name = name
        self.ok = ok
        self.message = message

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "message": self.message}


# -- HTTP helper --------------------------------------------------------------


async def _http_get(url: str, timeout: float = 5.0) -> tuple[int, str]:
    """HTTP GET returning (status_code, body). Runs in executor."""

    def _fetch() -> tuple[int, str]:
        req = Request(url)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return (resp.status, resp.read().decode("utf-8", errors="replace"))
        except URLError as e:
            return (0, str(e))
        except Exception as e:
            return (0, str(e))

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch)


# -- Checks -------------------------------------------------------------------


async def check_logos_api() -> CheckResult:
    """Check if the logos API is responding."""
    try:
        code, _ = await _http_get("http://127.0.0.1:8051/")
        return CheckResult("logos_api", code == 200, f"status {code}")
    except Exception as e:
        return CheckResult("logos_api", False, str(e))


async def check_qdrant() -> CheckResult:
    """Check if Qdrant is reachable."""
    url = os.environ.get("QDRANT_URL", "http://127.0.0.1:6433")
    try:
        code, _ = await _http_get(f"{url}/collections")
        return CheckResult("qdrant", code == 200, "reachable")
    except Exception as e:
        return CheckResult("qdrant", False, str(e))


async def check_litellm() -> CheckResult:
    """Check if LiteLLM is reachable."""
    url = os.environ.get("LITELLM_API_BASE", "http://127.0.0.1:4100")
    try:
        code, _ = await _http_get(f"{url}/health/liveliness")
        return CheckResult("litellm", code == 200, "reachable")
    except Exception as e:
        return CheckResult("litellm", False, str(e))


ALL_CHECKS = [check_logos_api, check_qdrant, check_litellm]


# -- Runner -------------------------------------------------------------------


async def run_checks() -> list[CheckResult]:
    """Run all checks in parallel."""
    return list(await asyncio.gather(*(fn() for fn in ALL_CHECKS)))


def _notify_failures(results: list[CheckResult]) -> None:
    """Send ntfy notification for any failures."""
    failures = [r for r in results if not r.ok]
    if not failures:
        return

    ntfy_url = os.environ.get("NTFY_BASE_URL", "http://127.0.0.1:8190")
    topic = os.environ.get("NTFY_TOPIC", "cockpit")
    names = ", ".join(f.name for f in failures)
    body = f"Failed checks: {names}"

    try:
        req = Request(
            f"{ntfy_url}/{topic}",
            data=body.encode(),
            headers={"Title": "System Check Failed", "Priority": "high"},
            method="POST",
        )
        urlopen(req, timeout=5)
    except Exception as e:
        log.warning("Could not send ntfy notification: %s", e)


# -- Formatters ---------------------------------------------------------------

_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"


def format_human(results: list[CheckResult], color: bool = True) -> str:
    """Format results as human-readable text."""
    lines: list[str] = []
    ok_count = sum(1 for r in results if r.ok)
    total = len(results)
    all_ok = ok_count == total

    if color:
        c = _GREEN if all_ok else _RED
        header = (
            f"System Check: {c}{'OK' if all_ok else 'FAILED'}{_RESET} ({ok_count}/{total} passed)"
        )
    else:
        header = f"System Check: {'OK' if all_ok else 'FAILED'} ({ok_count}/{total} passed)"
    lines.append(header)
    lines.append("")

    for r in results:
        if color:
            c = _GREEN if r.ok else _RED
            icon = f"{c}[{'OK' if r.ok else 'FAIL'}]{_RESET}"
        else:
            icon = f"[{'OK' if r.ok else 'FAIL'}]"
        padding = max(1, 20 - len(r.name))
        dots = "." * padding
        lines.append(f"  {icon} {r.name} {dots} {r.message}")

    return "\n".join(lines)


# -- CLI ----------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Management system health checks",
        prog="python -m agents.system_check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )

    args = parser.parse_args()
    results = await run_checks()

    if args.json:
        output = {
            "timestamp": datetime.now(UTC).isoformat(),
            "hostname": socket.gethostname(),
            "all_ok": all(r.ok for r in results),
            "checks": [r.to_dict() for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        color = sys.stdout.isatty()
        print(format_human(results, color=color))

    # Notify on failures
    _notify_failures(results)

    # Exit code: 0 if all ok, 1 if any failures
    if not all(r.ok for r in results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
