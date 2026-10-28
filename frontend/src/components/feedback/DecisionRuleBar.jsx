import { useState } from 'react'
import { decideByRule } from '../../lib/feedback.js'
import Button from '../Button.jsx'
import ConfirmDialog from '../ConfirmDialog.jsx'

const LOCKED = ['sent', 'sending']

function RuleInput({ label, value, min, max, step, isActive, onChange, onFocus }) {
  return (
    <input
      type="number"
      aria-label={label}
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(event) => onChange(event.target.value)}
      onFocus={onFocus}
      className={`h-10 w-16 rounded-xl border border-line bg-white text-center text-[15px] font-semibold text-navy ${
        isActive ? '' : 'opacity-60'
      }`}
    />
  )
}

// Decide by rule on the Assessments tab: hire the top N, or everyone with at
// least an overall score, and reject the rest of the ranked candidates with
// an approved report. A confirm shows who gets which decision first.
export default function DecisionRuleBar({ jobId, ranked, skipped, onChanged }) {
  const [rule, setRule] = useState('top')
  const [top, setTop] = useState(String(Math.min(2, ranked.length)))
  const [minScore, setMinScore] = useState('70')
  const [isConfirming, setIsConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const topValue = Number(top)
  const scoreValue = Number(minScore)
  const isValid =
    rule === 'top'
      ? Number.isInteger(topValue) && topValue >= 1
      : minScore !== '' && scoreValue >= 0 && scoreValue <= 100
  const preview = ranked.map((row, index) => ({
    row,
    hire: rule === 'top' ? index < topValue : row.overall_score >= scoreValue,
    isLocked: LOCKED.includes(row.feedback_status),
  }))
  const counts = {
    hire: preview.filter((item) => item.hire && !item.isLocked).length,
    reject: preview.filter((item) => !item.hire && !item.isLocked).length,
  }

  async function apply() {
    setBusy(true)
    setError('')
    try {
      await decideByRule(jobId, rule === 'top' ? { top: topValue } : { min_score: scoreValue })
      setIsConfirming(false)
      onChanged()
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  function radio(value, label) {
    return (
      <label className="flex items-center gap-2.5 text-[15px] text-navy">
        <input
          type="radio"
          name="decision-rule"
          checked={rule === value}
          onChange={() => setRule(value)}
          className="size-4.5 accent-brand"
        />
        {label}
      </label>
    )
  }

  return (
    <form
      aria-label="Decide by rule"
      onSubmit={(event) => {
        event.preventDefault()
        setError('')
        setIsConfirming(true)
      }}
      className="flex flex-wrap items-center gap-x-5.5 gap-y-3.5 rounded-[18px] border border-line bg-white px-5.5 py-4"
    >
      <span className="font-display text-[15.5px] font-extrabold text-navy">Decide by rule</span>
      <div className="flex flex-wrap items-center gap-2.5">
        {radio('top', 'Hire the top')}
        <RuleInput
          label="How many to hire"
          value={top}
          min={1}
          max={ranked.length}
          step={1}
          isActive={rule === 'top'}
          onChange={setTop}
          onFocus={() => setRule('top')}
        />
        <span className={`text-[15px] ${rule === 'top' ? 'text-navy' : ''}`}>candidates</span>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        {radio('score', 'Hire everyone with an overall score of at least')}
        <RuleInput
          label="Lowest overall score to hire"
          value={minScore}
          min={0}
          max={100}
          step={0.1}
          isActive={rule === 'score'}
          onChange={setMinScore}
          onFocus={() => setRule('score')}
        />
      </div>
      <span className="text-sm">· the rest are rejected</span>
      <Button type="submit" className="ml-auto" disabled={!isValid || ranked.length === 0}>
        Apply
      </Button>
      <p className="basis-full text-[13px]">
        Applies to ranked candidates with an approved report only. Drafts are skipped
        {skipped > 0 ? ` (${skipped} now)` : ''}. Candidates whose email is already sent keep their
        decision. You can change any row by hand afterwards.
      </p>

      {isConfirming && (
        <ConfirmDialog
          title={`Hire ${counts.hire} and reject ${counts.reject}?`}
          confirmLabel="Apply decisions"
          busyLabel="Applying…"
          confirmVariant="primary"
          isBusy={busy}
          error={error}
          onConfirm={apply}
          onCancel={() => setIsConfirming(false)}
        >
          <p>Nothing is sent yet; you review every email afterwards.</p>
          <ul className="flex flex-col gap-2 rounded-2xl border border-[#EEF2F9] bg-[#F8FAFE] px-4 py-3.5 text-sm text-navy">
            {preview.map(({ row, hire, isLocked }) => (
              <li key={row.session_id} className="flex justify-between gap-3">
                <span>
                  {row.rank} · {row.candidate_name}
                </span>
                <strong
                  className={isLocked ? 'text-[#6B7890]' : hire ? 'text-success' : 'text-danger'}
                >
                  {isLocked ? 'Kept · email sent' : hire ? 'Hire' : 'Reject'}
                </strong>
              </li>
            ))}
          </ul>
        </ConfirmDialog>
      )}
    </form>
  )
}
