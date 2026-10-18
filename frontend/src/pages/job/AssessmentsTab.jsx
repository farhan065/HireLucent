import { CircleAlert, CircleCheck, Sparkles } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import ConfirmDialog from '../../components/ConfirmDialog.jsx'
import RankedList from '../../components/assessment/RankedList.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import {
  RANK_FILTERS,
  SUITABILITY,
  approveAllDrafts,
  evaluationOf,
  matchesRankFilter,
  rankingSummary,
  readRanking,
} from '../../lib/assessment.js'

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
  const { job, listVersion, evaluation, onChanged } = useOutletContext()
  const [rows, setRows] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [openId, setOpenId] = useState(null)
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
  }, [job.id, listVersion, current])

  const summary = rankingSummary(rows ?? [])

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
  const unranked = rows.filter((row) => row.rank == null)
  const shownRanked = ranked.filter((row) => matchesRankFilter(row, filter))
  const shownUnranked = filter === 'all' ? unranked : []
  const counts = { all: rows.length, ...summary }

  return (
    <div className="flex flex-col gap-5">
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
        />
      )}
      {ranked.length > 0 && shownRanked.length === 0 && shownUnranked.length === 0 && (
        <p className="text-sm">No candidate matches this filter.</p>
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
        </ConfirmDialog>
      )}
    </div>
  )
}
