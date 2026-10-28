// Decisions and feedback emails (innovation feature F11, Candidate Feedback
// Composer). The screens only lay these out: what each email status is
// called, which candidates are rejected at screening, and the API calls.
import { apiRequest, ApiError } from './api.js'

// --- API ---

// { running, last, screening_to_send, interview_to_send }
export function readFeedbackActivity(jobId) {
  return apiRequest(`/jobs/${jobId}/feedback`)
}

// Writes the emails of the given candidates in the background; returns a task.
export function writeEmails(jobId, candidateIds) {
  return apiRequest(`/jobs/${jobId}/feedback`, {
    method: 'POST',
    body: { candidate_ids: candidateIds },
  })
}

// Sends every draft of a stage ("screening" or "interview") that passed.
export function sendAllPassed(jobId, stage) {
  return apiRequest(`/jobs/${jobId}/feedback/send`, { method: 'POST', body: { stage } })
}

// The email, or null when none is written yet.
export async function readFeedback(candidateId) {
  try {
    return await apiRequest(`/candidates/${candidateId}/feedback`)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null
    throw error
  }
}

// action: approve, send_anyway, edit (subject, body), request_changes (note), discard.
export function reviewFeedback(candidateId, body) {
  return apiRequest(`/candidates/${candidateId}/feedback/review`, { method: 'POST', body })
}

// decision: "hire", "reject" or null.
export function setDecision(candidateId, decision) {
  return apiRequest(`/candidates/${candidateId}/decision`, {
    method: 'PUT',
    body: { decision },
  })
}

// rule: { top } or { min_score }; returns { hired, rejected, skipped }.
export function decideByRule(jobId, rule) {
  return apiRequest(`/jobs/${jobId}/decisions`, { method: 'POST', body: rule })
}

// --- Who is rejected at screening ---

// Everyone not shortlisted after screening counts as rejected.
export const SCREENING_REJECTED = ['screened', 'excluded', 'screening_failed']

export function isScreeningRejected(candidate) {
  return SCREENING_REJECTED.includes(candidate.status)
}

// Why a candidate was not shortlisted: a chip and a short line.
export function rejectionReason(candidate) {
  if (candidate.status === 'screening_failed') {
    return {
      label: 'CV not readable',
      className: 'bg-danger-soft text-danger',
      note: candidate.screening_error ?? 'The file could not be read.',
    }
  }
  if (candidate.status === 'excluded') {
    const missing = (candidate.excluded_reason ?? '')
      .split('\n')
      .map((line) => line.replace(/^Missing must-have \(([^)]+)\): /, '$1 '))
      .filter(Boolean)
    return {
      label: 'Missed a must-have',
      className: 'bg-amber-soft text-amber',
      note: missing.join(' · ') || 'A must-have requirement was not found.',
    }
  }
  const preferred = (candidate.requirement_matches ?? []).filter(
    (item) => item.priority === 'preferred' && item.status !== 'met',
  ).length
  return {
    label: 'Not shortlisted',
    className: 'bg-tint text-brand-dark',
    note:
      preferred > 0
        ? `All must-haves met · ${preferred} preferred not met`
        : 'All requirements met',
  }
}

// A candidate's stage on the Screening tab, following the interview and the
// decision: { tone, label } for StatusChip.
export function stageChip(candidate) {
  if (candidate.status === 'assessed') {
    if (candidate.decision === 'hire') return { tone: 'success', label: 'Hired' }
    if (candidate.decision === 'reject')
      return { tone: 'danger', label: 'Rejected after interview' }
    return { tone: 'info', label: 'Interviewed' }
  }
  if (candidate.status === 'interview_scheduled')
    return { tone: 'amber', label: 'Interview scheduled' }
  if (candidate.status === 'shortlisted') return { tone: 'teal', label: 'Shortlisted' }
  // Not shortlisted: still open until the rejection email goes out, which
  // is also when shortlisting locks.
  if (['sent', 'sending'].includes(candidate.feedback_status)) {
    return { tone: 'danger', label: 'Rejected' }
  }
  return { tone: 'neutral', label: 'Not shortlisted' }
}

// Who writes the first draft of a candidate's email.
export function draftBy(candidate) {
  if (candidate.status === 'screening_failed') return 'Fixed message'
  if (candidate.decision === 'hire' && candidate.status === 'assessed') return 'Fixed message'
  return 'AI'
}

// --- Email status ---

const CHIPS = {
  none: { label: 'Not written', className: 'bg-[#EEF1F6] text-[#44526B]' },
  writing: { label: 'Writing…', className: 'bg-tint text-brand-dark' },
  queued: { label: 'Waiting to be written', className: 'bg-tint text-brand-dark' },
  ready: { label: 'Ready to send', className: 'bg-success-soft text-success' },
  review: { label: 'Needs your review', className: 'bg-amber-soft text-amber' },
  sending: { label: 'Sending…', className: 'bg-tint text-brand-dark' },
  sent: { label: 'Sent', className: 'bg-tint text-brand-dark' },
  failed: { label: 'Not sent', className: 'bg-danger-soft text-danger' },
  discarded: {
    label: 'Discarded',
    className: 'border border-dashed border-line bg-mist text-[#6B7890]',
  },
}

// The chip for one candidate's email. "row" has feedback_status and
// feedback_warnings (a candidate or a ranked row); "activity" is the job's
// feedback activity, to show the email being written now.
export function emailState(row, candidateId, activity) {
  const running = activity?.running
  if (running?.kind === 'feedback_writing') {
    const ids = running.result?.candidate_ids ?? []
    if (running.result?.current === candidateId) return 'writing'
    if (ids.includes(candidateId) && !row.feedback_status) return 'queued'
  }
  if (running?.kind === 'feedback_sending' && running.result?.current === candidateId) {
    return 'sending'
  }
  switch (row.feedback_status) {
    case 'waiting_review':
      return row.feedback_warnings > 0 ? 'review' : 'ready'
    case 'sending':
      return 'sending'
    case 'sent':
      return 'sent'
    case 'failed':
      return 'failed'
    case 'discarded':
      return 'discarded'
    default:
      return 'none'
  }
}

export function emailChip(state) {
  return CHIPS[state] ?? CHIPS.none
}

// A small note under the chip.
export function emailNote(state, warnings) {
  if (state === 'ready') return 'Fairness check passed'
  if (state === 'review') return `${warnings} fairness ${warnings === 1 ? 'warning' : 'warnings'}`
  if (state === 'failed') return 'Google could not be reached'
  return ''
}

// The row's email action, or null when it has none.
export function emailAction(state) {
  return (
    {
      none: { label: 'Write email', write: true },
      discarded: { label: 'Write again', write: true },
      ready: { label: 'Review', primary: true },
      review: { label: 'Review', primary: true },
      failed: { label: 'Try again', primary: true },
      sent: { label: 'View email' },
    }[state] ?? null
  )
}

// Counts for the feedback bar: { none, ready, review, sent }.
export function countStates(states) {
  const counts = { none: 0, ready: 0, review: 0, sent: 0 }
  for (const state of states) {
    if (state === 'none' || state === 'discarded') counts.none += 1
    else if (state === 'ready') counts.ready += 1
    else if (state === 'review' || state === 'failed') counts.review += 1
    else if (state === 'sent') counts.sent += 1
  }
  return counts
}

// What each warning highlights, split out of the text: [{ text, mark }].
// Each warning's exact words (older drafts only have the sentence).
export function highlight(body, warnings) {
  const quotes = warnings
    .flatMap((warning) => (warning.words?.length ? warning.words : [warning.quote]))
    .map((quote) => quote?.trim())
    .filter((quote) => quote?.length > 1)
  if (!quotes.length) return [{ text: body, mark: false }]
  const parts = []
  let rest = body
  while (rest) {
    let first = null
    for (const quote of quotes) {
      const at = rest.indexOf(quote)
      if (at !== -1 && (first === null || at < first.at)) first = { at, quote }
    }
    if (!first) {
      parts.push({ text: rest, mark: false })
      break
    }
    if (first.at > 0) parts.push({ text: rest.slice(0, first.at), mark: false })
    parts.push({ text: first.quote, mark: true })
    rest = rest.slice(first.at + first.quote.length)
  }
  return parts
}

export const KIND_LABELS = {
  screening_reject: 'Screening',
  interview_reject: 'After the interview',
  hire: 'Selection',
  cv_unreadable: 'CV not readable',
}
