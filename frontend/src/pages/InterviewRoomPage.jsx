import {
  ArrowLeft,
  Bot,
  CircleAlert,
  Lightbulb,
  MessageSquareText,
  UserRound,
} from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import Button from '../components/Button.jsx'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import CandidateProfile from '../components/room/CandidateProfile.jsx'
import ConnectionChip from '../components/room/ConnectionChip.jsx'
import InterviewChat from '../components/room/InterviewChat.jsx'
import LiveTranscript from '../components/room/LiveTranscript.jsx'
import RoomControls from '../components/room/RoomControls.jsx'
import RoomMessages from '../components/room/RoomMessages.jsx'
import SuggestedQuestions from '../components/room/SuggestedQuestions.jsx'
import VideoStage from '../components/room/VideoStage.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusChip from '../components/StatusChip.jsx'
import { useRoom } from '../hooks/useRoom.js'
import { useTranscript } from '../hooks/useTranscript.js'
import { useUnread } from '../hooks/useUnread.js'
import { apiRequest } from '../lib/api.js'
import { clock, minutesBetween, waitingFor } from '../lib/interviews.js'
import {
  admitCandidate,
  elapsed,
  endInterview,
  leaveFullScreen,
  openRoom,
  readInterview,
} from '../lib/room.js'

const REFRESH_MS = 3 * 1000

function useNow(intervalMs) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

// "12:48 of 45:00 · ends 3:45 PM", amber once the planned length has
// passed: "47:10 of 45:00 · 2 min over". Both count from when the
// interview really started, so the numbers always agree.
function Timer({ interview, now }) {
  const length = minutesBetween(interview.scheduled_start, interview.scheduled_end)
  if (!interview.started_at) {
    return <span className="text-sm">Starts at {clock(interview.scheduled_start)}</span>
  }
  const plannedEnd = new Date(new Date(interview.started_at).getTime() + length * 60000)
  const over = Math.floor((now - plannedEnd) / 60000)
  return (
    <span
      className={`font-display text-[14.5px] font-bold tabular-nums ${over > 0 ? 'text-amber' : 'text-navy'}`}
    >
      {elapsed(interview.started_at, now)} of {length}:00 ·{' '}
      {over > 0 ? `${over} min over` : `ends ${clock(plannedEnd)}`}
    </span>
  )
}

// Above the video while the candidate waits or before they arrive.
function AdmitBar({ interview, now, isAdmitting, error, onAdmit }) {
  const name = interview.candidate_name
  if (interview.status !== 'scheduled') return null
  if (!interview.candidate_waiting) {
    return (
      <p className="rounded-2xl border border-line bg-white px-4 py-3 text-sm">
        Waiting for <strong className="font-semibold text-navy">{name}</strong> to join. You will
        be asked to let them in.
      </p>
    )
  }
  return (
    <section
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-success/25 bg-success-soft px-4 py-3"
    >
      <span className="flex items-center gap-3 text-[15px] text-navy">
        <span aria-hidden="true" className="relative size-3 shrink-0">
          <span className="absolute -inset-1.5 animate-ping rounded-full bg-success/20" />
          <span className="absolute inset-0 rounded-full bg-success" />
        </span>
        <span>
          <strong className="font-semibold">{name} is waiting</strong> · for{' '}
          {waitingFor(interview, now)}
        </span>
      </span>
      <div className="flex items-center gap-3">
        {error && <span className="text-sm font-semibold text-danger">{error}</span>}
        <Button className="min-h-10.5 bg-success hover:bg-success/90" disabled={isAdmitting} onClick={onAdmit}>
          {isAdmitting ? 'Letting in…' : 'Admit'}
        </Button>
      </div>
    </section>
  )
}

const TABS = [
  { key: 'info', label: 'Candidate info', icon: UserRound, active: 'bg-tint text-brand-dark' },
  {
    key: 'questions',
    label: 'Suggested questions',
    icon: Lightbulb,
    active: 'bg-violet-soft text-violet',
  },
]

// The candidate at a glance, and questions to ask them. Both tabs stay
// loaded, so switching between them keeps their place.
function CandidatePanel({ sessionId, candidateName, candidate }) {
  const [tab, setTab] = useState('info')
  return (
    <section className="@container flex min-h-[36rem] flex-col overflow-hidden rounded-card border border-line bg-white shadow-card lg:min-h-0">
      <div role="tablist" aria-label="About the candidate" className="grid grid-cols-2 gap-1.5 border-b border-line p-1.5">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={`flex min-h-9.5 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl px-2 font-display text-[13px] font-bold ${
              tab === item.key ? item.active : 'text-body hover:text-navy'
            }`}
          >
            {/* On a narrow column the labels need the room. */}
            <item.icon className="hidden size-4 @[22rem]:block" aria-hidden="true" />
            {item.label}
          </button>
        ))}
      </div>
      <div className={`min-h-0 flex-1 flex-col ${tab === 'info' ? 'flex' : 'hidden'}`}>
        {candidate ? (
          <CandidateProfile candidate={candidate} />
        ) : (
          <div className="p-4.5">
            <Skeleton className="h-64 w-full" />
          </div>
        )}
      </div>
      <div className={`min-h-0 flex-1 flex-col ${tab === 'questions' ? 'flex' : 'hidden'}`}>
        <SuggestedQuestions sessionId={sessionId} candidateName={candidateName} />
      </div>
    </section>
  )
}

// The read-only AI Agent chat, and live messages with the candidate. Both
// tabs stay loaded; the Message tab counts messages that arrive while it
// is hidden.
function ChatPanel({ sessionId, candidateName, room }) {
  const [tab, setTab] = useState('agent')
  const [unread, markSeen] = useUnread(room.messages, tab === 'message')
  const firstName = candidateName.split(/\s+/)[0] || candidateName

  function choose(next) {
    if (tab === 'message' && next !== 'message') markSeen()
    setTab(next)
  }

  const tabs = [
    { key: 'agent', label: 'AI Agent', icon: Bot },
    { key: 'message', label: 'Message', icon: MessageSquareText, unread },
  ]
  return (
    <section className="flex min-h-[32rem] flex-col overflow-hidden rounded-card border border-line bg-white shadow-card lg:min-h-0">
      <div role="tablist" aria-label="Chat" className="grid grid-cols-2 gap-1.5 border-b border-line p-1.5">
        {tabs.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            aria-label={item.unread ? `${item.label}, ${item.unread} unread` : undefined}
            onClick={() => choose(item.key)}
            className={`flex min-h-9.5 items-center justify-center gap-1.5 whitespace-nowrap rounded-xl px-2 font-display text-[13px] font-bold ${
              tab === item.key ? 'bg-tint text-brand-dark' : 'text-body hover:text-navy'
            }`}
          >
            <item.icon className="size-4" aria-hidden="true" />
            {item.label}
            {item.unread > 0 && (
              <span className="inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-danger px-1.25 font-sans text-[11px] font-bold text-white">
                {item.unread}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className={`min-h-0 flex-1 flex-col ${tab === 'agent' ? 'flex' : 'hidden'}`}>
        <InterviewChat sessionId={sessionId} candidateName={candidateName} />
      </div>
      <div className={`min-h-0 flex-1 flex-col ${tab === 'message' ? 'flex' : 'hidden'}`}>
        <RoomMessages
          room={room}
          otherName={firstName}
          hint={`Only ${firstName} and you see these. They are not saved.`}
          waitingText={`You can message ${firstName} once they are in the room.`}
        />
      </div>
    </section>
  )
}

// The interviewer's interview room: the candidate and suggested questions
// on the left, the video with the live transcript below it in the middle,
// and the read-only AI Agent chat and messages with the candidate on the
// right.
export default function InterviewRoomPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const now = useNow(1000)
  const [info, setInfo] = useState(null)
  const [candidate, setCandidate] = useState(null)
  const [connection, setConnection] = useState(null)
  const [error, setError] = useState('')
  const [isAdmitting, setIsAdmitting] = useState(false)
  const [admitError, setAdmitError] = useState('')
  const [isConfirmingEnd, setIsConfirmingEnd] = useState(false)
  const [isEnding, setIsEnding] = useState(false)
  const [endError, setEndError] = useState('')
  // A fresh pass to rejoin the room after the connection was lost.
  const renewPass = useCallback(() => openRoom(sessionId), [sessionId])
  const room = useRoom(connection, renewPass)

  const load = useCallback(
    () =>
      readInterview(sessionId)
        .then(setInfo)
        .catch((loadError) => setError(loadError.message)),
    [sessionId],
  )

  // Open the room once, then keep the interview's state current.
  useEffect(() => {
    openRoom(sessionId)
      .then(setConnection)
      .catch((openError) => setError(openError.message))
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [sessionId, load])

  const jobId = info?.job_id
  const candidateId = info?.interview.candidate_id
  useEffect(() => {
    if (!jobId) return
    apiRequest(`/jobs/${jobId}/candidates`)
      .then((list) => setCandidate(list.find((item) => item.id === candidateId) ?? null))
      .catch(() => setCandidate(null))
  }, [jobId, candidateId])

  const backTo = jobId ? `/app/jobs/${jobId}/interviews` : '/app/jobs'
  const status = info?.interview.status
  const transcript = useTranscript(sessionId, room, status === 'in_progress')
  // Ended somewhere else, for example in another tab.
  useEffect(() => {
    const isOver = status === 'completed' || status === 'cancelled' || room.endReason === 'ended'
    if (isOver) navigate(backTo, { replace: true })
  }, [status, room.endReason, backTo, navigate])

  async function handleAdmit() {
    setIsAdmitting(true)
    setAdmitError('')
    try {
      await admitCandidate(sessionId)
      await load()
    } catch (admitFailure) {
      setAdmitError(admitFailure.message)
    } finally {
      setIsAdmitting(false)
    }
  }

  async function handleEnd() {
    setIsEnding(true)
    setEndError('')
    try {
      await endInterview(sessionId)
      room.leave()
      navigate(backTo, { replace: true })
    } catch (endFailure) {
      setEndError(endFailure.message)
      setIsEnding(false)
    }
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-mist p-6">
        <section className="flex max-w-md flex-col items-start gap-4 rounded-card bg-white p-8 shadow-card">
          <CircleAlert className="size-8 text-danger" aria-hidden="true" />
          <h1 className="text-xl font-extrabold tracking-tight">The room could not be opened</h1>
          <p>{error}</p>
          <Button variant="outline" to={backTo}>
            Back to Interviews
          </Button>
        </section>
      </div>
    )
  }
  if (!info) {
    return (
      <div role="status" aria-label="Opening the room" className="flex min-h-screen flex-col gap-5 bg-mist p-6">
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-[70vh] w-full rounded-card" />
      </div>
    )
  }

  const { interview } = info
  const isStarted = interview.status === 'in_progress'
  return (
    <div className="flex min-h-screen flex-col bg-mist lg:h-screen">
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-b border-line bg-white px-5 py-2 lg:h-15 lg:py-0">
        <div className="flex items-center gap-2.5">
          <Link
            to={backTo}
            aria-label="Back to Interviews"
            className="flex size-9 items-center justify-center rounded-xl text-body hover:bg-mist"
          >
            <ArrowLeft className="size-4.5" aria-hidden="true" />
          </Link>
          <div>
            <h1 className="text-base font-extrabold tracking-tight">
              Interview with {interview.candidate_name}
            </h1>
            <p className="text-[12.5px]">
              {info.job_title} · {info.job_code}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          {isStarted ? (
            <StatusChip tone="danger">Live</StatusChip>
          ) : (
            <StatusChip tone="amber">Not started</StatusChip>
          )}
          <Timer interview={interview} now={now} />
          <ConnectionChip state={room.state} />
        </div>
      </header>

      {/* The middle column is as wide as the 16:9 video that fits above the
          transcript, never more than 52% of the row; the candidate and chat
          columns share the rest, 23 to 25. With a 60px header and 16px
          padding the middle is 100vh - 92px tall, and the transcript keeps
          at least 250px or 41% of it, so the video is at most
          min(100vh - 354px, 59vh - 66px) tall. */}
      <div className="grid min-h-0 flex-1 gap-4 p-4 lg:grid-cols-[minmax(290px,23fr)_minmax(0,min(52%,calc(min(100vh_-_354px,59vh_-_66px)*16/9)))_minmax(310px,25fr)] lg:grid-rows-[minmax(0,1fr)]">
        <CandidatePanel
          sessionId={interview.id}
          candidateName={interview.candidate_name}
          candidate={candidate}
        />

        <div className="flex min-h-0 min-w-0 flex-col gap-3 lg:overflow-hidden">
          <AdmitBar
            interview={interview}
            now={now}
            isAdmitting={isAdmitting}
            error={admitError}
            onAdmit={handleAdmit}
          />
          {room.notice && (
            <p className="rounded-2xl bg-amber-soft px-4 py-2.5 text-sm text-amber">{room.notice}</p>
          )}
          <VideoStage
            room={room}
            selfName="You"
            otherName={interview.candidate_name}
            waitingText={isStarted ? `${interview.candidate_name} is joining…` : 'Not joined yet'}
            heading={`Interview with ${interview.candidate_name}`}
            clock={isStarted ? elapsed(interview.started_at, now) : null}
            frameClassName="aspect-video"
            controlsInside
            renderControls={(place) => (
              <RoomControls
                room={room}
                endLabel={isStarted ? 'End interview' : 'Leave room'}
                isEnding={isEnding}
                isOverlay={place === 'overlay'}
                variant={place === 'inside' ? 'compact' : 'full'}
                onEnd={() => {
                  leaveFullScreen()
                  setEndError('')
                  setIsConfirmingEnd(true)
                }}
              />
            )}
          />
          <LiveTranscript
            transcript={transcript}
            candidateName={interview.candidate_name}
            startedAt={interview.started_at}
            className="min-h-60 flex-1 lg:min-h-0"
          />
        </div>

        <ChatPanel
          sessionId={interview.id}
          candidateName={interview.candidate_name}
          room={room}
        />
      </div>

      {isConfirmingEnd && (
        <ConfirmDialog
          title={isStarted ? 'End the interview for both of you?' : 'Leave the room?'}
          cancelLabel="Stay"
          confirmLabel={isStarted ? 'End interview' : 'Leave'}
          busyLabel="Ending…"
          isBusy={isEnding}
          error={endError}
          onConfirm={
            isStarted
              ? handleEnd
              : () => {
                  room.leave()
                  navigate(backTo)
                }
          }
          onCancel={() => setIsConfirmingEnd(false)}
        >
          {isStarted ? (
            <p>
              The video room closes and {interview.candidate_name}&apos;s link stops working. The
              interview is marked as completed.
            </p>
          ) : (
            <p>
              The interview has not started, so it stays scheduled. You can come back from the
              Interviews tab.
            </p>
          )}
        </ConfirmDialog>
      )}
    </div>
  )
}
