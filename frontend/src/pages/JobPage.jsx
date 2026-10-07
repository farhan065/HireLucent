import { ExternalLink } from 'lucide-react'
import { Link, Navigate, Outlet, useLocation, useOutletContext, useParams } from 'react-router'
import JobTabs from '../components/jobs/JobTabs.jsx'
import StatusChip from '../components/StatusChip.jsx'
import { useJob } from '../hooks/useJob.js'
import { JOB_STAGES, formatDate, jobStage } from '../lib/jobs.js'

// One job's own page: its header and stage tabs, with the chosen tab below.
export default function JobPage() {
  const { jobId } = useParams()
  const { pathname } = useLocation()
  const { job, threadId, waiting, error, reload } = useJob(jobId)

  if (error) {
    return (
      <p role="alert" className="font-semibold text-danger">
        {error}
      </p>
    )
  }
  if (!job) return <p role="status">Loading the job…</p>

  const stage = JOB_STAGES[jobStage(job)]
  const current = pathname.endsWith('/screening') ? 'screening' : 'applications'

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm">
        <Link to="/app/jobs" className="font-semibold text-brand hover:text-brand-dark">
          Jobs
        </Link>
        <span aria-hidden="true">›</span>
        <span className="font-semibold text-navy">{job.title}</span>
      </nav>

      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">{job.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[15px]">
            <span>{job.job_code}</span>
            <StatusChip tone={stage.tone}>{stage.label}</StatusChip>
            {job.published_at && <span>Published {formatDate(job.published_at)}</span>}
          </div>
        </div>
        {job.post_url && (
          <a
            href={job.post_url}
            target="_blank"
            rel="noreferrer"
            className="flex min-h-10 items-center gap-1.5 text-[15px] font-semibold text-brand hover:text-brand-dark"
          >
            <ExternalLink className="size-4" aria-hidden="true" />
            View the public post
          </a>
        )}
      </header>

      <JobTabs job={job} threadId={threadId} waiting={waiting} current={current} />

      <Outlet context={{ job, threadId, waiting, reload }} />
    </div>
  )
}

// Opening a job lands on the stage it has reached.
export function JobIndex() {
  const { job, threadId } = useOutletContext()
  if (job.status !== 'published' && threadId) {
    return <Navigate to={`/app/assistant/${threadId}`} replace />
  }
  const tab = jobStage(job) === 'published' ? 'applications' : 'screening'
  return <Navigate to={tab} replace />
}
