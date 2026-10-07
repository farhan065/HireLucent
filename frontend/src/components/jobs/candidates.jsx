import { ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { apiFile } from '../../lib/api.js'

export const HEADING = 'px-5 py-2.5 text-left text-xs font-semibold uppercase tracking-wider'

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

// Opens the CV in a new browser tab. The file needs the access token, so
// it is downloaded first and then shown from memory.
export function ViewCvLink({ candidateId }) {
  const [error, setError] = useState('')

  async function handleClick() {
    setError('')
    // Opened at once, so the browser does not block it as a pop-up.
    const tab = window.open('', '_blank')
    try {
      const file = await apiFile(`/candidates/${candidateId}/cv`)
      tab.location = URL.createObjectURL(file)
    } catch (openError) {
      tab.close()
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
