import { ScanSearch } from 'lucide-react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import { HEADING, Initials, ListCard, ViewCvLink } from '../../components/jobs/candidates.jsx'
import RunPanel from '../../components/jobs/RunPanel.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusChip from '../../components/StatusChip.jsx'
import { useCandidates } from '../../hooks/useCandidates.js'
import { formatDateTime } from '../../lib/jobs.js'

const SCREENING = 'cv_screening'
const READ_AS = { text: 'Text', ocr: 'Scanned (OCR)' }

// The requirement match of one candidate as three small counts.
function MatchCounts({ counts }) {
  if (!counts) return <span className="text-sm">–</span>
  const parts = [
    ['met', 'met', 'bg-success-soft text-success'],
    ['partially_met', 'partly', 'bg-warning-soft text-warning'],
    ['unmet', 'not met', 'bg-danger-soft text-danger'],
  ]
  return (
    <div className="flex flex-wrap gap-1.5">
      {parts.map(([key, label, style]) => (
        <span key={key} className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${style}`}>
          {counts[key]} {label}
        </span>
      ))}
    </div>
  )
}

// How the last screening ended, in one line.
function LastScreening({ task }) {
  if (!task) return null
  const when = formatDateTime(task.finished_at ?? task.created_at)
  if (task.status !== 'succeeded') {
    return (
      <p className="text-sm">
        Last screening {when} ·{' '}
        <strong className="font-semibold text-danger">{task.error_message}</strong>
      </p>
    )
  }
  const { total, read, read_by_ocr: byOcr, passed = 0, excluded = 0, failed } = task.result
  return (
    <p className="text-sm">
      Last screening {when} · {total} {total === 1 ? 'CV' : 'CVs'}
      {read + byOcr > 0 && ` · ${read + byOcr} read${byOcr > 0 ? ` (${byOcr} by OCR)` : ''}`}
      {passed > 0 && (
        <>
          {' · '}
          <strong className="font-semibold text-success">{passed} matched</strong>
        </>
      )}
      {excluded > 0 && (
        <>
          {' · '}
          <strong className="font-semibold text-warning">{excluded} excluded</strong>
        </>
      )}
      {failed > 0 && (
        <>
          {' · '}
          <strong className="font-semibold text-danger">{failed} could not be read</strong>
        </>
      )}
    </p>
  )
}

function ScreenedList({ candidates }) {
  return (
    <ListCard
      title="Screened so far"
      count={candidates.length}
      note="Scores and ranking are added to this list in a later step."
    >
      <table className="w-full">
        <thead className="bg-mist">
          <tr>
            <th scope="col" className={HEADING}>Candidate</th>
            <th scope="col" className={`${HEADING} hidden lg:table-cell`}>CV read as</th>
            <th scope="col" className={HEADING}>Requirements</th>
            <th scope="col" className={HEADING}>Status</th>
            <th scope="col" className={HEADING}>
              <span className="sr-only">CV</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((candidate) => {
            const hasFailed = candidate.status === 'screening_failed'
            const isExcluded = candidate.status === 'excluded'
            const tint = hasFailed ? 'bg-danger-soft/40' : isExcluded ? 'bg-warning-soft/40' : ''
            return (
              <tr key={candidate.id} className={`border-t border-line/60 ${tint}`}>
                <td className="px-5 py-3.5">
                  <div className="flex items-center gap-4">
                    <Initials name={candidate.full_name} />
                    <div className="min-w-0">
                      <p className="text-[15px] font-semibold text-navy">{candidate.full_name}</p>
                      {hasFailed && (
                        <p className="mt-0.5 text-[13px] text-danger">
                          {candidate.screening_error}
                        </p>
                      )}
                      {isExcluded &&
                        candidate.excluded_reason?.split('\n').map((reason) => (
                          <p key={reason} className="mt-0.5 text-[13px] text-warning">
                            {reason}
                          </p>
                        ))}
                    </div>
                  </div>
                </td>
                <td className="hidden px-5 py-3.5 text-sm text-navy lg:table-cell">
                  {hasFailed ? '–' : READ_AS[candidate.cv_text_source]}
                </td>
                <td className="px-5 py-3.5">
                  <MatchCounts counts={candidate.match_counts} />
                </td>
                <td className="px-5 py-3.5">
                  {hasFailed ? (
                    <StatusChip tone="danger">Could not be read</StatusChip>
                  ) : isExcluded ? (
                    <StatusChip tone="warning">Excluded</StatusChip>
                  ) : candidate.match_counts ? (
                    <StatusChip tone="success">Matched</StatusChip>
                  ) : candidate.must_haves_met ? (
                    <StatusChip tone="info">Met the must-haves</StatusChip>
                  ) : (
                    <StatusChip tone="info">CV read</StatusChip>
                  )}
                </td>
                <td className="px-5 py-3.5">
                  <div className="flex justify-end">
                    <ViewCvLink candidateId={candidate.id} />
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

// The Screening tab of a job: run the screening and see what was read.
export default function ScreeningTab() {
  const { job, run, listVersion } = useOutletContext()
  const { candidates, error } = useCandidates(job.id, listVersion)
  const screening = run.running?.kind === SCREENING ? run.running : null
  const ready = run.ready_to_screen ?? 0
  const screened = (candidates ?? []).filter(
    (item) =>
      item.cv_text_source || item.status === 'screening_failed' || item.status === 'excluded',
  )
  const hasNone = candidates?.length === 0

  return (
    <>
      <RunPanel
        title="Screen CVs"
        description={
          hasNone ? (
            'Nothing to screen yet. Collect the applications first.'
          ) : ready > 0 ? (
            <>
              <strong className="font-semibold text-navy">
                {ready} {ready === 1 ? 'CV is' : 'CVs are'} ready to screen.
              </strong>{' '}
              Each CV is read, checked against the must-haves, and matched with every
              requirement by meaning. CVs already screened are skipped.
            </>
          ) : (
            'All collected CVs are screened. Fetch new applications to screen more.'
          )
        }
        buttonLabel="Screen CVs"
        busyLabel="Screening…"
        icon={ScanSearch}
        task={screening}
        isDisabled={!run.isLoaded || Boolean(run.running) || ready === 0}
        error={run.error}
        onStart={() => run.start('screen')}
      >
        {run.running && !screening && (
          <p className="text-sm">A fetch is running. Screen CVs is available when it ends.</p>
        )}
        <LastScreening task={run.last_screening} />
        {hasNone && (
          <div>
            <Button variant="outline" to="../applications" relative="path">
              Go to Applications
            </Button>
          </div>
        )}
      </RunPanel>

      {error && (
        <p role="alert" className="font-semibold text-danger">
          {error}
        </p>
      )}
      {!candidates && !error && <Skeleton className="h-48 w-full rounded-card" />}
      {screened.length > 0 && <ScreenedList candidates={screened} />}
    </>
  )
}
