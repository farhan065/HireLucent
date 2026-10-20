import { ArrowRight, LoaderCircle, Sparkles, Trash2, Video } from 'lucide-react'
import { Link } from 'react-router'
import { REPORT_STATUS } from '../../lib/assessment.js'
import { identityShown } from '../../lib/identity.js'
import {
  dayLabel,
  formatShortDate,
  joinState,
  minutesBetween,
  opensLabel,
  scoreLabel,
  span,
  waitingFor,
} from '../../lib/interviews.js'
import StatusChip from '../StatusChip.jsx'
import IdentityChip from './IdentityChip.jsx'

const GRID =
  'grid grid-cols-[minmax(0,1.4fr)_minmax(0,1.5fr)_minmax(0,1.1fr)_minmax(0,1.6fr)] items-center gap-4 px-6'
const LINK = 'min-h-10 text-sm font-semibold'

// The identity label is shown while the interview is upcoming or running.
function isActiveRow(interview) {
  return interview.status === 'scheduled' || interview.status === 'in_progress'
}

function minutesUntil(date, now) {
  return Math.max(1, Math.ceil((new Date(date) - now) / 60000))
}

// The status chip, worked out from the stored status and the time now.
function statusOf(interview, rules, now) {
  if (interview.status === 'cancelled') return { tone: 'neutral', label: 'Cancelled' }
  if (interview.status === 'completed') return { tone: 'success', label: 'Completed' }
  if (interview.status === 'in_progress') return { tone: 'info', label: 'In progress' }
  if (interview.candidate_waiting) {
    return { tone: 'success', label: `Waiting · ${waitingFor(interview, now)}`, row: 'bg-success-soft/50' }
  }
  const state = joinState(interview, rules, now)
  if (state === 'missed') return { tone: 'danger', label: 'Missed' }
  if (state === 'open') {
    const label =
      new Date(interview.scheduled_start) > now
        ? `Starts in ${minutesUntil(interview.scheduled_start, now)} min`
        : 'Waiting to start'
    return { tone: 'amber', label, row: 'bg-amber-soft/40' }
  }
  return { tone: 'amber', label: 'Scheduled' }
}

function When({ interview, now }) {
  const { status, scheduled_start: start, scheduled_end: end } = interview
  if (status === 'cancelled') {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-[15px] text-body/70 line-through">{dayLabel(start, now)}</span>
        <span className="text-[13.5px]">Cancelled on {formatShortDate(interview.cancelled_at)}</span>
      </div>
    )
  }
  const length =
    status === 'completed' && interview.started_at && interview.ended_at
      ? `took ${minutesBetween(interview.started_at, interview.ended_at)} min`
      : `${minutesBetween(start, end)} min`
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[15px] text-navy">{dayLabel(start, now)}</span>
      <span className="text-[13.5px]">
        {span(start, end)} · {length}
      </span>
    </div>
  )
}

// Opens the interview room once Join is open; before that it says when.
function StartButton({ interview, rules, now }) {
  if (joinState(interview, rules, now) !== 'open') {
    return (
      <button
        type="button"
        disabled
        className="inline-flex min-h-10.5 cursor-not-allowed items-center whitespace-nowrap rounded-full bg-mist px-4.5 font-display text-sm font-bold text-body"
      >
        Opens {opensLabel(interview, rules, now)}
      </button>
    )
  }
  return (
    <Link
      to={`/app/interviews/${interview.id}/room`}
      className="inline-flex min-h-10.5 items-center gap-2 whitespace-nowrap rounded-full bg-brand px-4.5 font-display text-sm font-bold text-white shadow-button hover:bg-brand-dark"
    >
      <Video className="size-4.5" aria-hidden="true" />
      {interview.status === 'in_progress' ? 'Rejoin interview' : 'Start interview'}
    </Link>
  )
}

// A completed interview: its transcript, and its evaluation as it stands.
function CompletedActions({ interview, evaluation, isBusy, onEvaluate }) {
  const transcript = (
    <Link
      to={`/app/interviews/${interview.id}/transcript`}
      aria-label={`View the transcript of the interview with ${interview.candidate_name}`}
      className={`${LINK} inline-flex items-center text-brand hover:text-brand-dark`}
    >
      View transcript
    </Link>
  )
  if (evaluation.state === 'running') {
    return (
      <div role="status" className="flex flex-col items-end gap-1.5">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-brand-dark">
          <LoaderCircle className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          Evaluating · {evaluation.message}
        </span>
        <span aria-hidden="true" className="h-1.5 w-60 overflow-hidden rounded-full bg-[#E4EAF4]">
          <span
            className="block h-full rounded-full bg-brand transition-[width]"
            style={{ width: `${Math.max(evaluation.percent ?? 0, 4)}%` }}
          />
        </span>
        <span className="text-[12.5px]">About a minute. You can leave this page.</span>
      </div>
    )
  }
  if (evaluation.state === 'queued') {
    return (
      <>
        {transcript}
        <span className="text-sm font-semibold text-body">Waiting to be evaluated</span>
      </>
    )
  }
  if (interview.assessment_status) {
    return (
      <>
        {transcript}
        <Link
          to={`/app/interviews/${interview.id}/assessment`}
          className="inline-flex min-h-10 items-center gap-2 whitespace-nowrap rounded-full border-[1.5px] border-brand bg-white px-4.5 font-display text-sm font-bold text-brand hover:bg-tint"
        >
          View assessment
          <ArrowRight className="size-4" aria-hidden="true" />
        </Link>
      </>
    )
  }
  const button = (
    <button
      type="button"
      disabled={isBusy}
      onClick={onEvaluate}
      title={isBusy ? 'Another evaluation is running. Wait for it to finish.' : undefined}
      className="inline-flex min-h-10 items-center gap-2 whitespace-nowrap rounded-full bg-brand px-4.5 font-display text-sm font-bold text-white shadow-button hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-line disabled:text-body disabled:shadow-none"
    >
      <Sparkles className="size-4" aria-hidden="true" />
      {evaluation.state === 'failed' ? 'Try again' : 'Evaluate'}
    </button>
  )
  if (evaluation.state === 'failed') {
    return (
      <div className="flex flex-col items-end gap-2">
        <span role="alert" className="max-w-sm text-right text-[13.5px] leading-snug text-danger">
          {evaluation.reason}
        </span>
        <div className="flex items-center gap-3.5">
          {transcript}
          {button}
        </div>
      </div>
    )
  }
  return (
    <>
      {transcript}
      {button}
    </>
  )
}

function Actions({
  interview,
  rules,
  now,
  canScheduleAgain,
  onNewPin,
  onMove,
  onCancel,
  onScheduleAgain,
  onDelete,
}) {
  const { status } = interview
  if (status === 'cancelled') {
    return (
      <>
        {canScheduleAgain && (
          <button
            type="button"
            onClick={onScheduleAgain}
            className={`${LINK} text-brand hover:text-brand-dark`}
          >
            Schedule again
          </button>
        )}
        <button
          type="button"
          aria-label={`Delete the cancelled interview of ${interview.candidate_name}`}
          title="Delete from the history"
          onClick={onDelete}
          className="flex size-10 shrink-0 items-center justify-center rounded-xl text-body hover:bg-danger-soft hover:text-danger"
        >
          <Trash2 className="size-4.5" aria-hidden="true" />
        </button>
      </>
    )
  }
  const isMissed = joinState(interview, rules, now) === 'missed'
  return (
    <>
      {status === 'scheduled' && (
        <>
          <button
            type="button"
            onClick={onNewPin}
            aria-label={`Send ${interview.candidate_name} a new PIN`}
            className={`${LINK} text-brand hover:text-brand-dark`}
          >
            New PIN
          </button>
          <button type="button" onClick={onMove} className={`${LINK} text-brand hover:text-brand-dark`}>
            Reschedule
          </button>
          <button type="button" onClick={onCancel} className={`${LINK} text-danger hover:opacity-80`}>
            Cancel
          </button>
        </>
      )}
      {!isMissed && <StartButton interview={interview} rules={rules} now={now} />}
    </>
  )
}

// Every interview of the job: upcoming first, then finished and cancelled.
// evaluationOf(interview) says where its evaluation stands; isEvaluating is
// true while any evaluation runs, since only one runs at a time.
export default function InterviewList({
  interviews,
  scores,
  rules,
  now,
  canScheduleAgain,
  onNewPin,
  onMove,
  onCancel,
  onScheduleAgain,
  onDelete,
  evaluationOf,
  isEvaluating,
  onEvaluate,
}) {
  return (
    <section
      aria-label="Interviews"
      className="overflow-hidden rounded-card border border-line bg-white shadow-card"
    >
      <div className="overflow-x-auto">
        <div className="min-w-[860px]">
          <div
            className={`${GRID} border-b border-line bg-mist py-3.5 text-xs font-semibold uppercase tracking-wider`}
          >
            <span>Candidate</span>
            <span>When (your time)</span>
            <span>Status</span>
            <span className="text-right">Actions</span>
          </div>
          {interviews.map((interview) => {
            const status = statusOf(interview, rules, now)
            const isCancelled = interview.status === 'cancelled'
            return (
              <div
                key={interview.id}
                className={`${GRID} border-b border-line/60 py-4.5 last:border-b-0 ${
                  status.row ?? ''
                }`}
              >
                <div className="flex flex-col gap-0.5">
                  <span
                    className={`text-[15.5px] font-semibold ${
                      isCancelled ? 'text-body/70' : 'text-navy'
                    }`}
                  >
                    {interview.candidate_name}
                  </span>
                  <span className="text-[13px]">{scoreLabel(scores.get(interview.candidate_id))}</span>
                  {isActiveRow(interview) && identityShown(interview.identity) && (
                    <span className="mt-1.5">
                      <IdentityChip identity={interview.identity} isLong />
                    </span>
                  )}
                </div>
                <When interview={interview} now={now} />
                <div className="flex flex-col items-start gap-1.5">
                  <StatusChip tone={status.tone}>{status.label}</StatusChip>
                  {REPORT_STATUS[interview.assessment_status] && (
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${
                        REPORT_STATUS[interview.assessment_status].className
                      }`}
                    >
                      {REPORT_STATUS[interview.assessment_status].label}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-end gap-3.5">
                  {interview.status === 'completed' ? (
                    <CompletedActions
                      interview={interview}
                      evaluation={evaluationOf(interview)}
                      isBusy={isEvaluating}
                      onEvaluate={() => onEvaluate(interview)}
                    />
                  ) : (
                    <Actions
                      interview={interview}
                      rules={rules}
                      now={now}
                      canScheduleAgain={canScheduleAgain(interview.candidate_id)}
                      onNewPin={() => onNewPin(interview)}
                      onMove={() => onMove(interview)}
                      onCancel={() => onCancel(interview)}
                      onScheduleAgain={() => onScheduleAgain(interview.candidate_id)}
                      onDelete={() => onDelete(interview)}
                    />
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
