import { useState } from 'react'
import { Link } from 'react-router'
import { useAuth } from '../auth/AuthContext.js'
import JobCard from '../components/dashboard/JobCard.jsx'
import RoleBox from '../components/dashboard/RoleBox.jsx'
import Skeleton from '../components/Skeleton.jsx'
import { useJobCards } from '../hooks/useJobCards.js'
import { JOB_STAGES, STAGE_GROUPS, jobStage, lastUpdated } from '../lib/jobs.js'
import { WAITING_STAGES } from '../lib/stages.js'

const WAITING = 'waiting'
const WAITING_SELECTED = 'border-warning bg-warning-soft text-warning'
// The stages shown as tiles. Archived jobs are found on the Jobs page.
const TILE_GROUPS = ['drafting', 'published', 'cvs_screened', 'interviews_scheduled']

function matches(card, filter) {
  if (filter === 'all') return card.group !== 'archived'
  if (filter === WAITING) return card.needsDecision
  return card.group === filter
}

// A number of jobs that also filters the cards below it.
function Tile({ value, label, selected, isActive, onClick }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`flex flex-1 basis-40 flex-col rounded-2xl border-[1.5px] px-5 py-4 text-left transition-colors hover:border-brand ${
        isActive ? selected : 'border-line bg-white'
      }`}
    >
      <span className={`font-display text-3xl font-extrabold ${isActive ? '' : 'text-navy'}`}>
        {value}
      </span>
      <span className="text-sm">{label}</span>
    </button>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const { cards, error } = useJobCards()
  const [filter, setFilter] = useState('all')

  const jobs = (cards ?? [])
    .map((card) => ({
      ...card,
      group: JOB_STAGES[jobStage(card.job, card.conversation)].group,
      needsDecision: Boolean(
        card.conversation && WAITING_STAGES.includes(card.conversation.stage),
      ),
    }))
    .sort((a, b) => lastUpdated(b).localeCompare(lastUpdated(a)))
  const shown = jobs.filter((card) => matches(card, filter))
  const toggle = (value) => setFilter(filter === value ? 'all' : value)
  const heading = filter === WAITING ? 'Waiting for your decision' : STAGE_GROUPS[filter]?.label
  const firstName = user.full_name.split(' ')[0]

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight">Welcome back, {firstName}</h1>
        <p className="mt-1 text-base">Start a new role or pick up where you left off.</p>
      </header>

      <RoleBox />

      <div className="flex flex-col gap-2.5">
        <p className="text-sm">Jobs by stage. Choose one to show only those jobs.</p>
        <div className="flex flex-wrap gap-3.5">
          {TILE_GROUPS.map((group) => (
            <Tile
              key={group}
              value={jobs.filter((card) => card.group === group).length}
              label={STAGE_GROUPS[group].label}
              selected={STAGE_GROUPS[group].selected}
              isActive={filter === group}
              onClick={() => toggle(group)}
            />
          ))}
          <Tile
            value={jobs.filter((card) => card.needsDecision).length}
            label="Waiting for your decision"
            selected={WAITING_SELECTED}
            isActive={filter === WAITING}
            onClick={() => toggle(WAITING)}
          />
        </div>
      </div>

      <section className="flex flex-col gap-4" aria-live="polite">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xl font-bold">{heading ?? 'Your jobs'}</h2>
          <Link to="/app/jobs" className="text-sm font-semibold text-brand hover:text-brand-dark">
            See all jobs
          </Link>
        </div>
        {error && (
          <p role="alert" className="font-semibold text-danger">
            {error}
          </p>
        )}
        {!cards && !error && (
          <div role="status" aria-label="Loading your jobs" className="grid gap-5 xl:grid-cols-2">
            <Skeleton className="h-56 rounded-card" />
            <Skeleton className="h-56 rounded-card" />
          </div>
        )}
        {cards && shown.length === 0 && (
          <p className="rounded-card border border-line bg-white p-8 text-center shadow-card">
            {filter === 'all'
              ? 'No jobs yet. Describe a role above to create your first one.'
              : 'Nothing here right now.'}
          </p>
        )}
        <div className="grid gap-5 xl:grid-cols-2">
          {shown.map((card) => (
            <JobCard key={card.key} card={card} />
          ))}
        </div>
      </section>
    </div>
  )
}
