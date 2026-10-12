import { useCallback, useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'

const REFRESH_MS = 30 * 1000

// A job's interviews and the scheduling rules. They load again every 30
// seconds, so "Starts in 8 min" and the Start button stay current, and when
// version changes. Nothing loads while jobId is empty.
export function useInterviews(jobId, version) {
  const [interviews, setInterviews] = useState(null)
  const [rules, setRules] = useState(null)
  const [now, setNow] = useState(() => new Date())
  const [error, setError] = useState('')

  const load = useCallback(() => {
    if (!jobId) return Promise.resolve()
    return apiRequest(`/jobs/${jobId}/interviews`)
      .then((loaded) => {
        setInterviews(loaded)
        setNow(new Date())
        setError('')
      })
      .catch((loadError) => setError(loadError.message))
  }, [jobId])

  useEffect(() => {
    if (!jobId) return undefined
    load()
    const timer = setInterval(load, REFRESH_MS)
    return () => clearInterval(timer)
  }, [jobId, version, load])

  useEffect(() => {
    if (!jobId) return
    apiRequest('/interviews/rules')
      .then(setRules)
      .catch(() => setRules(null))
  }, [jobId])

  return { interviews, rules, now, error, reload: load }
}
