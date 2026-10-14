import { CalendarDays, CircleCheck, CircleX, Lock, Mail, TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import { messageProblem } from '../../lib/interviews.js'
import { EditMessageButton, EmailText, MessageField } from '../interviews/EmailMessage.jsx'

// Shared pieces of the interview cards in the AI Agent conversation.

const SMALL_BUTTON =
  'inline-flex min-h-10 items-center justify-center rounded-full px-4 font-display text-sm font-bold transition-colors disabled:cursor-not-allowed disabled:bg-line disabled:text-body'

const CARD_ICONS = { mail: Mail, calendar: CalendarDays, lock: Lock }

// The message editor on a card. Saving sends the message back to the server,
// which checks it and returns the card with the new preview.
function MessageEditor({ email, draft, onDraft, onSave }) {
  const problem = messageProblem(draft)
  return (
    <div className="flex flex-col gap-2.5 border-b border-line/60 px-3.5 py-3.5">
      <MessageField
        label={email.fieldLabel}
        value={draft}
        hint={email.hint}
        onChange={onDraft}
      />
      {problem && draft.length > 0 && (
        <p role="alert" className="text-[13px] font-semibold text-danger">
          {problem}
        </p>
      )}
      <div className="flex justify-end gap-2.5">
        <button
          type="button"
          onClick={() => onDraft(null)}
          className={`${SMALL_BUTTON} bg-tint text-brand-dark hover:bg-lavender`}
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={Boolean(problem)}
          onClick={onSave}
          className={`${SMALL_BUTTON} bg-brand text-white hover:bg-brand-dark`}
        >
          Save message
        </button>
      </div>
    </div>
  )
}

// What happens when the interviewer approves, and the email that is sent.
// "email" describes the email: its preview, the message used in it and the
// wording around the editor. "draft" is the message being edited, or null.
export function WhenYouApprove({ lines, email, draft = null, onDraft, onSaveMessage }) {
  const [isOpen, setIsOpen] = useState(false)
  const isEditing = draft !== null
  const canEdit = Boolean(onSaveMessage)

  function save() {
    const text = draft.trim()
    onDraft(null)
    if (text !== email.message.trim()) onSaveMessage(text)
  }

  return (
    <div className="mx-4 mb-4 flex flex-col gap-2 rounded-2xl bg-mist px-4 py-3.5 text-sm">
      <span className="font-semibold text-navy">When you approve</span>
      {lines.map(({ icon, text }) => {
        const Icon = CARD_ICONS[icon]
        return (
          <span key={text} className="flex items-start gap-2.5">
            <Icon className="mt-px size-4.5 shrink-0 text-brand" aria-hidden="true" />
            {text}
          </span>
        )
      })}
      {email?.preview && (
        <>
          <button
            type="button"
            aria-expanded={isOpen || isEditing}
            onClick={() => {
              setIsOpen((open) => !open)
              onDraft?.(null)
            }}
            className="self-start pt-1 font-semibold text-brand hover:text-brand-dark"
          >
            {isOpen || isEditing ? `Hide the ${email.noun}` : `Show the ${email.noun}`}
          </button>
          {(isOpen || isEditing) && (
            <div className="flex flex-col rounded-xl border border-line bg-white">
              {email.title && (
                <div className="flex flex-wrap items-center justify-between gap-2.5 border-b border-line/60 px-3.5 py-3">
                  <span className="font-semibold text-navy">{email.title}</span>
                  <span className="text-[13px]">
                    Title: <strong className="text-navy">{email.preview.subject}</strong>
                  </span>
                </div>
              )}
              {isEditing && (
                <MessageEditor email={email} draft={draft} onDraft={onDraft} onSave={save} />
              )}
              <div className="flex flex-col gap-2 px-3.5 py-3.5">
                <div className="flex items-center justify-between gap-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wider">
                    {email.previewLabel}
                  </span>
                  {canEdit && !isEditing && (
                    <EditMessageButton onClick={() => onDraft(email.message)} />
                  )}
                </div>
                <EmailText text={email.preview.text} message={email.message} />
                <p className="text-xs">{email.footnote}</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const OUTCOMES = {
  done: { icon: CircleCheck, color: 'text-success' },
  warning: { icon: TriangleAlert, color: 'text-warning' },
  failed: { icon: CircleX, color: 'text-danger' },
}

// One line of a result: a name with what happened.
export function OutcomeLine({ kind, name, children }) {
  const { icon: Icon, color } = OUTCOMES[kind]
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line/60 py-2.5 last:border-b-0">
      <span className="flex items-center gap-2.5 font-semibold text-navy">
        <Icon className={`size-4.5 shrink-0 ${color}`} aria-hidden="true" />
        {name}
      </span>
      <span className="text-sm">{children}</span>
    </div>
  )
}
