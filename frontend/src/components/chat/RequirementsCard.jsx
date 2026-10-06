import Button from '../Button.jsx'
import StatusChip from '../StatusChip.jsx'

const STATUS_CHIPS = {
  waiting: { tone: 'info', label: 'Needs your approval' },
  approved: { tone: 'success', label: 'Approved by you' },
  changed: { tone: 'neutral', label: 'Changed' },
}

const WEIGHT_LABELS = {
  technical_skills: 'Technical',
  experience: 'Experience',
  qualifications: 'Qualifications',
}

function Row({ label, children }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-24 shrink-0 text-sm">{label}</span>
      {children}
    </div>
  )
}

function RequirementChips({ items, priority }) {
  const matching = items.filter((item) => item.priority === priority)
  if (matching.length === 0) return <span className="text-sm">None</span>
  const style = priority === 'must_have' ? 'bg-navy text-white' : 'bg-mist text-body'
  return matching.map((item) => (
    <span key={item.id} className={`rounded-full px-3 py-1 text-[13px] font-semibold ${style}`}>
      {item.text}
    </span>
  ))
}

// The requirements checklist and scoring weights proposed by the assistant.
// The job is only saved when the interviewer confirms this card.
export default function RequirementsCard({ item, canAct, onConfirm }) {
  const { requirements, scoring_weights: weights } = item.arguments
  const chip = STATUS_CHIPS[item.status] ?? STATUS_CHIPS.changed
  const isWaiting = item.status === 'waiting'

  return (
    <article
      className={`overflow-hidden rounded-2xl border bg-white ${
        isWaiting ? 'border-brand shadow-card' : 'border-line'
      } ${item.status === 'changed' ? 'opacity-70' : ''}`}
    >
      <header className="flex flex-wrap items-center justify-between gap-2.5 bg-mist px-4 py-3">
        <span className="font-display text-[15px] font-bold text-navy">
          {isWaiting ? 'Your decision: requirements and weights' : 'Requirements and weights'}
        </span>
        <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
      </header>

      <div className="flex flex-col gap-2.5 px-4 py-3.5">
        <Row label="Must-have">
          <RequirementChips items={requirements.items} priority="must_have" />
        </Row>
        <Row label="Preferred">
          <RequirementChips items={requirements.items} priority="preferred" />
        </Row>
        <Row label="Experience">
          <strong className="text-sm text-navy">
            {requirements.min_experience_years > 0
              ? `${requirements.min_experience_years}+ years`
              : 'No minimum'}
          </strong>
        </Row>
        <Row label="Weights">
          <span className="text-sm text-navy">
            {Object.entries(WEIGHT_LABELS)
              .map(([key, label]) => `${label} ${Math.round(weights[key] * 100)}%`)
              .join(' · ')}
          </span>
        </Row>
      </div>

      {isWaiting && canAct && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <span className="text-sm">or type what to change below</span>
          <Button onClick={onConfirm}>Confirm and save job</Button>
        </footer>
      )}
    </article>
  )
}
