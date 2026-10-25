import { CircleAlert, CircleCheck, Mail, Sparkles, TriangleAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate, useOutletContext, useSearchParams } from 'react-router'
import Button from '../../components/Button.jsx'
import ConfirmDialog from '../../components/ConfirmDialog.jsx'
import ConsistencyView from '../../components/assessment/ConsistencyView.jsx'
import RankedList from '../../components/assessment/RankedList.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import DecisionRuleBar from '../../components/feedback/DecisionRuleBar.jsx'
import EmailButtons, { EmailCounts } from '../../components/feedback/EmailButtons.jsx'
import {
  MAX_COMPARED,
  RANK_FILTERS,
  compareTo,
  SUITABILITY,
  approveAllDrafts,
  evaluationOf,
  matchesRankFilter,
  rankingSummary,
  readConsistency,
  readRanking,
} from '../../lib/assessment.js'
import { countStates, emailState } from '../../lib/feedback.js'

function LoadingRanking() {
  return (
    <div role="status" aria-label="Loading the ranked candidates" className="flex flex-col gap-4">
      <div className="grid grid-cols-4 gap-3">
        {['a', 'b', 'c', 'd'].map((key) => (
          <Skeleton key={key} className="h-24 rounded-2xl" />
        ))}
      </div>
      {['a', 'b', 'c'].map((key) => (
        <Skeleton key={key} className="h-18 w-full rounded-2xl" />
      ))}
    </div>
  )
}

function CountBox({ label, value, note, isReview }) {
  return (
    <div
      className={`flex flex-col gap-0.5 rounded-2xl border px-4 py-3.5 ${
        isReview ? 'border-[#F3D9A8] bg-[#FFFBF3]' : 'border-line bg-white'
      }`}
    >
      <span className={`text-[13px] font-semibold ${isReview ? 'text-amber' : 'text-[#6B7890]'}`}>
        {label}
      </span>
      <span className="font-display text-2xl font-extrabold tabular-nums text-navy">{value}</span>
      <span className="text-[12.5px]">{note}</span>
    </div>
  )
}

function EvaluateAllButton({ waiting, isRunning, onClick }) {
  if (!waiting) return null
  return (
    <Button
      disabled={isRunning}
      onClick={onClick}
      title={isRunning ? 'An evaluation is running. Wait for it to finish.' : undefined}
    >
      <Sparkles className="size-4.5" aria-hidden="true" />
      Evaluate all
      <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">{waiting} new</span>
    </Button>
  )
}

const VIEWS = [
  ['ranking', 'Ranked candidates'],
  ['consistency', 'Interview consistency'],
]

// The two views of a job's assessments: the ranked candidates (opens
// first) and how consistently their interviews were run (F10). "differ" is
// the Interview consistency badge: interviews that differ from the rest.
function ViewTabs({ view, differ, onChange }) {
  return (
    <div role="tablist" aria-label="Assessments views" className="flex flex-wrap gap-2">
      {VIEWS.map(([key, label]) => {
        const isActive = key === view
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(key)}
            className={`flex min-h-10 items-center gap-2 rounded-full border-[1.5px] px-4 text-sm font-semibold ${
              isActive
                ? 'border-brand bg-brand text-white'
                : 'border-line bg-white text-navy hover:border-brand/40 hover:bg-tint'
            }`}
          >
            {label}
            {key === 'consistency' && differ > 0 && (
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-bold ${
                  isActive ? 'bg-white/20 text-white' : 'bg-amber-soft text-amber'
                }`}
              >
                {differ} differ
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

function Empty({ title, children, action }) {
  return (
    <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-dashed border-[#A9C8FF] bg-white p-5.5">
      <h2 className="text-lg font-extrabold text-navy">{title}</h2>
      <p className="text-sm leading-relaxed">{children}</p>
      {action && <div>{action}</div>}
    </section>
  )
}

// The job's assessed candidates, ranked by overall score (40% CV, 60%
// interview); each row opens to show why it has its score. Draft reports are ranked
// too and marked; interviews without an overall score follow, unranked.
export default function AssessmentsTab() {
  const { job, listVersion, evaluation, feedback, onChanged } = useOutletContext()
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [openId, setOpenId] = useState(null)
  // The ranked candidates picked for comparing, in the order picked.
  const [picked, setPicked] = useState([])
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const view = searchParams.get('view') === 'consistency' ? 'consistency' : 'ranking'
  const [consistency, setConsistency] = useState(null)
  const [consistencyError, setConsistencyError] = useState('')

  function pick(sessionId) {
    setPicked((current) =>
      current.includes(sessionId)
        ? current.filter((id) => id !== sessionId)
        : current.length < MAX_COMPARED
          ? [...current, sessionId]
          : current,
    )
  }
  const [isApproving, setIsApproving] = useState(false)
  const [approveBusy, setApproveBusy] = useState(false)
  const [approveError, setApproveError] = useState('')
  const [approvedNotice, setApprovedNotice] = useState('')

  // Every draft report waiting for review is approved at once.
  async function approveAll() {
    setApproveBusy(true)
    setApproveError('')
    try {
      const result = await approveAllDrafts(job.id)
      setIsApproving(false)
      setApprovedNotice(
        `${result.approved} ${result.approved === 1 ? 'report' : 'reports'} approved.` +
          (result.skipped
            ? ` ${result.skipped} being rewritten ${result.skipped === 1 ? 'was' : 'were'} left as drafts.`
            : ''),
      )
      onChanged()
    } catch (error) {
      setApproveError(error.message)
    } finally {
      setApproveBusy(false)
    }
  }

  // Loaded again after each evaluation, and as Evaluate all moves on to the
  // next interview, so finished reports show up during the run.
  const current = evaluation.activity?.running?.result?.current ?? null
  // The same while feedback emails are written or sent, so each one shows.
  const feedbackCurrent = feedback.activity?.running?.result?.current ?? null
  useEffect(() => {
    let isCurrent = true
    readRanking(job.id)
      .then((loaded) => {
        if (!isCurrent) return
        setRows(loaded)
        setError('')
      })
      .catch((loadError) => isCurrent && setError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [job.id, listVersion, current, feedbackCurrent])

  // How consistently the interviews were run (F10), loaded again after each
  // evaluation like the ranking.
  useEffect(() => {
    let isCurrent = true
    readConsistency(job.id)
      .then((loaded) => {
        if (!isCurrent) return
        setConsistency(loaded)
        setConsistencyError('')
      })
      .catch((loadError) => isCurrent && setConsistencyError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [job.id, listVersion, current])

  function showView(next) {
    setSearchParams(next === 'ranking' ? {} : { view: next }, { replace: true })
  }

  const summary = rankingSummary(rows ?? [])
  // Drafts with a CV claim contradiction not looked at yet (F8): a warning
  // in Approve all drafts, never a block.
  const withContradictions = (rows ?? []).filter(
    (row) => row.status === 'draft' && row.open_contradictions > 0,
  )

  if (error) {
    return (
      <p role="alert" className="flex items-center gap-2 font-semibold text-danger">
        <CircleAlert className="size-5" aria-hidden="true" />
        {error}
      </p>
    )
  }
  if (!rows || !evaluation.isLoaded) return <LoadingRanking />

  const waiting = evaluation.activity.waiting
  const evaluateAll = (
    <EvaluateAllButton
      waiting={waiting}
      isRunning={evaluation.isRunning}
      onClick={() => evaluation.start()}
    />
  )

  if (rows.length === 0) {
    return (
      <Empty
        title="Nothing to assess yet"
        action={
          <Button variant="outline" to={`/app/jobs/${job.id}/interviews`}>
            Go to Interviews
          </Button>
        }
      >
        Candidates appear here after their interview is completed and evaluated.
      </Empty>
    )
  }

  const ranked = rows.filter((row) => row.rank != null)
  // A candidate who is no longer ranked cannot stay picked.
  const pickedRanked = picked.filter((id) => ranked.some((row) => row.session_id === id))
  const unranked = rows.filter((row) => row.rank == null)
  const shownRanked = ranked.filter((row) => matchesRankFilter(row, filter))
  const shownUnranked = filter === 'all' ? unranked : []
  const counts = { all: rows.length, ...summary }

  // Feedback emails (F11) of the candidates decided after the interview.
  const decided = rows.filter((row) => row.decision)
  const emailRows = decided.map((row) => ({
    row,
    state: emailState(row, row.candidate_id, feedback.activity),
  }))
  const person = ({ row }) => ({
    id: row.candidate_id,
    name: row.candidate_name,
    label: row.decision === 'hire' ? 'Hired' : 'Rejected',
  })
  const toWrite = emailRows.filter((item) => ['none', 'discarded'].includes(item.state)).map(person)
  const ready = emailRows.filter((item) => item.state === 'ready').map(person)
  const needReview = emailRows
    .filter((item) => ['review', 'failed'].includes(item.state))
    .map(person)
  const approvedRanked = ranked.filter((row) => row.status === 'approved')
  const feedbackProps = {
    activity: feedback.activity,
    isRunning: feedback.isRunning,
    write: feedback.write,
    onChanged,
  }

  return (
    <div className="flex flex-col gap-5">
      <ViewTabs view={view} differ={consistency?.differ ?? 0} onChange={showView} />
      {view === 'consistency' ? (
        <ConsistencyView consistency={consistency} error={consistencyError} />
      ) : (
        <>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 className="text-xl font-extrabold text-navy">Ranked candidates</h2>
              <p className="mt-1.5 text-sm">
                Ranked by overall score: 40% CV + 60% interview. The label is decision support; the
                decision stays with you.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2.5">
              {summary.review > 0 && (
                <Button
                  variant="outline"
                  disabled={evaluation.isRunning}
                  title={
                    evaluation.isRunning
                      ? 'An evaluation is running. Wait for it to finish.'
                      : undefined
                  }
                  onClick={() => {
                    setApproveError('')
                    setIsApproving(true)
                  }}
                >
                  Approve all drafts
                  <span className="rounded-full bg-tint px-2 py-0.5 text-xs">{summary.review}</span>
                </Button>
              )}
              {evaluateAll}
            </div>
          </div>

          {approvedNotice && (
            <p
              role="status"
              className="flex items-start gap-2.5 rounded-2xl bg-success-soft px-4 py-3 text-sm text-[#0B5C41]"
            >
              <CircleCheck className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
              {approvedNotice}
            </p>
          )}

          {evaluation.error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {evaluation.error}
            </p>
          )}

          {ranked.length === 0 ? (
            <Empty title="No candidate is ranked yet" action={evaluateAll}>
              {waiting > 0
                ? `${waiting} completed ${waiting === 1 ? 'interview has' : 'interviews have'} not been evaluated. Evaluate them to score the answers and write each candidate's report. Candidates are ranked here as soon as their report is written.`
                : 'Candidates are ranked here as soon as their report is written.'}
            </Empty>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {Object.entries(SUITABILITY).map(([key, item]) => (
                  <CountBox key={key} label={item.label} value={summary[key]} note={item.note} />
                ))}
                <CountBox
                  label="Waiting for your review"
                  value={summary.review}
                  note="draft reports"
                  isReview
                />
              </div>

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div role="group" aria-label="Show" className="flex flex-wrap gap-2">
                  {RANK_FILTERS.map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      aria-pressed={filter === key}
                      onClick={() => setFilter(key)}
                      className={`inline-flex min-h-9 items-center rounded-full px-3.5 text-[13.5px] font-semibold ${
                        filter === key
                          ? 'bg-navy text-white'
                          : 'border border-line bg-white text-navy hover:bg-tint'
                      }`}
                    >
                      {label} {counts[key]}
                    </button>
                  ))}
                </div>
                <span className="text-[13px]">Draft scores can still change after review.</span>
              </div>
            </>
          )}

          {approvedRanked.length > 0 && (
            <DecisionRuleBar
              key={approvedRanked.length}
              jobId={job.id}
              ranked={approvedRanked}
              skipped={ranked.length - approvedRanked.length}
              onChanged={onChanged}
            />
          )}

          {decided.length > 0 && (
            <section
              aria-label="Feedback emails"
              className="flex flex-wrap items-center justify-between gap-3.5 rounded-[18px] border border-[#E3D8FB] bg-[#FAF7FF] px-5.5 py-3.5"
            >
              <div className="flex flex-wrap items-center gap-3">
                <span className="flex size-9.5 items-center justify-center rounded-xl bg-violet-soft text-violet">
                  <Mail className="size-4.5" aria-hidden="true" />
                </span>
                <span className="font-display text-[15.5px] font-extrabold text-navy">
                  Feedback emails
                </span>
                <EmailCounts counts={countStates(emailRows.map((item) => item.state))} />
              </div>
              <EmailButtons
                toWrite={toWrite}
                ready={ready}
                needReview={needReview}
                isRunning={feedback.isRunning}
                onWrite={feedback.write}
                onSendAll={() => feedback.sendAll('interview')}
              />
              {feedback.error && (
                <p role="alert" className="basis-full text-sm font-semibold text-danger">
                  {feedback.error}
                </p>
              )}
            </section>
          )}

          {pickedRanked.length > 0 && (
            <section
              role="status"
              className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[#A9C8FF] bg-tint px-4.5 py-3"
            >
              <span className="text-[14.5px] font-semibold text-navy">
                {pickedRanked.length} selected · up to {MAX_COMPARED}
                {pickedRanked.length < 2 && (
                  <span className="font-normal text-body"> · pick one more to compare</span>
                )}
              </span>
              <span className="flex items-center gap-3.5">
                <button
                  type="button"
                  onClick={() => setPicked([])}
                  className="min-h-10 px-1 text-sm font-semibold text-brand hover:text-brand-dark"
                >
                  Clear
                </button>
                <Button
                  className="min-h-10"
                  disabled={pickedRanked.length < 2}
                  onClick={() => navigate(compareTo(job.id, pickedRanked))}
                >
                  Compare {pickedRanked.length} candidates
                </Button>
              </span>
            </section>
          )}

          {(shownRanked.length > 0 || shownUnranked.length > 0) && (
            <RankedList
              ranked={shownRanked}
              unranked={shownUnranked}
              openId={openId}
              onToggle={(id) => setOpenId((open) => (open === id ? null : id))}
              evaluationOf={(sessionId) => evaluationOf(evaluation.activity, sessionId)}
              isEvaluating={evaluation.isRunning}
              onEvaluate={(sessionId) => evaluation.start(sessionId)}
              onWriteReport={(sessionId) => evaluation.start(sessionId, { reportOnly: true })}
              picked={pickedRanked}
              onPick={pick}
              feedback={feedbackProps}
            />
          )}

          {ranked.length > 0 && shownRanked.length === 0 && shownUnranked.length === 0 && (
            <p className="text-sm">No candidate matches this filter.</p>
          )}
        </>
      )}

      {isApproving && (
        <ConfirmDialog
          title={`Approve ${summary.review} draft ${summary.review === 1 ? 'report' : 'reports'}?`}
          confirmLabel="Approve all"
          confirmVariant="primary"
          busyLabel="Approving…"
          isBusy={approveBusy}
          error={approveError}
          onConfirm={approveAll}
          onCancel={() => setIsApproving(false)}
        >
          <p>
            Each report becomes final and its candidate is marked assessed, the same as approving
            them one by one. Open a report first if you want to check or change it.
          </p>
          {withContradictions.length > 0 && (
            <p className="flex gap-2.5 rounded-2xl border border-[#F3D9A8] bg-[#FFFBF3] px-3.5 py-3 text-[13.5px] leading-normal text-[#6B3A00]">
              <TriangleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
              <span>
                <strong>A CV claim contradiction is not looked at yet</strong> for{' '}
                {withContradictions.map((row) => row.candidate_name).join(', ')}. You can still
                approve; it is on each assessment's CV claims tab.
              </span>
            </p>
          )}
        </ConfirmDialog>
      )}
    </div>
  )
}
