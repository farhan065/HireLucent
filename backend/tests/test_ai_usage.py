"""Tests for the AI cost report: the usage line written for each model
answer, and the report made from those lines. No real AI service is called."""

import csv
import json
from pathlib import Path
from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph

from app.ai import client, usage
from app.ai.usage import UsageRecorder, route_label, usage_context
from app.core.config import get_settings
from scripts import ai_cost_report

SECRET_PROMPT = "Candidate CV: Jane Example, jane@example.com"


@pytest.fixture
def usage_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The usage file and the reports go to a temporary folder."""
    settings = get_settings()
    monkeypatch.setattr(settings, "log_dir", str(tmp_path))
    monkeypatch.setattr(settings, "ai_price_input_per_1m", 0.30)
    monkeypatch.setattr(settings, "ai_price_output_per_1m", 2.50)
    monkeypatch.setattr(settings, "app_timezone", "UTC")
    return tmp_path / settings.ai_usage_file_name


@pytest.fixture(autouse=True)
def jobs_in_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stands in for the database: interview 7 is candidate 21's for job 8,
    and candidate 3 applied to job 8."""

    def find_job(candidate_id, session_id):
        if session_id == 7:
            return 21, 8
        return candidate_id, 8 if candidate_id == 3 else None

    monkeypatch.setattr(usage, "find_job", find_job)


def fake_model(*counts: tuple[int, int]) -> GenericFakeChatModel:
    """A chat model that answers with the given token counts."""
    answers = iter(
        AIMessage(
            "ok",
            usage_metadata={
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "total_tokens": tokens_in + tokens_out,
            },
        )
        for tokens_in, tokens_out in counts
    )
    return GenericFakeChatModel(messages=answers, callbacks=[UsageRecorder("test-model")])


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class State(TypedDict):
    answer: str


def graph_with(model: GenericFakeChatModel):
    """A one-node graph whose node asks the model, like the real graphs."""

    def judge_batch(state: State) -> dict:
        return {"answer": model.invoke(SECRET_PROMPT).text}

    graph = StateGraph(State)
    graph.add_node("judge_batch", judge_batch)
    graph.add_edge(START, "judge_batch")
    graph.add_edge("judge_batch", END)
    return graph.compile()


def test_a_call_in_a_graph_writes_one_line_with_its_step_and_ids(usage_file: Path) -> None:
    graph = graph_with(fake_model((1200, 300)))
    config = {"configurable": {"thread_id": "evaluation-task1-7"}}

    with usage_context(route=route_label("POST", "/interviews/7/evaluate")):
        graph.invoke({"answer": ""}, config)

    [line] = read_lines(usage_file)
    assert line["route"] == "POST /interviews/{id}/evaluate"
    assert line["graph"] == "qa_analysis"
    assert line["step"] == "judge_batch"
    assert line["session_id"] == 7
    # The job and candidate are recorded with the call, so deleting the
    # interview later does not take the call away from its job.
    assert (line["job_id"], line["candidate_id"]) == (8, 21)
    assert "chat_thread" not in line
    assert line["model"] == "test-model"
    assert (line["input_tokens"], line["output_tokens"], line["attempt"]) == (1200, 300, 1)


def test_the_prompt_and_the_answer_are_never_written(usage_file: Path) -> None:
    graph_with(fake_model((10, 5))).invoke(
        {"answer": ""}, {"configurable": {"thread_id": "feedback-3"}}
    )

    text = usage_file.read_text(encoding="utf-8")
    assert "Jane" not in text and "example.com" not in text and "CV" not in text
    line = read_lines(usage_file)[0]
    assert (line["candidate_id"], line["job_id"]) == (3, 8)


def test_agent_chat_calls_carry_their_conversation(usage_file: Path) -> None:
    graph_with(fake_model((50, 5))).invoke(
        {"answer": ""}, {"configurable": {"thread_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"}}
    )

    line = read_lines(usage_file)[0]
    assert line["graph"] == "recruiter"
    assert line["chat_thread"] == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
    assert line["job_id"] is None


def test_a_job_is_read_once_and_a_database_problem_never_stops_a_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()
    from app.db import session as db_session

    class BrokenDatabase:
        def __enter__(self):
            raise ConnectionError("database down")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(db_session, "SessionLocal", BrokenDatabase)
    usage._known_jobs.clear()
    assert usage.find_job(40, None) == (40, None)
    assert ("candidate", 40) not in usage._known_jobs

    usage._known_jobs[("session", 9)] = (41, 12)
    assert usage.find_job(None, 9) == (41, 12)
    usage._known_jobs.clear()


def test_tags_and_retries_are_recorded(usage_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client.time, "sleep", lambda seconds: None)
    model = fake_model((100, 20), (110, 25))
    calls = []

    def call() -> str:
        answer = model.invoke("prompt").text
        calls.append(answer)
        if len(calls) == 1:
            raise ValueError("the answer did not match the schema")
        return answer

    with usage_context(graph="questions", step="suggest_questions", job_id=4, session_id=9):
        client.run_with_retries("test", call)

    first, second = read_lines(usage_file)
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert {first["graph"], first["step"], first["job_id"]} == {"questions", "suggest_questions", 4}


def test_routes_group_all_ids_together() -> None:
    assert route_label("POST", "/jobs/15/screen") == "POST /jobs/{id}/screen"
    assert (
        route_label("PUT", "/chat/3f2b8c1e-9a4d-4c2e-8f1a-0b2c3d4e5f60/approval")
        == "PUT /chat/{id}/approval"
    )


def write_usage(path: Path, lines: list[dict]) -> None:
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")


def call(time: str, graph: str, step: str, tokens: tuple[int, int], **ids) -> dict:
    return {
        "time": time,
        "route": f"POST /{graph}",
        "graph": graph,
        "step": step,
        "model": "test-model",
        "attempt": ids.pop("attempt", 1),
        "input_tokens": tokens[0],
        "output_tokens": tokens[1],
        **ids,
    }


@pytest.fixture
def two_days(usage_file: Path) -> Path:
    """Job 1 screened on 27 Oct (two CVs), interviewed and given feedback on
    30 Oct. Candidate 11 was hired."""
    write_usage(
        usage_file,
        [
            call(
                "2026-10-27T10:00:00+00:00",
                "screening",
                "parse_cv",
                (1_000_000, 0),
                job_id=1,
                candidate_id=10,
            ),
            call(
                "2026-10-27T10:00:05+00:00",
                "screening",
                "score_candidate",
                (0, 400_000),
                job_id=1,
                candidate_id=10,
            ),
            call(
                "2026-10-27T10:00:09+00:00",
                "screening",
                "parse_cv",
                (1_000_000, 0),
                job_id=1,
                candidate_id=11,
            ),
            call(
                "2026-10-30T09:00:00+00:00",
                "qa_analysis",
                "judge_batch",
                (2_000_000, 0),
                session_id=5,
            ),
            call(
                "2026-10-30T09:00:03+00:00",
                "qa_analysis",
                "judge_batch",
                (2_000_000, 0),
                session_id=5,
                attempt=2,
            ),
            call(
                "2026-10-30T12:00:00+00:00",
                "feedback",
                "draft_feedback",
                (0, 200_000),
                candidate_id=10,
            ),
        ],
    )
    return usage_file


def links(records: list[dict]) -> tuple[dict, dict, dict, dict]:
    """Interview 5 is candidate 11's, both candidates applied to job 1, the
    AI Agent conversation "chat1" saved job 1, and candidate 11 was hired."""
    return {5: (11, 1)}, {10: 1, 11: 1}, {"chat1": 1}, {11: 1}


def summary(path: Path) -> dict[str, list]:
    """The summary rows, by their first cell. TOTAL is the first one, the
    total of the BY DAY block."""
    rows: dict[str, list] = {}
    with path.open(encoding="utf-8") as file:
        for row in csv.reader(file):
            if row:
                rows.setdefault(row[0], row)
    return rows


def test_the_report_adds_up_the_calls_and_costs(two_days: Path) -> None:
    path = ai_cost_report.main([], links=links)

    assert path.name == "ai_cost_summary_all.csv"
    rows = summary(path)
    # 0.30 + 1.00 + 0.30 + 0.60 + 0.60 + 0.50 dollars.
    assert rows["TOTAL"][-1] == "3.3000"
    assert rows["2026-10-27"][1:5] == ["1", "3", "2", "0"]
    assert rows["2026-10-30"][1:5] == ["1", "3", "0", "1"]
    # CV 10 cost 1.30, CV 11 cost 0.30.
    assert rows["per CV screened"][1:] == ["2", "1.5", "0.8000", "0.3000", "1.3000", "1.6000"]
    assert rows["per candidate interviewed"][3] == "1.2000"
    assert rows["per job"][1:4] == ["1", "6.0", "3.3000"]
    assert rows["per hire"][1:4] == ["1", "6.0", "3.3000"]
    assert rows["50 jobs a month"][2] == "165.00"
    assert (path.parent / "ai_calls_all.csv").exists()


def test_the_report_counts_retries_and_links_interviews_to_their_job(two_days: Path) -> None:
    rows = summary(ai_cost_report.main(["--job", "1"], links=links))

    assert rows["POST /qa_analysis"][1:3] == ["2", "1"]
    assert rows["TOTAL"][-1] == "3.3000"


def test_the_report_can_cover_chosen_days(two_days: Path) -> None:
    path = ai_cost_report.main(["--from", "2026-10-30", "--to", "2026-10-30"], links=links)

    assert path.name == "ai_cost_summary_2026-10-30.csv"
    rows = summary(path)
    assert rows["TOTAL"][-1] == "1.7000"
    assert "2026-10-27" not in rows
    assert "per CV screened" not in rows


def test_a_job_without_a_hire_has_no_cost_per_hire(two_days: Path) -> None:
    rows = summary(ai_cost_report.main([], links=lambda records: (*links(records)[:3], {})))

    assert rows["per hire"][1:4] == ["0", "", ""]


def test_the_chat_that_created_a_job_counts_for_it(usage_file: Path) -> None:
    write_usage(
        usage_file,
        [
            # Before the job was saved, so the call has no job yet.
            call(
                "2026-10-26T09:00:00+00:00", "recruiter", "agent", (100_000, 0), chat_thread="chat1"
            ),
            call(
                "2026-10-26T09:01:00+00:00",
                "recruiter",
                "agent",
                (100_000, 0),
                job_id=1,
                chat_thread="chat1",
            ),
            # A conversation that never saved a job.
            call(
                "2026-10-26T09:05:00+00:00", "recruiter", "agent", (100_000, 0), chat_thread="other"
            ),
        ],
    )

    rows = summary(ai_cost_report.main(["--job", "1"], links=links))

    assert rows["TOTAL"][2] == "2"
    assert rows["TOTAL"][-1] == "0.0600"


def test_nothing_is_written_without_recorded_calls(usage_file: Path) -> None:
    assert ai_cost_report.main([], links=links) is None
    assert not (usage_file.parent / "reports").exists()


@pytest.mark.parametrize(
    ("args", "name"),
    [
        ([], "all"),
        (["--from", "2026-10-27", "--to", "2026-10-30"], "2026-10-27_to_2026-10-30"),
        (["--from", "2026-10-27"], "from_2026-10-27"),
        (["--job", "15"], "job-15"),
    ],
)
def test_report_names(args: list[str], name: str) -> None:
    parsed = ai_cost_report.parse_args(args)
    assert ai_cost_report.report_name(parsed.start, parsed.end, parsed.job) == name
