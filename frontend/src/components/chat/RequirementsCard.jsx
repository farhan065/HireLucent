import { useState } from 'react'
import { WEIGHT_LABELS } from '../../lib/stages.js'
import Button from '../Button.jsx'
import RequirementList from '../RequirementList.jsx'
import StatusChip from '../StatusChip.jsx'
import RequirementsEditor from './RequirementsEditor.jsx'

const STATUS_CHIPS = {
  waiting: { tone: 'info', label: 'Needs your approval' },
  approved: { tone: 'success', label: 'Approved by you' },
  changed: { tone: 'neutral', label: 'Changed' },
}

function Row({ label, children }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="w-24 shrink-0 text-sm">{label}</span>
      {children}
    </div>
  )
}

// The requirements checklist and scoring weights proposed by the assistant.
// The job is only saved when the interviewer confirms this card.
export default function RequirementsCard({ item, canAct, onConfirm }) {
  // The interviewer's own edits, kept here until they confirm.
  const [edited, setEdited] = useState(null)
  const [isEditing, setIsEditing] = useState(false)
  const shown = edited ?? item.arguments
  const { requirements, scoring_weights: weights } = shown
  const chip = STATUS_CHIPS[item.status] ?? STATUS_CHIPS.changed
  const isWaiting = item.status === 'waiting'

  function handleSave(changes) {
    setEdited(changes)
    setIsEditing(false)
  }

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
        <StatusChip tone={chip.tone}>
          {isEditing ? 'Editing' : edited && isWaiting ? 'Edited by you' : chip.label}
        </StatusChip>
      </header>

      {isEditing ? (
        <RequirementsEditor
          initial={shown}
          onSave={handleSave}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <div className="flex flex-col gap-3 px-4 py-3.5">
          <RequirementList items={requirements.items} />
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
      )}

      {isWaiting && canAct && !isEditing && (
        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3">
          <span className="text-sm">or type what to change below</span>
          <div className="flex flex-wrap gap-2.5">
            <Button variant="outline" onClick={() => setIsEditing(true)}>
              Edit
            </Button>
            <Button onClick={() => onConfirm(edited)}>Confirm and save job</Button>
          </div>
        </footer>
      )}
    </article>
  )
}
