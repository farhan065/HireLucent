"""From speech-to-text results to transcript turns, kept free of the network
so it can be tested on its own.

Each person's audio is transcribed on its own connection, so every result
already belongs to one speaker. Every service sends two kinds of text:

- interim text while the person is still speaking, which keeps changing;
- final text, which no longer changes.

TurnBuilder reads Deepgram, which sends final pieces: they are joined into
one turn until the person pauses, and a turn that grows very long is saved
anyway, so a long answer is saved as it goes. AssemblyTurnBuilder reads
AssemblyAI, which sends each whole turn itself once the person stops.
Each turn gets its time from the start of the interview. How long the text
took to arrive after the words were spoken is measured too, as numbers only.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

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

    def spoken_at(self, audio_seconds: float) -> datetime:
        """The clock time at which this point of the audio was spoken."""
        return self.started_at + timedelta(milliseconds=self.elapsed_ms(audio_seconds))


class DelayMeter:
    """How long text took to arrive after its words were spoken, in
    milliseconds: "live" for the words still being spoken, "final" for text
    that no longer changes. Only numbers are kept, never the words."""

    KINDS = ("live", "final")

    def __init__(self):
        self._delays: dict[str, list[int]] = {kind: [] for kind in self.KINDS}

    def add(self, kind: str, spoken_at: datetime, arrived_at: datetime) -> None:
        delay = round((arrived_at - spoken_at).total_seconds() * 1000)
        self._delays[kind].append(max(delay, 0))

    def summary(self) -> dict[str, int]:
        """The average, the slowest 5% and the slowest delay of each kind,
        for example {"live_delay_avg_ms": 640, ...}. Kinds with no text
        are left out."""
        numbers: dict[str, int] = {}
        for kind, delays in self._delays.items():
            if not delays:
                continue
            ordered = sorted(delays)
            numbers[f"{kind}_delay_avg_ms"] = round(sum(ordered) / len(ordered))
            numbers[f"{kind}_delay_p95_ms"] = ordered[math.ceil(len(ordered) * 0.95) - 1]
            numbers[f"{kind}_delay_max_ms"] = ordered[-1]
        return numbers


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

    @staticmethod
    def spoken_end(message: dict) -> tuple[str, float] | None:
        """For measuring the delay: "live" or "final", and the position in
        the audio where the message's words end. None without words."""
        if message.get("type") != "Results":
            return None
        alternatives = message.get("channel", {}).get("alternatives") or [{}]
        if not (alternatives[0].get("transcript") or "").strip():
            return None
        end = float(message.get("start", 0)) + float(message.get("duration", 0))
        return ("final" if message.get("is_final") else "live"), end


class AssemblyTurnBuilder:
    """Reads one person's AssemblyAI messages.

    Each "Turn" message carries the whole turn so far, with every word's
    time in milliseconds from the start of the connection. While the person
    speaks, "transcript" holds only the words AssemblyAI is already sure of;
    the newest words are only in "words", so the live text is built from all
    of "words" and appears as soon as each word is heard. When they stop,
    the turn arrives with
    "end_of_turn" set, then once more with punctuation and capitals
    ("turn_is_formatted"). The formatted one is saved. A finished turn whose
    formatted copy never comes is saved when the next turn starts, or when
    the connection ends, so nothing is lost.
    """

    def __init__(self, speaker: str, clock: AudioClock):
        self.speaker = speaker
        self.clock = clock
        self._live = ""
        self._live_start = 0.0
        # A finished turn still waiting for its formatted copy.
        self._pending: tuple[int, Turn] | None = None
        self._saved_up_to = -1

    @property
    def live_text(self) -> str:
        return self._live

    @property
    def live_start_ms(self) -> int:
        return self.clock.elapsed_ms(self._live_start)

    def handle(self, message: dict) -> list[Turn]:
        """Read one message. Returns the turns that are complete."""
        if message.get("type") != "Turn":
            return []
        order = int(message.get("turn_order", 0))
        done: list[Turn] = []
        if self._pending and self._pending[0] != order:
            done.append(self.flush_pending())
        if order <= self._saved_up_to:
            return done
        text = (message.get("transcript") or "").strip()
        words = message.get("words") or []
        if not message.get("end_of_turn"):
            self._live = _spoken(words) or text
            if words:
                self._live_start = words[0]["start"] / 1000
            return done
        self._live = ""
        if not text:
            self._saved_up_to = order
            self._pending = None
            return done
        turn = self._turn(text, words)
        if message.get("turn_is_formatted"):
            self._pending = None
            self._saved_up_to = order
            done.append(turn)
        else:
            self._pending = (order, turn)
        return done

    def flush_pending(self) -> Turn:
        order, turn = self._pending
        self._pending = None
        self._saved_up_to = max(self._saved_up_to, order)
        return turn

    def flush(self) -> list[Turn]:
        """The finished turn still waiting, if any. Words that were never
        finished are dropped with the connection, as with Deepgram."""
        self._live = ""
        return [self.flush_pending()] if self._pending else []

    def _turn(self, text: str, words: list[dict]) -> Turn:
        start = words[0]["start"] / 1000 if words else self._live_start
        end = words[-1]["end"] / 1000 if words else start
        return Turn(
            speaker=self.speaker,
            start_ms=self.clock.elapsed_ms(start),
            end_ms=self.clock.elapsed_ms(end),
            text=text,
        )

    @staticmethod
    def spoken_end(message: dict) -> tuple[str, float] | None:
        """For measuring the delay: "live" while the person speaks, "final"
        for the formatted turn that is saved; the position in the audio where
        its words end. None without words."""
        if message.get("type") != "Turn":
            return None
        words = message.get("words") or []
        if not _spoken(words):
            return None
        if not message.get("end_of_turn"):
            kind = "live"
        elif message.get("turn_is_formatted"):
            kind = "final"
        else:
            return None
        return kind, words[-1]["end"] / 1000


def _spoken(words: list[dict]) -> str:
    """Every word heard so far in an AssemblyAI turn, sure or not yet."""
    return " ".join(word.get("text", "") for word in words).strip()
