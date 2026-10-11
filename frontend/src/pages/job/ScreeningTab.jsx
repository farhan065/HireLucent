import { ScanSearch, Search } from 'lucide-react'
import { useState } from 'react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import FinalRanking from '../../components/jobs/FinalRanking.jsx'
import MatchRanking from '../../components/jobs/MatchRanking.jsx'
import ResultFilter from '../../components/jobs/ResultFilter.jsx'
import RunPanel from '../../components/jobs/RunPanel.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { useCandidates } from '../../hooks/useCandidates.js'
import { formatDateTime } from '../../lib/jobs.js'
import { countGroups, filterCandidates } from '../../lib/results.js'

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
          <strong className="font-semibold text-success">{passed} scored</strong>
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
  { key: 'final', label: 'Final ranking', note: 'after scoring' },
  { key: 'match', label: 'Requirement match' },
]

// The two rankings of a job. The final ranking opens once someone is scored.
function SubTabs({ view, hasScores, onChange }) {
  return (
    <div role="tablist" aria-label="Rankings" className="flex flex-wrap gap-2">
      {SUB_TABS.map((tab) => {
        const isActive = tab.key === view
        const isDisabled = tab.key === 'final' && !hasScores
        return (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            disabled={isDisabled}
            onClick={() => onChange(tab.key)}
            className={`flex min-h-10 items-center gap-2 rounded-full border-[1.5px] px-4 text-sm font-semibold ${
              isActive
                ? 'border-brand bg-brand text-white'
                : isDisabled
                  ? 'cursor-not-allowed border-line bg-white text-body/60'
                  : 'border-line bg-white text-navy hover:border-brand/40 hover:bg-tint'
            }`}
          >
            {tab.label}
            {isDisabled && <span className="text-xs font-medium">{tab.note}</span>}
          </button>
        )
      })}
    </div>
  )
}

function SearchBox({ value, onChange }) {
  return (
    <label className="flex min-h-11 w-full items-center gap-2.5 rounded-full border-[1.5px] border-line bg-white px-3.5 focus-within:border-brand sm:w-72">
      <Search className="size-4.5 shrink-0 text-body" aria-hidden="true" />
      <span className="sr-only">Search candidates by name</span>
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search by name"
        className="min-w-0 flex-1 bg-transparent text-[15px] text-navy placeholder:text-body/70 focus:outline-none"
      />
    </label>
  )
}

// The rankings with their sub-tabs, the Show filter and the search. Kept in
// its own component so every choice starts afresh for another job.
function Results({ job, candidates, isLocked, onChanged }) {
  // The final ranking is shown first once anyone is scored, unless the
  // interviewer picks the other view. evidenceFor opens one candidate there.
  const [chosenView, setChosenView] = useState(null)
  const [evidenceFor, setEvidenceFor] = useState(null)
  const [group, setGroup] = useState('all')
  const [query, setQuery] = useState('')
  const hasScores = candidates.some((item) => item.scores)
  const view = hasScores ? (chosenView ?? 'final') : 'match'
  const counts = countGroups(candidates)
  const visible = filterCandidates(candidates, group, query)
  const isFiltered = group !== 'all' || query.trim() !== ''

  function changeView(next) {
    setEvidenceFor(null)
    setChosenView(next)
  }

  function showEvidence(candidateId) {
    setEvidenceFor(candidateId)
    setChosenView('match')
  }

  function showAll() {
    setGroup('all')
    setQuery('')
  }

  const shared = { candidates, visible, isFiltered, onShowAll: showAll, isLocked, onChanged }
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SubTabs view={view} hasScores={hasScores} onChange={changeView} />
        <div className="flex w-full flex-wrap items-center gap-3 sm:w-auto">
          <ResultFilter value={group} counts={counts} onChange={setGroup} />
          <SearchBox value={query} onChange={setQuery} />
        </div>
      </div>
      {view === 'final' ? (
        <FinalRanking jobId={job.id} onShowEvidence={showEvidence} {...shared} />
      ) : (
        <MatchRanking key={evidenceFor ?? 'all'} initialOpenId={evidenceFor} {...shared} />
      )}
    </>
  )
}

// The Screening tab of a job: run the screening and see the results.
export default function ScreeningTab() {
  const { job, run, listVersion, onChanged } = useOutletContext()
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
              Each CV is read, checked against the must-haves, matched with every
              requirement by meaning, and scored. CVs already screened are skipped.
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
        <Results
          key={job.id}
          job={job}
          candidates={screened}
          isLocked={Boolean(run.running)}
          onChanged={onChanged}
        />
      )}
    </>
  )
}
