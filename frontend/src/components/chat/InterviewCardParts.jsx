import { CalendarDays, CircleCheck, CircleX, Lock, Mail, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

// Shared pieces of the interview cards in the AI Agent conversation.

const CARD_ICONS = { mail: Mail, calendar: CalendarDays, lock: Lock }

// What happens when the interviewer approves, and the invitation that is sent.
export function WhenYouApprove({ lines, preview }) {
  const [isOpen, setIsOpen] = useState(false)
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
      {preview && (
        <>
          <button
            type="button"
            aria-expanded={isOpen}
            onClick={() => setIsOpen((open) => !open)}
            className="self-start pt-1 font-semibold text-brand hover:text-brand-dark"
          >
            {isOpen ? 'Hide the invitation' : 'Show the invitation'}
          </button>
          {isOpen && (
            <div className="flex flex-col gap-2 rounded-xl border border-line bg-white px-4 py-3">
              <p className="text-[13px]">
                Title: <strong className="text-navy">{preview.subject}</strong>
              </p>
              <p className="whitespace-pre-line text-[13.5px] leading-relaxed text-navy">
                {preview.text}
              </p>
              <p className="text-xs">
                An example. Each candidate gets their own private link where it says
                [private link].
              </p>
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
