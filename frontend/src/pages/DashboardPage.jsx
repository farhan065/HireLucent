import { useEffect, useState } from 'react'
import StatusChip from '../components/StatusChip.jsx'
import { apiRequest } from '../lib/api.js'

// Shows whether the frontend can reach the backend API.
function ApiStatus() {
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    apiRequest('/health')
      .then((health) => setState({ status: 'ok', health }))
      .catch((error) => setState({ status: 'error', message: error.message }))
  }, [])

  if (state.status === 'loading') return <StatusChip tone="neutral">Checking the server…</StatusChip>
  if (state.status === 'error') return <StatusChip tone="danger">{state.message}</StatusChip>
  return (
    <StatusChip tone="success">
      Connected to {state.health.service} v{state.health.version}
    </StatusChip>
  )
}

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-7">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight">Dashboard</h1>
          <p className="mt-1">Your open jobs and where each candidate pipeline stands.</p>
        </div>
        <ApiStatus />
      </header>

      <section className="rounded-card border border-line bg-white p-10 text-center shadow-card">
        <h2 className="text-xl font-bold">No jobs yet</h2>
        <p className="mx-auto mt-2 max-w-md leading-relaxed">
          Jobs you create will appear here with their candidate pipeline. Job creation is added
          with the job description assistant.
        </p>
      </section>
    </div>
  )
}