import { Check } from 'lucide-react'
import { useState } from 'react'
import RequirementList from '../RequirementList.jsx'
import SidePanel from '../SidePanel.jsx'
import StatusChip from '../StatusChip.jsx'
import WeightsBar from '../WeightsBar.jsx'
import Markdown from './Markdown.jsx'

function journeySteps(view) {
  const { brief, items } = view
  return [
    { label: 'Role described', done: items.some((item) => item.kind === 'user') },
    { label: 'Description approved', done: brief.description?.status === 'approved' },
    { label: 'Requirements confirmed', done: brief.requirements_status === 'confirmed' },
    { label: 'Published', done: false },
    { label: 'CVs screened', done: false },
    { label: 'Interviews scheduled', done: false },
  ]
}

function Journey({ view }) {
  const steps = journeySteps(view)
  const current = steps.findIndex((step) => !step.done)
  return (
    <ol className="flex flex-col gap-2.5">
      {steps.map((step, index) => {
        const isCurrent = index === current
        const circle = step.done
          ? 'bg-success text-white'
          : isCurrent
            ? 'bg-brand text-white ring-4 ring-tint'
            : 'bg-tint text-brand-dark'
        return (
          <li key={step.label} className="flex items-center gap-3">
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${circle}`}
            >
              {step.done ? <Check className="size-3.5" aria-hidden="true" /> : index + 1}
            </span>
            <span
              className={`text-sm font-semibold ${step.done || isCurrent ? 'text-navy' : 'text-body/70'}`}
            >
              {step.label}
            </span>
            {isCurrent && <StatusChip tone="info">now</StatusChip>}
          </li>
        )
      })}
    </ol>
  )
}

// One part of the brief. Giving it a key made from its content makes the
// highlight animation play again whenever that content changes.
function Section({ title, chip, watch, children }) {
  return (
    <section
      key={JSON.stringify(watch ?? null)}
      className={`flex flex-col gap-2.5 rounded-xl border-t border-line px-2 py-4 ${
        watch ? 'animate-highlight' : ''
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[13px] font-semibold uppercase tracking-widest">{title}</h3>
        {chip}
      </div>
      {children}
    </section>
  )
}

// The current state of the job, beside the conversation. It only displays:
// every change is made in the conversation.
export default function JobBrief({ view }) {
  const [isReading, setIsReading] = useState(false)
  const { brief } = view
  const description = brief.description

  return (
    <aside
      aria-label="Job brief"
      className="hidden w-96 shrink-0 flex-col overflow-y-auto border-l border-line bg-white px-5 py-5 lg:flex"
    >
      <div className="px-2 pb-4">
        <h2 className="text-lg font-bold">Job brief</h2>
        <p className="text-[13px]">Fills in as you and the assistant decide.</p>
      </div>

      <Section title="Journey">
        <Journey view={view} />
      </Section>

      <Section
        title="Description"
        watch={description && [description.version, description.status]}
        chip={
          description ? (
            <StatusChip tone={description.status === 'approved' ? 'success' : 'info'}>
              Draft {description.version} ·{' '}
              {description.status === 'approved' ? 'approved' : 'waiting for you'}
            </StatusChip>
          ) : (
            <StatusChip tone="neutral">Not written yet</StatusChip>
          )
        }
      >
        {description && (
          <button
            type="button"
            onClick={() => setIsReading(true)}
            className="self-start text-sm font-semibold text-brand hover:text-brand-dark"
          >
            Read the full description
          </button>
        )}
      </Section>

      <Section
        title="Requirements"
        watch={brief.requirements && [brief.requirements, brief.requirements_status]}
        chip={
          brief.requirements && (
            <StatusChip tone={brief.requirements_status === 'confirmed' ? 'success' : 'info'}>
              {brief.requirements_status === 'confirmed' ? 'Confirmed' : 'Proposed'}
            </StatusChip>
          )
        }
      >
        {brief.requirements ? (
          <>
            <RequirementList items={brief.requirements.items} />
            <p className="text-[13px]">
              Minimum experience:{' '}
              {brief.requirements.min_experience_years > 0
                ? `${brief.requirements.min_experience_years} years`
                : 'none'}
              .
            </p>
          </>
        ) : (
          <p className="text-sm">Proposed after you approve the description.</p>
        )}
      </Section>

      <Section title="Scoring weights" watch={brief.scoring_weights}>
        {brief.scoring_weights ? (
          <WeightsBar weights={brief.scoring_weights} />
        ) : (
          <p className="text-sm">Proposed together with the requirements.</p>
        )}
      </Section>

      <p className="mt-auto rounded-2xl bg-mist px-3.5 py-3 text-[13px] leading-normal">
        {brief.job_code
          ? `Saved as ${brief.job_code}.`
          : 'Nothing is saved or published until you confirm in the conversation.'}
      </p>

      {isReading && (
        <SidePanel
          title={`${description.title} · draft ${description.version}`}
          onClose={() => setIsReading(false)}
        >
          <div className="text-[15px]">
            <Markdown>{description.text}</Markdown>
          </div>
        </SidePanel>
      )}
    </aside>
  )
}
