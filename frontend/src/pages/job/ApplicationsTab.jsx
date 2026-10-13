import { CircleAlert, Download } from 'lucide-react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import DeleteCandidateButton from '../../components/jobs/DeleteCandidateButton.jsx'
import {
  HEADING,
  Initials,
  ListCard,
  ViewCvLink,
} from '../../components/jobs/candidates.jsx'
import RunPanel from '../../components/jobs/RunPanel.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusChip from '../../components/StatusChip.jsx'
import { useCandidates } from '../../hooks/useCandidates.js'
import { formatDateTime, INTERVIEW_CHIP, SHORTLISTED_CHIP } from '../../lib/jobs.js'

const INTAKE = 'cv_intake'

const STATUS_CHIPS = {
  applied: { tone: 'neutral', label: 'Applied' },
  screening_failed: { tone: 'danger', label: 'Could not be read' },
  excluded: { tone: 'warning', label: 'Excluded' },
  shortlisted: SHORTLISTED_CHIP,
  interview_scheduled: INTERVIEW_CHIP,
}
const SCREENED_CHIP = { tone: 'success', label: 'Screened' }

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

// How the last fetch ended, in one line.
function LastFetch({ task }) {
  if (!task) return null
  const when = formatDateTime(task.finished_at ?? task.created_at)
  if (task.status !== 'succeeded') {
    return (
      <p className="text-sm">
        Last fetch {when} · <strong className="font-semibold text-danger">{task.error_message}</strong>
      </p>
    )
  }
  const { collected, duplicates, failed } = task.result
  return (
    <p className="text-sm">
      Last fetch {when} ·{' '}
      <strong className="font-semibold text-success">{collected} collected</strong>
      {duplicates > 0 && ` · ${plural(duplicates, 'duplicate')} skipped`}
      {failed > 0 && (
        <>
          {' · '}
          <strong className="font-semibold text-danger">{failed} not collected</strong>
        </>
      )}
    </p>
  )
}

// Applications from the last fetch that could not be brought in, and why.
function NotCollected({ items }) {
  return (
    <section
      aria-label="Applications that could not be collected"
      className="overflow-hidden rounded-card border border-danger/20 bg-danger-soft/40"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <h2 className="text-lg font-bold">
          Could not be collected{' '}
          <span className="font-semibold text-danger">{items.length}</span>
        </h2>
        <span className="text-[13px]">
          From the last fetch. They are tried again on the next fetch.
        </span>
      </div>
      <ul>
        {items.map((item) => (
          <li
            key={`${item.email}-${item.name}`}
            className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-danger/15 px-5 py-3"
          >
            <CircleAlert className="size-4.5 shrink-0 text-danger" aria-hidden="true" />
            <span className="min-w-0 basis-72">
              <span className="text-[15px] font-semibold text-navy">{item.name}</span>
              <span className="ml-2 text-[13px]">{item.email}</span>
            </span>
            <span className="flex-1 basis-64 text-[15px] text-danger">{item.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Applicants({ candidates, isLocked, onChanged }) {
  return (
    <ListCard title="Applicants" count={candidates.length} note="Newest first">
      <table className="w-full">
        <thead className="bg-mist">
          <tr>
            <th scope="col" className={HEADING}>Applicant</th>
            <th scope="col" className={`${HEADING} hidden md:table-cell`}>Applied</th>
            <th scope="col" className={HEADING}>Status</th>
            <th scope="col" className={HEADING}>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => {
            const chip = STATUS_CHIPS[candidate.status] ?? SCREENED_CHIP
            return (
              <tr key={candidate.id} className="border-t border-line/60">
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-4">
                    <Initials name={candidate.full_name} />
                    <div className="min-w-0">
                      <p className="text-[15px] font-semibold text-navy">{candidate.full_name}</p>
                      <p className="mt-0.5 text-[13px]">{candidate.email}</p>
                    </div>
                  </div>
                </td>
                <td className="hidden px-5 py-3.5 text-sm md:table-cell">
                  {formatDateTime(candidate.created_at)}
                </td>
                <td className="px-5 py-3.5">
                  <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex items-center justify-end gap-2">
                    <ViewCvLink candidateId={candidate.id} />
                    <DeleteCandidateButton
                      candidate={candidate}
                      isLocked={isLocked}
                      onDeleted={onChanged}
                    />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </ListCard>
  )
}

// The Applications tab of a job: collect the CVs and see who applied.
export default function ApplicationsTab() {
  const { job, threadId, waiting, run, listVersion, onChanged } = useOutletContext()
  const { candidates, error } = useCandidates(job.id, listVersion)
  const isPublished = job.status === 'published'
  const fetching = run.running?.kind === INTAKE ? run.running : null
  const failedItems = run.last_intake?.result?.failed_items ?? []

  if (!isPublished) {
    return (
      <section className="flex flex-col items-center gap-3 rounded-card border border-line bg-white p-10 text-center shadow-card">
        <h2 className="text-xl font-bold">This job is not published yet</h2>
        <p>Applications can be collected once the job is published.</p>
        {threadId && (
          <Button variant="outline" to={`/app/assistant/${threadId}`}>
            Publish it with the AI Agent
          </Button>
        )}
      </section>
    )
  }

  return (
    <>
      <RunPanel
        title="Collect applications"
        description="Brings in the CVs submitted through the application form since the last fetch."
        buttonLabel="Fetch CVs"
        busyLabel="Fetching…"
        icon={Download}
        task={fetching}
        isDisabled={!run.isLoaded || Boolean(run.running)}
        isQuiet={waiting === 0 && candidates?.length > 0}
        error={run.error}
        onStart={() => run.start('intake')}
      >
        {waiting > 0 ? (
          <p className="flex items-center gap-2.5 rounded-xl bg-warning-soft px-3.5 py-2.5 text-[15px] font-semibold text-warning">
            <span className="size-2 shrink-0 rounded-full bg-warning" aria-hidden="true" />
            {plural(waiting, 'new application')} waiting in the form
          </p>
        ) : (
          run.last_intake && <p className="text-[15px]">No new applications since the last fetch.</p>
        )}
        {run.running && !fetching && (
          <p className="text-sm">Screening is running. Fetch CVs is available when it ends.</p>
        )}
        <LastFetch task={run.last_intake} />
      </RunPanel>

      {failedItems.length > 0 && <NotCollected items={failedItems} />}

      {error && (
        <p role="alert" className="font-semibold text-danger">
          {error}
        </p>
      )}
      {!candidates && !error && <Skeleton className="h-48 w-full rounded-card" />}
      {candidates?.length === 0 && (
        <section className="rounded-card border border-line bg-white p-10 text-center shadow-card">
          <h2 className="text-lg font-bold">No applications collected yet</h2>
          <p className="mt-1.5">Use Fetch CVs to bring in the applications from the form.</p>
        </section>
      )}
      {candidates?.length > 0 && (
        <>
          <Applicants
            candidates={candidates}
            isLocked={Boolean(run.running)}
            onChanged={onChanged}
          />
          <div className="flex justify-end">
            <Button variant="outline" to="../screening" relative="path">
              Next: Screening
            </Button>
          </div>
        </>
      )}
    </>
  )
}
