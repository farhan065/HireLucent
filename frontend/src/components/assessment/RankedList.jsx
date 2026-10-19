import { ChevronDown, ChevronRight, LoaderCircle } from 'lucide-react'
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
import Button from '../Button.jsx'
import SourceChip from './SourceChip.jsx'

const GRID =
  'grid grid-cols-[24px_56px_minmax(0,1.4fr)_minmax(0,1.25fr)_minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.15fr)_170px] items-center gap-4 px-6'
const LABEL = 'text-xs font-bold uppercase tracking-wider'
const RANK_STYLES = [
  'bg-[#FFF4D6] text-[#8A5A00]',
  'bg-[#EEF1F6] text-[#44526B]',
  'bg-[#FBEBDD] text-[#8A4B00]',
]
// How many strengths and weaknesses the opened row shows.
const SHOWN_STRENGTHS = 2
const SHOWN_WEAKNESSES = 1
const SHOWN_FINDINGS = 2

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
      <span className="self-start rounded-full bg-[#EEF1F6] px-3 py-1 text-[13px] font-semibold text-[#44526B]">
        Not evaluated
      </span>
    )
  }
  return (
    <div className="flex flex-col items-start gap-1">
      <span className={`rounded-full px-3 py-1 text-[13px] font-semibold ${status.className}`}>
        {row.status === 'draft' ? 'Draft' : status.label}
      </span>
      {row.status === 'draft' && <span className="text-[12.5px]">needs your review</span>}
      {row.status === 'approved' && row.approved_at && (
        <span className="text-[12.5px]">approved {shortDay(row.approved_at)}</span>
      )}
    </div>
  )
}

function Claims({ title, tone, claims, limit, sessionId }) {
  if (!claims?.length) return null
  return (
    <div className="flex flex-col gap-2">
      <span className={`${LABEL} ${tone}`}>{title}</span>
      {claims.slice(0, limit).map((claim) => (
        <div key={claim.id} className="flex flex-col gap-1.5 text-sm text-navy">
          <span>{claim.text}</span>
          <span className="flex flex-wrap gap-1.5">
            {claim.sources.map((source, index) => (
              <SourceChip key={index} sessionId={sessionId} source={source} />
            ))}
          </span>
        </div>
      ))}
    </div>
  )
}

// The opened row: the sum behind the overall score, the report's top
// strengths and weaknesses with their sources, and the gaps to check.
function Details({ row }) {
  const parts = scoreParts(row)
  const label = SUITABILITY[row.suitability]
  return (
    <div className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1.6fr)_minmax(0,1fr)] gap-5 border-b border-[#EEF2F9] pt-1.5 pr-6 pb-6 pl-34">
      <div className="flex flex-col gap-2.5 self-start rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] p-4">
        <span className={`${LABEL} text-[#6B7890]`}>How the score is made</span>
        <div className="flex justify-between gap-3 text-sm">
          <span>
            CV score <span className="text-[12.5px]">(screening)</span>
          </span>
          <span className="whitespace-nowrap tabular-nums text-navy">
            {oneDecimal(row.cv_score)} × 40% = <strong>{parts.cv}</strong>
          </span>
        </div>
        <div className="flex justify-between gap-3 text-sm">
          <span>
            Interview score{' '}
            <span className="text-[12.5px]">
              ({row.answers_evaluated} {row.answers_evaluated === 1 ? 'answer' : 'answers'})
            </span>
          </span>
          <span className="whitespace-nowrap tabular-nums text-navy">
            {oneDecimal(row.interview_score)} × 60% = <strong>{parts.interview}</strong>
          </span>
        </div>
        <div className="flex justify-between gap-3 border-t border-line pt-2 text-[14.5px] font-bold text-navy">
          <span>Overall</span>
          <span className="whitespace-nowrap tabular-nums">
            {oneDecimal(row.overall_score)} · {label?.label}
          </span>
        </div>
        <span className="text-[12.5px] leading-snug">
          Interview score = average of the evaluated answers. Small talk is not counted.
        </span>
      </div>

      <div className="flex min-w-0 flex-col gap-3.5">
        <Claims
          title="Top strengths"
          tone="text-success"
          claims={row.strengths}
          limit={SHOWN_STRENGTHS}
          sessionId={row.session_id}
        />
        <Claims
          title={row.weaknesses?.length > 1 ? 'Top weakness' : 'Weakness'}
          tone="text-danger"
          claims={row.weaknesses}
          limit={SHOWN_WEAKNESSES}
          sessionId={row.session_id}
        />
        {!row.strengths?.length && !row.weaknesses?.length && (
          <p className="text-sm">The report lists no strengths or weaknesses.</p>
        )}
      </div>

      <div className="flex flex-col gap-2.5 self-start">
        {row.gaps?.length > 0 && (
          <div className="rounded-2xl border border-[#F3D9A8] bg-[#FFFBF3] px-4 py-3.5 text-[13.5px] leading-snug text-[#6B3A00]">
            <strong>
              {row.gaps.length} evidence {row.gaps.length === 1 ? 'gap' : 'gaps'}
            </strong>
            {row.gaps.slice(0, SHOWN_FINDINGS).map((gap) => (
              <span key={gap.id} className="mt-1 block">
                {gap.text}
              </span>
            ))}
          </div>
        )}
        {row.areas_to_verify?.length > 0 && (
          <div className="rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] px-4 py-3.5 text-[13.5px] leading-snug">
            <strong className="text-navy">
              {row.areas_to_verify.length} {row.areas_to_verify.length === 1 ? 'area' : 'areas'} to
              verify
            </strong>
            {row.areas_to_verify.slice(0, SHOWN_FINDINGS).map((area) => (
              <span key={area.id} className="mt-1 block">
                {area.text}
              </span>
            ))}
          </div>
        )}
        <Link to={reportTo(row)} className="text-sm font-semibold text-brand hover:text-brand-dark">
          Open the full report →
        </Link>
      </div>
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

function RankedRow({ row, isOpen, onToggle, isPicked, canPick, onPick }) {
  const label = SUITABILITY[row.suitability]
  const isDraft = row.status === 'draft'
  const coverage = row.coverage
  const missing = [
    coverage?.weak ? `${coverage.weak} weak` : null,
    coverage?.not_explored ? `${coverage.not_explored} not explored` : null,
  ].filter(Boolean)
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
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2.5">
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
          <span aria-hidden="true" className="h-1.5 w-36 overflow-hidden rounded-full bg-[#E4EAF4]">
            <span
              className={`block h-full rounded-full ${label?.bar ?? 'bg-brand'}`}
              style={{ width: `${row.overall_score}%` }}
            />
          </span>
        </div>
        <div className="flex flex-col gap-0.5 text-sm text-navy">
          <span>
            CV <strong className="tabular-nums">{oneDecimal(row.cv_score)}</strong>
          </span>
          <span>
            Interview <strong className="tabular-nums">{oneDecimal(row.interview_score)}</strong>
          </span>
        </div>
        <div className="flex flex-col gap-0.5 text-[13.5px]">
          {coverage && coverage.total > 0 ? (
            <>
              <span className="font-semibold text-navy">
                {coverage.covered} of {coverage.total} covered
              </span>
              {missing.length > 0 && <span>{missing.join(' · ')}</span>}
            </>
          ) : (
            <span>No requirements</span>
          )}
        </div>
        <StatusCell row={row} />
        <div className="flex justify-end">
          <Button
            to={reportTo(row)}
            variant={isDraft ? 'primary' : 'outline'}
            className="min-h-10 whitespace-nowrap px-4 text-sm"
          >
            {isDraft ? 'Review report' : 'Open report'}
          </Button>
        </div>
      </div>
      {isOpen && <Details row={row} />}
    </>
  )
}

function UnrankedRow({ row, evaluation, isEvaluating, onEvaluate, onWriteReport }) {
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
        <span aria-hidden="true" className="h-1.5 w-64 overflow-hidden rounded-full bg-[#E4EAF4]">
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
    action = (
      <Button
        to={reportTo(row)}
        variant="outline"
        className="min-h-10 whitespace-nowrap px-4 text-sm"
      >
        Open report
      </Button>
    )
  }
  return (
    <div className={`${GRID} border-b border-[#EEF2F9] py-4.5 last:border-b-0`}>
      <span aria-hidden="true" />
      <span className="text-center font-bold text-[#9AA6BA]">–</span>
      <Person row={row} />
      <div className="col-span-3">{middle}</div>
      <StatusCell row={row} />
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
}) {
  return (
    <section
      aria-label="Ranked candidates"
      className="overflow-x-auto rounded-[22px] border border-line bg-white shadow-card"
    >
      <div className="min-w-[1040px]">
        <div
          className={`${GRID} border-b border-line bg-mist py-3.5 text-xs font-semibold uppercase tracking-wider text-[#6B7890]`}
        >
          <span>
            <span className="sr-only">Compare</span>
          </span>
          <span>Rank</span>
          <span>Candidate</span>
          <span>Overall</span>
          <span>CV · Interview</span>
          <span>Requirements</span>
          <span>Report</span>
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
          />
        ))}
        {unranked.length > 0 && (
          <>
            <div className="border-b border-[#EEF2F9] bg-[#F8FAFE] px-6 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7890]">
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
              />
            ))}
          </>
        )}
      </div>
    </section>
  )
}
