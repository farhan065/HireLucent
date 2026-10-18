import { Bot, ChevronDown, ChevronUp, CircleAlert, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router'
import {
  CRITERIA,
  KINDS,
  NOT_ANSWERED,
  SOURCES,
  roundScore,
  scoreTone,
} from '../../lib/assessment.js'
import { fromStart } from '../../lib/room.js'

const LABEL = 'text-xs font-semibold uppercase tracking-wider text-[#6B7890]'

function Chip({ className, children }) {
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${className}`}>
      {children}
    </span>
  )
}

// A turn's text with the evidence quote marked, when it can be found as
// written. Upper and lower case do not matter.
function Marked({ text, quote }) {
  const at = quote ? text.toLowerCase().indexOf(quote.toLowerCase()) : -1
  if (at < 0) return text
  return (
    <>
      {text.slice(0, at)}
      <mark className="rounded bg-success-soft px-0.5 text-navy">
        {text.slice(at, at + quote.length)}
      </mark>
      {text.slice(at + quote.length)}
    </>
  )
}

function TurnLine({ sessionId, turn, quote }) {
  return (
    <div className="grid grid-cols-[52px_minmax(0,1fr)] items-baseline gap-2.5">
      <Link
        to={`/app/interviews/${sessionId}/transcript?turn=${turn.id}`}
        title={`Open the transcript at ${fromStart(turn.start_ms)}`}
        className="text-[13px] font-semibold tabular-nums text-brand hover:text-brand-dark"
      >
        {fromStart(turn.start_ms)}
      </Link>
      <p className="text-[14.5px] leading-relaxed text-navy">
        <Marked text={turn.text} quote={quote} />
      </p>
    </div>
  )
}

function CriterionBox({ name, criterion }) {
  const tone = scoreTone(criterion.score)
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] px-3.5 py-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-navy">{name}</span>
        <span className="font-display text-base font-extrabold tabular-nums text-navy">
          {criterion.score}
        </span>
      </div>
      <span aria-hidden="true" className="h-1.5 overflow-hidden rounded-full bg-[#E4EAF4]">
        <span
          className={`block h-full rounded-full ${tone.bar}`}
          style={{ width: `${criterion.score}%` }}
        />
      </span>
      <span className="text-[13.5px] leading-relaxed">{criterion.reason}</span>
    </div>
  )
}

// Where the accuracy judgement came from, in words, with the passage when a
// reference was used.
function AccuracySource({ source, kind }) {
  if (source.type === 'reference') {
    return (
      <div className="flex flex-col gap-2 rounded-2xl border border-[#BFE6D3] bg-[#F2FBF7] px-4 py-3.5">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <span className="inline-flex items-center gap-2 text-sm font-bold text-success">
            <ShieldCheck className="size-4.5" aria-hidden="true" />
            Accuracy verified against {source.source}
          </span>
          {source.similarity != null && (
            <span className="text-[12.5px] tabular-nums">
              Similarity {source.similarity.toFixed(2)}
            </span>
          )}
        </div>
        <blockquote className="border-l-[3px] border-[#8FD3B4] pl-3 text-[13.5px] leading-relaxed text-navy">
          {source.passage}
        </blockquote>
      </div>
    )
  }
  if (source.type === 'not_checked') {
    return (
      <p className="flex items-start gap-2 rounded-2xl border border-[#F3D9A8] bg-[#FFF9EE] px-3.5 py-3 text-[13.5px] leading-relaxed text-[#6B3A00]">
        <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
        {kind === 'company' ? (
          <span>
            <strong>Accuracy not checked.</strong> No company reference covers this, and the AI does
            not guess company facts. The score uses relevance, completeness and articulation only.
            Upload the policy as a Reference to check it next time.
          </span>
        ) : (
          <span>
            <strong>Accuracy not checked.</strong> The AI could not judge the accuracy of this
            answer. The score uses relevance, completeness and articulation only.
          </span>
        )}
      </p>
    )
  }
  return (
    <p className="flex items-start gap-2 rounded-2xl border border-[#E1E6EF] bg-[#F4F6FA] px-3.5 py-3 text-[13.5px] leading-relaxed text-[#2F3B52]">
      <Bot className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
      <span>
        <strong>Judged by the AI interviewer.</strong> No reference document covers this, so
        accuracy comes from the AI&apos;s own technical knowledge.
      </span>
    </p>
  )
}

function Details({ sessionId, pair, turns }) {
  const evaluation = pair.evaluation
  const quote = evaluation?.evidence?.quote
  const answerTurns = pair.answer_turn_ids.map((id) => turns.get(id)).filter(Boolean)
  const askedTurns = pair.question_turn_ids.map((id) => turns.get(id)).filter(Boolean)

  if (!evaluation) {
    return (
      <div className="flex flex-col gap-2.5 pt-4.5 pr-4.5 pb-5 pl-[72px]">
        {[...askedTurns, ...answerTurns].map((turn) => (
          <TurnLine key={turn.id} sessionId={sessionId} turn={turn} />
        ))}
        <p className="text-[13.5px]">Small talk is kept in the transcript but not evaluated.</p>
      </div>
    )
  }

  const answeredLabel = {
    answered: 'answered',
    partly_answered: 'partly answered',
    not_answered: 'not answered',
  }[evaluation.answered]

  return (
    <div className="flex flex-col gap-4.5 pt-4.5 pr-4.5 pb-5 pl-[72px]">
      <div className="flex flex-col gap-2">
        <span className={LABEL}>Candidate&apos;s answer · {answeredLabel}</span>
        {answerTurns.length === 0 ? (
          <p className="text-[14.5px] text-navy">No answer given.</p>
        ) : (
          answerTurns.map((turn) => (
            <TurnLine
              key={turn.id}
              sessionId={sessionId}
              turn={turn}
              quote={evaluation.evidence?.turn_id === turn.id ? quote : null}
            />
          ))
        )}
      </div>

      {evaluation.criteria && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {CRITERIA.map(([key, name]) =>
            evaluation.criteria[key] ? (
              <CriterionBox key={key} name={name} criterion={evaluation.criteria[key]} />
            ) : null,
          )}
        </div>
      )}

      <div className="flex flex-col gap-1.5">
        <span className={LABEL}>Justification</span>
        <p className="text-[14.5px] leading-relaxed text-navy">{evaluation.justification}</p>
        {evaluation.evidence && (
          <span className="text-[13.5px]">
            Evidence: “{evaluation.evidence.quote}” at{' '}
            <Link
              to={`/app/interviews/${sessionId}/transcript?turn=${evaluation.evidence.turn_id}`}
              className="font-semibold text-brand hover:text-brand-dark"
            >
              {fromStart(evaluation.evidence.start_ms)}
            </Link>
          </span>
        )}
      </div>

      {evaluation.accuracy_source && (
        <AccuracySource source={evaluation.accuracy_source} kind={pair.kind} />
      )}
    </div>
  )
}

// One question and its answer. Closed, it shows the question, its kind,
// the requirements it explores, where accuracy came from and the score;
// open, the answer with its evidence and the four criteria.
export default function QuestionCard({
  sessionId,
  pair,
  turns,
  requirementNames,
  isOpen,
  onToggle,
}) {
  const kind = KINDS[pair.kind] ?? KINDS.technical
  const evaluation = pair.evaluation
  const isSmallTalk = !evaluation
  const score = roundScore(evaluation?.score)
  const tone = scoreTone(isSmallTalk ? null : score)
  const notAnswered = evaluation?.answered === 'not_answered'
  const source = notAnswered ? NOT_ANSWERED : SOURCES[evaluation?.accuracy_source?.type]
  const panelId = `pair-${pair.id}`
  // Only an evaluated question is shown under the one it follows up. Small
  // talk always stays in line.
  const followUpOf = isSmallTalk ? null : pair.follow_up_of

  return (
    <article
      className={`rounded-[18px] border ${
        isOpen ? 'border-[1.5px] border-[#A9C8FF] bg-white shadow-card' : 'border-line'
      } ${isSmallTalk && !isOpen ? 'bg-[#FBFCFE]' : 'bg-white'} ${followUpOf ? 'ml-10' : ''}`}
    >
      <button
        type="button"
        aria-expanded={isOpen}
        aria-controls={panelId}
        onClick={onToggle}
        className={`grid min-h-16 w-full grid-cols-[40px_minmax(0,1fr)_auto_auto] items-center gap-3.5 px-4.5 py-3.5 text-left ${
          isOpen ? 'border-b border-[#EEF2F9]' : ''
        }`}
      >
        <span
          className={`font-display text-[15px] font-extrabold ${isOpen ? 'text-brand' : 'text-[#6B7890]'}`}
        >
          {pair.id}
        </span>
        <span className="flex min-w-0 flex-col gap-1.5">
          <span
            className={`text-[15.5px] font-semibold ${isSmallTalk ? 'text-body' : 'text-navy'}`}
          >
            {pair.question}
          </span>
          <span className="flex flex-wrap items-center gap-1.5 text-[12.5px]">
            <Chip className={kind.className}>{kind.label}</Chip>
            {followUpOf && (
              <Chip className="bg-mist text-[#44526B]">Follow-up of {followUpOf}</Chip>
            )}
            {pair.requirement_ids.map((id) => (
              <span key={id} className="rounded-md border border-line px-2 py-0.5 text-navy">
                {requirementNames[id] ?? id}
              </span>
            ))}
            {source && <Chip className={source.className}>{source.label}</Chip>}
            <span className="tabular-nums">{fromStart(pair.start_ms)}</span>
          </span>
        </span>
        <span
          className={`min-w-14 rounded-xl px-2.5 py-1.5 text-center font-display font-extrabold tabular-nums ${tone.chip} ${
            isSmallTalk ? 'text-[12.5px]' : 'text-lg'
          }`}
        >
          {isSmallTalk ? 'Not scored' : score}
        </span>
        {isOpen ? (
          <ChevronUp className="size-4.5 text-body" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-4.5 text-body" aria-hidden="true" />
        )}
      </button>
      {isOpen && (
        <div id={panelId}>
          <Details sessionId={sessionId} pair={pair} turns={turns} />
        </div>
      )}
    </article>
  )
}
