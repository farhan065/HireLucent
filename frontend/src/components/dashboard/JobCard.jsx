import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { STAGE_LABELS, WAITING_STAGES } from '../../lib/stages.js'
import StatusChip from '../StatusChip.jsx'

const JOB_STATUS_CHIPS = {
  approved: { tone: 'info', label: 'Saved, not published' },
  published: { tone: 'success', label: 'Published' },
  archived: { tone: 'neutral', label: 'Archived' },
}

const SCREENED = ['screened', 'shortlisted', 'selected', 'interview_scheduled', 'assessed']
const SHORTLISTED = ['shortlisted', 'selected', 'interview_scheduled', 'assessed']

function count(counts, statuses) {
  return statuses.reduce((sum, status) => sum + (counts[status] ?? 0), 0)
}

// The candidate pipeline of one job as a row of counts.
function Pipeline({ counts }) {
  const stages = [
    ['Applied', Object.values(counts).reduce((sum, value) => sum + value, 0)],
    ['Screened', count(counts, SCREENED)],
    ['Shortlisted', count(counts, SHORTLISTED)],
    ['Assessed', count(counts, ['assessed'])],
  ]
  return (
    <div className="flex flex-wrap gap-3">
      {stages.map(([label, value]) => (
        <div key={label} className="flex flex-1 basis-16 flex-col gap-1.5">
          <div className={`h-1.5 rounded-full ${value > 0 ? 'bg-brand' : 'bg-line'}`} />
          <span className="font-display text-lg font-bold text-navy">{value}</span>
          <span className="text-xs">{label}</span>
        </div>
      ))}
    </div>
  )
}

function nextStep(job, conversation) {
  if (!job) return STAGE_LABELS[conversation.stage].toLowerCase()
  if (job.status === 'approved') return 'publish the job'
  if (job.status === 'published') return 'collect and screen CVs'
  return 'none, this job is archived'
}

// One job on the dashboard. A job that is still being drafted has a
// conversation but no saved job yet.
export default function JobCard({ job, conversation, onViewDetails }) {
  const isWaiting = conversation && WAITING_STAGES.includes(conversation.stage)
  const chip = job
    ? JOB_STATUS_CHIPS[job.status]
    : { tone: isWaiting ? 'info' : 'neutral', label: isWaiting ? 'Waiting for you' : 'Draft' }

  return (
    <article className="flex animate-rise-in flex-col gap-4 rounded-card border border-line bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold">{job ? job.job_code : 'Not saved yet'}</p>
          <h3 className="mt-1 truncate text-xl font-bold">{job?.title ?? conversation.title}</h3>
        </div>
        <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
      </div>

      <Pipeline counts={job?.candidate_counts ?? {}} />

      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
        <span className="text-sm">
          <strong className="text-navy">Next:</strong> {nextStep(job, conversation)}
        </span>
        <div className="flex flex-wrap items-center gap-4">
          {job && (
            <button
              type="button"
              onClick={() => onViewDetails(job.id)}
              className="text-sm font-semibold text-brand hover:text-brand-dark"
            >
              View details
            </button>
          )}
          {conversation && (
            <Link
              to={`/app/assistant/${conversation.thread_id}`}
              className="flex min-h-10 items-center gap-1.5 rounded-full bg-tint px-4 text-sm font-bold text-brand-dark hover:bg-lavender"
            >
              {job ? 'Open' : 'Continue'} <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          )}
        </div>
      </div>
    </article>
  )
}
