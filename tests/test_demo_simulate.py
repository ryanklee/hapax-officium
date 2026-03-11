# tests/test_demo_simulate.py
"""Tests for demo agent --simulate integration."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

# Stub playwright before agents.demo is imported so the module loads cleanly
# in environments where playwright is not installed.
if "playwright" not in sys.modules:
    _pw_stub = ModuleType("playwright")
    _pw_async = ModuleType("playwright.async_api")
    _pw_async.async_playwright = MagicMock()
    _pw_async.TimeoutError = TimeoutError
    sys.modules["playwright"] = _pw_stub
    sys.modules["playwright.async_api"] = _pw_async

import contextlib
from typing import TYPE_CHECKING

from agents.demo import _run_simulated_demo
from shared.config import config

if TYPE_CHECKING:
    from pathlib import Path


class TestDemoSimulateOrchestration:
    async def test_simulate_calls_simulation_then_warmup_then_demo(self, tmp_path: Path):
        """--simulate runs simulation, warm-up, then demo generation."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()

        call_order = []

        async def mock_run_sim(**kwargs):
            call_order.append("simulate")
            return sim_dir

        async def mock_warmup(path):
            call_order.append("warmup")

        async def mock_generate_demo(request, **kwargs):
            call_order.append("demo")
            demo_dir = tmp_path / "demo-output"
            demo_dir.mkdir(exist_ok=True)
            return demo_dir

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            patch("agents.demo.config"),
        ):
            await _run_simulated_demo(
                request="the management cockpit for a technical peer",
                window="5d",
                variant="experienced-em",
                scenario=None,
                audience="technical-peer",
                format="slides",
                duration=None,
                persona_file=None,
                voice=False,
            )

        assert call_order == ["simulate", "warmup", "demo"]

    async def test_simulate_resets_data_dir_on_error(self, tmp_path: Path):
        """config.data_dir is reset even if demo generation fails."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()

        original_dir = config.data_dir

        async def mock_run_sim(**kwargs):
            return sim_dir

        async def mock_warmup(path):
            pass

        async def mock_generate_demo(request, **kwargs):
            raise RuntimeError("demo failed")

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            contextlib.suppress(RuntimeError),
        ):
            await _run_simulated_demo(
                request="test",
                window="5d",
                variant="experienced-em",
                scenario=None,
                audience=None,
                format="slides",
                duration=None,
                persona_file=None,
                voice=False,
            )

        assert config.data_dir == original_dir


class TestDemoSimulateRoleInference:
    async def test_infers_role_from_request(self, tmp_path: Path):
        """Role is inferred from request when --role not provided."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()
        captured_kwargs = {}

        async def mock_run_sim(**kwargs):
            captured_kwargs.update(kwargs)
            return sim_dir

        async def mock_warmup(path):
            pass

        async def mock_generate_demo(request, **kwargs):
            demo_dir = tmp_path / "demo-output"
            demo_dir.mkdir(exist_ok=True)
            return demo_dir

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            patch("agents.demo.config"),
        ):
            await _run_simulated_demo(
                request="show the VP of engineering dashboard",
                window="5d",
                variant="baseline",
            )

        assert captured_kwargs["role"] == "vp-engineering"

    async def test_explicit_role_overrides_inference(self, tmp_path: Path):
        """--role overrides inference from request text."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()
        captured_kwargs = {}

        async def mock_run_sim(**kwargs):
            captured_kwargs.update(kwargs)
            return sim_dir

        async def mock_warmup(path):
            pass

        async def mock_generate_demo(request, **kwargs):
            demo_dir = tmp_path / "demo-output"
            demo_dir.mkdir(exist_ok=True)
            return demo_dir

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            patch("agents.demo.config"),
        ):
            await _run_simulated_demo(
                request="show the VP of engineering dashboard",
                role="tech-lead",
                window="5d",
                variant="baseline",
            )

        assert captured_kwargs["role"] == "tech-lead"

    async def test_org_dossier_passed_through(self, tmp_path: Path):
        """--org-dossier is passed through to run_simulation."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()
        captured_kwargs = {}

        async def mock_run_sim(**kwargs):
            captured_kwargs.update(kwargs)
            return sim_dir

        async def mock_warmup(path):
            pass

        async def mock_generate_demo(request, **kwargs):
            demo_dir = tmp_path / "demo-output"
            demo_dir.mkdir(exist_ok=True)
            return demo_dir

        dossier_path = tmp_path / "custom-org.yaml"

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            patch("agents.demo.config"),
        ):
            await _run_simulated_demo(
                request="show the management cockpit",
                window="5d",
                variant="experienced-em",
                org_dossier=dossier_path,
            )

        assert captured_kwargs["org_dossier"] == dossier_path

    async def test_defaults_to_em_when_no_hints(self, tmp_path: Path):
        """Falls back to engineering-manager when request has no role hints."""
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir()
        captured_kwargs = {}

        async def mock_run_sim(**kwargs):
            captured_kwargs.update(kwargs)
            return sim_dir

        async def mock_warmup(path):
            pass

        async def mock_generate_demo(request, **kwargs):
            demo_dir = tmp_path / "demo-output"
            demo_dir.mkdir(exist_ok=True)
            return demo_dir

        with (
            patch("agents.demo.run_simulation", side_effect=mock_run_sim),
            patch("agents.demo.run_warmup", side_effect=mock_warmup),
            patch("agents.demo.generate_demo", side_effect=mock_generate_demo),
            patch("agents.demo.config"),
        ):
            await _run_simulated_demo(
                request="show the management cockpit",
                window="5d",
                variant="experienced-em",
            )

        assert captured_kwargs["role"] == "engineering-manager"
