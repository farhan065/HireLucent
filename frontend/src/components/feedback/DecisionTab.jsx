import { Check, Mail, X } from 'lucide-react'
import { useCallback, useState } from 'react'
import { useFeedback } from '../../hooks/useFeedback.js'
import { formatDate } from '../../lib/jobs.js'
import { setDecision } from '../../lib/feedback.js'
import FeedbackEmail from './FeedbackEmail.jsx'

const LOCKED = ['sent', 'sending']

// The assessment page's Decision tab (F11), shown once the report is
// approved: Hire or Reject, then the candidate's feedback email below. A
// decision writes the email straight away (the AI for a rejection, the
// selection message for a hire); it can change until the email is sent.
export default function DecisionTab({ jobId, assessment, candidateName, onChanged }) {
  const [version, setVersion] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const refresh = useCallback(() => {
    setVersion((value) => value + 1)
    onChanged()
  }, [onChanged])
  const feedback = useFeedback(jobId, refresh)
  const candidateId = assessment.candidate_id
  const running = feedback.activity?.running
  const isWriting =
    running?.kind === 'feedback_writing' &&
    (running.result?.candidate_ids ?? []).includes(candidateId)
  const isLocked = LOCKED.includes(assessment.feedback_status)

  async function decide(decision) {
    setBusy(true)
    setError('')
    try {
      await setDecision(candidateId, assessment.decision === decision ? null : decision)
      onChanged()
      setVersion((value) => value + 1)
      if (decision !== assessment.decision) await feedback.write([candidateId])
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  const line = isLocked
    ? 'The email is sent, so the decision is locked.'
    : assessment.decision
      ? `${assessment.decision === 'hire' ? 'Hired' : 'Rejected'} by you. You can change it until the email is sent.`
      : 'Choose Hire or Reject. The email to the candidate is written next, for you to review.'

  return (
    <div className="flex flex-col gap-5">
      <section
        aria-labelledby="decision-title"
        className="flex flex-wrap items-center justify-between gap-4.5 rounded-[20px] border border-line bg-white px-6 py-5 shadow-card"
      >
        <div className="max-w-xl">
          <h2 id="decision-title" className="text-lg font-extrabold text-navy">
            Your decision
          </h2>
          <p className="mt-1.5 text-sm leading-relaxed">{line}</p>
          {assessment.approved_at && (
            <p className="mt-1 text-[13px]">
              Report approved {formatDate(assessment.approved_at)}.
            </p>
          )}
        </div>
        <div role="group" aria-label="Decision" className="flex gap-2.5">
          <button
            type="button"
            aria-pressed={assessment.decision === 'hire'}
            disabled={busy || isLocked}
            onClick={() => decide('hire')}
            className={`inline-flex min-h-12 items-center gap-2 rounded-full px-5.5 font-display text-[15px] font-bold disabled:cursor-not-allowed disabled:opacity-60 ${
              assessment.decision === 'hire'
                ? 'bg-success text-white'
                : 'border-[1.5px] border-[#9FD9BE] bg-white text-success hover:bg-success-soft'
            }`}
          >
            <Check className="size-4.5" aria-hidden="true" />
            {assessment.decision === 'hire' ? 'Hired' : 'Hire'}
          </button>
          <button
            type="button"
            aria-pressed={assessment.decision === 'reject'}
            disabled={busy || isLocked}
            onClick={() => decide('reject')}
            className={`inline-flex min-h-12 items-center gap-2 rounded-full px-5.5 font-display text-[15px] font-bold disabled:cursor-not-allowed disabled:opacity-60 ${
              assessment.decision === 'reject'
                ? 'bg-danger text-white'
                : 'border-[1.5px] border-[#F3C4C0] bg-white text-danger hover:bg-danger-soft'
            }`}
          >
            <X className="size-4.5" aria-hidden="true" />
            {assessment.decision === 'reject' ? 'Rejected' : 'Reject'}
          </button>
        </div>
        {(error || feedback.error) && (
          <p role="alert" className="basis-full text-sm font-semibold text-danger">
            {error || feedback.error}
          </p>
        )}
      </section>

      {assessment.decision && (
        <section
          aria-labelledby="email-title"
          className="flex flex-col gap-4 rounded-[22px] border border-line bg-white px-6.5 py-6 shadow-card"
        >
          <h2 id="email-title" className="flex items-center gap-3 text-lg font-extrabold text-navy">
            <span className="flex size-9.5 items-center justify-center rounded-xl bg-violet-soft text-violet">
              <Mail className="size-4.5" aria-hidden="true" />
            </span>
            Feedback email
          </h2>
          <FeedbackEmail
            candidateId={candidateId}
            candidateName={candidateName}
            version={version}
            isWriting={isWriting}
            onWrite={() => feedback.write([candidateId])}
            onChanged={onChanged}
          />
        </section>
      )}
    </div>
  )
}
