import { Link } from 'react-router'
import { CV_RESULTS } from '../../lib/assessment.js'
import { fromStart } from '../../lib/room.js'

// Where a conclusion of the report comes from. A transcript source opens
// the transcript at its turn; a CV source shows the requirement and what
// screening found.
export default function SourceChip({ sessionId, source }) {
  if (source.type === 'transcript') {
    const time = source.start_ms != null ? ` · ${fromStart(source.start_ms)}` : ''
    return (
      <Link
        to={`/app/interviews/${sessionId}/transcript?turn=${source.turn_id}`}
        title="Open the transcript at this moment"
        className="max-w-full rounded-lg border border-line px-2.5 py-0.5 text-[12.5px] text-brand hover:border-brand/40 hover:bg-tint"
      >
        <strong className="font-semibold">
          {source.pair_id}
          {time}
        </strong>
        {source.quote && <span> “{source.quote}”</span>}
      </Link>
    )
  }
  const cv = CV_RESULTS[source.status]
  return (
    <span
      title={source.evidence ? `CV: “${source.evidence}”` : undefined}
      className={`rounded-lg px-2.5 py-0.5 text-[12.5px] ${cv ? cv.className : 'bg-mist text-body'}`}
    >
      {source.requirement_id} {source.requirement} · {cv ? cv.label : 'CV not screened'}
    </span>
  )
}
