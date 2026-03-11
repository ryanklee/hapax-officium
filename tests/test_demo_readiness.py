"""Tests for system readiness gate."""

from unittest.mock import AsyncMock, MagicMock, patch

from agents.demo_pipeline.readiness import ReadinessResult, check_readiness


def _make_check_results(ok_count: int = 4, total: int = 4):
    """Create a list of mock CheckResult objects matching system_check interface."""
    results = []
    for i in range(ok_count):
        r = MagicMock()
        r.name = f"check_{i}"
        r.ok = True
        r.message = "OK"
        results.append(r)
    for i in range(total - ok_count):
        r = MagicMock()
        r.name = f"check_failed_{i}"
        r.ok = False
        r.message = "FAIL"
        results.append(r)
    return results


class TestReadiness:
    def test_readiness_all_healthy(self):
        """All checks pass -> ready=True."""
        mock_results = _make_check_results()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ) as mock_run,
            patch("urllib.request.urlopen"),
        ):
            result = check_readiness()
            assert result.ready is True
            assert result.health_score == "4/4"
            mock_run.assert_called_once()

    def test_readiness_health_failures(self):
        """Health failures -> ready=True (warnings, not blockers)."""
        mock_results = _make_check_results(ok_count=3, total=4)

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen"),
        ):
            result = check_readiness()
            assert result.ready is True
            assert any("failed" in w.lower() for w in result.warnings)

    def test_readiness_health_failures_no_autofix(self):
        """Health failures with auto_fix=False -> still reports warnings."""
        mock_results = _make_check_results(ok_count=3, total=4)

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen"),
        ):
            result = check_readiness(auto_fix=False)
            assert result.ready is True
            assert any("failed" in w.lower() for w in result.warnings)

    def test_readiness_cockpit_api_down(self):
        """Cockpit API down -> ready=False."""
        mock_results = _make_check_results()

        def urlopen_side_effect(url, **kwargs):
            if "8060" in url:
                raise ConnectionError("Connection refused")
            return MagicMock()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen", side_effect=urlopen_side_effect),
        ):
            result = check_readiness()
            assert result.ready is False
            assert any("8060" in i for i in result.issues)

    def test_readiness_cockpit_web_down(self):
        """Cockpit web down -> ready=False."""
        mock_results = _make_check_results()

        def urlopen_side_effect(url, **kwargs):
            if "5173" in url:
                raise ConnectionError("Connection refused")
            return MagicMock()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen", side_effect=urlopen_side_effect),
        ):
            result = check_readiness()
            assert result.ready is False
            assert any("5173" in i for i in result.issues)

    def test_readiness_tts_not_required(self):
        """TTS down but not required -> still ready."""
        mock_results = _make_check_results()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen"),
        ):
            result = check_readiness(require_tts=False)
            assert result.ready is True

    def test_readiness_tts_required_but_down(self):
        """TTS required but down -> ready=False."""
        mock_results = _make_check_results()

        def urlopen_side_effect(url, **kwargs):
            if "4123" in url:
                raise ConnectionError("Connection refused")
            return MagicMock()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen", side_effect=urlopen_side_effect),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = check_readiness(require_tts=True)
            assert result.ready is False
            assert any("4123" in i for i in result.issues)

    def test_readiness_voice_sample_missing(self):
        """Voice sample missing -> ready=False."""
        mock_results = _make_check_results()

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen"),
            patch("pathlib.Path.exists", return_value=False),
        ):
            result = check_readiness(require_tts=True)
            assert result.ready is False
            assert any("voice" in i.lower() for i in result.issues)

    def test_readiness_system_check_unavailable(self):
        """System check import failure -> warning, not issue."""
        with (
            patch(
                "agents.system_check.run_checks",
                new_callable=AsyncMock,
                side_effect=ImportError("no module"),
            ),
            patch("urllib.request.urlopen"),
        ):
            result = check_readiness()
            assert result.ready is True
            assert any("unavailable" in w.lower() for w in result.warnings)

    def test_readiness_on_progress_callback(self):
        """on_progress callback is invoked."""
        mock_results = _make_check_results()
        progress_msgs: list[str] = []

        with (
            patch(
                "agents.system_check.run_checks", new_callable=AsyncMock, return_value=mock_results
            ),
            patch("urllib.request.urlopen"),
        ):
            check_readiness(on_progress=progress_msgs.append)
            assert len(progress_msgs) > 0
            assert any("health" in m.lower() for m in progress_msgs)

    def test_readiness_result_dataclass(self):
        """ReadinessResult defaults work correctly."""
        result = ReadinessResult(ready=True)
        assert result.ready is True
        assert result.issues == []
        assert result.warnings == []
        assert result.health_report is None
        assert result.health_score == ""
        assert result.briefing_summary == ""
