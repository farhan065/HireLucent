import { Bot, SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { readChat, sendChat } from '../../lib/room.js'
import Markdown from '../chat/Markdown.jsx'
import Skeleton from '../Skeleton.jsx'

const MAX_LENGTH = 2000

function Typing() {
  return (
    <div
      role="status"
      aria-label="The AI Agent is replying"
      className="flex items-center gap-1 self-start rounded-[14px_14px_14px_4px] bg-mist px-3 py-3"
    >
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="size-1.5 animate-bounce rounded-full bg-[#8fa3c7]"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  )
}

function Message({ message }) {
  if (message.role === 'interviewer') {
    return (
      <div className="max-w-[85%] self-end whitespace-pre-wrap break-words rounded-[14px_14px_4px_14px] bg-brand px-3 py-2 text-[13.5px] leading-snug text-white">
        {message.text}
      </div>
    )
  }
  return (
    <div className="max-w-[92%] self-start break-words rounded-[14px_14px_14px_4px] bg-mist px-3 py-2 text-[13.5px] text-navy [&>div>*:first-child]:mt-0">
      {message.from_question_bank && (
        <span className="mb-1 inline-block rounded-full bg-teal-soft px-2 py-px text-[11.5px] font-bold text-teal">
          Question bank
        </span>
      )}
      <div>
        <Markdown>{message.text}</Markdown>
      </div>
    </div>
  )
}

// The interview room's chat with the AI Agent. It is read-only: the agent
// answers about the job, this candidate and the question bank, and cannot
// change anything. The chat is kept with the interview.
export default function InterviewChat({ sessionId, candidateName }) {
  const [messages, setMessages] = useState(null)
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef(null)
  const firstName = candidateName.split(/\s+/)[0] || candidateName

  useEffect(() => {
    let isCurrent = true
    readChat(sessionId)
      .then((loaded) => isCurrent && setMessages(loaded))
      .catch((loadError) => {
        if (!isCurrent) return
        setMessages([])
        setError(loadError.message)
      })
    return () => {
      isCurrent = false
    }
  }, [sessionId])

  // Keep the newest message in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, isSending])

  async function handleSubmit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return
    const before = messages ?? []
    setMessages([...before, { role: 'interviewer', text }])
    setDraft('')
    setError('')
    setIsSending(true)
    try {
      setMessages(await sendChat(sessionId, text))
    } catch (sendError) {
      setMessages(before)
      setDraft(text)
      setError(sendError.message)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <section className="flex min-h-80 flex-col overflow-hidden rounded-card border border-line bg-white shadow-card lg:min-h-0">
      <header className="flex shrink-0 flex-col gap-0.5 border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-2 text-[15px] font-bold">
          <Bot className="size-4.5 text-brand" aria-hidden="true" />
          Chat with the AI Agent
        </h2>
        <span className="text-xs">Read-only during the interview: it answers, it changes nothing.</span>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-3 [&>*]:shrink-0">
        {messages === null ? (
          <Skeleton className="h-24 w-full" />
        ) : messages.length === 0 && !isSending ? (
          <p className="m-auto max-w-60 text-center text-[13.5px] leading-relaxed">
            Ask about the job, {firstName} or the question bank.
          </p>
        ) : (
          messages.map((message, index) => <Message key={index} message={message} />)
        )}
        {isSending && <Typing />}
        <div ref={endRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex shrink-0 flex-col gap-1.5 border-t border-[#eef2f9] px-3 pb-3 pt-2.5">
        {error && (
          <p role="alert" className="text-xs font-semibold text-danger">
            {error}
          </p>
        )}
        <div className="flex items-center gap-2">
          <label htmlFor="interview-chat" className="sr-only">
            Ask the AI Agent
          </label>
          <input
            id="interview-chat"
            type="text"
            value={draft}
            maxLength={MAX_LENGTH}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={`Ask about the job, ${firstName} or the question bank…`}
            className="min-h-10.5 min-w-0 flex-1 rounded-xl border-[1.5px] border-line px-3 text-[13.5px] text-navy placeholder:text-body/70 focus:border-brand focus:outline-none"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={!draft.trim() || isSending}
            className="flex size-10.5 shrink-0 items-center justify-center rounded-full bg-brand text-white hover:bg-brand-dark disabled:opacity-50"
          >
            <SendHorizontal className="size-4.5" aria-hidden="true" />
          </button>
        </div>
      </form>
    </section>
  )
}
