"""Tests that an interrupted download cannot leave a broken file behind.

A voice is only re-downloaded when its file is missing or empty -- sizes and
hashes are deliberately not checked -- so a truncated model would never be
retried and the voice would stay broken until someone deleted it by hand.
"""

import io
import json
from pathlib import Path
from typing import Any, List

import pytest

from wyoming_piper import download as download_module
from wyoming_piper.download import ensure_voice_exists, get_voices

_VOICE = "en_US-lessac-medium"


class _TruncatedResponse(io.RawIOBase):
    """Yields a few bytes, then fails the way a dropped connection does."""

    def __init__(self) -> None:
        self._sent = False

    def readinto(self, buffer: Any) -> int:
        if not self._sent:
            self._sent = True
            chunk = b"partial data"
            buffer[: len(chunk)] = chunk
            return len(chunk)
        raise ConnectionResetError("connection dropped mid-download")

    def readable(self) -> bool:
        return True

    def __enter__(self) -> "_TruncatedResponse":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


def _fail_midway(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        download_module, "urlopen", lambda *args, **kwargs: _TruncatedResponse()
    )


def _succeed_with(monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    monkeypatch.setattr(
        download_module, "urlopen", lambda *args, **kwargs: io.BytesIO(payload)
    )


def _leftovers(directory: Path) -> List[str]:
    return sorted(p.name for p in directory.iterdir())


def test_interrupted_voice_download_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No truncated .onnx, and no stray .part file either."""
    _fail_midway(monkeypatch)
    voices_info = {
        _VOICE: {"key": _VOICE, "files": {f"en/{_VOICE}.onnx": {"size_bytes": 999}}}
    }

    # URLError is caught inside ensure_voice_exists; other errors are not, and
    # either way nothing partial may survive.
    with pytest.raises(ConnectionResetError):
        ensure_voice_exists(_VOICE, [tmp_path], tmp_path, voices_info)

    assert _leftovers(tmp_path) == []


def test_completed_voice_download_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The happy path still puts the file where it belongs, with no .part left."""
    _succeed_with(monkeypatch, b"onnx bytes")
    voices_info = {
        _VOICE: {"key": _VOICE, "files": {f"en/{_VOICE}.onnx": {"size_bytes": 10}}}
    }

    ensure_voice_exists(_VOICE, [tmp_path], tmp_path, voices_info)

    assert _leftovers(tmp_path) == [f"{_VOICE}.onnx"]
    assert (tmp_path / f"{_VOICE}.onnx").read_bytes() == b"onnx bytes"


def test_interrupted_catalog_update_keeps_the_previous_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed --update-voices must not corrupt the voices.json already there."""
    existing = {"a_custom-voice": {"key": "a_custom-voice"}}
    (tmp_path / "voices.json").write_text(json.dumps(existing), encoding="utf-8")

    _fail_midway(monkeypatch)
    voices = get_voices(tmp_path, update_voices=True)

    assert "a_custom-voice" in voices
    assert (
        json.loads((tmp_path / "voices.json").read_text(encoding="utf-8")) == existing
    )
    assert "voices.json.part" not in _leftovers(tmp_path)
