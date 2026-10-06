import { ChevronDown } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { apiRequest } from '../../lib/api.js'
import { STAGE_LABELS } from '../../lib/stages.js'

// The job's name at the top of the assistant. Clicking it lists all of the
// interviewer's conversations, so they can move to another job.
export default function JobSwitcher({ title, currentThreadId }) {
  const [conversations, setConversations] = useState(null)
  const isOpen = conversations !== null

  async function toggle() {
    if (isOpen) {
      setConversations(null)
      return
    }
    setConversations(await apiRequest('/chat/conversations').catch(() => []))
  }

  return (
    <div className="relative min-w-0">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={toggle}
        className="flex min-h-11 max-w-full items-center gap-2.5 rounded-2xl border-[1.5px] border-line bg-white px-4 font-display text-[17px] font-bold text-navy hover:border-brand"
      >
        <span className="truncate">{title}</span>
        <ChevronDown className="size-4 shrink-0 text-body" aria-hidden="true" />
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute left-0 top-full z-10 mt-2 flex max-h-96 w-80 max-w-[90vw] animate-rise-in flex-col overflow-y-auto rounded-2xl border border-line bg-white p-2 shadow-card"
        >
          {conversations.length === 0 && (
            <p className="px-3 py-2 text-sm">No conversations yet.</p>
          )}
          {conversations.map((conversation) => (
            <Link
              key={conversation.thread_id}
              role="menuitem"
              to={`/app/assistant/${conversation.thread_id}`}
              onClick={() => setConversations(null)}
              className={`flex flex-col gap-0.5 rounded-xl px-3 py-2.5 hover:bg-mist ${
                conversation.thread_id === currentThreadId ? 'bg-tint' : ''
              }`}
            >
              <span className="truncate text-[15px] font-semibold text-navy">
                {conversation.title}
              </span>
              <span className="text-[13px]">{STAGE_LABELS[conversation.stage]}</span>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
