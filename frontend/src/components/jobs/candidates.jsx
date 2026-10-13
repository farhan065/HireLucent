import { CalendarDays, ChevronDown, ChevronRight, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { openCv } from '../../lib/jobs.js'
import StatusChip from '../StatusChip.jsx'

export const HEADING = 'px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wider'
// The same heading style inside a grid row, which has its own padding.
export const LABEL = 'text-left text-xs font-semibold uppercase tracking-wider'

// The first letters of a name, in a round badge.
export function Initials({ name }) {
  const letters = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
  return (
    <span
      aria-hidden="true"
      className="flex size-10 shrink-0 items-center justify-center rounded-full bg-tint text-sm font-bold text-brand-dark"
    >
      {letters}
    </span>
  )
}

// Opens the CV in a new browser tab.
export function ViewCvLink({ candidateId }) {
  const [error, setError] = useState('')

  async function handleClick() {
    setError('')
    try {
      await openCv(candidateId)
    } catch (openError) {
      setError(openError.message)
    }
  }

  return (
    <span className="flex flex-col items-end">
      <button
        type="button"
        onClick={handleClick}
        className="flex min-h-10 items-center gap-1.5 whitespace-nowrap text-sm font-semibold text-brand hover:text-brand-dark"
      >
        <ExternalLink className="size-4" aria-hidden="true" />
        View CV
      </button>
      {error && (
        <span role="alert" className="text-xs text-danger">
          {error}
        </span>
      )}
    </span>
  )
}

// Opens the Interviews tab, for a candidate who has an interview.
export function SeeInterviewLink() {
  return (
    <Link
      to="../interviews"
      relative="path"
      className="flex min-h-10 items-center gap-1.5 whitespace-nowrap rounded-full border-[1.5px] border-amber/30 bg-white px-3.5 text-sm font-semibold text-amber hover:bg-amber-soft"
    >
      <CalendarDays className="size-4" aria-hidden="true" />
      See interview
    </Link>
  )
}

// A white card that holds a list, with its title and a note on the right.
export function ListCard({ title, count, note, children }) {
  return (
    <section className="overflow-hidden rounded-card border border-line bg-white shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <h2 className="text-lg font-bold">
          {title} <span className="font-semibold text-body">{count}</span>
        </h2>
        {note && <span className="text-[13px]">{note}</span>}
      </div>
      <div className="overflow-x-auto">{children}</div>
    </section>
  )
}

// The last cell of a ranking row. On a phone it becomes its own line, with
// the status on the left, since the status column is hidden there.
export function RowActions({ chip, children }) {
  return (
    <div className="col-span-full flex flex-wrap items-center justify-end gap-x-2 gap-y-1 lg:col-span-1">
      {chip && (
        <span className="mr-auto lg:hidden">
          <StatusChip tone={chip.tone}>{chip.label}</StatusChip>
        </span>
      )}
      {children}
    </div>
  )
}

const UNRANKED = {
  excluded: { tone: 'warning', label: 'Excluded', color: 'text-warning', tint: 'bg-warning-soft/40' },
  screening_failed: {
    tone: 'danger',
    label: 'Could not be read',
    color: 'text-danger',
    tint: 'bg-danger-soft/40',
  },
}

// A candidate without a rank in a ranking: excluded, unreadable, or not
// screened to the end yet. "grid" is the column layout of the ranking.
// With "details", the row opens like a ranked row to show them.
export function UnrankedRow({ candidate, grid, actions, details = null, isOpen = false, onToggle }) {
  const status = UNRANKED[candidate.status] ?? {
    tone: 'info',
    label: candidate.requirement_matches
      ? 'Matched'
      : candidate.must_haves_met
        ? 'Met the must-haves'
        : 'CV read',
    color: '',
    tint: '',
  }
  const notes =
    candidate.status === 'excluded'
      ? (candidate.excluded_reason ?? '').split('\n')
      : candidate.status === 'screening_failed'
        ? [candidate.screening_error]
        : [
            `Not ${candidate.requirement_matches ? 'scored' : 'matched'} yet. Screen the CVs to finish.`,
          ]
  const Chevron = isOpen ? ChevronDown : ChevronRight
  const who = (
    <>
      <Initials name={candidate.full_name} />
      <div className="min-w-0">
        <p className="text-[15px] font-semibold text-navy">{candidate.full_name}</p>
        {notes.map((note) => (
          <p key={note} className={`text-[13px] ${status.color}`}>
            {note}
          </p>
        ))}
      </div>
    </>
  )
  return (
    <li className={`border-t border-line/60 ${status.tint}`}>
      <div className={`${grid} py-3.5`}>
        <span className="pl-3 text-lg text-line" aria-hidden="true">
          –
        </span>
        {details ? (
          <button
            type="button"
            aria-expanded={isOpen}
            onClick={onToggle}
            className="flex min-h-10 min-w-0 items-center gap-3 text-left"
          >
            <Chevron className="size-4.5 shrink-0 text-body" aria-hidden="true" />
            {who}
          </button>
        ) : (
          <div className="flex min-w-0 items-center gap-3">
            <span className="w-4.5 shrink-0" />
            {who}
          </div>
        )}
        <span className="text-sm">–</span>
        <span className="hidden text-sm lg:block">–</span>
        <div className="hidden lg:block">
          <StatusChip tone={status.tone}>{status.label}</StatusChip>
        </div>
        <RowActions chip={status}>{actions}</RowActions>
      </div>
      {details && isOpen && (
        <div className="flex flex-col gap-3 border-t border-line/60 px-5 pb-4 pt-3 lg:pl-24">
          {details}
        </div>
      )}
    </li>
  )
}

// Shown beside a ranking's title while the Show filter or the search is on.
export function FilterNote({ shown, total, onShowAll }) {
  return (
    <span className="text-[13px] font-normal">
      Showing {shown} of {total} ·{' '}
      <button
        type="button"
        onClick={onShowAll}
        className="font-semibold text-brand hover:text-brand-dark"
      >
        Show all
      </button>
    </span>
  )
}

// The single line a ranking shows when the filter leaves nobody.
export function NoMatches({ onShowAll }) {
  return (
    <li className="border-t border-line/60 px-5 py-6 text-center text-[15px]">
      No candidate matches this filter.{' '}
      <button
        type="button"
        onClick={onShowAll}
        className="font-semibold text-brand hover:text-brand-dark"
      >
        Show all
      </button>
    </li>
  )
}
