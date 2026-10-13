"""The audio side of the transcription worker, kept free of LiveKit so it can
be tested on its own.

Each person in an interview has their own audio stream, labelled by who
they are, so speech is never mixed and never guessed. A stream is handed to
an audio sink: today the sink only measures how much audio arrived and how
much of it was speech; in Module 5 the speech-to-text sink takes its place.

Raw audio is never stored. Each piece is measured in memory and dropped, and
only the numbers are logged.
"""

from typing import Protocol

import numpy as np

from app.core.logging import get_logger, log_event

logger = get_logger(__name__)

# Audio as speech-to-text services expect it: 16 kHz, one channel, 16-bit.
SAMPLE_RATE = 16000
CHANNELS = 1
# The people whose audio is captured, by their identity in the room.
SPEAKERS = {"interviewer", "candidate"}
# A piece louder than this (16-bit RMS, about -36 dBFS) counts as speech.
SPEECH_LEVEL = 500
# How often a running stream reports its numbers, in seconds of audio.
REPORT_EVERY_SECONDS = 30


class AudioSink(Protocol):
    """Where one person's audio goes, one piece at a time."""

    def push(self, pcm: bytes, sample_rate: int) -> None: ...

    def close(self) -> None: ...


class MeterSink:
    """Measures one person's audio and logs only the numbers."""

    def __init__(self, session_id: int, speaker: str):
        self.session_id = session_id
        self.speaker = speaker
        self.seconds = 0.0
        self.speech_seconds = 0.0
        self._next_report = REPORT_EVERY_SECONDS
        log_event(logger, "audio_stream_started", session_id=session_id, speaker=speaker)

    def push(self, pcm: bytes, sample_rate: int) -> None:
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

    def close(self) -> None:
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


def open_sink(session_id: int, speaker: str) -> AudioSink:
    """The sink for one person's audio in one interview."""
    return MeterSink(session_id, speaker)


def plan(running: set[int], listening: set[int]) -> tuple[set[int], set[int]]:
    """Which interviews to start and stop listening to: every running
    interview is listened to, and nothing else."""
    return running - listening, listening - running
