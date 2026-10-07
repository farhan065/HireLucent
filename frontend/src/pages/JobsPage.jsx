import { ArrowRight, Search, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import Button from '../components/Button.jsx'
import StatusChip from '../components/StatusChip.jsx'
import { useJobCards } from '../hooks/useJobCards.js'
import {
  JOB_STAGES,
  STAGE_GROUPS,
  formatDateTime,
  jobStage,
  lastUpdated,
  totalCandidates,
} from '../lib/jobs.js'

const LINK = 'flex min-h-10 items-center gap-1.5 text-sm font-semibold text-brand hover:text-brand-dark'
const HEADING = 'px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wider'

function FilterButton({ isActive, count, onClick, children }) {
  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={onClick}
      className={`min-h-10 rounded-full px-3.5 text-sm font-semibold ${
        isActive
          ? 'bg-navy text-white'
          : 'border-[1.5px] border-line bg-white text-body hover:border-brand'
      }`}
    >
      {children} <span className="ml-1 opacity-70">{count}</span>
    </button>
  )
}

function JobRow({ card }) {
  const { job, conversation, waiting, stage } = card
  const chatLink = conversation && `/app/assistant/${conversation.thread_id}`
  return (
    <tr className="border-t border-line/60">
      <td className="px-5 py-3.5">
        <p className="text-[15px] font-semibold text-navy">{job?.title ?? conversation.title}</p>
        <p className="mt-0.5 text-[13px]">{job ? job.job_code : 'Not saved yet'}</p>
      </td>
      <td className="px-5 py-3.5">
        <StatusChip tone={stage.tone}>{stage.label}</StatusChip>
      </td>
      <td className="px-5 py-3.5 text-[15px] text-navy">
        {totalCandidates(job)}
        {waiting > 0 && (
          <span className="ml-2 rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning">
            {waiting} new
          </span>
        )}
      </td>
      <td className="hidden px-5 py-3.5 text-sm lg:table-cell">
        {formatDateTime(lastUpdated(card))}
      </td>
      <td className="px-5 py-3.5">
        <div className="flex items-center justify-end gap-4">
          {chatLink && (
            <Link to={chatLink} className={LINK}>
              <Sparkles className="size-4" aria-hidden="true" />
              AI Agent
            </Link>
          )}
          {job && (
            <Link to={`/app/jobs/${job.id}`} className={LINK}>
              <ArrowRight className="size-4" aria-hidden="true" />
              Open job
            </Link>
          )}
        </div>
      </td>
    </tr>
  )
}

// Every job in one list, with filters by stage and a search box.
export default function JobsPage() {
  const { cards, error } = useJobCards()
  const [group, setGroup] = useState('all')
  const [search, setSearch] = useState('')

  const rows = (cards ?? [])
    .map((card) => ({ ...card, stage: JOB_STAGES[jobStage(card.job, card.conversation)] }))
    .sort((a, b) => lastUpdated(b).localeCompare(lastUpdated(a)))
  const term = search.trim().toLowerCase()
  const shown = rows.filter((row) => {
    const text = `${row.job?.title ?? row.conversation.title} ${row.job?.job_code ?? ''}`
    return (group === 'all' || row.stage.group === group) && text.toLowerCase().includes(term)
  })

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Jobs</h1>
          <p className="mt-1.5 text-base">
            Every job in one place. Open a job to work on its applications and screening.
          </p>
        </div>
        <Button to="/app/assistant" state={{ fresh: true }}>
          <Sparkles className="size-4.5" aria-hidden="true" />
          New job
        </Button>
      </header>

      {error && (
        <p role="alert" className="font-semibold text-danger">
          {error}
        </p>
      )}
      {!cards && !error && <p role="status">Loading your jobs…</p>}

      {cards && (
        <section
          aria-label="Jobs"
          className="overflow-hidden rounded-card border border-line bg-white shadow-card"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <FilterButton
                isActive={group === 'all'}
                count={rows.length}
                onClick={() => setGroup('all')}
              >
                All
              </FilterButton>
              {Object.entries(STAGE_GROUPS).map(([key, label]) => (
                <FilterButton
                  key={key}
                  isActive={group === key}
                  count={rows.filter((row) => row.stage.group === key).length}
                  onClick={() => setGroup(key)}
                >
                  {label}
                </FilterButton>
              ))}
            </div>
            <label className="flex h-11 items-center gap-2 rounded-full border-[1.5px] border-line px-3.5 focus-within:border-brand">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Search jobs</span>
              <input
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by title or code"
                className="w-48 bg-transparent text-sm text-navy outline-none"
              />
            </label>
          </div>

          {shown.length === 0 ? (
            <p className="border-t border-line/60 p-8 text-center">
              {rows.length === 0
                ? 'No jobs yet. Start one with New job.'
                : 'No jobs match this filter.'}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-mist">
                  <tr>
                    <th scope="col" className={HEADING}>Job</th>
                    <th scope="col" className={HEADING}>Stage</th>
                    <th scope="col" className={HEADING}>Applicants</th>
                    <th scope="col" className={`${HEADING} hidden lg:table-cell`}>Updated</th>
                    <th scope="col" className={HEADING}>
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((row) => (
                    <JobRow key={row.key} card={row} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
