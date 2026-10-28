import { BarChart3, ChevronDown, ChevronUp, CircleAlert, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { DIMENSION_SHORT, oneDecimal, roundScore, scoreTone } from '../../lib/assessment.js'
import { fromStart } from '../../lib/room.js'
import Button from '../Button.jsx'

const CARD = 'rounded-[20px] border border-line bg-white'
const HEADING = 'font-display text-lg font-extrabold text-navy'
const PRIORITIES = { must_have: 'Must-have', preferred: 'Preferred' }
const COVERAGE_LABELS = { covered: 'Covered', weak: 'Weak' }

// What each dimension's average is made of, shown when it is opened.
function howMade(item) {
  const count = item.answers.length
  switch (item.key) {
    case 'technical':
      return 'Average of accuracy and completeness of each technical answer. A technical question not answered counts as 0.'
    case 'communication':
      return 'Average clarity of the answered questions. A question not answered is left out.'
    case 'relevance':
      return 'Average relevance of every question asked. A question not answered counts as 0.'
    case 'problem_solving':
      return `Average of the ${count} ${count === 1 ? 'answer' : 'answers'} that showed problem-solving. Answers that did not call for it are left out.`
    case 'depth':
      return `Average of the ${count} ${count === 1 ? 'answer' : 'answers'} that described the candidate's own work. Answers that did not are left out.`
    default:
      return 'Average coverage of the explored requirements, must-haves counted twice. Requirements never explored are left out and listed as evidence gaps.'
  }
}

function Bar({ score, height = 'h-2' }) {
  return (
    <span aria-hidden="true" className={`${height} overflow-hidden rounded-full bg-[#E4EAF4]`}>
      <span
        className={`block h-full rounded-full ${scoreTone(score).bar}`}
        style={{ width: `${score}%` }}
      />
    </span>
  )
}

function NotAssessed({ className = '' }) {
  return (
    <span
      className={`rounded-full border border-dashed border-[#B8C3D6] px-3 py-1 text-[13px] font-semibold text-[#44526B] ${className}`}
    >
      Not assessed
    </span>
  )
}

function AnswerCard({ sessionId, answer }) {
  const tone = scoreTone(answer.score)
  return (
    <div className="grid grid-cols-[54px_minmax(0,1fr)_56px] items-start gap-3.5 rounded-[14px] border border-[#E8EEF8] bg-white px-4 py-3.5">
      <span className="font-display text-[15px] font-extrabold text-[#6B7890]">
        {answer.pair_id}
      </span>
      <span className="flex min-w-0 flex-col gap-1.5">
        <span className="text-sm font-semibold text-navy">{answer.question}</span>
        {answer.quote && <span className="text-sm leading-normal text-navy">“{answer.quote}”</span>}
        {answer.reason && <span className="text-[13px]">{answer.reason}</span>}
        <Link
          to={`/app/interviews/${sessionId}/transcript${
            answer.turn_id != null ? `?turn=${answer.turn_id}` : ''
          }`}
          className="self-start text-[13px] font-semibold text-brand hover:text-brand-dark"
        >
          {fromStart(answer.start_ms)} · Open in transcript →
        </Link>
      </span>
      <span
        className={`justify-self-end rounded-[10px] px-2.5 py-1 text-center font-display text-[15px] font-extrabold tabular-nums ${tone.chip}`}
      >
        {roundScore(answer.score)}
      </span>
    </div>
  )
}

function RequirementLine({ entry }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[14px] border border-[#E8EEF8] bg-white px-4 py-3">
      <span className="flex min-w-0 flex-col gap-0.5">
        <span className="text-sm font-semibold text-navy">
          {entry.requirement_id} {entry.text}
        </span>
        <span className="text-[13px]">
          {PRIORITIES[entry.priority]}
          {entry.priority === 'must_have' ? ' · counts double' : ''}
        </span>
      </span>
      <span className="flex items-center gap-2.5 text-[13px]">
        <span>{COVERAGE_LABELS[entry.status] ?? entry.status}</span>
        <span
          className={`min-w-11 rounded-[10px] px-2.5 py-1 text-center font-display text-[15px] font-extrabold tabular-nums ${
            scoreTone(entry.average).chip
          }`}
        >
          {roundScore(entry.average)}
        </span>
      </span>
    </div>
  )
}

function Evidence({ sessionId, item }) {
  return (
    <div className="flex flex-col gap-2.5 px-6 pb-5">
      <p className="text-[13.5px]">{howMade(item)}</p>
      {item.key === 'alignment' ? (
        <>
          {item.requirements.map((entry) => (
            <RequirementLine key={entry.requirement_id} entry={entry} />
          ))}
          {item.not_explored.length > 0 && (
            <span className="flex flex-wrap items-center gap-1.5 text-[13px]">
              <span>Not explored:</span>
              {item.not_explored.map((id) => (
                <span
                  key={id}
                  className="rounded-lg bg-amber-soft px-2 py-0.5 font-semibold text-amber"
                >
                  {id}
                </span>
              ))}
            </span>
          )}
        </>
      ) : (
        item.answers.map((answer) => (
          <AnswerCard key={answer.pair_id} sessionId={sessionId} answer={answer} />
        ))
      )}
    </div>
  )
}

function DimensionRow({ sessionId, item, isOpen, onToggle }) {
  if (item.score == null) {
    return (
      <div className="grid min-h-16 grid-cols-[minmax(0,1.25fr)_minmax(0,1.4fr)] items-center gap-4.5 border-b border-[#EEF2F9] bg-[#FBFCFF] px-6 py-3 last:border-b-0">
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="text-[15px] font-semibold text-navy">{item.name}</span>
          <span className="text-[13px]">{item.based_on} Left out of the interview score.</span>
        </span>
        <NotAssessed className="justify-self-start" />
      </div>
    )
  }
  const panelId = `dimension-${item.key}`
  return (
    <div className={`border-b border-[#EEF2F9] last:border-b-0 ${isOpen ? 'bg-[#FBFCFF]' : ''}`}>
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
        className="grid min-h-16 w-full grid-cols-[minmax(0,1.25fr)_minmax(0,1.4fr)_48px_20px] items-center gap-4.5 px-6 py-3 text-left"
      >
        <span className="flex min-w-0 flex-col gap-0.5">
          <span
            className={`text-[15px] ${isOpen ? 'font-bold text-brand' : 'font-semibold text-navy'}`}
          >
            {item.name}
          </span>
          <span className="text-[13px]">{item.based_on}</span>
        </span>
        <Bar score={item.score} />
        <span className="text-right font-display text-lg font-extrabold tabular-nums text-navy">
          {roundScore(item.score)}
        </span>
        {isOpen ? (
          <ChevronUp className="size-4.5 text-brand" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-4.5 text-body" aria-hidden="true" />
        )}
      </button>
      {isOpen && (
        <div id={panelId}>
          <Evidence sessionId={sessionId} item={item} />
        </div>
      )}
    </div>
  )
}

// The interview performance score (F9) on the Report tab: six dimensions,
// each opening to the answers or requirements it rests on. An interview
// evaluated before F9 has no breakdown and can be evaluated again.
export default function InterviewPerformance({ assessment, onEvaluateAgain }) {
  const [open, setOpen] = useState(null)
  const dims = assessment.interview_dimensions

  if (!dims) {
    return (
      <section
        aria-label="Interview performance"
        className={`${CARD} flex flex-col gap-3 px-6 py-5`}
      >
        <h2 className={HEADING}>Interview performance</h2>
        <div className="flex items-start gap-3 rounded-[14px] border border-[#EEF2F9] bg-[#F8FAFE] px-4 py-3.5">
          <BarChart3 className="mt-0.5 size-5 shrink-0 text-brand" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <span className="text-[15px] font-bold text-navy">Breakdown not available</span>
            <span className="text-[13.5px] leading-normal">
              This interview was evaluated before the six dimensions existed. Its interview score is
              still the average of the answers. Evaluate again to see the breakdown; the report goes
              back to draft.
            </span>
          </div>
        </div>
        {onEvaluateAgain && (
          <div>
            <Button variant="soft" onClick={onEvaluateAgain}>
              <RotateCcw className="size-4.5" aria-hidden="true" />
              Evaluate again
            </Button>
          </div>
        )}
      </section>
    )
  }

  const notEnough = dims.score == null
  const shown = notEnough ? dims.dimensions.filter((item) => item.score != null) : dims.dimensions
  const missing = dims.dimensions.filter((item) => item.score == null)

  return (
    <section aria-label="Interview performance" className={`${CARD} overflow-hidden`}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#EEF2F9] px-6 pt-5 pb-4">
        <div className="flex flex-col gap-1">
          <h2 className={HEADING}>Interview performance</h2>
          <span className="text-[13.5px]">
            Six dimensions, each from 0 to 100. Open one to see the answers behind it.
          </span>
        </div>
        <div className="flex flex-col items-end gap-0.5">
          <span
            className={`font-display text-[28px] font-extrabold tabular-nums ${
              notEnough ? 'text-[#9AA6BA]' : 'text-navy'
            }`}
          >
            {notEnough ? '–' : oneDecimal(dims.score)}
          </span>
          <span className="text-[13px]">
            {dims.assessed} of {dims.total} assessed
            {notEnough ? '' : ' · each counts equally'}
          </span>
        </div>
      </div>
      {notEnough && (
        <p className="mx-6 mt-3.5 mb-1 flex items-start gap-2.5 rounded-[14px] border border-[#F3D9A8] bg-[#FFFBF3] px-3.5 py-3 text-[13.5px] leading-normal text-[#6B3A00]">
          <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>Not enough interview evidence.</strong> At least {dims.min_assessed} of the{' '}
            {dims.total} dimensions are needed for an interview score, so there is no interview
            score and no overall score.
          </span>
        </p>
      )}
      {shown.map((item) => (
        <DimensionRow
          key={item.key}
          sessionId={assessment.session_id}
          item={item}
          isOpen={open === item.key}
          onToggle={() => setOpen((current) => (current === item.key ? null : item.key))}
        />
      ))}
      {notEnough && missing.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 px-6 pt-3 pb-4.5">
          <span className="text-[13.5px]">Not assessed:</span>
          {missing.map((item) => (
            <span
              key={item.key}
              className="rounded-full border border-dashed border-[#B8C3D6] px-2.5 py-0.5 text-[12.5px] font-semibold text-[#44526B]"
            >
              {item.name}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}

// The six dimensions as small bars, for the opened row of the Assessments
// list.
export function DimensionBars({ dimensions }) {
  return (
    <div className="flex flex-col gap-1.5 border-t border-[#E8EEF8] pt-2.5">
      <span className="text-[12.5px] font-semibold text-[#44526B]">
        Interview · {dimensions.assessed} of {dimensions.total} dimensions
      </span>
      {dimensions.dimensions.map((item) => (
        <span
          key={item.key}
          className="grid grid-cols-[112px_minmax(0,1fr)_28px] items-center gap-2.5 text-[13px]"
        >
          <span>{DIMENSION_SHORT[item.key]}</span>
          {item.score == null ? (
            <span className="col-span-2 text-[12.5px] text-[#6B7890]">Not assessed</span>
          ) : (
            <>
              <Bar score={item.score} height="h-1.5" />
              <strong className="text-right tabular-nums text-navy">
                {roundScore(item.score)}
              </strong>
            </>
          )}
        </span>
      ))}
    </div>
  )
}
