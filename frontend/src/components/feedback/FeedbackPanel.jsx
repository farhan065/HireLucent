import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import SidePanel from '../SidePanel.jsx'
import FeedbackEmail from './FeedbackEmail.jsx'

// The review panel over the Screening or Assessments tab. "people" are the
// candidates whose emails can be gone through with ‹ ›, each { id, name,
// label }; "startId" is the one opened.
export default function FeedbackPanel({ people, startId, stageLabel, onChanged, onClose }) {
  const [index, setIndex] = useState(() =>
    Math.max(
      people.findIndex((person) => person.id === startId),
      0,
    ),
  )
  const person = people[index]
  if (!person) return null

  const nav = people.length > 1 && (
    <div className="flex items-center gap-1.5">
      <span className="text-[13.5px] font-semibold text-navy">
        {index + 1} of {people.length}
      </span>
      <button
        type="button"
        aria-label="Previous email"
        disabled={index === 0}
        onClick={() => setIndex(index - 1)}
        className="flex size-10 items-center justify-center rounded-xl border border-line bg-white text-navy disabled:text-[#9AA6BA]"
      >
        <ChevronLeft className="size-4.5" aria-hidden="true" />
      </button>
      <button
        type="button"
        aria-label="Next email"
        disabled={index === people.length - 1}
        onClick={() => setIndex(index + 1)}
        className="flex size-10 items-center justify-center rounded-xl border border-line bg-white text-navy disabled:text-[#9AA6BA]"
      >
        <ChevronRight className="size-4.5" aria-hidden="true" />
      </button>
    </div>
  )

  return (
    <SidePanel
      title={person.name}
      subtitle={`Feedback email · ${stageLabel}${person.label ? ` · ${person.label}` : ''}`}
      onClose={onClose}
      isWide
    >
      <div className="flex flex-col gap-4">
        {nav && <div className="flex justify-end">{nav}</div>}
        <FeedbackEmail
          key={person.id}
          candidateId={person.id}
          candidateName={person.name}
          onChanged={onChanged}
        />
      </div>
    </SidePanel>
  )
}
