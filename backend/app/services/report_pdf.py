"""The assessment report as a PDF file, for printing or sharing with the
hiring team.

Page 1 is the report as the Report tab shows it: the scores with the
suitability label, the summary, strengths, weaknesses, evidence gaps and
areas to verify, each point with its sources. The appendix that follows
lists the requirement coverage and every question with its score, so the
file makes sense without HireLucent.

The pages are written from simple HTML with PyMuPDF (already used to read
CVs), so the text in the file is real text that can be searched and copied.
Every value from the assessment is escaped before it goes into the HTML.
"""

import io
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pymupdf

from app.graphs.final_assessment import scoring

PAGE = pymupdf.paper_rect("a4")
MARGIN = 40
# The text area, with room at the bottom for the footer.
CONTENT = pymupdf.Rect(MARGIN, MARGIN, PAGE.width - MARGIN, PAGE.height - MARGIN - 18)

NAVY = "#0B1F4B"
BODY = "#51607A"
MUTED = "#6B7890"
BLUE = "#1557E0"
GREEN = ("#E6F6EF", "#0B7A55")
AMBER = ("#FFF4E0", "#8A4B00")
GREY = ("#EEF1F6", "#44526B")
RED = ("#FDECEA", "#B42318")

LABELS = {
    scoring.STRONG_FIT: ("Strong fit", GREEN),
    scoring.POSSIBLE_FIT: ("Possible fit", ("#EAF1FF", BLUE)),
    scoring.NOT_A_FIT: ("Not a fit", RED),
}
CV_RESULTS = {
    "met": ("CV: met", GREEN),
    "partially_met": ("CV: partly met", AMBER),
    "unmet": ("CV: not met", RED),
}
COVERAGE = {
    "covered": ("Covered", GREEN),
    "weak": ("Weak", AMBER),
    "not_explored": ("Not explored", GREY),
}
KINDS = {
    "technical": "Technical",
    "behavioural": "Behavioural",
    "company": "Company",
    "small_talk": "Small talk",
}
ACCURACY = {
    "reference": "Verified",
    "ai_judgement": "AI interviewer",
    "not_checked": "Not checked",
}
PRIORITIES = {"must_have": "Must-have", "preferred": "Preferred"}

CSS = f"""
body {{ font-family: sans-serif; font-size: 9.5pt; color: {BODY}; }}
h1 {{ font-size: 17pt; color: {NAVY}; margin: 2pt 0 2pt 0; }}
h2 {{ font-size: 11.5pt; color: {NAVY}; margin: 10pt 0 3pt 0; }}
p {{ margin: 0 0 3pt 0; }}
.brand {{ font-size: 9pt; color: {BLUE}; font-weight: bold; }}
.small {{ font-size: 8pt; color: {MUTED}; }}
.point {{ color: {NAVY}; margin: 5pt 0 1pt 0; }}
.sources {{ font-size: 8pt; margin: 0 0 3pt 0; }}
.box {{ border: 1px solid #DCE5F5; padding: 5pt; }}
.label {{ font-size: 7pt; color: {MUTED}; font-weight: bold; }}
.score {{ font-size: 15pt; color: {NAVY}; font-weight: bold; }}
th {{ font-size: 7.5pt; color: {MUTED}; text-align: left; border-bottom: 1px solid #DCE5F5;
      padding: 3pt; }}
td {{ font-size: 8.5pt; color: {NAVY}; border-bottom: 1px solid #EEF2F9; padding: 3pt; }}
"""


def _zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def _day(value: datetime, zone: ZoneInfo) -> str:
    local = value.astimezone(zone)
    return f"{local:%a} {local.day} {local:%b %Y}"


def _clock(value: datetime, zone: ZoneInfo) -> str:
    local = value.astimezone(zone)
    return f"{local.hour % 12 or 12}:{local:%M} {local:%p}"


def _score(value: float | None) -> str:
    return "–" if value is None else f"{round(value, 1):g}"


def _chip(text: str, colors: tuple[str, str]) -> str:
    background, color = colors
    style = f"background-color: {background}; color: {color}"
    return f'<span style="{style}">&#160;{escape(text)}&#160;</span>'


def _time(ms: int | None) -> str:
    if ms is None:
        return ""
    minutes, seconds = divmod(max(ms, 0) // 1000, 60)
    return f" · {minutes}:{seconds:02}"


def _source(source: dict) -> str:
    if source["type"] == "transcript":
        quote = f" “{escape(source['quote'])}”" if source.get("quote") else ""
        return (
            f'<span style="color: {BLUE}"><b>{escape(source["pair_id"])}'
            f"{_time(source.get('start_ms'))}</b>{quote}</span>"
        )
    name = f"{source['requirement_id']} {source['requirement']}"
    result = CV_RESULTS.get(source.get("status"))
    if result is None:
        return _chip(f"{name} · CV not screened", GREY)
    return _chip(f"{name} · {result[0]}", result[1])


def _points(claims: list[dict] | None, empty: str) -> str:
    if not claims:
        return f'<p class="small">{escape(empty)}</p>'
    parts = []
    for claim in claims:
        sources = " &#160; ".join(_source(source) for source in claim["sources"])
        parts.append(f'<p class="point">{escape(claim["text"])}</p>')
        if sources:
            parts.append(f'<p class="sources">{sources}</p>')
    return "".join(parts)


def _status(context: dict) -> str:
    if context["status"] == "approved":
        by = f" by {escape(context['approved_by'])}" if context.get("approved_by") else ""
        when = f", {escape(context['approved_on'])}" if context.get("approved_on") else ""
        return f"{_chip('Approved', GREEN)}<br/><span class='small'>{by.strip()}{when}</span>"
    return f"{_chip('Draft', AMBER)}<br/><span class='small'>not yet reviewed</span>"


def report_html(context: dict) -> str:
    """Page 1: the report itself."""
    label = LABELS.get(context["suitability"])
    chip = f" &#160;{_chip(label[0], label[1])}" if label else ""
    if context["overall_score"] is not None:
        cv, interview = _score(context["cv_score"]), _score(context["interview_score"])
        overall_note = f"{cv} × 40% + {interview} × 60% · decision support only"
    elif context["interview_score"] is None:
        overall_note = "no job-related questions"
    else:
        overall_note = "no CV score"
    answers = context["answers_evaluated"]
    return f"""
<table style="width: 100%; border-bottom: 2px solid {BLUE}">
<tr><td style="border: none; padding: 0 0 6pt 0">
<p class="brand">HireLucent · Candidate assessment report</p>
<h1>{escape(context["candidate_name"])}</h1>
<p>{escape(context["job_title"])} · {escape(context["job_code"])} · Interview
{escape(context["interview_when"])}</p>
</td><td style="border: none; text-align: right; vertical-align: top">
{_status(context)}</td></tr>
</table>
<table style="width: 100%; margin-top: 8pt">
<tr>
<td class="box" width="31%"><span class="label">CV SCORE</span><br/>
<span class="score">{_score(context["cv_score"])}</span><br/>
<span class="small">from screening · 40%</span></td>
<td style="border: none" width="3%"></td>
<td class="box" width="31%"><span class="label">INTERVIEW SCORE</span><br/>
<span class="score">{_score(context["interview_score"])}</span><br/>
<span class="small">{answers} {"answer" if answers == 1 else "answers"} · 60%</span></td>
<td style="border: none" width="3%"></td>
<td class="box" width="32%"><span class="label">OVERALL</span><br/>
<span class="score">{_score(context["overall_score"])}</span>{chip}<br/>
<span class="small">{escape(overall_note)}</span></td>
</tr>
</table>
<h2>Summary</h2>
<p style="color: {NAVY}; font-size: 10pt">{escape(context["summary"] or "")}</p>
<h2>Strengths ({len(context["strengths"] or [])})</h2>
{_points(context["strengths"], "No strength could be traced to the CV or the transcript.")}
<h2>Weaknesses ({len(context["weaknesses"] or [])})</h2>
{_points(context["weaknesses"], "No weakness was found.")}
<h2>Evidence gaps ({len(context["gaps"] or [])})</h2>
<p class="small">Requirements the interview never explored.</p>
{_points(context["gaps"], "None.")}
<h2>Areas to verify ({len(context["areas_to_verify"] or [])})</h2>
<p class="small">To double-check before deciding.</p>
{_points(context["areas_to_verify"], "None.")}
<p class="small" style="margin-top: 10pt">Sources: Q = interview question with its time in
the interview and the candidate's words; R = job requirement with what CV screening found.
Points the AI could not trace to a source were left out.</p>
"""


def appendix_html(context: dict) -> str:
    """The pages after the report: requirement coverage, then every question
    with its score."""
    coverage_rows = []
    for entry in context["coverage"]:
        status = COVERAGE.get(entry["status"], (entry["status"], GREY))
        cv = CV_RESULTS.get((entry.get("cv") or {}).get("status"))
        questions = ", ".join(item["pair_id"] for item in entry["question_scores"]) or "–"
        coverage_rows.append(
            "<tr>"
            f"<td><b>{escape(entry['requirement_id'])}</b> {escape(entry['text'])}</td>"
            f"<td>{PRIORITIES.get(entry['priority'], escape(entry['priority']))}</td>"
            f"<td>{_chip(status[0], status[1])}</td>"
            f"<td>{_score(entry['average'])}</td>"
            f"<td>{escape(questions)}</td>"
            f"<td>{_chip(cv[0].removeprefix('CV: '), cv[1]) if cv else 'Not screened'}</td>"
            "</tr>"
        )
    question_rows = []
    for pair in context["pairs"]:
        evaluation = pair.get("evaluation")
        if evaluation is None:
            score, accuracy = "–", "Not scored"
        elif evaluation["answered"] == "not_answered":
            score, accuracy = _score(evaluation["score"]), "Not answered"
        else:
            source = (evaluation.get("accuracy_source") or {}).get("type")
            score, accuracy = _score(evaluation["score"]), ACCURACY.get(source, "–")
        question_rows.append(
            "<tr>"
            f"<td><b>{escape(pair['id'])}</b></td>"
            f"<td>{escape(pair['question'])}</td>"
            f"<td>{KINDS.get(pair['kind'], escape(pair['kind']))}</td>"
            f"<td><b>{score}</b></td>"
            f"<td>{accuracy}</td>"
            "</tr>"
        )
    no_rows = '<tr><td colspan="6">None.</td></tr>'
    return f"""
<p class="small">{escape(context["candidate_name"])} · {escape(context["job_title"])} ·
Appendix</p>
<h2>A · Requirement coverage</h2>
<p class="small">Covered = average answer score 60 or more. Weak = asked, but below 60.
Not explored = no question touched it.</p>
<table style="width: 100%">
<tr><th>Requirement</th><th>Priority</th><th>In the interview</th><th>Average</th>
<th>Questions</th><th>CV screening</th></tr>
{"".join(coverage_rows) or no_rows}
</table>
<h2>B · Questions and scores</h2>
<p class="small">Each answer is scored 0–100 on relevance, accuracy, completeness and
articulation. Small talk is not scored. Full answers and reasons are in HireLucent.</p>
<table style="width: 100%">
<tr><th>#</th><th>Question</th><th>Kind</th><th>Score</th><th>Accuracy</th></tr>
{"".join(question_rows) or no_rows}
</table>
"""


def _write(writer: pymupdf.DocumentWriter, html: str) -> None:
    """Write one part on as many pages as it needs, starting a new page."""
    story = pymupdf.Story(html=html, user_css=CSS)
    more = True
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(CONTENT)
        story.draw(device)
        writer.end_page()


def build_pdf(context: dict) -> bytes:
    """The report and its appendix as PDF bytes, with a footer on every page."""
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    _write(writer, report_html(context))
    _write(writer, appendix_html(context))
    writer.close()

    document = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    footer = (
        "HireLucent · Confidential: for the hiring team only · "
        f"Generated {context['generated_on']}"
    )
    total = len(document)
    for number, page in enumerate(document, start=1):
        y = PAGE.height - MARGIN + 4
        page.insert_text((MARGIN, y), footer, fontsize=7, color=(0.48, 0.53, 0.61))
        text = f"Page {number} of {total}"
        width = pymupdf.get_text_length(text, fontsize=7)
        page.insert_text(
            (PAGE.width - MARGIN - width, y), text, fontsize=7, color=(0.48, 0.53, 0.61)
        )
    document.set_metadata({"title": "Candidate assessment report", "creator": "HireLucent"})
    return document.tobytes(garbage=3, deflate=True)


def report_context(assessment, session, job, time_zone: str | None) -> dict:
    """Everything the PDF shows, from the saved assessment. Dates and times
    are in the interviewer's time zone."""
    zone = _zone(time_zone)
    now = datetime.now(timezone.utc)
    start = session.started_at or session.scheduled_start
    end = session.ended_at or session.scheduled_end
    candidate = session.candidate
    return {
        "candidate_name": candidate.full_name if candidate else "",
        "job_title": job.title,
        "job_code": job.job_code,
        "interview_when": (
            f"{_day(start, zone)}, {_clock(start, zone)} – {_clock(end, zone)}"
        ),
        "status": assessment.status,
        "approved_by": assessment.approved_by_name,
        "approved_on": _day(assessment.approved_at, zone) if assessment.approved_at else None,
        "cv_score": assessment.cv_score,
        "interview_score": assessment.interview_score,
        "overall_score": assessment.overall_score,
        "suitability": assessment.suitability,
        "answers_evaluated": len(scoring.evaluated(assessment.qa_evaluations)),
        "summary": assessment.report,
        "strengths": assessment.strengths,
        "weaknesses": assessment.weaknesses,
        "gaps": assessment.gaps,
        "areas_to_verify": assessment.areas_to_verify,
        "coverage": assessment.coverage_map,
        "pairs": assessment.qa_evaluations,
        "generated_on": f"{_day(now, zone)}, {_clock(now, zone)}",
    }


def file_name(job_code: str, start: datetime) -> str:
    """"assessment_HL-BE-01_2026-10-13.pdf". The candidate's name is left out
    of the file name, which shows up in download lists and email attachments."""
    code = "".join(char if char.isalnum() or char in "_-" else "-" for char in job_code)
    return f"assessment_{code}_{start:%Y-%m-%d}.pdf"
