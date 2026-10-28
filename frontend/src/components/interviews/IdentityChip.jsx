import { IDENTITY, IDENTITY_TONES } from '../../lib/identity.js'

// The identity check as a small chip (F7). "isLong" gives the full label
// ("Low match: check identity") and the match score, for the waiting row
// and the Admit bar; the short one ("Low match") is for the sidebar.
export default function IdentityChip({ identity, isLong = false }) {
  const kind = IDENTITY[identity.result] ?? IDENTITY.not_checked
  const Icon = kind.icon
  const showScore = isLong && identity.result !== 'other_applicant' && identity.score != null
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-[12.5px] font-bold ${IDENTITY_TONES[kind.tone]}`}
    >
      <Icon className="size-3.5" aria-hidden="true" />
      {isLong ? kind.long : kind.short}
      {showScore && <span className="font-medium"> · match {identity.score.toFixed(2)}</span>}
    </span>
  )
}
