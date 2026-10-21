import { emailChip, emailNote } from '../../lib/feedback.js'

// The status of a candidate's feedback email, with a short note below.
export default function EmailChip({ state, warnings = 0, note }) {
  const chip = emailChip(state)
  const line = note ?? emailNote(state, warnings)
  return (
    <span className="flex flex-col items-start gap-1">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-semibold ${chip.className}`}
      >
        <span className="size-1.5 rounded-full bg-current" aria-hidden="true" />
        {chip.label}
      </span>
      {line && <span className="text-[12.5px]">{line}</span>}
    </span>
  )
}
