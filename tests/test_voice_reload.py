"""Tests that a voice replaced on disk is reloaded instead of kept in memory."""

import argparse
import asyncio
import os
import wave
from pathlib import Path
from typing import List

import pytest

from wyoming_piper import handler as handler_module
from wyoming_piper.download import VoiceNotFoundError
from wyoming_piper.handler import PiperEventHandler


class _FakeConfig:
    speaker_id_map: dict = {}


class _FakeVoice:
    def __init__(self, model_path: Path) -> None:
        self.model_bytes = model_path.read_bytes()
        self.config = _FakeConfig()

    def synthesize_wav(self, text: str, wav_writer: wave.Wave_write, *args) -> None:
        wav_writer.setframerate(22050)
        wav_writer.setsampwidth(2)
        wav_writer.setnchannels(1)
        wav_writer.writeframes(bytes(2))


def _write_voice(voice_dir: Path, name: str, model: bytes, mtime: int) -> None:
    for path in (voice_dir / f"{name}.onnx", voice_dir / f"{name}.onnx.json"):
        path.write_bytes(model if path.suffix == ".onnx" else b"{}")
        os.utime(path, ns=(mtime, mtime))


@pytest.fixture
def loads(monkeypatch: pytest.MonkeyPatch) -> List[_FakeVoice]:
    loaded: List[_FakeVoice] = []

    def load(model_path, config_path, use_cuda=False):  # type: ignore[no-untyped-def]
        voice = _FakeVoice(Path(model_path))
        loaded.append(voice)
        return voice

    monkeypatch.setattr(handler_module.PiperVoice, "load", load)
    monkeypatch.setattr(handler_module, "_VOICE", None)
    monkeypatch.setattr(handler_module, "_VOICE_NAME", None)
    monkeypatch.setattr(handler_module, "_VOICE_FILES", None, raising=False)
    return loaded


def _synthesize(voice_dir: Path, name: str) -> None:
    cli_args = argparse.Namespace(
        data_dir=[str(voice_dir)],
        download_dir=str(voice_dir),
        use_cuda=False,
        length_scale=None,
        noise_scale=None,
        noise_w_scale=None,
    )
    handler = PiperEventHandler(
        lambda: None,  # type: ignore[arg-type,return-value]
        cli_args,
        {},
        asyncio.StreamReader(),
        None,
    )
    with open(voice_dir / "out.wav", "wb") as out_file:
        wav_writer = wave.open(out_file, "wb")
        wav_writer.setparams((1, 2, 22050, 0, "NONE", "not compressed"))
        handler._synthesize_piper("Hello.", wav_writer, name, None)
        wav_writer.close()


async def test_unchanged_voice_is_not_reloaded(
    tmp_path: Path, loads: List[_FakeVoice]
) -> None:
    _write_voice(tmp_path, "custom", b"v1", 1_000_000_000)

    _synthesize(tmp_path, "custom")
    _synthesize(tmp_path, "custom")

    assert len(loads) == 1


async def test_replaced_voice_is_reloaded(
    tmp_path: Path, loads: List[_FakeVoice]
) -> None:
    """Uploading a voice again under the same name takes effect right away."""
    _write_voice(tmp_path, "custom", b"v1", 1_000_000_000)
    _synthesize(tmp_path, "custom")

    _write_voice(tmp_path, "custom", b"v2-model", 2_000_000_000)
    _synthesize(tmp_path, "custom")

    assert [voice.model_bytes for voice in loads] == [b"v1", b"v2-model"]
    assert handler_module._VOICE is loads[-1]


async def test_deleted_voice_is_not_spoken(
    tmp_path: Path, loads: List[_FakeVoice]
) -> None:
    """A voice removed from disk fails instead of playing from memory."""
    _write_voice(tmp_path, "custom", b"v1", 1_000_000_000)
    _synthesize(tmp_path, "custom")

    (tmp_path / "custom.onnx").unlink()
    (tmp_path / "custom.onnx.json").unlink()

    with pytest.raises(VoiceNotFoundError):
        _synthesize(tmp_path, "custom")
