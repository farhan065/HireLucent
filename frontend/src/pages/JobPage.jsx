import { ExternalLink } from 'lucide-react'
import { useCallback, useState } from 'react'
import {
  Link,
  Navigate,
  Outlet,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
} from 'react-router'
import DeleteJobButton from '../components/jobs/DeleteJobButton.jsx'
import JobTabs from '../components/jobs/JobTabs.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusChip from '../components/StatusChip.jsx'
import { useEvaluation } from '../hooks/useEvaluation.js'
import { useInterviews } from '../hooks/useInterviews.js'
import { useJob } from '../hooks/useJob.js'
import { useJobActivity } from '../hooks/useJobActivity.js'
import { countToday, countWaiting } from '../lib/interviews.js'
import { JOB_STAGES, formatDate, jobStage } from '../lib/jobs.js'

const TABS = ['applications', 'screening', 'interviews']

function LoadingJob() {
  return (
    <div role="status" aria-label="Loading the job" className="flex flex-col gap-6">
      <Skeleton className="h-4 w-40" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-9 w-80" />
        <Skeleton className="h-5 w-64" />
      </div>
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-40 w-full rounded-card" />
    </div>
  )
}

// One job's own page: its header and stage tabs, with the chosen tab below.
export default function JobPage() {
  const { jobId } = useParams()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { job, threadId, waiting, error, reload } = useJob(jobId)

  // When a fetch or a screening ends, the job and its candidates load again.
  const [listVersion, setListVersion] = useState(0)
  const handleFinished = useCallback(() => {
    reload()
    setListVersion((version) => version + 1)
  }, [reload])
  const run = useJobActivity(jobId, handleFinished)
  // Interviews are loaded here, so the tab's "today" badge and the
  // Interviews tab share one list.
  const interviews = useInterviews(job?.status === 'published' ? jobId : null, listVersion)
  // Interview evaluations. When one ends, the interviews load again, so their
  // rows show View assessment.
  const evaluation = useEvaluation(job?.status === 'published' ? jobId : null, handleFinished)

  // After a shortlist change or a deletion, the same as after a run.
  function handleChanged() {
    handleFinished()
    run.reload()
  }

  if (error) {
    return (
      <p role="alert" className="font-semibold text-danger">
        {error}
      </p>
    )
  }

  const stage = job && JOB_STAGES[jobStage(job)]
  const current = TABS.find((tab) => pathname.endsWith(`/${tab}`)) ?? 'applications'

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      {!job ? (
        <LoadingJob />
      ) : (
        <>
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
            <div className="flex flex-wrap items-center gap-5">
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
              <DeleteJobButton
                job={job}
                label="Delete job"
                onDeleted={() => navigate('/app/jobs', { replace: true })}
              />
            </div>
          </header>

          <JobTabs
            job={job}
            threadId={threadId}
            waiting={waiting}
            today={countToday(interviews.interviews, interviews.now)}
            inWaitingRoom={countWaiting(interviews.interviews)}
            current={current}
          />

          <Outlet
            context={{
              job,
              threadId,
              waiting,
              run,
              listVersion,
              interviews,
              evaluation,
              onChanged: handleChanged,
            }}
          />
        </>
      )}
    </div>
  )
}

// Opening a job lands on the stage it has reached.
export function JobIndex() {
  const { job, threadId } = useOutletContext()
  if (job.status !== 'published' && threadId) {
    return <Navigate to={`/app/assistant/${threadId}`} replace />
  }
  const tab = {
    published: 'applications',
    cvs_screened: 'screening',
    interviews_scheduled: 'interviews',
  }[jobStage(job)]
  return <Navigate to={tab ?? 'applications'} replace />
}
