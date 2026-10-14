import { ArrowRight, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import {
  CARD_STATUS,
  clockAfter,
  longDay,
  rangeLabel,
  scoreLabel,
  shortDay,
} from '../../lib/interviews.js'
import Button from '../Button.jsx'
import StatusChip from '../StatusChip.jsx'
import { OutcomeLine, WhenYouApprove } from './InterviewCardParts.jsx'

const GRID =
  'grid grid-cols-[minmax(0,1.6fr)_minmax(0,1.1fr)_minmax(0,0.9fr)_minmax(0,0.8fr)_2.75rem] items-center gap-3'
const INPUT =
  'min-h-10 w-full rounded-[10px] border-[1.5px] border-line bg-white px-2.5 text-[14.5px] text-navy focus:border-brand focus:outline-none'

// The parts of a row the interviewer can change, as the agent's tool takes them.
function editable(row) {
  return {
    candidate_id: row.candidate_id,
    date: row.date,
    start_time: row.start_time,
    duration_minutes: row.duration_minutes,
  }
}

// A date string such as "2026-10-14" read as that calendar day.
function calendarDay(date) {
  return `${date}T12:00:00Z`
}

function summary(rows, zoneLabel) {
  const days = [...new Set(rows.map((row) => row.date))]
  const lengths = [...new Set(rows.map((row) => row.duration_minutes))]
  return [
    days.length === 1 && days[0] ? longDay(calendarDay(days[0]), 'UTC') : 'Several days',
    lengths.length === 1 && `${lengths[0]} minutes each`,
    zoneLabel && `your time (${zoneLabel})`,
  ]
    .filter(Boolean)
    .join(' · ')
}

function Row({ row, isEditing, canRemove, onChange, onRemove }) {
  const name = row.candidate_name ?? `Candidate ${row.candidate_id}`
  const details = [
    row.final_score != null && scoreLabel(row.final_score),
    row.rank && `rank ${row.rank}`,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <div className={`${GRID} border-b border-line/60 py-3 last:border-b-0`}>
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-[15px] font-semibold text-navy">{name}</span>
        {details && <span className="text-[13px]">{details}</span>}
      </div>
      {isEditing ? (
        <>
          <input
            type="date"
            aria-label={`Date for ${name}`}
            value={row.date}
            onChange={(event) => onChange({ date: event.target.value })}
            className={INPUT}
          />
          <input
            type="time"
            step={300}
            aria-label={`Start time for ${name}`}
            value={row.start_time}
            onChange={(event) => onChange({ start_time: event.target.value })}
            className={INPUT}
          />
        </>
      ) : (
        <>
          <span className="text-[14.5px] text-navy">
            {row.date ? shortDay(calendarDay(row.date), 'UTC') : ''}
          </span>
          <span className="text-[14.5px] text-navy">
            {row.start_time ? clockAfter(row.start_time, 0) : ''}
          </span>
        </>
      )}
      <span className="text-[14.5px] text-navy">
        {row.start_time && row.duration_minutes
          ? clockAfter(row.start_time, row.duration_minutes)
          : ''}
      </span>
      {isEditing && canRemove ? (
        <button
          type="button"
          aria-label={`Remove ${name} from the schedule`}
          onClick={onRemove}
          className="flex size-10 items-center justify-center rounded-[10px] text-body hover:bg-mist"
        >
          <X className="size-4.5" aria-hidden="true" />
        </button>
      ) : (
        <span />
      )}
    </div>
  )
}

// What happened to each candidate once the schedule was approved.
function ScheduleResult({ results, timeZone, jobId }) {
  const sent = results.filter((item) => item.status === 'scheduled').length
  return (
    <article className="overflow-hidden rounded-2xl border border-line bg-white shadow-card">
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
        <span className="font-display text-[15px] font-bold text-navy">Interviews scheduled</span>
        <StatusChip tone={sent === results.length ? 'amber' : 'warning'}>
          {sent} of {results.length} {results.length === 1 ? 'invite' : 'invites'} sent
        </StatusChip>
      </header>
      <div className="flex flex-col px-4 py-1.5">
        {results.map((item) => {
          const when = rangeLabel(item.start, item.end, timeZone) || item.when
          if (item.status === 'failed') {
            return (
              <OutcomeLine key={item.candidate_id} kind="failed" name={item.candidate_name}>
                <span className="text-danger">{item.error}</span>
              </OutcomeLine>
            )
          }
          return (
            <OutcomeLine
              key={item.candidate_id}
              kind={item.warning ? 'warning' : 'done'}
              name={item.candidate_name}
            >
              {when}
              {item.warning ? (
                <span className="block text-warning">{item.warning}</span>
              ) : (
                ' · calendar invitation sent'
              )}
            </OutcomeLine>
          )
        })}
      </div>
      {jobId && (
        <div className="px-4 pb-4 pt-1.5">
          <Link
            to={`/app/jobs/${jobId}/interviews`}
            className="inline-flex items-center gap-1.5 text-[14.5px] font-semibold text-brand hover:text-brand-dark"
          >
            Open the Interviews tab
            <ArrowRight className="size-4" aria-hidden="true" />
          </Link>
        </div>
      )}
    </article>
  )
}

// The schedule the AI Agent proposes. Nothing is sent until the interviewer
// approves. Changed times or a changed message go back to the server to be
// checked first, and the card comes back with the checked schedule and its
// new preview, which starts the edits afresh.
export default function ScheduleCard(props) {
  return <Schedule key={JSON.stringify(props.item.arguments)} {...props} />
}

function Schedule({ item, canAct, jobId, onApprove, onCheck, onRequestChanges }) {
  const args = item.arguments ?? {}
  const original = args.interviews ?? []
  const [rows, setRows] = useState(original)
  // The message being edited, or null.
  const [draft, setDraft] = useState(null)
  const isWaiting = item.status === 'waiting'
  const isEditing = isWaiting && canAct
  const isEdited =
    JSON.stringify(rows.map(editable)) !== JSON.stringify(original.map(editable))
  const chip = CARD_STATUS[item.status] ?? CARD_STATUS.changed
  const count = rows.length
  // The interviewer's own message, or null for the default one.
  const message = args.message ?? null
  const email = {
    preview: args.email_preview,
    message: message ?? args.default_message ?? '',
    noun: 'invitation',
    title: 'The invitation',
    previewLabel: `Preview for ${original[0]?.candidate_name ?? 'the candidate'}`,
    fieldLabel: count === 1 ? 'Message to the candidate' : 'Message to the candidates',
    hint: 'The greeting with each name, the time, the Join link, the tips and the signature are added automatically. Do not type them here.',
    footnote:
      'The highlighted part is your message. Each candidate gets their own name and private link.',
  }

  // Changed times or a new message go back to the server to be checked.
  function check(changes) {
    onCheck({ interviews: rows.map(editable), message, ...changes })
  }

  function change(index, changes) {
    setRows((current) => current.map((row, at) => (at === index ? { ...row, ...changes } : row)))
  }

  function remove(index) {
    setRows((current) => current.filter((_, at) => at !== index))
  }

  return (
    <div className="flex w-full flex-col gap-4">
      <article
        className={`overflow-hidden rounded-2xl border bg-white ${
          isWaiting ? 'border-brand shadow-card' : 'border-line'
        } ${item.status === 'changed' ? 'opacity-70' : ''}`}
      >
        <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
          <div>
            <div className="font-display text-[15px] font-bold text-navy">
              Interview schedule · {count} {count === 1 ? 'candidate' : 'candidates'}
            </div>
            <div className="mt-0.5 text-[13.5px]">
              {summary(rows, args.time_zone_label ?? args.time_zone)}
            </div>
          </div>
          <StatusChip tone={chip.tone}>
            {(isEdited || message) && isWaiting ? 'Edited by you' : chip.label}
          </StatusChip>
        </header>

        <div className="overflow-x-auto px-4 py-1.5">
          <div className="min-w-[560px]">
            <div
              className={`${GRID} border-b border-line/60 py-2.5 text-xs font-semibold uppercase tracking-wider`}
            >
              <span>Candidate</span>
              <span>Date</span>
              <span>Start</span>
              <span>Ends</span>
              <span />
            </div>
            {rows.map((row, index) => (
              <Row
                key={row.candidate_id}
                row={row}
                isEditing={isEditing}
                canRemove={rows.length > 1}
                onChange={(changes) => change(index, changes)}
                onRemove={() => remove(index)}
              />
            ))}
          </div>
        </div>

        {isWaiting && (
          <WhenYouApprove
            email={email}
            draft={draft}
            onDraft={setDraft}
            onSaveMessage={isEditing ? (text) => check({ message: text }) : null}
            lines={[
              {
                icon: 'mail',
                text: 'Each candidate gets one calendar invitation by email, with their own private Join link.',
              },
              {
                icon: 'calendar',
                text: 'It adds the interview to their calendar, in their own time zone.',
              },
              {
                icon: 'lock',
                text: 'Requirements and weights are locked for this job, so every interviewed candidate keeps the same rules.',
              },
            ]}
          />
        )}

        {isEditing && (
          <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3.5">
            <span className="text-sm">
              {draft !== null
                ? 'Save the message to see it in the preview, then approve.'
                : isEdited
                  ? 'Your new times are checked before anything is sent.'
                  : 'or type what to change below'}
            </span>
            <div className="flex flex-wrap gap-2.5">
              {isEdited ? (
                <>
                  <Button variant="soft" onClick={() => setRows(original)}>
                    Undo changes
                  </Button>
                  <Button onClick={() => check()}>Check the new times</Button>
                </>
              ) : (
                <>
                  <Button variant="outline" onClick={onRequestChanges}>
                    Request changes
                  </Button>
                  <Button onClick={onApprove} disabled={draft !== null}>
                    Approve and send {count === 1 ? 'the invite' : `${count} invites`}
                  </Button>
                </>
              )}
            </div>
          </footer>
        )}
      </article>

      {Array.isArray(item.result) && (
        <ScheduleResult results={item.result} timeZone={args.time_zone} jobId={jobId} />
      )}
    </div>
  )
}
