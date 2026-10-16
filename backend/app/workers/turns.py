"""From speech-to-text results to transcript turns, kept free of the network
so it can be tested on its own.

Each person's audio is transcribed on its own connection, so every result
already belongs to one speaker. The service sends two kinds of text:

- interim text while the person is still speaking, which keeps changing;
- final pieces, which no longer change.

Final pieces are joined into one turn until the person pauses. A turn that
grows very long is saved anyway, so a long answer is saved as it goes.
Each turn gets its time from the start of the interview.
"""

from dataclasses import dataclass
from datetime import datetime

# A gap in the audio longer than this (for example while a person is muted)
# moves the clock on to the real time.
GAP_MS = 500
# A turn longer than this is saved without waiting for a pause.
MAX_TURN_SECONDS = 30


@dataclass(frozen=True)
class Turn:
    speaker: str
    # Milliseconds from the start of the interview.
    start_ms: int
    end_ms: int
    text: str


class AudioClock:
    """Turns a position in the audio sent on one connection into the time
    since the interview started.

    The service counts time in audio received. When a person is muted, no
    audio is sent, so its count falls behind the real clock. Each time the
    audio comes back after a gap, a new anchor ties the two together again.
    """

    def __init__(self, started_at: datetime):
        self.started_at = started_at
        self.sent_seconds = 0.0
        # (seconds of audio sent, milliseconds since the start) pairs.
        self._anchors: list[tuple[float, float]] = []

    def add(self, seconds: float, ended_at: datetime) -> None:
        """Record a piece of audio of this length that ended at this time."""
        began_ms = max((ended_at - self.started_at).total_seconds() * 1000 - seconds * 1000, 0)
        if not self._anchors or began_ms - self.elapsed_ms(self.sent_seconds) > GAP_MS:
            self._anchors.append((self.sent_seconds, began_ms))
        self.sent_seconds += seconds

    def elapsed_ms(self, audio_seconds: float) -> int:
        """Milliseconds since the interview started at this audio position."""
        if not self._anchors:
            return 0
        sent, elapsed = self._anchors[0]
        for anchor in self._anchors:
            if anchor[0] > audio_seconds:
                break
            sent, elapsed = anchor
        return round(elapsed + (audio_seconds - sent) * 1000)


class TurnBuilder:
    """Joins one person's final pieces into turns, and keeps the words of
    the turn still being spoken for the live transcript."""

    def __init__(self, speaker: str, clock: AudioClock):
        self.speaker = speaker
        self.clock = clock
        self._texts: list[str] = []
        self._start = 0.0
        self._end = 0.0
        # The latest interim text, which may still change.
        self._interim = ""
        self._interim_start = 0.0

    @property
    def live_text(self) -> str:
        """Everything said in the current turn so far: its final pieces and
        the interim words after them. Empty between turns."""
        return " ".join([*self._texts, self._interim]).strip()

    @property
    def live_start_ms(self) -> int:
        return self.clock.elapsed_ms(self._start if self._texts else self._interim_start)

    def handle(self, message: dict) -> Turn | None:
        """Read one message from the service. Returns a turn when one is
        complete."""
        kind = message.get("type")
        if kind == "UtteranceEnd":
            return self.flush()
        if kind != "Results":
            return None
        alternatives = message.get("channel", {}).get("alternatives") or [{}]
        text = (alternatives[0].get("transcript") or "").strip()
        if not message.get("is_final"):
            self._interim = text
            self._interim_start = float(message.get("start", 0))
            return None
        self._interim = ""
        if text:
            start = float(message.get("start", 0))
            if not self._texts:
                self._start = start
            self._texts.append(text)
            self._end = start + float(message.get("duration", 0))
        if message.get("speech_final") or self._end - self._start >= MAX_TURN_SECONDS:
            return self.flush()
        return None

    def flush(self) -> Turn | None:
        """The turn so far, if any, and start a new one."""
        self._interim = ""
        if not self._texts:
            return None
        turn = Turn(
            speaker=self.speaker,
            start_ms=self.clock.elapsed_ms(self._start),
            end_ms=self.clock.elapsed_ms(self._end),
            text=" ".join(self._texts),
        )
        self._texts = []
        return turn
