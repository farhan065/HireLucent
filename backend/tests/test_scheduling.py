"""Tests for scheduling: times, the calendar invitation, the scheduling
service, the agent's interview tools and the endpoints. Nothing is sent to
Google."""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

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


def test_invitation_starts_with_the_link_and_has_the_time_and_consent_note() -> None:
    invitation = interview_emails.invitation("Test", "Backend Engineer", START, END, LINK)

    assert invitation.title == "HireLucent video interview – Backend Engineer"
    assert invitation.description.startswith(f"Join the interview: {LINK}")
    assert "3:00–3:45 PM (Dhaka, GMT+6)" in invitation.description
    assert "45-minute" in invitation.description
    assert "not recorded" in invitation.description


def test_moved_invitation_says_the_old_link_stops_working() -> None:
    invitation = interview_emails.moved("Test", "Backend Engineer", START, END, LINK)

    assert invitation.description.startswith(f"Join the interview: {LINK}")
    assert "no longer works" in invitation.description


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
    first_line = event["description"].splitlines()[0]
    assert first_line.startswith("Join the interview: ")
    assert first_line.endswith("/interview/secret-token")
    assert session.calendar_event_id == "event-1"


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

    change = scheduling_service.cancel(FakeDB({(Job, 2): job}), 9)

    assert change.warning is None
    [(tool, arguments)] = google["calls"]
    assert tool == "cancel_calendar_event" and arguments["event_id"] == "event-1"
    assert "has been cancelled" in arguments["description"]
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
    assert "/interview/new-token" in event["description"].splitlines()[0]


# --- The agent's interview tools ---


def test_interview_actions_wait_for_approval() -> None:
    assert {"ScheduleInterviews", "RescheduleInterview", "CancelInterview"} <= EXTERNAL_ACTIONS
    assert "GetShortlistedCandidates" not in EXTERNAL_ACTIONS
    assert {"ScheduleInterviews", "RescheduleInterview", "CancelInterview"} <= set(PREPARERS)
    assert "GetShortlistedCandidates" in TOOL_HANDLERS


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
    assert "candidate@example.com" not in json.dumps(card)


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
        interview_tools.get_shortlisted({}, {"user_id": 1})


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

    def fake_schedule(db, job_id, slots, created_by):
        seen.update(job_id=job_id, slots=slots, created_by=created_by)
        return []

    monkeypatch.setattr(scheduling_service, "schedule", fake_schedule)

    response = client.post("/jobs/2/interviews", json=_body(5), headers=_auth(UserRole.INTERVIEWER))

    assert response.status_code == 200
    assert seen["job_id"] == 2 and seen["created_by"] == 1
    assert seen["slots"] == [Slot(5, START, END)]


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
