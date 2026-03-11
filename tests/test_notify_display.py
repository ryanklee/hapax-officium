"""Test that notify-send is skipped when no display server is available."""

from unittest.mock import patch


def test_send_desktop_skips_without_display():
    """_send_desktop returns False immediately when no DISPLAY or WAYLAND_DISPLAY."""
    with patch.dict("os.environ", {}, clear=True):
        from shared.notify import _send_desktop

        with patch("subprocess.run") as mock_run:
            result = _send_desktop("title", "message")
            assert result is False
            mock_run.assert_not_called()


def test_send_desktop_runs_with_display():
    """_send_desktop attempts notify-send when DISPLAY is set."""
    with patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True):
        from shared.notify import _send_desktop

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            _send_desktop("title", "message")
            mock_run.assert_called_once()


def test_send_desktop_runs_with_wayland():
    """_send_desktop attempts notify-send when WAYLAND_DISPLAY is set."""
    with patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"}, clear=True):
        from shared.notify import _send_desktop

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            _send_desktop("title", "message")
            mock_run.assert_called_once()
