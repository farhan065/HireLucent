import { useState } from 'react'
import Button from '../Button.jsx'
import StatusChip from '../StatusChip.jsx'
import Markdown from './Markdown.jsx'
import { WritingCaret } from './MessageBubble.jsx'

const STATUS_CHIPS = {
  waiting: { tone: 'info', label: 'Waiting for your approval' },
  approved: { tone: 'success', label: 'Approved by you' },
  replaced: { tone: 'neutral', label: 'Replaced' },
  writing: { tone: 'neutral', label: 'Writing…' },
}

// A job description draft in the conversation. The newest draft is shown in
// full with its actions. Older and approved drafts are collapsed.
export default function DescriptionCard({ item, canAct, onApprove }) {
  const isCurrent = item.status === 'waiting' || item.status === 'writing'
  const [isOpen, setIsOpen] = useState(isCurrent)
  const chip = STATUS_CHIPS[item.status]
  const showActions = item.status === 'waiting' && canAct

  return (
    <article
      className={`overflow-hidden rounded-2xl border bg-white ${
        item.status === 'waiting' ? 'border-brand shadow-card' : 'border-line'
      }`}
    >
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
        <span className="font-display text-[15px] font-bold text-navy">
          Job description{item.version ? ` · draft ${item.version}` : ''}
        </span>
        <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
      </header>

      <div className="px-4 py-3.5 text-[15px]">
        <h3 className="text-lg font-bold">{item.title}</h3>
        {isOpen || isCurrent ? (
          <>
            <Markdown>{item.text}</Markdown>
            {item.status === 'writing' && <WritingCaret />}
          </>
        ) : (
          <p className="mt-1.5 line-clamp-2 leading-relaxed">{item.text.replace(/[#*]/g, '')}</p>
        )}
        {!isCurrent && (
          <button
            type="button"
            onClick={() => setIsOpen((open) => !open)}
            className="mt-2 text-sm font-semibold text-brand hover:text-brand-dark"
          >
            {isOpen ? 'Show less' : 'Show the full description'}
          </button>
        )}
      </div>

      {showActions && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <span className="text-sm">or type what to change below</span>
          <Button onClick={onApprove}>Approve description</Button>
        </footer>
      )}
    </article>
  )
}
