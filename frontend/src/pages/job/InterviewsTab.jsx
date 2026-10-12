import { Bot, CalendarDays, CircleCheck, Info, TriangleAlert, Video, X } from 'lucide-react'
import { useState } from 'react'
import { useOutletContext } from 'react-router'
import Button from '../../components/Button.jsx'
import ConfirmDialog from '../../components/ConfirmDialog.jsx'
import InterviewList from '../../components/interviews/InterviewList.jsx'
import SchedulePanel from '../../components/interviews/SchedulePanel.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import { useCandidates } from '../../hooks/useCandidates.js'
import {
  cancelInterview,
  clock,
  deleteInterview,
  isActive,
  scoreLabel,
  shortDay,
  sortInterviews,
  span,
  waitingFor,
} from '../../lib/interviews.js'

// The three views of the list. Upcoming includes interviews in progress and
// missed ones, which still need a new time or a cancellation.
const VIEWS = [
  { key: 'upcoming', label: 'Upcoming', matches: isActive },
  { key: 'completed', label: 'Completed', matches: (item) => item.status === 'completed' },
  { key: 'cancelled', label: 'Cancelled', matches: (item) => item.status === 'cancelled' },
]

// Pills that switch the list between the views, each with its count. A view
// with nothing in it cannot be picked, except Upcoming, the starting view.
function ViewPills({ view, counts, onChange }) {
  return (
    <div role="tablist" aria-label="Interviews" className="flex flex-wrap gap-2">
      {VIEWS.map((item) => {
        const isActive = item.key === view
        const isDisabled = counts[item.key] === 0 && item.key !== 'upcoming'
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={isActive}
            disabled={isDisabled}
            onClick={() => onChange(item.key)}
            className={`flex min-h-10 items-center gap-2 rounded-full border-[1.5px] px-4 text-sm font-semibold ${
              isActive
                ? 'border-brand bg-brand text-white'
                : isDisabled
                  ? 'cursor-not-allowed border-line bg-white text-body/60'
                  : 'border-line bg-white text-navy hover:border-brand/40 hover:bg-tint'
            }`}
          >
            {item.label}
            <span
              className={`rounded-full px-2 py-0.5 text-xs ${
                isActive ? 'bg-white/20 text-white' : 'bg-mist text-body'
              }`}
            >
              {counts[item.key]}
            </span>
          </button>
        )
      })}
    </div>
  )
}

// A candidate in the waiting room. Start interview opens the room, where
// the interviewer lets them in; the room comes in the next step.
function WaitingBanner({ interview, now }) {
  return (
    <section
      role="status"
      className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-success/25 bg-success-soft px-5 py-4"
    >
      <span className="flex items-center gap-3 text-[15.5px] text-navy">
        <span aria-hidden="true" className="relative size-3 shrink-0">
          <span className="absolute -inset-1.5 animate-ping rounded-full bg-success/20" />
          <span className="absolute inset-0 rounded-full bg-success" />
        </span>
        <span>
          <strong className="font-semibold">
            {interview.candidate_name} is in the waiting room
          </strong>{' '}
          · for {waitingFor(interview, now)} · interview at {clock(interview.scheduled_start)}
        </span>
      </span>
      <button
        type="button"
        disabled
        title="The interview room is coming soon."
        className="inline-flex min-h-11 cursor-not-allowed items-center gap-2 rounded-full bg-success/15 px-5 font-display text-[15px] font-bold text-success/70"
      >
        <Video className="size-4.5" aria-hidden="true" />
        Start interview · room coming soon
      </button>
    </section>
  )
}

function NoUpcoming() {
  return (
    <p className="rounded-card border border-line bg-white px-6 py-8 text-center text-[15px]">
      No upcoming interviews.
    </p>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-card border border-dashed border-line bg-white px-6 py-14 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-tint text-brand">
        <CalendarDays className="size-6" aria-hidden="true" />
      </span>
      <h2 className="text-xl font-extrabold tracking-tight">No one to interview yet</h2>
      <p className="max-w-md leading-relaxed">
        Shortlist candidates on the Screening tab first. Then schedule their interviews here or
        with the AI Agent.
      </p>
      <Button variant="outline" to="../screening" relative="path">
        Go to Screening
      </Button>
    </div>
  )
}

// Shortlisted candidates who have no interview yet, with a quick way in.
function Waiting({ candidates, onSchedule }) {
  const count = candidates.length
  const names = candidates
    .map((item) => `${item.full_name} (${scoreLabel(item.scores?.final_score).toLowerCase()})`)
    .join(', ')
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-dashed border-brand/40 bg-white px-5 py-4">
      <span className="text-[15px] text-navy">
        <strong className="font-semibold">
          {count} shortlisted {count === 1 ? 'candidate has' : 'candidates have'} no interview
          yet:
        </strong>{' '}
        {names}
      </span>
      <Button variant="soft" className="min-h-10 px-4.5 text-[14.5px]" onClick={onSchedule}>
        {count === 1 ? `Schedule ${candidates[0].full_name.split(' ')[0]}` : `Schedule all ${count}`}
      </Button>
    </section>
  )
}

// Shown when nobody shortlisted is waiting and nothing is coming up, for
// example after every interview was cancelled.
function NoneWaiting() {
  return (
    <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-dashed border-brand/40 bg-white px-5 py-4">
      <span className="flex items-start gap-2.5 text-[15px] text-navy">
        <Info className="mt-0.5 size-4.5 shrink-0 text-brand" aria-hidden="true" />
        <span>
          <strong className="font-semibold">
            No shortlisted candidates are waiting for an interview.
          </strong>{' '}
          Shortlist candidates on the Screening tab to schedule more.
        </span>
      </span>
      <Button
        variant="soft"
        className="min-h-10 px-4.5 text-[14.5px]"
        to="../screening"
        relative="path"
      >
        Go to Screening
      </Button>
    </section>
  )
}

const NOTICE_STYLES = {
  success: { icon: CircleCheck, className: 'bg-success-soft text-success' },
  warning: { icon: TriangleAlert, className: 'bg-warning-soft text-warning' },
}

function Notice({ notice, onClose }) {
  const { icon: Icon, className } = NOTICE_STYLES[notice.tone]
  return (
    <p
      role="status"
      className={`flex items-start gap-2.5 rounded-2xl px-4 py-3 text-sm font-semibold ${className}`}
    >
      <Icon className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
      <span className="flex-1">{notice.text}</span>
      <button type="button" aria-label="Dismiss" onClick={onClose} className="hover:opacity-70">
        <X className="size-4.5" aria-hidden="true" />
      </button>
    </p>
  )
}

// The Interviews tab of a job: schedule, move and cancel interviews, and
// see when each one can start.
export default function InterviewsTab() {
  const { job, threadId, listVersion, interviews: data, onChanged } = useOutletContext()
  const { candidates, error: candidatesError } = useCandidates(job.id, listVersion)
  const { interviews, rules, now, error } = data
  // What the side panel is doing: null, { preselected } or { interview }.
  const [panel, setPanel] = useState(null)
  const [cancelling, setCancelling] = useState(null)
  const [isBusy, setIsBusy] = useState(false)
  const [cancelError, setCancelError] = useState('')
  const [notice, setNotice] = useState(null)
  const [view, setView] = useState('upcoming')
  const [deleting, setDeleting] = useState(null)

  if (error || candidatesError) {
    return (
      <p role="alert" className="font-semibold text-danger">
        {error || candidatesError}
      </p>
    )
  }
  if (!interviews || !candidates) return <Skeleton className="h-64 w-full rounded-card" />

  const upcoming = new Set(interviews.filter(isActive).map((item) => item.candidate_id))
  const waiting = candidates
    .filter((item) => item.status === 'shortlisted' && !upcoming.has(item.id))
    .sort((a, b) => (a.scores?.final_rank ?? 999) - (b.scores?.final_rank ?? 999))
  const scores = new Map(candidates.map((item) => [item.id, item.scores?.final_score]))
  const canScheduleAgain = (candidateId) => waiting.some((item) => item.id === candidateId)

  if (interviews.length === 0 && waiting.length === 0) return <EmptyState />

  const counts = Object.fromEntries(
    VIEWS.map((item) => [item.key, interviews.filter(item.matches).length]),
  )
  // After the last cancelled interview is deleted, go back to Upcoming.
  const currentView = counts[view] === 0 ? 'upcoming' : view
  const shown = interviews.filter(VIEWS.find((item) => item.key === currentView).matches)

  function handleDone(warning) {
    onChanged()
    setNotice(warning ? { tone: 'warning', text: warning } : null)
  }

  async function confirmCancel() {
    setIsBusy(true)
    setCancelError('')
    try {
      const change = await cancelInterview(cancelling.id)
      setNotice(
        change.warning
          ? { tone: 'warning', text: change.warning }
          : {
              tone: 'success',
              text: `${cancelling.candidate_name}'s interview is cancelled and they were told.`,
            },
      )
      setCancelling(null)
      onChanged()
    } catch (cancelFailure) {
      setCancelError(cancelFailure.message)
    } finally {
      setIsBusy(false)
    }
  }

  async function confirmDelete() {
    setIsBusy(true)
    setCancelError('')
    try {
      await deleteInterview(deleting.id)
      setDeleting(null)
      onChanged()
    } catch (deleteError) {
      setCancelError(deleteError.message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <>
      {notice && <Notice notice={notice} onClose={() => setNotice(null)} />}
      {sortInterviews(interviews.filter((item) => item.candidate_waiting)).map((item) => (
        <WaitingBanner key={item.id} interview={item} now={now} />
      ))}

      <section className="flex flex-wrap items-center justify-between gap-4">
        <ViewPills view={currentView} counts={counts} onChange={setView} />
        <div className="flex flex-wrap gap-3">
          {threadId && (
            <Button variant="outline" to={`/app/assistant/${threadId}`}>
              <Bot className="size-4.5" aria-hidden="true" />
              Schedule in AI Agent
            </Button>
          )}
          <Button
            disabled={waiting.length === 0}
            onClick={() => setPanel({ preselected: waiting.map((item) => item.id) })}
          >
            <CalendarDays className="size-4.5" aria-hidden="true" />
            Schedule interviews
          </Button>
        </div>
      </section>

      {waiting.length > 0 && (
        <Waiting
          candidates={waiting}
          onSchedule={() => setPanel({ preselected: waiting.map((item) => item.id) })}
        />
      )}
      {waiting.length === 0 && upcoming.size === 0 && <NoneWaiting />}

      {shown.length === 0 ? (
        <NoUpcoming />
      ) : (
        <InterviewList
          interviews={sortInterviews(shown)}
          scores={scores}
          rules={rules}
          now={now}
          canScheduleAgain={canScheduleAgain}
          onMove={(interview) => setPanel({ interview })}
          onCancel={(interview) => {
            setCancelError('')
            setCancelling(interview)
          }}
          onScheduleAgain={(candidateId) => setPanel({ preselected: [candidateId] })}
          onDelete={(interview) => {
            setCancelError('')
            setDeleting(interview)
          }}
        />
      )}

      <p className="flex items-start gap-2.5 text-sm">
        <Info className="mt-0.5 size-4.5 shrink-0 text-brand" aria-hidden="true" />
        <span>
          Each candidate gets a calendar invitation by email with a private link. Their Join
          button opens{' '}
          {rules?.join_opens_minutes_before ?? 10} minutes before the start. Rescheduling sends a
          new link and the old one stops working.
        </span>
      </p>

      {panel && (
        <SchedulePanel
          job={job}
          candidates={candidates}
          interviews={interviews}
          rules={rules}
          interview={panel.interview}
          preselected={panel.preselected}
          onClose={() => setPanel(null)}
          onDone={handleDone}
        />
      )}

      {cancelling && (
        <ConfirmDialog
          title="Cancel this interview?"
          cancelLabel="Keep it"
          confirmLabel="Cancel interview"
          busyLabel="Cancelling…"
          isBusy={isBusy}
          error={cancelError}
          onConfirm={confirmCancel}
          onCancel={() => setCancelling(null)}
        >
          <p>
            <strong className="font-semibold text-navy">{cancelling.candidate_name}</strong>,{' '}
            {shortDay(cancelling.scheduled_start)} ·{' '}
            {span(cancelling.scheduled_start, cancelling.scheduled_end)}
          </p>
          <p>
            Google Calendar sends them a cancellation notice. Their link stops working, and they
            go back on the shortlist.
          </p>
        </ConfirmDialog>
      )}

      {deleting && (
        <ConfirmDialog
          title="Delete this cancelled interview?"
          cancelLabel="Keep it"
          confirmLabel="Delete"
          isBusy={isBusy}
          error={cancelError}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        >
          <p>
            <strong className="font-semibold text-navy">{deleting.candidate_name}</strong>,{' '}
            {shortDay(deleting.scheduled_start)} ·{' '}
            {span(deleting.scheduled_start, deleting.scheduled_end)}
          </p>
          <p>It is removed from the history. The candidate is not affected.</p>
        </ConfirmDialog>
      )}
    </>
  )
}
