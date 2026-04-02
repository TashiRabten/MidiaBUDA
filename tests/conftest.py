"""Shared fixtures for MediaBUDA tests."""
import os
import sys
import pytest

# Ensure APP package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# QApplication singleton — required for any widget tests
_qapp = None


@pytest.fixture(scope="session")
def qapp():
    """Create a single QApplication for the entire test session."""
    global _qapp
    if _qapp is None:
        from PyQt6.QtWidgets import QApplication
        _qapp = QApplication.instance() or QApplication([])
    return _qapp


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    """Redirect config I/O to a temp directory."""
    config_dir = tmp_path / ".ffmpeg_pro_studio"
    config_dir.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return config_dir
