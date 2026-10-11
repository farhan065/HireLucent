import { Clock } from 'lucide-react'
import { Link } from 'react-router'
import { JOB_STAGES, formatDateTime, jobStage, lastUpdated } from '../../lib/jobs.js'
import { WAITING_STAGES } from '../../lib/stages.js'
import AgentAvatar from '../AgentAvatar.jsx'
import StatusChip from '../StatusChip.jsx'

const SCREENED = ['screened', 'shortlisted', 'selected', 'interview_scheduled', 'assessed']
const SHORTLISTED = ['shortlisted', 'selected', 'interview_scheduled', 'assessed']
const LINK = 'flex min-h-10 items-center gap-1.5 text-sm font-semibold text-brand hover:text-brand-dark'

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

// One job on the dashboard. A job that is still being drafted has a
// conversation but no saved job yet.
export default function JobCard({ card }) {
  const { job, conversation, waiting } = card
  const stage = JOB_STAGES[jobStage(job, conversation)]
  const needsDecision = conversation && WAITING_STAGES.includes(conversation.stage)
  const chatLink = conversation && `/app/assistant/${conversation.thread_id}`

  return (
    <article className="flex animate-rise-in flex-col gap-4 rounded-card border border-line bg-white p-6 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold">{job ? job.job_code : 'Not saved yet'}</p>
          <h3 className="mt-1 truncate text-xl font-bold">{job?.title ?? conversation.title}</h3>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <StatusChip tone={stage.tone}>{stage.label}</StatusChip>
          {needsDecision && <StatusChip tone="warning">Waiting for you</StatusChip>}
        </div>
      </div>

      <Pipeline counts={job?.candidate_counts ?? {}} />

      {waiting > 0 && (
        <p className="flex items-center gap-2.5 rounded-xl bg-warning-soft px-3.5 py-2 text-[15px] font-semibold text-warning">
          <span className="size-2 shrink-0 rounded-full bg-warning" aria-hidden="true" />
          {waiting} new {waiting === 1 ? 'application' : 'applications'}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3.5">
        <span className="flex items-center gap-1.5 text-[13px]">
          <Clock className="size-4" aria-hidden="true" />
          Updated {formatDateTime(lastUpdated(card))}
        </span>
        <div className="flex flex-wrap items-center gap-4">
          {chatLink && (
            <Link to={chatLink} className={LINK}>
              <AgentAvatar className="size-5" />
              {job ? 'AI Agent' : 'Continue with the AI Agent'}
            </Link>
          )}
          {job && (
            <Link
              to={`/app/jobs/${job.id}`}
              className="flex min-h-10 items-center rounded-full border-[1.5px] border-brand px-4 text-sm font-bold text-brand hover:bg-tint"
            >
              Open job page
            </Link>
          )}
        </div>
      </div>
    </article>
  )
}
