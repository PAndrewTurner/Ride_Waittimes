"""CLI smoke tests."""

import subprocess
import sys


def test_main_help():
    result = subprocess.run(
        [sys.executable, "-m", "parkwaits", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "collect" in result.stdout
    assert "status" in result.stdout
    assert "discover" in result.stdout


def test_collect_help():
    result = subprocess.run(
        [sys.executable, "-m", "parkwaits", "collect", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "hourly" in result.stdout
    assert "daily" in result.stdout
