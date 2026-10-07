import { useCallback, useEffect, useRef, useState } from 'react'
import { apiRequest } from '../lib/api.js'

const POLL_MS = 2000

// What is running for a job (a fetch or a screening) and how the last runs
// ended. While something runs it is asked again every two seconds, so the
// progress also shows after a page reload. onFinished is called when a run ends.
export function useJobActivity(jobId, onFinished) {
  const [activity, setActivity] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(
    () =>
      apiRequest(`/jobs/${jobId}/activity`)
        .then(setActivity)
        .catch((loadError) => setError(loadError.message)),
    [jobId],
  )

  useEffect(() => {
    load()
  }, [load])

  const runningId = activity?.running?.id
  useEffect(() => {
    if (!runningId) return undefined
    const timer = setInterval(load, POLL_MS)
    return () => clearInterval(timer)
  }, [runningId, load])

  const wasRunning = useRef(false)
  useEffect(() => {
    if (wasRunning.current && !runningId) onFinished()
    wasRunning.current = Boolean(runningId)
  }, [runningId, onFinished])

  // action is "intake" (Fetch CVs) or "screen" (Screen CVs).
  async function start(action) {
    setError('')
    try {
      const task = await apiRequest(`/jobs/${jobId}/${action}`, { method: 'POST' })
      setActivity((current) => ({ ...current, running: task }))
    } catch (startError) {
      setError(startError.message)
    }
  }

  return { ...activity, isLoaded: activity !== null, error, start }
}
