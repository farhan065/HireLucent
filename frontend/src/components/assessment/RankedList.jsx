import { Check, ChevronDown, ChevronRight, LoaderCircle, X } from 'lucide-react'
import { Link } from 'react-router'
import {
  MAX_COMPARED,
  REPORT_STATUS,
  SUITABILITY,
  oneDecimal,
  scoreParts,
  unrankedReason,
} from '../../lib/assessment.js'
import { shortDay } from '../../lib/interviews.js'
import { emailAction, emailState } from '../../lib/feedback.js'
import Button from '../Button.jsx'
import DecisionButtons from '../feedback/DecisionButtons.jsx'
import EmailChip from '../feedback/EmailChip.jsx'
import { DimensionBars } from './InterviewPerformance.jsx'

// Eight columns that fit a standard laptop screen with no sideways scroll:
// compare, rank, candidate, overall (with CV · interview), report,
// decision, feedback email, action.
const GRID =
  'grid grid-cols-[22px_40px_minmax(110px,1.3fr)_minmax(120px,1.3fr)_minmax(88px,0.8fr)_148px_minmax(110px,1fr)_132px] items-center gap-3.5 px-5.5'
const LABEL = 'text-xs font-bold uppercase tracking-wider'
const RANK_STYLES = [
  'bg-[#FFF4D6] text-[#8A5A00]',
  'bg-[#EEF1F6] text-[#44526B]',
  'bg-[#FBEBDD] text-[#8A4B00]',
]
// How many strengths and weaknesses the opened row's summary shows; the
// rest are on the Report tab.
const SHOWN_STRENGTHS = 2
const SHOWN_WEAKNESSES = 1
// The report status, short enough for its column.
const SHORT_STATUS = { analysed: 'Analysed', draft: 'Draft', approved: 'Approved' }

function reportTo(row) {
  return `/app/interviews/${row.session_id}/assessment`
}

function Person({ row }) {
  return (
    <span className="flex min-w-0 flex-col gap-0.5">
      <span className="truncate text-[15.5px] font-semibold text-navy">{row.candidate_name}</span>
      <span className="text-[13px]">
        Interview {shortDay(row.started_at ?? row.scheduled_start)}
      </span>
    </span>
  )
}

// The arrow and the name open the row, as on the Screening tab.
function PersonToggle({ row, isOpen, onToggle }) {
  const Chevron = isOpen ? ChevronDown : ChevronRight
  return (
    <button
      type="button"
      aria-expanded={isOpen}
      aria-label={`${isOpen ? 'Hide' : 'Show'} why ${row.candidate_name} has this score`}
      onClick={onToggle}
      className="flex min-h-10 min-w-0 items-center gap-2.5 text-left"
    >
      <Chevron className="size-4.5 shrink-0 text-body" aria-hidden="true" />
      <Person row={row} />
    </button>
  )
}

function StatusCell({ row }) {
  const status = REPORT_STATUS[row.status]
  if (!status) {
    return (
      <span className="self-start whitespace-nowrap rounded-full bg-[#EEF1F6] px-3 py-1 text-[13px] font-semibold text-[#44526B]">
        Not evaluated
      </span>
    )
  }
  return (
    <div className="flex flex-col items-start gap-1">
      <span
        className={`whitespace-nowrap rounded-full px-3 py-1 text-[13px] font-semibold ${status.className}`}
      >
        {SHORT_STATUS[row.status] ?? status.label}
      </span>
      {row.status === 'draft' && <span className="text-[12.5px]">needs your review</span>}
      {row.status === 'approved' && row.approved_at && (
        <span className="text-[12.5px]">approved {shortDay(row.approved_at)}</span>
      )}
    </div>
  )
}

// The feedback email of a decided candidate (F11).
function EmailCell({ row, feedback }) {
  if (!row.decision) {
    return <span className="text-[13px]">{row.status === 'approved' ? 'Decide first' : '–'}</span>
  }
  const state = emailState(row, row.candidate_id, feedback.activity)
  const note =
    state === 'none' && row.decision === 'hire'
      ? 'Selection message'
      : state === 'none'
        ? 'AI writes it from the report'
        : undefined
  return <EmailChip state={state} warnings={row.feedback_warnings} note={note} />
}

// The row's action: review a draft report, the email's action once
// decided (the email opens on the assessment page's Decision tab), or open
// the report.
function ActionCell({ row, feedback }) {
  if (row.status === 'draft') {
    return (
      <Button to={reportTo(row)} className="min-h-10 whitespace-nowrap px-4 text-sm">
        Review report
      </Button>
    )
  }
  const state = row.decision ? emailState(row, row.candidate_id, feedback.activity) : null
  const action = state ? emailAction(state) : null
  if (action) {
    return (
      <Button
        variant={action.primary ? 'primary' : 'outline'}
        className="min-h-10 whitespace-nowrap px-4 text-sm"
        disabled={action.write && feedback.isRunning}
        to={action.write ? undefined : `${reportTo(row)}?tab=decision`}
        onClick={action.write ? () => feedback.write([row.candidate_id]) : undefined}
      >
        {action.label === 'Review' ? 'Review email' : action.label}
      </Button>
    )
  }
  if (!row.status) return null
  return (
    <Button
      to={reportTo(row)}
      variant="outline"
      className="min-h-10 whitespace-nowrap px-4 text-sm"
    >
      Open report
    </Button>
  )
}

function SummaryCard({ title, children }) {
  return (
    <div className="flex min-w-0 flex-col gap-2.5 rounded-2xl border border-[#E8EEF8] bg-white px-4.5 py-4">
      <span className={`${LABEL} text-[#6B7890]`}>{title}</span>
      {children}
    </div>
  )
}

function Point({ text, isStrength }) {
  const Icon = isStrength ? Check : X
  return (
    <span className="flex items-start gap-2.5 text-sm leading-snug text-navy">
      <span
        className={`mt-px flex size-5.5 shrink-0 items-center justify-center rounded-full ${
          isStrength ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
        }`}
      >
        <Icon className="size-3.5" strokeWidth={3} aria-hidden="true" />
      </span>
      <span className="line-clamp-2" title={text}>
        {text}
      </span>
    </span>
  )
}

// The opened row: a short summary only (the full report, with its quotes
// and sources, is on the Report tab). The score sum, the top strengths and
// weakness in a line each, and what is left to check.
function Details({ row }) {
  const parts = scoreParts(row)
  const label = SUITABILITY[row.suitability]
  const coverage = row.coverage
  const notExplored = (row.coverage_map ?? [])
    .filter((entry) => entry.status === 'not_explored')
    .map((entry) => entry.requirement_id)
  const areas = row.areas_to_verify?.length ?? 0
  const strengths = (row.strengths ?? []).slice(0, SHOWN_STRENGTHS)
  const weaknesses = (row.weaknesses ?? []).slice(0, SHOWN_WEAKNESSES)
  return (
    <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1.35fr)_minmax(0,1fr)] gap-3.5 border-b border-[#EEF2F9] bg-[#FBFCFF] pt-1 pr-5.5 pb-5.5 pl-24">
      <SummaryCard title="Score">
        <span className="flex justify-between gap-2.5 text-sm">
          <span>CV × 40%</span>
          <span className="whitespace-nowrap tabular-nums text-navy">
            {oneDecimal(row.cv_score)} → <strong>{parts.cv}</strong>
          </span>
        </span>
        <span className="flex justify-between gap-2.5 text-sm">
          <span>Interview × 60%</span>
          <span className="whitespace-nowrap tabular-nums text-navy">
            {oneDecimal(row.interview_score)} → <strong>{parts.interview}</strong>
          </span>
        </span>
        <span className="flex justify-between gap-2.5 border-t border-[#E8EEF8] pt-2 text-[14.5px] font-bold text-navy">
          <span>Overall</span>
          <span className="whitespace-nowrap tabular-nums">
            {oneDecimal(row.overall_score)} · {label?.label}
          </span>
        </span>
        {row.interview_dimensions && <DimensionBars dimensions={row.interview_dimensions} />}
      </SummaryCard>

      <SummaryCard title="In short">
        {strengths.map((claim) => (
          <Point key={claim.id} text={claim.text} isStrength />
        ))}
        {weaknesses.map((claim) => (
          <Point key={claim.id} text={claim.text} isStrength={false} />
        ))}
        {!strengths.length && !weaknesses.length && (
          <span className="text-sm">The report lists no strengths or weaknesses.</span>
        )}
      </SummaryCard>

      <SummaryCard title="To check">
        <span className="text-sm text-navy">
          {coverage && coverage.total > 0 ? (
            <>
              <strong>
                {coverage.covered} of {coverage.total}
              </strong>{' '}
              requirements covered
            </>
          ) : (
            'No requirements'
          )}
        </span>
        {notExplored.length > 0 && (
          <span className="flex flex-wrap items-center gap-1.5 text-[13px]">
            <span>Not explored:</span>
            {notExplored.map((id) => (
              <span
                key={id}
                className="rounded-lg bg-amber-soft px-2 py-0.5 font-semibold text-amber"
              >
                {id}
              </span>
            ))}
          </span>
        )}
        {areas > 0 && (
          <span className="text-sm text-navy">
            <strong>{areas}</strong> {areas === 1 ? 'area' : 'areas'} to verify
          </span>
        )}
        <Link to={reportTo(row)} className="text-sm font-semibold text-brand hover:text-brand-dark">
          Open the full report →
        </Link>
      </SummaryCard>
    </div>
  )
}

// The box that picks a candidate for comparing. Up to MAX_COMPARED can be
// picked; the others are then greyed out.
function PickBox({ row, isPicked, canPick, onPick }) {
  return (
    <input
      type="checkbox"
      checked={isPicked}
      disabled={!isPicked && !canPick}
      onChange={() => onPick(row.session_id)}
      aria-label={`Compare ${row.candidate_name}`}
      title={
        !isPicked && !canPick ? `Up to ${MAX_COMPARED} candidates can be compared.` : undefined
      }
      className="size-4.5 cursor-pointer accent-brand disabled:cursor-not-allowed disabled:opacity-40"
    />
  )
}

function RankedRow({ row, isOpen, onToggle, isPicked, canPick, onPick, feedback }) {
  const label = SUITABILITY[row.suitability]
  const isDraft = row.status === 'draft'
  return (
    <>
      <div
        className={`${GRID} border-b border-[#EEF2F9] py-4.5 ${
          isOpen || isPicked ? 'bg-mist/60' : isDraft ? 'bg-[#FFFCF6]' : 'bg-white'
        }`}
      >
        <PickBox row={row} isPicked={isPicked} canPick={canPick} onPick={onPick} />
        <span
          className={`flex size-9 items-center justify-center rounded-xl font-display text-base font-extrabold ${
            RANK_STYLES[row.rank - 1] ?? 'bg-mist text-[#6B7890]'
          }`}
        >
          {row.rank}
        </span>
        <PersonToggle row={row} isOpen={isOpen} onToggle={onToggle} />
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-display text-xl font-extrabold tabular-nums text-navy">
              {oneDecimal(row.overall_score)}
            </span>
            {label && (
              <span
                className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-bold ${label.className}`}
              >
                {label.label}
              </span>
            )}
          </div>
          <span
            aria-hidden="true"
            className="h-1.5 w-full max-w-36 overflow-hidden rounded-full bg-[#E4EAF4]"
          >
            <span
              className={`block h-full rounded-full ${label?.bar ?? 'bg-brand'}`}
              style={{ width: `${row.overall_score}%` }}
            />
          </span>
          <span className="text-[13px]">
            CV <strong className="tabular-nums text-navy">{oneDecimal(row.cv_score)}</strong> ·
            Interview{' '}
            <strong className="tabular-nums text-navy">{oneDecimal(row.interview_score)}</strong>
          </span>
        </div>
        <StatusCell row={row} />
        <DecisionButtons row={row} name={row.candidate_name} onChanged={feedback.onChanged} />
        <EmailCell row={row} feedback={feedback} />
        <div className="flex justify-end">
          <ActionCell row={row} feedback={feedback} />
        </div>
      </div>
      {isOpen && <Details row={row} />}
    </>
  )
}

function UnrankedRow({ row, evaluation, isEvaluating, onEvaluate, onWriteReport, feedback }) {
  let middle = <span className="text-[13.5px] leading-snug">{unrankedReason(row)}</span>
  let action = null
  if (evaluation.state === 'running') {
    middle = (
      <span role="status" className="flex flex-col gap-1.5">
        <span className="flex items-center gap-2 text-sm font-semibold text-brand-dark">
          <LoaderCircle
            className="size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          Evaluating · {evaluation.message === 'starting' ? 'starting' : evaluation.message}
        </span>
        <span aria-hidden="true" className="h-1.5 w-full overflow-hidden rounded-full bg-[#E4EAF4]">
          <span
            className="block h-full rounded-full bg-brand transition-[width]"
            style={{ width: `${Math.max(evaluation.percent ?? 0, 4)}%` }}
          />
        </span>
      </span>
    )
  } else if (evaluation.state === 'queued') {
    middle = <span className="text-[13.5px]">Waiting to be evaluated.</span>
  } else if (evaluation.state === 'failed') {
    middle = (
      <span role="alert" className="text-[13.5px] leading-snug text-danger">
        {evaluation.reason}
      </span>
    )
  }
  const isBusy = ['running', 'queued'].includes(evaluation.state)
  // Answers evaluated without a report (for example before reports
  // existed): only the report is written. Not evaluated: the full run.
  const startable = !isBusy && (!row.status || row.status === 'analysed')
  if (startable) {
    const writesReport = row.status === 'analysed'
    action = (
      <Button
        className="min-h-10 whitespace-nowrap px-4 text-sm"
        disabled={isEvaluating}
        title={isEvaluating ? 'An evaluation is running. Wait for it to finish.' : undefined}
        onClick={() => (writesReport ? onWriteReport : onEvaluate)(row.session_id)}
      >
        {writesReport ? 'Write report' : 'Evaluate'}
      </Button>
    )
  } else if (row.status && !isBusy) {
    action = <ActionCell row={row} feedback={feedback} />
  }
  const isApproved = row.status === 'approved'
  return (
    <div className={`${GRID} border-b border-[#EEF2F9] py-4.5 last:border-b-0`}>
      <span aria-hidden="true" />
      <span className="text-center font-bold text-[#9AA6BA]">–</span>
      <Person row={row} />
      <div className="min-w-0">{middle}</div>
      <StatusCell row={row} />
      {isApproved ? (
        <DecisionButtons row={row} name={row.candidate_name} onChanged={feedback.onChanged} />
      ) : (
        <span aria-hidden="true" />
      )}
      {isApproved ? <EmailCell row={row} feedback={feedback} /> : <span aria-hidden="true" />}
      <div className="flex justify-end">{action}</div>
    </div>
  )
}

// The job's completed interviews: ranked candidates by overall score, each
// opening to show why it has its score, then the interviews not ranked yet.
export default function RankedList({
  ranked,
  unranked,
  openId,
  onToggle,
  evaluationOf,
  isEvaluating,
  onEvaluate,
  onWriteReport,
  picked,
  onPick,
  feedback,
}) {
  return (
    <section
      aria-label="Ranked candidates"
      className="overflow-x-auto rounded-[22px] border border-line bg-white shadow-card"
    >
      <div className="min-w-[920px]">
        <div
          className={`${GRID} border-b border-line bg-mist py-3.5 text-xs font-semibold uppercase tracking-wider text-[#6B7890]`}
        >
          <span>
            <span className="sr-only">Compare</span>
          </span>
          <span>Rank</span>
          <span>Candidate</span>
          <span>Overall</span>
          <span>Report</span>
          <span>Decision</span>
          <span>Feedback email</span>
          <span className="text-right">Action</span>
        </div>
        {ranked.map((row) => (
          <RankedRow
            key={row.session_id}
            row={row}
            isOpen={openId === row.session_id}
            onToggle={() => onToggle(row.session_id)}
            isPicked={picked.includes(row.session_id)}
            canPick={picked.length < MAX_COMPARED}
            onPick={onPick}
            feedback={feedback}
          />
        ))}
        {unranked.length > 0 && (
          <>
            <div className="border-b border-[#EEF2F9] bg-[#F8FAFE] px-5.5 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7890]">
              Not ranked yet
            </div>
            {unranked.map((row) => (
              <UnrankedRow
                key={row.session_id}
                row={row}
                evaluation={evaluationOf(row.session_id)}
                isEvaluating={isEvaluating}
                onEvaluate={onEvaluate}
                onWriteReport={onWriteReport}
                feedback={feedback}
              />
            ))}
          </>
        )}
      </div>
    </section>
  )
}
