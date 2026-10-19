import { ArrowLeft, CircleAlert, FileText, RotateCcw } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import Button from '../components/Button.jsx'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusChip from '../components/StatusChip.jsx'
import CoverageTable from '../components/assessment/CoverageTable.jsx'
import {
  EvaluatingCard,
  FailedCard,
  NotEvaluatedCard,
} from '../components/assessment/EvaluationStatus.jsx'
import QuestionBankCard from '../components/assessment/QuestionBankCard.jsx'
import QuestionCard from '../components/assessment/QuestionCard.jsx'
import ReportView from '../components/assessment/ReportView.jsx'
import { useEvaluation } from '../hooks/useEvaluation.js'
import {
  KIND_FILTERS,
  KINDS,
  SOURCES,
  coverageSummary,
  evaluationOf,
  kindCounts,
  needsAttention,
  SUITABILITY,
  hasReport,
  oneDecimal,
  qaSummary,
  readAssessment,
  reportFileName,
  requirementNames,
  turnsById,
} from '../lib/assessment.js'
import { readInterview, readTranscript } from '../lib/room.js'
import { whenLabel } from '../lib/transcript.js'

const TABS = ['report', 'qa', 'coverage']
// The Report tab's badge for each assessment status.
const REPORT_BADGES = {
  draft: { label: 'Draft', className: 'bg-amber-soft text-amber' },
  approved: { label: 'Approved', className: 'bg-success-soft text-success' },
}
// The header chip for each assessment status.
const STATUS_CHIPS = {
  analysed: { tone: 'info', label: 'Answers evaluated' },
  draft: { tone: 'amber', label: 'Draft report' },
  approved: { tone: 'success', label: 'Report approved' },
}

function LoadingAssessment() {
  return (
    <div role="status" aria-label="Loading the assessment" className="flex flex-col gap-5">
      <Skeleton className="h-4 w-72" />
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-5 w-[28rem]" />
      </div>
      <div className="flex gap-3">
        {['a', 'b', 'c'].map((key) => (
          <Skeleton key={key} className="h-20 w-44 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-12 w-[30rem] rounded-xl" />
      {['a', 'b', 'c', 'd'].map((key) => (
        <Skeleton key={key} className="h-16 w-full rounded-[18px]" />
      ))}
    </div>
  )
}

function ScoreTile({ label, value, note, chip }) {
  return (
    <div className="flex min-w-36 flex-col gap-0.5 rounded-2xl border border-line bg-white px-4 py-3">
      <span className="text-xs font-semibold uppercase tracking-wider text-[#6B7890]">{label}</span>
      <span className="flex items-center gap-2">
        <span
          className={`font-display text-[26px] font-extrabold tabular-nums ${
            value == null ? 'text-[#9AA6BA]' : 'text-navy'
          }`}
        >
          {value ?? '–'}
        </span>
        {chip && (
          <span className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-bold ${chip.className}`}>
            {chip.label}
          </span>
        )}
      </span>
      <span className="text-[12.5px]">{note}</span>
    </div>
  )
}

// The Report tab of an interview whose answers are evaluated but whose
// report is not written yet.
function NoReport({ isBusy, onWriteReport }) {
  return (
    <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-dashed border-[#A9C8FF] bg-white p-5.5">
      <h2 className="text-lg font-extrabold text-navy">The report has not been written yet</h2>
      <p className="text-sm leading-relaxed">
        The answers are evaluated. Write the report to get the scores, the summary, and the
        strengths and weaknesses with their sources.
      </p>
      <div>
        <Button
          disabled={isBusy}
          title={isBusy ? 'An evaluation is running. Wait for it to finish.' : undefined}
          onClick={onWriteReport}
        >
          Write report
        </Button>
      </div>
    </section>
  )
}

function SummaryBox({ label, value, note, children }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-line bg-white px-4 py-3.5">
      <span className="text-[13px] font-semibold text-[#6B7890]">{label}</span>
      {value != null && (
        <span className="font-display text-2xl font-extrabold tabular-nums text-navy">{value}</span>
      )}
      {children}
      {note && <span className="text-[12.5px]">{note}</span>}
    </div>
  )
}

function FilterChip({ isActive, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`inline-flex min-h-9 items-center rounded-full px-3.5 text-[13.5px] font-semibold ${
        isActive ? 'bg-navy text-white' : 'border border-line bg-white text-navy hover:bg-tint'
      }`}
    >
      {children}
    </button>
  )
}

function ScoringKey() {
  return (
    <section className="flex flex-col gap-3 rounded-[20px] border border-line bg-white p-4.5">
      <h2 className="text-[15px] font-extrabold text-navy">How answers are scored</h2>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[13.5px] leading-snug">
        <li>Score = average of the criteria that apply. Behavioural answers have no accuracy.</li>
        <li>Not answered or silent = 0.</li>
        <li>Small talk is kept but not scored.</li>
      </ul>
      <dl className="flex flex-col gap-2 text-[13px]">
        {[
          ['reference', 'checked against your reference documents'],
          ['ai_judgement', 'no reference found, judged by the AI'],
          ['not_checked', 'company fact with no reference, accuracy left out'],
        ].map(([type, text]) => (
          <div key={type} className="flex items-start gap-2">
            <dt
              className={`shrink-0 rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${SOURCES[type].className}`}
            >
              {SOURCES[type].label}
            </dt>
            <dd className="pt-0.5 leading-snug">{text}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function QaTab({ info, assessment, turns, openIds, setOpenIds, kind, setKind, onAdded }) {
  const pairs = assessment.qa_evaluations
  const summary = qaSummary(pairs)
  const counts = kindCounts(pairs)
  const names = useMemo(() => requirementNames(assessment.coverage_map), [assessment])
  const shown = kind === 'all' ? pairs : pairs.filter((pair) => pair.kind === kind)
  const allOpen = shown.length > 0 && shown.every((pair) => openIds.has(pair.id))

  function toggle(id) {
    setOpenIds((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAll() {
    setOpenIds(allOpen ? new Set() : new Set(shown.map((pair) => pair.id)))
  }

  return (
    <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
          <SummaryBox
            label="Questions"
            value={summary.total}
            note={`${summary.evaluated} evaluated · ${summary.smallTalk} small talk`}
          />
          <SummaryBox
            label="Average answer score"
            value={summary.average ?? '–'}
            note={`across the ${summary.evaluated} evaluated`}
          />
          <SummaryBox label="Accuracy checked by">
            <span className="flex flex-col gap-0.5 text-[13.5px] font-semibold text-navy">
              <span>{summary.sources.reference} reference</span>
              <span>{summary.sources.ai_judgement} AI interviewer</span>
              <span>{summary.sources.not_checked} not checked</span>
            </span>
          </SummaryBox>
          <SummaryBox
            label="Not answered"
            value={summary.notAnswered}
            note="scored 0, listed to verify"
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <div role="group" aria-label="Show questions" className="flex flex-wrap gap-2">
            <FilterChip isActive={kind === 'all'} onClick={() => setKind('all')}>
              All {pairs.length}
            </FilterChip>
            {KIND_FILTERS.map((item) =>
              counts[item] > 0 ? (
                <FilterChip key={item} isActive={kind === item} onClick={() => setKind(item)}>
                  {KINDS[item].label} {counts[item]}
                </FilterChip>
              ) : null,
            )}
          </div>
          {shown.length > 0 && (
            <button
              type="button"
              onClick={toggleAll}
              className="min-h-9 px-2 text-sm font-semibold text-brand hover:text-brand-dark"
            >
              {allOpen ? 'Collapse all' : 'Expand all'}
            </button>
          )}
        </div>

        {pairs.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-line bg-white px-5 py-6 text-sm">
            No questions were found in this interview.
          </p>
        ) : (
          <div className="flex flex-col gap-2.5">
            {shown.map((pair) => (
              <div key={pair.id} id={`question-${pair.id}`} className="scroll-mt-6">
                <QuestionCard
                  sessionId={assessment.session_id}
                  pair={pair}
                  turns={turns}
                  requirementNames={names}
                  isOpen={openIds.has(pair.id)}
                  onToggle={() => toggle(pair.id)}
                />
              </div>
            ))}
          </div>
        )}
      </div>

      <aside className="flex flex-col gap-4">
        <QuestionBankCard
          sessionId={assessment.session_id}
          jobTitle={info.job_title}
          jobCode={info.job_code}
          suggestions={assessment.question_suggestions}
          onAdded={onAdded}
        />
        <ScoringKey />
      </aside>
    </div>
  )
}

function CoverageTab({ coverage, onPickQuestion }) {
  const [filter, setFilter] = useState('all')
  const summary = coverageSummary(coverage)
  const must = coverage.filter((entry) => entry.priority === 'must_have')
  const attention = coverage.filter(needsAttention)
  const shown = filter === 'must' ? must : filter === 'attention' ? attention : coverage

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SummaryBox
          label="Covered"
          value={summary.covered}
          note={`average answer 60 or more${summary.mixed ? ` · ${summary.mixed} mixed` : ''}`}
        />
        <SummaryBox label="Weak" value={summary.weak} note="asked, but average below 60" />
        <SummaryBox
          label="Not explored"
          value={summary.notExplored}
          note={`no question touched them${
            summary.mustHaveNotExplored ? ` · ${summary.mustHaveNotExplored} must-have` : ''
          }`}
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Show requirements" className="flex flex-wrap gap-2">
          <FilterChip isActive={filter === 'all'} onClick={() => setFilter('all')}>
            All {coverage.length}
          </FilterChip>
          <FilterChip isActive={filter === 'must'} onClick={() => setFilter('must')}>
            Must-have {must.length}
          </FilterChip>
          <FilterChip isActive={filter === 'attention'} onClick={() => setFilter('attention')}>
            Needs attention {attention.length}
          </FilterChip>
        </div>
        <span className="text-[13px]">
          Covered = average answer score of 60 or more. Mixed = covered, but one answer below 40.
        </span>
      </div>

      <section className="overflow-hidden rounded-[20px] border border-line bg-white shadow-card">
        {coverage.length === 0 ? (
          <p className="px-5.5 py-6 text-sm">This job has no requirements to map.</p>
        ) : shown.length === 0 ? (
          <p className="px-5.5 py-6 text-sm">No requirement needs attention.</p>
        ) : (
          <CoverageTable coverage={shown} onPickQuestion={onPickQuestion} />
        )}
      </section>

      <p className="text-[13px] leading-relaxed">
        A requirement that was not explored does not lower any score. It is listed under Evidence
        gaps in the report, with what the CV says about it.
      </p>
    </div>
  )
}

// One interview's assessment: the Q&A analysis (each answer's scores,
// evidence and where accuracy came from, with question bank suggestions)
// and the requirement coverage. Evaluating, failed and not-yet-evaluated
// interviews show their state instead. The report tab comes with the
// review step.
export default function AssessmentPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [searchParams, setSearchParams] = useSearchParams()
  // The tab asked for in the address; without one, the page picks (see currentTab).
  const tab = TABS.includes(searchParams.get('tab')) ? searchParams.get('tab') : null
  const [info, setInfo] = useState(null)
  const [assessment, setAssessment] = useState(undefined)
  const [turns, setTurns] = useState(new Map())
  const [error, setError] = useState('')
  const [isConfirming, setIsConfirming] = useState(false)
  const [kind, setKind] = useState('all')
  const [openIds, setOpenIds] = useState(() => new Set())
  const scrollTo = useRef(null)

  const loadAssessment = useCallback(
    () =>
      Promise.all([readAssessment(sessionId), readTranscript(sessionId).catch(() => null)])
        .then(([loaded, transcript]) => {
          setAssessment(loaded)
          if (transcript) setTurns(turnsById(transcript.turns))
          // The first evaluated question starts open.
          const first = loaded?.qa_evaluations.find((pair) => pair.evaluation)
          setOpenIds(first ? new Set([first.id]) : new Set())
        })
        .catch((loadError) => setError(loadError.message)),
    [sessionId],
  )

  useEffect(() => {
    let isCurrent = true
    readInterview(sessionId)
      .then((loaded) => isCurrent && setInfo(loaded))
      .catch((loadError) => isCurrent && setError(loadError.message))
    loadAssessment()
    return () => {
      isCurrent = false
    }
  }, [sessionId, loadAssessment])

  const evaluation = useEvaluation(info?.job_id ?? null, loadAssessment)
  const state = evaluationOf(evaluation.activity, id)

  // A question picked on the coverage tab is scrolled to once it is shown.
  useEffect(() => {
    if (tab !== 'qa' || !scrollTo.current) return
    document
      .getElementById(`question-${scrollTo.current}`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    scrollTo.current = null
  }, [tab, openIds])

  function showTab(next) {
    setSearchParams({ tab: next }, { replace: true })
  }

  function pickQuestion(pairId) {
    setKind('all')
    setOpenIds((current) => new Set(current).add(pairId))
    scrollTo.current = pairId
    showTab('qa')
  }

  async function evaluate() {
    setIsConfirming(false)
    await evaluation.start(id)
  }

  if (error) {
    return (
      <section className="mx-auto flex max-w-md flex-col items-start gap-4 rounded-card bg-white p-8 shadow-card">
        <CircleAlert className="size-8 text-danger" aria-hidden="true" />
        <h1 className="text-xl font-extrabold tracking-tight">
          The assessment could not be opened
        </h1>
        <p>{error}</p>
        <Button variant="outline" to="/app/jobs">
          Back to Jobs
        </Button>
      </section>
    )
  }
  if (!info || assessment === undefined || !evaluation.isLoaded) {
    return (
      <div className="mx-auto max-w-6xl">
        <LoadingAssessment />
      </div>
    )
  }

  const { interview } = info
  const backTo = `/app/jobs/${info.job_id}/interviews`
  const transcriptTo = `/app/interviews/${id}/transcript`
  const isCompleted = interview.status === 'completed'
  const isRunning = state.state === 'running'
  const isQueued = state.state === 'queued'
  const coverage = assessment?.coverage_map ?? []
  const notExplored = coverage.filter((entry) => entry.status === 'not_explored').length
  const isReport = hasReport(assessment)
  // The page opens on the report once there is one, else on the answers.
  const currentTab = tab ?? (isReport ? 'report' : 'qa')
  const answersEvaluated = assessment ? qaSummary(assessment.qa_evaluations).evaluated : 0

  let body
  if (isRunning) {
    body = <EvaluatingCard message={state.message} percent={state.percent} />
  } else if (isQueued) {
    body = (
      <section role="status" className="max-w-xl rounded-[20px] border border-line bg-white p-5.5">
        <h2 className="text-[17px] font-extrabold text-navy">Waiting to be evaluated</h2>
        <p className="mt-1 text-[13.5px]">
          Evaluate all is working through this job&apos;s interviews. This one is next in line.
        </p>
      </section>
    )
  } else if (state.state === 'failed' && !assessment) {
    body = (
      <FailedCard
        reason={state.reason}
        transcriptTo={transcriptTo}
        isBusy={evaluation.isRunning}
        onRetry={evaluate}
      />
    )
  } else if (!assessment) {
    body = (
      <NotEvaluatedCard
        isCompleted={isCompleted}
        isBusy={evaluation.isRunning}
        onEvaluate={evaluate}
      />
    )
  }

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm">
        <Link to="/app/jobs" className="font-semibold text-brand hover:text-brand-dark">
          Jobs
        </Link>
        <span aria-hidden="true">›</span>
        <Link
          to={`/app/jobs/${info.job_id}`}
          className="font-semibold text-brand hover:text-brand-dark"
        >
          {info.job_title}
        </Link>
        <span aria-hidden="true">›</span>
        <Link to={backTo} className="font-semibold text-brand hover:text-brand-dark">
          Interviews
        </Link>
        <span aria-hidden="true">›</span>
        <span className="font-semibold text-navy">Assessment</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-start gap-3.5">
          <Link
            to={backTo}
            aria-label="Back to Interviews"
            className="inline-flex size-11 shrink-0 items-center justify-center rounded-xl border border-line bg-white text-body hover:bg-tint hover:text-brand"
          >
            <ArrowLeft className="size-5" aria-hidden="true" />
          </Link>
          <div>
            <h1 className="text-[28px] font-extrabold tracking-tight">
              {interview.candidate_name} · Assessment
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-2.5 text-[14.5px]">
              <span>
                {info.job_title} · {info.job_code}
              </span>
              <span aria-hidden="true">·</span>
              <span>Interview {whenLabel(interview)}</span>
              {assessment && !isRunning && (
                <StatusChip tone={STATUS_CHIPS[assessment.status].tone}>
                  {STATUS_CHIPS[assessment.status].label}
                </StatusChip>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Button variant="outline" to={transcriptTo}>
            <FileText className="size-4.5" aria-hidden="true" />
            View transcript
          </Button>
          {assessment && !isRunning && !isQueued && (
            <Button
              variant="soft"
              disabled={evaluation.isRunning}
              title={
                evaluation.isRunning
                  ? 'Another evaluation is running. Wait for it to finish.'
                  : undefined
              }
              onClick={() => setIsConfirming(true)}
            >
              <RotateCcw className="size-4.5" aria-hidden="true" />
              Evaluate again
            </Button>
          )}
        </div>
      </header>

      {evaluation.error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {evaluation.error}
        </p>
      )}

      {body ?? (
        <>
          {state.state === 'failed' && (
            <p
              role="alert"
              className="flex items-start gap-2.5 rounded-2xl border border-[#F3C4C0] bg-danger-soft px-4 py-3 text-[13.5px] leading-relaxed text-danger"
            >
              <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
              <span>
                <strong>The last evaluation stopped.</strong> {state.reason}
              </span>
            </p>
          )}

          <div className="flex flex-wrap gap-3">
            <ScoreTile
              label="CV score"
              value={oneDecimal(assessment.cv_score ?? assessment.screening_score)}
              note="from screening"
            />
            <ScoreTile
              label="Interview"
              value={oneDecimal(assessment.interview_score)}
              note={
                !isReport
                  ? 'after the report'
                  : assessment.interview_score == null
                    ? 'no job questions'
                    : `${answersEvaluated} ${answersEvaluated === 1 ? 'answer' : 'answers'}`
              }
            />
            <ScoreTile
              label="Overall"
              value={oneDecimal(assessment.overall_score)}
              chip={SUITABILITY[assessment.suitability]}
              note="40% CV · 60% interview"
            />
          </div>

          <div
            role="tablist"
            aria-label="Assessment"
            className="flex flex-wrap gap-1 border-b border-line"
          >
            {[
              [
                'report',
                'Report',
                REPORT_BADGES[assessment.status]?.label ?? null,
                REPORT_BADGES[assessment.status]?.className,
              ],
              ['qa', 'Q&A analysis', assessment.qa_evaluations.length, 'bg-tint text-brand-dark'],
              [
                'coverage',
                'Requirement coverage',
                notExplored ? `${notExplored} not explored` : null,
                'bg-warning-soft text-warning',
              ],
            ].map(([key, label, badge, badgeClass]) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={currentTab === key}
                onClick={() => showTab(key)}
                className={`-mb-px inline-flex min-h-11 items-center gap-2 border-b-2 px-4 text-[15px] font-semibold ${
                  currentTab === key
                    ? 'border-brand text-navy'
                    : 'border-transparent text-body hover:text-navy'
                }`}
              >
                {label}
                {badge != null && (
                  <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${badgeClass}`}>
                    {badge}
                  </span>
                )}
              </button>
            ))}
          </div>

          {currentTab === 'report' ? (
            isReport ? (
              <ReportView
                assessment={assessment}
                candidateName={interview.candidate_name}
                fileName={reportFileName(info)}
                onChanged={(updated) => setAssessment(updated)}
              />
            ) : (
              <NoReport
                isBusy={evaluation.isRunning}
                onWriteReport={() => evaluation.start(id, { reportOnly: true })}
              />
            )
          ) : currentTab === 'qa' ? (
            <QaTab
              info={info}
              assessment={assessment}
              turns={turns}
              openIds={openIds}
              setOpenIds={setOpenIds}
              kind={kind}
              setKind={setKind}
              onAdded={(suggestions) =>
                setAssessment((current) => ({
                  ...current,
                  question_suggestions: suggestions,
                }))
              }
            />
          ) : (
            <CoverageTab coverage={coverage} onPickQuestion={pickQuestion} />
          )}
        </>
      )}

      {isConfirming && (
        <ConfirmDialog
          title="Evaluate this interview again?"
          confirmLabel="Evaluate again"
          confirmVariant="primary"
          busyLabel="Starting…"
          onConfirm={evaluate}
          onCancel={() => setIsConfirming(false)}
        >
          <p>
            The answers are scored again from the transcript and the current reference documents.
            The new results replace the ones shown here.
          </p>
          <p>Questions already added to the question bank stay there.</p>
        </ConfirmDialog>
      )}
    </div>
  )
}
