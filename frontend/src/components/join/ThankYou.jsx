import { Check } from 'lucide-react'
import CandidateLayout from './CandidateLayout.jsx'

// Shown to the candidate when the interviewer ends the interview.
export default function ThankYou({ firstName, jobTitle }) {
  return (
    <CandidateLayout>
      <section className="mx-auto flex w-full max-w-xl flex-col items-start gap-4 rounded-card border border-line bg-white p-9 shadow-card">
        <span className="flex size-14 items-center justify-center rounded-[18px] bg-success-soft text-success">
          <Check className="size-7" aria-hidden="true" />
        </span>
        <h1 className="text-[28px] font-extrabold tracking-tight">
          Thank you{firstName ? `, ${firstName}` : ''}
        </h1>
        <p className="text-base leading-relaxed">
          Your interview for {jobTitle} has ended. The hiring team will contact you by email about
          the next steps.
        </p>
        <p className="text-[14.5px]">You can close this tab now.</p>
      </section>
    </CandidateLayout>
  )
}
