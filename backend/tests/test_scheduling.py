"""Tests for scheduling: times, the calendar invitation, the scheduling
service, the agent's interview tools and the endpoints. Nothing is sent to
Google."""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from pydantic import ValidationError

from app.core.errors import ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.recruiter import interview_tools
from app.graphs.recruiter.tools import EXTERNAL_ACTIONS, PREPARERS, TOOL_HANDLERS
from app.main import create_app
from app.models import Candidate, InterviewSession, Job
from app.models.enums import CandidateStatus, SessionStatus, UserRole
from app.services import interview_emails, interview_times, scheduling_service
from app.services.conversation_view import build_view
from app.services.scheduling_service import Slot

# Tuesday 14 October 2026, 3:00-3:45 PM in Dhaka (GMT+6).
START = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
END = START + timedelta(minutes=45)
LINK = "http://localhost:3000/interview/secret-token"


# --- Times ---


def test_email_time_names_the_zone_and_gives_utc() -> None:
    assert interview_times.describe(START, END) == (
        "Wednesday 14 October 2026, 3:00–3:45 PM (Dhaka, GMT+6) · 9:00–9:45 AM UTC"
    )


def test_utc_on_another_day_names_that_day() -> None:
    early = datetime(2026, 10, 14, 2, 0, tzinfo=timezone(timedelta(hours=6)))
    text = interview_times.describe(early, early + timedelta(minutes=30))

    assert "2:00–2:30 AM (Dhaka, GMT+6)" in text
    assert text.endswith("8:00–8:30 PM UTC on Tuesday 13 October 2026")


def test_a_typed_time_is_read_in_the_app_time_zone() -> None:
    moment = interview_times.parse_local("2026-10-14", "15:00")

    assert moment.astimezone(timezone.utc) == START


def test_the_agent_is_told_the_local_date() -> None:
    text = interview_times.now_description(START)

    assert text == "Now it is Wednesday 14 October 2026, 3:00 PM in Asia/Dhaka (Dhaka, GMT+6)."


# --- Calendar invitation ---


def _order(text: str, *parts: str) -> list[int]:
    return [text.index(part) for part in parts]


def test_invitation_has_the_message_then_the_time_then_the_link() -> None:
    invitation = interview_emails.invitation("Test", "Backend Engineer", START, END, LINK)
    text = invitation.description

    assert invitation.title == "HireLucent video interview – Backend Engineer"
    assert text.startswith("Hello Test,\n\nThank you for applying for the Backend Engineer")
    assert "45-minute" in text
    positions = _order(
        text, "Thank you", "When: ", f"Join the interview: {LINK}", "Before the interview",
        "not recorded", "Best regards",
    )
    assert positions == sorted(positions)
    assert "3:00–3:45 PM (Dhaka, GMT+6)" in text


def test_the_interviewers_message_replaces_only_the_default() -> None:
    message = "Please have your portfolio ready to share on screen."
    text = interview_emails.invitation(
        "Test", "Backend Engineer", START, END, LINK, message
    ).description

    assert "Thank you for applying" not in text
    positions = _order(text, "Hello Test,", message, "When: ", "Join the interview: ")
    assert positions == sorted(positions)


def test_moved_invitation_says_the_old_link_stops_working() -> None:
    text = interview_emails.moved("Test", "Backend Engineer", START, END, LINK).description

    positions = _order(text, "has moved to a new time", "New time: ", "Join the interview: ")
    assert positions == sorted(positions)
    assert "earlier invitation no longer works" in text


def test_cancellation_keeps_the_fixed_sentence_and_uses_the_message() -> None:
    text = interview_emails.cancelled("Test", "Backend Engineer", START, END, "We will call you.")

    assert "has been cancelled" in text
    assert "We will call you." in text
    assert "hiring team will contact you" not in text
    assert "/interview/" not in text


def test_a_message_is_tidied() -> None:
    assert interview_emails.clean_message("  Hello there.  \r\n\n\n\nThanks.  ") == (
        "Hello there.\n\nThanks."
    )


@pytest.mark.parametrize(
    ("message", "problem"),
    [
        ("   ", "cannot be empty"),
        ("a" * 1501, "at most 1500"),
        ("Please <b>bring</b> your CV", "plain text"),
    ],
)
def test_a_bad_message_is_refused(message, problem) -> None:
    with pytest.raises(ValueError, match=problem):
        interview_emails.clean_message(message)


def test_a_message_of_1500_characters_is_fine() -> None:
    assert len(interview_emails.clean_message("a" * 1500)) == 1500


def test_a_preview_names_the_message_and_the_default() -> None:
    preview = interview_emails.preview(
        interview_emails.CANCELLED, "Test", "Backend Engineer", START, END
    )

    assert preview["message"] == preview["default_message"]
    assert preview["default_message"] == "The hiring team will contact you about the next steps."
    assert preview["message"] in preview["text"]


# --- Scheduling service ---


class FakeDB:
    def __init__(self, objects):
        self.objects = objects
        self.commits = 0

    def get(self, model, key):
        return self.objects.get((model, key))

    def commit(self):
        self.commits += 1


def _job_and_candidate():
    job = Job(id=2, title="Backend Engineer")
    candidate = Candidate(
        id=5, job_id=2, full_name="Test Candidate", email="candidate@example.com",
        status=CandidateStatus.SHORTLISTED,
    )
    return job, candidate


def _session(candidate: Candidate) -> InterviewSession:
    session = InterviewSession(
        id=9, candidate_id=candidate.id, job_id=2, scheduled_start=START,
        scheduled_end=END, join_token_hash="hash", status=SessionStatus.SCHEDULED,
        calendar_event_id="event-1",
    )
    session.candidate = candidate
    return session


@pytest.fixture()
def google(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Record Google calls; a tool listed in `fail` raises."""
    record = {"calls": [], "fail": set()}

    def fake(tool, arguments):
        record["calls"].append((tool, arguments))
        if tool in record["fail"]:
            raise ServiceUnavailableError("Google down")
        return {"event_id": "event-1"} if tool == "create_calendar_event" else {}

    monkeypatch.setattr(scheduling_service, "_google", fake)
    return record


def test_scheduling_sends_only_the_calendar_invitation(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    session = _session(candidate)
    monkeypatch.setattr(
        scheduling_service.session_service,
        "create_session",
        lambda *args, **kwargs: (session, "secret-token"),
    )

    [outcome] = scheduling_service.schedule(db, 2, [Slot(5, START, END)], created_by=1)

    assert outcome.status == "scheduled" and outcome.warning is None
    assert [tool for tool, _ in google["calls"]] == ["create_calendar_event"]
    event = google["calls"][0][1]
    assert event["title"] == "HireLucent video interview – Backend Engineer"
    assert event["attendee"] == "candidate@example.com"
    assert event["time_zone"] == "Asia/Dhaka"
    assert event["start"] == "2026-10-14T15:00:00+06:00"
    assert "Join the interview: http://localhost:3000/interview/secret-token" in (
        event["description"]
    )
    assert session.calendar_event_id == "event-1"


def test_scheduling_sends_the_interviewers_message(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    monkeypatch.setattr(
        scheduling_service.session_service,
        "create_session",
        lambda *args, **kwargs: (_session(candidate), "secret-token"),
    )

    scheduling_service.schedule(
        db, 2, [Slot(5, START, END)], created_by=1, message="Bring your portfolio."
    )

    description = google["calls"][0][1]["description"]
    assert "Bring your portfolio." in description
    assert "Thank you for applying" not in description


def test_failed_calendar_removes_the_interview(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    session = _session(candidate)
    discarded = []
    monkeypatch.setattr(
        scheduling_service.session_service,
        "create_session",
        lambda *args, **kwargs: (session, "secret-token"),
    )
    monkeypatch.setattr(
        scheduling_service.session_service, "discard", lambda db, s: discarded.append(s)
    )
    google["fail"].add("create_calendar_event")

    [outcome] = scheduling_service.schedule(db, 2, [Slot(5, START, END)], created_by=1)

    assert outcome.status == "failed" and "nothing was sent" in outcome.error
    assert discarded == [session]
    assert [tool for tool, _ in google["calls"]] == ["create_calendar_event"]


def test_a_candidate_of_another_job_is_not_scheduled(google) -> None:
    job, candidate = _job_and_candidate()
    candidate.job_id = 3
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})

    [outcome] = scheduling_service.schedule(db, 2, [Slot(5, START, END)], created_by=1)

    assert outcome.status == "failed" and google["calls"] == []


def test_a_failed_calendar_update_undoes_the_move(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    session = _session(candidate)
    db = FakeDB({(Job, 2): job})
    later = START + timedelta(days=1)

    def fake_reschedule(db, session_id, start, end):
        session.scheduled_start, session.scheduled_end = start, end
        session.join_token_hash = "new-hash"
        return session, "new-token"

    monkeypatch.setattr(scheduling_service.session_service, "get_session", lambda db, i: session)
    monkeypatch.setattr(scheduling_service.session_service, "reschedule", fake_reschedule)
    google["fail"].add("update_calendar_event")

    with pytest.raises(ServiceUnavailableError, match="Nothing was changed"):
        scheduling_service.reschedule(db, 9, later, later + timedelta(minutes=45))

    assert session.scheduled_start == START and session.join_token_hash == "hash"


def test_cancel_stands_even_when_google_is_down(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    session = _session(candidate)
    session.status = SessionStatus.CANCELLED
    monkeypatch.setattr(scheduling_service.session_service, "cancel", lambda db, i: session)
    google["fail"].add("cancel_calendar_event")

    change = scheduling_service.cancel(FakeDB({(Job, 2): job}), 9)

    assert change.interview.status == "cancelled"
    assert "candidate could not be told" in change.warning
    assert [tool for tool, _ in google["calls"]] == ["cancel_calendar_event"]


def test_cancellation_notice_says_cancelled_without_a_link(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    session = _session(candidate)
    monkeypatch.setattr(scheduling_service.session_service, "cancel", lambda db, i: session)

    change = scheduling_service.cancel(FakeDB({(Job, 2): job}), 9, "We will call you.")

    assert change.warning is None
    [(tool, arguments)] = google["calls"]
    assert tool == "cancel_calendar_event" and arguments["event_id"] == "event-1"
    assert "has been cancelled" in arguments["description"]
    assert "We will call you." in arguments["description"]
    assert "/interview/" not in arguments["description"]


def test_a_move_updates_the_invitation_with_the_new_link(monkeypatch, google) -> None:
    job, candidate = _job_and_candidate()
    session = _session(candidate)
    later = START + timedelta(days=1)
    monkeypatch.setattr(scheduling_service.session_service, "get_session", lambda db, i: session)
    monkeypatch.setattr(
        scheduling_service.session_service,
        "reschedule",
        lambda db, session_id, start, end: (session, "new-token"),
    )

    change = scheduling_service.reschedule(
        FakeDB({(Job, 2): job}), 9, later, later + timedelta(minutes=45)
    )

    assert change.warning is None
    [(tool, event)] = google["calls"]
    assert tool == "update_calendar_event"
    assert "Join the interview: http://localhost:3000/interview/new-token" in (
        event["description"]
    )


# --- The agent's interview tools ---


def test_interview_actions_wait_for_approval() -> None:
    assert {"ScheduleInterviews", "RescheduleInterview", "CancelInterview"} <= EXTERNAL_ACTIONS
    assert "GetCandidates" not in EXTERNAL_ACTIONS
    assert {"ScheduleInterviews", "RescheduleInterview", "CancelInterview"} <= set(PREPARERS)
    assert "GetCandidates" in TOOL_HANDLERS


@contextmanager
def _fake_session_local(db):
    yield db


def test_schedule_card_has_exact_times_and_an_email_preview(monkeypatch) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    monkeypatch.setattr(interview_tools, "SessionLocal", lambda: _fake_session_local(db))
    monkeypatch.setattr(interview_tools.session_service, "check_new", lambda *a, **k: candidate)

    card = interview_tools.prepare_schedule(
        {"interviews": [
            {"candidate_id": 5, "date": "2026-10-14", "start_time": "15:00",
             "duration_minutes": 45},
        ]},
        {"saved_job_id": 2, "user_id": 1},
    )

    [row] = card["interviews"]
    assert row["candidate_name"] == "Test Candidate"
    assert row["start"] == "2026-10-14T15:00:00+06:00"
    assert row["when"].startswith("Wednesday 14 October 2026, 3:00–3:45 PM")
    assert card["time_zone_label"] == "Dhaka, GMT+6"
    assert "[private link]" in card["email_preview"]["text"]
    assert card["message"] is None
    assert card["default_message"].startswith("Thank you for applying")
    assert card["default_message"] in card["email_preview"]["text"]
    assert "candidate@example.com" not in json.dumps(card)


def test_schedule_card_shows_the_interviewers_message(monkeypatch) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    monkeypatch.setattr(interview_tools, "SessionLocal", lambda: _fake_session_local(db))
    monkeypatch.setattr(interview_tools.session_service, "check_new", lambda *a, **k: candidate)

    card = interview_tools.prepare_schedule(
        {"interviews": [{"candidate_id": 5, "date": "2026-10-14", "start_time": "15:00",
                         "duration_minutes": 45}],
         "message": "Bring your portfolio."},
        {"saved_job_id": 2, "user_id": 1},
    )

    assert card["message"] == "Bring your portfolio."
    assert "Bring your portfolio." in card["email_preview"]["text"]
    assert "Thank you for applying" not in card["email_preview"]["text"]


def test_the_cancel_card_has_a_preview_without_a_link(monkeypatch) -> None:
    job, candidate = _job_and_candidate()
    session = _session(candidate)
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    monkeypatch.setattr(interview_tools, "SessionLocal", lambda: _fake_session_local(db))
    monkeypatch.setattr(interview_tools.session_service, "find_scheduled", lambda *a: session)

    card = interview_tools.prepare_cancel({"candidate_id": 5}, {"saved_job_id": 2})

    text = card["email_preview"]["text"]
    assert "has been cancelled" in text
    assert card["default_message"] in text
    assert "[private link]" not in text


def test_the_agent_cannot_send_html_in_a_message() -> None:
    with pytest.raises(ValidationError):
        interview_tools.CancelInterview.model_validate(
            {"candidate_id": 5, "message": "<script>x</script>"}
        )


# --- GetCandidates: each candidate's interview status ---

NOW = START + timedelta(days=1)


def _candidate(status: CandidateStatus) -> Candidate:
    return Candidate(id=5, job_id=2, full_name="Test", status=status)


def _interview(status: SessionStatus, start: datetime) -> InterviewSession:
    return InterviewSession(
        candidate_id=5, job_id=2, status=status, scheduled_start=start,
        scheduled_end=start + timedelta(minutes=45),
    )


def test_a_screened_candidate_is_not_shortlisted() -> None:
    status, when = interview_tools.interview_status(
        _candidate(CandidateStatus.SCREENED), [], NOW
    )

    assert (status, when) == ("not_shortlisted", None)


def test_a_shortlisted_candidate_without_interviews_is_not_invited() -> None:
    status, _ = interview_tools.interview_status(_candidate(CandidateStatus.SHORTLISTED), [], NOW)

    assert status == "shortlisted_not_invited"


def test_an_interviewed_candidate_is_reported_as_interviewed() -> None:
    finished = _interview(SessionStatus.COMPLETED, START)

    status, when = interview_tools.interview_status(
        _candidate(CandidateStatus.INTERVIEW_SCHEDULED), [finished], NOW
    )

    assert status == "interviewed"
    assert when.startswith("Wednesday 14 October 2026")


@pytest.mark.parametrize(
    ("session_status", "start", "expected"),
    [
        (SessionStatus.SCHEDULED, NOW + timedelta(days=1), "interview_scheduled"),
        (SessionStatus.SCHEDULED, NOW - timedelta(hours=2), "interview_missed"),
        (SessionStatus.IN_PROGRESS, NOW, "interview_in_progress"),
    ],
)
def test_an_open_interview_counts_before_a_finished_one(session_status, start, expected) -> None:
    sessions = [_interview(SessionStatus.COMPLETED, START), _interview(session_status, start)]

    status, when = interview_tools.interview_status(
        _candidate(CandidateStatus.INTERVIEW_SCHEDULED), sessions, NOW
    )

    assert status == expected and when


def test_a_rule_problem_names_the_candidate(monkeypatch) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    monkeypatch.setattr(interview_tools, "SessionLocal", lambda: _fake_session_local(db))

    def too_soon(*args, **kwargs):
        raise ConflictError("An interview must start at least 15 minutes from now.")

    monkeypatch.setattr(interview_tools.session_service, "check_new", too_soon)

    with pytest.raises(ConflictError, match="Test Candidate: An interview must start"):
        interview_tools.prepare_schedule(
            {"interviews": [{"candidate_id": 5, "date": "2026-10-14",
                             "start_time": "15:00", "duration_minutes": 45}]},
            {"saved_job_id": 2, "user_id": 1},
        )


def _row(candidate_id: int, name: str, start: str, end: str) -> dict:
    return {"candidate_id": candidate_id, "candidate_name": name, "start": start, "end": end}


def test_two_interviews_at_the_same_time_are_refused() -> None:
    with pytest.raises(ConflictError, match="overlap"):
        interview_tools.check_batch([
            _row(5, "A", "2026-10-14T15:00:00+06:00", "2026-10-14T15:45:00+06:00"),
            _row(6, "B", "2026-10-14T15:30:00+06:00", "2026-10-14T16:15:00+06:00"),
        ])


def test_back_to_back_interviews_are_fine() -> None:
    interview_tools.check_batch([
        _row(5, "A", "2026-10-14T15:00:00+06:00", "2026-10-14T15:45:00+06:00"),
        _row(6, "B", "2026-10-14T15:45:00+06:00", "2026-10-14T16:30:00+06:00"),
    ])


def test_scheduling_needs_a_saved_job() -> None:
    with pytest.raises(ConflictError, match="no saved job"):
        interview_tools.get_candidates({}, {"user_id": 1})


def test_conversation_shows_the_schedule_card_with_its_result() -> None:
    arguments = {"interviews": [{"candidate_name": "Test Candidate"}], "email_preview": {}}
    result = [{"candidate_name": "Test Candidate", "status": "scheduled"}]
    messages = [
        HumanMessage("Schedule Test on Wednesday at 3 pm", id="h1"),
        AIMessage(
            "",
            id="a1",
            tool_calls=[{"name": "ScheduleInterviews", "args": arguments, "id": "c1"}],
        ),
        ToolMessage(interview_tools.SCHEDULED_PREFIX + json.dumps(result), tool_call_id="c1"),
    ]

    view = build_view("t1", {"messages": messages, "saved_job_id": 2}, None, "HL-BE-01")

    card = next(item for item in view.items if item.kind == "schedule")
    assert card.status == "approved"
    assert card.result == result


# --- Endpoints ---


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    return TestClient(app)


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


def _body(*candidate_ids: int) -> dict:
    return {
        "interviews": [
            {"candidate_id": cid, "start": START.isoformat(), "end": END.isoformat()}
            for cid in candidate_ids
        ]
    }


def test_schedule_endpoint_returns_one_result_per_candidate(client, monkeypatch) -> None:
    seen = {}

    def fake_schedule(db, job_id, slots, created_by, message):
        seen.update(job_id=job_id, slots=slots, created_by=created_by, message=message)
        return []

    monkeypatch.setattr(scheduling_service, "schedule", fake_schedule)

    response = client.post("/jobs/2/interviews", json=_body(5), headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    assert seen["job_id"] == 2 and seen["created_by"] == 1
    assert seen["slots"] == [Slot(5, START, END)]
    assert seen["message"] is None


def test_schedule_endpoint_passes_the_message_on(client, monkeypatch) -> None:
    seen = {}
    monkeypatch.setattr(
        scheduling_service,
        "schedule",
        lambda db, job_id, slots, created_by, message: seen.update(message=message) or [],
    )
    body = {**_body(5), "message": "  Bring your portfolio.  "}

    response = client.post("/jobs/2/interviews", json=body, headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    assert seen["message"] == "Bring your portfolio."


@pytest.mark.parametrize("message", ["   ", "a" * 1501, "<b>Hi</b>"])
def test_a_bad_message_is_refused_by_the_endpoints(client, message) -> None:
    headers = _auth(UserRole.INTERVIEWER)
    times = {"start": START.isoformat(), "end": END.isoformat()}

    assert client.post(
        "/jobs/2/interviews", json={**_body(5), "message": message}, headers=headers
    ).status_code == 422
    assert client.put(
        "/interviews/9", json={**times, "message": message}, headers=headers
    ).status_code == 422
    assert client.post(
        "/interviews/9/cancel", json={"message": message}, headers=headers
    ).status_code == 422


def test_cancel_works_with_and_without_a_message(client, monkeypatch) -> None:
    seen = []
    job, candidate = _job_and_candidate()
    change = scheduling_service._change(_session(candidate), None)
    monkeypatch.setattr(
        scheduling_service, "cancel", lambda db, i, message: seen.append(message) or change
    )
    headers = _auth(UserRole.INTERVIEWER)

    assert client.post("/interviews/9/cancel", headers=headers).status_code == 200
    assert client.post(
        "/interviews/9/cancel", json={"message": "We will call you."}, headers=headers
    ).status_code == 200
    assert seen == [None, "We will call you."]


def test_preview_endpoint_returns_the_email(client, monkeypatch) -> None:
    job, candidate = _job_and_candidate()
    db = FakeDB({(Job, 2): job, (Candidate, 5): candidate})
    client.app.dependency_overrides[get_db] = lambda: db
    body = {"kind": "invitation", "candidate_id": 5, "start": START.isoformat(),
            "end": END.isoformat(), "message": "Bring your portfolio."}

    response = client.post(
        "/jobs/2/interviews/preview", json=body, headers=_auth(UserRole.INTERVIEWER)
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["subject"] == "HireLucent video interview – Backend Engineer"
    assert preview["text"].startswith("Hello Test Candidate,\n\nBring your portfolio.")
    assert "[private link]" in preview["text"]
    assert preview["default_message"].startswith("Thank you for applying")
    assert "candidate@example.com" not in response.text


def test_preview_refuses_a_candidate_of_another_job(client) -> None:
    job, candidate = _job_and_candidate()
    candidate.job_id = 3
    client.app.dependency_overrides[get_db] = lambda: FakeDB(
        {(Job, 2): job, (Candidate, 5): candidate}
    )
    body = {"kind": "cancelled", "candidate_id": 5, "start": START.isoformat(),
            "end": END.isoformat()}

    response = client.post(
        "/jobs/2/interviews/preview", json=body, headers=_auth(UserRole.INTERVIEWER)
    )

    assert response.status_code == 404


def test_the_same_candidate_twice_is_refused(client) -> None:
    response = client.post(
        "/jobs/2/interviews", json=_body(5, 5), headers=_auth(UserRole.INTERVIEWER)
    )

    assert response.status_code == 422


def test_a_time_without_a_zone_is_refused(client) -> None:
    body = {"interviews": [{"candidate_id": 5, "start": "2026-10-14T15:00:00",
                            "end": "2026-10-14T15:45:00"}]}

    response = client.post("/jobs/2/interviews", json=body, headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 422


def test_candidates_cannot_schedule_or_cancel(client) -> None:
    headers = _auth(UserRole.CANDIDATE)

    assert client.post("/jobs/2/interviews", json=_body(5), headers=headers).status_code == 403
    assert client.post("/interviews/9/cancel", headers=headers).status_code == 403
