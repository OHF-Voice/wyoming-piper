"""Tests for the ONNX Runtime telemetry opt-out (issue #64)."""

import os
import subprocess
import sys

_CODE = (
    "import wyoming_piper, os, sys; "
    "sys.stdout.write(os.environ.get('ORT_DISABLE_TELEMETRY', '<unset>'))"
)


def _run(env_value):
    env = dict(os.environ)
    if env_value is None:
        env.pop("ORT_DISABLE_TELEMETRY", None)
    else:
        env["ORT_DISABLE_TELEMETRY"] = env_value

    return subprocess.check_output(
        [sys.executable, "-c", _CODE], env=env, text=True
    ).strip()


def test_telemetry_disabled_by_default() -> None:
    """Importing the package opts out of ONNX Runtime telemetry."""
    assert _run(None) == "1"


def test_telemetry_env_is_not_overridden() -> None:
    """An explicit setting wins, so telemetry can be turned back on."""
    assert _run("0") == "0"
