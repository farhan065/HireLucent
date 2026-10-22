import { CircleAlert, LoaderCircle, Sparkles } from 'lucide-react'
import { Link } from 'react-router'
import Button from '../Button.jsx'

// The stages of an evaluation, in order.
const STAGES = [
  'Questions and answers found',
  'Judging answers and checking references',
  "Mapping the job's requirements",
  'Checking CV claims',
  'Writing the report',
]
const CHECKING_CLAIMS = 'checking CV claims'
const WRITING = 'writing the report'

// Which stage the progress message is at: 0 while the questions are being
// found, 1 while answers are judged, 3 while the CV claims are checked and
// 4 while the report is written.
function stageOf(message) {
  if (!message || message === 'starting') return 0
  if (message === CHECKING_CLAIMS) return 3
  return message === WRITING ? 4 : 1
}

// While this interview is being evaluated.
export function EvaluatingCard({ message, percent }) {
  const stage = stageOf(message)
  return (
    <section
      role="status"
      className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-line bg-white p-5.5"
    >
      <div className="flex items-center gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-tint text-brand">
          <LoaderCircle
            className="size-5 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
        </span>
        <div>
          <h2 className="text-[17px] font-extrabold text-navy">Evaluating the interview</h2>
          <p className="text-[13.5px]">
            {stage === 0
              ? 'Finding the questions and answers'
              : stage === 3
                ? 'Checking CV claims'
                : stage === 4
                  ? 'Writing the report'
                  : message}
          </p>
        </div>
      </div>
      <span aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-[#E4EAF4]">
        <span
          className="block h-full rounded-full bg-brand transition-[width]"
          style={{ width: `${Math.max(percent ?? 0, 4)}%` }}
        />
      </span>
      <ol className="flex list-decimal flex-col gap-1.5 pl-5 text-[13.5px]">
        {STAGES.map((name, index) => {
          const isDone = index < stage
          const isNow = index === stage
          return (
            <li
              key={name}
              className={
                isDone ? 'font-semibold text-success' : isNow ? 'font-semibold text-navy' : ''
              }
            >
              {name}
            </li>
          )
        })}
      </ol>
      <p className="text-[13px]">
        A minute or two. You can leave this page; the result is saved when it finishes.
      </p>
    </section>
  )
}

// The last evaluation of this interview did not finish.
export function FailedCard({ reason, transcriptTo, isBusy, onRetry }) {
  return (
    <section
      role="alert"
      className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-[#F3C4C0] bg-white p-5.5"
    >
      <div className="flex items-start gap-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-danger-soft text-danger">
          <CircleAlert className="size-5" aria-hidden="true" />
        </span>
        <div>
          <h2 className="text-[17px] font-extrabold text-navy">The evaluation stopped</h2>
          <p className="mt-1 text-sm leading-relaxed">{reason}</p>
        </div>
      </div>
      <p className="text-[13px]">Nothing from this run was saved. The transcript is safe.</p>
      <div className="flex flex-wrap items-center gap-3">
        <Button disabled={isBusy} onClick={onRetry}>
          Try again
        </Button>
        <Link
          to={transcriptTo}
          className="inline-flex min-h-11 items-center px-4 text-[14.5px] font-semibold text-brand hover:text-brand-dark"
        >
          View transcript
        </Link>
      </div>
    </section>
  )
}

// An interview with no assessment yet. Only a completed one can be
// evaluated.
export function NotEvaluatedCard({ isCompleted, isBusy, onEvaluate }) {
  return (
    <section className="flex max-w-xl flex-col gap-3.5 rounded-[20px] border border-dashed border-[#A9C8FF] bg-white p-5.5">
      <h2 className="text-[17px] font-extrabold text-navy">
        This interview has not been evaluated yet
      </h2>
      {isCompleted ? (
        <>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-[13.5px] leading-snug">
            <li>Finds each question and the answer it got</li>
            <li>Scores each answer, checking your reference documents first</li>
            <li>Shows which job requirements were covered</li>
          </ul>
          <div>
            <Button
              disabled={isBusy}
              onClick={onEvaluate}
              title={isBusy ? 'Another evaluation is running. Wait for it to finish.' : undefined}
            >
              <Sparkles className="size-4.5" aria-hidden="true" />
              Evaluate
            </Button>
          </div>
        </>
      ) : (
        <p className="text-[13.5px]">Only a completed interview can be evaluated.</p>
      )}
    </section>
  )
}
