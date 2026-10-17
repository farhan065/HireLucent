"""What every speech-to-text service shares: one live connection per person.

The worker hands each person's audio to a sink for the chosen service
(deepgram.py or assemblyai.py). Every sink works the same way: it sends the
audio in small pieces and reads back the text. Final text becomes turns
(see turns.py), which are saved as soon as each one is complete. The words
of the turn still being spoken, and each saved turn, are also handed to
the worker, which sends them to the interviewer's screen. Each service only
says how to connect, which messages to send and how to read its replies.

- Raw audio is never stored. It is sent and dropped.
- The text is never logged: each saved turn is logged with its speaker,
  times and number of words only.
- If the connection drops, the sink connects again. Audio from the last
  thirty seconds waits in a queue meanwhile, so short drops lose nothing.
- A message that cannot be read, or an error message, is skipped and
  logged by its kind only; the connection carries on.
- The delay between speaking and the text arriving is measured, and only
  its numbers are logged when the stream finishes.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus, WebSocketException

from app.core.logging import get_logger, log_event
from app.workers.turns import AudioClock, DelayMeter, Turn

logger = get_logger(__name__)

# The audio format sent: 16 kHz, one channel, 16-bit.
SAMPLE_RATE = 16000
# Audio is sent in pieces of a tenth of a second (16-bit, one channel).
CHUNK_SECONDS = 0.1
CHUNK_BYTES = int(SAMPLE_RATE * 2 * CHUNK_SECONDS)
# Up to thirty seconds of audio waits while the connection is down.
QUEUE_CHUNKS = 300
# How long the sink waits for audio before sending a keep-alive message, for
# a service that needs one while a person is muted.
KEEP_ALIVE_SECONDS = 4
# Waits between connection attempts start here and double up to the maximum.
# The maximum is short, so the sink is back within seconds of the network
# returning, well before the thirty-second queue fills and audio is lost.
FIRST_RETRY_SECONDS = 1
MAX_RETRY_SECONDS = 5
# How long closing may take to collect the last words.
CLOSE_TIMEOUT_SECONDS = 10

# Saves a turn and returns its id.
SaveTurn = Callable[[Turn], Awaitable[int]]
# Sends one live transcript event to the interviewer's screen.
Publish = Callable[[dict], Awaitable[None]]


def next_wait(wait: float) -> float:
    """The wait before the next connection attempt: double the last one,
    never more than the maximum."""
    return min(wait * 2, MAX_RETRY_SECONDS)


def pace_wait(
    sent_seconds: float, elapsed_seconds: float, speed: float, head_start: float
) -> float:
    """How long to wait before sending more audio, for a service that refuses
    audio sent much faster than it is spoken. Up to "speed" times real time
    is allowed after a head start, so audio queued during a drop still
    catches up."""
    allowed = head_start + elapsed_seconds * speed
    return max(sent_seconds - allowed, 0) / speed


class StreamingSink:
    """Transcribes one person's audio in one interview. Each service's sink
    fills in the parts marked below."""

    # Its name in the logs.
    PROVIDER = ""
    # Sent while there is no audio, or None when the service needs nothing.
    KEEP_ALIVE: dict | None = None
    # Sent to say no more audio will come; the service then sends the last
    # words and closes the connection.
    CLOSE: dict = {}
    # None sends queued audio at once; a number limits it to that many times
    # real time (see pace_wait).
    CATCH_UP_SPEED: float | None = None
    CATCH_UP_HEAD_START = 1.0

    def __init__(
        self,
        session_id: int,
        speaker: str,
        started_at: datetime,
        keyterms: list[str],
        save: SaveTurn,
        publish: Publish | None = None,
    ):
        self.session_id = session_id
        self.speaker = speaker
        self.started_at = started_at
        self.keyterms = keyterms
        self.save = save
        self.publish = publish
        # True while the connection to the service is down and being retried.
        self.has_problem = False
        self.turns = 0
        self.dropped_chunks = 0
        self.skipped_messages = 0
        self.delays = DelayMeter()
        self._buffer = bytearray()
        # Pieces of audio with the time each one ended; None means "close".
        self._queue: asyncio.Queue[tuple[bytes, datetime] | None] = asyncio.Queue(QUEUE_CHUNKS)
        self._closing = False
        self._task = asyncio.create_task(self._run())

    # --- Filled in by each service ---

    def connection_url(self) -> str:
        raise NotImplementedError

    def headers(self) -> dict[str, str]:
        raise NotImplementedError

    def new_builder(self, clock: AudioClock):
        """What turns this service's messages into turns and live words."""
        raise NotImplementedError

    def is_error(self, message: dict) -> bool:
        """True for an error message from the service."""
        return False

    # --- Shared ---

    async def push(self, pcm: bytes, sample_rate: int) -> None:
        """Add a piece of audio. It is sent in tenth-of-a-second pieces."""
        self._buffer.extend(pcm)
        while len(self._buffer) >= CHUNK_BYTES:
            self._queue_chunk(bytes(self._buffer[:CHUNK_BYTES]))
            del self._buffer[:CHUNK_BYTES]

    def _queue_chunk(self, chunk: bytes) -> None:
        try:
            self._queue.put_nowait((chunk, datetime.now(timezone.utc)))
        except asyncio.QueueFull:
            self.dropped_chunks += 1

    async def close(self) -> None:
        """Send the rest of the audio, save the last words and disconnect."""
        if self._buffer:
            self._queue_chunk(bytes(self._buffer))
            self._buffer.clear()
        self._closing = True
        if self._queue.full():
            # Make room for the close signal by dropping the oldest audio.
            self._queue.get_nowait()
            self.dropped_chunks += 1
        self._queue.put_nowait(None)
        try:
            await asyncio.wait_for(asyncio.shield(self._task), CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            self._task.cancel()
        log_event(
            logger,
            "stt_stream_finished",
            session_id=self.session_id,
            speaker=self.speaker,
            provider=self.PROVIDER,
            turns=self.turns,
            dropped_chunks=self.dropped_chunks,
            skipped_messages=self.skipped_messages,
            **self.delays.summary(),
        )

    async def _run(self) -> None:
        """Stay connected until closed, connecting again after a drop."""
        wait = FIRST_RETRY_SECONDS
        while True:
            try:
                async with connect(
                    self.connection_url(), additional_headers=self.headers(), open_timeout=10
                ) as connection:
                    log_event(
                        logger,
                        "stt_connected",
                        session_id=self.session_id,
                        speaker=self.speaker,
                        provider=self.PROVIDER,
                        keyterms=len(self.keyterms),
                    )
                    wait = FIRST_RETRY_SECONDS
                    self.has_problem = False
                    if await self._stream(connection):
                        return
            except InvalidStatus as exc:
                # For example 401 when the key is wrong, 402 when the credit
                # has run out.
                self._log_problem("stt_refused", status=exc.response.status_code, retry_in=wait)
            except ConnectionClosed as exc:
                # The service closed the connection; its close code says why
                # (for example 1008 for a wrong key or no credit left).
                code = exc.rcvd.code if exc.rcvd else None
                self._log_problem(
                    "stt_disconnected", error_type=type(exc).__name__, code=code, retry_in=wait
                )
            except (OSError, TimeoutError, WebSocketException) as exc:
                self._log_problem("stt_disconnected", error_type=type(exc).__name__, retry_in=wait)
            if self._closing:
                return
            self.has_problem = True
            await asyncio.sleep(wait)
            wait = next_wait(wait)

    def _log_problem(self, event: str, **fields) -> None:
        log_event(
            logger,
            event,
            level=logging.WARNING,
            session_id=self.session_id,
            speaker=self.speaker,
            provider=self.PROVIDER,
            **fields,
        )

    async def _stream(self, connection: ClientConnection) -> bool:
        """Send audio and read results on one connection. Returns True when
        the sink was closed, False when the connection dropped."""
        builder = self.new_builder(AudioClock(self.started_at))
        sender = asyncio.create_task(self._send(connection, builder.clock))
        try:
            async for raw in connection:
                if isinstance(raw, str):
                    await self._read(builder, raw)
        finally:
            for turn in _as_list(builder.flush()):
                await self._save(turn)
            await self._send_live(builder)
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
        return sender.done() and not sender.cancelled() and sender.exception() is None

    async def _send(self, connection: ClientConnection, clock: AudioClock) -> None:
        """Send queued audio, with keep-alive messages while there is none if
        the service needs them. Ends after telling the service that no more
        audio will come."""
        loop = asyncio.get_running_loop()
        opened = loop.time()
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), KEEP_ALIVE_SECONDS)
            except TimeoutError:
                if self.KEEP_ALIVE is not None:
                    await connection.send(json.dumps(self.KEEP_ALIVE))
                continue
            if item is None:
                await connection.send(json.dumps(self.CLOSE))
                return
            chunk, ended_at = item
            if self.CATCH_UP_SPEED:
                wait = pace_wait(
                    clock.sent_seconds,
                    loop.time() - opened,
                    self.CATCH_UP_SPEED,
                    self.CATCH_UP_HEAD_START,
                )
                if wait:
                    await asyncio.sleep(wait)
            clock.add(len(chunk) / (SAMPLE_RATE * 2), ended_at)
            await connection.send(chunk)

    async def _read(self, builder, raw: str) -> None:
        """Handle one message. One that cannot be read is skipped, so a bad
        message never ends the connection or loses the turn being built."""
        try:
            message = json.loads(raw)
            if self.is_error(message):
                # Its wording is not logged; the service closes the connection
                # itself if the error is serious, and the sink connects again.
                self._log_problem("stt_error_message")
                return
            await self._handle(builder, message)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            self.skipped_messages += 1
            self._log_problem("stt_message_skipped", error_type=type(exc).__name__)

    async def _handle(self, builder, message: dict) -> None:
        """Save each finished turn, and send the words still being spoken
        whenever they change."""
        self._measure(builder, message)
        before = builder.live_text
        for turn in _as_list(builder.handle(message)):
            await self._save(turn)
        if builder.live_text != before:
            await self._send_live(builder)

    def _measure(self, builder, message: dict) -> None:
        """Record how long the text took to arrive after its last word was
        spoken. Messages without words (silence) are not counted."""
        point = builder.spoken_end(message)
        if point is None:
            return
        kind, audio_seconds = point
        self.delays.add(kind, builder.clock.spoken_at(audio_seconds), datetime.now(timezone.utc))

    async def _send_live(self, builder) -> None:
        """The words of the current turn so far; empty text clears them."""
        await self._publish(
            {
                "type": "live",
                "speaker": self.speaker,
                "start_ms": builder.live_start_ms,
                "text": builder.live_text,
            }
        )

    async def _save(self, turn: Turn | None) -> None:
        if turn is None:
            return
        try:
            turn_id = await self.save(turn)
        except Exception as exc:
            self._log_problem("transcript_turn_not_saved", error_type=type(exc).__name__)
            return
        self.turns += 1
        # Numbers only: what was said is never logged.
        log_event(
            logger,
            "transcript_turn_saved",
            session_id=self.session_id,
            speaker=self.speaker,
            start_ms=turn.start_ms,
            end_ms=turn.end_ms,
            words=len(turn.text.split()),
        )
        await self._publish(
            {
                "type": "turn",
                "id": turn_id,
                "speaker": turn.speaker,
                "start_ms": turn.start_ms,
                "end_ms": turn.end_ms,
                "text": turn.text,
            }
        )

    async def _publish(self, event: dict) -> None:
        """Send to the interviewer's screen. A failure only affects the live
        view: the turn is already saved and loads again from the database."""
        if self.publish is None:
            return
        try:
            await self.publish(event)
        except Exception:
            pass


def _as_list(result: Turn | list[Turn] | None) -> list[Turn]:
    """A builder gives back no turn, one turn or several."""
    if result is None:
        return []
    return result if isinstance(result, list) else [result]
