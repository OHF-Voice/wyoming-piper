"""Tests that a finished text stream doesn't swallow later requests."""

import argparse
import asyncio
import wave
from typing import List

import pytest
from wyoming.audio import AudioStart, AudioStop
from wyoming.event import Event
from wyoming.tts import Synthesize, SynthesizeChunk, SynthesizeStart, SynthesizeStop

from wyoming_piper.handler import PiperEventHandler


def _handler(monkeypatch: pytest.MonkeyPatch) -> PiperEventHandler:
    cli_args = argparse.Namespace(
        backend="piper",
        voice="en_US-lessac-medium",
        speaker=None,
        auto_punctuation=".?!",
        sentence_silence=None,
        samples_per_chunk=1024,
        no_streaming=False,
    )
    handler = PiperEventHandler(
        lambda: None,  # type: ignore[arg-type,return-value]
        cli_args,
        {},
        asyncio.StreamReader(),
        None,
    )

    def synthesize(
        text: str, wav_writer: wave.Wave_write, *args: object, **kwargs: object
    ) -> None:
        wav_writer.setframerate(22050)
        wav_writer.setsampwidth(2)
        wav_writer.setnchannels(1)
        wav_writer.writeframes(bytes(100))

    monkeypatch.setattr(handler, "_synthesize_piper", synthesize)
    return handler


@pytest.mark.asyncio
async def test_synthesize_after_stream_is_spoken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain synthesize on the same connection after a stream gets audio."""
    handler = _handler(monkeypatch)
    events: List[Event] = []

    async def write_event(event: Event) -> None:
        events.append(event)

    monkeypatch.setattr(handler, "write_event", write_event)

    await handler.handle_event(SynthesizeStart().event())
    await handler.handle_event(SynthesizeChunk(text="Streamed text.").event())
    await handler.handle_event(Synthesize(text="Streamed text.").event())
    await handler.handle_event(SynthesizeStop().event())

    events.clear()
    await handler.handle_event(Synthesize(text="Not streamed.").event())

    assert any(AudioStart.is_type(event.type) for event in events)
    assert events and AudioStop.is_type(events[-1].type)
