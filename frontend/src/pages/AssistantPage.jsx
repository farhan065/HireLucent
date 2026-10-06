import { CircleAlert } from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router'
import Button from '../components/Button.jsx'
import Composer from '../components/chat/Composer.jsx'
import Timeline from '../components/chat/Timeline.jsx'
import { useConversation } from '../hooks/useConversation.js'

const APPROVE_MESSAGE = 'I approve this job description.'

const STATUS_LABELS = {
  connecting: { text: 'Connecting…', dot: 'bg-warning' },
  connected: { text: 'Connected', dot: 'bg-success' },
  disconnected: { text: 'Reconnecting…', dot: 'bg-danger' },
}

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

// The Hiring Assistant: one conversation that creates and manages one job.
export default function AssistantPage() {
  const { threadId } = useParams()
  const location = useLocation()
  // The key decides when the conversation screen starts afresh: for every
  // different conversation and for "+ New job", but not at the moment a new
  // conversation receives its address.
  const key = location.state?.conversationKey ?? threadId ?? location.key
  return <Conversation key={key} threadId={threadId} conversationKey={key} />
}

function Conversation({ threadId, conversationKey }) {
  const navigate = useNavigate()
  const conversation = useConversation(threadId, (newThreadId) =>
    navigate(`/app/assistant/${newThreadId}`, {
      replace: true,
      state: { conversationKey },
    }),
  )
  const { view, status, error, isBusy } = conversation
  const connection = STATUS_LABELS[status]
  const stage = view?.stage ?? 'describing'
  const isEmpty = !view && !isBusy

  return (
    <div className="-m-6 flex h-screen flex-col md:-m-10">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-white px-6 py-4">
        <h1 className="text-xl font-extrabold tracking-tight">{view?.title ?? 'New job'}</h1>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5 text-[13px]" role="status">
            <span className={`size-2 rounded-full ${connection.dot}`} aria-hidden="true" />
            {connection.text}
          </span>
          <Button variant="outline" to="/app/assistant">
            + New job
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col">
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
                onApprove={() => conversation.sendMessage(APPROVE_MESSAGE)}
                onConfirm={() => conversation.submitApproval(true)}
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
              stage={stage}
              isDisabled={isBusy || status !== 'connected'}
              onSend={conversation.sendMessage}
            />
          </div>
        </div>
      </div>
    </div>
  )
}
