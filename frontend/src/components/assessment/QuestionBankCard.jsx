import { Check, CircleCheck } from 'lucide-react'
import { useState } from 'react'
import { addQuestions, KINDS } from '../../lib/assessment.js'
import Button from '../Button.jsx'

// The interview's new questions offered for the question bank. The
// interviewer ticks the ones to keep; nothing is added otherwise.
// suggestions is null when the question bank could not be searched.
export default function QuestionBankCard({ sessionId, jobTitle, jobCode, suggestions, onAdded }) {
  const [ticked, setTicked] = useState(() => new Set())
  const [isBusy, setIsBusy] = useState(false)
  const [error, setError] = useState('')
  const [added, setAdded] = useState(0)

  const heading = (
    <h2 className="text-[17px] font-extrabold text-navy">Suggested for the question bank</h2>
  )

  if (suggestions === null) {
    return (
      <section className="flex flex-col gap-2 rounded-[20px] border border-line bg-white p-4.5">
        {heading}
        <p className="text-[13.5px] leading-relaxed">
          The question bank could not be searched when this interview was evaluated. Evaluate it
          again to get suggestions.
        </p>
      </section>
    )
  }

  const open = suggestions.filter((item) => !item.added)

  function toggle(pairId) {
    setTicked((current) => {
      const next = new Set(current)
      if (next.has(pairId)) next.delete(pairId)
      else next.add(pairId)
      return next
    })
  }

  async function add() {
    setIsBusy(true)
    setError('')
    try {
      const updated = await addQuestions(sessionId, [...ticked])
      setAdded(ticked.size)
      setTicked(new Set())
      onAdded(updated)
    } catch (addError) {
      setError(addError.message)
    } finally {
      setIsBusy(false)
    }
  }

  return (
    <section className="flex flex-col gap-3.5 rounded-[20px] border border-line bg-white p-4.5 shadow-card">
      <div>
        {heading}
        <p className="mt-1.5 text-[13.5px] leading-relaxed">
          {suggestions.length === 0
            ? 'No new questions to suggest. The useful ones from this interview are already in the question bank.'
            : `New questions from this interview. Tick the ones to reuse in later ${jobTitle} interviews. Optional.`}
        </p>
      </div>

      {suggestions.length > 0 && (
        <div className="flex flex-col gap-2">
          {suggestions.map((item) =>
            item.added ? (
              <div
                key={item.pair_id}
                className="flex items-start gap-2.5 rounded-xl border border-[#EEF2F9] px-3 py-2.5"
              >
                <Check className="mt-0.5 size-4.5 shrink-0 text-success" aria-hidden="true" />
                <span className="text-sm leading-snug text-body">
                  {item.question}
                  <span className="block text-[12.5px] font-semibold text-success">
                    Added to the question bank
                  </span>
                </span>
              </div>
            ) : (
              <label
                key={item.pair_id}
                htmlFor={`suggest-${item.pair_id}`}
                className={`flex cursor-pointer items-start gap-2.5 rounded-xl px-3 py-2.5 ${
                  ticked.has(item.pair_id) ? 'bg-mist' : 'border border-[#EEF2F9]'
                }`}
              >
                <input
                  id={`suggest-${item.pair_id}`}
                  type="checkbox"
                  checked={ticked.has(item.pair_id)}
                  onChange={() => toggle(item.pair_id)}
                  className="mt-0.5 size-4.5 shrink-0 accent-brand"
                />
                <span className="text-sm leading-snug text-navy">
                  {item.question}
                  <span className="block text-[12.5px] text-body">
                    {item.pair_id} · {KINDS[item.kind]?.label}
                  </span>
                </span>
              </label>
            ),
          )}
        </div>
      )}

      {open.length > 0 && (
        <Button disabled={ticked.size === 0 || isBusy} onClick={add}>
          {isBusy
            ? 'Adding…'
            : ticked.size === 0
              ? 'Tick questions to add'
              : `Add ${ticked.size} to question bank`}
        </Button>
      )}
      {error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
      {added > 0 && (
        <p
          role="status"
          className="flex items-start gap-2.5 rounded-2xl bg-success-soft px-3.5 py-3 text-[13.5px] leading-relaxed text-[#0B5C41]"
        >
          <CircleCheck className="mt-0.5 size-4.5 shrink-0" aria-hidden="true" />
          <span>
            <strong>
              {added} {added === 1 ? 'question' : 'questions'} added
            </strong>{' '}
            to “Interview questions - {jobCode}.txt”. They can now be suggested in {jobTitle}{' '}
            interviews.
          </span>
        </p>
      )}
      {suggestions.length > 0 && (
        <p className="text-[12.5px] leading-relaxed">
          Questions already in the bank, follow-ups and small talk are left out. Added questions
          go to “Interview questions - {jobCode}.txt” in the Knowledge Base.
        </p>
      )}
    </section>
  )
}
