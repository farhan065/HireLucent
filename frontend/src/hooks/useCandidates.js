import { useEffect, useState } from 'react'
import { apiRequest } from '../lib/api.js'

// A job's candidates, newest first. They load again when version changes,
// which the job page does after a fetch or a screening ends.
export function useCandidates(jobId, version) {
  const [candidates, setCandidates] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    apiRequest(`/jobs/${jobId}/candidates`)
      .then(setCandidates)
      .catch((loadError) => setError(loadError.message))
  }, [jobId, version])

  return { candidates, error }
}
