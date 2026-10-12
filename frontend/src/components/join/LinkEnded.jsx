import { CalendarX2 } from 'lucide-react'
import CandidateLayout from './CandidateLayout.jsx'

// Shown for a link that is unknown, moved, cancelled or past its interview.
export default function LinkEnded() {
  return (
    <CandidateLayout>
      <section className="mx-auto flex w-full max-w-xl flex-col items-start gap-4 rounded-card border border-line bg-white p-9 shadow-card">
        <span className="flex size-14 items-center justify-center rounded-[18px] bg-line/60 text-navy/75">
          <CalendarX2 className="size-7" aria-hidden="true" />
        </span>
        <h1 className="text-[28px] font-extrabold tracking-tight">
          This interview link no longer works
        </h1>
        <p className="text-base leading-relaxed">
          The interview it was for has ended, was cancelled, or was moved to a new time. If it
          was moved, use the link in your newest invitation email.
        </p>
        <p className="text-[14.5px]">
          If you think this is a mistake, reply to your invitation email.
        </p>
      </section>
    </CandidateLayout>
  )
}
