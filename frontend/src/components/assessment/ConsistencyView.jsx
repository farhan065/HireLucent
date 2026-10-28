import { Check, Search, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { QUALITY_LABELS, roundScore } from '../../lib/assessment.js'
import Skeleton from '../Skeleton.jsx'

const CARD = 'rounded-[22px] border border-line bg-white'
const LABEL = 'text-xs font-bold uppercase tracking-[0.06em] text-[#6B7890]'
const PRIORITIES = { must_have: 'must-have', preferred: 'preferred' }
const PAGE = 10

function interviewDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function Quality({ score, label }) {
  const tone = QUALITY_LABELS[label]
  return (
    <span className="flex items-center gap-2">
      <strong className="font-display text-[17px] tabular-nums text-navy">
        {score == null ? '–' : roundScore(score)}
      </strong>
      {tone && (
        <span className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-bold ${tone.className}`}>
          {tone.label}
        </span>
      )}
    </span>
  )
}

function OpenLink({ sessionId, name }) {
  return (
    <Link
      to={`/app/interviews/${sessionId}/assessment?tab=quality`}
      aria-label={`Open the interview quality of ${name}`}
      className="inline-flex min-h-10 items-center rounded-full border-[1.5px] border-brand px-3.5 font-display text-sm font-bold text-brand hover:bg-tint"
    >
      Open
    </Link>
  )
}

function Typical({ typical, count }) {
  const tiles = [
    [`${typical.minutes ?? '–'} min`, 'length'],
    [typical.questions ?? '–', 'questions'],
    [`${typical.candidate_share ?? '–'}%`, 'candidate spoke'],
  ]
  return (
    <div className="flex flex-[1_1_260px] flex-col gap-2.5">
      <span className={LABEL}>A typical interview</span>
      <div className="grid grid-cols-3 gap-2.5">
        {tiles.map(([value, note]) => (
          <div key={note} className="flex flex-col gap-0.5 rounded-[14px] bg-[#F4F8FF] px-3.5 py-3">
            <span className="font-display text-xl font-extrabold tabular-nums text-navy">
              {value}
            </span>
            <span className="text-[13px]">{note}</span>
          </div>
        ))}
      </div>
      <span className="text-[12.5px]">The middle value of the {count} interviews.</span>
    </div>
  )
}

function Requirements({ requirements }) {
  return (
    <div className="flex min-w-0 flex-[1.4_1_380px] flex-col gap-2.5">
      <span className={LABEL}>How many interviews asked each requirement</span>
      {requirements.map((item) => (
        <div
          key={item.id}
          className="grid grid-cols-[34px_minmax(0,1.2fr)_minmax(0,1fr)_64px] items-center gap-3 text-[13.5px]"
        >
          <strong className="text-[#6B7890]">{item.id}</strong>
          <span className="flex min-w-0 flex-wrap items-center gap-2 text-navy">
            <span>
              {item.text} · {PRIORITIES[item.priority] ?? item.priority}
            </span>
            {item.mostly_missed && (
              <span className="rounded-full bg-amber-soft px-2 py-0.5 text-xs font-semibold text-amber">
                Mostly missed
              </span>
            )}
          </span>
          <span aria-hidden="true" className="h-[7px] overflow-hidden rounded-full bg-[#E4EAF4]">
            <span
              className={`block h-full ${item.mostly_missed ? 'bg-[#D97706]' : 'bg-brand'}`}
              style={{ width: `${(100 * item.asked) / item.total}%` }}
            />
          </span>
          <span className="text-right font-bold tabular-nums text-navy">
            {item.asked} of {item.total}
          </span>
        </div>
      ))}
    </div>
  )
}

const ROW = 'grid grid-cols-[minmax(0,0.9fr)_minmax(0,2fr)_170px_80px] items-center gap-3.5 px-6'

function Differing({ interviews }) {
  const differing = interviews.filter((item) => item.flags.length > 0)
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 pt-4.5 pb-2">
        <span className={LABEL}>Interviews that differ from the rest</span>
        {differing.length > 0 && <span className="text-[13px]">Most differences first</span>}
      </div>
      {differing.length === 0 ? (
        <p className="px-6 pb-4 text-sm">Every interview was run in a similar way.</p>
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div
              className={`${ROW} border-y border-[#EEF2F9] bg-[#F4F8FF] py-2.5 text-xs font-semibold tracking-[0.05em] text-[#6B7890] uppercase`}
            >
              <span>Candidate</span>
              <span>What differs</span>
              <span>Interview quality</span>
              <span />
            </div>
            {differing.map((item) => (
              <div key={item.session_id} className={`${ROW} border-b border-[#EEF2F9] py-3.5`}>
                <span className="flex flex-col gap-0.5">
                  <span className="text-[15px] font-semibold text-navy">{item.candidate_name}</span>
                  <span className="text-[13px]">Interview {interviewDate(item.interview_at)}</span>
                </span>
                <span className="flex flex-wrap gap-1.5">
                  {item.flags.map((flag) => (
                    <span
                      key={flag.kind + (flag.requirement_id ?? '')}
                      className="rounded-full bg-amber-soft px-2.5 py-1 text-[13px] font-semibold text-amber"
                    >
                      {flag.text}
                    </span>
                  ))}
                </span>
                <Quality score={item.quality_score} label={item.quality_label} />
                <span className="flex justify-end">
                  <OpenLink sessionId={item.session_id} name={item.candidate_name} />
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  )
}

function Mark({ isAsked, isFlagged }) {
  return isAsked ? (
    <Check className="size-4 text-success" aria-label="asked" />
  ) : (
    <X className={`size-4 ${isFlagged ? 'text-amber' : 'text-danger'}`} aria-label="not asked" />
  )
}

// Every checked interview, with search and a filter.
function AllInterviews({ consistency }) {
  const [query, setQuery] = useState('')
  const [onlyDiffer, setOnlyDiffer] = useState(false)
  const [shown, setShown] = useState(PAGE)
  const requirements = consistency.requirements
  const needle = query.trim().toLowerCase()
  const rows = consistency.interviews.filter(
    (item) =>
      (!onlyDiffer || item.flags.length > 0) &&
      (!needle || item.candidate_name.toLowerCase().includes(needle)),
  )
  const columns = `minmax(160px,1fr) 80px 90px 110px repeat(${requirements.length}, 44px) 170px`
  return (
    <div className="flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-y border-[#EEF2F9] px-6 py-3.5">
        <label
          htmlFor="consistency-search"
          className="flex min-h-11 w-full items-center gap-2.5 rounded-full border-[1.5px] border-line bg-white px-3.5 focus-within:border-brand sm:w-80"
        >
          <Search className="size-4.5 shrink-0 text-body" aria-hidden="true" />
          <span className="sr-only">Search candidates by name</span>
          <input
            id="consistency-search"
            type="search"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              setShown(PAGE)
            }}
            placeholder="Search candidates"
            className="min-w-0 flex-1 bg-transparent text-[14.5px] text-navy placeholder:text-body/70 focus:outline-none"
          />
        </label>
        <div role="group" aria-label="Show" className="flex gap-1.5">
          {[
            [false, `All ${consistency.count}`],
            [true, `Differ ${consistency.differ}`],
          ].map(([value, label]) => (
            <button
              key={label}
              type="button"
              aria-pressed={onlyDiffer === value}
              onClick={() => {
                setOnlyDiffer(value)
                setShown(PAGE)
              }}
              className={`min-h-9 rounded-full border-[1.5px] px-3.5 text-[13.5px] font-bold ${
                onlyDiffer === value
                  ? 'border-brand bg-tint text-brand-dark'
                  : 'border-line bg-white text-body hover:bg-tint'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <div className="min-w-max">
          <div
            className="grid items-center gap-3 bg-[#F4F8FF] px-6 py-2.5 text-xs font-semibold tracking-[0.05em] text-[#6B7890] uppercase"
            style={{ gridTemplateColumns: columns }}
          >
            <span>Candidate</span>
            <span>Length</span>
            <span>Questions</span>
            <span>Cand. spoke</span>
            {requirements.map((item) => (
              <span key={item.id} title={item.text}>
                {item.id}
              </span>
            ))}
            <span>Quality</span>
          </div>
          {rows.slice(0, shown).map((item) => {
            const kinds = new Set(item.flags.map((flag) => flag.kind))
            const missed = new Set(
              item.flags.filter((flag) => flag.requirement_id).map((flag) => flag.requirement_id),
            )
            return (
              <div
                key={item.session_id}
                className="grid items-center gap-3 border-b border-[#EEF2F9] px-6 py-3 text-sm"
                style={{ gridTemplateColumns: columns }}
              >
                <Link
                  to={`/app/interviews/${item.session_id}/assessment?tab=quality`}
                  className="font-semibold text-navy hover:text-brand"
                >
                  {item.candidate_name}
                </Link>
                <span className={kinds.has('length') ? 'font-bold text-amber' : ''}>
                  {item.minutes ?? '–'} min
                </span>
                <span className={kinds.has('questions') ? 'font-bold text-amber' : ''}>
                  {item.questions}
                </span>
                <span className={kinds.has('speaking_share') ? 'font-bold text-amber' : ''}>
                  {item.candidate_share ?? '–'}%
                </span>
                {requirements.map((requirement) => (
                  <Mark
                    key={requirement.id}
                    isAsked={item.explored.includes(requirement.id)}
                    isFlagged={missed.has(requirement.id)}
                  />
                ))}
                <Quality score={item.quality_score} label={item.quality_label} />
              </div>
            )
          })}
        </div>
      </div>
      {rows.length === 0 && <p className="px-6 py-4 text-sm">No candidate matches.</p>}
      {rows.length > shown && (
        <div className="flex justify-center px-6 pt-3 pb-4">
          <button
            type="button"
            onClick={() => setShown((current) => current + PAGE)}
            className="min-h-10 px-4 text-sm font-semibold text-brand hover:text-brand-dark"
          >
            Show {Math.min(PAGE, rows.length - shown)} more
          </button>
        </div>
      )}
    </div>
  )
}

// The Interview consistency sub-tab of a job's Assessments (F10): were the
// candidates interviewed in a similar way? A summary, then only the
// interviews that differ, and every interview on request.
export default function ConsistencyView({ consistency, error }) {
  const [isAll, setIsAll] = useState(false)

  if (error) {
    return (
      <p role="alert" className="text-sm font-semibold text-danger">
        {error}
      </p>
    )
  }
  if (!consistency) {
    return (
      <div
        role="status"
        aria-label="Loading the interview consistency"
        className="flex flex-col gap-3"
      >
        <Skeleton className="h-40 rounded-[22px]" />
        <Skeleton className="h-56 rounded-[22px]" />
      </div>
    )
  }
  if (consistency.count < consistency.min_interviews) {
    return (
      <section className={`${CARD} flex max-w-xl flex-col gap-3 p-6`}>
        <h2 className="font-display text-lg font-extrabold text-navy">Interview consistency</h2>
        <p className="text-[14.5px] leading-relaxed">
          Shown once at least {consistency.min_interviews} interviews of this job are evaluated.{' '}
          {consistency.count} {consistency.count === 1 ? 'is' : 'are'} evaluated so far.
        </p>
      </section>
    )
  }

  return (
    <section aria-label="Interview consistency" className={`${CARD} overflow-hidden shadow-card`}>
      <div className="flex flex-col gap-1 border-b border-[#EEF2F9] px-6 pt-5 pb-4">
        <h2 className="font-display text-lg font-extrabold text-navy">Interview consistency</h2>
        <span className="text-[13.5px]">
          Were the candidates for this job interviewed in a similar way? Compares the{' '}
          {consistency.count} evaluated interviews.
        </span>
      </div>
      <div className="flex flex-wrap gap-5.5 border-b border-[#EEF2F9] px-6 py-5">
        <Typical typical={consistency.typical} count={consistency.count} />
        <Requirements requirements={consistency.requirements} />
      </div>
      {isAll ? (
        <AllInterviews consistency={consistency} />
      ) : (
        <Differing interviews={consistency.interviews} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 px-6 pt-3.5 pb-4.5">
        <span className="max-w-3xl text-[13px] leading-normal">
          Flagged when a must-have asked in most other interviews was not asked, the length or
          number of questions is under half or over 1.5 times the typical one, or the candidate's
          share differs by more than 20 points.
        </span>
        <button
          type="button"
          onClick={() => setIsAll((current) => !current)}
          className="inline-flex min-h-10 items-center rounded-full border-[1.5px] border-brand bg-white px-4 font-display text-sm font-bold text-brand hover:bg-tint"
        >
          {isAll ? 'Show only those that differ' : `Show all ${consistency.count} interviews`}
        </button>
      </div>
    </section>
  )
}
