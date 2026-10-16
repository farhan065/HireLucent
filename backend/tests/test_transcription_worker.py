"""Tests for the transcription worker's audio capture: which interviews it
listens to, how one person's audio is measured, and its listen-only pass."""

import asyncio
import logging
from datetime import timedelta

import jwt
import numpy as np
import pytest

from app.core.config import get_settings
from app.services import video
from app.workers import capture

SECRET = "s" * 32


def _pcm(level: int, seconds: float = 1.0) -> bytes:
    samples = np.full(int(capture.SAMPLE_RATE * seconds), level, dtype=np.int16)
    return samples.tobytes()


def test_running_interviews_are_joined_and_ended_ones_left() -> None:
    to_start, to_stop = capture.plan(running={1, 2, 3}, listening={2, 4})

    assert to_start == {1, 3}
    assert to_stop == {4}


def test_speech_and_silence_are_measured_separately() -> None:
    sink = capture.MeterSink(9, "candidate")

    asyncio.run(sink.push(_pcm(4000, 2.0), capture.SAMPLE_RATE))
    asyncio.run(sink.push(_pcm(0, 1.0), capture.SAMPLE_RATE))

    assert sink.seconds == pytest.approx(3.0)
    assert sink.speech_seconds == pytest.approx(2.0)


def test_only_numbers_are_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    sink = capture.MeterSink(9, "interviewer")

    asyncio.run(sink.push(_pcm(4000, capture.REPORT_EVERY_SECONDS), capture.SAMPLE_RATE))
    asyncio.run(sink.close())

    events = [record.getMessage() for record in caplog.records]
    assert events == ["audio_stream_started", "audio_stream_progress", "audio_stream_finished"]
    assert caplog.records[-1].fields == {
        "session_id": 9,
        "speaker": "interviewer",
        "seconds": capture.REPORT_EVERY_SECONDS,
        "speech_seconds": capture.REPORT_EVERY_SECONDS,
    }


def test_the_worker_pass_is_hidden_and_listen_only(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "livekit_api_key", "devkey")
    monkeypatch.setattr(settings, "livekit_api_secret", SECRET)

    token = video.create_room_token(
        "interview-9",
        "transcription-worker",
        "Transcription",
        timedelta(minutes=5),
        hidden=True,
        can_publish=False,
    )

    grants = jwt.decode(token, SECRET, algorithms=["HS256"])["video"]
    assert grants["room"] == "interview-9" and grants["hidden"] is True
    assert grants["canSubscribe"] is True
    assert grants["canPublish"] is False and grants["canPublishData"] is False


# --- One stream per person ---


class _Track:
    def __init__(self, kind) -> None:
        self.kind = kind


class _Publication:
    def __init__(self, sid: str) -> None:
        self.sid = sid


class _Person:
    def __init__(self, identity: str) -> None:
        self.identity = identity


def test_a_rejoining_person_keeps_one_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    rtc = pytest.importorskip("livekit.rtc")
    from app.workers import transcription_worker as worker

    async def scenario() -> tuple:
        listener = worker.InterviewListener.__new__(worker.InterviewListener)
        listener.session_id = 9
        listener._streams = {}

        async def capture_forever(track, speaker):
            await asyncio.Event().wait()

        monkeypatch.setattr(listener, "_capture", capture_forever)
        track = _Track(rtc.TrackKind.KIND_AUDIO)
        candidate = _Person("candidate")

        listener._on_subscribed(track, _Publication("TR_old"), candidate)
        first = listener._streams["candidate"][1]
        # The same track again changes nothing.
        listener._on_subscribed(track, _Publication("TR_old"), candidate)
        assert listener._streams["candidate"][1] is first
        # After a reload, the new track replaces the old one.
        listener._on_subscribed(track, _Publication("TR_new"), candidate)
        await asyncio.sleep(0)
        streams = dict(listener._streams)
        # Leaving ends the stream.
        listener._on_left(candidate)
        await asyncio.sleep(0)
        return first.cancelled(), streams, dict(listener._streams)

    old_cancelled, streams, after_leaving = asyncio.run(scenario())

    assert old_cancelled is True
    assert list(streams) == ["candidate"] and streams["candidate"][0] == "TR_new"
    assert after_leaving == {}
