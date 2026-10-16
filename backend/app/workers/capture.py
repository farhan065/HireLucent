"""The audio side of the transcription worker, kept free of LiveKit so it can
be tested on its own.

Each person in an interview has their own audio stream, labelled by who
they are, so speech is never mixed and never guessed. A stream is handed to
an audio sink: the speech-to-text sink (deepgram.py), or, when speech-to-text
is off or has no key, a sink that only measures how much audio arrived.

Raw audio is never stored. Each piece is handled in memory and dropped, and
only numbers are logged.
"""

import logging
from datetime import datetime
from typing import Protocol

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.workers import deepgram

logger = get_logger(__name__)

# Audio as speech-to-text services expect it: 16 kHz, one channel, 16-bit.
SAMPLE_RATE = deepgram.SAMPLE_RATE
CHANNELS = 1
# The people whose audio is captured, by their identity in the room.
SPEAKERS = {"interviewer", "candidate"}
# A piece louder than this (16-bit RMS, about -36 dBFS) counts as speech.
SPEECH_LEVEL = 500
# How often a running stream reports its numbers, in seconds of audio.
REPORT_EVERY_SECONDS = 30


class AudioSink(Protocol):
    """Where one person's audio goes, one piece at a time."""

    async def push(self, pcm: bytes, sample_rate: int) -> None: ...

    async def close(self) -> None: ...


class MeterSink:
    """Measures one person's audio and logs only the numbers."""

    def __init__(self, session_id: int, speaker: str):
        self.session_id = session_id
        self.speaker = speaker
        self.seconds = 0.0
        self.speech_seconds = 0.0
        self._next_report = REPORT_EVERY_SECONDS
        log_event(logger, "audio_stream_started", session_id=session_id, speaker=speaker)

    async def push(self, pcm: bytes, sample_rate: int) -> None:
        samples = np.frombuffer(pcm, dtype=np.int16)
        if samples.size == 0:
            return
        duration = samples.size / sample_rate
        self.seconds += duration
        level = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
        if level >= SPEECH_LEVEL:
            self.speech_seconds += duration
        if self.seconds >= self._next_report:
            self._next_report += REPORT_EVERY_SECONDS
            self._log("audio_stream_progress")

    async def close(self) -> None:
        self._log("audio_stream_finished")

    def _log(self, event: str) -> None:
        log_event(
            logger,
            event,
            session_id=self.session_id,
            speaker=self.speaker,
            seconds=round(self.seconds, 1),
            speech_seconds=round(self.speech_seconds, 1),
        )


def open_sink(
    session_id: int,
    speaker: str,
    started_at: datetime,
    keyterms: list[str],
    save: deepgram.SaveTurn,
) -> AudioSink:
    """The sink for one person's audio in one interview."""
    settings = get_settings()
    if settings.stt_provider == "deepgram":
        if settings.deepgram_api_key:
            return deepgram.DeepgramSink(session_id, speaker, started_at, keyterms, save)
        log_event(logger, "stt_not_configured", level=logging.WARNING, session_id=session_id)
    return MeterSink(session_id, speaker)


def plan(running: set[int], listening: set[int]) -> tuple[set[int], set[int]]:
    """Which interviews to start and stop listening to: every running
    interview is listened to, and nothing else."""
    return running - listening, listening - running
