import { CircleAlert } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router'
import Button from '../components/Button.jsx'
import Composer from '../components/chat/Composer.jsx'
import JobBrief from '../components/chat/JobBrief.jsx'
import JobSwitcher from '../components/chat/JobSwitcher.jsx'
import Timeline from '../components/chat/Timeline.jsx'
import JobTabs from '../components/jobs/JobTabs.jsx'
import { useConversation } from '../hooks/useConversation.js'
import { useInterviews } from '../hooks/useInterviews.js'
import { useJob } from '../hooks/useJob.js'
import { countToday, countWaiting } from '../lib/interviews.js'
import { jobStage } from '../lib/jobs.js'
import { getLastThread, setLastThread } from '../lib/stages.js'

const APPROVE_MESSAGE = 'I approve this job description.'
const INTERVIEW_CARDS = ['schedule', 'reschedule', 'cancel_interview']
const INTERVIEW_PLACEHOLDER =
  'Or type what to change, for example "make the message more formal"'

const STATUS_LABELS = {
  connecting: { text: 'Connecting…', dot: 'bg-warning' },
  connected: { text: 'Connected', dot: 'bg-success' },
  disconnected: { text: 'Reconnecting…', dot: 'bg-danger' },
}

// What the brief shows before the conversation has any content.
const EMPTY_VIEW = { items: [], brief: {}, stage: 'describing' }

function EmptyState() {
  return (
    <div className="m-auto flex max-w-md flex-col items-center gap-3 py-16 text-center">
      <img src="/favicon.svg" alt="" className="size-14" />
      <h2 className="text-2xl font-extrabold tracking-tight">What role are you hiring for?</h2>
      <p className="leading-relaxed">
        Describe it in a sentence or two. I will draft the job description, and nothing is
        saved until you confirm.
      </p>
    </div>
  )
}

// The AI Agent: one conversation that creates and manages one job.
export default function AssistantPage() {
  const { threadId } = useParams()
  const location = useLocation()
  const isFresh = Boolean(location.state?.fresh)

  // Opening the assistant from the sidebar returns to the last conversation.
  const lastThread = getLastThread()
  if (!threadId && !isFresh && lastThread) {
    return <Navigate to={`/app/assistant/${lastThread}`} replace />
  }

  // The key decides when the conversation screen starts afresh: for every
  // different conversation and for "+ New job", but not at the moment a new
  // conversation receives its address.
  const key = location.state?.conversationKey ?? threadId ?? location.key
  return (
    <Conversation
      key={key}
      threadId={threadId}
      conversationKey={key}
      firstMessage={location.state?.firstMessage}
    />
  )
}

function Conversation({ threadId, conversationKey, firstMessage }) {
  const navigate = useNavigate()
  const conversation = useConversation(
    threadId,
    (newThreadId) =>
      navigate(`/app/assistant/${newThreadId}`, {
        replace: true,
        state: { conversationKey },
      }),
    firstMessage,
  )
  const { view, status, error, isBusy } = conversation
  const connection = STATUS_LABELS[status]
  const stage = view?.stage ?? 'describing'
  const isInterviewCardWaiting = (view?.items ?? []).some(
    (item) => INTERVIEW_CARDS.includes(item.kind) && item.status === 'waiting',
  )
  const isEmpty = !view && !isBusy
  // Once the job is saved, its stage tabs are shown above the conversation.
  // The job loads again when it is published and after each interview
  // change approved here, so its stage stays current.
  const changes = (view?.items ?? []).filter((item) => item.result).length
  const saved = useJob(view?.brief.job_id, `${view?.brief.post_url}|${changes}`)
  // A published job's interviews: they load again whenever the conversation
  // changes, for example after the interviewer approves a schedule.
  const interviews = useInterviews(
    saved.job?.status === 'published' ? saved.job.id : null,
    view?.items.length,
  )
  // The same rule as the server: any interview that is not cancelled locks
  // the requirements and weights.
  const hasInterviews = (interviews.interviews ?? []).some(
    (item) => item.status !== 'cancelled',
  )
  const composerRef = useRef(null)

  // Remember this conversation, or forget it if it could not be opened.
  useEffect(() => {
    if (view) setLastThread(view.thread_id)
    else if (threadId && error) setLastThread(null)
  }, [view, threadId, error])

  return (
    <div className="-m-6 flex h-screen flex-col md:-m-10">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-white px-6 py-3.5">
        <JobSwitcher title={view?.title ?? 'New job'} currentThreadId={threadId} />
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-[13px]" role="status">
            <span className={`size-2 rounded-full ${connection.dot}`} aria-hidden="true" />
            {connection.text}
          </span>
          <Button variant="outline" to="/app/assistant" state={{ fresh: true }}>
            + New job
          </Button>
        </div>
      </header>
      {saved.job && (
        <div className="border-b border-line bg-white px-6 pt-3.5">
          <JobTabs
            job={saved.job}
            threadId={view.thread_id}
            waiting={saved.waiting}
            today={countToday(interviews.interviews, interviews.now)}
            inWaitingRoom={countWaiting(interviews.interviews)}
            current="post"
          />
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-1 flex-col overflow-y-auto px-6 py-6">
            <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col">
              {isEmpty ? (
                <EmptyState />
              ) : (
                <Timeline
                  items={view?.items ?? []}
                  pendingText={conversation.pendingText}
                  streamingText={conversation.streamingText}
                  isBusy={isBusy}
                  canEdit={stage === 'reviewing_description'}
                  onApprove={() => conversation.sendMessage(APPROVE_MESSAGE)}
                  onConfirm={(edited) =>
                    conversation.submitApproval(true, edited ? { arguments: edited } : {})
                  }
                  onEdit={conversation.editDescription}
                  onPublish={() => conversation.submitApproval(true)}
                  onEditPost={(changes) =>
                    conversation.submitApproval(false, { arguments: changes })
                  }
                  jobId={view?.brief.job_id}
                  onApproveAction={() => conversation.submitApproval(true)}
                  onEditAction={(changes) =>
                    conversation.submitApproval(false, { arguments: changes })
                  }
                  onRejectAction={(feedback) =>
                    conversation.submitApproval(false, { feedback })
                  }
                  onRequestChanges={() => composerRef.current?.focus()}
                />
              )}
            </div>
          </div>

          <div className="px-6 pb-5">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-2.5">
              {error && (
                <p
                  role="alert"
                  className="flex items-center gap-2 rounded-2xl bg-danger-soft px-4 py-3 text-sm font-semibold text-danger"
                >
                  <CircleAlert className="size-5 shrink-0" aria-hidden="true" />
                  {error}
                </p>
              )}
              <Composer
                inputRef={composerRef}
                stage={stage}
                isDisabled={isBusy || status !== 'connected'}
                onSend={conversation.sendMessage}
                placeholder={isInterviewCardWaiting ? INTERVIEW_PLACEHOLDER : undefined}
              />
            </div>
          </div>
        </div>

        <JobBrief
          view={view ?? EMPTY_VIEW}
          stage={saved.job ? jobStage(saved.job) : null}
          isLocked={hasInterviews}
          onProfileSaved={() => {
            conversation.reloadView()
            saved.reload()
          }}
        />
      </div>
    </div>
  )
}
