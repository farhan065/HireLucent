import { WEIGHT_LABELS } from '../lib/stages.js'

const COLOURS = {
  technical_skills: 'bg-brand',
  experience: 'bg-[#7c8cf8]',
  qualifications: 'bg-[#a9c8ff]',
}

// The three scoring weights as one divided bar with a legend.
export default function WeightsBar({ weights }) {
  const keys = Object.keys(WEIGHT_LABELS)
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex h-3 overflow-hidden rounded-full bg-tint">
        {keys.map((key) => (
          <div key={key} className={COLOURS[key]} style={{ width: `${weights[key] * 100}%` }} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[13px]">
        {keys.map((key) => (
          <span key={key} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${COLOURS[key]}`} aria-hidden="true" />
            {WEIGHT_LABELS[key]} {Math.round(weights[key] * 100)}%
          </span>
        ))}
      </div>
    </div>
  )
}
