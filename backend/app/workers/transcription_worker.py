"""The transcription worker: each person's audio from running interviews.

Every few seconds it looks for interviews in progress. For each one it joins
the interview's video room as a hidden, listen-only participant, so the two
people never see it, and receives the interviewer's and the candidate's
microphones as two separate streams. Video is never received. Each stream
goes to an audio sink (see capture.py). When an interview ends, the worker
leaves its room.

If the worker restarts, or loses a room, it joins again on the next check.

Run with:  python -m app.workers.transcription_worker
"""

import asyncio
import logging
from datetime import datetime, timezone

from livekit import rtc
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.db.session import SessionLocal
from app.models import InterviewSession
from app.models.enums import SessionStatus
from app.services import video
from app.services.room_service import PASS_EXTRA
from app.workers import capture

logger = get_logger(__name__)

IDENTITY = "transcription-worker"


class InterviewListener:
    """Listens to one interview's room: one audio stream per person.

    A person who reloads the page or rejoins comes back with a new
    microphone track. Their old stream is closed first, so each person
    always has exactly one stream."""

    def __init__(self, session_id: int, scheduled_end: datetime):
        self.session_id = session_id
        self.scheduled_end = scheduled_end
        self.room = rtc.Room()
        # Per speaker: the microphone track being captured and its task.
        self._streams: dict[str, tuple[str, asyncio.Task]] = {}

    @property
    def is_connected(self) -> bool:
        return self.room.isconnected()

    async def start(self) -> None:
        now = datetime.now(timezone.utc)
        token = video.create_room_token(
            video.room_name(self.session_id),
            IDENTITY,
            "Transcription",
            max(self.scheduled_end, now) + PASS_EXTRA - now,
            hidden=True,
            can_publish=False,
        )
        self.room.on("track_published", self._on_published)
        self.room.on("track_subscribed", self._on_subscribed)
        self.room.on("track_unsubscribed", self._on_unsubscribed)
        self.room.on("participant_disconnected", self._on_left)
        # Nothing is received unless asked for, so video never arrives.
        options = rtc.RoomOptions(auto_subscribe=False)
        await self.room.connect(get_settings().capture_livekit_url, token, options)
        for participant in self.room.remote_participants.values():
            for publication in participant.track_publications.values():
                self._on_published(publication, participant)
        log_event(logger, "interview_audio_joined", session_id=self.session_id)

    def _on_published(
        self, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant
    ) -> None:
        """Ask for the microphone of each person in the interview."""
        is_microphone = publication.source == rtc.TrackSource.SOURCE_MICROPHONE
        if is_microphone and participant.identity in capture.SPEAKERS:
            publication.set_subscribed(True)

    def _on_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        speaker = participant.identity
        if track.kind != rtc.TrackKind.KIND_AUDIO or speaker not in capture.SPEAKERS:
            return
        current = self._streams.get(speaker)
        if current and current[0] == publication.sid:
            return
        # A new track replaces the speaker's old one.
        self._end_stream(speaker)
        task = asyncio.create_task(self._capture(track, speaker))
        self._streams[speaker] = (publication.sid, task)
        task.add_done_callback(lambda done: self._forget(speaker, done))

    def _on_unsubscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        current = self._streams.get(participant.identity)
        if current and current[0] == publication.sid:
            self._end_stream(participant.identity)

    def _on_left(self, participant: rtc.RemoteParticipant) -> None:
        self._end_stream(participant.identity)

    def _end_stream(self, speaker: str) -> None:
        current = self._streams.pop(speaker, None)
        if current:
            current[1].cancel()

    def _forget(self, speaker: str, task: asyncio.Task) -> None:
        current = self._streams.get(speaker)
        if current and current[1] is task:
            del self._streams[speaker]

    async def _capture(self, track: rtc.Track, speaker: str) -> None:
        """Pass one person's audio to its sink until their track ends."""
        sink = capture.open_sink(self.session_id, speaker)
        stream = rtc.AudioStream(
            track, sample_rate=capture.SAMPLE_RATE, num_channels=capture.CHANNELS
        )
        try:
            async for event in stream:
                sink.push(bytes(event.frame.data), event.frame.sample_rate)
        finally:
            sink.close()
            await stream.aclose()

    async def stop(self) -> None:
        tasks = [task for _, task in self._streams.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.room.disconnect()
        log_event(logger, "interview_audio_left", session_id=self.session_id)


def running_interviews() -> dict[int, datetime]:
    """Interviews in progress, with their planned end."""
    with SessionLocal() as db:
        rows = db.execute(
            select(InterviewSession.id, InterviewSession.scheduled_end).where(
                InterviewSession.status == SessionStatus.IN_PROGRESS
            )
        )
        return {session_id: end for session_id, end in rows}


async def run() -> None:
    settings = get_settings()
    listeners: dict[int, InterviewListener] = {}
    log_event(logger, "transcription_worker_started")
    while True:
        try:
            running = await asyncio.to_thread(running_interviews)
        except Exception as exc:
            log_event(
                logger, "worker_db_unavailable", level=logging.WARNING, error_type=type(exc).__name__
            )
            running = None

        if running is not None:
            # A room that dropped is left, so it is joined again below.
            lost = {sid for sid, listener in listeners.items() if not listener.is_connected}
            to_start, to_stop = capture.plan(set(running), set(listeners) - lost)
            for session_id in to_stop | lost:
                listener = listeners.pop(session_id, None)
                if listener:
                    await listener.stop()
            for session_id in to_start:
                listener = InterviewListener(session_id, running[session_id])
                try:
                    await listener.start()
                    listeners[session_id] = listener
                except Exception as exc:
                    # Tried again on the next check.
                    await listener.room.disconnect()
                    log_event(
                        logger,
                        "interview_audio_join_failed",
                        level=logging.WARNING,
                        session_id=session_id,
                        error_type=type(exc).__name__,
                    )
        await asyncio.sleep(settings.capture_poll_seconds)


if __name__ == "__main__":
    configure_logging(get_settings())
    asyncio.run(run())
