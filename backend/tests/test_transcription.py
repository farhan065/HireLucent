"""Tests for speech-to-text: turn times, joining final pieces into turns,
the job keywords, the live connection (against a local stand-in for
Deepgram, so no network or key is needed) and the transcript endpoint."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from websockets.asyncio.server import serve

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import create_app
from app.models import InterviewSession, TranscriptTurn
from app.models.enums import UserRole
from app.services import transcript_service
from app.workers import capture, deepgram
from app.workers.turns import MAX_TURN_SECONDS, AudioClock, DelayMeter, Turn, TurnBuilder

STARTED = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)


def _at(seconds: float) -> datetime:
    return STARTED + timedelta(seconds=seconds)


def _result(text: str, start: float, duration: float, *, final=True, pause=False) -> dict:
    return {
        "type": "Results",
        "is_final": final,
        "speech_final": pause,
        "start": start,
        "duration": duration,
        "channel": {"alternatives": [{"transcript": text, "confidence": 0.9}]},
    }


# --- Turn times ---


def test_times_count_from_the_start_of_the_interview() -> None:
    # The worker joined 10 seconds after the start and sends audio steadily.
    clock = AudioClock(STARTED)
    for step in range(1, 21):
        clock.add(0.1, _at(10 + step * 0.1))

    assert clock.elapsed_ms(0) == 10_000
    assert clock.elapsed_ms(1.5) == 11_500


def test_a_muted_gap_moves_the_clock_to_the_real_time() -> None:
    clock = AudioClock(STARTED)
    for step in range(1, 11):
        clock.add(0.1, _at(step * 0.1))
    # Muted for 5 seconds: no audio, then it comes back.
    for step in range(1, 11):
        clock.add(0.1, _at(6 + step * 0.1))

    assert clock.elapsed_ms(0.5) == 500
    # One second of audio was sent before the gap, so 1.2 s of audio is
    # 0.2 s after the audio came back at 6 s.
    assert clock.elapsed_ms(1.2) == 6_200


# --- Joining final pieces into turns ---


def _builder() -> TurnBuilder:
    clock = AudioClock(STARTED)
    clock.add(0.1, _at(0.1))
    return TurnBuilder("candidate", clock)


def test_interim_text_is_not_saved() -> None:
    builder = _builder()

    assert builder.handle(_result("I built a", 0, 1, final=False)) is None
    assert builder.flush() is None


def test_the_words_being_spoken_are_kept_until_the_turn_is_saved() -> None:
    builder = _builder()

    builder.handle(_result("I built a", 1.0, 1.0, final=False))
    assert builder.live_text == "I built a"
    builder.handle(_result("I built a REST API", 1.0, 1.5))
    builder.handle(_result("with", 2.5, 0.3, final=False))
    assert builder.live_text == "I built a REST API with"
    assert builder.live_start_ms == 1000

    builder.handle(_result("with FastAPI.", 2.5, 1.0, pause=True))
    assert builder.live_text == ""


def test_final_pieces_become_one_turn_at_a_pause() -> None:
    builder = _builder()

    assert builder.handle(_result("I built a REST API", 1.0, 1.5)) is None
    turn = builder.handle(_result("with FastAPI.", 2.5, 1.0, pause=True))

    assert turn == Turn("candidate", 1000, 3500, "I built a REST API with FastAPI.")
    assert builder.flush() is None


def test_utterance_end_closes_the_turn() -> None:
    builder = _builder()
    builder.handle(_result("Yes.", 4.0, 0.5))

    turn = builder.handle({"type": "UtteranceEnd", "last_word_end": 4.5})

    assert turn is not None and turn.text == "Yes."


def test_silence_and_empty_results_save_nothing() -> None:
    builder = _builder()

    assert builder.handle(_result("", 0, 3, pause=True)) is None
    assert builder.handle({"type": "Metadata"}) is None
    assert builder.handle({"type": "UtteranceEnd"}) is None


def test_a_long_answer_is_saved_without_waiting_for_a_pause() -> None:
    builder = _builder()
    turns = [
        builder.handle(_result(f"part {index}", index * 10.0, 10.0))
        for index in range(MAX_TURN_SECONDS // 10 + 1)
    ]

    saved = [turn for turn in turns if turn]
    assert len(saved) == 1 and saved[0].end_ms - saved[0].start_ms >= MAX_TURN_SECONDS * 1000


# --- Job keywords ---


def test_keyterms_put_must_haves_first_without_repeats_or_everyday_words() -> None:
    requirements = {
        "items": [
            {"priority": "preferred", "keywords": ["kubernetes", "python"]},
            {"priority": "must_have", "keywords": ["python", "fastapi", "team", "Data"]},
        ]
    }

    assert transcript_service.keyterms(requirements) == ["python", "fastapi", "kubernetes"]


def test_keyterms_are_limited() -> None:
    requirements = {"items": [{"keywords": [f"tool{index}" for index in range(80)]}]}

    assert len(transcript_service.keyterms(requirements)) == transcript_service.MAX_KEYTERMS


def test_the_connection_asks_for_english_interim_text_and_no_model_training() -> None:
    query = parse_qs(urlsplit(deepgram.listen_url(["fastapi", "scikit learn"])).query)

    assert query["language"] == ["en"] and query["interim_results"] == ["true"]
    assert query["mip_opt_out"] == ["true"]
    assert query["keyterm"] == ["fastapi", "scikit learn"]
    assert "keyterm" not in parse_qs(urlsplit(deepgram.listen_url([])).query)


# --- Which sink is used ---


@pytest.mark.parametrize(("provider", "key"), [("off", "key"), ("deepgram", "")])
def test_without_speech_to_text_the_audio_is_only_measured(
    monkeypatch: pytest.MonkeyPatch, provider: str, key: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "stt_provider", provider)
    monkeypatch.setattr(settings, "deepgram_api_key", key)

    sink = capture.open_sink(9, "candidate", STARTED, [], save=None)

    assert isinstance(sink, capture.MeterSink)


# --- The live connection ---


class FakeDeepgram:
    """A local stand-in for Deepgram's live endpoint. It answers the first
    second of audio with one final result, and closes when told to."""

    def __init__(self, drop_first: bool = False, before: list[str] | None = None):
        self.drop_first = drop_first
        # Messages sent before the answer, for example ones that cannot be read.
        self.before = before or []
        self.connections = 0
        self.headers: list[str] = []
        self.audio_bytes = 0
        self.closed_by_client = False

    async def handler(self, connection) -> None:
        self.connections += 1
        self.headers.append(connection.request.headers.get("Authorization"))
        received = 0
        answered = False
        async for message in connection:
            if isinstance(message, bytes):
                received += len(message)
                self.audio_bytes += len(message)
                if not answered and received >= deepgram.CHUNK_BYTES * 10:
                    answered = True
                    for extra in self.before:
                        await connection.send(extra)
                    text = f"answer {self.connections}"
                    await connection.send(json.dumps(_result(text, 0.0, 1.0, pause=True)))
                    if self.drop_first and self.connections == 1:
                        await connection.close(code=1011)
                        return
            elif json.loads(message)["type"] == "CloseStream":
                self.closed_by_client = True
                await connection.close()
                return


def _run_sink(
    monkeypatch: pytest.MonkeyPatch, fake: FakeDeepgram, seconds: float, sent: list | None = None
) -> list:
    saved: list[Turn] = []

    async def save(turn: Turn) -> int:
        saved.append(turn)
        return len(saved)

    async def publish(event: dict) -> None:
        if sent is not None:
            sent.append(event)

    async def scenario() -> None:
        async with serve(fake.handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            settings = get_settings()
            monkeypatch.setattr(settings, "deepgram_url", f"ws://127.0.0.1:{port}")
            monkeypatch.setattr(settings, "deepgram_api_key", "test-key")
            monkeypatch.setattr(deepgram, "FIRST_RETRY_SECONDS", 0.01)
            monkeypatch.setattr(deepgram, "MAX_RETRY_SECONDS", 0.05)
            sink = deepgram.DeepgramSink(
                9, "interviewer", datetime.now(timezone.utc), [], save, publish
            )
            # Audio arrives in 10 ms frames, as from the video room.
            frame = bytes(deepgram.CHUNK_BYTES // 10)
            for _ in range(int(seconds * 100)):
                await sink.push(frame, deepgram.SAMPLE_RATE)
                await asyncio.sleep(0.001)
            await asyncio.sleep(0.3)
            await sink.close()

    asyncio.run(scenario())
    return saved


def test_speech_is_sent_and_each_turn_saved(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    fake = FakeDeepgram()
    sent: list[dict] = []

    saved = _run_sink(monkeypatch, fake, seconds=1.5, sent=sent)

    assert fake.headers == ["Token test-key"]
    assert fake.audio_bytes == deepgram.CHUNK_BYTES * 15
    assert fake.closed_by_client is True
    assert [(turn.speaker, turn.text) for turn in saved] == [("interviewer", "answer 1")]
    # The saved turn goes to the interviewer's screen with its id.
    assert sent[0] == {
        "type": "turn",
        "id": 1,
        "speaker": "interviewer",
        "start_ms": sent[0]["start_ms"],
        "end_ms": sent[0]["end_ms"],
        "text": "answer 1",
    }
    # Each saved turn is logged with numbers only, never its words.
    [logged] = [r for r in caplog.records if r.getMessage() == "transcript_turn_saved"]
    assert logged.fields["speaker"] == "interviewer" and logged.fields["words"] == 2
    assert "answer" not in str(logged.fields)


def test_a_dropped_connection_is_opened_again(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDeepgram(drop_first=True)

    saved = _run_sink(monkeypatch, fake, seconds=3)

    assert fake.connections == 2
    assert [turn.text for turn in saved] == ["answer 1", "answer 2"]


def test_bad_and_error_messages_are_skipped_without_losing_text(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    bad_start = {**_result("half", 0.0, 0.5, final=False), "start": "soon"}
    fake = FakeDeepgram(
        before=[
            "not json",
            json.dumps([1, 2]),
            json.dumps(bad_start),
            json.dumps({"type": "Error", "description": "something went wrong"}),
            json.dumps({"type": "Metadata"}),
        ]
    )

    saved = _run_sink(monkeypatch, fake, seconds=1.5)

    # The connection carried on and the answer after the bad messages was saved.
    assert fake.connections == 1
    assert [turn.text for turn in saved] == ["answer 1"]
    skipped = [r for r in caplog.records if r.getMessage() == "stt_message_skipped"]
    assert [r.fields["error_type"] for r in skipped] == [
        "JSONDecodeError",
        "AttributeError",
        "ValueError",
    ]
    [error] = [r for r in caplog.records if r.getMessage() == "stt_error_message"]
    assert "went wrong" not in str(error.fields)
    [finished] = [r for r in caplog.records if r.getMessage() == "stt_stream_finished"]
    assert finished.fields["skipped_messages"] == 3


def test_the_delay_is_measured_and_logged_as_numbers(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    _run_sink(monkeypatch, FakeDeepgram(), seconds=1.5)

    [finished] = [r for r in caplog.records if r.getMessage() == "stt_stream_finished"]
    delays = {key: value for key, value in finished.fields.items() if "delay" in key}
    # One final result arrived; there were no live words to measure.
    assert set(delays) == {"final_delay_avg_ms", "final_delay_p95_ms", "final_delay_max_ms"}
    assert all(isinstance(value, int) and 0 <= value < 5000 for value in delays.values())


def test_retries_wait_at_most_five_seconds() -> None:
    waits = [deepgram.FIRST_RETRY_SECONDS]
    for _ in range(5):
        waits.append(deepgram.next_wait(waits[-1]))

    # Back within seconds of the network returning, before the queue is full.
    assert waits == [1, 2, 4, 5, 5, 5]
    assert deepgram.MAX_RETRY_SECONDS * 2 < deepgram.QUEUE_CHUNKS * deepgram.CHUNK_SECONDS


# --- Delay ---


def test_the_clock_time_of_a_point_in_the_audio() -> None:
    clock = AudioClock(STARTED)
    clock.add(1.0, _at(11))

    assert clock.spoken_at(0.5) == _at(10.5)


def test_the_delay_meter_keeps_average_slowest_and_maximum() -> None:
    meter = DelayMeter()
    for delay in range(100, 2100, 100):
        meter.add("live", _at(0), _at(delay / 1000))
    meter.add("final", _at(5), _at(4))

    assert meter.summary() == {
        "live_delay_avg_ms": 1050,
        "live_delay_p95_ms": 1900,
        "live_delay_max_ms": 2000,
        # Clocks that disagree never give a delay below zero.
        "final_delay_avg_ms": 0,
        "final_delay_p95_ms": 0,
        "final_delay_max_ms": 0,
    }


def test_without_text_no_delay_is_reported() -> None:
    assert DelayMeter().summary() == {}


# --- Reading the transcript ---


class FakeDB:
    def __init__(self, session, turns):
        self.session = session
        self.turns = turns

    def get(self, model, key):
        return self.session if model is InterviewSession and key == self.session.id else None

    def scalars(self, _query):
        return iter(self.turns)


def test_each_turn_has_its_clock_time() -> None:
    session = InterviewSession(id=9, job_id=2, candidate_id=5, started_at=STARTED)
    turn = TranscriptTurn(
        id=1, session_id=9, speaker="candidate", start_ms=65_000, end_ms=68_000, text="Hello."
    )

    transcript = transcript_service.read_transcript(FakeDB(session, [turn]), 9)

    [item] = transcript["turns"]
    assert item["spoken_at"] == STARTED + timedelta(seconds=65)
    assert item["speaker"] == "candidate" and item["text"] == "Hello."


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        transcript_service,
        "read_transcript",
        lambda db, session_id: {
            "session_id": session_id,
            "started_at": STARTED,
            "turns": [
                SimpleNamespace(
                    id=1,
                    speaker="interviewer",
                    start_ms=0,
                    end_ms=1500,
                    spoken_at=STARTED,
                    text="Welcome.",
                ).__dict__
            ],
        },
    )
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def test_interviewer_reads_the_transcript(client: TestClient) -> None:
    response = client.get("/interviews/9/transcript", headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    assert response.json()["turns"][0]["text"] == "Welcome."


def test_candidate_cannot_read_the_transcript(client: TestClient) -> None:
    response = client.get("/interviews/9/transcript", headers=_auth(UserRole.CANDIDATE))

    assert response.status_code == 403


# --- The status the interviewer's screen shows ---


@pytest.mark.parametrize(
    ("provider", "key", "problem", "expected"),
    [
        ("deepgram", "key", False, "listening"),
        ("deepgram", "key", True, "paused"),
        ("deepgram", "", False, "off"),
        ("off", "key", False, "off"),
    ],
)
def test_the_status_says_whether_transcription_works(
    monkeypatch: pytest.MonkeyPatch, provider: str, key: str, problem: bool, expected: str
) -> None:
    pytest.importorskip("livekit.rtc")
    from app.workers import transcription_worker as worker

    settings = get_settings()
    monkeypatch.setattr(settings, "stt_provider", provider)
    monkeypatch.setattr(settings, "deepgram_api_key", key)
    listener = worker.InterviewListener.__new__(worker.InterviewListener)
    listener._sinks = {"candidate": SimpleNamespace(has_problem=problem)}

    assert listener.status() == expected
