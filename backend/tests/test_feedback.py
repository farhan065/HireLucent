"""Tests for the Candidate Feedback Composer (F11): the fixed parts, the
safety rules, the named-term check, the AI prompts, LangGraph 5, decisions
and the endpoints. No test calls the real AI or Google, and the database is
replaced with stand-ins."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from app.core.errors import ConflictError, ServiceUnavailableError
from app.core.security import create_access_token
from app.db.session import get_db
from app.graphs.base import MAX_ATTEMPTS, thread_config
from app.graphs.feedback import fairness, templates, writing
from app.graphs.feedback import graph as fb
from app.graphs.feedback import store as fb_store
from app.graphs.feedback.writing import FeedbackAnswer, ReviewAnswer
from app.main import create_app
from app.models import Candidate, CandidateFeedback
from app.models.enums import CandidateStatus, FeedbackKind, UserRole
from app.schemas.feedback import DecisionRule, FeedbackReview
from app.services import feedback_service

# --- The fixed parts ---------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "years", "level"),
    [
        ("Senior Machine Learning Engineer", 5, templates.SENIOR),
        ("Backend Developer", 3, templates.SENIOR),
        ("Junior Backend Developer", 1, templates.JUNIOR),
        ("Backend Developer", None, templates.JUNIOR),
        ("AI Trainee", 0, templates.ENTRY),
        ("Software Engineering Intern", 2, templates.ENTRY),
    ],
)
def test_the_role_level_comes_from_the_title_and_years(title, years, level) -> None:
    assert templates.role_level(title, years) == level


def test_the_name_is_put_in_and_the_signature_added() -> None:
    body = templates.finish("Dear [first name],\n\nThank you.", "Nadia")

    assert body.startswith("Dear Nadia,") and body.endswith("HireLucent Careers")


def test_each_kind_has_its_subject() -> None:
    assert templates.subject("hire", "Backend Developer") == (
        "Congratulations – Backend Developer at HireLucent"
    )
    assert templates.subject("screening_reject", "QA").startswith("Thank you for applying")


# --- The fairness rules ------------------------------------------------------

SCREENING_EMAIL = """Dear Nadia,

Thank you for applying for the Backend Developer role and for taking the time to share your experience with us.

After reviewing your CV, we found that you have strong experience with Python and building REST APIs, which shows a solid foundation in backend development.

But we are really sorry that we cannot move forward with you this time. Beyond the core requirements, this role also looks for experience that we could not find in your CV:
- Working with cloud platforms such as AWS
- Running ML pipelines with tools such as Airflow

We are looking for someone who can bring these strengths from the very first day.

We are confident you will go far, and we would be glad to see your application again in the future.

With warm regards,
HireLucent Careers"""


@pytest.mark.parametrize("kind", ["hire", "cv_unreadable"])
def test_the_fixed_messages_pass_every_rule(kind: str) -> None:
    body = templates.fixed_body(kind, "Nadia", "Backend Developer")

    assert fairness.rule_warnings(body, "Nadia") == []


def test_an_agreed_rejection_email_passes_every_rule() -> None:
    assert fairness.rule_warnings(SCREENING_EMAIL, "Nadia") == []


@pytest.mark.parametrize(
    ("sentence", "code"),
    [
        ("Your CV matched 48% of our requirements.", "score"),
        ("You scored below the others.", "score"),
        ("Other candidates had more experience.", "other_candidates"),
        ("We found a stronger candidate.", "other_candidates"),
        ("At your age, this role might be demanding.", "personal"),
        ("We will definitely consider you for the next opening.", "promise"),
        ("The salary was set for someone more senior.", "offer"),
        ('You said "the QA team handled all of that".', "quote"),
        ("Please see <b>this</b>.", "format"),
        ("We will send [details] soon.", "format"),
        ("Your identity was confirmed.", "identity"),
    ],
)
def test_each_rule_names_what_it_found(sentence: str, code: str) -> None:
    found = fairness.rule_warnings(f"Dear Nadia,\n\n{sentence}\n\nWith warm regards", "Nadia")

    assert code in fairness.codes(found)
    assert next(w for w in found if w["code"] == code)["quote"]


def test_the_candidates_own_name_is_not_a_placeholder() -> None:
    assert fairness.rule_warnings("Dear Nadia,\n\nThank you.", "Nadia") == []


# --- Personal data and named skills -----------------------------------------


def test_contact_details_and_links_are_personal_data() -> None:
    body = "Dear Nadia,\n\nWrite to me at nadia.k@mail.com, call +880 1712-345678 or see www.x.io"

    found = fairness.rule_warnings(body, "Nadia")

    assert fairness.codes(found) == ["personal_data"]
    assert set(found[0]["words"]) == {"nadia.k@mail.com", "+880 1712-345678", "www.x.io"}


def test_dates_and_years_are_not_phone_numbers() -> None:
    assert fairness.rule_warnings("You worked there from 2021-2024 for 3 years.") == []


def test_a_warning_names_the_exact_words() -> None:
    found = fairness.rule_warnings("Your CV matched 48% of our needs.")

    assert found[0]["words"] == ["48%"] and '"48%"' in found[0]["message"]


def test_a_personal_word_in_the_jobs_own_requirements_is_allowed() -> None:
    assert fairness.rule_warnings("Your work in health data stood out.", known="Health data") == []


KNOWN = (
    "Senior Backend Engineer\n- R2: A modern backend language (Python, Go, Node.js, or Java)\n"
    "- R3: RESTful APIs and microservices\nReact\nNext.js\nTypeScript\nHTML5"
)


def test_named_skills_must_be_in_the_candidates_results_or_the_job() -> None:
    body = (
        "Dear Nadia,\n\nYour work with React, Next.js, TypeScript and HTML5 stands out. "
        "Growing your Python and REST APIs skills would help. You may also explore Kubernetes "
        "and AWS."
    )

    assert fairness.unknown_terms(body, "Nadia", KNOWN) == ["Kubernetes", "AWS"]


def test_ordinary_capitalised_words_are_not_named_skills() -> None:
    body = (
        "Dear Nadia,\n\nThank you for applying for the Senior Backend Engineer role. "
        "Please send your CV as a PDF or Word document.\n\n" + templates.SIGNATURE
    )

    assert fairness.unknown_terms(body, "Nadia", KNOWN) == []


# --- The AI's prompts --------------------------------------------------------

EVIDENCE = {
    "kind": FeedbackKind.SCREENING_REJECT,
    "job_id": 2,
    "job_title": "Backend Developer",
    "first_name": "Nadia",
    "level": templates.SENIOR,
    "strengths": [{"id": "R1", "text": "Python web development", "note": "must-have · met"}],
    "growth": [
        {"id": "R7", "text": "Cloud platforms such as AWS", "note": "preferred · not met"},
        {"id": "R8", "text": "ML pipelines", "note": "preferred · not met"},
    ],
    "reason": fb_store.PREFERRED,
    "requirements": "- R1: Python web development\n- R7: Cloud platforms such as AWS",
}

AI_EMAIL = (
    "Dear [first name],\n\nThank you for applying for the Backend Developer role and for "
    "taking the time to share your experience with us. Your CV shows a solid foundation in "
    "Python web development.\n\nWe are really sorry that we cannot move forward this time. "
    "Beyond the core requirements, this role also looks for experience that we could not "
    "find in your CV:\n- Building on cloud platforms such as AWS\n- Running ML pipelines "
    "end to end\n\nFor this role, we need someone who can deliver in these areas from the "
    "very first day. We would be glad to see your application again in the future."
)
GOOD = FeedbackAnswer(email=AI_EMAIL, strength_ids=["R1"], growth_ids=["R7", "R8"])


def test_the_prompt_never_holds_the_name_and_guides_without_fixing_words() -> None:
    text = writing.prompt(EVIDENCE)

    assert "Nadia" not in text and templates.NAME in text
    assert "as a guide only" in text and "Never add any other skill" in text
    assert templates.LEVEL_SENTENCES[templates.SENIOR] in text
    assert "R7: Cloud platforms such as AWS" in text


def test_without_growth_areas_the_email_names_a_difficult_choice() -> None:
    text = writing.prompt({**EVIDENCE, "growth": [], "reason": fb_store.NONE})

    assert "difficult choice" in text and "from the very first day" not in text


def test_the_review_gets_the_points_and_the_jobs_requirements() -> None:
    text = writing.review_prompt(AI_EMAIL, EVIDENCE)

    assert "R8: ML pipelines" in text and "R1: Python web development" in text
    assert "unsupported" in text and "unfair" in text


def test_a_missing_greeting_is_added() -> None:
    assert writing.with_greeting("Thank you.").startswith(f"Dear {templates.NAME},")
    assert writing.with_greeting("Dear [first name],\n\nHi").count("Dear") == 1


def test_the_based_on_box_lists_the_points_used_and_the_level() -> None:
    used = writing.evidence_used(GOOD, EVIDENCE)

    assert [(item["group"], item["id"]) for item in used] == [
        ("strength", "R1"),
        ("growth", "R7"),
        ("growth", "R8"),
        ("level", templates.SENIOR),
    ]


def test_made_up_ids_are_left_out_of_the_based_on_box() -> None:
    answer = FeedbackAnswer(email=AI_EMAIL, strength_ids=["R1", "R99"], growth_ids=["R8"])

    used = writing.evidence_used(answer, EVIDENCE)

    assert [item["id"] for item in used] == ["R1", "R8", templates.SENIOR]


def test_every_screening_point_is_passed_on() -> None:
    matches = [
        {"id": f"R{n}", "text": f"Skill {n}", "priority": "must_have", "status": "met"}
        for n in range(1, 8)
    ] + [
        {"id": "R8", "text": "AWS", "priority": "preferred", "status": "partially_met"},
        {"id": "R9", "text": "Airflow", "priority": "preferred", "status": "unmet"},
    ]
    candidate = SimpleNamespace(
        status=CandidateStatus.SCREENED,
        full_name="Nadia Islam",
        screening_result=SimpleNamespace(requirement_matches=matches, excluded_reason=None),
        cv_parsed={},
    )

    strengths, growth, reason = fb_store._screening_points(candidate, None)

    assert len(strengths) == 7
    assert [point["id"] for point in growth] == ["R9", "R8"]
    assert reason == fb_store.PREFERRED


def test_an_excluded_candidate_gets_every_missing_must_have_and_skill() -> None:
    candidate = SimpleNamespace(
        status=CandidateStatus.EXCLUDED,
        full_name="Nadia Islam",
        screening_result=SimpleNamespace(
            requirement_matches=None,
            excluded_reason="\n".join(
                f"Missing must-have (R{n}): Skill {n}" for n in range(1, 6)
            ),
        ),
        cv_parsed={"skills": ["Python", "SQL", "React", "Vue", "Go", "Rust", "C#"]},
    )

    strengths, growth, reason = fb_store._screening_points(candidate, None)

    assert len(growth) == 5 and reason == fb_store.MUST_HAVE
    assert len(strengths) == 7


def _excluded(cv_parsed: dict, reason: str = "Missing must-have (R2): Go", name: str = "Tashsin Ahmed"):
    return SimpleNamespace(
        status=CandidateStatus.EXCLUDED,
        full_name=name,
        screening_result=SimpleNamespace(requirement_matches=None, excluded_reason=reason),
        cv_parsed=cv_parsed,
    )


def test_the_cv_profile_leads_the_strengths_without_the_name() -> None:
    candidate = _excluded(
        {
            "summary": "Tahsin Ahmed Rahman is a frontend engineer with 8+ years in React.",
            "skills": ["React", "Next.js", "Git"],
        }
    )

    strengths, _, _ = fb_store._screening_points(candidate, None)

    assert strengths[0]["id"] == fb_store.PROFILE_ID
    assert strengths[0]["text"] == "the candidate is a frontend engineer with 8+ years in React."
    assert [point["text"] for point in strengths[1:]] == ["React", "Next.js", "Git"]


def test_without_a_summary_the_roles_in_the_cv_are_the_profile() -> None:
    candidate = _excluded(
        {
            "summary": "",
            "skills": ["React"],
            "experience": [
                {"title": "Senior Frontend Engineer", "company": "Saffron Tech"},
                {"title": "Frontend Developer", "company": "Beacon"},
                {"title": "frontend developer", "company": "Other"},
            ],
        }
    )

    strengths, _, _ = fb_store._screening_points(candidate, None)

    assert strengths[0]["text"] == "Roles in the CV: Senior Frontend Engineer, Frontend Developer"
    assert "Saffron" not in strengths[0]["text"]


def test_a_scored_candidate_gets_the_profile_beside_the_met_requirements() -> None:
    matches = [{"id": "R1", "text": "Python", "priority": "must_have", "status": "met"}]
    candidate = SimpleNamespace(
        status=CandidateStatus.SCREENED,
        full_name="Nadia Islam",
        screening_result=SimpleNamespace(requirement_matches=matches, excluded_reason=None),
        cv_parsed={"summary": "Data engineer building pipelines."},
    )

    strengths, _, _ = fb_store._screening_points(candidate, None)

    assert [point["id"] for point in strengths] == [fb_store.PROFILE_ID, "R1"]


def test_a_cv_with_nothing_to_praise_gives_no_strengths() -> None:
    strengths, growth, _ = fb_store._screening_points(_excluded({"skills": ["", " "]}), None)

    assert strengths == [] and len(growth) == 1


def test_every_exclusion_wording_becomes_a_growth_area() -> None:
    reason = "\n".join(
        [
            "Missing must-have (R2): Go",
            "2 years of experience; the job asks for at least 5 years.",
            "Some other must-have reason",
        ]
    )

    _, growth, why = fb_store._screening_points(_excluded({}, reason), None)

    assert [point["id"] for point in growth] == ["R2", "EXP", "MH3"]
    assert why == fb_store.MUST_HAVE


@pytest.mark.parametrize(
    ("text", "name", "expected"),
    [
        ("Joy Das brings joy to teams.", "Joy Das", "the candidate brings joy to teams."),
        ("In 2020 Ahmed Rahman joined a startup.", "Ahmed", "In 2020 the candidate joined a startup."),
        ("Frontend engineer with 8+ years.", "Tashsin Ahmed", "Frontend engineer with 8+ years."),
        ("NADIA's work spans data.", "Nadia Islam", "the candidate's work spans data."),
    ],
)
def test_the_name_is_taken_out_of_the_profile(text: str, name: str, expected: str) -> None:
    assert fb_store._without_name(text, name) == expected


@pytest.mark.parametrize(
    ("full_name", "greeting"),
    [
        ("TASHSIN AHMED", "Tashsin"),
        ("Md. Tashsin Ahmed", "Tashsin"),
        ("md rafi", "Rafi"),
        ("Dr Sadia Rahman", "Sadia"),
        ("jean-luc martin", "Jean-Luc"),
        ("McKenzie Hall", "McKenzie"),
        ("", "there"),
    ],
)
def test_the_greeting_uses_the_name_the_candidate_goes_by(full_name: str, greeting: str) -> None:
    assert templates.first_name(full_name) == greeting


def test_the_prompt_leads_with_the_main_strength_or_leaves_strengths_out() -> None:
    profile = {"id": fb_store.PROFILE_ID, "text": "Frontend engineer", "note": "profile in the CV"}
    screening = {**EVIDENCE, "kind": FeedbackKind.SCREENING_REJECT, "strengths": [profile]}

    assert "not this role's focus" in writing.prompt(screening)
    assert "Never list every skill" in writing.prompt(screening)
    assert "Lead with what the interview showed" in writing.prompt(
        {**EVIDENCE, "kind": FeedbackKind.INTERVIEW_REJECT}
    )
    empty = writing.prompt({**screening, "strengths": []})
    assert "There are no strengths to mention" in empty
    assert "not this role's focus" not in empty


# --- LangGraph 5 -------------------------------------------------------------


class FakeStore:
    def __init__(self, evidence: dict | None) -> None:
        self.evidence = evidence
        self.drafts: list[dict] = []
        self.events: list[tuple] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(fb.store, "load_evidence", lambda cid: self.evidence)
        monkeypatch.setattr(fb.store, "recipient", lambda cid: "nadia@example.com")
        monkeypatch.setattr(
            fb.store, "save_draft", lambda cid, values: self.drafts.append(dict(values))
        )
        monkeypatch.setattr(
            fb.store, "mark_sending", lambda cid, uid: self.events.append(("sending", uid))
        )
        monkeypatch.setattr(
            fb.store, "mark_failed", lambda cid, msg: self.events.append(("failed", msg))
        )
        monkeypatch.setattr(
            fb.store,
            "record_sent",
            lambda cid, uid, anyway: self.events.append(("sent", uid, anyway)),
        )
        monkeypatch.setattr(fb.store, "discard", lambda cid: self.events.append(("discarded",)))


OK = ReviewAnswer(respectful=True)


class FakeAI:
    """Answers in turn; an exception in the list is raised instead."""

    def __init__(self, answers: list, reviews: list | None = None) -> None:
        self.answers = answers
        self.reviews = reviews or []
        self.calls: list[dict] = []
        self.review_calls: list[str] = []

    def ask(self, evidence, **kwargs):
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def review(self, email, evidence):
        self.review_calls.append(email)
        answer = self.reviews.pop(0) if self.reviews else OK
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeGoogle:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[dict] = []

    def __call__(self, server, tool, arguments, timeout=None):
        if self.fail:
            raise RuntimeError("down")
        self.sent.append(arguments)
        return SimpleNamespace(is_error=False)


CONFIG = thread_config("feedback-5")


def _start(monkeypatch, answers, evidence=EVIDENCE, reviews=None, google=None):
    store = FakeStore(evidence)
    store.install(monkeypatch)
    ai = FakeAI(answers, reviews)
    monkeypatch.setattr(fb.writing, "ask_ai", ai.ask)
    monkeypatch.setattr(fb.writing, "review_email", ai.review)
    google = google or FakeGoogle()
    monkeypatch.setattr(fb.client, "call_tool", google)
    graph = fb.build_feedback_graph(InMemorySaver())
    graph.invoke({"candidate_id": 5}, CONFIG)
    return graph, store, ai, google


def _resume(graph, **review):
    from langgraph.types import Command

    graph.invoke(Command(resume={"user_id": 1, **review}), CONFIG)
    return graph.get_state(CONFIG).values


def _with(text: str) -> FeedbackAnswer:
    return GOOD.model_copy(update={"email": AI_EMAIL + " " + text})


def test_a_good_draft_is_saved_and_waits_for_review(monkeypatch) -> None:
    graph, store, ai, _ = _start(monkeypatch, [GOOD])

    assert fb.is_waiting_for_review(graph, CONFIG)
    draft = store.drafts[0]
    assert draft["body"].startswith("Dear Nadia,") and draft["warnings"] == []
    assert draft["written_by"] == "ai" and draft["kind"] == FeedbackKind.SCREENING_REJECT
    assert "Nadia" not in ai.review_calls[0]


def test_free_wording_is_never_sent_back(monkeypatch) -> None:
    reworded = GOOD.model_copy(
        update={"email": AI_EMAIL.replace("Running ML pipelines end to end", "Owning ML pipelines")}
    )

    graph, store, ai, _ = _start(monkeypatch, [reworded])

    assert len(ai.calls) == 1 and store.drafts[0]["warnings"] == []


def test_a_draft_breaking_a_rule_is_written_again_with_the_reason(monkeypatch) -> None:
    graph, store, ai, _ = _start(monkeypatch, [_with("Your CV matched 48% of them."), GOOD])

    assert len(ai.calls) == 2 and '"48%"' in ai.calls[1]["problems"][0]
    assert store.drafts[0]["warnings"] == []


def test_an_invented_tool_is_caught_by_the_code_check(monkeypatch) -> None:
    graph, store, ai, _ = _start(monkeypatch, [_with("Try Kubernetes too.")] * MAX_ATTEMPTS)

    warning = store.drafts[0]["warnings"][0]
    assert len(ai.calls) == MAX_ATTEMPTS and warning["code"] == "invented"
    assert warning["words"] == ["Kubernetes"]


def test_an_invented_quality_is_caught_by_the_review(monkeypatch) -> None:
    invented = ReviewAnswer(respectful=True, unsupported=["led large teams"])

    graph, store, ai, _ = _start(monkeypatch, [GOOD, GOOD], reviews=[invented])

    assert len(ai.calls) == 2
    assert "led large teams" in ai.calls[1]["problems"][0]


def test_unfair_meaning_is_kept_as_a_warning_after_the_last_try(monkeypatch) -> None:
    unfair = ReviewAnswer(respectful=True, unfair=["younger in spirit"])

    graph, store, ai, _ = _start(monkeypatch, [GOOD] * MAX_ATTEMPTS, reviews=[unfair] * MAX_ATTEMPTS)

    assert fairness.codes(store.drafts[0]["warnings"]) == ["unfair"]


def test_an_unkind_draft_is_written_again(monkeypatch) -> None:
    unkind = ReviewAnswer(respectful=False, tone_issue="Too blunt.")

    graph, store, ai, _ = _start(monkeypatch, [GOOD, GOOD], reviews=[unkind])

    assert len(ai.calls) == 2 and ai.calls[1]["problems"] == ["Tone: Too blunt"]


def test_a_hire_uses_the_fixed_message_without_the_ai(monkeypatch) -> None:
    evidence = {**EVIDENCE, "kind": FeedbackKind.HIRE, "strengths": [], "growth": []}

    graph, store, ai, _ = _start(monkeypatch, [], evidence=evidence)

    assert not ai.calls and not ai.review_calls
    assert "selected for the Backend Developer role" in store.drafts[0]["body"]
    assert store.drafts[0]["written_by"] == "template"


def test_approving_sends_and_records_the_email(monkeypatch) -> None:
    graph, store, _, google = _start(monkeypatch, [GOOD])

    _resume(graph, action="approve")

    assert google.sent[0]["to"] == "nadia@example.com"
    assert google.sent[0]["subject"].startswith("Thank you for applying")
    assert store.events == [("sending", 1), ("sent", 1, False)]
    assert not fb.is_waiting_for_review(graph, CONFIG)


def test_a_failed_send_waits_for_try_again(monkeypatch) -> None:
    graph, store, _, google = _start(monkeypatch, [GOOD], google=FakeGoogle(fail=True))

    values = _resume(graph, action="approve")

    assert values["send_error"] == fb.SEND_FAILED
    assert store.events[-1] == ("failed", fb.SEND_FAILED)
    assert fb.is_waiting_for_review(graph, CONFIG)
    google.fail = False
    _resume(graph, action="approve")
    assert store.events[-1] == ("sent", 1, False)


def test_send_anyway_is_recorded(monkeypatch) -> None:
    graph, store, _, _ = _start(monkeypatch, [GOOD])

    _resume(graph, action="send_anyway")

    assert store.events[-1] == ("sent", 1, True)


def test_an_edit_is_checked_again_but_never_rewritten(monkeypatch) -> None:
    graph, store, ai, _ = _start(monkeypatch, [GOOD])

    _resume(graph, action="edit", body="Dear Nadia,\n\nYou scored 40.\n\nWith warm regards")

    assert len(ai.calls) == 1 and len(ai.review_calls) == 2
    assert fairness.codes(store.drafts[-1]["warnings"]) == ["score"]
    assert fb.is_waiting_for_review(graph, CONFIG)


def test_requested_changes_go_to_the_ai_with_the_note(monkeypatch) -> None:
    graph, store, ai, _ = _start(monkeypatch, [GOOD, GOOD])

    _resume(graph, action="request_changes", note="Keep it shorter.")

    assert ai.calls[1]["note"] == "Keep it shorter."
    assert "Nadia" not in ai.calls[1]["draft"]
    assert len(store.drafts) == 2


def test_discarding_ends_without_sending(monkeypatch) -> None:
    graph, store, _, google = _start(monkeypatch, [GOOD])

    _resume(graph, action="discard")

    assert store.events == [("discarded",)] and not google.sent
    assert not fb.is_waiting_for_review(graph, CONFIG)


def test_an_unavailable_ai_writes_no_draft(monkeypatch) -> None:
    graph, store, _, _ = _start(monkeypatch, [ServiceUnavailableError("down")])

    assert graph.get_state(CONFIG).values["failure"] == fb.AI_UNAVAILABLE
    assert not store.drafts


def test_an_unavailable_ai_keeps_the_draft_when_rewriting(monkeypatch) -> None:
    graph, store, _, _ = _start(monkeypatch, [GOOD, ServiceUnavailableError("down")])

    values = _resume(graph, action="request_changes", note="Shorter.")

    assert values["revision_failed"] and len(store.drafts) == 1
    assert fb.is_waiting_for_review(graph, CONFIG)


def test_nothing_is_written_for_a_candidate_who_cannot_get_an_email(monkeypatch) -> None:
    graph, store, _, _ = _start(monkeypatch, [], evidence=None)

    assert graph.get_state(CONFIG).values["failure"] == fb.NOTHING_TO_WRITE


def test_a_review_that_cannot_run_says_not_checked(monkeypatch) -> None:
    graph, store, _, _ = _start(monkeypatch, [GOOD], reviews=[ServiceUnavailableError("down")])

    assert fairness.codes(store.drafts[0]["warnings"]) == ["not_checked"]


# --- Decisions and reviews ---------------------------------------------------


def test_one_rule_is_needed_to_decide() -> None:
    DecisionRule(top=2)
    with pytest.raises(ValidationError):
        DecisionRule(top=2, min_score=70)


def test_a_request_for_changes_needs_a_note() -> None:
    with pytest.raises(ValidationError):
        FeedbackReview(action="request_changes")


@pytest.mark.parametrize(
    ("status", "decision", "stage"),
    [
        (CandidateStatus.SCREENED, None, "screening"),
        (CandidateStatus.EXCLUDED, None, "screening"),
        (CandidateStatus.SCREENING_FAILED, None, "screening"),
        (CandidateStatus.SHORTLISTED, None, None),
        (CandidateStatus.ASSESSED, None, None),
        (CandidateStatus.ASSESSED, "reject", "interview"),
    ],
)
def test_the_stage_of_a_candidate(status, decision, stage) -> None:
    assert feedback_service.stage_of(Candidate(status=status, decision=decision)) == stage


def _feedback(status="waiting_review", warnings=None, kind="screening_reject"):
    candidate = Candidate(id=5, job_id=2, status=CandidateStatus.SCREENED, full_name="Nadia")
    feedback = CandidateFeedback(
        candidate_id=5, job_id=2, kind=kind, status=status, warnings=warnings or []
    )
    candidate.feedback = feedback
    return feedback


class WaitingGraph:
    def get_state(self, config):
        return SimpleNamespace(next=("human_review",), values={})


@pytest.mark.parametrize(
    ("feedback", "action", "message"),
    [
        (_feedback(warnings=[{"code": "score"}]), "approve", "fairness warnings"),
        (_feedback(kind="hire"), "request_changes", "fixed message"),
        (_feedback(status="sent"), "approve", "not waiting"),
    ],
)
def test_some_reviews_are_refused(monkeypatch, feedback, action, message) -> None:
    monkeypatch.setattr(feedback_service, "get_feedback", lambda db, cid: feedback)
    review = FeedbackReview(action=action, note="Shorter." if action != "approve" else None)

    with pytest.raises(ConflictError, match=message):
        feedback_service.review(None, WaitingGraph(), 5, review, 1)


class DecisionDB:
    def __init__(self, candidate, approved=True):
        self.candidate = candidate
        self.approved = approved
        self.committed = False

    def get(self, model, key):
        return self.candidate

    def scalar(self, query):
        return 1 if self.approved else None

    def commit(self):
        self.committed = True


def test_a_decision_needs_an_approved_report() -> None:
    candidate = Candidate(id=5, status=CandidateStatus.ASSESSED)

    with pytest.raises(ConflictError, match="Approve the candidate's report"):
        feedback_service.set_decision(DecisionDB(candidate, approved=False), 5, "hire", 1)


def test_a_decision_is_locked_once_the_email_is_sent() -> None:
    candidate = Candidate(id=5, status=CandidateStatus.ASSESSED, decision="reject")
    candidate.feedback = CandidateFeedback(status="sent", warnings=[])

    with pytest.raises(ConflictError, match="already sent"):
        feedback_service.set_decision(DecisionDB(candidate), 5, "hire", 1)


def test_a_decision_is_set(monkeypatch) -> None:
    candidate = Candidate(id=5, status=CandidateStatus.ASSESSED)
    db = DecisionDB(candidate)

    feedback_service.set_decision(db, 5, "hire", 1)

    assert candidate.decision == "hire" and candidate.decided_by == 1 and db.committed


def test_the_rule_hires_the_top_and_rejects_the_rest(monkeypatch) -> None:
    candidates = {
        sid: Candidate(id=sid, status=CandidateStatus.ASSESSED) for sid in (1, 2, 3)
    }
    candidates[3].decision = "reject"
    candidates[3].feedback = CandidateFeedback(status="sent", warnings=[])
    rows = [
        {"candidate_id": sid, "rank": sid, "status": "approved", "overall_score": 90 - sid * 10}
        for sid in (1, 2, 3)
    ] + [{"candidate_id": 4, "rank": None, "status": "approved", "overall_score": None}]
    monkeypatch.setattr(feedback_service.evaluation_service, "ranked_assessments", lambda db, j: rows)
    db = SimpleNamespace(get=lambda model, key: candidates[key], commit=lambda: None)

    result = feedback_service.decide_by_rule(db, 2, DecisionRule(top=1), 1)

    assert result == {"hired": 1, "rejected": 1, "skipped": 1}
    assert candidates[1].decision == "hire" and candidates[2].decision == "reject"


# --- Endpoints ---------------------------------------------------------------


def _auth(role: UserRole) -> dict[str, str]:
    token = create_access_token(subject="1", role=role, expires_in=timedelta(minutes=5))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[feedback_service.get_feedback_graph] = lambda: SimpleNamespace()
    return TestClient(app)


def test_candidates_cannot_reach_feedback(client: TestClient) -> None:
    for method, path in [
        ("get", "/candidates/5/feedback"),
        ("post", "/candidates/5/feedback/review"),
        ("put", "/candidates/5/decision"),
        ("get", "/jobs/2/feedback"),
    ]:
        response = client.request(method.upper(), path, headers=_auth(UserRole.CANDIDATE), json={})
        assert response.status_code == 403


def test_a_review_without_a_note_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/candidates/5/feedback/review",
        json={"action": "request_changes"},
        headers=_auth(UserRole.INTERVIEWER),
    )

    assert response.status_code == 422
