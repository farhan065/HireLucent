import { Check } from 'lucide-react'
import { Link } from 'react-router'
import { jobStage, totalCandidates } from '../../lib/jobs.js'

function Tab({ number, label, to, isCurrent, isDone, badge }) {
  const isLocked = !to
  const circle = isCurrent
    ? 'bg-brand text-white'
    : isDone
      ? 'bg-success text-white'
      : 'bg-line text-body'
  const content = (
    <>
      <span
        className={`flex size-6.5 shrink-0 items-center justify-center rounded-full text-[13px] font-bold ${circle}`}
      >
        {isDone && !isCurrent ? <Check className="size-3.5" aria-hidden="true" /> : number}
      </span>
      {label}
      {badge}
      {isLocked && <span className="text-xs font-medium">soon</span>}
    </>
  )
  const base =
    '-mb-0.5 flex shrink-0 items-center gap-2.5 border-b-[3px] px-1 pb-3.5 text-[15px] font-semibold'

  if (isLocked) {
    return (
      <span aria-disabled="true" className={`${base} border-transparent text-body/60`}>
        {content}
      </span>
    )
  }
  return (
    <Link
      to={to}
      aria-current={isCurrent ? 'page' : undefined}
      className={`${base} ${
        isCurrent
          ? 'border-brand text-navy'
          : `border-transparent hover:text-navy ${isDone ? 'text-navy' : 'text-body'}`
      }`}
    >
      {content}
    </Link>
  )
}

// The stages of one job, in order. The same row is shown on the job's pages
// and above its conversation with the AI Agent. "today" is the number of
// interviews still to come today, "inWaitingRoom" the candidates waiting now
// and "toReview" the draft reports waiting for the interviewer's review.
// "interviewsDone" and "assessmentsDone" tick the last two stages.
export default function JobTabs({
  job,
  threadId,
  waiting = 0,
  today = 0,
  inWaitingRoom = 0,
  toReview = 0,
  interviewsDone = false,
  assessmentsDone = false,
  current,
}) {
  const stage = jobStage(job)
  const isPublished = job.status === 'published'
  const tabs = [
    {
      key: 'post',
      label: 'Job post',
      to: threadId ? `/app/assistant/${threadId}` : `/app/jobs/${job.id}`,
      isDone: isPublished,
    },
    {
      key: 'applications',
      label: 'Applications',
      to: `/app/jobs/${job.id}/applications`,
      isDone: totalCandidates(job) > 0,
      badge: waiting > 0 && (
        <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning">
          {waiting} new
        </span>
      ),
    },
    {
      key: 'screening',
      label: 'Screening',
      to: `/app/jobs/${job.id}/screening`,
      isDone: stage === 'cvs_screened' || stage === 'interviews_scheduled',
    },
    {
      key: 'interviews',
      label: 'Interviews',
      // Open once the job is published. Until someone is shortlisted it
      // explains what to do first.
      to: isPublished ? `/app/jobs/${job.id}/interviews` : undefined,
      isDone: interviewsDone,
      badge:
        inWaitingRoom > 0 ? (
          <span className="rounded-full bg-success-soft px-2 py-0.5 text-xs font-semibold text-success">
            {inWaitingRoom} waiting
          </span>
        ) : (
          today > 0 && (
            <span className="rounded-full bg-amber-soft px-2 py-0.5 text-xs font-semibold text-amber">
              {today} today
            </span>
          )
        ),
    },
    {
      key: 'assessments',
      label: 'Assessments',
      // The ranked candidates, once the job is published.
      to: isPublished ? `/app/jobs/${job.id}/assessments` : undefined,
      isDone: assessmentsDone,
      badge: toReview > 0 && (
        <span className="rounded-full bg-amber-soft px-2 py-0.5 text-xs font-semibold text-amber">
          {toReview} to review
        </span>
      ),
    },
  ]

  return (
    <nav
      aria-label="Job stages"
      className="flex gap-8 overflow-x-auto border-b-2 border-line"
    >
      {tabs.map((tab, index) => (
        <Tab
          key={tab.key}
          number={index + 1}
          label={tab.label}
          to={tab.to}
          isCurrent={tab.key === current}
          isDone={Boolean(tab.isDone)}
          badge={tab.badge}
        />
      ))}
    </nav>
  )
}
