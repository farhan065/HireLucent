import { CircleAlert } from 'lucide-react'
import { COVERAGE, CV_RESULTS, roundScore, scoreTone } from '../../lib/assessment.js'

const GRID =
  'grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,1.5fr)] items-start gap-4.5'

function Row({ entry, onPickQuestion }) {
  const status = COVERAGE[entry.status]
  const cv = entry.cv ? CV_RESULTS[entry.cv.status] : null
  const average = roundScore(entry.average)
  const isMust = entry.priority === 'must_have'
  // A requirement the CV claims but the interview never checked.
  const toVerify = entry.status === 'not_explored' && entry.cv?.status === 'met'
  return (
    <div
      className={`flex flex-col gap-2.5 border-b border-[#EEF2F9] px-5.5 py-4 last:border-b-0 ${
        toVerify ? 'bg-[#FFFCF6]' : ''
      }`}
    >
      <div className={GRID}>
        <div className="flex min-w-0 flex-col gap-1.5">
          <span className="text-[15px] font-semibold text-navy">
            <span className="mr-1.5 font-bold text-[#6B7890]">{entry.requirement_id}</span>
            {entry.text}
          </span>
          <span
            className={`self-start rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              isMust ? 'bg-tint text-brand-dark' : 'bg-[#F4F6FA] text-[#5A667D]'
            }`}
          >
            {isMust ? 'Must-have' : 'Preferred'}
          </span>
        </div>
        <div className="flex flex-col gap-2">
          <span
            className={`self-start rounded-full px-3 py-1 text-[13px] font-bold ${status.className}`}
          >
            {status.label}
          </span>
          {average != null && (
            <span className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="h-1.5 max-w-30 flex-1 overflow-hidden rounded-full bg-[#E4EAF4]"
              >
                <span className={`block h-full rounded-full ${status.bar}`} style={{ width: `${average}%` }} />
              </span>
              <span className="text-[13px] font-semibold tabular-nums text-navy">avg {average}</span>
            </span>
          )}
          {entry.mixed && (
            <span className="self-start rounded-full bg-warning-soft px-2.5 py-0.5 text-xs font-semibold text-warning">
              Mixed: one weak answer
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {entry.question_scores.length === 0 ? (
            <span className="text-[13.5px] text-[#7B879C]">No question asked</span>
          ) : (
            entry.question_scores.map((item) => {
              const tone = scoreTone(item.score)
              return (
                <button
                  key={item.pair_id}
                  type="button"
                  onClick={() => onPickQuestion(item.pair_id)}
                  title={`Open ${item.pair_id} on the Q&A analysis tab`}
                  className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-line px-2.5 text-[13px] text-navy tabular-nums hover:border-brand/40 hover:bg-tint"
                >
                  <strong className="font-bold">{item.pair_id}</strong>
                  <span className={`rounded-md px-1.5 font-bold ${tone.chip}`}>
                    {roundScore(item.score)}
                  </span>
                </button>
              )
            })
          )}
        </div>
        <div className="flex min-w-0 flex-col gap-1.5">
          {cv ? (
            <>
              <span
                className={`self-start rounded-full px-2.5 py-0.5 text-[12.5px] font-semibold ${cv.className}`}
              >
                {cv.label}
              </span>
              {entry.cv.evidence && (
                <span className="text-[13.5px] leading-snug">“{entry.cv.evidence}”</span>
              )}
            </>
          ) : (
            <span className="text-[13.5px] text-[#7B879C]">Not screened</span>
          )}
        </div>
      </div>
      {toVerify && (
        <p className="flex items-start gap-2 rounded-xl bg-warning-soft px-3 py-2.5 text-[13.5px] leading-snug text-[#6B3A00]">
          <CircleAlert className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          The CV claims this, but the interview did not check it. Listed under Areas to verify.
        </p>
      )}
    </div>
  )
}

// One row per job requirement: how the interview explored it, the
// questions behind that (each opens on the Q&A tab) and what CV screening
// found.
export default function CoverageTable({ coverage, onPickQuestion }) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[940px]">
        <div
          className={`${GRID} border-b border-line bg-mist px-5.5 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7890]`}
        >
          <span>Requirement</span>
          <span>In the interview</span>
          <span>Questions</span>
          <span>CV screening</span>
        </div>
        {coverage.map((entry) => (
          <Row key={entry.requirement_id} entry={entry} onPickQuestion={onPickQuestion} />
        ))}
      </div>
    </div>
  )
}
