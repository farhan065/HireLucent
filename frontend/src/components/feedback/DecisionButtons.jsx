import { useState } from 'react'
import { setDecision } from '../../lib/feedback.js'

const LOCKED = ['sent', 'sending']

// Hire | Reject for one interviewed candidate. Only after the report is
// approved, and locked once the feedback email is sent. Choosing the chosen
// one again takes the decision back.
export default function DecisionButtons({ row, name, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const isApproved = row.status === 'approved'
  const isLocked = LOCKED.includes(row.feedback_status)
  const canDecide = isApproved && !isLocked && !busy

  async function decide(decision) {
    setBusy(true)
    setError('')
    try {
      await setDecision(row.candidate_id, row.decision === decision ? null : decision)
      onChanged()
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  const note = !isApproved
    ? 'Approve the report first'
    : isLocked
      ? 'Locked · email sent'
      : row.decision === 'hire'
        ? 'Hired'
        : row.decision === 'reject'
          ? 'Rejected'
          : 'Not decided'

  return (
    <span className="flex flex-col gap-1">
      <span
        role="group"
        aria-label={`Decision for ${name}`}
        className={`inline-flex w-fit gap-0.5 rounded-full border-[1.5px] border-line bg-white p-0.5 ${
          canDecide || busy ? '' : 'opacity-55'
        }`}
      >
        {[
          ['hire', 'Hire', 'bg-success text-white'],
          ['reject', 'Reject', 'bg-danger text-white'],
        ].map(([value, label, active]) => (
          <button
            key={value}
            type="button"
            aria-pressed={row.decision === value}
            disabled={!canDecide}
            onClick={() => decide(value)}
            className={`min-h-9 rounded-full px-3.5 text-[13.5px] font-bold disabled:cursor-not-allowed ${
              row.decision === value ? active : 'text-navy hover:bg-tint'
            }`}
          >
            {label}
          </button>
        ))}
      </span>
      <span className="text-[12.5px]">{note}</span>
      {error && (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      )}
    </span>
  )
}
