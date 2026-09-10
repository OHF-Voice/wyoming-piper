"""Tests that a failing synthesis reports what actually went wrong.

The wave writer never gets its parameters set when synthesis raises, so closing
it raises "# channels not specified" in turn. That error used to replace the
real one, and since ``handle_event`` turns the exception into a Wyoming
``Error`` event, the client was told the wrong thing.
"""

import argparse
import asyncio
import wave

import pytest
from wyoming.tts import Synthesize

from wyoming_piper.handler import PiperEventHandler


def _handler(monkeypatch: pytest.MonkeyPatch, error: Exception) -> PiperEventHandler:
    cli_args = argparse.Namespace(
        backend="piper",
        voice="en_US-lessac-medium",
        speaker=None,
        auto_punctuation=".?!",
        sentence_silence=None,
        samples_per_chunk=1024,
        no_streaming=True,
    )
    handler = PiperEventHandler(
        lambda: None,  # type: ignore[arg-type,return-value]
        cli_args,
        {},
        asyncio.StreamReader(),
        None,
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(handler, "_synthesize_piper", fail)
    return handler


@pytest.mark.asyncio
async def test_synthesis_error_is_not_masked_by_the_wave_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing phonemizer surfaces as itself, not as a wave error."""
    handler = _handler(monkeypatch, ModuleNotFoundError("No module named 'tltk'"))

    with pytest.raises(ModuleNotFoundError, match="tltk"):
        await handler._handle_synthesize(Synthesize(text="สวัสดี"))


@pytest.mark.asyncio
async def test_wave_error_is_not_raised_for_an_empty_synthesis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Specifically, the old '# channels not specified' must be gone."""
    handler = _handler(monkeypatch, RuntimeError("backend exploded"))

    with pytest.raises(RuntimeError) as excinfo:
        await handler._handle_synthesize(Synthesize(text="hello"))

    assert not isinstance(excinfo.value, wave.Error)
    assert "channels" not in str(excinfo.value)
