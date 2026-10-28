import { SendHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

const MAX_LENGTH = 1000
// Web addresses in a message become links that open in a new tab.
const LINK = /(https?:\/\/[^\s<>"]+)/g

function time(at) {
  return new Date(at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
}

function TextWithLinks({ text, isMine }) {
  return text.split(LINK).map((part, index) =>
    index % 2 === 1 ? (
      <a
        key={index}
        href={part}
        target="_blank"
        rel="noopener noreferrer"
        className={`break-all underline ${isMine ? 'text-white hover:text-white/85' : ''}`}
      >
        {part}
      </a>
    ) : (
      part
    ),
  )
}

function Message({ message }) {
  const { isMine } = message
  return (
    <div className={`flex max-w-[88%] flex-col gap-0.75 ${isMine ? 'items-end self-end' : 'self-start'}`}>
      <span className="px-0.5 text-[11.5px]">
        {isMine ? 'You' : <strong className="font-bold text-navy">{message.name}</strong>} ·{' '}
        {time(message.at)}
      </span>
      <div
        className={`whitespace-pre-wrap break-words px-3 py-2 text-[13.5px] leading-snug ${
          isMine
            ? 'rounded-[14px_4px_14px_14px] bg-brand text-white'
            : 'rounded-[4px_14px_14px_14px] bg-mist text-navy'
        }`}
      >
        <TextWithLinks text={message.text} isMine={isMine} />
      </div>
    </div>
  )
}

// Live text messages between the interviewer and the candidate, sent
// straight between the two browsers. They are not saved: they last while
// the room page is open. "otherName" is who receives them; "hint" says who
// can see them.
export default function RoomMessages({ room, otherName, hint, waitingText }) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [isSending, setIsSending] = useState(false)
  const endRef = useRef(null)
  const canSend = room.state === 'connected' && room.isRemoteHere

  // Keep the newest message in view.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [room.messages])

  async function handleSubmit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || !canSend || isSending) return
    setIsSending(true)
    setError('')
    try {
      await room.sendMessage(text)
      setDraft('')
    } catch (sendError) {
      setError(sendError.message)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <p className="shrink-0 border-b border-[#eef2f9] px-4 py-2 text-xs">{hint}</p>
      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto px-3.5 py-3 [&>*]:shrink-0">
        {room.messages.length === 0 ? (
          <p className="m-auto max-w-60 text-center text-[13.5px] leading-relaxed">
            {canSend ? `Send ${otherName} a message, for example a link.` : waitingText}
          </p>
        ) : (
          room.messages.map((message) => <Message key={message.id} message={message} />)
        )}
        <div ref={endRef} />
      </div>
      <form
        onSubmit={handleSubmit}
        className="flex shrink-0 flex-col gap-1.5 border-t border-[#eef2f9] px-3 pb-3 pt-2.5"
      >
        {error && (
          <p role="alert" className="text-xs font-semibold text-danger">
            {error}
          </p>
        )}
        <div className="flex items-center gap-2">
          <label htmlFor="room-message" className="sr-only">
            Message {otherName}
          </label>
          <input
            id="room-message"
            type="text"
            value={draft}
            maxLength={MAX_LENGTH}
            disabled={!canSend}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={canSend ? `Message ${otherName}…` : waitingText}
            className="min-h-10.5 min-w-0 flex-1 rounded-xl border-[1.5px] border-line px-3 text-[13.5px] text-navy placeholder:text-body/70 focus:border-brand focus:outline-none disabled:bg-mist"
          />
          <button
            type="submit"
            aria-label="Send"
            disabled={!draft.trim() || !canSend || isSending}
            className="flex size-10.5 shrink-0 items-center justify-center rounded-full bg-brand text-white hover:bg-brand-dark disabled:opacity-50"
          >
            <SendHorizontal className="size-4.5" aria-hidden="true" />
          </button>
        </div>
      </form>
    </div>
  )
}
