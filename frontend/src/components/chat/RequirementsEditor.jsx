import { Plus, X } from 'lucide-react'
import { useRequirementsForm } from '../../hooks/useRequirementsForm.js'
import { WEIGHT_LABELS } from '../../lib/stages.js'
import Button from '../Button.jsx'

const FIELD_CLASS = 'rounded-xl border-[1.5px] border-line px-3 text-[15px] text-navy'
const CATEGORIES = [
  ['technical_skills', 'Technical skills'],
  ['experience', 'Experience'],
  ['qualifications', 'Qualifications'],
]

// The fields of the requirements and weights form. "editor" is the state
// from useRequirementsForm, so the buttons can be placed where they fit.
export function RequirementsFields({ editor }) {
  const { form, total, updateItem, addItem, removeItem, setMinExperience, setWeight } = editor
  return (
    <>
      <label className="flex flex-wrap items-center gap-3 text-sm font-semibold text-navy">
        Minimum experience (years)
        <input
          type="number"
          min="0"
          max="50"
          value={form.minExperience}
          onChange={(event) => setMinExperience(event.target.value)}
          className={`${FIELD_CLASS} h-10 w-24 font-normal`}
        />
      </label>

      {form.items.map((item) => (
        <fieldset key={item.id} className="flex flex-col gap-2.5 rounded-2xl border border-line p-3">
          <legend className="sr-only">Requirement {item.id}</legend>
          <div className="flex items-center gap-2.5">
            <span className="rounded-lg bg-navy px-2.5 py-1 text-[13px] font-bold text-white">
              {item.id}
            </span>
            <input
              aria-label={`Requirement ${item.id}`}
              value={item.text}
              placeholder="Describe the requirement"
              onChange={(event) => updateItem(item.id, { text: event.target.value })}
              className={`${FIELD_CLASS} h-10 min-w-0 flex-1`}
            />
            <button
              type="button"
              aria-label={`Remove ${item.id}`}
              onClick={() => removeItem(item.id)}
              className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-danger-soft text-danger"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <select
              aria-label={`Category of ${item.id}`}
              value={item.category}
              onChange={(event) => updateItem(item.id, { category: event.target.value })}
              className={`${FIELD_CLASS} h-10 bg-white`}
            >
              {CATEGORIES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <div role="group" aria-label={`Priority of ${item.id}`} className="flex overflow-hidden rounded-xl border-[1.5px] border-line">
              {[
                ['must_have', 'Must-have'],
                ['preferred', 'Preferred'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={item.priority === value}
                  onClick={() => updateItem(item.id, { priority: value })}
                  className={`h-9 px-3 text-sm font-semibold ${
                    item.priority === value ? 'bg-brand text-white' : 'bg-white text-body'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <label className="flex flex-col gap-1 text-[13px]">
            Keywords, separated by commas
            <input
              value={item.keywords}
              onChange={(event) => updateItem(item.id, { keywords: event.target.value })}
              className={`${FIELD_CLASS} h-10`}
            />
          </label>
        </fieldset>
      ))}

      <button
        type="button"
        onClick={addItem}
        className="flex min-h-10 items-center gap-1.5 self-start rounded-full border-[1.5px] border-dashed border-brand px-4 text-sm font-semibold text-brand"
      >
        <Plus className="size-4" aria-hidden="true" /> Add requirement
      </button>

      <div className="flex flex-col gap-2.5 border-t border-line pt-3.5">
        <div className="flex items-center justify-between">
          <span className="font-display text-[15px] font-bold text-navy">Scoring weights (%)</span>
          <span
            className={`rounded-full px-3 py-1 text-[13px] font-semibold ${
              total === 100 ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
            }`}
          >
            Total {total}%{total === 100 ? '' : ', must be 100%'}
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          {Object.entries(WEIGHT_LABELS).map(([key, label]) => (
            <label key={key} className="flex flex-1 basis-28 flex-col gap-1 text-sm font-semibold text-navy">
              {label}
              <input
                type="number"
                min="0"
                max="100"
                value={form.weights[key]}
                onChange={(event) => setWeight(key, event.target.value)}
                className={`${FIELD_CLASS} h-10 w-full font-normal`}
              />
            </label>
          ))}
        </div>
      </div>
    </>
  )
}

// The form shown when the interviewer edits the requirements directly.
export default function RequirementsEditor({ initial, onSave, onCancel }) {
  const editor = useRequirementsForm(initial)
  return (
    <div className="flex flex-col gap-3.5 px-4 py-3.5">
      <RequirementsFields editor={editor} />
      <div className="flex flex-wrap justify-end gap-2.5">
        <Button variant="soft" onClick={onCancel}>
          Cancel
        </Button>
        <Button disabled={!editor.isValid} onClick={() => onSave(editor.value())}>
          Save changes
        </Button>
      </div>
    </div>
  )
}
