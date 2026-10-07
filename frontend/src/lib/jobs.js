// Shared helpers for showing jobs: their stage, their cards and their dates.
import { apiRequest } from './api.js'

// The stage a job has reached, in the order of the Journey in the job brief.
// "group" is the filter the stage belongs to on the Jobs page and Dashboard.
export const JOB_STAGES = {
  role_described: { label: 'Role described', tone: 'info', group: 'drafting' },
  description_approved: { label: 'Description approved', tone: 'info', group: 'drafting' },
  requirements_confirmed: { label: 'Requirements confirmed', tone: 'info', group: 'drafting' },
  published: { label: 'Published', tone: 'success', group: 'published' },
  cvs_screened: { label: 'CVs screened', tone: 'teal', group: 'cvs_screened' },
  interviews_scheduled: {
    label: 'Interviews scheduled',
    tone: 'amber',
    group: 'interviews_scheduled',
  },
  archived: { label: 'Archived', tone: 'neutral', group: 'archived' },
}

// The filters on the Jobs page and Dashboard. "selected" is how a filter
// looks when it is chosen, in the colour of its stage.
export const STAGE_GROUPS = {
  drafting: { label: 'Drafting', selected: 'border-brand bg-tint text-brand-dark' },
  published: { label: 'Published', selected: 'border-success bg-success-soft text-success' },
  cvs_screened: { label: 'CVs screened', selected: 'border-teal bg-teal-soft text-teal' },
  interviews_scheduled: {
    label: 'Interviews scheduled',
    selected: 'border-amber bg-amber-soft text-amber',
  },
  archived: { label: 'Archived', selected: 'border-body bg-mist text-navy' },
}

const SCREENED = ['screened', 'excluded', 'shortlisted', 'selected']
const INTERVIEWING = ['interview_scheduled', 'assessed']

function hasAny(counts, statuses) {
  return statuses.some((status) => (counts[status] ?? 0) > 0)
}

// A job that is still being drafted has a conversation but no saved job.
export function jobStage(job, conversation) {
  if (!job) {
    return conversation.stage === 'confirming_requirements'
      ? 'description_approved'
      : 'role_described'
  }
  if (job.status === 'archived') return 'archived'
  if (job.status !== 'published') return 'requirements_confirmed'
  if (hasAny(job.candidate_counts, INTERVIEWING)) return 'interviews_scheduled'
  if (hasAny(job.candidate_counts, SCREENED)) return 'cvs_screened'
  return 'published'
}

export function totalCandidates(job) {
  return Object.values(job?.candidate_counts ?? {}).reduce((sum, value) => sum + value, 0)
}

// Join saved jobs with their conversations, and add conversations that
// have not saved a job yet. Each entry is one job as the interviewer sees it.
export function buildCards(jobs, conversations) {
  const byJob = new Map(
    conversations.filter((item) => item.job_id).map((item) => [item.job_id, item]),
  )
  const drafts = conversations
    .filter((item) => !item.job_id)
    .map((conversation) => ({ key: conversation.thread_id, conversation }))
  const saved = jobs.map((job) => ({
    key: `job-${job.id}`,
    job,
    conversation: byJob.get(job.id),
  }))
  return [...drafts, ...saved]
}

// The most recent change to a job or to its conversation.
export function lastUpdated({ job, conversation }) {
  const times = [job?.updated_at, conversation?.updated_at].filter(Boolean)
  return times.sort().at(-1)
}

// Applications that arrived since the last fetch. Only a published job has
// a form to ask, and a failed request counts as none.
export async function loadWaiting(job) {
  if (job.status !== 'published') return 0
  const status = await apiRequest(`/jobs/${job.id}/intake/status`).catch(() => null)
  return status?.waiting ?? 0
}

// "07 Oct, 4:20 PM"
export function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  const day = date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  return `${day}, ${time}`
}

export function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}
