import { useState } from 'react'
import { useNavigate } from 'react-router'
import Button from '../Button.jsx'

const EXAMPLES = [
  ['Backend engineer', 'A backend engineer with Python and FastAPI, about 2 years of experience'],
  ['UI designer', 'A UI designer with Figma experience and a strong portfolio'],
  ['Data analyst', 'A data analyst who knows SQL, Python and dashboards'],
  ['QA engineer', 'A QA engineer with test automation experience'],
]

// Start a new job from the dashboard by describing the role. The text is
// carried to the Hiring Assistant and sent as the first message.
export default function RoleBox() {
  const [text, setText] = useState('')
  const navigate = useNavigate()

  function start() {
    const firstMessage = text.trim()
    if (!firstMessage) return
    navigate('/app/assistant', { state: { fresh: true, firstMessage } })
  }

  function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      start()
    }
  }

  return (
    <section
      aria-label="Start a new job"
      className="relative flex flex-col gap-4 overflow-hidden rounded-[26px] border border-line bg-white bg-[radial-gradient(520px_260px_at_92%_0%,#dde4ff_0%,transparent_70%)] p-7 shadow-card"
    >
      {/* Decorative light rings. */}
      <svg viewBox="0 0 360 360" aria-hidden="true" className="absolute -right-24 -top-36 w-90">
        <g fill="none" stroke="#1557e0" strokeOpacity="0.12">
          {[60, 100, 140, 178].map((radius) => (
            <circle key={radius} cx="180" cy="180" r={radius} />
          ))}
        </g>
      </svg>

      <div className="relative">
        <span className="text-[13px] font-semibold uppercase tracking-widest text-brand">
          Hiring Assistant
        </span>
        <h2 className="mt-1.5 text-2xl font-extrabold tracking-tight">
          What role are you hiring for?
        </h2>
      </div>

      <div className="relative flex flex-wrap items-end gap-3">
        <textarea
          aria-label="Describe the role"
          rows={2}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="For example: a backend engineer with Python and FastAPI, about 2 years of experience…"
          className="min-h-16 flex-1 basis-96 resize-none rounded-2xl border-[1.5px] border-line bg-white px-4 py-3.5 text-base text-navy placeholder:text-body/60"
        />
        <Button disabled={!text.trim()} onClick={start} className="min-h-13 px-7 text-base">
          Start drafting
        </Button>
      </div>

      <div className="relative flex flex-wrap items-center gap-2">
        <span className="text-sm">Try:</span>
        {EXAMPLES.map(([label, example]) => (
          <button
            key={label}
            type="button"
            onClick={() => setText(example)}
            className="min-h-9 rounded-full bg-tint px-3.5 text-[13px] font-semibold text-brand-dark hover:bg-lavender"
          >
            {label}
          </button>
        ))}
      </div>
    </section>
  )
}
