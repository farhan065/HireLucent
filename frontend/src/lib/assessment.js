// The post-interview assessment: evaluating interviews and showing what the
// evaluation found. Scores, labels and colours are worked out here, so the
// pages and cards only lay them out.
import { apiFile, apiRequest, ApiError } from './api.js'
import { dateValue } from './interviews.js'

export function evaluateInterview(sessionId) {
  return apiRequest(`/interviews/${sessionId}/evaluate`, { method: 'POST' })
}

// Writes only the report of an interview whose answers are evaluated.
export function writeReport(sessionId) {
  return apiRequest(`/interviews/${sessionId}/report`, { method: 'POST' })
}

// Compares the CV's claims with the interview, without touching the report
// (an interview evaluated before CV claim checks, or Check again).
export function checkClaims(sessionId) {
  return apiRequest(`/interviews/${sessionId}/assessment/claims`, { method: 'POST' })
}

// Marks a contradiction or unverified claim: action is 'checked',
// 'dismissed' or 'reopen'. Returns the assessment.
export function reviewClaim(sessionId, claimId, action, note = '') {
  return apiRequest(`/interviews/${sessionId}/assessment/claims/${claimId}/review`, {
    method: 'POST',
    body: { action, note: note.trim() || null },
  })
}

// Evaluates every completed interview of the job not evaluated yet.
export function evaluateAll(jobId) {
  return apiRequest(`/jobs/${jobId}/evaluate`, { method: 'POST' })
}

// { running, last, waiting }: see the backend's EvaluationActivity.
export function readEvaluation(jobId) {
  return apiRequest(`/jobs/${jobId}/evaluation`)
}

// The assessment, or null when the interview has not been evaluated yet.
export async function readAssessment(sessionId) {
  try {
    return await apiRequest(`/interviews/${sessionId}/assessment`)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404 && error.code === 'not_found') {
      return null
    }
    throw error
  }
}

// Adds the ticked suggestions to the question bank; returns them all.
export function addQuestions(sessionId, pairIds) {
  return apiRequest(`/interviews/${sessionId}/assessment/questions`, {
    method: 'POST',
    body: { pair_ids: pairIds },
  })
}

// --- Where an interview's evaluation stands ---

// What the evaluation of one interview is doing, from the job's
// evaluation status: { state, message, percent, reason }. state is
// "running" (this interview now), "queued" (later in an Evaluate all),
// "failed" (the last run could not evaluate it) or null.
export function evaluationOf(activity, sessionId) {
  const running = activity?.running
  if (running) {
    const ids = running.result?.session_ids ?? []
    const current = running.result?.current ?? ids[0]
    // Only the CV claims are being checked: the rest of the page stays.
    if (current === sessionId && running.result?.claims_only) return { state: 'checking_claims' }
    if (current === sessionId) {
      return { state: 'running', message: answersPart(running.message), percent: running.percent }
    }
    if (ids.includes(sessionId)) return { state: 'queued' }
  }
  const failure = activity?.last?.result?.failures?.find((item) => item.session_id === sessionId)
  if (failure && activity.last.result.claims_only) {
    return { state: 'claims_failed', reason: failure.reason }
  }
  if (failure) return { state: 'failed', reason: failure.reason }
  // A run of this one interview that failed outright keeps only its message.
  const last = activity?.last
  if (
    last?.status === 'failed' &&
    last.result?.session_ids?.length === 1 &&
    last.result.session_ids[0] === sessionId
  ) {
    return { state: 'failed', reason: last.error_message }
  }
  return { state: null }
}

// "5 of 8 answers evaluated" from the task's "Interview 1 of 1 · 5 of 8
// answers evaluated", or the start of the work.
export function answersPart(message) {
  const parts = (message ?? '').split(' · ')
  return parts.length > 1 ? parts.slice(1).join(' · ') : 'starting'
}

// Which interview of an Evaluate all is being evaluated: { index, total }.
export function batchPosition(running) {
  const ids = running?.result?.session_ids ?? []
  if (ids.length < 2) return null
  const index = ids.indexOf(running.result.current)
  return { index: Math.max(index, 0) + 1, total: ids.length, sessionId: running.result.current }
}

// --- Labels and colours ---

export const KINDS = {
  technical: { label: 'Technical', className: 'bg-tint text-brand-dark' },
  behavioural: { label: 'Behavioural', className: 'bg-violet-soft text-violet' },
  company: { label: 'Company', className: 'bg-teal-soft text-teal' },
  small_talk: { label: 'Small talk', className: 'bg-mist text-body' },
}

export const KIND_FILTERS = ['technical', 'behavioural', 'company', 'small_talk']

// Where an accuracy judgement came from, as a chip.
export const SOURCES = {
  reference: { label: 'Verified', className: 'bg-success-soft text-success' },
  ai_judgement: { label: 'AI interviewer', className: 'bg-[#EEF1F6] text-[#44526B]' },
  not_checked: { label: 'Not checked', className: 'bg-warning-soft text-warning' },
}

export const NOT_ANSWERED = { label: 'Not answered', className: 'bg-danger-soft text-danger' }

// The colour of a 0–100 score: green from 75, blue from 60, amber from 40,
// red below.
export function scoreTone(score) {
  if (score == null) return { chip: 'bg-[#F4F6FA] text-[#7B879C]', bar: 'bg-[#9AA6BA]' }
  if (score >= 75) return { chip: 'bg-success-soft text-success', bar: 'bg-success' }
  if (score >= 60) return { chip: 'bg-tint text-brand-dark', bar: 'bg-brand' }
  if (score >= 40) return { chip: 'bg-warning-soft text-warning', bar: 'bg-[#D97706]' }
  return { chip: 'bg-danger-soft text-danger', bar: 'bg-danger' }
}

export function roundScore(score) {
  return score == null ? null : Math.round(score)
}

export const CRITERIA = [
  ['relevance', 'Relevance'],
  ['accuracy', 'Accuracy'],
  ['completeness', 'Completeness'],
  ['articulation', 'Articulation'],
]

// The criteria that feed only the interview performance dimensions (F9),
// given only when an answer shows them. They never change the answer's score.
export const SHOWN_CRITERIA = [
  [
    'problem_solving',
    'Problem-solving',
    'This answer does not show how the candidate works through a problem, so it is left out of problem-solving.',
  ],
  [
    'depth',
    'Depth of experience',
    "This answer does not describe the candidate's own past work, so it is left out of depth of experience.",
  ],
]

// An evaluation judged with problem-solving and depth (F9). Answers
// evaluated before F9 have neither key.
export function isF9Evaluation(evaluation) {
  return evaluation != null && 'problem_solving' in evaluation
}

// Short names of the six interview performance dimensions, for small bars.
export const DIMENSION_SHORT = {
  technical: 'Technical',
  communication: 'Communication',
  relevance: 'Relevance',
  problem_solving: 'Problem-solving',
  depth: 'Depth',
  alignment: 'Alignment',
}

// What the interview score tile and lists say under the score.
export function interviewNote(row, answers) {
  const dims = row.interview_dimensions
  if (dims) return `${dims.assessed} of ${dims.total} dimensions`
  if (row.interview_score == null) return 'no job questions'
  return `${answers} ${answers === 1 ? 'answer' : 'answers'}`
}

// Why there is no interview score, when there is none.
export function noInterviewScore(row) {
  const dims = row.interview_dimensions
  if (dims && dims.assessed > 0) {
    return `not enough interview evidence (${dims.assessed} of ${dims.total} dimensions)`
  }
  return 'the interview had no job-related questions'
}

export const COVERAGE = {
  covered: { label: 'Covered', className: 'bg-success-soft text-success', bar: 'bg-success' },
  weak: { label: 'Weak', className: 'bg-warning-soft text-warning', bar: 'bg-[#D97706]' },
  not_explored: { label: 'Not explored', className: 'bg-[#EEF1F6] text-[#44526B]', bar: '' },
}

export const CV_RESULTS = {
  met: { label: 'CV: met', className: 'bg-success-soft text-success' },
  partially_met: { label: 'CV: partly met', className: 'bg-warning-soft text-warning' },
  unmet: { label: 'CV: not met', className: 'bg-danger-soft text-danger' },
}

// A CV claim's result (F8), as a chip.
export const CLAIM_RESULTS = {
  contradiction: { label: 'Contradiction', className: 'bg-amber-soft text-amber' },
  unverified: { label: 'Unverified', className: 'bg-violet-soft text-violet' },
  not_discussed: { label: 'Not discussed', className: 'bg-[#EEF1F6] text-[#44526B]' },
  consistent: { label: 'Consistent', className: 'bg-success-soft text-success' },
  not_checked: { label: 'Not checked', className: 'bg-[#EEF1F6] text-[#44526B]' },
}

// Where in the CV a claim comes from.
export const CLAIM_SECTIONS = {
  total_experience: 'Total experience',
  work_experience: 'Work experience',
  project: 'Project',
  certification: 'Certification',
  education: 'Education',
  skill: 'Skill',
}

// The order claims are listed in: what to check first.
export const CLAIM_ORDER = ['contradiction', 'unverified', 'consistent', 'not_discussed']

// Contradictions and unverified claims the interviewer has not marked yet.
export function openClaims(checks, result = null) {
  return (checks?.status === 'checked' ? checks.claims : []).filter(
    (claim) =>
      ['contradiction', 'unverified'].includes(claim.result) &&
      !claim.review &&
      (result === null || claim.result === result),
  )
}

// --- Summaries ---

// The counts the Q&A tab shows above its list.
export function qaSummary(pairs) {
  const evaluated = pairs.filter((pair) => pair.evaluation)
  const scores = evaluated.map((pair) => pair.evaluation.score)
  const sources = { reference: 0, ai_judgement: 0, not_checked: 0 }
  evaluated.forEach((pair) => {
    const type = pair.evaluation.accuracy_source?.type
    if (type in sources) sources[type] += 1
  })
  return {
    total: pairs.length,
    evaluated: evaluated.length,
    smallTalk: pairs.filter((pair) => pair.kind === 'small_talk').length,
    average: scores.length
      ? Math.round(scores.reduce((sum, score) => sum + score, 0) / scores.length)
      : null,
    sources,
    notAnswered: evaluated.filter((pair) => pair.evaluation.answered === 'not_answered').length,
  }
}

export function kindCounts(pairs) {
  return Object.fromEntries(
    KIND_FILTERS.map((kind) => [kind, pairs.filter((pair) => pair.kind === kind).length]),
  )
}

// The counts the coverage tab shows above its table.
export function coverageSummary(coverage) {
  const count = (status) => coverage.filter((entry) => entry.status === status).length
  return {
    covered: count('covered'),
    weak: count('weak'),
    notExplored: count('not_explored'),
    mixed: coverage.filter((entry) => entry.mixed).length,
    mustHaveNotExplored: coverage.filter(
      (entry) => entry.status === 'not_explored' && entry.priority === 'must_have',
    ).length,
  }
}

// A requirement worth a second look: not covered, or covered with a poor
// answer.
export function needsAttention(entry) {
  return entry.status !== 'covered' || entry.mixed
}

// "R2 FastAPI" for a pair's requirement chips, from the coverage entries.
export function requirementNames(coverage) {
  return Object.fromEntries(
    coverage.map((entry) => [entry.requirement_id, `${entry.requirement_id} ${entry.text}`]),
  )
}

// The transcript turns of a pair, by id, for showing the answer.
export function turnsById(turns) {
  return new Map(turns.map((turn) => [turn.id, turn]))
}

// --- The job's ranked list -------------------------------------------------

// Every completed interview of the job: ranked rows first, then unranked.
export function readRanking(jobId) {
  return apiRequest(`/jobs/${jobId}/assessments`)
}

// The shares the backend uses for the overall score.
export const CV_SHARE = 0.4
export const INTERVIEW_SHARE = 0.6

export const SUITABILITY = {
  strong_fit: {
    label: 'Strong fit',
    note: 'overall 70 or more',
    className: 'bg-success-soft text-success',
    bar: 'bg-success',
  },
  possible_fit: {
    label: 'Possible fit',
    note: 'overall 60–69',
    className: 'bg-tint text-brand-dark',
    bar: 'bg-brand',
  },
  not_a_fit: {
    label: 'Not a fit',
    note: 'overall below 60',
    className: 'bg-danger-soft text-danger',
    bar: 'bg-danger',
  },
}

// What an interview's assessment status means, as a chip.
export const REPORT_STATUS = {
  analysed: { label: 'Answers evaluated', className: 'bg-tint text-brand-dark' },
  draft: { label: 'Draft report', className: 'bg-amber-soft text-amber' },
  approved: { label: 'Report approved', className: 'bg-success-soft text-success' },
}

export const RANK_FILTERS = [
  ['all', 'All'],
  ['strong_fit', 'Strong fit'],
  ['possible_fit', 'Possible fit'],
  ['not_a_fit', 'Not a fit'],
  ['review', 'Needs review'],
]

export function matchesRankFilter(row, filter) {
  if (filter === 'all') return true
  if (filter === 'review') return row.status === 'draft'
  return row.suitability === filter
}

// The counts above the list.
export function rankingSummary(rows) {
  const count = (test) => rows.filter(test).length
  return {
    strong_fit: count((row) => row.suitability === 'strong_fit'),
    possible_fit: count((row) => row.suitability === 'possible_fit'),
    not_a_fit: count((row) => row.suitability === 'not_a_fit'),
    review: count((row) => row.status === 'draft'),
  }
}

// 84.24 → 84.2, 74.0 → 74
export function oneDecimal(value) {
  return value == null ? null : Math.round(value * 10) / 10
}

// The two parts of the overall score, for "How the score is made".
export function scoreParts(row) {
  return {
    cv: oneDecimal(row.cv_score * CV_SHARE),
    interview: oneDecimal(row.interview_score * INTERVIEW_SHARE),
  }
}

// Why an unranked interview has no place in the ranking yet.
export function unrankedReason(row) {
  if (!row.status) return 'Interview completed. Not evaluated yet.'
  if (row.status === 'analysed') {
    return 'Answers evaluated. The report has not been written yet.'
  }
  if (row.interview_score == null) {
    return `No overall score: ${noInterviewScore(row)}.`
  }
  return 'No overall score: the candidate has no CV score.'
}

// The Assessments tab is done when every completed interview has an
// approved report: none waits to be evaluated and no draft waits for review.
export function allAssessed(interviews) {
  const completed = (interviews ?? []).filter((item) => item.status === 'completed')
  return completed.length > 0 && completed.every((item) => item.assessment_status === 'approved')
}

// How many drafts wait for review, from the interviews list.
export function draftsToReview(interviews) {
  return (interviews ?? []).filter((item) => item.assessment_status === 'draft').length
}

// --- Reviewing the report --------------------------------------------------

// action: "approve", "request_changes" (with note) or "edit" (summary and/or
// remove). Returns the assessment as it is afterwards.
export function reviewReport(sessionId, body) {
  return apiRequest(`/interviews/${sessionId}/assessment/review`, { method: 'POST', body })
}

// Approves every draft report of the job: { approved, skipped }.
export function approveAllDrafts(jobId) {
  return apiRequest(`/jobs/${jobId}/assessments/approve`, { method: 'POST' })
}

export const MAX_SUMMARY_CHARS = 1500
export const MAX_NOTE_CHARS = 1000

export function hasReport(assessment) {
  return assessment?.status === 'draft' || assessment?.status === 'approved'
}

// --- The report as a PDF ---------------------------------------------------

// The report PDF, with dates in the interviewer's time zone.
export function readReportPdf(sessionId) {
  const zone = Intl.DateTimeFormat().resolvedOptions().timeZone
  return apiFile(`/interviews/${sessionId}/assessment/report.pdf?tz=${encodeURIComponent(zone)}`)
}

// "assessment_HL-BE-01_2026-10-13.pdf". The candidate's name is left out of
// the file name, which shows up in download lists and email attachments.
export function reportFileName(info) {
  const code = info.job_code.replace(/[^A-Za-z0-9_-]+/g, '-')
  const day = new Date(info.interview.started_at ?? info.interview.scheduled_start)
  return `assessment_${code}_${dateValue(day)}.pdf`
}

// Saves the PDF under its file name.
export function saveFile(file, name) {
  const url = URL.createObjectURL(file)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 60_000)
}

// Opens the browser's print dialog for the PDF, from a hidden frame. Where
// a browser cannot print from a frame, the PDF opens in a new tab instead.
export function printFile(file) {
  const url = URL.createObjectURL(file)
  const frame = document.createElement('iframe')
  frame.style.position = 'fixed'
  frame.style.width = '0'
  frame.style.height = '0'
  frame.style.border = '0'
  frame.src = url
  frame.onload = () => {
    try {
      frame.contentWindow.focus()
      frame.contentWindow.print()
    } catch {
      window.open(url, '_blank')
    }
    // The frame stays until the print dialog has surely closed.
    setTimeout(() => {
      frame.remove()
      URL.revokeObjectURL(url)
    }, 60_000)
  }
  document.body.appendChild(frame)
}

// --- Comparing candidates --------------------------------------------------

export const MAX_COMPARED = 3

// The address of the comparison of the picked interviews.
export function compareTo(jobId, sessionIds) {
  return `/app/jobs/${jobId}/compare?ids=${sessionIds.join(',')}`
}

// The interview ids in the comparison's address, at most MAX_COMPARED.
export function comparedIds(value) {
  return [
    ...new Set(
      (value ?? '')
        .split(',')
        .map(Number)
        .filter((id) => Number.isInteger(id) && id > 0),
    ),
  ].slice(0, MAX_COMPARED)
}

// For each candidate, whether its value is the best (highest) among those
// compared. Empty values are never best, nothing is best on its own, and
// when every value is the same nobody stands out.
export function bestOf(values) {
  const present = values.filter((value) => value != null)
  const top = Math.max(...present)
  if (present.length < 2 || present.every((value) => value === top)) {
    return values.map(() => false)
  }
  return values.map((value) => value != null && value === top)
}

// Every requirement any compared candidate has, in the job's order.
export function comparedRequirements(rows) {
  const seen = new Map()
  rows.forEach((row) =>
    (row.coverage_map ?? []).forEach((entry) => {
      if (!seen.has(entry.requirement_id)) seen.set(entry.requirement_id, entry)
    }),
  )
  return [...seen.values()]
}
