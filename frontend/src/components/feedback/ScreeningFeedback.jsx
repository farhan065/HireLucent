import { Mail } from 'lucide-react'
import { useState } from 'react'
import {
  countStates,
  draftBy,
  emailAction,
  emailState,
  rejectionReason,
} from '../../lib/feedback.js'
import { Initials } from '../jobs/candidates.jsx'
import EmailButtons, { EmailCounts } from './EmailButtons.jsx'
import EmailChip from './EmailChip.jsx'
import FeedbackPanel from './FeedbackPanel.jsx'

const ROW =
  'grid grid-cols-[minmax(0,1.3fr)_minmax(0,1.7fr)_minmax(0,0.9fr)_minmax(0,1.2fr)_12rem] items-center gap-4 px-6'
const HEAD = 'text-xs font-semibold uppercase tracking-wider text-[#6B7890]'

function subLine(candidate) {
  if (candidate.status === 'screening_failed') return 'CV could not be read'
  if (candidate.status === 'excluded') return 'Excluded'
  const rank = candidate.scores?.final_rank
  const score = candidate.scores?.final_score
  return rank ? `Rank ${rank} · ${Math.round(score * 10) / 10}` : 'Scored'
}

// The Screening tab's feedback emails for everyone not shortlisted: each
// row with why, who writes the first draft and the email's status, plus
// Write emails and Send all passed.
export default function ScreeningFeedback({
  candidates,
  query = '',
  openFor = null,
  feedback,
  onChanged,
}) {
  const activity = feedback.activity
  const rows = candidates.map((candidate) => ({
    candidate,
    state: emailState(candidate, candidate.id, activity),
  }))
  // A chip clicked in the ranking opens that candidate's email, if written.
  const [openId, setOpenId] = useState(() =>
    rows.some(
      (row) => row.candidate.id === openFor && !['none', 'writing', 'queued'].includes(row.state),
    )
      ? openFor
      : null,
  )
  const text = query.trim().toLowerCase()
  const shown = text
    ? rows.filter((row) => row.candidate.full_name.toLowerCase().includes(text))
    : rows
  const counts = countStates(rows.map((row) => row.state))
  const person = ({ candidate }) => ({
    id: candidate.id,
    name: candidate.full_name,
    label: rejectionReason(candidate).label,
  })
  const toWrite = rows.filter((row) => ['none', 'discarded'].includes(row.state)).map(person)
  const ready = rows.filter((row) => row.state === 'ready').map(person)
  const needReview = rows.filter((row) => ['review', 'failed'].includes(row.state)).map(person)
  const withEmail = rows.filter((row) => !['none', 'writing', 'queued'].includes(row.state))

  return (
    <section
      aria-labelledby="screening-feedback-title"
      className="overflow-x-auto rounded-card border border-line bg-white shadow-card"
    >
      <div>
        <div className="flex flex-wrap items-start justify-between gap-5 px-6 py-5">
          <div className="flex max-w-2xl items-start gap-3.5">
            <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-violet-soft text-violet">
              <Mail className="size-5" aria-hidden="true" />
            </span>
            <div>
              <h2 id="screening-feedback-title" className="text-lg font-extrabold text-navy">
                Feedback emails · not shortlisted{' '}
                <span className="font-semibold text-body">{candidates.length}</span>
              </h2>
              <p className="mt-1.5 text-sm leading-relaxed">
                Everyone not shortlisted counts as rejected. Each email is written from that
                candidate's own screening results and checked for fairness. You can still shortlist
                someone until their email is sent.
              </p>
            </div>
          </div>
          <EmailButtons
            toWrite={toWrite}
            ready={ready}
            needReview={needReview}
            isRunning={feedback.isRunning}
            onWrite={feedback.write}
            onSendAll={() => feedback.sendAll('screening')}
          />
        </div>
        {feedback.error && (
          <p role="alert" className="px-6 pb-3 text-sm font-semibold text-danger">
            {feedback.error}
          </p>
        )}
        <div className="px-6 pb-4">
          <EmailCounts counts={counts} />
        </div>
        <div className={`${ROW} border-t border-[#EEF2F9] bg-mist py-2.5`}>
          <span className={HEAD}>Candidate</span>
          <span className={HEAD}>Why not shortlisted</span>
          <span className={HEAD}>First draft by</span>
          <span className={HEAD}>Email</span>
          <span className={`${HEAD} text-right`}>Action</span>
        </div>
        <ul>
          {shown.map(({ candidate, state }) => {
            const reason = rejectionReason(candidate)
            const action = emailAction(state)
            return (
              <li
                key={candidate.id}
                className={`${ROW} border-t border-[#EEF2F9] py-4 ${state === 'review' ? 'bg-[#FFFCF6]' : ''}`}
              >
                <span className="flex min-w-0 items-center gap-3">
                  <Initials name={candidate.full_name} />
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate text-[15px] font-semibold text-navy">
                      {candidate.full_name}
                    </span>
                    <span className="text-[12.5px]">{subLine(candidate)}</span>
                  </span>
                </span>
                <span className="flex flex-col items-start gap-1">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[12.5px] font-bold ${reason.className}`}
                  >
                    {reason.label}
                  </span>
                  <span className="text-[13px] leading-snug">{reason.note}</span>
                </span>
                <span className="text-[13.5px] text-navy">{draftBy(candidate)}</span>
                <EmailChip state={state} warnings={candidate.feedback_warnings} />
                <span className="flex justify-end">
                  {action && (
                    <button
                      type="button"
                      disabled={action.write && feedback.isRunning}
                      onClick={() =>
                        action.write ? feedback.write([candidate.id]) : setOpenId(candidate.id)
                      }
                      className={`inline-flex min-h-10 items-center rounded-full border-[1.5px] border-brand px-4 font-display text-sm font-bold disabled:cursor-not-allowed disabled:border-line disabled:text-body ${
                        action.primary ? 'bg-brand text-white' : 'bg-white text-brand'
                      }`}
                    >
                      {action.label}
                      <span className="sr-only"> for {candidate.full_name}</span>
                    </button>
                  )}
                </span>
              </li>
            )
          })}
          {rows.length === 0 && (
            <li className="border-t border-[#EEF2F9] px-6 py-6 text-center text-[15px]">
              Every screened candidate is shortlisted, so no rejection email is needed.
            </li>
          )}
          {rows.length > 0 && shown.length === 0 && (
            <li className="border-t border-[#EEF2F9] px-6 py-6 text-center text-[15px]">
              Nobody here matches “{query.trim()}”.
            </li>
          )}
        </ul>
      </div>
      {openId && (
        <FeedbackPanel
          people={withEmail.map(person)}
          startId={openId}
          stageLabel="Screening"
          onChanged={onChanged}
          onClose={() => {
            setOpenId(null)
            onChanged()
          }}
        />
      )}
    </section>
  )
}
