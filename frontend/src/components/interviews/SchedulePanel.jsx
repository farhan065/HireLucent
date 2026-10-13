import { CircleAlert, CircleCheck, CircleX, Mail, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import {
  BREAKS,
  LENGTHS,
  MAX_DAYS_AHEAD,
  addMinutes,
  browserZoneLabel,
  clock,
  dateValue,
  dayLabel,
  earliestStart,
  fromInputs,
  invites,
  isActive,
  minutesBetween,
  moveInterview,
  scheduleInterviews,
  scoreLabel,
  shortDay,
  span,
  timeValue,
} from '../../lib/interviews.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'
import SidePanel from '../SidePanel.jsx'

const FIELD =
  'min-h-11.5 w-full rounded-xl border-[1.5px] border-line bg-white px-3.5 text-[15px] text-navy focus:border-brand focus:outline-none'
const LABEL = 'flex flex-col gap-1.5 text-[14.5px] font-semibold text-navy'

function Field({ label, children }) {
  return (
    <label className={LABEL}>
      {label}
      {children}
    </label>
  )
}

function minutesLabel(minutes) {
  return minutes === 0 ? 'None' : `${minutes} minutes`
}

// The shortlisted candidates, best first. Those with an upcoming interview
// are shown but cannot be picked.
function CandidatePicker({ candidates, upcoming, selected, onToggle }) {
  return (
    <fieldset className="flex flex-col gap-2.5">
      <legend className="mb-2.5 text-[15px] font-semibold text-navy">Candidates</legend>
      {candidates.map((candidate) => {
        const interview = upcoming.get(candidate.id)
        const isChecked = selected.includes(candidate.id)
        return (
          <label
            key={candidate.id}
            className={`flex min-h-13 items-center gap-3 rounded-2xl border-[1.5px] px-3.5 py-2 text-[15px] ${
              interview
                ? 'border-line text-body/70'
                : isChecked
                  ? 'border-brand bg-mist text-navy'
                  : 'border-line text-navy hover:border-brand/40'
            }`}
          >
            <input
              type="checkbox"
              checked={isChecked}
              disabled={Boolean(interview)}
              onChange={() => onToggle(candidate.id)}
              className="size-4.5 accent-brand"
            />
            <span className="flex-1">
              <strong className="font-semibold">{candidate.full_name}</strong>
              <span className="block text-[13px] text-body">
                {interview
                  ? `Already scheduled · ${shortDay(interview.scheduled_start)}, ${clock(
                      interview.scheduled_start,
                    )}`
                  : `Shortlisted · ${scoreLabel(candidate.scores?.final_score).toLowerCase()}`}
              </span>
            </span>
          </label>
        )
      })}
      <span className="text-[13px]">Only shortlisted candidates can be scheduled.</span>
    </fieldset>
  )
}

function Preview({ slots }) {
  return (
    <div className="flex flex-col gap-2.5">
      <span className="text-[15px] font-semibold text-navy">Preview</span>
      {slots.map((slot) => (
        <div
          key={slot.candidate.id}
          className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-mist px-4 py-3.5"
        >
          <span className="font-semibold text-navy">{slot.candidate.full_name}</span>
          <span className="text-[14.5px]">
            {shortDay(slot.start)} · {span(slot.start, slot.end)}
          </span>
        </div>
      ))}
    </div>
  )
}

const OUTCOME_ICONS = {
  scheduled: { icon: CircleCheck, color: 'text-success' },
  warning: { icon: TriangleAlert, color: 'text-warning' },
  failed: { icon: CircleX, color: 'text-danger' },
}

// What happened to each candidate after the invites were sent.
function Outcomes({ outcomes }) {
  const sent = outcomes.filter((item) => item.status === 'scheduled').length
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[15px] font-semibold text-navy">
        {sent} of {outcomes.length} {outcomes.length === 1 ? 'invite' : 'invites'} sent
      </p>
      {outcomes.map((item) => {
        const kind = item.status === 'failed' ? 'failed' : item.warning ? 'warning' : 'scheduled'
        const { icon: Icon, color } = OUTCOME_ICONS[kind]
        return (
          <div key={item.candidate_id} className="flex gap-3 rounded-2xl bg-mist px-4 py-3.5">
            <Icon className={`mt-0.5 size-5 shrink-0 ${color}`} aria-hidden="true" />
            <div className="flex min-w-0 flex-col gap-0.5 text-sm">
              <strong className="text-[15px] font-semibold text-navy">
                {item.candidate_name}
              </strong>
              {item.scheduled_start && (
                <span>
                  {shortDay(item.scheduled_start)} ·{' '}
                  {span(item.scheduled_start, item.scheduled_end)}
                  {kind === 'scheduled' && ' · calendar invitation sent'}
                </span>
              )}
              {item.warning && <span className="text-warning">{item.warning}</span>}
              {item.error && <span className="text-danger">{item.error}</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// Schedules new interviews, or moves one ("interview" is given). Nothing is
// sent until the interviewer confirms. "onDone" runs after the server has
// answered, with a warning if something could not be sent.
export default function SchedulePanel({
  job,
  candidates,
  interviews,
  rules,
  interview = null,
  preselected = [],
  onClose,
  onDone,
}) {
  const isMove = Boolean(interview)
  const [first] = useState(() => earliestStart(rules))
  const [date, setDate] = useState(dateValue(first))
  const [time, setTime] = useState(timeValue(first))
  const currentLength = isMove
    ? minutesBetween(interview.scheduled_start, interview.scheduled_end)
    : 45
  const lengths = LENGTHS.includes(currentLength)
    ? LENGTHS
    : [...LENGTHS, currentLength].sort((a, b) => a - b)
  const [length, setLength] = useState(currentLength)
  const [gap, setGap] = useState(15)
  const [selected, setSelected] = useState(preselected)
  const [isConfirming, setIsConfirming] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const [outcomes, setOutcomes] = useState(null)

  // Shortlisted candidates and those with an upcoming interview, best first.
  const upcoming = new Map(
    (interviews ?? []).filter(isActive).map((item) => [item.candidate_id, item]),
  )
  const choices = (candidates ?? [])
    .filter((item) => item.status === 'shortlisted' || upcoming.has(item.id))
    .sort((a, b) => (a.scores?.final_rank ?? 999) - (b.scores?.final_rank ?? 999))
  const chosen = choices.filter((item) => selected.includes(item.id))

  // Back to back, in ranking order, with the break between them.
  const start = fromInputs(date, time)
  const slots = start
    ? (isMove ? [{ id: interview.candidate_id, full_name: interview.candidate_name }] : chosen).map(
        (candidate, index) => {
          const slotStart = addMinutes(start, index * (length + gap))
          return { candidate, start: slotStart, end: addMinutes(slotStart, length) }
        },
      )
    : []

  const now = new Date()
  const notice = rules?.min_notice_minutes ?? 15
  let problem = ''
  if (!start) problem = 'Pick a date and a start time.'
  else if (start < addMinutes(now, notice)) {
    problem = `Pick a start at least ${notice} ${notice === 1 ? 'minute' : 'minutes'} from now.`
  } else if (start > addMinutes(now, MAX_DAYS_AHEAD * 24 * 60)) {
    problem = `Interviews can be scheduled at most ${MAX_DAYS_AHEAD} days ahead.`
  }
  const canReview = !problem && slots.length > 0
  const zone = browserZoneLabel()

  function toggle(candidateId) {
    setSelected((ids) =>
      ids.includes(candidateId) ? ids.filter((id) => id !== candidateId) : [...ids, candidateId],
    )
  }

  async function send() {
    setIsBusy(true)
    setError('')
    try {
      if (isMove) {
        const [slot] = slots
        const change = await moveInterview(
          interview.id,
          slot.start.toISOString(),
          slot.end.toISOString(),
        )
        onDone(change.warning)
        onClose()
        return
      }
      const result = await scheduleInterviews(
        job.id,
        slots.map((slot) => ({
          candidate_id: slot.candidate.id,
          start: slot.start.toISOString(),
          end: slot.end.toISOString(),
        })),
      )
      setOutcomes(result)
      setIsConfirming(false)
      onDone()
    } catch (sendError) {
      setError(sendError.message)
    } finally {
      setIsBusy(false)
    }
  }

  // While the confirmation is open, Escape closes only the confirmation.
  const closePanel = isConfirming ? () => {} : onClose
  const title = isMove ? 'Reschedule interview' : 'Schedule interviews'
  const subtitle = isMove
    ? `${interview.candidate_name} · now ${dayLabel(interview.scheduled_start)}, ${span(
        interview.scheduled_start,
        interview.scheduled_end,
      )}`
    : `${job.title} · ${job.job_code}`

  if (outcomes) {
    return (
      <SidePanel
        title="Invites sent"
        subtitle={subtitle}
        onClose={onClose}
        footer={
          <div className="flex justify-end">
            <Button onClick={onClose}>Done</Button>
          </div>
        }
      >
        <Outcomes outcomes={outcomes} />
      </SidePanel>
    )
  }

  const reviewLabel = isMove
    ? 'Review and send new time'
    : slots.length > 1
      ? `Review and send ${slots.length} invites`
      : 'Review and send invite'

  return (
    <>
      <SidePanel
        title={title}
        subtitle={subtitle}
        onClose={closePanel}
        footer={
          <div className="flex flex-wrap justify-end gap-3">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button disabled={!canReview} onClick={() => setIsConfirming(true)}>
              {reviewLabel}
            </Button>
          </div>
        }
      >
        <div className="flex flex-col gap-5.5">
          {!isMove && (
            <CandidatePicker
              candidates={choices}
              upcoming={upcoming}
              selected={selected}
              onToggle={toggle}
            />
          )}

          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2">
            <Field label="Date">
              <input
                type="date"
                value={date}
                min={dateValue(now)}
                max={dateValue(addMinutes(now, MAX_DAYS_AHEAD * 24 * 60))}
                onChange={(event) => setDate(event.target.value)}
                className={FIELD}
              />
            </Field>
            <Field label={isMove || slots.length < 2 ? 'Starts' : 'First interview starts'}>
              <input
                type="time"
                value={time}
                step={300}
                onChange={(event) => setTime(event.target.value)}
                className={FIELD}
              />
            </Field>
            <Field label="Length">
              <select
                value={length}
                onChange={(event) => setLength(Number(event.target.value))}
                className={FIELD}
              >
                {lengths.map((minutes) => (
                  <option key={minutes} value={minutes}>
                    {minutesLabel(minutes)}
                  </option>
                ))}
              </select>
            </Field>
            {!isMove && (
              <Field label="Break between interviews">
                <select
                  value={gap}
                  onChange={(event) => setGap(Number(event.target.value))}
                  className={FIELD}
                >
                  {BREAKS.map((minutes) => (
                    <option key={minutes} value={minutes}>
                      {minutesLabel(minutes)}
                    </option>
                  ))}
                </select>
              </Field>
            )}
          </div>
          <p className="-mt-1.5 text-[13.5px]">
            Times are in your time zone ({zone}). Candidates see their own local time.
          </p>

          {problem && start && (
            <p role="alert" className="flex items-center gap-2 text-sm font-semibold text-danger">
              <CircleAlert className="size-4.5 shrink-0" aria-hidden="true" />
              {problem}
            </p>
          )}
          {slots.length > 0 && <Preview slots={slots} />}
          {!isMove && choices.length === 0 && (
            <p className="text-sm">No candidates are shortlisted for this job yet.</p>
          )}
        </div>
      </SidePanel>

      {isConfirming && (
        <ConfirmDialog
          title={isMove ? 'Send the new time?' : `Send ${invites(slots.length)}?`}
          icon={Mail}
          lead={
            isMove
              ? `${interview.candidate_name} gets an updated invitation with the new time and a new private link. The old link stops working.`
              : slots.length === 1
                ? `${slots[0].candidate.full_name} gets a calendar invitation by email with a private interview link.`
                : 'Each candidate gets a calendar invitation by email with their own private interview link.'
          }
          cancelLabel="Go back"
          confirmLabel={
            isMove ? 'Send new time' : slots.length === 1 ? 'Send invite' : `Send ${slots.length} invites`
          }
          busyLabel="Sending…"
          confirmVariant="primary"
          isBusy={isBusy}
          error={error}
          onConfirm={send}
          onCancel={() => {
            setIsConfirming(false)
            setError('')
          }}
        >
          <div className="flex flex-col gap-1.5 rounded-2xl bg-mist px-4 py-3.5 text-[14.5px]">
            {slots.map((slot) => (
              <span key={slot.candidate.id} className="flex justify-between gap-3">
                <span>{slots.length === 1 ? 'When' : slot.candidate.full_name}</span>
                <strong className="text-right font-semibold text-navy">
                  {slots.length === 1
                    ? `${shortDay(slot.start)} ${slot.start.getFullYear()}, `
                    : `${shortDay(slot.start)}, `}
                  {span(slot.start, slot.end)}
                </strong>
              </span>
            ))}
            <span className="flex justify-between gap-3">
              <span>Time zone</span>
              <strong className="font-semibold text-navy">{zone}</strong>
            </span>
          </div>
          {!isMove && (
            <p className="text-[13.5px]">
              After this, the requirements and weights for this job can no longer be changed.
            </p>
          )}
        </ConfirmDialog>
      )}
    </>
  )
}
