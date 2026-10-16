"""The transcription worker: each person's speech in running interviews,
turned into text.

Every few seconds it looks for interviews in progress. For each one it joins
the interview's video room as a hidden, listen-only participant, so the two
people never see it, and receives the interviewer's and the candidate's
microphones as two separate streams. Video is never received. Each stream
goes to an audio sink (see capture.py), which transcribes it; every finished
turn is saved at once with its speaker and time. When an interview ends,
the worker leaves its room.

The live transcript is sent over the room to the interviewer only, never to
the candidate: the words still being spoken, each saved turn, and every few
seconds a status ("listening", "paused" or "off") so the screen can tell
when transcription is not working.

If the worker restarts, or loses a room, it joins again on the next check,
and the turns saved so far are kept.

Run with:  python -m app.workers.transcription_worker
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from livekit import rtc
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger, log_event
from app.db.session import SessionLocal
from app.models import InterviewSession
from app.models.enums import SessionStatus
from app.services import transcript_service, video
from app.services.room_service import PASS_EXTRA
from app.workers import capture
from app.workers.turns import Turn

logger = get_logger(__name__)

IDENTITY = "transcription-worker"
# The live transcript goes on this topic, to the interviewer only.
TRANSCRIPT_TOPIC = "transcript"
INTERVIEWER = "interviewer"
# How often the status is sent.
STATUS_SECONDS = 5


@dataclass(frozen=True)
class RunningInterview:
    scheduled_end: datetime
    started_at: datetime


class InterviewListener:
    """Listens to one interview's room: one audio stream per person.

    A person who reloads the page or rejoins comes back with a new
    microphone track. Their old stream is closed first, so each person
    always has exactly one stream."""

    def __init__(self, session_id: int, interview: RunningInterview):
        self.session_id = session_id
        self.scheduled_end = interview.scheduled_end
        self.started_at = interview.started_at
        self.keyterms: list[str] = []
        self.room = rtc.Room()
        # Per speaker: the microphone track being captured and its task.
        self._streams: dict[str, tuple[str, asyncio.Task]] = {}
        # Per speaker: the sink their audio goes to, while it is open.
        self._sinks: dict[str, capture.AudioSink] = {}
        self._status_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        return self.room.isconnected()

    async def start(self) -> None:
        if get_settings().stt_keyterms:
            self.keyterms = await asyncio.to_thread(load_keyterms, self.session_id)
        now = datetime.now(timezone.utc)
        token = video.create_room_token(
            video.room_name(self.session_id),
            IDENTITY,
            "Transcription",
            max(self.scheduled_end, now) + PASS_EXTRA - now,
            hidden=True,
            can_publish=False,
            can_publish_data=True,
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
        self._status_task = asyncio.create_task(self._send_status())
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
        sink = capture.open_sink(
            self.session_id,
            speaker,
            self.started_at,
            self.keyterms,
            self._save_turn,
            self._publish,
        )
        self._sinks[speaker] = sink
        stream = rtc.AudioStream(
            track, sample_rate=capture.SAMPLE_RATE, num_channels=capture.CHANNELS
        )
        try:
            async for event in stream:
                await sink.push(bytes(event.frame.data), event.frame.sample_rate)
        finally:
            if self._sinks.get(speaker) is sink:
                del self._sinks[speaker]
            await sink.close()
            await stream.aclose()

    async def _save_turn(self, turn: Turn) -> int:
        return await asyncio.to_thread(save_turn, self.session_id, turn)

    async def _publish(self, event: dict) -> None:
        """Send one live transcript event to the interviewer only."""
        await self.room.local_participant.publish_data(
            json.dumps(event),
            reliable=True,
            topic=TRANSCRIPT_TOPIC,
            destination_identities=[INTERVIEWER],
        )

    def status(self) -> str:
        """The live transcript's state: "off" without speech-to-text,
        "paused" while a connection to it is being retried, otherwise
        "listening"."""
        if not capture.stt_enabled():
            return "off"
        if any(getattr(sink, "has_problem", False) for sink in self._sinks.values()):
            return "paused"
        return "listening"

    async def _send_status(self) -> None:
        while True:
            try:
                await self._publish({"type": "status", "state": self.status()})
            except Exception:
                # The interviewer may not be in the room right now.
                pass
            await asyncio.sleep(STATUS_SECONDS)

    async def stop(self) -> None:
        if self._status_task:
            self._status_task.cancel()
        tasks = [task for _, task in self._streams.values()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.room.disconnect()
        log_event(logger, "interview_audio_left", session_id=self.session_id)


def running_interviews() -> dict[int, RunningInterview]:
    """Interviews in progress, with their planned end and real start."""
    with SessionLocal() as db:
        rows = db.execute(
            select(
                InterviewSession.id,
                InterviewSession.scheduled_end,
                InterviewSession.started_at,
                InterviewSession.scheduled_start,
            ).where(InterviewSession.status == SessionStatus.IN_PROGRESS)
        )
        return {
            session_id: RunningInterview(end, started or planned)
            for session_id, end, started, planned in rows
        }


def load_keyterms(session_id: int) -> list[str]:
    with SessionLocal() as db:
        return transcript_service.keyterms_for_session(db, session_id)


def save_turn(session_id: int, turn: Turn) -> int:
    with SessionLocal() as db:
        return transcript_service.add_turn(
            db, session_id, turn.speaker, turn.start_ms, turn.end_ms, turn.text
        ).id


async def run() -> None:
    settings = get_settings()
    listeners: dict[int, InterviewListener] = {}
    log_event(
        logger,
        "transcription_worker_started",
        stt_provider=settings.stt_provider,
        stt_key_set=bool(settings.deepgram_api_key),
        stt_keyterms=settings.stt_keyterms,
    )
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
