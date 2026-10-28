import {
  CircleAlert,
  ClipboardCheck,
  Clock,
  LoaderCircle,
  MessageSquare,
  Mic,
  RotateCcw,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import {
  QUALITY_LABELS,
  clockTime,
  consistencyOf,
  lengthOf,
  minutesSeconds,
  oneDecimal,
  qualityBar,
  readConsistency,
  roundScore,
} from '../../lib/assessment.js'
import Button from '../Button.jsx'

const CARD = 'rounded-[20px] border border-line bg-white'
const HEADING = 'font-display text-lg font-extrabold text-navy'
const LABEL = 'text-xs font-bold uppercase tracking-[0.06em] text-[#6B7890]'
const BUSY_TITLE = 'Another evaluation is running. Wait for it to finish.'
const STRETCH_MAX_MS = 120_000
const SMALL_TALK_MAX = 20

// The icon of a recommendation, from the kind of finding it rests on.
const REQUIREMENT_KINDS = ['not_explored', 'weak', 'no_technical', 'no_job_questions']
const QUESTION_KINDS = ['little_signal', 'not_linked']
const SPEAKING_KINDS = ['speaking_share', 'long_stretch']

function iconOf(kinds) {
  if (kinds.some((kind) => REQUIREMENT_KINDS.includes(kind))) return [CircleAlert, true]
  if (kinds.some((kind) => QUESTION_KINDS.includes(kind))) return [MessageSquare, false]
  if (kinds.some((kind) => SPEAKING_KINDS.includes(kind))) return [Mic, false]
  return [Clock, false]
}

function Bar({ score }) {
  return (
    <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-[#E4EAF4]">
      <span
        className={`block h-full rounded-full ${qualityBar(score)}`}
        style={{ width: `${score ?? 0}%` }}
      />
    </span>
  )
}

// A question or requirement chip opens it on its own tab.
function IdChip({ id, isWarning, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-2 py-0.5 text-[12.5px] font-bold ${
        isWarning
          ? 'bg-amber-soft text-amber hover:bg-[#FFE9C7]'
          : 'bg-tint text-brand-dark hover:bg-lavender'
      }`}
    >
      {id}
    </button>
  )
}

function LinkButton({ onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="font-semibold text-brand hover:text-brand-dark"
    >
      {children}
    </button>
  )
}

function PartRow({ name, score, children }) {
  return (
    <div className="grid grid-cols-[112px_minmax(0,1fr)_40px] items-start gap-3.5">
      <span className="text-[15px] font-semibold text-navy">{name}</span>
      <span className="flex min-w-0 flex-col gap-1.5 pt-1.5">
        <Bar score={score} />
        <span className="flex flex-wrap items-center gap-1.5 text-[13px]">{children}</span>
      </span>
      <span className="text-right font-display text-lg font-extrabold tabular-nums text-navy">
        {score == null ? '–' : roundScore(score)}
      </span>
    </div>
  )
}

function ScoreCard({ quality, onPickQuestion, onOpenCoverage }) {
  const { questions, coverage, interaction } = quality.parts
  const label = QUALITY_LABELS[quality.label]
  const flagged = [...questions.little_signal, ...questions.not_linked]
    .map((item) => item.id)
    .sort((a, b) => Number(a.slice(1)) - Number(b.slice(1)))
  const metrics = quality.metrics
  return (
    <section
      aria-label="Quality score"
      className={`${CARD} flex flex-wrap items-center gap-7 p-5.5 shadow-card`}
    >
      <div className="flex w-52 flex-col gap-2">
        <span className={LABEL}>Interview quality</span>
        <span className="flex items-baseline gap-1.5">
          <span className="font-display text-[44px] leading-none font-extrabold tabular-nums text-navy">
            {quality.score == null ? '–' : oneDecimal(quality.score)}
          </span>
          <span className="text-[15px]">/ 100</span>
        </span>
        {label && (
          <span
            className={`self-start rounded-full px-3 py-1 text-[13px] font-bold ${label.className}`}
          >
            {label.label}
          </span>
        )}
      </div>
      <div className="flex min-w-0 flex-[999_1_380px] flex-col gap-4">
        <PartRow name="Questions" score={questions.score}>
          {questions.total === 0 ? (
            <span>No job-related questions were asked.</span>
          ) : (
            <span>
              {questions.useful} of {questions.total} job-related questions gave a useful answer.
            </span>
          )}
          {flagged.length > 0 && <span>Little evidence:</span>}
          {flagged.map((id) => (
            <IdChip key={id} id={id} onClick={() => onPickQuestion(id)} />
          ))}
          {questions.total > 0 && (
            <LinkButton onClick={() => onPickQuestion(null)}>See in Q&amp;A analysis →</LinkButton>
          )}
        </PartRow>
        <PartRow name="Coverage" score={coverage?.score ?? null}>
          {coverage ? (
            <>
              <span>
                {coverage.explored} of {coverage.total} requirements explored
                {coverage.weak.length > 0 && `, ${coverage.weak.length} only weakly`}.
              </span>
              {coverage.missing.length > 0 && <span>Missing:</span>}
              {coverage.missing.map((id) => (
                <IdChip key={id} id={id} isWarning onClick={onOpenCoverage} />
              ))}
              {coverage.weak.length > 0 && <span>Weak:</span>}
              {coverage.weak.map((id) => (
                <IdChip key={id} id={id} isWarning onClick={onOpenCoverage} />
              ))}
              <LinkButton onClick={onOpenCoverage}>See requirement coverage →</LinkButton>
            </>
          ) : (
            <span>The job has no requirements to explore.</span>
          )}
        </PartRow>
        <PartRow name="Interaction" score={interaction?.score ?? null}>
          {interaction ? (
            <span>
              Candidate spoke {metrics.candidate_share}%
              {metrics.longest_stretch &&
                ` · longest interviewer stretch ${lengthOf(metrics.longest_stretch.ms)}`}
            </span>
          ) : (
            <span>No speaking time was recorded.</span>
          )}
        </PartRow>
      </div>
    </section>
  )
}

function RefChip({ item, onPickQuestion, onOpenCoverage }) {
  const isRequirement = item.type === 'requirement'
  const className = `rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${
    isRequirement
      ? 'bg-amber-soft text-amber hover:bg-[#FFE9C7]'
      : item.type === 'question'
        ? 'bg-tint text-brand-dark hover:bg-lavender'
        : 'bg-[#EEF1F6] text-[#44526B]'
  }`
  if (item.type === 'question') {
    return (
      <button type="button" className={className} onClick={() => onPickQuestion(item.id)}>
        {item.label}
      </button>
    )
  }
  if (isRequirement) {
    return (
      <button type="button" className={className} onClick={onOpenCoverage}>
        {item.label}
      </button>
    )
  }
  return <span className={className}>{item.label}</span>
}

function Recommendations({ quality, state, isBusy, onCheck, onPickQuestion, onOpenCoverage }) {
  const { status, items } = quality.recommendations
  return (
    <section aria-label="Recommendations" className={`${CARD} overflow-hidden`}>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#EEF2F9] px-6 pt-5 pb-3.5">
        <div className="flex flex-col gap-1">
          <h2 className={HEADING}>Recommendations for the next interview</h2>
          {status === 'written' && (
            <span className="text-[13.5px]">
              Written by the AI from the findings. Every question, requirement and number it names
              was checked.
            </span>
          )}
        </div>
        {status === 'written' && (
          <span className="rounded-full bg-tint px-2.5 py-0.5 text-[12.5px] font-bold text-brand-dark">
            {items.length}
          </span>
        )}
      </div>

      {status === 'none_needed' && (
        <p className="px-6 py-5 text-[14.5px] leading-relaxed">
          Nothing to improve was found. The questions explored the job's requirements, gave useful
          answers, and the speaking time was balanced.
        </p>
      )}

      {status === 'not_written' && (
        <div className="mx-6 my-5 flex flex-wrap items-center justify-between gap-4 rounded-[14px] border border-[#F3D9A8] bg-[#FFFBF3] px-4.5 py-4">
          <span className="flex max-w-md gap-3 text-[#6B3A00]">
            <TriangleAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <span className="flex flex-col gap-1">
              <strong className="text-[14.5px] text-navy">
                Recommendations could not be written
              </strong>
              <span className="text-[13.5px] leading-normal text-body">
                {quality.recommendations.reason === 'ai_unavailable'
                  ? 'The AI service was not available. '
                  : 'None could be checked against the findings. '}
                The score, questions, coverage and interaction are complete.
              </span>
              {state.state === 'quality_failed' && (
                <span role="alert" className="text-[13px] font-semibold text-danger">
                  {state.reason}
                </span>
              )}
            </span>
          </span>
          <Button
            variant="outline"
            disabled={isBusy}
            title={isBusy ? BUSY_TITLE : undefined}
            onClick={onCheck}
          >
            <RotateCcw className="size-4" aria-hidden="true" />
            Check again
          </Button>
        </div>
      )}

      {status === 'written' &&
        items.map((item, index) => {
          const [Icon, isWarning] = iconOf(item.kinds)
          return (
            <div
              key={item.id}
              className={`grid grid-cols-[36px_minmax(0,1fr)] gap-3.5 px-6 py-4.5 ${
                index < items.length - 1 ? 'border-b border-[#EEF2F9]' : ''
              }`}
            >
              <span
                aria-hidden="true"
                className={`flex size-9 items-center justify-center rounded-xl ${
                  isWarning ? 'bg-amber-soft text-amber' : 'bg-tint text-brand-dark'
                }`}
              >
                <Icon className="size-4.5" />
              </span>
              <div className="flex min-w-0 flex-col gap-2">
                <p className="text-[15px] font-semibold leading-snug text-navy">{item.text}</p>
                {item.example_question && (
                  <p className="rounded-xl bg-[#F4F8FF] px-3.5 py-2.5 text-sm text-navy">
                    For example: “{item.example_question}”
                  </p>
                )}
                {item.refs.length > 0 && (
                  <span className="flex flex-wrap gap-1.5">
                    {item.refs.map((ref) => (
                      <RefChip
                        key={`${ref.type}-${ref.id ?? ''}-${ref.label}`}
                        item={ref}
                        onPickQuestion={onPickQuestion}
                        onOpenCoverage={onOpenCoverage}
                      />
                    ))}
                  </span>
                )}
              </div>
            </div>
          )
        })}
    </section>
  )
}

function Tile({ label, value, note, isWarning }) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-[14px] border px-4 py-3.5 ${
        isWarning ? 'border-[#F3D9A8] bg-[#FFFBF3]' : 'border-[#E8EEF8]'
      }`}
    >
      <span
        className={`text-xs font-bold uppercase tracking-[0.06em] ${
          isWarning ? 'text-amber' : 'text-[#6B7890]'
        }`}
      >
        {label}
      </span>
      <span className="font-display text-xl font-extrabold tabular-nums text-navy">{value}</span>
      <span className="text-[13px]">{note}</span>
    </div>
  )
}

// Who spoke when: one lane per speaker, the interviewer's longest stretch
// marked in amber when it ran over two minutes. Each bar opens the
// transcript at that moment.
function Timeline({ sessionId, metrics }) {
  const end = Math.max(
    metrics.actual_ms ?? 0,
    ...metrics.segments.map((segment) => segment.end_ms),
    1,
  )
  const stretch = metrics.longest_stretch
  const isLong = stretch && stretch.ms > STRETCH_MAX_MS
  const lanes = [
    ['interviewer', 'You'],
    ['candidate', 'Candidate'],
  ]
  const marks = [0, 0.25, 0.5, 0.75, 1].map((share) => clockTime(end * share))
  return (
    <div className="flex flex-col gap-2">
      <span className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="text-[13px] font-semibold text-[#44526B]">Who spoke when</span>
        <span className="text-xs text-[#6B7890]">Click a bar to open the transcript there</span>
      </span>
      <div className="grid grid-cols-[82px_minmax(0,1fr)] items-center gap-2.5 text-[13px]">
        {lanes.map(([speaker, name]) => (
          <div key={speaker} className="contents">
            <span>{name}</span>
            <div className="relative h-4 rounded-md bg-[#F4F8FF]">
              {metrics.segments
                .filter((segment) => segment.speaker === speaker)
                .map((segment) => {
                  const inStretch =
                    isLong &&
                    speaker === 'interviewer' &&
                    segment.start_ms >= stretch.start_ms &&
                    segment.end_ms <= stretch.start_ms + stretch.ms
                  const label = `${name} · ${clockTime(segment.start_ms)}–${clockTime(
                    segment.end_ms,
                  )} (${lengthOf(segment.end_ms - segment.start_ms)}) · Open in transcript`
                  return (
                    <Link
                      key={segment.start_ms}
                      to={`/app/interviews/${sessionId}/transcript${
                        segment.turn_id != null ? `?turn=${segment.turn_id}` : ''
                      }`}
                      aria-label={label}
                      title={label}
                      className={`absolute inset-y-0 min-w-1 rounded transition-[filter] hover:brightness-90 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand ${
                        inStretch
                          ? 'bg-[#D97706]'
                          : speaker === 'interviewer'
                            ? 'bg-[#9DB8F0]'
                            : 'bg-brand'
                      }`}
                      style={{
                        left: `${(100 * segment.start_ms) / end}%`,
                        width: `${Math.max((100 * (segment.end_ms - segment.start_ms)) / end, 0.4)}%`,
                      }}
                    />
                  )
                })}
            </div>
          </div>
        ))}
        <span />
        <div className="flex justify-between text-xs text-[#6B7890] tabular-nums">
          {marks.map((mark, index) => (
            <span key={index}>{mark}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Interaction({ sessionId, quality }) {
  const metrics = quality.metrics
  if (metrics.candidate_share == null) {
    return (
      <section aria-label="Interaction" className={`${CARD} p-6`}>
        <h2 className={HEADING}>Interaction</h2>
        <p className="mt-2 text-sm">No speaking time was recorded for this interview.</p>
      </section>
    )
  }
  const interviewer = Math.round((100 - metrics.candidate_share) * 10) / 10
  const stretch = metrics.longest_stretch
  const followUps = metrics.follow_ups
  const isShort =
    metrics.planned_ms && metrics.actual_ms && metrics.actual_ms < metrics.planned_ms / 2
  return (
    <section aria-label="Interaction" className={`${CARD} flex flex-col gap-4.5 px-6 pt-5 pb-5.5`}>
      <div className="flex flex-col gap-1">
        <h2 className={HEADING}>Interaction</h2>
        <span className="text-[13.5px]">Measured from the transcript times of each speaker.</span>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap justify-between gap-3 text-sm">
          <span>
            <strong className="text-navy">You</strong> {interviewer}% ·{' '}
            {minutesSeconds(metrics.interviewer_ms)}
          </span>
          <span>
            <strong className="text-navy">Candidate</strong> {metrics.candidate_share}% ·{' '}
            {minutesSeconds(metrics.candidate_ms)}
          </span>
        </div>
        <div aria-hidden="true" className="flex h-4.5 overflow-hidden rounded-full">
          <span className="bg-[#9DB8F0]" style={{ width: `${interviewer}%` }} />
          <span className="bg-brand" style={{ width: `${metrics.candidate_share}%` }} />
        </div>
        <div className="relative h-6 text-[12.5px]">
          <span
            aria-hidden="true"
            className="absolute top-0 h-1.5 rounded-full bg-success"
            style={{ left: '30%', width: '10%' }}
          />
          <span className="absolute top-2.5" style={{ left: '24%' }}>
            Balanced: candidate speaks 60–70%
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Longest stretch"
          value={stretch ? lengthOf(stretch.ms) : '–'}
          note={
            stretch
              ? `You, at ${clockTime(stretch.start_ms)}${stretch.ms > STRETCH_MAX_MS ? ' · over 2 min' : ''}`
              : 'No interviewer speech'
          }
          isWarning={stretch && stretch.ms > STRETCH_MAX_MS}
        />
        <Tile
          label="Small talk"
          value={`${metrics.small_talk_share ?? 0}%`}
          note={`${minutesSeconds(metrics.small_talk_ms)} · ${metrics.small_talk_questions} ${
            metrics.small_talk_questions === 1 ? 'question' : 'questions'
          }`}
          isWarning={(metrics.small_talk_share ?? 0) > SMALL_TALK_MAX}
        />
        <Tile
          label="Follow-ups"
          value={followUps.length}
          note={followUps.length ? `after ${[...new Set(followUps)].join(', ')}` : 'none asked'}
        />
        <Tile
          label="Length"
          value={metrics.actual_minutes != null ? `${metrics.actual_minutes} min` : '–'}
          note={
            metrics.planned_minutes != null
              ? `of ${metrics.planned_minutes} min planned`
              : 'no planned length'
          }
          isWarning={isShort}
        />
      </div>

      {metrics.segments.length > 0 && <Timeline sessionId={sessionId} metrics={metrics} />}
    </section>
  )
}

function InLine({ label, value, isOff }) {
  return (
    <div
      className={`flex flex-col gap-0.5 rounded-xl px-3.5 py-3 text-[13.5px] ${
        isOff ? 'border border-[#F3D9A8] bg-[#FFFBF3]' : 'bg-[#F4F8FF]'
      }`}
    >
      <span className="font-semibold text-navy">
        {label} · {isOff ? 'differs' : 'in line'}
      </span>
      <span>{value}</span>
    </div>
  )
}

// This interview against the job's other checked interviews.
function Comparison({ jobId, sessionId, requirements, consistency, error }) {
  const row = consistencyOf(consistency, sessionId)
  const others = (consistency?.count ?? 1) - 1
  const typical = consistency?.typical
  const kinds = new Set((row?.flags ?? []).map((flag) => flag.kind))
  const requirementFlags = (row?.flags ?? []).filter((flag) => flag.kind === 'must_have_not_asked')
  const names = new Map(requirements.map((item) => [item.id, item.text]))
  return (
    <section
      aria-label="Consistency with other interviews"
      className={`${CARD} flex flex-col gap-3.5 px-6 pt-5 pb-5.5`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <h2 className={HEADING}>Compared with this job's other interviews</h2>
          {row && (
            <span className="text-[13.5px]">
              {others} other evaluated {others === 1 ? 'interview' : 'interviews'} for this job
            </span>
          )}
        </div>
        {row && (
          <Link
            to={`/app/jobs/${jobId}/assessments?view=consistency`}
            className="text-sm font-semibold text-brand hover:text-brand-dark"
          >
            See all interviews of this job →
          </Link>
        )}
      </div>
      {error ? (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      ) : !consistency ? (
        <p className="text-sm">Loading…</p>
      ) : !row ? (
        <p className="text-sm">No other interview of this job is evaluated yet.</p>
      ) : (
        <>
          {requirementFlags.map((flag) => (
            <div
              key={flag.requirement_id}
              className="flex items-start gap-3 rounded-[14px] border border-[#F3D9A8] bg-[#FFFBF3] px-4 py-3.5"
            >
              <span
                aria-hidden="true"
                className="mt-1.5 size-2.5 shrink-0 rounded-full bg-[#D97706]"
              />
              <span className="flex flex-col gap-0.5 text-sm">
                <strong className="text-navy">
                  {flag.requirement_id} {names.get(flag.requirement_id) ?? ''} was not asked here
                </strong>
                <span>
                  It was asked in {flag.asked} of the {flag.others} other interviews.
                </span>
              </span>
            </div>
          ))}
          <div className="grid gap-3 sm:grid-cols-3">
            <InLine
              label="Length"
              isOff={kinds.has('length')}
              value={`${row.minutes ?? '–'} min · typical ${typical.minutes ?? '–'} min`}
            />
            <InLine
              label="Questions"
              isOff={kinds.has('questions')}
              value={`${row.questions} · typical ${typical.questions ?? '–'}`}
            />
            <InLine
              label="Candidate spoke"
              isOff={kinds.has('speaking_share')}
              value={`${row.candidate_share ?? '–'}% · typical ${typical.candidate_share ?? '–'}%`}
            />
          </div>
        </>
      )}
    </section>
  )
}

function HowMade({ quality }) {
  const { questions, coverage, interaction } = quality.parts
  const label = QUALITY_LABELS[quality.label]?.label
  return (
    <aside className="flex flex-[1_1_300px] flex-col gap-4 lg:max-w-[360px]">
      <section className={`${CARD} flex flex-col gap-2.5 px-5 py-4.5`}>
        <h2 className="mb-1 font-display text-base font-extrabold text-navy">
          How the quality score is made
        </h2>
        {[
          ['Questions', questions.score],
          ['Coverage', coverage?.score],
          ['Interaction', interaction?.score],
        ].map(([name, score]) => (
          <div key={name} className="flex justify-between gap-3 text-sm">
            <span>{name}</span>
            <strong className="text-navy">{score == null ? 'Left out' : roundScore(score)}</strong>
          </div>
        ))}
        <div className="flex justify-between gap-3 border-t border-line pt-2 text-[14.5px] font-bold text-navy">
          <span>Average</span>
          <span>
            {quality.score == null ? '–' : oneDecimal(quality.score)}
            {label && ` · ${label}`}
          </span>
        </div>
        <p className="text-[12.5px] leading-normal">
          Questions: share of job-related questions with a useful answer. Coverage: covered 1, weak
          ½, not explored 0, must-haves count double. Each part counts equally. Good 70+, Needs
          improvement 50–69, Poor below 50.
        </p>
      </section>
      {interaction && (
        <section className={`${CARD} flex flex-col gap-2 px-5 py-4.5 text-[13.5px]`}>
          <h2 className="font-display text-base font-extrabold text-navy">Interaction points</h2>
          <div className="flex justify-between gap-2.5">
            <span>Start</span>
            <span className="text-navy">100</span>
          </div>
          {interaction.penalties.map((item) => (
            <div key={item.key} className="flex justify-between gap-2.5">
              <span>{item.label}</span>
              <span className={item.points ? 'font-semibold text-amber' : ''}>
                {item.points ? `−${Math.abs(roundScore(item.points))}` : '0'}
              </span>
            </div>
          ))}
          <div className="flex justify-between gap-2.5 border-t border-line pt-2 font-bold text-navy">
            <span>Interaction</span>
            <span>{roundScore(interaction.score)}</span>
          </div>
        </section>
      )}
    </aside>
  )
}

function CheckingCard() {
  return (
    <section role="status" className={`${CARD} flex max-w-xl flex-col gap-3.5 p-5.5`}>
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-tint text-brand">
          <LoaderCircle
            className="size-5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        </span>
        <div>
          <h2 className="text-[17px] font-extrabold text-navy">Checking interview quality…</h2>
          <p className="text-[13.5px]">
            Measuring the questions, coverage and speaking time, then writing recommendations
          </p>
        </div>
      </div>
      <p className="text-[13.5px]">
        You can leave this page. The rest of the assessment can be used while this runs.
      </p>
    </section>
  )
}

// The Interview quality tab (F10): how the interview itself was run, not
// the candidate. A score from three parts with their evidence, the
// recommendations for the next interview, the speaking time, and this
// interview against the job's other interviews. An interview evaluated
// before F10 offers a run of the quality check alone; nothing else of the
// assessment is touched.
export default function QualityTab({
  assessment,
  jobId,
  state,
  isBusy,
  onCheck,
  onPickQuestion,
  onOpenCoverage,
}) {
  const quality = assessment.interview_quality
  const [consistency, setConsistency] = useState(null)
  const [consistencyError, setConsistencyError] = useState('')
  const checkedAt = quality?.checked_at

  useEffect(() => {
    if (!checkedAt) return undefined
    let isCurrent = true
    readConsistency(jobId)
      .then((loaded) => {
        if (!isCurrent) return
        setConsistency(loaded)
        setConsistencyError('')
      })
      .catch((loadError) => isCurrent && setConsistencyError(loadError.message))
    return () => {
      isCurrent = false
    }
  }, [jobId, checkedAt])

  if (state.state === 'checking_quality') return <CheckingCard />

  if (!quality) {
    return (
      <section className="flex max-w-xl flex-col items-center gap-3.5 self-center rounded-[22px] border border-line bg-white px-7 py-9 text-center shadow-card">
        <span className="flex size-13 items-center justify-center rounded-2xl bg-tint text-brand">
          <ClipboardCheck className="size-6" aria-hidden="true" />
        </span>
        <h2 className="text-lg font-extrabold text-navy">Interview quality not checked yet</h2>
        <p className="text-sm leading-relaxed">
          This interview was evaluated before interview quality checks were added. Checking it looks
          at the questions, coverage and speaking time. The report, its approval and the decision
          stay as they are.
        </p>
        <Button disabled={isBusy} title={isBusy ? BUSY_TITLE : undefined} onClick={onCheck}>
          Check interview quality
        </Button>
        {state.state === 'quality_failed' && (
          <p role="alert" className="text-sm font-semibold text-danger">
            {state.reason}
          </p>
        )}
      </section>
    )
  }

  const checked = new Date(quality.checked_at)
  return (
    <div className="flex flex-col gap-5.5">
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <span>
          How well this interview was run. It is about the interview, not the candidate, and never
          changes the candidate's scores, report or decision.
        </span>
        <span className="text-[13px] text-[#6B7890]">
          Checked{' '}
          {checked.toLocaleString(undefined, {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
            hour: 'numeric',
            minute: '2-digit',
          })}
        </span>
      </div>
      <div className="flex flex-wrap items-start gap-5.5">
        <article
          aria-label="Interview quality"
          className="flex min-w-0 flex-[999_1_560px] flex-col gap-4.5"
        >
          <ScoreCard
            quality={quality}
            onPickQuestion={onPickQuestion}
            onOpenCoverage={onOpenCoverage}
          />
          <Recommendations
            quality={quality}
            state={state}
            isBusy={isBusy}
            onCheck={onCheck}
            onPickQuestion={onPickQuestion}
            onOpenCoverage={onOpenCoverage}
          />
          <Interaction sessionId={assessment.session_id} quality={quality} />
          <Comparison
            jobId={jobId}
            sessionId={assessment.session_id}
            requirements={quality.requirements}
            consistency={consistency}
            error={consistencyError}
          />
        </article>
        <HowMade quality={quality} />
      </div>
    </div>
  )
}
