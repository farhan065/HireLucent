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
from app.workers import assemblyai, capture, deepgram, stt_stream
from app.workers.turns import (
    MAX_TURN_SECONDS,
    AssemblyTurnBuilder,
    AudioClock,
    DelayMeter,
    Turn,
    TurnBuilder,
)

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


@pytest.mark.parametrize(
    ("provider", "key"), [("off", "key"), ("deepgram", ""), ("assemblyai", "")]
)
def test_without_speech_to_text_the_audio_is_only_measured(
    monkeypatch: pytest.MonkeyPatch, provider: str, key: str
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "stt_provider", provider)
    monkeypatch.setattr(settings, "deepgram_api_key", key)
    monkeypatch.setattr(settings, "assemblyai_api_key", key)

    sink = capture.open_sink(9, "candidate", STARTED, [], save=None)

    assert isinstance(sink, capture.MeterSink)
    assert capture.stt_enabled() is False


@pytest.mark.parametrize(
    ("provider", "sink_class"),
    [("deepgram", deepgram.DeepgramSink), ("assemblyai", assemblyai.AssemblyAISink)],
)
def test_the_service_is_chosen_by_stt_provider(
    monkeypatch: pytest.MonkeyPatch, provider: str, sink_class: type
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "stt_provider", provider)
    monkeypatch.setattr(settings, f"{provider}_api_key", "key")

    async def scenario() -> None:
        sink = capture.open_sink(9, "candidate", STARTED, [], save=None)
        sink._task.cancel()
        assert type(sink) is sink_class

    asyncio.run(scenario())
    assert capture.stt_enabled() is True


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
                if not answered and received >= stt_stream.CHUNK_BYTES * 10:
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
    monkeypatch: pytest.MonkeyPatch,
    fake,
    seconds: float,
    sent: list | None = None,
    provider: str = "deepgram",
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
            monkeypatch.setattr(settings, f"{provider}_url", f"ws://127.0.0.1:{port}")
            monkeypatch.setattr(settings, f"{provider}_api_key", "test-key")
            monkeypatch.setattr(stt_stream, "FIRST_RETRY_SECONDS", 0.01)
            monkeypatch.setattr(stt_stream, "MAX_RETRY_SECONDS", 0.05)
            sink = capture.SINKS[provider](
                9, "interviewer", datetime.now(timezone.utc), [], save, publish
            )
            # Audio arrives in 10 ms frames, as from the video room.
            frame = bytes(stt_stream.CHUNK_BYTES // 10)
            for _ in range(int(seconds * 100)):
                await sink.push(frame, stt_stream.SAMPLE_RATE)
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
    assert fake.audio_bytes == stt_stream.CHUNK_BYTES * 15
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
    waits = [stt_stream.FIRST_RETRY_SECONDS]
    for _ in range(5):
        waits.append(stt_stream.next_wait(waits[-1]))

    # Back within seconds of the network returning, before the queue is full.
    assert waits == [1, 2, 4, 5, 5, 5]
    assert stt_stream.MAX_RETRY_SECONDS * 2 < stt_stream.QUEUE_CHUNKS * stt_stream.CHUNK_SECONDS


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


# --- AssemblyAI ---


def _turn_message(
    text: str, order: int, start_ms: int, end_ms: int, *, end=False, formatted=False
) -> dict:
    return {
        "type": "Turn",
        "turn_order": order,
        "end_of_turn": end,
        "turn_is_formatted": formatted,
        "transcript": text,
        "words": [{"text": text, "start": start_ms, "end": end_ms, "word_is_final": end}],
    }


def _assembly_builder() -> AssemblyTurnBuilder:
    clock = AudioClock(STARTED)
    clock.add(60.0, _at(70))  # audio began 10 s after the interview started
    return AssemblyTurnBuilder("candidate", clock)


def test_assemblyai_connection_asks_for_formatted_turns_and_keywords() -> None:
    url = assemblyai.listen_url(["FastAPI", "scikit learn"])
    query = parse_qs(urlsplit(url).query)

    assert urlsplit(url).netloc == "streaming.assemblyai.com"
    assert query["encoding"] == ["pcm_s16le"] and query["sample_rate"] == ["16000"]
    assert query["format_turns"] == ["true"]
    assert query["speech_model"] == ["universal-streaming-english"]
    assert json.loads(query["keyterms_prompt"][0]) == ["FastAPI", "scikit learn"]
    assert "keyterms_prompt" not in parse_qs(urlsplit(assemblyai.listen_url([])).query)


def test_assemblyai_words_are_live_until_the_formatted_turn_is_saved() -> None:
    builder = _assembly_builder()

    assert builder.handle(_turn_message("we used alembic", 0, 2000, 3500)) == []
    assert builder.live_text == "we used alembic"
    assert builder.live_start_ms == 12_000
    # The finished turn comes first without punctuation, then formatted.
    assert builder.handle(_turn_message("we used alembic", 0, 2000, 3500, end=True)) == []
    assert builder.live_text == ""
    [turn] = builder.handle(
        _turn_message("We used Alembic.", 0, 2000, 3500, end=True, formatted=True)
    )

    assert turn == Turn("candidate", 12_000, 13_500, "We used Alembic.")
    # A repeat of a saved turn is not saved twice.
    assert builder.handle(
        _turn_message("We used Alembic.", 0, 2000, 3500, end=True, formatted=True)
    ) == []
    assert builder.flush() == []


def test_assemblyai_a_finished_turn_without_formatting_is_still_saved() -> None:
    builder = _assembly_builder()
    builder.handle(_turn_message("first answer", 0, 1000, 2000, end=True))

    # The next turn starts before the formatted copy came.
    [turn] = builder.handle(_turn_message("second", 1, 3000, 3400))
    assert turn.text == "first answer"

    builder.handle(_turn_message("second answer", 1, 3000, 4000, end=True))
    # The connection ends before the formatted copy came.
    assert [t.text for t in builder.flush()] == ["second answer"]


def test_assemblyai_live_text_includes_words_not_yet_sure() -> None:
    builder = _assembly_builder()
    message = {
        "type": "Turn",
        "turn_order": 0,
        "end_of_turn": False,
        "transcript": "tell me",
        "words": [
            {"text": "tell", "start": 1000, "end": 1200, "word_is_final": True},
            {"text": "me", "start": 1200, "end": 1300, "word_is_final": True},
            {"text": "about", "start": 1300, "end": 1500, "word_is_final": False},
        ],
    }

    builder.handle(message)

    # The newest word shows at once, before AssemblyAI is sure of it.
    assert builder.live_text == "tell me about"
    assert AssemblyTurnBuilder.spoken_end({**message, "transcript": ""}) == ("live", 1.5)


def test_assemblyai_silence_and_other_messages_save_nothing() -> None:
    builder = _assembly_builder()

    assert builder.handle({"type": "Begin", "id": "abc"}) == []
    silence = {**_turn_message("", 0, 0, 0, end=True, formatted=True), "words": []}
    assert builder.handle(silence) == []
    assert builder.handle({"type": "Termination", "audio_duration_seconds": 5}) == []


def test_assemblyai_delay_counts_live_words_and_the_saved_turn() -> None:
    live = _turn_message("hello", 0, 0, 800)
    unformatted = _turn_message("hello", 0, 0, 800, end=True)
    formatted = _turn_message("Hello.", 0, 0, 800, end=True, formatted=True)

    assert AssemblyTurnBuilder.spoken_end(live) == ("live", 0.8)
    assert AssemblyTurnBuilder.spoken_end(unformatted) is None
    assert AssemblyTurnBuilder.spoken_end(formatted) == ("final", 0.8)


def test_queued_audio_catches_up_at_most_one_and_a_half_times_real_time() -> None:
    # Within the head start: send at once.
    assert stt_stream.pace_wait(0.5, 0.0, 1.5, 1.0) == 0
    # 4 s of audio after 1 s: 2.5 s allowed, so wait until the rest is due.
    assert stt_stream.pace_wait(4.0, 1.0, 1.5, 1.0) == pytest.approx(1.0)


class FakeAssemblyAI:
    """A local stand-in for AssemblyAI's streaming endpoint. After a second
    of audio it sends live words, the finished turn and its formatted copy;
    it answers Terminate with Termination and closes."""

    def __init__(self, refuse: bool = False):
        self.refuse = refuse
        self.headers: list[str] = []
        self.terminated = False

    async def handler(self, connection) -> None:
        self.headers.append(connection.request.headers.get("Authorization"))
        if self.refuse:
            await connection.close(code=1008, reason="Unauthorized Connection: Invalid API key")
            return
        received = 0
        answered = False
        async for message in connection:
            if isinstance(message, bytes):
                received += len(message)
                if not answered and received >= stt_stream.CHUNK_BYTES * 10:
                    answered = True
                    for reply in (
                        _turn_message("answer", 0, 0, 900),
                        _turn_message("answer one", 0, 0, 1000, end=True),
                        _turn_message("Answer one.", 0, 0, 1000, end=True, formatted=True),
                    ):
                        await connection.send(json.dumps(reply))
            elif json.loads(message)["type"] == "Terminate":
                self.terminated = True
                await connection.send(json.dumps({"type": "Termination"}))
                await connection.close()
                return


def test_assemblyai_speech_is_sent_and_each_turn_saved(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    fake = FakeAssemblyAI()
    sent: list[dict] = []

    saved = _run_sink(monkeypatch, fake, seconds=1.5, sent=sent, provider="assemblyai")

    # The key goes as it is, and the stream ends with Terminate.
    assert fake.headers == ["test-key"]
    assert fake.terminated is True
    assert [(turn.speaker, turn.text) for turn in saved] == [("interviewer", "Answer one.")]
    assert {"type": "live", "speaker": "interviewer", "text": "answer"}.items() <= sent[0].items()
    [finished] = [r for r in caplog.records if r.getMessage() == "stt_stream_finished"]
    assert finished.fields["provider"] == "assemblyai"
    assert "final_delay_avg_ms" in finished.fields and "live_delay_avg_ms" in finished.fields


def test_a_refused_connection_is_logged_by_its_close_code(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    saved = _run_sink(monkeypatch, FakeAssemblyAI(refuse=True), seconds=0.3, provider="assemblyai")

    assert saved == []
    refused = [r for r in caplog.records if r.getMessage() == "stt_disconnected"]
    assert refused and refused[0].fields["code"] == 1008
    # The reason given by the service is not logged.
    assert "Invalid API key" not in str(refused[0].fields)


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
