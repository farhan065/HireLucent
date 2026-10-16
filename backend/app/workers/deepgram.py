"""Speech-to-text with Deepgram: one live connection per person.

The worker hands each person's audio to a DeepgramSink. The sink sends the
audio in small pieces and reads back the text. Final text becomes turns
(see turns.py), which are saved as soon as each one is complete. The words
of the turn still being spoken, and each saved turn, are also handed to
the worker, which sends them to the interviewer's screen.

- Raw audio is never stored. It is sent and dropped.
- The text is never logged: each saved turn is logged with its speaker,
  times and number of words only.
- Deepgram is asked not to keep the audio for improving its models.
- If the connection drops, the sink connects again. Audio from the last
  thirty seconds waits in a queue meanwhile, so short drops lose nothing.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import urlencode

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import InvalidStatus, WebSocketException

from app.core.config import get_settings
from app.core.logging import get_logger, log_event
from app.workers.turns import AudioClock, Turn, TurnBuilder

logger = get_logger(__name__)

# The audio format sent: 16 kHz, one channel, 16-bit.
SAMPLE_RATE = 16000
# Audio is sent in pieces of a tenth of a second (16-bit, one channel).
CHUNK_SECONDS = 0.1
CHUNK_BYTES = int(SAMPLE_RATE * 2 * CHUNK_SECONDS)
# Up to thirty seconds of audio waits while the connection is down.
QUEUE_CHUNKS = 300
# Deepgram closes a connection that receives nothing for about ten seconds,
# for example while a person is muted. A keep-alive message prevents that.
KEEP_ALIVE_SECONDS = 4
# Waits between connection attempts start here and double up to the maximum.
FIRST_RETRY_SECONDS = 1
MAX_RETRY_SECONDS = 30
# How long closing may take to collect the last words.
CLOSE_TIMEOUT_SECONDS = 10

# Saves a turn and returns its id.
SaveTurn = Callable[[Turn], Awaitable[int]]
# Sends one live transcript event to the interviewer's screen.
Publish = Callable[[dict], Awaitable[None]]


def listen_url(keyterms: list[str]) -> str:
    """The address of a live connection: English, interim results, and a
    pause of 300 ms ending a piece of speech."""
    settings = get_settings()
    params = [
        ("model", settings.deepgram_model),
        ("language", "en"),
        ("encoding", "linear16"),
        ("sample_rate", str(SAMPLE_RATE)),
        ("channels", "1"),
        ("interim_results", "true"),
        ("smart_format", "true"),
        ("endpointing", "300"),
        ("utterance_end_ms", "1000"),
        ("mip_opt_out", "true"),
    ]
    params += [("keyterm", term) for term in keyterms]
    return f"{settings.deepgram_url}?{urlencode(params)}"


class DeepgramSink:
    """Transcribes one person's audio in one interview."""

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
        # True while the connection to Deepgram is down and being retried.
        self.has_problem = False
        self.turns = 0
        self.dropped_chunks = 0
        self._buffer = bytearray()
        # Pieces of audio with the time each one ended; None means "close".
        self._queue: asyncio.Queue[tuple[bytes, datetime] | None] = asyncio.Queue(QUEUE_CHUNKS)
        self._closing = False
        self._task = asyncio.create_task(self._run())

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
            turns=self.turns,
            dropped_chunks=self.dropped_chunks,
        )

    async def _run(self) -> None:
        """Stay connected until closed, connecting again after a drop."""
        settings = get_settings()
        wait = FIRST_RETRY_SECONDS
        while True:
            try:
                async with connect(
                    listen_url(self.keyterms),
                    additional_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
                    open_timeout=10,
                ) as connection:
                    log_event(
                        logger,
                        "stt_connected",
                        session_id=self.session_id,
                        speaker=self.speaker,
                        keyterms=len(self.keyterms),
                    )
                    wait = FIRST_RETRY_SECONDS
                    self.has_problem = False
                    if await self._stream(connection):
                        return
            except InvalidStatus as exc:
                # 401 means the key is wrong; 402 that the credit has run out.
                self._log_problem("stt_refused", status=exc.response.status_code, retry_in=wait)
            except (OSError, TimeoutError, WebSocketException) as exc:
                self._log_problem("stt_disconnected", error_type=type(exc).__name__, retry_in=wait)
            if self._closing:
                return
            self.has_problem = True
            await asyncio.sleep(wait)
            wait = min(wait * 2, MAX_RETRY_SECONDS)

    def _log_problem(self, event: str, **fields) -> None:
        log_event(
            logger,
            event,
            level=logging.WARNING,
            session_id=self.session_id,
            speaker=self.speaker,
            **fields,
        )

    async def _stream(self, connection: ClientConnection) -> bool:
        """Send audio and read results on one connection. Returns True when
        the sink was closed, False when the connection dropped."""
        builder = TurnBuilder(self.speaker, AudioClock(self.started_at))
        sender = asyncio.create_task(self._send(connection, builder.clock))
        try:
            async for raw in connection:
                if isinstance(raw, str):
                    await self._handle(builder, json.loads(raw))
        finally:
            await self._save(builder.flush())
            await self._send_live(builder)
            if not sender.done():
                sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
        return sender.done() and not sender.cancelled() and sender.exception() is None

    async def _send(self, connection: ClientConnection, clock: AudioClock) -> None:
        """Send queued audio, with keep-alive messages while there is none.
        Ends after telling Deepgram that no more audio will come."""
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), KEEP_ALIVE_SECONDS)
            except TimeoutError:
                await connection.send(json.dumps({"type": "KeepAlive"}))
                continue
            if item is None:
                await connection.send(json.dumps({"type": "CloseStream"}))
                return
            chunk, ended_at = item
            clock.add(len(chunk) / (SAMPLE_RATE * 2), ended_at)
            await connection.send(chunk)

    async def _handle(self, builder: TurnBuilder, message: dict) -> None:
        """Save a finished turn, and send the words still being spoken
        whenever they change."""
        before = builder.live_text
        await self._save(builder.handle(message))
        if builder.live_text != before:
            await self._send_live(builder)

    async def _send_live(self, builder: TurnBuilder) -> None:
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
