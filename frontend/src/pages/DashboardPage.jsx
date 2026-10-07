import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext.js'
import JobCard from '../components/dashboard/JobCard.jsx'
import JobDetailsPanel from '../components/dashboard/JobDetailsPanel.jsx'
import RoleBox from '../components/dashboard/RoleBox.jsx'
import { apiRequest } from '../lib/api.js'
import { buildCards } from '../lib/jobs.js'
import { WAITING_STAGES } from '../lib/stages.js'

const FILTERS = {
  all: 'All jobs',
  open: 'Open jobs',
  waiting: 'Waiting for your decision',
}

function matchesFilter(card, filter) {
  if (filter === 'open') return card.job && card.job.status !== 'archived'
  if (filter === 'waiting') {
    return !card.job && WAITING_STAGES.includes(card.conversation.stage)
  }
  return true
}

// A summary number that also filters the list of jobs below it.
function SummaryTile({ value, label, isActive, onClick }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`flex flex-1 basis-44 flex-col rounded-2xl border bg-white px-5 py-4 text-left transition-colors hover:border-brand ${
        isActive ? 'border-brand ring-2 ring-tint' : 'border-line'
      }`}
    >
      <span className="font-display text-3xl font-extrabold text-navy">{value}</span>
      <span className="text-sm">{label}</span>
    </button>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')
  const [detailsFor, setDetailsFor] = useState(null)

  useEffect(() => {
    Promise.all([apiRequest('/jobs'), apiRequest('/chat/conversations')])
      .then(([jobs, conversations]) => setData({ jobs, conversations }))
      .catch((loadError) => setError(loadError.message))
  }, [])

  const cards = data ? buildCards(data.jobs, data.conversations) : []
  const shown = cards.filter((card) => matchesFilter(card, filter))
  const candidates = (data?.jobs ?? []).reduce(
    (sum, job) => sum + Object.values(job.candidate_counts).reduce((a, b) => a + b, 0),
    0,
  )
  const firstName = user.full_name.split(' ')[0]

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-3xl font-extrabold tracking-tight">Welcome back, {firstName}</h1>
        <p className="mt-1 text-base">Start a new role or pick up where you left off.</p>
      </header>

      <RoleBox />

      <div className="flex flex-wrap gap-4">
        <SummaryTile
          value={cards.filter((card) => matchesFilter(card, 'open')).length}
          label="Open jobs"
          isActive={filter === 'open'}
          onClick={() => setFilter(filter === 'open' ? 'all' : 'open')}
        />
        <SummaryTile
          value={candidates}
          label="Candidates in the pipeline"
          isActive={false}
          onClick={() => setFilter('all')}
        />
        <SummaryTile
          value={cards.filter((card) => matchesFilter(card, 'waiting')).length}
          label="Waiting for your decision"
          isActive={filter === 'waiting'}
          onClick={() => setFilter(filter === 'waiting' ? 'all' : 'waiting')}
        />
      </div>

      <section className="flex flex-col gap-4" aria-live="polite">
        <h2 className="text-xl font-bold">{FILTERS[filter]}</h2>
        {error && <p role="alert" className="font-semibold text-danger">{error}</p>}
        {!data && !error && <p role="status">Loading your jobs…</p>}
        {data && shown.length === 0 && (
          <p className="rounded-card border border-line bg-white p-8 text-center shadow-card">
            {filter === 'all'
              ? 'No jobs yet. Describe a role above to create your first one.'
              : 'Nothing here right now.'}
          </p>
        )}
        <div className="grid gap-5 xl:grid-cols-2">
          {shown.map((card) => (
            <JobCard
              key={card.key}
              job={card.job}
              conversation={card.conversation}
              onViewDetails={setDetailsFor}
            />
          ))}
        </div>
      </section>

      {detailsFor && (
        <JobDetailsPanel
          jobId={detailsFor}
          threadId={
            cards.find((card) => card.job?.id === detailsFor)?.conversation?.thread_id
          }
          onClose={() => setDetailsFor(null)}
        />
      )}
    </div>
  )
}
