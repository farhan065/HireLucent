import { ScanSearch } from 'lucide-react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import MatchRanking from '../../components/jobs/MatchRanking.jsx'
import RunPanel from '../../components/jobs/RunPanel.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { useCandidates } from '../../hooks/useCandidates.js'
import { formatDateTime } from '../../lib/jobs.js'

const SCREENING = 'cv_screening'

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

const SUB_TABS = [
  { key: 'match', label: 'Requirement match' },
  { key: 'final', label: 'Final ranking', note: 'after scoring' },
]

// The two rankings of a job. The final ranking opens once scoring exists.
function SubTabs() {
  return (
    <div role="tablist" aria-label="Rankings" className="flex flex-wrap gap-2">
      {SUB_TABS.map((tab) => {
        const isActive = tab.key === 'match'
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            disabled={!isActive}
            className={`flex min-h-10 items-center gap-2 rounded-full border-[1.5px] px-4 text-sm font-semibold ${
              isActive
                ? 'border-brand bg-brand text-white'
                : 'cursor-not-allowed border-line bg-white text-body/60'
            }`}
          >
            {tab.label}
            {tab.note && <span className="text-xs font-medium">{tab.note}</span>}
          </button>
        )
      })}
    </div>
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
      {screened.length > 0 && (
        <>
          <SubTabs />
          <MatchRanking candidates={screened} />
        </>
      )}
    </>
  )
}
