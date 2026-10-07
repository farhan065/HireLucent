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

const FIELD_CLASS =
  'w-full rounded-xl border-[1.5px] border-line px-3 py-2.5 text-[15px] text-navy'

// The form shown when the interviewer edits a draft directly.
function DescriptionEditor({ item, onSave, onCancel }) {
  const [title, setTitle] = useState(item.title)
  const [text, setText] = useState(item.text)
  const isValid = title.trim().length >= 3 && text.trim().length >= 50

  return (
    <div className="flex flex-col gap-3 px-4 py-3.5">
      <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
        Job title
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          className={`${FIELD_CLASS} font-normal`}
        />
      </label>
      <label className="flex flex-col gap-1.5 text-sm font-semibold text-navy">
        Description
        <textarea
          rows={14}
          value={text}
          onChange={(event) => setText(event.target.value)}
          className={`${FIELD_CLASS} font-normal leading-relaxed`}
        />
      </label>
      <p className="text-[13px]">
        Lines starting with ## are section headings, and lines starting with - are bullet
        points.
      </p>
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button variant="soft" onClick={onCancel}>
          Cancel
        </Button>
        <Button disabled={!isValid} onClick={() => onSave(title.trim(), text.trim())}>
          Save as a new draft
        </Button>
      </div>
    </div>
  )
}

// A job description draft in the conversation. The newest draft is shown in
// full with its actions. Older and approved drafts are collapsed.
export default function DescriptionCard({ item, canAct, canEdit, onApprove, onEdit }) {
  const isCurrent = item.status === 'waiting' || item.status === 'writing'
  const [isOpen, setIsOpen] = useState(isCurrent)
  const [isEditing, setIsEditing] = useState(false)
  const chip = STATUS_CHIPS[item.status]
  const showActions = item.status === 'waiting' && canAct

  function handleSave(title, text) {
    setIsEditing(false)
    onEdit(title, text)
  }

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
        <StatusChip tone={chip.tone}>{isEditing ? 'Editing' : chip.label}</StatusChip>
      </header>

      {isEditing ? (
        <DescriptionEditor
          item={item}
          onSave={handleSave}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <div className="px-4 py-3.5 text-[15px]">
          <h3 className="text-lg font-bold">{item.title}</h3>
          {isOpen || isCurrent ? (
            <>
              <Markdown>{item.text}</Markdown>
              {item.status === 'writing' && <WritingCaret />}
            </>
          ) : (
            <p className="mt-1.5 line-clamp-2 leading-relaxed">
              {item.text.replace(/[#*]/g, '')}
            </p>
          )}
          {item.from_knowledge_base && (
            <div className="mt-3">
              <StatusChip tone="source">Source: Knowledge Base</StatusChip>
            </div>
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
      )}

      {showActions && !isEditing && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <span className="text-sm">or type what to change below</span>
          <div className="flex flex-wrap gap-2.5">
            {canEdit && (
              <Button variant="outline" onClick={() => setIsEditing(true)}>
                Edit
              </Button>
            )}
            <Button onClick={onApprove}>Approve description</Button>
          </div>
        </footer>
      )}
    </article>
  )
}
