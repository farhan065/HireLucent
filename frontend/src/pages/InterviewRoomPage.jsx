import { ArrowLeft, Bot, CircleAlert, Lightbulb, MessageSquareText, UserRound } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import Button from '../components/Button.jsx'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import CvFacts from '../components/jobs/CvFacts.jsx'
import { ViewCvLink } from '../components/jobs/candidates.jsx'
import ConnectionChip from '../components/room/ConnectionChip.jsx'
import RoomControls from '../components/room/RoomControls.jsx'
import VideoStage from '../components/room/VideoStage.jsx'
import Skeleton from '../components/Skeleton.jsx'
import StatusChip from '../components/StatusChip.jsx'
import { useRoom } from '../hooks/useRoom.js'
import { apiRequest } from '../lib/api.js'
import { clock, minutesBetween, scoreLabel, waitingFor } from '../lib/interviews.js'
import { admitCandidate, elapsed, endInterview, openRoom, readInterview } from '../lib/room.js'

const REFRESH_MS = 3 * 1000

function useNow(intervalMs) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

// "12:48 of 45:00 · ends 3:45 PM", amber once the planned end has passed.
function Timer({ interview, now }) {
  const length = minutesBetween(interview.scheduled_start, interview.scheduled_end)
  if (!interview.started_at) {
    return <span className="text-sm">Starts at {clock(interview.scheduled_start)}</span>
  }
  const over = Math.floor((now - new Date(interview.scheduled_end)) / 60000)
  return (
    <span
      className={`font-display text-[15px] font-bold tabular-nums ${over > 0 ? 'text-amber' : 'text-navy'}`}
    >
      {elapsed(interview.started_at, now)} of {length}:00 ·{' '}
      {over > 0 ? `${over} min over` : `ends ${clock(interview.scheduled_end)}`}
    </span>
  )
}

// A column the next steps fill in, shown now so the room keeps its shape.
function ComingSoon({ icon: Icon, title, note, children }) {
  return (
    <section className="flex min-h-0 flex-col overflow-hidden rounded-card border border-line bg-white shadow-card">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
        <span className="flex items-center gap-2 font-display text-[15px] font-bold text-navy">
          <Icon className="size-4.5 text-brand" aria-hidden="true" />
          {title}
        </span>
        {note && <span className="text-xs">{note}</span>}
      </header>
      <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-8 text-center text-sm">
        {children}
      </div>
    </section>
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
  { key: 'info', label: 'Candidate info', icon: UserRound },
  { key: 'questions', label: 'Suggested questions', icon: Lightbulb },
]

// The candidate's screening summary and CV facts, with the full CV.
function CandidatePanel({ candidate }) {
  const [tab, setTab] = useState('info')
  return (
    <section className="flex min-h-0 flex-col overflow-hidden rounded-card border border-line bg-white shadow-card">
      <div role="tablist" aria-label="About the candidate" className="flex border-b border-line">
        {TABS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={tab === item.key}
            onClick={() => setTab(item.key)}
            className={`-mb-px flex min-h-12 flex-1 items-center justify-center gap-1.5 whitespace-nowrap border-b-[3px] px-2 text-[13.5px] font-semibold ${
              tab === item.key ? 'border-brand text-navy' : 'border-transparent text-body hover:text-navy'
            }`}
          >
            <item.icon className="size-4" aria-hidden="true" />
            {item.label}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {tab === 'questions' ? (
          <p className="py-8 text-center text-sm">
            Questions prepared from this candidate&apos;s CV arrive with the next step.
          </p>
        ) : !candidate ? (
          <Skeleton className="h-64 w-full" />
        ) : (
          <div className="flex flex-col gap-2">
            <h2 className="text-lg font-extrabold tracking-tight">{candidate.full_name}</h2>
            <p className="text-[13px]">
              {scoreLabel(candidate.scores?.final_score)}
              {candidate.scores?.final_rank && ` · rank ${candidate.scores.final_rank}`}
            </p>
            {candidate.scores?.summary && (
              <p className="text-sm leading-relaxed text-navy">{candidate.scores.summary}</p>
            )}
            {candidate.cv_facts && <CvFacts facts={candidate.cv_facts} />}
            <div className="mt-3 border-t border-line pt-3">
              <ViewCvLink candidateId={candidate.id} />
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

// The interviewer's interview room: the video in the middle, the live
// transcript on the left and the candidate on the right. The transcript
// (Module 5), the chat and the suggested questions (next step) fill in later.
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
  const room = useRoom(connection)

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
  // Ended somewhere else, for example in another tab.
  useEffect(() => {
    if (status === 'completed' || status === 'cancelled') navigate(backTo, { replace: true })
  }, [status, backTo, navigate])

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
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-white px-6 py-3">
        <div className="flex items-center gap-4">
          <Link
            to={backTo}
            aria-label="Back to Interviews"
            className="flex size-10 items-center justify-center rounded-xl text-body hover:bg-mist"
          >
            <ArrowLeft className="size-5" aria-hidden="true" />
          </Link>
          <div>
            <h1 className="text-lg font-extrabold tracking-tight">
              Interview with {interview.candidate_name}
            </h1>
            <p className="text-[13px]">
              {info.job_title} · {info.job_code}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {isStarted ? (
            <StatusChip tone="danger">Live</StatusChip>
          ) : (
            <StatusChip tone="amber">Not started</StatusChip>
          )}
          <Timer interview={interview} now={now} />
          <ConnectionChip state={room.state} />
        </div>
      </header>

      <div className="grid min-h-0 flex-1 gap-5 p-5 lg:grid-cols-[minmax(240px,300px)_minmax(0,1fr)_minmax(280px,340px)]">
        <ComingSoon icon={MessageSquareText} title="Live transcript" note="Only you see this">
          <p className="font-semibold text-navy">The live transcript appears here</p>
          <p>Each person&apos;s words are written down once speech-to-text is added.</p>
        </ComingSoon>

        <div className="flex min-h-0 min-w-0 flex-col gap-4">
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
          {room.error && (
            <p role="alert" className="rounded-2xl bg-danger-soft px-4 py-2.5 text-sm font-semibold text-danger">
              {room.error}
            </p>
          )}
          <VideoStage
            room={room}
            selfName="You"
            otherName={interview.candidate_name}
            waitingText={isStarted ? `${interview.candidate_name} is joining…` : 'Not joined yet'}
          />
          <RoomControls
            room={room}
            endLabel={isStarted ? 'End interview' : 'Leave room'}
            isEnding={isEnding}
            onEnd={() => {
              setEndError('')
              setIsConfirmingEnd(true)
            }}
          />
          <div className="h-44 shrink-0">
            <ComingSoon icon={Bot} title="Chat" note="AI Agent · read-only during the interview">
              <p>Ask the AI Agent about the job, this candidate or the question bank. Arrives with the next step.</p>
            </ComingSoon>
          </div>
        </div>

        <CandidatePanel candidate={candidate} />
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
