"""AI cost report: how many chat model calls were made, for what, and what
they cost, from the usage file the backend writes (logs/ai_usage.log).

Usage (inside the backend container):
    python -m scripts.ai_cost_report
    python -m scripts.ai_cost_report --from 2026-10-27 --to 2026-10-27
    python -m scripts.ai_cost_report --job 15

Writes two CSV files to logs/reports/, which is logs/reports in the project
folder on your computer:
    ai_calls_<name>.csv          one row per call
    ai_cost_summary_<name>.csv   totals by day, route and step, unit costs
                                 (per CV, interview, email, job and hire)
                                 and a monthly projection

The costs use AI_PRICE_INPUT_PER_1M and AI_PRICE_OUTPUT_PER_1M from .env.
Dates are in APP_TIMEZONE. Only IDs and counts are written, never names,
emails, CV text or prompts.
"""

import argparse
import csv
import json
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Candidate, Conversation, InterviewSession
from app.models.enums import Decision

CALL_COLUMNS = (
    "time",
    "route",
    "graph",
    "step",
    "model",
    "job_id",
    "candidate_id",
    "session_id",
    "attempt",
    "input_tokens",
    "output_tokens",
    "cost_usd",
)
PROJECTED_JOBS = (50, 200)


def read_usage(path: Path) -> list[dict]:
    """Every call in the usage file. Damaged lines are skipped."""
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def load_links(records: list[dict]) -> tuple[dict, dict, dict, dict]:
    """From the database: each interview's candidate and job, each
    candidate's job, the job each AI Agent conversation saved, and the job
    of each candidate marked Hire."""
    session_ids = {r["session_id"] for r in records if r.get("session_id")}
    with SessionLocal() as db:
        sessions = {
            s.id: (s.candidate_id, s.job_id)
            for s in db.scalars(
                select(InterviewSession).where(InterviewSession.id.in_(session_ids))
            )
        }
        candidates = {c.id: c.job_id for c in db.scalars(select(Candidate))}
        conversations = {
            c.thread_id: c.job_id
            for c in db.scalars(select(Conversation).where(Conversation.job_id.is_not(None)))
        }
        hired = {
            c.id: c.job_id
            for c in db.scalars(select(Candidate).where(Candidate.decision == Decision.HIRE))
        }
    return sessions, candidates, conversations, hired


def link_ids(records: list[dict], sessions: dict, candidates: dict, conversations: dict) -> None:
    """Fill in the candidate and job of each call from its interview,
    candidate or AI Agent conversation, so every call that belongs to a job
    is counted for it. Calls written before a job was known (such as the
    chat that created the job) are linked here."""
    for record in records:
        session = sessions.get(record.get("session_id"))
        if session:
            record["candidate_id"] = record.get("candidate_id") or session[0]
            record["job_id"] = record.get("job_id") or session[1]
        if not record.get("job_id"):
            record["job_id"] = candidates.get(record.get("candidate_id"))
        if not record.get("job_id"):
            record["job_id"] = conversations.get(record.get("chat_thread"))


def add_times_and_costs(
    records: list[dict], zone: ZoneInfo, price_in: float, price_out: float
) -> None:
    """Local time, and the cost of each call in US dollars."""
    for record in records:
        local = datetime.fromisoformat(record["time"]).astimezone(zone)
        record["local_time"] = local
        record["time"] = local.strftime("%Y-%m-%d %H:%M:%S")
        record["cost_usd"] = (
            record.get("input_tokens", 0) * price_in + record.get("output_tokens", 0) * price_out
        ) / 1_000_000


def select_records(
    records: list[dict], start: date | None, end: date | None, job: int | None
) -> list[dict]:
    """The calls in the chosen days and job, oldest first."""
    chosen = [
        r
        for r in records
        if (start is None or r["local_time"].date() >= start)
        and (end is None or r["local_time"].date() <= end)
        and (job is None or r.get("job_id") == job)
    ]
    return sorted(chosen, key=lambda r: r["local_time"])


def money(value: float) -> str:
    return f"{value:.4f}"


def totals(records: Iterable[dict]) -> list:
    """calls, retries, input tokens, output tokens, cost."""
    records = list(records)
    return [
        len(records),
        sum(1 for r in records if (r.get("attempt") or 1) > 1),
        sum(r.get("input_tokens", 0) for r in records),
        sum(r.get("output_tokens", 0) for r in records),
        sum(r["cost_usd"] for r in records),
    ]


def grouped(records: list[dict], key: Callable[[dict], object]) -> dict:
    """The records grouped by key, in order of first appearance."""
    groups: dict = defaultdict(list)
    for record in records:
        groups[key(record)].append(record)
    return groups


def unit_row(name: str, groups: dict) -> list | None:
    """unit, count, average calls, average, lowest and highest cost, total."""
    if not groups:
        return None
    costs = [sum(r["cost_usd"] for r in group) for group in groups.values()]
    calls = sum(len(group) for group in groups.values())
    count = len(groups)
    return [
        name,
        count,
        f"{calls / count:.1f}",
        money(sum(costs) / count),
        money(min(costs)),
        money(max(costs)),
        money(sum(costs)),
    ]


def summary_rows(
    records: list[dict], title: str, model: str, price_in: float, price_out: float, hired: dict
) -> list[list]:
    """The summary file: header, by day, by route, by step, unit costs and
    projection."""
    all_totals = totals(records)
    grand_total = all_totals[4] or 1

    def with_share(values: list) -> list:
        return [*values[:4], money(values[4]), f"{100 * values[4] / grand_total:.1f}"]

    rows: list[list] = [
        ["HireLucent AI cost summary"],
        ["report", title],
        ["period", records[0]["time"], records[-1]["time"]],
        ["model", model],
        ["price_per_1M_input_usd", price_in],
        ["price_per_1M_output_usd", price_out],
        [],
        ["BY DAY"],
        [
            "date",
            "job_ids",
            "calls",
            "cvs_screened",
            "interviews",
            "input_tokens",
            "output_tokens",
            "cost_usd",
        ],
    ]

    def day_row(label: str, group: list[dict], with_jobs: bool) -> list:
        calls, _, tokens_in, tokens_out, cost = totals(group)
        jobs = sorted({r["job_id"] for r in group if r.get("job_id")})
        return [
            label,
            " ".join(str(j) for j in jobs) if with_jobs else "",
            calls,
            len({r["candidate_id"] for r in group if r.get("graph") == "screening"}),
            len({r["session_id"] for r in group if r.get("session_id")}),
            tokens_in,
            tokens_out,
            money(cost),
        ]

    for day, group in grouped(records, lambda r: r["local_time"].date().isoformat()).items():
        rows.append(day_row(day, group, True))
    rows += [day_row("TOTAL", records, False), []]

    rows += [
        ["BY ROUTE"],
        ["route", "calls", "retries", "input_tokens", "output_tokens", "cost_usd", "share_%"],
    ]
    by_route = grouped(records, lambda r: r.get("route") or "(no route)")
    for route, group in sorted(by_route.items(), key=lambda item: -totals(item[1])[4]):
        rows.append([route, *with_share(totals(group))])
    rows += [["TOTAL", *with_share(all_totals)], []]

    rows += [
        ["BY STEP"],
        [
            "graph",
            "step",
            "calls",
            "retries",
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "share_%",
        ],
    ]
    for (graph, step), group in grouped(records, lambda r: (r.get("graph"), r.get("step"))).items():
        rows.append([graph, step, *with_share(totals(group))])
    rows += [["TOTAL", "", *with_share(all_totals)], []]

    rows += [
        ["UNIT COSTS"],
        [
            "unit",
            "count",
            "avg_calls",
            "avg_cost_usd",
            "min_cost_usd",
            "max_cost_usd",
            "total_cost_usd",
        ],
    ]
    for_jobs = [r for r in records if r.get("job_id")]
    jobs = grouped(for_jobs, lambda r: r["job_id"])
    units = (
        ("per CV screened", [r for r in records if r.get("graph") == "screening"], "candidate_id"),
        ("per candidate interviewed", [r for r in records if r.get("session_id")], "session_id"),
        (
            "per feedback email",
            [r for r in records if r.get("graph") == "feedback"],
            "candidate_id",
        ),
    )
    for name, chosen, key in units:
        row = unit_row(name, grouped([r for r in chosen if r.get(key)], lambda r, k=key: r[k]))
        if row:
            rows.append(row)
    job_row = unit_row("per job", jobs)
    if job_row:
        rows.append(job_row)
        hires = sum(1 for job_id in hired.values() if job_id in jobs)
        job_cost = sum(r["cost_usd"] for r in for_jobs)
        if hires:
            rows.append(
                [
                    "per hire",
                    hires,
                    f"{len(for_jobs) / hires:.1f}",
                    money(job_cost / hires),
                    "",
                    "",
                    money(job_cost),
                ]
            )
        else:
            rows.append(["per hire", 0, "", "", "", "", money(job_cost)])

        average_job = job_cost / len(jobs)
        rows += [
            [],
            ["PROJECTION (average job in this report)"],
            ["scenario", "jobs_per_month", "cost_per_month_usd"],
        ]
        rows += [[f"{n} jobs a month", n, f"{n * average_job:.2f}"] for n in PROJECTED_JOBS]
    return rows


def report_name(start: date | None, end: date | None, job: int | None) -> str:
    """all, 2026-10-27, 2026-10-27_to_2026-10-30, job-15, ..."""
    parts = []
    if start and end:
        parts.append(start.isoformat() if start == end else f"{start}_to_{end}")
    elif start:
        parts.append(f"from_{start}")
    elif end:
        parts.append(f"until_{end}")
    if job is not None:
        parts.append(f"job-{job}")
    return "_".join(parts) or "all"


def write_csv(path: Path, rows: Iterable[Iterable]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(rows)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the AI cost report as CSV files.")
    parser.add_argument(
        "--from", dest="start", type=date.fromisoformat, help="first day, YYYY-MM-DD"
    )
    parser.add_argument("--to", dest="end", type=date.fromisoformat, help="last day, YYYY-MM-DD")
    parser.add_argument("--job", type=int, help="only the calls for this job ID")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, links: Callable = load_links) -> Path | None:
    args = parse_args(argv)
    settings = get_settings()
    log_dir = Path(settings.log_dir)
    records = read_usage(log_dir / settings.ai_usage_file_name)
    if not records:
        print("No AI calls have been recorded yet.")
        return None

    sessions, candidates, conversations, hired = links(records)
    link_ids(records, sessions, candidates, conversations)
    price_in, price_out = settings.ai_price_input_per_1m, settings.ai_price_output_per_1m
    add_times_and_costs(records, ZoneInfo(settings.app_timezone), price_in, price_out)
    chosen = select_records(records, args.start, args.end, args.job)
    if not chosen:
        print("No AI calls match these dates or job.")
        return None

    name = report_name(args.start, args.end, args.job)
    reports = log_dir / "reports"
    write_csv(
        reports / f"ai_calls_{name}.csv",
        [
            CALL_COLUMNS,
            *(
                [r.get(c) if c != "cost_usd" else f"{r[c]:.6f}" for c in CALL_COLUMNS]
                for r in chosen
            ),
        ],
    )
    summary = reports / f"ai_cost_summary_{name}.csv"
    write_csv(summary, summary_rows(chosen, name, settings.llm_model, price_in, price_out, hired))
    total = sum(r["cost_usd"] for r in chosen)
    print(
        f"{len(chosen)} AI calls, {total:.4f} USD. Written to {reports}/ai_cost_summary_{name}.csv"
    )
    return summary


if __name__ == "__main__":
    main()
